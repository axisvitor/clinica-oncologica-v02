"""
Base action executor for follow-up system.
Handles execution of pending follow-up actions.
"""

import logging
from typing import Dict, Any
from datetime import datetime, timezone
from uuid import UUID

from ..models import FollowUpAction
from ..enums import FollowUpType

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Base executor for follow-up actions."""

    def __init__(self, redis_store, pending_actions: dict):
        """
        Initialize action executor.

        Args:
            redis_store: Redis storage instance for persistence
            pending_actions: Fallback in-memory storage
        """
        self.redis_store = redis_store
        self.pending_actions = pending_actions

    async def execute_pending_actions(self, limit: int = 100) -> Dict[str, Any]:
        """
        Execute pending follow-up actions.

        Args:
            limit: Maximum number of actions to execute

        Returns:
            Execution statistics
        """
        try:
            executed_count = 0
            failed_count = 0
            current_time = datetime.now(timezone.utc)

            # Get actions ready for execution from Redis
            ready_action_dicts = await self.redis_store.get_pending_actions(
                limit=limit, before=current_time
            )

            # If Redis returned nothing, try in-memory fallback
            if not ready_action_dicts and self.pending_actions:
                ready_action_dicts = [
                    self._action_to_dict(action)
                    for action in self.pending_actions.values()
                    if action.status == "pending"
                    and action.scheduled_for <= current_time
                ][:limit]

            # Execute each action
            for action_dict in ready_action_dicts:
                action_id = UUID(action_dict["action_id"])
                try:
                    # Reconstruct action object for execution
                    action = self._dict_to_action(action_dict)

                    success = await self._execute_action(action)

                    if success:
                        executed_count += 1
                        # Update status in Redis
                        await self.redis_store.update_action_status(
                            action_id=action_id,
                            status="executed",
                            executed_at=current_time,
                            execution_result=action.execution_result,
                        )
                    else:
                        failed_count += 1
                        await self.redis_store.update_action_status(
                            action_id=action_id,
                            status="failed",
                            executed_at=current_time,
                        )

                except Exception as e:
                    logger.error(f"Failed to execute action {action_id}: {e}")
                    failed_count += 1
                    await self.redis_store.update_action_status(
                        action_id=action_id, status="failed", executed_at=current_time
                    )

            # Get total pending count
            all_pending = await self.redis_store.get_pending_actions(limit=10000)
            total_pending = len(all_pending)

            return {
                "executed": executed_count,
                "failed": failed_count,
                "total_pending": total_pending,
            }

        except Exception as e:
            logger.error(f"Failed to execute pending actions: {e}")
            return {"error": str(e)}

    async def _execute_action(self, action: FollowUpAction) -> bool:
        """
        Execute a specific follow-up action.

        Args:
            action: FollowUpAction to execute

        Returns:
            True if successful
        """
        try:
            # Generic execution - subclasses should override
            logger.info(f"Executed action {action.action_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to execute action {action.action_id}: {e}")
            return False

    def _action_to_dict(self, action: FollowUpAction) -> dict:
        """Convert FollowUpAction to dictionary."""
        return {
            "action_id": str(action.action_id),
            "patient_id": str(action.patient_id),
            "follow_up_type": action.follow_up_type.value
            if hasattr(action.follow_up_type, "value")
            else str(action.follow_up_type),
            "priority": action.priority,
            "scheduled_for": action.scheduled_for.isoformat(),
            "parameters": action.parameters,
            "created_by": action.created_by,
            "created_at": action.created_at.isoformat(),
            "status": action.status,
            "executed_at": action.executed_at.isoformat()
            if action.executed_at
            else None,
            "execution_result": action.execution_result,
        }

    def _dict_to_action(self, action_dict: dict) -> FollowUpAction:
        """Convert dictionary to FollowUpAction."""

        def _parse_dt_tz_aware(dt_str: str) -> datetime:
            """FIX P1-006: Ensure timezone-aware datetime parsing."""
            dt = datetime.fromisoformat(dt_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt

        action = FollowUpAction(
            action_id=UUID(action_dict["action_id"]),
            patient_id=UUID(action_dict["patient_id"]),
            follow_up_type=FollowUpType(action_dict["follow_up_type"]),
            priority=action_dict["priority"],
            # FIX P1-006: Use timezone-aware parsing
            scheduled_for=_parse_dt_tz_aware(action_dict["scheduled_for"]),
            parameters=action_dict["parameters"],
            created_by=action_dict["created_by"],
        )
        action.status = action_dict["status"]
        # FIX P1-006: Use timezone-aware parsing
        action.created_at = _parse_dt_tz_aware(action_dict["created_at"])
        return action
