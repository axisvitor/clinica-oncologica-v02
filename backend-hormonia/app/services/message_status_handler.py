import logging
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.message import DeliveryStatus, Message, MessageStatus
import app.services.websocket_events as websocket_events_module
from app.schemas.websocket import WebSocketEventType
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class MessageStatusHandler:
    """
    Handles synchronization of message status between Integration layer (WhatsAppMessage)
    and Domain layer (Message).
    """

    _STATUS_TO_DELIVERY_STATUS = {
        MessageStatus.SENT: DeliveryStatus.SENT,
        MessageStatus.DELIVERED: DeliveryStatus.DELIVERED,
        MessageStatus.READ: DeliveryStatus.READ,
        MessageStatus.FAILED: DeliveryStatus.FAILED,
        MessageStatus.CANCELLED: DeliveryStatus.CANCELLED,
    }
    _FAILURE_REASON_FALLBACK = "Message delivery failed"
    _FAILURE_REASON_KEYS = ("failure_reason", "error_message", "error", "reason")

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

            now = now_sao_paulo()

            # Update status
            message.status = new_status
            message.updated_at = now

            if error_message:
                # Append to existing metadata or create new
                if not message.message_metadata:
                    message.message_metadata = {}
                message.message_metadata["error"] = error_message
                message.message_metadata["last_error_at"] = now.isoformat()

            if metadata:
                if not message.message_metadata:
                    message.message_metadata = {}
                message.message_metadata.update(metadata)

            # Update timestamps based on status
            if new_status == MessageStatus.SENT:
                message.sent_at = now
            elif new_status == MessageStatus.DELIVERED:
                message.delivered_at = now
            elif new_status == MessageStatus.READ:
                message.read_at = now
            elif new_status == MessageStatus.FAILED:
                failure_reason = self._resolve_failure_reason(
                    message=message,
                    error_message=error_message,
                    metadata=metadata,
                )
                message.failure_reason = failure_reason
                message.last_retry_at = now

                if not message.message_metadata:
                    message.message_metadata = {}
                message.message_metadata.setdefault("error", failure_reason)
                message.message_metadata["last_error_at"] = now.isoformat()

            self._sync_delivery_status(message, new_status)

            await self.db.commit()

            # Publish WebSocket event
            publish_error = error_message
            if new_status == MessageStatus.FAILED and not publish_error:
                publish_error = message.failure_reason
            await self._publish_event(message, new_status, publish_error)

            logger.info(
                f"Updated domain message {domain_message_id} status to {new_status.value}"
            )

        except Exception as e:
            logger.error(
                f"Failed to handle status update for message {domain_message_id}: {e}"
            )
            # Don't raise, just log - we don't want to break the integration layer

    def _resolve_failure_reason(
        self,
        message: Message,
        error_message: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> str:
        """Resolve failure reason from explicit error, metadata, or a stable fallback."""
        candidates = [error_message, message.failure_reason]

        if metadata:
            candidates.extend(metadata.get(key) for key in self._FAILURE_REASON_KEYS)

        if message.message_metadata:
            candidates.extend(
                message.message_metadata.get(key) for key in self._FAILURE_REASON_KEYS
            )

        for candidate in candidates:
            if isinstance(candidate, str):
                value = candidate.strip()
                if value:
                    return value

        return self._FAILURE_REASON_FALLBACK

    def _sync_delivery_status(
        self, message: Message, status: MessageStatus
    ) -> None:
        """Keep `delivery_status` aligned with terminal/progress statuses."""
        target = self._STATUS_TO_DELIVERY_STATUS.get(status)
        if not target:
            return

        current = message.delivery_status
        current_value = current.value if isinstance(current, DeliveryStatus) else current
        if current_value != target.value:
            message.delivery_status = target

    async def _publish_event(
        self, message: Message, status: MessageStatus, error_message: Optional[str]
    ):
        """Publish WebSocket event for status change."""
        event_type = WebSocketEventType.MESSAGE_STATUS_UPDATED

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

        websocket_events = websocket_events_module.websocket_events
        if not websocket_events:
            logger.debug("WebSocket events service unavailable; skipping status event")
            return

        await websocket_events.broadcast_message_event(
            event_type=event_type,
            message_data={
                "message_id": message.id,
                "patient_id": message.patient_id,
                "direction": message.direction.value,
                "type": message.type.value,
                "content": message.content,
                "status": status.value,
                "whatsapp_id": message.whatsapp_id,
                "metadata": payload,
            },
        )
