"""
Status webhook handler for Evolution API integration.
Processes message delivery status updates.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.config.settings.cache import cache_settings
from app.models.message import MessageStatus
from app.models.message_events import MessageStatusEvent
from app.domain.messaging.core import MessageService
import app.services.websocket_events as websocket_events_module
from app.schemas.websocket import WebSocketEventType
from app.core.redis_manager import get_async_redis_client as get_async_redis
from app.utils.db_retry import with_db_retry
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class StatusWebhookHandler:
    """
    Handler for message status update webhooks.

    Processes delivery status updates from Evolution API
    (pending, sent, delivered, read, failed).
    """

    def __init__(self, db: Any):
        """
        Initialize status handler.

        Args:
            db: Database session
        """
        self.db = db
        self.message_service = MessageService(db)

    @with_db_retry(max_retries=3)
    async def process_status(
        self,
        event_data: dict[str, Any],
        webhook_store: Optional[Any] = None,
        webhook_id: Optional[str] = None,
    ) -> bool:
        """
        Process message status update webhook.

        Args:
            event_data: Webhook event data
            webhook_store: Optional webhook persistence store
            webhook_id: Optional webhook event ID header (for persistence)

        Returns:
            True if processed successfully
        """
        stored_event_id = None
        try:
            # Persist webhook event if store provided
            if webhook_store:
                if webhook_id:
                    _, stored_event_id = await webhook_store.persist_event_atomic(
                        event_id=webhook_id,
                        event_type="message.status",
                        source="evolution_api",
                        payload=event_data,
                    )
                else:
                    stored_event_id = await webhook_store.persist_event(
                        event_type="message.status",
                        source="evolution_api",
                        payload=event_data,
                    )

            # Extract status data
            whatsapp_id = event_data.get("key", {}).get("id")
            status = event_data.get("update", {}).get("status")

            if not whatsapp_id or not status:
                logger.warning("Missing required fields in status webhook")
                if stored_event_id and webhook_store:
                    await webhook_store.mark_processed(
                        stored_event_id, False, "Missing required fields"
                    )
                return False

            # FIX: Use atomic SET NX BEFORE database operation to prevent race conditions
            # Bug: Previous code used exists() which is read-only, allowing race condition
            # where two workers could both see key doesn't exist and process same status
            redis_client = None
            try:
                redis_client = await get_async_redis()
            except Exception as redis_error:
                logger.error(
                    "Redis unavailable for status webhook idempotency; "
                    "falling back to DB-only processing",
                    exc_info=True,
                    extra={
                        "instance": "status_webhook_handler",
                        "error_type": type(redis_error).__name__,
                    },
                )
            idempotency_key = f"webhook:status:{whatsapp_id}:{status}"

            if not redis_client:
                # DB-only fallback: check for existing status event
                existing_event = (
                    self.db.query(MessageStatusEvent)
                    .filter(
                        MessageStatusEvent.whatsapp_id == whatsapp_id,
                        MessageStatusEvent.status == self._map_evolution_status(status).value,
                    )
                    .first()
                )
                if existing_event:
                    logger.info(
                        f"Duplicate status webhook detected (DB fallback): "
                        f"{whatsapp_id} -> {status}"
                    )
                    if stored_event_id and webhook_store:
                        await webhook_store.mark_processed(
                            stored_event_id, True, "Duplicate status event (DB)"
                        )
                    return True
                # Not a duplicate -- fall through to processing below
                acquired = True
            else:
                # Atomic acquire: SET NX returns True only if key was set (first worker wins)
                acquired = await redis_client.set(
                    idempotency_key,
                    "processing",
                    nx=True,  # Only set if key doesn't exist
                    ex=cache_settings.CACHE_WEBHOOK_IDEMPOTENCY_TTL_SECONDS
                )

            if not acquired:
                # Another worker is processing or already processed this status
                logger.info(
                    f"Duplicate status webhook detected (atomic check): {whatsapp_id} -> {status}"
                )
                if stored_event_id and webhook_store:
                    await webhook_store.mark_processed(
                        stored_event_id, True, "Duplicate status event"
                    )
                return True

            # Map the new status
            new_status = self._map_evolution_status(status)

            # Get previous status before update for audit trail
            previous_status = None
            existing_message = self.message_service.get_message_by_whatsapp_id(whatsapp_id)
            if existing_message:
                previous_status = existing_message.status.value if existing_message.status else None

            # Update message status (now protected by atomic lock)
            message = self.message_service.update_message_status_by_whatsapp_id(
                whatsapp_id=whatsapp_id, status=new_status
            )

            if message:
                # Create audit trail event for message status change
                status_event = MessageStatusEvent(
                    message_id=message.id,
                    status=new_status.value,
                    previous_status=previous_status,
                    whatsapp_id=whatsapp_id,
                    created_at=now_sao_paulo(),
                    event_metadata={"source": "webhook", "event_type": "message.status"}
                )
                self.db.add(status_event)
                self.db.commit()
                # Publish WebSocket event for status update
                websocket_events = websocket_events_module.websocket_events
                if websocket_events:
                    await websocket_events.broadcast_message_event(
                        event_type=WebSocketEventType.MESSAGE_STATUS_UPDATED,
                        message_data={
                            "message_id": message.id,
                            "patient_id": message.patient_id,
                            "direction": message.direction.value,
                            "type": message.type.value,
                            "status": message.status.value,
                            "whatsapp_id": whatsapp_id,
                            "metadata": {"whatsapp_id": whatsapp_id},
                        },
                    )

                logger.info(f"Updated message {message.id} status to {status}")

                # FIX: Update Redis key to mark as "completed" (key already exists from SET NX)
                # This is informational - the lock was already acquired above
                if redis_client:
                    await redis_client.set(
                        idempotency_key,
                        "completed",
                        ex=cache_settings.CACHE_WEBHOOK_IDEMPOTENCY_TTL_SECONDS
                    )

                if stored_event_id and webhook_store:
                    await webhook_store.mark_processed(stored_event_id, True)
                return True

            logger.warning(f"Message not found for WhatsApp ID: {whatsapp_id}")
            if stored_event_id and webhook_store:
                await webhook_store.mark_processed(
                    stored_event_id, False, "Message not found"
                )
            return False

        except Exception as e:
            logger.error(f"Error processing status webhook: {e}", exc_info=True)
            if stored_event_id and webhook_store:
                await webhook_store.mark_processed(stored_event_id, False, str(e))
            return False

    def _map_evolution_status(self, evolution_status: str) -> MessageStatus:
        """
        Map Evolution API status to internal MessageStatus.

        Args:
            evolution_status: Status from Evolution API

        Returns:
            Internal MessageStatus enum
        """
        status_mapping = {
            "PENDING": MessageStatus.PENDING,
            "SENT": MessageStatus.SENT,
            "DELIVERED": MessageStatus.DELIVERED,
            "READ": MessageStatus.READ,
            "FAILED": MessageStatus.FAILED,
            "ERROR": MessageStatus.FAILED,
        }

        return status_mapping.get(evolution_status.upper(), MessageStatus.PENDING)
