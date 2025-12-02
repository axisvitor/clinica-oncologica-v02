"""
Message-based follow-up action scheduler.
Handles scheduling of message-based follow-ups.
"""
import logging
from datetime import datetime

from ..models import FollowUpAction
from app.models.message import Message, MessageDirection, MessageType, MessageStatus

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

            # Create message
            message = Message(
                patient_id=action.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=message_content,
                status=MessageStatus.PENDING,
                scheduled_for=action.scheduled_for,
                message_metadata={
                    "follow_up_action_id": str(action.action_id),
                    "follow_up_type": action.follow_up_type.value,
                    "priority": action.priority,
                    "ai_generated": True
                }
            )

            # Save message
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)

            # Schedule with message scheduler
            await self.message_scheduler.schedule_message(
                message_id=message.id,
                send_time=action.scheduled_for,
                priority=action.priority
            )

            logger.info(f"Scheduled message for action {action.action_id}")

        except Exception as e:
            logger.error(f"Failed to schedule message action: {e}")
            self.db.rollback()
