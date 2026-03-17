"""
Message-based follow-up action scheduler.
Handles scheduling of message-based follow-ups.
"""

import logging

from ..models import FollowUpAction
from ..message_deduplication_service import MessageDeduplicationService
from app.models.message import MessageType
from app.domain.messaging.core.message_service.service import MessageService

logger = logging.getLogger(__name__)


class MessageScheduler:
    """Schedules message-based follow-up actions."""

    def __init__(self, db, message_scheduler):
        """
        Initialize message scheduler.

        Args:
            db: Database session
            message_scheduler: Domain message scheduler
        """
        self.db = db
        self.message_scheduler = message_scheduler
        self.dedup_service = MessageDeduplicationService()
        self.message_service = MessageService(db)

    async def schedule_message_action(self, action: FollowUpAction) -> None:
        """
        Schedule a message-based follow-up action.

        Args:
            action: FollowUpAction with message content
        """
        try:
            message_content = action.parameters.get("message_content")
            if not message_content:
                logger.warning(f"No message content for action {action.action_id}")
                return

            # Check for duplicates
            is_duplicate = await self.dedup_service.check_duplicate(
                patient_id=action.patient_id,
                message_content=message_content,
                follow_up_type=action.follow_up_type.value,
            )
            if is_duplicate:
                logger.info(
                    f"Skipping duplicate follow-up message for action {action.action_id}"
                )
                return

            # Create message with domain service (handles idempotency key)
            message = self.message_service.schedule_message(
                patient_id=action.patient_id,
                content=message_content,
                scheduled_for=action.scheduled_for,
                message_type=MessageType.TEXT,
                message_metadata={
                    "follow_up_action_id": str(action.action_id),
                    "follow_up_type": action.follow_up_type.value,
                    "priority": action.priority,
                    "ai_generated": True,
                },
            )

            # Schedule delivery task at the desired time
            await self.message_scheduler.task_scheduler.schedule_task(
                message, action.scheduled_for
            )

            # Mark message as sent in deduplication cache
            await self.dedup_service.mark_as_sent(
                patient_id=action.patient_id,
                message_content=message_content,
                follow_up_type=action.follow_up_type.value,
            )

            logger.info(f"Scheduled message for action {action.action_id}")

        except Exception as e:
            logger.error(f"Failed to schedule message action: {e}")
            self.db.rollback()
