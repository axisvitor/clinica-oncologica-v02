"""
Webhook processor for Evolution API integration.
Handles incoming messages from WhatsApp and processes them through the flow engine.

This module delegates processing to specialized handlers:
- app.services.webhook.handlers.message_handler.MessageWebhookHandler
- app.services.webhook.handlers.status_handler.StatusWebhookHandler
- app.services.webhook.handlers.connection_handler.ConnectionWebhookHandler
- app.services.webhook.persistence.webhook_store.WebhookEventStore

The original monolithic implementation (1,291 lines) has been decomposed into:
- handlers/ (message, status, connection) - ~880 lines
- utils/ (phone_normalizer, message_extractor) - ~320 lines
- persistence/ (webhook_store) - ~320 lines
"""

import logging
from typing import Any, Optional, Dict
from datetime import timedelta
from uuid import UUID
from sqlalchemy import text

from app.repositories.connection_state import ConnectionStateRepository
from app.utils.db_retry import with_db_retry

from app.services.webhook.handlers import (
    MessageWebhookHandler,
    StatusWebhookHandler,
    ConnectionWebhookHandler,
)
from app.services.webhook.persistence import WebhookEventStore
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class WebhookProcessor:
    """
    Process webhooks from Evolution API for WhatsApp messages.

    Delegates processing to specialized handlers:
    - MessageWebhookHandler: Message processing with flow routing
    - StatusWebhookHandler: Delivery status updates
    - ConnectionWebhookHandler: Connection and QR code events
    - WebhookEventStore: Persistence and retry logic

    Responsibilities (delegated to handlers):
    1. Normalize and validate incoming webhook data
    2. Find or create patient based on phone number
    3. Create inbound message record
    4. Publish WebSocket events
    5. Route to appropriate handler (Flow Engine or General Chat)
    6. Generate and send responses
    """

    def __init__(
        self,
        db: Any,
        connection_state_repository: Optional[ConnectionStateRepository] = None,
    ):
        """
        Initialize webhook processor with required services.

        Args:
            db: Database session
            connection_state_repository: Optional connection state repository
        """
        self.db = db

        self.message_handler = MessageWebhookHandler(db)
        self.status_handler = StatusWebhookHandler(db)
        self.connection_handler = ConnectionWebhookHandler(connection_state_repository)
        self.webhook_store = WebhookEventStore(db)

        logger.info("WebhookProcessor initialized with modular handlers")

    @with_db_retry(max_retries=3)
    async def process_message_webhook(
        self,
        event_data: dict[str, Any],
        webhook_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Process incoming message webhook from Evolution API.

        REFACTORED: Delegates to MessageWebhookHandler for all processing.

        The handler implements:
        - Webhook persistence (P0 FIX #2)
        - Message extraction and validation
        - Idempotency checks (Redis + DB)
        - Patient lookup with security monitoring
        - Flow routing and general chat handling
        - Response generation and sending

        Args:
            event_data: Webhook event data from Evolution API
            webhook_id: Optional webhook event ID header (for persistence)

        Returns:
            Message ID if processed successfully, None otherwise
        """
        try:
            return await self.message_handler.process_message(
                event_data=event_data,
                webhook_store=self.webhook_store,
                webhook_id=webhook_id,
            )
        except Exception as e:
            logger.error(f"Error processing message webhook: {e}", exc_info=True)
            return None

    @with_db_retry(max_retries=3)
    async def process_status_webhook(self, event_data: dict[str, Any]) -> bool:
        """
        Process message status update webhook (delivered, read, etc).

        REFACTORED: Delegates to StatusWebhookHandler.

        The handler implements:
        - Webhook persistence (P0 FIX #2)
        - Status mapping (Evolution API -> Internal)
        - Message record updates

        Args:
            event_data: Webhook event data

        Returns:
            True if processed successfully
        """
        try:
            return await self.status_handler.process_status(
                event_data=event_data, webhook_store=self.webhook_store
            )
        except Exception as e:
            logger.error(f"Error processing status webhook: {e}", exc_info=True)
            return False

    # NOTE: The following methods have been moved to modular handlers/utils:
    # - _extract_message_data -> app.services.webhook.utils.message_extractor
    # - _normalize_phone_e164 -> app.services.webhook.utils.PhoneNormalizer
    # - _find_patient_by_phone -> app.services.webhook.utils.PhoneNormalizer
    # - _clean_phone_number -> app.services.webhook.utils.PhoneNormalizer

    # NOTE: The following methods were moved to modular handlers:
    # - _map_evolution_status -> app.services.webhook.handlers.StatusWebhookHandler
    # - _persist_webhook_event -> app.services.webhook.persistence.WebhookEventStore
    # - _mark_webhook_processed -> app.services.webhook.persistence.WebhookEventStore

    @with_db_retry(max_retries=3)
    async def process_connection_webhook(
        self, event_data: dict[str, Any], webhook_id: Optional[str] = None
    ) -> bool:
        """
        P0 FIX #3: Process connection status webhook (connection.update events).

        REFACTORED: Delegates to ConnectionWebhookHandler.

        The handler implements:
        - Webhook persistence
        - Connection state updates (open, close, connecting)
        - Redis state management

        Args:
            event_data: Webhook event data
            webhook_id: Optional webhook event ID header (for persistence)

        Returns:
            True if processed successfully
        """
        try:
            return await self.connection_handler.process_connection(
                event_data=event_data,
                webhook_store=self.webhook_store,
                webhook_id=webhook_id,
            )
        except Exception as e:
            logger.error(f"Error processing connection webhook: {e}", exc_info=True)
            return False

    @with_db_retry(max_retries=3)
    async def process_qrcode_webhook(self, event_data: dict[str, Any]) -> bool:
        """
        P0 FIX #5: Process QR code webhook (qrcode.updated events).

        REFACTORED: Delegates to ConnectionWebhookHandler.

        The handler implements:
        - Webhook persistence
        - QR code storage in Redis
        - TTL management

        Args:
            event_data: Webhook event data containing QR code

        Returns:
            True if processed successfully
        """
        try:
            return await self.connection_handler.process_qrcode(
                event_data=event_data, webhook_store=self.webhook_store
            )
        except Exception as e:
            logger.error(f"Error processing QR code webhook: {e}", exc_info=True)
            return False

    async def retry_failed_webhooks(self) -> int:
        """
        P0 FIX #4: Retry failed webhook events with exponential backoff.

        Simple retry mechanism:
        - Retry webhooks where processed=false and retry_count < max_retries
        - Exponential backoff: 60s, 120s, 240s
        - Update next_retry_at for scheduling

        Returns:
            Number of webhooks retried
        """
        try:
            # Find webhooks eligible for retry
            select_stmt = text("""
                SELECT id, event_type, payload, retry_count, related_message_id, related_patient_id
                FROM webhook_events
                WHERE processed = false
                  AND retry_count < max_retries
                  AND (next_retry_at IS NULL OR next_retry_at <= NOW())
                ORDER BY created_at ASC
                LIMIT 50
            """)

            results = self.db.execute(select_stmt).fetchall()
            retried_count = 0

            for row in results:
                event_id = UUID(row[0])
                event_type = row[1]
                payload = row[2]
                retry_count = row[3]
                UUID(row[4]) if row[4] else None
                UUID(row[5]) if row[5] else None

                try:
                    # Route to appropriate handler based on event type
                    success = False

                    if event_type == "message.received":
                        message_id = await self.process_message_webhook(payload)
                        success = bool(message_id)
                    elif event_type == "message.status":
                        success = await self.process_status_webhook(payload)
                    elif event_type == "connection.update":
                        success = await self.process_connection_webhook(payload)
                    elif event_type == "qrcode.updated":
                        success = await self.process_qrcode_webhook(payload)
                    else:
                        logger.warning(f"Unknown event type for retry: {event_type}")
                        success = False

                    if success:
                        # Mark as processed using WebhookEventStore
                        await self.webhook_store.mark_processed(event_id, success=True)
                        retried_count += 1
                        logger.info(
                            f"Successfully retried webhook {event_id} (type={event_type})"
                        )
                    else:
                        # Increment retry count and schedule next retry
                        next_retry_delay = 60 * (2**retry_count)  # 60s, 120s, 240s
                        next_retry_at = now_sao_paulo() + timedelta(
                            seconds=next_retry_delay
                        )

                        update_stmt = text("""
                            UPDATE webhook_events
                            SET retry_count = retry_count + 1,
                                next_retry_at = :next_retry_at,
                                error_message = 'Retry failed, will retry again'
                            WHERE id = :event_id
                        """)

                        self.db.execute(
                            update_stmt,
                            {"event_id": str(event_id), "next_retry_at": next_retry_at},
                        )
                        self.db.commit()

                        logger.warning(
                            f"Webhook retry failed: {event_id} "
                            f"(retry_count={retry_count + 1}, next_retry_at={next_retry_at})"
                        )

                except Exception as retry_error:
                    logger.error(
                        f"Error retrying webhook {event_id}: {retry_error}",
                        exc_info=True,
                    )

                    # Update retry count and schedule next retry
                    next_retry_delay = 60 * (2**retry_count)
                    next_retry_at = now_sao_paulo() + timedelta(
                        seconds=next_retry_delay
                    )

                    update_stmt = text("""
                        UPDATE webhook_events
                        SET retry_count = retry_count + 1,
                            next_retry_at = :next_retry_at,
                            error_message = :error_message
                        WHERE id = :event_id
                    """)

                    self.db.execute(
                        update_stmt,
                        {
                            "event_id": str(event_id),
                            "next_retry_at": next_retry_at,
                            "error_message": str(retry_error),
                        },
                    )
                    self.db.commit()

            logger.info(
                f"Webhook retry completed: {retried_count}/{len(results)} succeeded"
            )
            return retried_count

        except Exception as e:
            logger.error(f"Error in retry_failed_webhooks: {e}", exc_info=True)
            return 0
