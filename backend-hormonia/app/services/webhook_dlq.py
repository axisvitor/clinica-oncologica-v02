"""
Webhook Dead Letter Queue (DLQ) Service.

Handles failed webhook events with retry logic and exponential backoff.
Implements MEDIUM-005: Dead Letter Queue for failed webhooks.

Architecture:
- Uses Redis LIST for DLQ storage (FIFO with priority)
- Exponential backoff: 60s, 120s, 240s, 480s
- Max retries: 5 attempts (configurable)
- Automatic cleanup of aged failed events
- Monitoring metrics for DLQ size and failure rates

Integration:
- WebhookProcessor sends failed events to DLQ
- Celery periodic task processes DLQ every minute
- Alerts trigger on DLQ overflow (>1000 events)
"""

import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from uuid import UUID

from redis.asyncio import Redis

from app.core.redis_unified import get_async_redis

logger = logging.getLogger(__name__)


class WebhookDLQ:
    """
    Dead Letter Queue for failed webhook events.

    Responsibilities:
    1. Store failed webhook events with retry metadata
    2. Process DLQ with exponential backoff
    3. Track retry attempts and failure reasons
    4. Provide metrics for monitoring
    5. Auto-cleanup aged events
    """

    # DLQ configuration
    DLQ_KEY_PREFIX = "webhook:dlq"
    DLQ_METADATA_KEY = "webhook:dlq:metadata"
    MAX_RETRIES = 5
    BASE_RETRY_DELAY = 60  # 60 seconds
    MAX_DLQ_SIZE = 10000  # Alert threshold
    EVENT_TTL_DAYS = 7  # Auto-cleanup after 7 days

    def __init__(self, db: Any, redis: Optional[Redis] = None):
        """
        Initialize DLQ service.

        Args:
            db: Database session
            redis: Optional Redis client (will use shared if not provided)
        """
        self.db = db
        self._redis = redis
        self.logger = logger

    @property
    async def redis(self) -> Redis:
        """Get Redis client (lazy load)."""
        if self._redis is None:
            self._redis = await get_async_redis()
        return self._redis

    async def send_to_dlq(
        self,
        event_id: UUID,
        event_type: str,
        event_data: Dict[str, Any],
        error: str,
        retry_count: int = 0,
        original_timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        Send failed webhook event to DLQ.

        Args:
            event_id: Unique event identifier
            event_type: Type of webhook event (e.g., 'message.received')
            event_data: Original webhook payload
            error: Error message explaining failure
            retry_count: Current retry count
            original_timestamp: Original event timestamp

        Returns:
            True if successfully added to DLQ
        """
        try:
            redis_client = await self.redis

            # Create DLQ entry
            dlq_entry = {
                "event_id": str(event_id),
                "event_type": event_type,
                "event_data": event_data,
                "error": error,
                "retry_count": retry_count,
                "max_retries": self.MAX_RETRIES,
                "timestamp": (original_timestamp or datetime.utcnow()).isoformat(),
                "added_to_dlq_at": datetime.utcnow().isoformat(),
                "next_retry_at": self._calculate_next_retry(retry_count).isoformat(),
            }

            # Add to DLQ (Redis LIST - FIFO)
            dlq_key = f"{self.DLQ_KEY_PREFIX}:{event_type}"
            await redis_client.rpush(dlq_key, json.dumps(dlq_entry))

            # Set TTL on DLQ list (auto-cleanup)
            await redis_client.expire(dlq_key, self.EVENT_TTL_DAYS * 86400)

            # Update metadata (statistics)
            await self._update_dlq_metadata(event_type, "added")

            self.logger.info(
                f"Added event to DLQ: {event_id} (type={event_type}, retry={retry_count})",
                extra={
                    "event_id": str(event_id),
                    "event_type": event_type,
                    "retry_count": retry_count,
                    "error": error[:100],  # Truncate error
                },
            )

            # Check for DLQ overflow and alert if needed
            await self._check_dlq_overflow(event_type)

            return True

        except Exception as e:
            self.logger.error(f"Failed to add event to DLQ: {e}", exc_info=True)
            return False

    async def process_dlq(
        self, batch_size: int = 50, event_type: Optional[str] = None
    ) -> int:
        """
        Process DLQ events with exponential backoff.

        Processes events that are ready for retry based on next_retry_at timestamp.

        Args:
            batch_size: Maximum number of events to process per batch
            event_type: Optional filter by event type

        Returns:
            Number of events successfully processed
        """
        try:
            redis_client = await self.redis
            processed_count = 0

            # Get DLQ keys (all event types or specific)
            if event_type:
                dlq_keys = [f"{self.DLQ_KEY_PREFIX}:{event_type}"]
            else:
                # Get all DLQ keys
                pattern = f"{self.DLQ_KEY_PREFIX}:*"
                dlq_keys = await redis_client.keys(pattern)

            current_time = datetime.utcnow()

            for dlq_key in dlq_keys:
                # Process batch from this DLQ
                for _ in range(batch_size):
                    # Get next event (FIFO - left pop)
                    event_json = await redis_client.lpop(dlq_key)
                    if not event_json:
                        break  # Queue empty

                    try:
                        event = json.loads(event_json)

                        # Check if ready for retry
                        next_retry_at = datetime.fromisoformat(event["next_retry_at"])
                        if current_time < next_retry_at:
                            # Not ready yet - put back at front of queue
                            await redis_client.lpush(dlq_key, event_json)
                            break  # Skip rest of batch (ordered by time)

                        # Process event
                        success = await self._retry_webhook_event(event)

                        if success:
                            processed_count += 1
                            await self._update_dlq_metadata(
                                event["event_type"], "processed"
                            )
                            self.logger.info(
                                f"Successfully processed DLQ event: {event['event_id']}"
                            )
                        else:
                            # Retry failed - check if should re-queue
                            retry_count = event["retry_count"] + 1

                            if retry_count >= event["max_retries"]:
                                # Max retries exceeded - move to dead letter
                                await self._move_to_dead_letter(event)
                                await self._update_dlq_metadata(
                                    event["event_type"], "dead_letter"
                                )
                                self.logger.warning(
                                    f"Event exceeded max retries: {event['event_id']} "
                                    f"({retry_count}/{event['max_retries']})"
                                )
                            else:
                                # Re-queue with updated retry count
                                event["retry_count"] = retry_count
                                event["next_retry_at"] = self._calculate_next_retry(
                                    retry_count
                                ).isoformat()
                                await redis_client.rpush(dlq_key, json.dumps(event))
                                await self._update_dlq_metadata(
                                    event["event_type"], "requeued"
                                )
                                self.logger.info(
                                    f"Re-queued event for retry: {event['event_id']} "
                                    f"(attempt {retry_count}/{event['max_retries']})"
                                )

                    except json.JSONDecodeError as e:
                        self.logger.error(f"Invalid JSON in DLQ: {e}")
                        continue
                    except Exception as e:
                        self.logger.error(
                            f"Error processing DLQ event: {e}", exc_info=True
                        )
                        # Put back in queue to avoid losing event
                        await redis_client.rpush(dlq_key, event_json)

            self.logger.info(
                f"DLQ processing complete: {processed_count} events processed"
            )
            return processed_count

        except Exception as e:
            self.logger.error(f"Error in process_dlq: {e}", exc_info=True)
            return 0

    async def _retry_webhook_event(self, event: Dict[str, Any]) -> bool:
        """
        Retry processing a webhook event.

        Routes event to appropriate webhook processor based on event_type.

        Args:
            event: DLQ event entry

        Returns:
            True if processing succeeded
        """
        try:
            event_type = event["event_type"]
            event_data = event["event_data"]

            # Import webhook processor
            from app.services.webhook_processor import WebhookProcessor

            processor = WebhookProcessor(self.db)

            # Route to appropriate handler
            if event_type == "message.received":
                result = await processor.process_message_webhook(event_data)
                return result is not None
            elif event_type == "message.status":
                return await processor.process_status_webhook(event_data)
            elif event_type == "connection.update":
                return await processor.process_connection_webhook(event_data)
            elif event_type == "qrcode.updated":
                return await processor.process_qrcode_webhook(event_data)
            else:
                self.logger.warning(f"Unknown event type for retry: {event_type}")
                return False

        except Exception as e:
            self.logger.error(f"Error retrying webhook event: {e}", exc_info=True)
            return False

    async def _move_to_dead_letter(self, event: Dict[str, Any]) -> None:
        """
        Move event to permanent dead letter storage (max retries exceeded).

        Args:
            event: DLQ event entry
        """
        try:
            redis_client = await self.redis

            # Add to dead letter storage (separate key with longer TTL)
            dead_letter_key = f"webhook:dead_letter:{event['event_type']}"
            event["moved_to_dead_letter_at"] = datetime.utcnow().isoformat()
            await redis_client.rpush(dead_letter_key, json.dumps(event))

            # Set longer TTL (30 days for manual review)
            await redis_client.expire(dead_letter_key, 30 * 86400)

            self.logger.warning(
                f"Moved event to dead letter: {event['event_id']} "
                f"(type={event['event_type']}, retries={event['retry_count']})"
            )

        except Exception as e:
            self.logger.error(
                f"Failed to move event to dead letter: {e}", exc_info=True
            )

    def _calculate_next_retry(self, retry_count: int) -> datetime:
        """
        Calculate next retry time with exponential backoff.

        Formula: BASE_DELAY * (2 ^ retry_count)

        Examples:
            retry_count=0: 60s
            retry_count=1: 120s
            retry_count=2: 240s
            retry_count=3: 480s
            retry_count=4: 960s (16 min)

        Args:
            retry_count: Current retry count

        Returns:
            Next retry timestamp
        """
        delay_seconds = self.BASE_RETRY_DELAY * (2**retry_count)
        # Cap at 30 minutes
        delay_seconds = min(delay_seconds, 1800)
        return datetime.utcnow() + timedelta(seconds=delay_seconds)

    async def _update_dlq_metadata(self, event_type: str, action: str) -> None:
        """
        Update DLQ metadata for monitoring.

        Args:
            event_type: Event type
            action: Action performed (added, processed, requeued, dead_letter)
        """
        try:
            redis_client = await self.redis
            metadata_key = f"{self.DLQ_METADATA_KEY}:{event_type}"

            # Increment counter for action
            await redis_client.hincrby(metadata_key, f"total_{action}", 1)
            await redis_client.hset(
                metadata_key, "last_updated", datetime.utcnow().isoformat()
            )

            # Set TTL
            await redis_client.expire(metadata_key, 7 * 86400)

        except Exception as e:
            self.logger.error(f"Failed to update DLQ metadata: {e}")

    async def _check_dlq_overflow(self, event_type: str) -> None:
        """
        Check for DLQ overflow and trigger alerts if needed.

        Args:
            event_type: Event type to check
        """
        try:
            redis_client = await self.redis
            dlq_key = f"{self.DLQ_KEY_PREFIX}:{event_type}"

            # Get queue size
            queue_size = await redis_client.llen(dlq_key)

            if queue_size > self.MAX_DLQ_SIZE:
                self.logger.error(
                    f"DLQ OVERFLOW ALERT: {event_type} queue size ({queue_size}) "
                    f"exceeded threshold ({self.MAX_DLQ_SIZE})",
                    extra={
                        "event_type": event_type,
                        "queue_size": queue_size,
                        "threshold": self.MAX_DLQ_SIZE,
                        "alert_type": "dlq_overflow",
                    },
                )

                # TODO: Send alert to monitoring system (Sentry, email, etc.)

        except Exception as e:
            self.logger.error(f"Failed to check DLQ overflow: {e}")

    async def get_dlq_stats(self, event_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get DLQ statistics for monitoring.

        Args:
            event_type: Optional filter by event type

        Returns:
            Dictionary with DLQ statistics
        """
        try:
            redis_client = await self.redis
            stats = {}

            # Get all DLQ keys or specific event type
            if event_type:
                dlq_keys = [f"{self.DLQ_KEY_PREFIX}:{event_type}"]
            else:
                pattern = f"{self.DLQ_KEY_PREFIX}:*"
                dlq_keys = await redis_client.keys(pattern)

            total_pending = 0
            by_event_type = {}

            for dlq_key in dlq_keys:
                # Extract event type from key
                event_type_name = dlq_key.decode().split(":")[-1]

                # Get queue size
                queue_size = await redis_client.llen(dlq_key)
                total_pending += queue_size

                # Get metadata
                metadata_key = f"{self.DLQ_METADATA_KEY}:{event_type_name}"
                metadata = await redis_client.hgetall(metadata_key)

                by_event_type[event_type_name] = {
                    "pending": queue_size,
                    "total_added": int(metadata.get(b"total_added", 0)),
                    "total_processed": int(metadata.get(b"total_processed", 0)),
                    "total_requeued": int(metadata.get(b"total_requeued", 0)),
                    "total_dead_letter": int(metadata.get(b"total_dead_letter", 0)),
                    "last_updated": metadata.get(b"last_updated", b"").decode(),
                }

            stats = {
                "total_pending": total_pending,
                "by_event_type": by_event_type,
                "max_dlq_size": self.MAX_DLQ_SIZE,
                "overflow_alert": total_pending > self.MAX_DLQ_SIZE,
            }

            return stats

        except Exception as e:
            self.logger.error(f"Failed to get DLQ stats: {e}", exc_info=True)
            return {"error": str(e)}


# Singleton instance
_webhook_dlq_instance: Optional[WebhookDLQ] = None


def get_webhook_dlq(db: Any) -> WebhookDLQ:
    """
    Get shared WebhookDLQ instance.

    Args:
        db: Database session

    Returns:
        WebhookDLQ instance
    """
    global _webhook_dlq_instance
    if _webhook_dlq_instance is None:
        _webhook_dlq_instance = WebhookDLQ(db)
    return _webhook_dlq_instance
