"""
Connection webhook handler for Evolution API integration.
Processes connection state and QR code updates.
"""
import logging
from typing import Any, Optional
from datetime import datetime

from app.config.settings.cache import cache_settings
from app.repositories.connection_state import ConnectionStateRepository
from app.core.redis_unified import get_async_redis
from app.utils.db_retry import with_db_retry

logger = logging.getLogger(__name__)


class ConnectionWebhookHandler:
    """
    Handler for connection and QR code webhooks.
    
    Processes:
    - connection.update events (open, close, connecting)
    - qrcode.updated events (QR code for scanning)
    """
    
    def __init__(
        self,
        connection_state_repo: Optional[ConnectionStateRepository] = None
    ):
        """
        Initialize connection handler.
        
        Args:
            connection_state_repo: Optional connection state repository
        """
        self.connection_state_repo = connection_state_repo or ConnectionStateRepository()
    
    @with_db_retry(max_retries=3)
    async def process_connection(
        self,
        event_data: dict[str, Any],
        webhook_store: Optional[Any] = None
    ) -> bool:
        """
        Process connection status webhook (connection.update events).
        
        Handles WhatsApp instance connection state changes:
        - open: Instance is connected
        - close: Instance disconnected
        - connecting: Instance is connecting
        
        Args:
            event_data: Webhook event data
            webhook_store: Optional webhook persistence store
            
        Returns:
            True if processed successfully
        """
        webhook_id = None
        try:
            # Persist webhook event if store provided
            if webhook_store:
                webhook_id = await webhook_store.persist_event(
                    event_type="connection.update",
                    source="evolution_api",
                    payload=event_data
                )
            
            # Extract connection data
            instance = event_data.get("instance")
            state = event_data.get("state") or event_data.get("data", {}).get("state")
            
            if not instance or not state:
                logger.warning("Missing instance or state in connection webhook")
                if webhook_id and webhook_store:
                    await webhook_store.mark_processed(webhook_id, False, "Missing required fields")
                return False
            
            # Update connection state in Redis
            await self.connection_state_repo.set_state(instance, state)
            
            logger.info(
                f"Updated connection state for instance '{instance}': {state}",
                extra={"instance": instance, "state": state}
            )
            
            if webhook_id and webhook_store:
                await webhook_store.mark_processed(webhook_id, True)
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing connection webhook: {e}", exc_info=True)
            if webhook_id and webhook_store:
                await webhook_store.mark_processed(webhook_id, False, str(e))
            return False
    
    @with_db_retry(max_retries=3)
    async def process_qrcode(
        self,
        event_data: dict[str, Any],
        webhook_store: Optional[Any] = None
    ) -> bool:
        """
        Process QR code webhook (qrcode.updated events).
        
        Stores QR code data in Redis for UI display.
        
        Args:
            event_data: Webhook event data containing QR code
            webhook_store: Optional webhook persistence store
            
        Returns:
            True if processed successfully
        """
        webhook_id = None
        try:
            # Persist webhook event if store provided
            if webhook_store:
                webhook_id = await webhook_store.persist_event(
                    event_type="qrcode.updated",
                    source="evolution_api",
                    payload=event_data
                )
            
            # Extract QR code data
            instance = event_data.get("instance")
            qr_code = event_data.get("qrcode") or event_data.get("data", {}).get("qrcode")
            
            if not instance:
                logger.warning("Missing instance in QR code webhook")
                if webhook_id and webhook_store:
                    await webhook_store.mark_processed(webhook_id, False, "Missing instance")
                return False
            
            # Store QR code in Redis with metadata
            redis_client = await get_async_redis()
            qr_key = f"qrcode:{instance}"
            qr_data = {
                "instance": instance,
                "qrcode": qr_code,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "pending"
            }
            
            # Store with QR code TTL (QR codes expire quickly)
            await redis_client.setex(
                qr_key,
                cache_settings.QRCODE_TTL,
                str(qr_data)
            )
            
            logger.info(
                f"Stored QR code for instance '{instance}'",
                extra={"instance": instance, "has_qrcode": bool(qr_code)}
            )
            
            if webhook_id and webhook_store:
                await webhook_store.mark_processed(webhook_id, True)
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing QR code webhook: {e}", exc_info=True)
            if webhook_id and webhook_store:
                await webhook_store.mark_processed(webhook_id, False, str(e))
            return False
