"""
Message action executor.
Executes message-based follow-up actions.
"""

import logging

from .executor import ActionExecutor
from ..models import FollowUpAction
from ..enums import FollowUpType

logger = logging.getLogger(__name__)


class MessageExecutor(ActionExecutor):
    """Executes message-based follow-up actions."""

    async def _execute_action(self, action: FollowUpAction) -> bool:
        """
        Execute a specific follow-up action.

        Args:
            action: FollowUpAction to execute

        Returns:
            True if successful
        """
        try:
            if action.follow_up_type == FollowUpType.EMPATHETIC_RESPONSE:
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

    async def _execute_message_action(self, action: FollowUpAction) -> bool:
        """
        Execute message-based action.

        Args:
            action: FollowUpAction to execute

        Returns:
            True if successful
        """
        try:
            # Message should already be scheduled, just mark as executed
            action.execution_result = {"message_scheduled": True}
            return True

        except Exception as e:
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
