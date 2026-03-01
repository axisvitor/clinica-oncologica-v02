"""
Saga compensation step handlers.

This module contains standalone handlers for compensation steps.
Chain orchestration and retry coordination remain in compensation.py.
"""

from __future__ import annotations

import json
import inspect
import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes as orm_attributes

from app.core.monitoring_config import capture_exception, capture_message
from app.models.alert import Alert, AlertSeverity
from app.models.flow import PatientFlowState
from app.models.message import Message, MessageStatus
from app.models.patient import Patient
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.orchestration.saga_orchestrator.query_helpers import metadata_key_equals
from app.services import notification_service
from app.utils.timezone import now_sao_paulo

if TYPE_CHECKING:
    from app.models.patient_onboarding_saga import PatientOnboardingSaga as PatientOnboardingSagaModel

logger = logging.getLogger(__name__)


def _sync_select_execute(db, statement):
    entity = statement.column_descriptions[0].get("entity")
    query = db.query(entity)

    where_criteria = tuple(getattr(statement, "_where_criteria", ()))
    if where_criteria:
        query = query.filter(*where_criteria)

    rows = query.all() if hasattr(query, "all") else None
    if not isinstance(rows, list):
        first_row = query.first() if hasattr(query, "first") else None
        rows = [first_row] if first_row is not None else []

    class _ScalarResult:
        def __init__(self, items):
            self._items = items

        def first(self):
            return self._items[0] if self._items else None

        def all(self):
            return self._items

    class _QueryResult:
        def __init__(self, items):
            self._items = items

        def scalars(self):
            return _ScalarResult(self._items)

    return _QueryResult(rows)


async def _db_execute(db, statement):
    if not isinstance(db, AsyncSession) and hasattr(db, "query"):
        return _sync_select_execute(db, statement)
    result = db.execute(statement)
    if inspect.isawaitable(result):
        return await result
    return result


async def _db_flush(db) -> None:
    result = db.flush()
    if inspect.isawaitable(result):
        await result


async def _db_delete(db, obj) -> None:
    result = db.delete(obj)
    if inspect.isawaitable(result):
        await result


