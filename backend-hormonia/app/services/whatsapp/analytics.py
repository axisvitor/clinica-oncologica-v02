"""
Analytics module for WhatsApp metrics and tracking.
"""
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class WhatsAppAnalytics:
    """
    Handles analytics, metrics, and status caching for WhatsApp messages.
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client

    async def track_delivery(
        self,
        message_data: Any,  # Use Any to avoid circular import of WhatsAppMessage
        result: Dict[str, Any]
    ):
        """Track message delivery for analytics."""
        if not self.redis:
            return

        try:
            # Store delivery record
            delivery_data = {
                "phone_number": message_data.phone_number,
                "message_type": message_data.message_type.value,
                "priority": message_data.priority.value,
                "status": result.get("status", "sent"),
                "message_id": result.get("message_id"),
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": message_data.metadata
            }

            # Store in Redis with expiration
            await self.redis.set(
                f"whatsapp:delivery:{result.get('message_id', 'unknown')}",
                delivery_data,
                expire=86400  # 24 hours
            )

            # Update daily statistics
            stats_key = f"whatsapp:stats:{datetime.utcnow().strftime('%Y%m%d')}"
            await self.redis.hincrby(stats_key, "total_sent", 1)
            await self.redis.hincrby(
                stats_key,
                f"type_{message_data.message_type.value}",
                1
            )
            await self.redis.expire(stats_key, 604800)  # 7 days

        except Exception as e:
            logger.warning(f"Failed to track delivery: {e}")

    async def update_delivery_metrics(self, status: str):
        """
        Update delivery metrics in Redis.

        Args:
            status: Delivery status
        """
        if self.redis:
            try:
                # Update daily metrics
                today = datetime.utcnow().strftime("%Y%m%d")
                metrics_key = f"whatsapp:metrics:{today}"

                await self.redis.hincrby(metrics_key, f"status_{status}", 1)
                await self.redis.expire(metrics_key, 604800)  # 7 days

            except Exception as e:
                logger.warning(f"Failed to update delivery metrics: {e}")

    async def update_status_cache(
        self,
        message_id: str,
        status: str,
        timestamp: str
    ):
        """
        Update message status in Redis cache.

        Args:
            message_id: WhatsApp message ID
            status: Delivery status
            timestamp: Status update timestamp
        """
        try:
            if self.redis:
                cache_key = f"whatsapp:status:{message_id}"
                status_data = {
                    "status": status,
                    "timestamp": timestamp,
                    "updated_at": datetime.utcnow().isoformat()
                }

                await self.redis.set(
                    cache_key,
                    status_data,
                    expire=86400  # 24 hours
                )

                logger.debug(f"Cached status for message {message_id}")

        except Exception as e:
            logger.warning(f"Failed to cache status update: {e}")
