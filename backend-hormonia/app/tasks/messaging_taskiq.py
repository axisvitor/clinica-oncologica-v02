"""
Taskiq messaging tasks — async-native replacements for Celery messaging tasks (M009-S02).

This module contains the Taskiq version of send_scheduled_message, the most complex
messaging task. The Celery original in messaging.py remains untouched for backward
compatibility during migration.

Key translation patterns from Celery → Taskiq:
  - run_async() bridge removed: task body is directly async
  - self.retry(countdown=) → raise exception, SmartRetryMiddleware handles retry
  - self.request.retries → context.message.labels.get('_retries', 0)
  - get_scoped_session() (sync) → AsyncSession via TaskiqDepends (main flow)
  - DLQ writes still use sync DLQService via get_scoped_session() (pragmatic)
  - Structured logging via log_task_start/success/error from taskiq_base
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from taskiq import Context, TaskiqDepends

from app.models.message import (
    DeliveryStatus,
    Message,
    MessageDirection,
    MessageStatus,
    MessageType,
)
from app.services.unified_whatsapp_service import create_unified_whatsapp_service
from app.taskiq_broker import broker
from app.tasks.taskiq_base import DbSession, log_task_error, log_task_start, log_task_success
from app.utils.timezone import now_sao_paulo

# Pure helper functions — imported from Celery module (no duplication).
from app.tasks.messaging import (
    _build_idempotency_key,
    _compute_next_reminder_time,
    _schedule_next_reminder,
)

logger = logging.getLogger("app.tasks.messaging_taskiq")


@broker.task(retry_on_error=True, max_retries=3, delay=2)
async def send_scheduled_message(
    message_id: str,
    db: AsyncSession = DbSession,
    context: Context = TaskiqDepends(),
) -> dict[str, Any]:
    """Send a scheduled message to a patient.

    Async-native Taskiq replacement for the Celery send_scheduled_message task.
    Uses SmartRetryMiddleware for retry logic (exponential backoff with jitter).

    The short base delay (2s) handles the "message not found" race condition
    where the saga commit hasn't propagated yet. SmartRetryMiddleware applies
    exponential backoff on top: 2s → 4s → 8s (capped by max_delay_exponent).

    Args:
        message_id: UUID string of the message to send.
        db: Async database session (injected by TaskiqDepends).
        context: Taskiq context (provides retry count via message labels).

    Returns:
        Dict with result details (success, message_id, patient_id, etc.).

    Raises:
        RuntimeError: If message not found and retries not exhausted (triggers retry).
        Exception: Re-raised after updating message metadata (triggers retry or DLQ).
    """
    start_time = log_task_start("send_scheduled_message", message_id=message_id)

    message_uuid = UUID(message_id)
    retries = int(context.message.labels.get("_retries", 0))

    try:
        # ---------------------------------------------------------------
        # Atomic claim: only one worker transitions eligible → SENDING.
        # Accept SCHEDULED for backward compat with legacy rows.
        # ---------------------------------------------------------------
        claim = await db.execute(
            update(Message)
            .where(
                Message.id == message_uuid,
                Message.status.in_([MessageStatus.PENDING, MessageStatus.SCHEDULED]),
            )
            .values(
                status=MessageStatus.SENDING,
                delivery_status=DeliveryStatus.SENDING,
            )
            .execution_options(synchronize_session=False)
        )
        await db.commit()

        if int(claim.rowcount or 0) == 0:
            # Message may not exist or already claimed/processed.
            status_stmt = select(Message.status).where(Message.id == message_uuid)
            status_result = await db.execute(status_stmt)
            current_status = status_result.scalar_one_or_none()

            if current_status is None:
                # Not found — likely saga commit lag. Retry via SmartRetryMiddleware.
                if retries >= 3:
                    logger.error(
                        "Message %s not found after %d retries, giving up",
                        message_id,
                        retries,
                    )
                    log_task_error(
                        "send_scheduled_message",
                        RuntimeError("Message not found after retries"),
                        start_time,
                        message_id=message_id,
                        retries=retries,
                    )
                    return {
                        "success": False,
                        "message_id": message_id,
                        "error": "Message not found after retries",
                    }
                raise RuntimeError(
                    f"Message {message_id} not found (attempt {retries + 1}/3), will retry"
                )

            # Already claimed/processed by another worker.
            logger.info(
                "Message %s already processed with status: %s",
                message_id,
                current_status.value,
            )
            log_task_success(
                "send_scheduled_message",
                start_time,
                message_id=message_id,
                already_processed=True,
                status=current_status.value,
            )
            return {
                "success": True,
                "message_id": message_id,
                "message": "Message already processed",
                "status": current_status.value,
            }

        # ---------------------------------------------------------------
        # Load message with patient relationship.
        # ---------------------------------------------------------------
        stmt = (
            select(Message)
            .options(selectinload(Message.patient))
            .where(Message.id == message_uuid)
        )
        result = await db.execute(stmt)
        message = result.scalar_one_or_none()

        if not message:
            # Shouldn't happen after successful claim, but defensive.
            raise RuntimeError(f"Message {message_id} not found after claim")

        # Double-check: another process may have finalized before our load.
        if message.status != MessageStatus.SENDING:
            log_task_success(
                "send_scheduled_message",
                start_time,
                message_id=message_id,
                already_processed=True,
                status=message.status.value,
            )
            return {
                "success": True,
                "message_id": message_id,
                "message": "Message already processed",
                "status": message.status.value,
            }

        # ---------------------------------------------------------------
        # Validation checks — non-retriable failures route to DLQ.
        # ---------------------------------------------------------------
        patient = message.patient

        if not patient:
            message.status = MessageStatus.FAILED
            message.delivery_status = DeliveryStatus.FAILED
            message.failure_reason = "Patient not found"
            await db.commit()

            _route_to_dlq(
                message_id=message_uuid,
                patient_id=message.patient_id,
                error_message="Patient not found",
                error_type="ValidationError",
                flow_context=(message.message_metadata or {}).get("flow_context", {}),
                message_type=message.type,
            )
            log_task_error(
                "send_scheduled_message",
                ValueError("Patient not found"),
                start_time,
                message_id=message_id,
            )
            return {
                "success": False,
                "message_id": message_id,
                "error": "Patient not found",
                "non_retriable": True,
            }

        # SAFETY: Do not send messages to deleted patients.
        if patient.deleted_at:
            message.status = MessageStatus.CANCELLED
            message.failure_reason = "Patient deleted"
            await db.commit()

            logger.warning("Message %s cancelled: patient deleted", message_id)
            log_task_success(
                "send_scheduled_message",
                start_time,
                message_id=message_id,
                cancelled=True,
            )
            return {
                "success": False,
                "message_id": message_id,
                "error": "Patient deleted",
                "status": "cancelled",
            }

        if not patient.phone:
            message.status = MessageStatus.FAILED
            message.delivery_status = DeliveryStatus.FAILED
            message.failure_reason = "Patient phone number missing"
            await db.commit()

            _route_to_dlq(
                message_id=message_uuid,
                patient_id=message.patient_id,
                error_message="Patient phone number missing",
                error_type="ValidationError",
                flow_context=(message.message_metadata or {}).get("flow_context", {}),
                message_type=message.type,
            )
            log_task_error(
                "send_scheduled_message",
                ValueError("Patient phone number missing"),
                start_time,
                message_id=message_id,
                patient_id=str(message.patient_id),
            )
            return {
                "success": False,
                "message_id": message_id,
                "error": "Patient phone number missing",
                "non_retriable": True,
            }

        # ---------------------------------------------------------------
        # Send via WhatsApp.
        # ---------------------------------------------------------------
        whatsapp_service = create_unified_whatsapp_service(db)
        success = await whatsapp_service.send_message(message)

        if success:
            message.status = MessageStatus.SENT
            message.delivery_status = DeliveryStatus.SENT
            message.sent_at = now_sao_paulo()

            # Schedule next reminder (recurring messages).
            try:
                await _schedule_next_reminder(message, db)
            except Exception as sched_exc:
                logger.warning(
                    "Failed to schedule next reminder for message %s: %s",
                    message_id,
                    sched_exc,
                    extra={"message_id": message_id},
                )

            await db.commit()

            log_task_success(
                "send_scheduled_message",
                start_time,
                message_id=message_id,
                patient_id=str(message.patient_id),
            )
            return {
                "success": True,
                "message_id": message_id,
                "patient_id": str(message.patient_id),
                "sent_at": now_sao_paulo().isoformat(),
            }

        # WhatsApp service returned failure (non-exception).
        message.status = MessageStatus.PENDING
        message.delivery_status = DeliveryStatus.QUEUED
        await db.commit()

        raise RuntimeError("WhatsApp service returned failure")

    except Exception as exc:
        # ---------------------------------------------------------------
        # Exception handler — update message metadata, then re-raise
        # so SmartRetryMiddleware decides whether to retry or give up.
        # ---------------------------------------------------------------
        try:
            # Refresh message in case the session is dirty from a failed commit.
            await db.rollback()
            msg_result = await db.execute(
                select(Message).where(Message.id == message_uuid)
            )
            message_obj = msg_result.scalar_one_or_none()

            if message_obj and message_obj.status == MessageStatus.SENDING:
                message_obj.retry_count = int(message_obj.retry_count or 0) + 1
                message_obj.last_retry_at = now_sao_paulo()

                metadata = dict(message_obj.message_metadata or {})
                metadata["last_retry_error"] = str(exc)
                metadata["last_retry_trigger"] = "send_scheduled_message"
                message_obj.message_metadata = metadata

                if retries >= 3:
                    # Retries exhausted — mark FAILED and route to DLQ.
                    message_obj.status = MessageStatus.FAILED
                    message_obj.delivery_status = DeliveryStatus.FAILED
                    message_obj.failure_reason = str(exc)
                    await db.commit()

                    _route_to_dlq(
                        message_id=message_uuid,
                        patient_id=message_obj.patient_id,
                        error_message=str(exc),
                        error_type=type(exc).__name__,
                        flow_context=(message_obj.message_metadata or {}).get(
                            "flow_context", {}
                        ),
                        message_type=message_obj.type,
                        failure_reason_key="MAX_RETRIES_EXCEEDED",
                        extra_payload={
                            "taskiq_retries_exhausted": 3,
                            "last_error": str(exc),
                        },
                    )
                else:
                    # Reset to PENDING so next retry can claim it.
                    message_obj.status = MessageStatus.PENDING
                    message_obj.delivery_status = DeliveryStatus.QUEUED
                    await db.commit()

        except Exception as meta_exc:
            logger.error(
                "Failed to update retry state for message %s: %s",
                message_id,
                meta_exc,
            )

        log_task_error(
            "send_scheduled_message",
            exc,
            start_time,
            message_id=message_id,
            retries=retries,
        )
        raise


# ---------------------------------------------------------------------------
# DLQ routing helper — uses sync DLQService (pragmatic, per plan).
# ---------------------------------------------------------------------------

def _route_to_dlq(
    *,
    message_id: UUID,
    patient_id: UUID | None,
    error_message: str,
    error_type: str,
    flow_context: dict[str, Any],
    message_type: Any,
    failure_reason_key: str = "UNKNOWN",
    extra_payload: dict[str, Any] | None = None,
) -> None:
    """Route a failed message to the Dead Letter Queue using sync DLQService.

    Uses a fresh sync session (get_scoped_session) because DLQService is sync-only.
    This is the pragmatic approach — DLQ writes are rare exception-path operations.
    """
    if not patient_id:
        logger.warning(
            "Skipping DLQ routing for message %s: patient_id is None", message_id
        )
        return

    try:
        from app.database import get_scoped_session
        from app.models.failed_message import FailureReason
        from app.services.dlq.service import DLQService

        failure_reason = getattr(FailureReason, failure_reason_key, FailureReason.UNKNOWN)

        payload: dict[str, Any] = {
            "message_id": str(message_id),
            "patient_id": str(patient_id),
            "message_type": str(
                getattr(message_type, "value", message_type) or "unknown"
            ),
            "flow_context": flow_context,
            "original_status": "failed",
            "non_retriable": failure_reason_key == "UNKNOWN",
        }
        if extra_payload:
            payload.update(extra_payload)

        with get_scoped_session() as sync_db:
            dlq_service = DLQService(sync_db)
            dlq_service.add_to_dlq(
                message_id=message_id,
                patient_id=patient_id,
                error_message=error_message,
                error_type=error_type,
                payload=payload,
                failure_reason=failure_reason,
            )

        logger.info("Message %s routed to DLQ: %s", message_id, error_message)
    except Exception as dlq_error:
        logger.error(
            "Failed to route message %s to DLQ: %s",
            message_id,
            dlq_error,
            exc_info=True,
        )
