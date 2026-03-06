"""Celery task for retrying failed outbound flow message sends."""

import logging
import random
from datetime import timedelta
from typing import Any
from uuid import UUID

from asgiref.sync import async_to_sync
from celery.exceptions import MaxRetriesExceededError

from app.config.settings.tasks import (
    FLOW_MAX_RETRIES,
    MESSAGE_RETRY_DELAY,
    RETRY_BACKOFF_FACTOR,
)
from app.database import get_scoped_session
from app.exceptions import ExternalServiceError
from app.models.message import Message, MessageStatus
from app.repositories.flow import FlowStateRepository
from app.services.unified_whatsapp_service import UnifiedWhatsAppService
from app.task_queue import task_queue as celery_app
from app.tasks.flows.base import FlowTaskBase
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

SEND_RETRY_MAX_RETRIES = FLOW_MAX_RETRIES
SEND_RETRY_BASE_DELAY = MESSAGE_RETRY_DELAY
SEND_RETRY_BACKOFF_FACTOR = RETRY_BACKOFF_FACTOR
SEND_RETRY_MAX_JITTER = 10
_TERMINAL_MESSAGE_STATUSES = {
    MessageStatus.SENT,
    MessageStatus.DELIVERED,
    MessageStatus.READ,
}


def _resolve_flow_context(
    message: Message,
    flow_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if flow_context is not None:
        return flow_context

    metadata = message.message_metadata or {}
    stored_context = metadata.get("flow_context")
    return stored_context if isinstance(stored_context, dict) else None


def _current_attempt(retries: int) -> int:
    return min(retries + 1, SEND_RETRY_MAX_RETRIES)


def _record_permanent_delivery_failure(message: Message, db: Any) -> None:
    flow_repo = FlowStateRepository(db)
    active_flow = flow_repo.get_active_flow(message.patient_id)
    if not active_flow:
        return

    state_data = dict(active_flow.state_data or {})
    delivery_failures = list(state_data.get("delivery_failures") or [])
    delivery_failures.append(
        {
            "message_id": str(message.id),
            "failure_timestamp": now_sao_paulo().isoformat(),
            "failure_reason": message.failure_reason,
            "retry_count": message.retry_count,
            "step": active_flow.current_step,
        }
    )

    state_data["delivery_failures"] = delivery_failures
    state_data["skip_waiting_for_message"] = str(message.id)
    state_data["last_delivery_failure"] = now_sao_paulo().isoformat()

    active_flow.state_data = state_data
    db.add(active_flow)


def _finalize_permanent_failure(
    message: Message,
    db: Any,
    exc: Exception,
    flow_context: dict[str, Any] | None,
) -> dict[str, Any]:
    message.status = MessageStatus.FAILED
    message.failure_reason = str(exc)
    message.next_retry_at = None
    message.retry_count = _current_attempt(SEND_RETRY_MAX_RETRIES)
    metadata = dict(message.message_metadata or {})
    metadata["permanently_failed_at"] = now_sao_paulo().isoformat()
    if flow_context is not None:
        metadata["flow_context"] = flow_context
    message.message_metadata = metadata

    db.add(message)
    _record_permanent_delivery_failure(message, db)
    db.commit()

    logger.error(
        "Flow message send permanently failed after retry exhaustion",
        extra={
            "message_id": str(message.id),
            "patient_id": str(message.patient_id),
            "attempts": SEND_RETRY_MAX_RETRIES,
            "flow_context": flow_context or {},
        },
    )

    return {
        "status": "permanently_failed",
        "message_id": str(message.id),
        "attempts": SEND_RETRY_MAX_RETRIES,
        "permanently_failed": True,
    }


@celery_app.task(
    bind=True,
    base=FlowTaskBase,
    name="app.tasks.flows.send_retry.retry_failed_flow_send",
    max_retries=SEND_RETRY_MAX_RETRIES,
    acks_late=True,
    reject_on_worker_lost=True,
)
def retry_failed_flow_send(
    self,
    message_id: str,
    flow_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Retry a failed outbound flow message send with exponential backoff."""
    try:
        message_uuid = UUID(str(message_id))
    except (TypeError, ValueError):
        return {"status": "invalid_message_id", "message_id": str(message_id)}

    with get_scoped_session() as db:
        message = db.query(Message).filter(Message.id == message_uuid).first()
        if not message:
            return {"status": "message_not_found", "message_id": str(message_id)}

        if message.status in _TERMINAL_MESSAGE_STATUSES:
            return {
                "status": "already_finalized",
                "message_id": str(message.id),
                "message_status": message.status.value,
            }

        resolved_flow_context = _resolve_flow_context(message, flow_context)
        attempt = _current_attempt(self.request.retries)

        if message.status == MessageStatus.FAILED:
            message.status = MessageStatus.PENDING

        message.retry_count = attempt
        message.last_retry_at = now_sao_paulo()
        message.next_retry_at = None
        message.failure_reason = None
        db.add(message)
        db.commit()

        whatsapp_service = UnifiedWhatsAppService(db)

        try:
            success = async_to_sync(whatsapp_service.send_message)(
                message,
                flow_context=resolved_flow_context,
            )
            if not success:
                raise ExternalServiceError(
                    f"Flow message retry returned False for message {message.id}"
                )

            return {
                "status": "ok",
                "message_id": str(message.id),
                "attempt": attempt,
            }

        except ExternalServiceError as exc:
            countdown = (
                SEND_RETRY_BASE_DELAY
                * (SEND_RETRY_BACKOFF_FACTOR ** self.request.retries)
            ) + random.randint(0, SEND_RETRY_MAX_JITTER)

            message.failure_reason = str(exc)
            message.next_retry_at = now_sao_paulo() + timedelta(seconds=countdown)
            db.add(message)
            db.commit()

            logger.warning(
                "Retrying failed flow message send",
                extra={
                    "message_id": str(message.id),
                    "patient_id": str(message.patient_id),
                    "attempt": attempt,
                    "countdown": countdown,
                },
            )

            try:
                raise self.retry(countdown=countdown, exc=exc)
            except MaxRetriesExceededError:
                return _finalize_permanent_failure(
                    message=message,
                    db=db,
                    exc=exc,
                    flow_context=resolved_flow_context,
                )
