"""
Base action scheduler for follow-up system.
Handles scheduling of follow-up actions in Redis or in-memory storage.
"""
import logging
from uuid import UUID

from ..models import FollowUpAction
from ..enums import FollowUpType

logger = logging.getLogger(__name__)


class ActionScheduler:
    """Base scheduler for follow-up actions."""

    def __init__(self, redis_store, pending_actions: dict):
        """
        Initialize action scheduler.

        Args:
            redis_store: Redis storage instance for persistence
            pending_actions: Fallback in-memory storage
        """
        self.redis_store = redis_store
        self.pending_actions = pending_actions

    async def schedule_action(self, action: FollowUpAction) -> bool:
        """
        Schedule a follow-up action for execution.

        Args:
            action: FollowUpAction to schedule

        Returns:
            True if successfully scheduled
        """
        try:
            # Store action in Redis (with fallback to in-memory)
            stored = await self.redis_store.store_action(action)
            if not stored:
                # Fallback to in-memory
                self.pending_actions[action.action_id] = action
                logger.debug(f"Stored action in memory: {action.action_id}")
            else:
                logger.debug(f"Stored action in Redis: {action.action_id}")

            logger.info(f"Scheduled follow-up action {action.action_id} for patient {action.patient_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to schedule follow-up action: {e}")
            return False

    async def get_pending_actions_by_type(
        self,
        follow_up_type: FollowUpType,
        limit: int = 100
    ) -> list:
        """
        Get pending actions by type.

        Args:
            follow_up_type: Type of follow-up action
            limit: Maximum number of actions to retrieve

        Returns:
            List of pending actions
        """
        try:
            # Get from Redis first
            all_pending = await self.redis_store.get_pending_actions(limit=limit * 2)

            # Filter by type
            filtered = [
                action for action in all_pending
                if action.get("follow_up_type") == follow_up_type.value
            ][:limit]

            return filtered

        except Exception as e:
            logger.error(f"Failed to get pending actions by type: {e}")
            return []
