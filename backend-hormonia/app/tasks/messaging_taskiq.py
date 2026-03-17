"""
Taskiq messaging tasks — async-native replacements for Celery messaging tasks (M009-S02).

All 9 messaging tasks migrated from Celery to Taskiq:
  1. send_scheduled_message      — on-demand, retry-enabled
  2. process_scheduled_messages  — 60s interval, dispatches due messages
  3. retry_failed_messages       — 300s interval, retries failed sends
  4. send_bulk_messages          — on-demand, ETA dispatch via schedule_task_at
  5. cleanup_old_messages        — 86400s interval, archives old messages
  6. generate_message_analytics  — 3600s interval, computes delivery stats
  7. process_whatsapp_dlq        — 600s interval, auto-retries transient DLQ failures
  8. process_dlq_messages        — cron */5, processes SQL-backed DLQ retries (sync)
  9. retry_pending_welcome_messages — 600s interval, retries stuck welcome msgs

Key translation patterns from Celery → Taskiq:
  - run_async() bridge removed: task body is directly async
  - self.retry(countdown=) → raise exception, SmartRetryMiddleware handles retry
  - self.request.retries → context.message.labels.get('_retries', 0)
  - get_scoped_session() (sync) → AsyncSession via TaskiqDepends (main flow)
  - DLQ writes still use sync DLQService via get_scoped_session() (pragmatic)
  - .delay() → await .kiq()
  - .apply_async(eta=) → await schedule_task_at()
  - Structured logging via log_task_start/success/error from taskiq_base

Schedule labels (7 of 9 tasks are periodic):
  - process_scheduled_messages:      interval 60s
  - retry_failed_messages:           interval 300s
  - retry_pending_welcome_messages:  interval 600s
  - cleanup_old_messages:            interval 86400s
  - generate_message_analytics:      interval 3600s
  - process_whatsapp_dlq:            interval 600s
  - process_dlq_messages:            cron */5 * * * *
"""

import logging
from datetime import timedelta
from typing import Any, List
from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from taskiq import Context, TaskiqDepends

from app.models.message import (
    DeliveryStatus,
    Message,
    MessageDirection,
    MessagePriority,
    MessageStatus,
    MessageType,
)
from app.services.unified_whatsapp_service import create_unified_whatsapp_service
from app.taskiq_broker import broker
from app.tasks.taskiq_base import (
    DbSession,
    log_task_error,
    log_task_start,
    log_task_success,
    schedule_task_at,
)
from app.utils.timezone import now_sao_paulo

