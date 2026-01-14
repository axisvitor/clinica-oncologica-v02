"""
Saga Compensation Logic.

This module handles compensation (rollback) operations for saga failures,
implementing the compensating transaction pattern for distributed systems.
"""

import asyncio
import json
import logging
from typing import Optional, List, Tuple, Any
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.models.message import Message, MessageStatus
from app.models.flow import PatientFlowState
from app.models.enums import SagaStatus
from app.repositories.patient import PatientRepository
from app.core.distributed_lock import acquire_lock, LockAcquisitionError

from .exceptions import SagaCompensationError

logger = logging.getLogger(__name__)


class SagaCompensator:
    """
    Handles saga compensation (rollback) operations.

    Implements the compensating transaction pattern with:
    - Distributed locking to prevent concurrent compensations
    - Retry logic with exponential backoff
    - Idempotent compensation steps
    - Error tracking for monitoring
    """

    def __init__(
        self,
        db: Session,
        patient_repo: PatientRepository,
        redis_client: Optional[Any] = None,
    ):
        self.db = db
        self.patient_repo = patient_repo
        self.redis = redis_client

    async def compensate_saga(self, saga: PatientOnboardingSaga) -> None:
        """
        Execute compensation steps in reverse order with atomic transaction.

        QW-002: Enhanced error propagation and tracking for compensation failures.

        ATOMIC COMPENSATION:
        - All compensation steps are executed within a single transaction
        - If any step fails with retry exhausted, we rollback and track failure
        - Uses distributed lock to prevent concurrent compensation
        - Each step has its own retry logic with exponential backoff

        Args:
            saga: The saga to compensate

        Raises:
            SagaCompensationError: If compensation fails
        """
        lock_key = f"saga:compensate:{saga.id}"
        try:
            async with acquire_lock(lock_key, timeout=5.0, ttl=120):
                await self._compensate_saga_internal(saga)
        except LockAcquisitionError as lock_error:
            logger.error(
                f"Saga {saga.id}: Failed to acquire compensation lock - "
                "concurrent compensation in progress",
                exc_info=True,
            )
            raise SagaCompensationError(
                f"Saga {saga.id}: Cannot acquire compensation lock (concurrent operation)",
                saga_id=saga.id,
                original_error=lock_error,
            )

    async def _compensate_saga_internal(
        self, saga: PatientOnboardingSaga
    ) -> None:
        """Internal compensation logic within lock context."""
        logger.info(f"Compensating saga {saga.id} from step {saga.current_step}")
        saga.status = SagaStatus.COMPENSATING

        compensation_errors: List[Tuple[int, Exception]] = []

        try:
            # Step 4 Compensation: Mark Message as Cancelled
            if saga.current_step >= 4:
                await self._compensate_step_with_retry(
                    saga=saga,
                    step_num=4,
                    step_name="compensate_message",
                    compensate_fn=self._compensate_message,
                    compensation_errors=compensation_errors,
                )

            # Step 3 Compensation: Delete/Deactivate Flow
            if saga.current_step >= 3:
                await self._compensate_step_with_retry(
                    saga=saga,
                    step_num=3,
                    step_name="compensate_flow",
                    compensate_fn=self._compensate_flow,
                    compensation_errors=compensation_errors,
                )

            # Step 1 Compensation: Delete Patient
            if saga.current_step >= 1 and saga.patient_id:
                await self._compensate_step_with_retry(
                    saga=saga,
                    step_num=1,
                    step_name="compensate_patient",
                    compensate_fn=self._compensate_patient,
                    compensation_errors=compensation_errors,
                )

            saga.status = SagaStatus.FAILED

            try:
                self.db.commit()
                logger.info(
                    f"Saga {saga.id}: Compensation transaction committed successfully"
                )
            except Exception as commit_error:
                logger.error(
                    f"Saga {saga.id}: CRITICAL - Compensation commit failed: "
                    f"{commit_error}",
                    exc_info=True,
                )
                self.db.rollback()
                await self._track_compensation_failure(saga.id, 0, commit_error)
                raise SagaCompensationError(
                    f"Saga {saga.id}: Failed to commit compensation transaction",
                    saga_id=saga.id,
                    original_error=commit_error,
                )

            if compensation_errors:
                error_details = "; ".join(
                    [f"{step}: {str(err)}" for step, err in compensation_errors]
                )
                raise SagaCompensationError(
                    f"Saga {saga.id} compensation failed with "
                    f"{len(compensation_errors)} error(s): {error_details}",
                    saga_id=saga.id,
                    original_error=compensation_errors[0][1],
                )

        except SagaCompensationError:
            raise
        except Exception as e:
            logger.error(f"Critical error during compensation: {e}", exc_info=True)
            await self._track_compensation_failure(saga.id, 0, e)
            raise SagaCompensationError(
                f"Critical compensation error for saga {saga.id}: {str(e)}",
                saga_id=saga.id,
                original_error=e,
            )

    async def _compensate_step_with_retry(
        self,
        saga: PatientOnboardingSaga,
        step_num: int,
        step_name: str,
        compensate_fn,
        compensation_errors: List[Tuple[int, Exception]],
        max_retries: int = 3,
    ) -> None:
        """
        Execute a compensation step with retry logic.

        QW-002: Implements exponential backoff for transient failures.

        Args:
            saga: The saga being compensated
            step_num: Step number for logging
            step_name: Name of the compensation step
            compensate_fn: Async function to execute for compensation
            compensation_errors: List to append errors to
            max_retries: Maximum number of retry attempts
        """
        last_error = None
        for attempt in range(max_retries):
            try:
                await compensate_fn(saga)
                saga.add_log_entry(step_num, step_name, "compensated")
                logger.info(
                    f"Saga {saga.id}: {step_name} compensation succeeded "
                    f"on attempt {attempt + 1}"
                )
                return
            except Exception as e:
                last_error = e
                # Backoff: 1s, 2s, 4s (spec: 1/2/4s)
                wait_time = (2**attempt) * 1.0
                logger.warning(
                    f"Saga {saga.id}: {step_name} compensation attempt "
                    f"{attempt + 1}/{max_retries} failed: {e}. "
                    f"Retrying in {wait_time}s..."
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)


        logger.error(
            f"Saga {saga.id}: {step_name} compensation failed after "
            f"{max_retries} attempts"
        )
        saga.add_log_entry(step_num, step_name, "compensation_failed", str(last_error))
        compensation_errors.append((step_num, last_error))
        await self._track_compensation_failure(saga.id, step_num, last_error)

    async def _compensate_message(self, saga: PatientOnboardingSaga) -> None:
        """
        Compensate Step 4: Mark welcome message as cancelled.

        Note: WhatsApp messages cannot be unsent, but we mark as cancelled
        in our database for audit trail and to prevent retries.

        FIX P1-008: Made idempotent - checks if already compensated.
        """
        try:
            compensated_steps = (
                saga.step_data.get("compensated_steps", []) if saga.step_data else []
            )
            if "message" in compensated_steps:
                logger.info(
                    f"Saga {saga.id}: Message compensation already done, skipping"
                )
                return

            messages = (
                self.db.query(Message)
                .filter(
                    Message.patient_id == saga.patient_id,
                    Message.message_metadata["saga_id"].astext == str(saga.id),
                    Message.status != MessageStatus.CANCELLED,
                )
                .all()
            )

            for message in messages:
                message.status = MessageStatus.CANCELLED
                message.message_metadata = {
                    **(message.message_metadata or {}),
                    "cancelled_by": "saga_compensation",
                    "cancelled_at": datetime.now(timezone.utc).isoformat(),
                }

            saga.step_data = {
                **(saga.step_data or {}),
                "compensated_steps": compensated_steps + ["message"],
            }

            if messages:
                logger.info(
                    f"Saga {saga.id}: Marked {len(messages)} message(s) as cancelled"
                )
            else:
                logger.info(
                    f"Saga {saga.id}: No messages found to compensate (or already done)"
                )

        except Exception as e:
            logger.error(f"Saga {saga.id}: Message compensation error: {e}")
            raise

    async def _compensate_flow(self, saga: PatientOnboardingSaga) -> None:
        """
        Compensate Step 3: Delete or deactivate flow state.

        FIX P1-008: Made idempotent - checks if already compensated.
        """
        try:
            compensated_steps = (
                saga.step_data.get("compensated_steps", []) if saga.step_data else []
            )
            if "flow" in compensated_steps:
                logger.info(
                    f"Saga {saga.id}: Flow compensation already done, skipping"
                )
                return

            if not saga.patient_id:
                logger.info(f"Saga {saga.id}: No patient_id to compensate flow")
                saga.step_data = {
                    **(saga.step_data or {}),
                    "compensated_steps": compensated_steps + ["flow"],
                }
                return

            flow_states = (
                self.db.query(PatientFlowState)
                .filter(PatientFlowState.patient_id == saga.patient_id)
                .all()
            )

            for flow_state in flow_states:
                self.db.delete(flow_state)

            saga.step_data = {
                **(saga.step_data or {}),
                "compensated_steps": compensated_steps + ["flow"],
            }

            if flow_states:
                logger.info(
                    f"Saga {saga.id}: Deleted {len(flow_states)} flow state(s)"
                )
            else:
                logger.info(
                    f"Saga {saga.id}: No flow states found to compensate (or already done)"
                )

        except Exception as e:
            logger.error(f"Saga {saga.id}: Flow compensation error: {e}")
            raise

    async def _compensate_patient(self, saga: PatientOnboardingSaga) -> None:
        """
        Compensate Step 1: Delete patient record.

        This is a hard delete since the patient was never fully onboarded.

        FIX P1-008: Made idempotent - checks if already compensated.
        """
        try:
            compensated_steps = (
                saga.step_data.get("compensated_steps", []) if saga.step_data else []
            )
            if "patient" in compensated_steps:
                logger.info(
                    f"Saga {saga.id}: Patient compensation already done, skipping"
                )
                return

            if not saga.patient_id:
                logger.info(f"Saga {saga.id}: No patient_id to compensate")
                saga.step_data = {
                    **(saga.step_data or {}),
                    "compensated_steps": compensated_steps + ["patient"],
                }
                return

            patient = self.patient_repo.get_by_id(saga.patient_id)
            if not patient:
                logger.info(
                    f"Saga {saga.id}: Patient {saga.patient_id} already deleted"
                )
                saga.step_data = {
                    **(saga.step_data or {}),
                    "compensated_steps": compensated_steps + ["patient"],
                }
                return

            self.db.delete(patient)

            saga.step_data = {
                **(saga.step_data or {}),
                "compensated_steps": compensated_steps + ["patient"],
            }

            logger.info(f"Saga {saga.id}: Deleted patient {saga.patient_id}")

        except Exception as e:
            logger.error(f"Saga {saga.id}: Patient compensation error: {e}")
            raise

    async def _track_compensation_failure(
        self, saga_id: UUID, step: int, error: Exception
    ) -> None:
        """
        Track compensation failures for audit and manual recovery.

        QW-002: Proper error tracking for compensation failures.
        P1-FIX: Creates Alert record and quarantines affected patient.

        Args:
            saga_id: UUID of the saga
            step: Step number that failed
            error: Exception that occurred
        """
        try:
            # Track in Redis (7 days retention)
            if self.redis:
                failure_key = f"saga:compensation_failure:{saga_id}"
                failure_data = {
                    "saga_id": str(saga_id),
                    "step": step,
                    "error": str(error),
                    "error_type": type(error).__name__,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                self.redis.setex(
                    failure_key, 86400 * 7, json.dumps(failure_data)  # 7 days
                )
                logger.warning(
                    f"Compensation failure tracked in Redis: {failure_key}"
                )

            # Fetch saga to get patient_id
            from app.models.patient_onboarding_saga import PatientOnboardingSaga
            saga = (
                self.db.query(PatientOnboardingSaga)
                .filter(PatientOnboardingSaga.id == saga_id)
                .first()
            )

            patient_id = saga.patient_id if saga else None

            # Create Alert record with HIGH severity
            if patient_id:
                from app.models.alert import Alert, AlertSeverity

                alert = Alert(
                    patient_id=patient_id,
                    alert_type="SAGA_COMPENSATION_FAILURE",
                    severity=AlertSeverity.HIGH,
                    description=(
                        f"Saga compensation failed at step {step}. "
                        f"Error: {str(error)[:500]}. "
                        f"Manual intervention required."
                    ),
                    data={
                        "saga_id": str(saga_id),
                        "failed_step": step,
                        "error_type": type(error).__name__,
                        "error_message": str(error)[:1000],
                    },
                    acknowledged=False,
                )
                self.db.add(alert)
                logger.info(
                    f"Created SAGA_COMPENSATION_FAILURE alert for patient {patient_id}"
                )

                # Notify team without blocking compensation tracking.
                try:
                    from app.services.notification_service import (
                        get_notification_service,
                    )

                    notification_service = get_notification_service()
                    logger.info(
                        "Sending compensation failure alert notification",
                        extra={
                            "saga_id": str(saga_id),
                            "patient_id": str(patient_id),
                            "failed_step": step,
                            "error_type": type(error).__name__,
                        },
                    )
                    await notification_service.send_alert(
                        alert_type="SAGA_COMPENSATION_FAILURE",
                        title=(
                            f"Compensacao de Saga Falhou - Patient {patient_id}"
                        ),
                        description=(
                            "Saga compensation failure detected. "
                            f"Saga ID: {saga_id}. "
                            f"Patient ID: {patient_id}. "
                            f"Failed step: {step}. "
                            f"Error: {str(error)[:500]}"
                        ),
                        severity="high",
                        context={
                            "saga_id": str(saga_id),
                            "patient_id": str(patient_id),
                            "failed_step": step,
                            "error_type": type(error).__name__,
                            "error_message": str(error)[:1000],
                        },
                    )
                    logger.info(
                        "Compensation failure alert notification sent",
                        extra={
                            "saga_id": str(saga_id),
                            "patient_id": str(patient_id),
                            "alert_type": "SAGA_COMPENSATION_FAILURE",
                        },
                    )
                except Exception as notification_error:
                    logger.error(
                        "Failed to send compensation failure alert notification",
                        extra={
                            "saga_id": str(saga_id),
                            "patient_id": str(patient_id),
                            "error": str(notification_error),
                        },
                        exc_info=True,
                    )

                # Quarantine patient by setting patient_data['quarantine']=true
                from app.models.patient import Patient
                from sqlalchemy.orm.attributes import flag_modified

                patient = (
                    self.db.query(Patient)
                    .filter(Patient.id == patient_id)
                    .first()
                )
                if patient:
                    if patient.patient_data is None:
                        patient.patient_data = {}
                    patient.patient_data["quarantine"] = True
                    patient.patient_data["quarantine_reason"] = (
                        "saga_compensation_failure"
                    )
                    patient.patient_data["quarantine_at"] = (
                        datetime.now(timezone.utc).isoformat()
                    )
                    patient.patient_data["saga_id"] = str(saga_id)
                    flag_modified(patient, "patient_data")
                    logger.warning(
                        f"Patient {patient_id} quarantined due to compensation failure"
                    )

                # Flush changes (will be committed by caller)
                self.db.flush()

            # Send Sentry notification
            try:
                from app.core.monitoring_config import capture_message, capture_exception
                capture_message(
                    f"Saga compensation failure: {saga_id}",
                    level="error",
                    extra={
                        "saga_id": str(saga_id),
                        "patient_id": str(patient_id) if patient_id else None,
                        "step": step,
                        "error": str(error),
                        "error_type": type(error).__name__,
                    },
                )
            except Exception as sentry_error:
                logger.error(f"Failed to send Sentry notification: {sentry_error}")

        except Exception as tracking_error:
            logger.error(
                f"Failed to track compensation failure: {tracking_error}",
                exc_info=True,
            )