async def compensate_message(
    db: AsyncSession, saga: PatientOnboardingSagaModel
) -> None:
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

        result = await _db_execute(
            db,
            select(Message).filter(
                Message.patient_id == saga.patient_id,
                metadata_key_equals(
                    Message.message_metadata,
                    "saga_id",
                    str(saga.id),
                ),
                Message.status != MessageStatus.CANCELLED,
            )
        )
        messages = result.scalars().all()

        for message in messages:
            message.status = MessageStatus.CANCELLED
            message.message_metadata = {
                **(message.message_metadata or {}),
                "cancelled_by": "saga_compensation",
                "cancelled_at": now_sao_paulo().isoformat(),
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


async def compensate_flow(db: AsyncSession, saga: PatientOnboardingSagaModel) -> None:
    """
    Compensate Step 3: Delete or deactivate flow state.

    FIX P1-008: Made idempotent - checks if already compensated.
    """
    try:
        compensated_steps = (
            saga.step_data.get("compensated_steps", []) if saga.step_data else []
        )
        if "flow" in compensated_steps:
            logger.info(f"Saga {saga.id}: Flow compensation already done, skipping")
            return

        if not saga.patient_id:
            logger.info(f"Saga {saga.id}: No patient_id to compensate flow")
            saga.step_data = {
                **(saga.step_data or {}),
                "compensated_steps": compensated_steps + ["flow"],
            }
            return

        result = await _db_execute(
            db,
            select(PatientFlowState).filter(PatientFlowState.patient_id == saga.patient_id)
        )
        flow_states = result.scalars().all()

        for flow_state in flow_states:
            await _db_delete(db, flow_state)

        saga.step_data = {
            **(saga.step_data or {}),
            "compensated_steps": compensated_steps + ["flow"],
        }

        if flow_states:
            logger.info(f"Saga {saga.id}: Deleted {len(flow_states)} flow state(s)")
        else:
            logger.info(
                f"Saga {saga.id}: No flow states found to compensate (or already done)"
            )

    except Exception as e:
        logger.error(f"Saga {saga.id}: Flow compensation error: {e}")
        raise


async def compensate_patient(
    db: AsyncSession, saga: PatientOnboardingSagaModel
) -> None:
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
            logger.info(f"Saga {saga.id}: Patient compensation already done, skipping")
            return

        if not saga.patient_id:
            logger.info(f"Saga {saga.id}: No patient_id to compensate")
            saga.step_data = {
                **(saga.step_data or {}),
                "compensated_steps": compensated_steps + ["patient"],
            }
            return

        result = await _db_execute(
            db, select(Patient).filter(Patient.id == saga.patient_id)
        )
        patient = result.scalars().first()

        if not patient:
            logger.info(f"Saga {saga.id}: Patient {saga.patient_id} already deleted")
            saga.step_data = {
                **(saga.step_data or {}),
                "compensated_steps": compensated_steps + ["patient"],
            }
            return

        await _db_delete(db, patient)

        saga.step_data = {
            **(saga.step_data or {}),
            "compensated_steps": compensated_steps + ["patient"],
        }

        logger.info(f"Saga {saga.id}: Deleted patient {saga.patient_id}")

    except Exception as e:
        logger.error(f"Saga {saga.id}: Patient compensation error: {e}")
        raise


async def track_compensation_failure(
    db: AsyncSession, redis: Any, saga_id: UUID, step: int, error: Exception
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
        if redis:
            failure_key = f"saga:compensation_failure:{saga_id}"
            failure_data = {
                "saga_id": str(saga_id),
                "step": step,
                "error": str(error),
                "error_type": type(error).__name__,
                "timestamp": now_sao_paulo().isoformat(),
            }
            redis.setex(failure_key, 86400 * 7, json.dumps(failure_data))
            logger.warning(f"Compensation failure tracked in Redis: {failure_key}")

        result = await _db_execute(
            db,
            select(PatientOnboardingSaga).filter(PatientOnboardingSaga.id == saga_id)
        )
        saga = result.scalars().first()

        patient_id = saga.patient_id if saga else None

        if patient_id:
            alert = Alert(
                patient_id=patient_id,
                alert_type="SAGA_COMPENSATION_FAILURE",
                severity=AlertSeverity.HIGH,
                description=(
                    f"Saga compensation failed at step {step}. "
                    f"Error: {str(error)[:500]}. "
                    "Manual intervention required."
                ),
                data={
                    "saga_id": str(saga_id),
                    "failed_step": step,
                    "error_type": type(error).__name__,
                    "error_message": str(error)[:1000],
                },
                acknowledged=False,
            )
            db.add(alert)
            logger.info(
                f"Created SAGA_COMPENSATION_FAILURE alert for patient {patient_id}"
            )

            try:
                notification_service_instance = (
                    notification_service.get_notification_service()
                )
                logger.info(
                    "Sending compensation failure alert notification",
                    extra={
                        "saga_id": str(saga_id),
                        "patient_id": str(patient_id),
                        "failed_step": step,
                        "error_type": type(error).__name__,
                    },
                )
                await notification_service_instance.send_alert(
                    alert_type="SAGA_COMPENSATION_FAILURE",
                    title=(f"Compensacao de Saga Falhou - Patient {patient_id}"),
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
                from . import compensation as compensation_module

                compensation_module.logger.error(
                    "Failed to send compensation failure alert notification"
                )

            p_result = await _db_execute(
                db, select(Patient).filter(Patient.id == patient_id)
            )
            patient = p_result.scalars().first()
            if patient:
                if patient.patient_data is None:
                    patient.patient_data = {}
                patient.patient_data["quarantine"] = True
                patient.patient_data["quarantine_reason"] = "saga_compensation_failure"
                patient.patient_data["quarantine_at"] = now_sao_paulo().isoformat()
                patient.patient_data["saga_id"] = str(saga_id)
                orm_attributes.flag_modified(patient, "patient_data")
                logger.warning(
                    f"Patient {patient_id} quarantined due to compensation failure"
                )

            await _db_flush(db)

        try:
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
            capture_exception(sentry_error)

    except Exception as tracking_error:
        logger.error(
            f"Failed to track compensation failure: {tracking_error}",
            exc_info=True,
        )


__all__ = [
    "compensate_message",
    "compensate_flow",
    "compensate_patient",
    "track_compensation_failure",
]
