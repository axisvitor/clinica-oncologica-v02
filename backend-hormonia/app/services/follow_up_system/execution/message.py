"""
Message action executor.
Executes message-based follow-up actions.
"""

import logging
from typing import Any, Awaitable, Callable, Optional

from .executor import ActionExecutor
from ..enums import FollowUpType
from ..models import FollowUpAction

logger = logging.getLogger(__name__)

MESSAGE_ACTION_TYPES = {
    FollowUpType.EMPATHETIC_RESPONSE,
    FollowUpType.MEDICAL_CLARIFICATION,
    FollowUpType.APPOINTMENT_SCHEDULING,
    FollowUpType.MEDICATION_GUIDANCE,
    FollowUpType.EMOTIONAL_SUPPORT,
    FollowUpType.TREATMENT_ENCOURAGEMENT,
    FollowUpType.INFORMATION_REQUEST,
    FollowUpType.CONVERSATION_CONTINUATION,
}


class MessageExecutor(ActionExecutor):
    """Executes message-based follow-up actions."""

    def __init__(
        self,
        redis_store,
        pending_actions: dict,
        *,
        scheduler: Optional[Callable[[FollowUpAction], Awaitable[None]]] = None,
    ) -> None:
        super().__init__(redis_store, pending_actions)
        self._scheduler = scheduler

    async def _execute_action(self, action: FollowUpAction) -> bool:
        """
        Execute a specific follow-up action.

        Args:
            action: FollowUpAction to execute

        Returns:
            True if successful
        """
        try:
            if action.follow_up_type in MESSAGE_ACTION_TYPES:
                return await self._execute_message_action(action)
            elif action.follow_up_type == FollowUpType.ESCALATION_NOTIFICATION:
                return await self._execute_escalation_action(action)
            elif action.follow_up_type == FollowUpType.PROVIDER_ALERT:
                return await self._execute_provider_alert(action)
            else:
                # Generic execution
                logger.info(f"Executed generic action {action.action_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to execute action {action.action_id}: {e}")
            return False

    async def _schedule_message_action(self, action: FollowUpAction) -> bool:
        """Schedule the underlying follow-up message delivery."""
        if self._scheduler is not None:
            await self._scheduler(action)

        action.execution_result = {"message_scheduled": True}
        return True

    async def _enqueue_retry(self, action: FollowUpAction) -> None:
        """Queue retry task for message-like follow-up actions."""
        from datetime import datetime, timedelta, timezone
        from app.tasks.flows_taskiq import retry_failed_followup_send
        from app.tasks.taskiq_base import schedule_task_at

        FOLLOWUP_RETRY_BASE_DELAY = 30  # seconds (same as Celery original)

        await schedule_task_at(
            retry_failed_followup_send,
            datetime.now(timezone.utc) + timedelta(seconds=FOLLOWUP_RETRY_BASE_DELAY),
            str(action.action_id),
            str(action.patient_id),
            parameters=action.parameters,
            follow_up_type=action.follow_up_type.value,
            priority=action.priority,
        )

    async def _execute_message_action(self, action: FollowUpAction) -> bool:
        """
        Execute message-based action.

        Args:
            action: FollowUpAction to execute

        Returns:
            True if successful
        """
        try:
            return await self._schedule_message_action(action)

        except Exception as e:
            await self._enqueue_retry(action)
            action.execution_result = {
                "message_scheduled": False,
                "retry_enqueued": True,
                "error": str(e),
            }
            logger.warning(
                "Follow-up send failed, enqueued retry task",
                extra={
                    "action_id": str(action.action_id),
                    "patient_id": str(action.patient_id),
                    "follow_up_type": action.follow_up_type.value,
                },
            )
            logger.error(f"Failed to execute message action: {e}")
            return False

    async def _execute_escalation_action(self, action: FollowUpAction) -> bool:
        """
        Execute escalation action.

        Args:
            action: FollowUpAction to execute

        Returns:
            True if successful
        """
        try:
            # Escalation should already be sent, just mark as executed
            action.execution_result = {"escalation_sent": True}
            return True

        except Exception as e:
            logger.error(f"Failed to execute escalation action: {e}")
            return False

    async def _execute_provider_alert(self, action: FollowUpAction) -> bool:
        """
        Execute provider alert action.

        Args:
            action: FollowUpAction to execute

        Returns:
            True if successful
        """
        try:
            # Alert should already be sent, just mark as executed
            action.execution_result = {"alert_sent": True}
            return True

        except Exception as e:
            logger.error(f"Failed to execute provider alert: {e}")
            return False
