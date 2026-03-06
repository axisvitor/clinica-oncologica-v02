"""Celery task for retrying failed deferred follow-up sends."""

from __future__ import annotations

import logging
import random
from uuid import UUID

from asgiref.sync import async_to_sync
from celery.exceptions import MaxRetriesExceededError

from app.database import get_scoped_session
from app.services.follow_up_system.enums import FollowUpType
from app.services.follow_up_system.models import FollowUpAction
from app.task_queue import task_queue as celery_app
from app.tasks.flows.base import FlowTaskBase
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

FOLLOWUP_RETRY_MAX = 3
FOLLOWUP_RETRY_BASE_DELAY = 30
FOLLOWUP_RETRY_BACKOFF = 2
FOLLOWUP_RETRY_MAX_JITTER = 10


def _build_retry_action(
    *,
    action_id: str,
    patient_id: str,
    parameters: dict | None,
    follow_up_type: str,
    priority: str,
) -> FollowUpAction | None:
    if not parameters:
        return None

    return FollowUpAction(
        action_id=UUID(str(action_id)),
        patient_id=UUID(str(patient_id)),
        follow_up_type=FollowUpType(follow_up_type),
        priority=priority,
        scheduled_for=now_sao_paulo(),
        parameters=parameters,
        created_by="followup_retry_task",
    )


@celery_app.task(
    bind=True,
    base=FlowTaskBase,
    name="app.tasks.flows.followup_retry.retry_failed_followup_send",
    max_retries=FOLLOWUP_RETRY_MAX,
    acks_late=True,
    reject_on_worker_lost=True,
)
def retry_failed_followup_send(
    self,
    action_id: str,
    patient_id: str,
    *,
    parameters: dict | None = None,
    follow_up_type: str = FollowUpType.CONVERSATION_CONTINUATION.value,
    priority: str = "normal",
) -> dict:
    """Retry a failed deferred follow-up send with exponential backoff."""
    try:
        retry_action = _build_retry_action(
            action_id=action_id,
            patient_id=patient_id,
            parameters=parameters,
            follow_up_type=follow_up_type,
            priority=priority,
        )
    except (TypeError, ValueError) as exc:
        return {"status": "invalid_action", "action_id": str(action_id), "error": str(exc)}

    if retry_action is None:
        return {"status": "action_not_found", "action_id": str(action_id)}

    with get_scoped_session() as db:
        from app.services.follow_up_system.service import FollowUpSystemService

        follow_up_service = FollowUpSystemService(db, auto_rehydrate=False)

        try:
            success = async_to_sync(
                follow_up_service.action_executor._schedule_message_action
            )(retry_action)
            if not success:
                raise RuntimeError(
                    f"Follow-up retry returned False for action {retry_action.action_id}"
                )

            executed_at = now_sao_paulo()
            async_to_sync(follow_up_service.redis_store.update_action_status)(
                action_id=retry_action.action_id,
                status="executed",
                executed_at=executed_at,
                execution_result=retry_action.execution_result,
            )
            return {
                "status": "ok",
                "action_id": str(retry_action.action_id),
                "attempt": self.request.retries + 1,
            }

        except Exception as exc:
            countdown = (
                FOLLOWUP_RETRY_BASE_DELAY
                * (FOLLOWUP_RETRY_BACKOFF ** self.request.retries)
            ) + random.randint(0, FOLLOWUP_RETRY_MAX_JITTER)

            logger.warning(
                "Retrying failed follow-up send",
                extra={
                    "action_id": str(retry_action.action_id),
                    "patient_id": str(retry_action.patient_id),
                    "attempt": self.request.retries + 1,
                    "countdown": countdown,
                },
            )

            try:
                raise self.retry(countdown=countdown, exc=exc)
            except MaxRetriesExceededError:
                executed_at = now_sao_paulo()
                execution_result = {
                    "error": str(exc),
                    "retry_exhausted": True,
                    "attempts": FOLLOWUP_RETRY_MAX,
                }
                async_to_sync(follow_up_service.redis_store.update_action_status)(
                    action_id=retry_action.action_id,
                    status="failed",
                    executed_at=executed_at,
                    execution_result=execution_result,
                )
                logger.error(
                    "Follow-up send permanently failed after retry exhaustion",
                    extra={
                        "action_id": str(retry_action.action_id),
                        "patient_id": str(retry_action.patient_id),
                        "attempts": FOLLOWUP_RETRY_MAX,
                    },
                )
                return {
                    "status": "permanently_failed",
                    "action_id": str(retry_action.action_id),
                    "attempts": FOLLOWUP_RETRY_MAX,
                }