# Pure helper functions — imported from Celery module (no duplication).
from app.tasks.helpers.messaging_helpers import (
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


# ===========================================================================
# 2. process_scheduled_messages — periodic (60s)
# ===========================================================================

@broker.task(
    schedule=[{"interval": {"seconds": 60}, "kwargs": {"limit": 60}}],
)
async def process_scheduled_messages(
    limit: int = 100,
    db: AsyncSession = DbSession,
) -> dict[str, Any]:
    """Process all scheduled messages that are due for delivery.

    Fetches PENDING messages whose ``scheduled_for`` is in the past (or now)
    and dispatches each to ``send_scheduled_message`` via ``.kiq()``.

    Args:
        limit: Maximum number of messages to dispatch per run.
        db: Async database session (injected).

    Returns:
        Dict with processed_count and timestamp.
    """
    start_time = log_task_start("process_scheduled_messages", limit=limit)

    try:
        now = now_sao_paulo()

        # Direct async query — avoids sync MessageService dependency.
        stmt = (
            select(Message.id)
            .where(
                Message.status == MessageStatus.PENDING,
                Message.scheduled_for <= now,
            )
            .order_by(Message.scheduled_for.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        message_ids = result.scalars().all()

        processed_count = 0
        for msg_id in message_ids:
            await send_scheduled_message.kiq(str(msg_id))
            processed_count += 1

        log_task_success(
            "process_scheduled_messages",
            start_time,
            processed_count=processed_count,
        )
        return {
            "success": True,
            "processed_count": processed_count,
            "processed_at": now.isoformat(),
        }

    except Exception as exc:
        log_task_error("process_scheduled_messages", exc, start_time, limit=limit)
        raise


# ===========================================================================
# 3. retry_failed_messages — periodic (300s)
# ===========================================================================

@broker.task(
    schedule=[{"interval": {"seconds": 300}, "kwargs": {"limit": 50, "max_retries": 3}}],
)
async def retry_failed_messages(
    limit: int = 50,
    max_retries: int = 3,
    db: AsyncSession = DbSession,
) -> dict[str, Any]:
    """Retry sending failed messages that haven't exceeded max retries.

    Resets eligible FAILED messages to PENDING and dispatches each to
    ``send_scheduled_message`` via ``.kiq()``.

    Args:
        limit: Maximum number of messages to retry.
        max_retries: Skip messages whose retry_count >= this value.
        db: Async database session (injected).

    Returns:
        Dict with retry_count and timestamp.
    """
    start_time = log_task_start(
        "retry_failed_messages", limit=limit, max_retries=max_retries
    )

    try:
        now = now_sao_paulo()

        # Fetch failed messages eligible for retry.
        stmt = (
            select(Message)
            .where(
                Message.status == MessageStatus.FAILED,
                Message.retry_count < max_retries,
            )
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        failed_messages = result.scalars().all()

        retry_count = 0
        for message in failed_messages:
            try:
                metadata = dict(message.message_metadata or {})
                metadata["retry_trigger"] = "auto_retry_task"
                metadata["last_retry_at"] = now.isoformat()

                message.status = MessageStatus.PENDING
                message.last_retry_at = now
                message.retry_count = int(message.retry_count or 0) + 1
                message.message_metadata = metadata
                await db.commit()

                await send_scheduled_message.kiq(str(message.id))
                retry_count += 1

            except Exception as e:
                logger.error("Failed to queue retry for message %s: %s", message.id, e)
                await db.rollback()

        log_task_success(
            "retry_failed_messages",
            start_time,
            retry_count=retry_count,
        )
        return {
            "success": True,
            "retry_count": retry_count,
            "retried_at": now.isoformat(),
        }

    except Exception as exc:
        log_task_error(
            "retry_failed_messages", exc, start_time, limit=limit, max_retries=max_retries
        )
        raise


# ===========================================================================
# 4. send_bulk_messages — on-demand (no schedule label)
# ===========================================================================

@broker.task()
async def send_bulk_messages(
    message_data_list: List[dict[str, Any]],
    db: AsyncSession = DbSession,
) -> dict[str, Any]:
    """Send multiple messages in bulk with ETA dispatch.

    Creates messages via async DB writes and schedules each for delivery
    using ``schedule_task_at`` (replaces Celery ``.apply_async(eta=)``).

    Args:
        message_data_list: List of dicts with patient_id, content, scheduled_for, etc.
        db: Async database session (injected).

    Returns:
        Dict with creation/scheduling counts and task references.
    """
    start_time = log_task_start(
        "send_bulk_messages", total_requested=len(message_data_list)
    )

    try:
        from datetime import datetime as dt_cls
        from app.utils.timezone import SAO_PAULO_TZ

        created_messages: list[Message] = []
        failed_creations: list[dict[str, Any]] = []

        # --- Create messages ---
        for message_data in message_data_list:
            try:
                scheduled_for_raw = message_data.get("scheduled_for")
                if scheduled_for_raw:
                    scheduled_for = dt_cls.fromisoformat(scheduled_for_raw)
                else:
                    scheduled_for = now_sao_paulo()

                if scheduled_for.tzinfo is None:
                    scheduled_for = SAO_PAULO_TZ.localize(scheduled_for)

                msg = Message(
                    patient_id=UUID(message_data["patient_id"]),
                    direction=MessageDirection.OUTBOUND,
                    type=MessageType(message_data.get("type", "text")),
                    content=message_data["content"],
                    status=MessageStatus.PENDING,
                    delivery_status=DeliveryStatus.QUEUED,
                    priority=MessagePriority.NORMAL,
                    scheduled_for=scheduled_for,
                    message_metadata=message_data.get("metadata", {}),
                )
                db.add(msg)
                await db.flush()  # Get the ID without committing.
                created_messages.append(msg)

            except Exception as exc:
                logger.error("Failed to create bulk message: %s", exc)
                failed_creations.append(
                    {"patient_id": message_data.get("patient_id"), "error": str(exc)}
                )

        await db.commit()

        # --- Schedule individual send tasks via ETA ---
        scheduled_tasks: list[dict[str, Any]] = []
        for message in created_messages:
            eta = message.scheduled_for or now_sao_paulo()
            schedule_result = await schedule_task_at(
                send_scheduled_message, eta, str(message.id)
            )
            scheduled_tasks.append(
                {
                    "message_id": str(message.id),
                    "schedule_id": str(schedule_result.schedule_id),
                    "scheduled_for": eta.isoformat(),
                }
            )

        result = {
            "success": True,
            "total_requested": len(message_data_list),
            "messages_created": len(created_messages),
            "creation_failures": len(failed_creations),
            "scheduled_tasks": scheduled_tasks,
            "failed_creations": failed_creations,
            "processed_at": now_sao_paulo().isoformat(),
        }

        logger.info(
            "Bulk message operation: %d/%d messages created and scheduled",
            len(created_messages),
            len(message_data_list),
        )
        log_task_success(
            "send_bulk_messages",
            start_time,
            messages_created=len(created_messages),
        )
        return result

    except Exception as exc:
        log_task_error(
            "send_bulk_messages",
            exc,
            start_time,
            total_requested=len(message_data_list),
        )
        return {
            "success": False,
            "error": str(exc),
            "total_requested": len(message_data_list),
            "messages_created": 0,
        }


# ===========================================================================
# 5. cleanup_old_messages — periodic (86400s / daily)
# ===========================================================================

@broker.task(
    schedule=[{"interval": {"seconds": 86400}, "kwargs": {"days_old": 90}}],
)
async def cleanup_old_messages(
    days_old: int = 90,
    db: AsyncSession = DbSession,
) -> dict[str, Any]:
    """Archive old completed messages to manage database size.

    Moves messages older than ``days_old`` (DELIVERED, READ, CANCELLED) from
    the messages table to the message_archives table.

    Args:
        days_old: Age threshold in days for archival.
        db: Async database session (injected).

    Returns:
        Dict with archived_count and cutoff date.
    """
    start_time = log_task_start("cleanup_old_messages", days_old=days_old)

    try:
        from app.models.message_archive import MessageArchive

        cutoff_date = now_sao_paulo() - timedelta(days=days_old)

        # Fetch messages eligible for archival (batch of 1000).
        stmt = (
            select(Message)
            .where(
                Message.created_at < cutoff_date,
                Message.status.in_([
                    MessageStatus.DELIVERED,
                    MessageStatus.READ,
                    MessageStatus.CANCELLED,
                ]),
            )
            .limit(1000)
        )
        result = await db.execute(stmt)
        messages_to_archive = result.scalars().all()

        if not messages_to_archive:
            log_task_success("cleanup_old_messages", start_time, archived_count=0)
            return {
                "success": True,
                "archived_count": 0,
                "message": "No messages to archive",
            }

        archived_count = 0
        for msg in messages_to_archive:
            try:
                archive = MessageArchive(
                    original_id=msg.id,
                    patient_id=msg.patient_id,
                    direction=msg.direction,
                    type=msg.type,
                    content=msg.content,
                    message_metadata=msg.message_metadata,
                    priority=msg.priority,
                    idempotency_key=msg.idempotency_key,
                    whatsapp_id=msg.whatsapp_id,
                    status=msg.status,
                    scheduled_for=msg.scheduled_for,
                    sent_at=msg.sent_at,
                    delivered_at=msg.delivered_at,
                    read_at=msg.read_at,
                    delivery_status=msg.delivery_status,
                    retry_count=msg.retry_count,
                    last_retry_at=msg.last_retry_at,
                    failure_reason=msg.failure_reason,
                    archived_at=now_sao_paulo(),
                )
                db.add(archive)
                await db.delete(msg)
                archived_count += 1
            except Exception as e:
                logger.error("Failed to archive message %s: %s", msg.id, e)
                continue

        await db.commit()

        log_task_success(
            "cleanup_old_messages",
            start_time,
            archived_count=archived_count,
            cutoff_date=cutoff_date.isoformat(),
        )
        return {
            "success": True,
            "archived_count": archived_count,
            "cutoff_date": cutoff_date.isoformat(),
            "cleaned_at": now_sao_paulo().isoformat(),
        }

    except Exception as exc:
        log_task_error("cleanup_old_messages", exc, start_time, days_old=days_old)
        return {"success": False, "error": str(exc), "archived_count": 0}


# ===========================================================================
# 6. generate_message_analytics — periodic (3600s / hourly)
# ===========================================================================

@broker.task(
    schedule=[{"interval": {"seconds": 3600}, "kwargs": {"days_back": 7}}],
)
async def generate_message_analytics(
    patient_id: str | None = None,
    days_back: int = 30,
    db: AsyncSession = DbSession,
) -> dict[str, Any]:
    """Generate analytics for message delivery and engagement.

    Computes delivery rates, read rates, and average delivery time using
    async queries (replaces sync MessageService.get_message_statistics).

    Args:
        patient_id: Optional patient UUID string to scope analytics.
        days_back: Number of days to look back.
        db: Async database session (injected).

    Returns:
        Dict with analytics payload (rates, counts, performance).
    """
    start_time = log_task_start(
        "generate_message_analytics", patient_id=patient_id, days_back=days_back
    )

    try:
        end_date = now_sao_paulo()
        start_date = end_date - timedelta(days=days_back)
        patient_uuid = UUID(patient_id) if patient_id else None

        # --- Message statistics by status ---
        stats_stmt = select(Message.status, func.count(Message.id)).where(
            and_(
                Message.created_at >= start_date,
                Message.created_at <= end_date,
            )
        )
        if patient_uuid:
            stats_stmt = stats_stmt.where(Message.patient_id == patient_uuid)
        stats_stmt = stats_stmt.group_by(Message.status)

        stats_result = await db.execute(stats_stmt)
        statistics: dict[str, int] = {
            str(status.value): count for status, count in stats_result.all()
        }

        # --- Delivery / read rates ---
        total_sent = (
            statistics.get("sent", 0)
            + statistics.get("delivered", 0)
            + statistics.get("read", 0)
        )
        total_delivered = statistics.get("delivered", 0) + statistics.get("read", 0)
        total_read = statistics.get("read", 0)

        delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
        read_rate = (total_read / total_delivered * 100) if total_delivered > 0 else 0

        # --- Average delivery time ---
        dt_stmt = select(
            func.extract("epoch", Message.delivered_at - Message.sent_at).label(
                "delivery_seconds"
            )
        ).where(
            and_(
                Message.created_at >= start_date,
                Message.created_at <= end_date,
                Message.sent_at.isnot(None),
                Message.delivered_at.isnot(None),
            )
        )
        if patient_uuid:
            dt_stmt = dt_stmt.where(Message.patient_id == patient_uuid)

        dt_result = await db.execute(dt_stmt)
        delivery_times = [row.delivery_seconds for row in dt_result.all() if row.delivery_seconds]
        avg_delivery_time = (
            sum(delivery_times) / len(delivery_times) if delivery_times else 0
        )

        result = {
            "success": True,
            "analytics": {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": days_back,
                },
                "patient_id": patient_id,
                "message_counts": statistics,
                "rates": {
                    "delivery_rate_percent": round(delivery_rate, 2),
                    "read_rate_percent": round(read_rate, 2),
                },
                "performance": {
                    "avg_delivery_time_seconds": round(avg_delivery_time, 2),
                    "total_messages": sum(statistics.values()),
                },
            },
            "generated_at": now_sao_paulo().isoformat(),
        }

        logger.info(
            "Generated message analytics for %d days%s",
            days_back,
            f" for patient {patient_id}" if patient_id else "",
        )
        log_task_success(
            "generate_message_analytics",
            start_time,
            days_back=days_back,
            total_messages=sum(statistics.values()),
        )
        return result

    except Exception as exc:
        log_task_error(
            "generate_message_analytics", exc, start_time, days_back=days_back
        )
        return {"success": False, "error": str(exc), "analytics": {}}


# ===========================================================================
# 7. process_whatsapp_dlq — periodic (600s)
# ===========================================================================

@broker.task(
    schedule=[{"interval": {"seconds": 600}, "kwargs": {"limit": 50}}],
)
async def process_whatsapp_dlq(
    limit: int = 50,
) -> dict[str, Any]:
    """Process the WhatsApp Dead Letter Queue.

    Retrieves pending DLQ entries and auto-retries transient failures
    (rate limit, timeout, network error). Others are left for manual review.

    Note: DLQHandler is declared with ``async def`` methods but internally uses
    sync ORM (``self.db.query()``, ``self.db.commit()``). We use a dedicated
    sync session via ``get_scoped_session()`` to match the original Celery
    pattern. The ``await`` calls work because the methods are coroutines that
    perform sync I/O (no real async benefit, but the interface is honoured).

    Args:
        limit: Maximum number of DLQ messages to process.

    Returns:
        Dict with processed/requeued counts.
    """
    start_time = log_task_start("process_whatsapp_dlq", limit=limit)

    try:
        from app.database import get_scoped_session
        from app.integrations.whatsapp.queue.dlq import DLQHandler
        from app.models.failed_message import FailureReason

        # DLQHandler uses sync ORM internally — provide sync session.
        with get_scoped_session() as sync_db:
            dlq_handler = DLQHandler(sync_db)

            # DLQHandler methods are async def but use sync ORM internally.
            pending_messages = await dlq_handler.get_pending_review(limit=limit)

            if not pending_messages:
                logger.info("No pending DLQ messages to process")
                log_task_success(
                    "process_whatsapp_dlq", start_time, processed=0
                )
                return {
                    "success": True,
                    "message": "No pending DLQ messages",
                    "processed": 0,
                }

            logger.info("Processing %d DLQ messages", len(pending_messages))

            processed_count = 0
            requeued_count = 0

            auto_retry_reasons = [
                FailureReason.RATE_LIMIT.value,
                FailureReason.TIMEOUT.value,
                FailureReason.NETWORK_ERROR.value,
            ]

            for failed_msg in pending_messages:
                try:
                    if (
                        failed_msg.error_code in auto_retry_reasons
                        and failed_msg.retry_count < 3
                    ):
                        await dlq_handler.requeue_for_retry(
                            dlq_id=failed_msg.id, immediate=False
                        )
                        requeued_count += 1
                        logger.info("Auto-requeued DLQ message %s", failed_msg.id)
                    else:
                        logger.info(
                            "DLQ message %s requires manual review", failed_msg.id
                        )

                    processed_count += 1

                except Exception as e:
                    logger.error(
                        "Failed to process DLQ message %s: %s", failed_msg.id, e
                    )
                    continue

        result = {
            "success": True,
            "message": f"Processed {processed_count} DLQ messages",
            "processed": processed_count,
            "requeued": requeued_count,
            "manual_review": processed_count - requeued_count,
        }

        log_task_success(
            "process_whatsapp_dlq",
            start_time,
            processed=processed_count,
            requeued=requeued_count,
        )
        return result

    except Exception as exc:
        log_task_error("process_whatsapp_dlq", exc, start_time, limit=limit)
        return {"success": False, "error": str(exc), "processed": 0}


# ===========================================================================
# 8. process_dlq_messages — periodic (cron */5)
# ===========================================================================

@broker.task(
    schedule=[{"cron": "*/5 * * * *", "kwargs": {"limit": 100}}],
)
async def process_dlq_messages(
    limit: int = 100,
) -> dict[str, Any]:
    """Process scheduled retries for SQL-backed DLQ entries.

    # DLQService is sync-only — uses dedicated sync session. Async conversion deferred.
    """
    start_time = log_task_start("process_dlq_messages", limit=limit)

    try:
        from app.database import get_scoped_session
        from app.services.dlq.service import DLQService

        with get_scoped_session() as sync_db:
            dlq_service = DLQService(sync_db)
            processed = dlq_service.process_scheduled_retries()

        log_task_success(
            "process_dlq_messages", start_time, processed=processed
        )
        return {
            "success": True,
            "processed": processed,
            "limit": limit,
            "processed_at": now_sao_paulo().isoformat(),
        }

    except Exception as exc:
        log_task_error("process_dlq_messages", exc, start_time, limit=limit)
        return {"success": False, "error": str(exc), "processed": 0, "limit": limit}


# ===========================================================================
# 9. retry_pending_welcome_messages — periodic (600s)
# ===========================================================================

@broker.task(
    schedule=[{"interval": {"seconds": 600}, "kwargs": {"limit": 50, "min_age_minutes": 5, "max_age_hours": 24}}],
)
async def retry_pending_welcome_messages(
    limit: int = 50,
    min_age_minutes: int = 5,
    max_age_hours: int = 24,
    db: AsyncSession = DbSession,
) -> dict[str, Any]:
    """Retry welcome messages stuck in PENDING status.

    FIX: Welcome messages can get stuck in PENDING if WhatsApp API fails
    during patient registration. This task targets welcome messages
    (identified by ``message_metadata->>'message_type' == 'welcome'``)
    that have been pending within a configurable time window.

    Args:
        limit: Maximum number of messages to retry per run.
        min_age_minutes: Minimum age to avoid race conditions with normal send.
        max_age_hours: Maximum age — skip very old messages.
        db: Async database session (injected).

    Returns:
        Dict with retry/failed counts.
    """
    start_time = log_task_start(
        "retry_pending_welcome_messages",
        limit=limit,
        min_age_minutes=min_age_minutes,
    )

    try:
        now = now_sao_paulo()
        min_created_at = now - timedelta(hours=max_age_hours)
        max_created_at = now - timedelta(minutes=min_age_minutes)

        # JSONB query for welcome messages stuck in PENDING within time window.
        stmt = (
            select(Message)
            .where(
                Message.status == MessageStatus.PENDING,
                Message.message_metadata["message_type"].astext == "welcome",
                Message.created_at >= min_created_at,
                Message.created_at <= max_created_at,
            )
            .limit(limit)
        )
        result = await db.execute(stmt)
        pending_welcome_messages = result.scalars().all()

        if not pending_welcome_messages:
            logger.info("No pending welcome messages to retry")
            log_task_success(
                "retry_pending_welcome_messages", start_time, retry_count=0
            )
            return {
                "success": True,
                "retry_count": 0,
                "message": "No pending welcome messages found",
            }

        retry_count = 0
        failed_count = 0

        for message in pending_welcome_messages:
            try:
                metadata = dict(message.message_metadata or {})
                retry_attempts = metadata.get("welcome_retry_attempts", 0)

                if retry_attempts >= 3:
                    logger.warning(
                        "Welcome message %s exceeded max retries, marking as failed",
                        message.id,
                    )
                    message.status = MessageStatus.FAILED
                    metadata["final_failure_reason"] = "max_welcome_retries_exceeded"
                    metadata["failed_at"] = now.isoformat()
                    message.message_metadata = metadata
                    failed_count += 1
                    continue

                # Update retry tracking.
                metadata["welcome_retry_attempts"] = retry_attempts + 1
                metadata["last_welcome_retry_at"] = now.isoformat()
                message.message_metadata = metadata

                await db.commit()

                await send_scheduled_message.kiq(str(message.id))
                retry_count += 1

                logger.info(
                    "Queued welcome message %s for retry (attempt %d)",
                    message.id,
                    retry_attempts + 1,
                )

            except Exception as e:
                logger.error("Failed to retry welcome message %s: %s", message.id, e)
                await db.rollback()
                failed_count += 1

        # Commit any remaining status changes (failed messages).
        try:
            await db.commit()
        except Exception:
            await db.rollback()

        log_task_success(
            "retry_pending_welcome_messages",
            start_time,
            retry_count=retry_count,
            failed_count=failed_count,
            total_found=len(pending_welcome_messages),
        )
        return {
            "success": True,
            "retry_count": retry_count,
            "failed_count": failed_count,
            "total_found": len(pending_welcome_messages),
            "retried_at": now.isoformat(),
        }

    except Exception as exc:
        log_task_error(
            "retry_pending_welcome_messages", exc, start_time, limit=limit
        )
        raise
