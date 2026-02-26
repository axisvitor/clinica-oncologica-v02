"""
Saga Compensation Logic.

This module handles compensation (rollback) operations for saga failures,
implementing the compensating transaction pattern for distributed systems.
"""

import asyncio
import logging
from typing import Optional, List, Tuple, Any
from uuid import UUID

from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.models.enums import SagaStatus
from app.core.distributed_lock import acquire_lock, LockAcquisitionError

from .exceptions import SagaCompensationError
from .compensation_handlers import (
    compensate_message,
    compensate_flow,
    compensate_patient,
    track_compensation_failure,
)

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
        db: Any,  # AsyncSession (typed as Any for backward compat with orchestrator)
        patient_repo: Any = None,  # Kept for backward compat; inlined for async compat
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

            if compensation_errors:
                saga.status = SagaStatus.FAILED
            else:
                # Compensation completed successfully: avoid retry pipelines
                # picking this saga as a regular FAILED item again.
                saga.status = SagaStatus.COMPENSATED
                saga.error_message = None
                saga.error_type = None
                saga.failed_at = None

            try:
                await self.db.commit()
                logger.info(
                    f"Saga {saga.id}: Compensation transaction committed successfully"
                )
            except Exception as commit_error:
                logger.error(
                    f"Saga {saga.id}: CRITICAL - Compensation commit failed: "
                    f"{commit_error}",
                    exc_info=True,
                )
                await self.db.rollback()
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
        await compensate_message(self.db, saga)

    async def _compensate_flow(self, saga: PatientOnboardingSaga) -> None:
        await compensate_flow(self.db, saga)

    async def _compensate_patient(self, saga: PatientOnboardingSaga) -> None:
        await compensate_patient(self.db, saga)

    async def _track_compensation_failure(
        self, saga_id: UUID, step: int, error: Exception
    ) -> None:
        await track_compensation_failure(self.db, self.redis, saga_id, step, error)
