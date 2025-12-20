import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.message import Message, MessageStatus
from app.services.websocket_events import websocket_events
from app.schemas.websocket import WebSocketEventType

logger = logging.getLogger(__name__)


class MessageStatusHandler:
    """
    Handles synchronization of message status between Integration layer (WhatsAppMessage)
    and Domain layer (Message).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def handle_status_update(
        self,
        domain_message_id: UUID,
        new_status: MessageStatus,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Update domain message status and trigger events.

        Args:
            domain_message_id: ID of the domain Message
            new_status: New status to apply
            error_message: Optional error message
            metadata: Optional additional metadata
        """
        try:
            # Fetch domain message
            stmt = select(Message).where(Message.id == domain_message_id)
            result = await self.db.execute(stmt)
            message = result.scalar_one_or_none()

            if not message:
                logger.warning(
                    f"Domain message {domain_message_id} not found for status update"
                )
                return

            # Update status
            message.status = new_status
            message.updated_at = datetime.now(timezone.utc)

            if error_message:
                # Append to existing metadata or create new
                if not message.message_metadata:
                    message.message_metadata = {}
                message.message_metadata["error"] = error_message
                message.message_metadata["last_error_at"] = (
                    datetime.now(timezone.utc).isoformat()
                )

            if metadata:
                if not message.message_metadata:
                    message.message_metadata = {}
                message.message_metadata.update(metadata)

            # Update timestamps based on status
            now = datetime.now(timezone.utc)
            if new_status == MessageStatus.SENT:
                message.sent_at = now
            elif new_status == MessageStatus.DELIVERED:
                message.delivered_at = now
            elif new_status == MessageStatus.READ:
                message.read_at = now
            elif new_status == MessageStatus.FAILED:
                # Don't overwrite failed_at if already set (keep first failure)
                if not message.failed_at:
                    message.failed_at = now

            await self.db.commit()

            # Publish WebSocket event
            await self._publish_event(message, new_status, error_message)

            logger.info(
                f"Updated domain message {domain_message_id} status to {new_status.value}"
            )

        except Exception as e:
            logger.error(
                f"Failed to handle status update for message {domain_message_id}: {e}"
            )
            # Don't raise, just log - we don't want to break the integration layer

    async def _publish_event(
        self, message: Message, status: MessageStatus, error_message: Optional[str]
    ):
        """Publish WebSocket event for status change."""
        event_type = WebSocketEventType.MESSAGE_UPDATED

        if status == MessageStatus.SENT:
            event_type = WebSocketEventType.MESSAGE_SENT
        elif status == MessageStatus.FAILED:
            event_type = WebSocketEventType.MESSAGE_FAILED
        elif status == MessageStatus.DELIVERED:
            event_type = WebSocketEventType.MESSAGE_DELIVERED
        elif status == MessageStatus.READ:
            event_type = WebSocketEventType.MESSAGE_READ

        payload = {
            "status": status.value,
            "updated_at": message.updated_at.isoformat()
            if message.updated_at
            else None,
        }

        if error_message:
            payload["error"] = error_message

        await websocket_events.publish_message_event(
            event_type=event_type,
            message_id=message.id,
            patient_id=message.patient_id,
            direction=message.direction.value,
            message_type=message.type.value,
            content=message.content,
            status=status.value,
            metadata=payload,
        )
