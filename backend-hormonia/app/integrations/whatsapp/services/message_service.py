"""
WhatsApp message service with queue management and retry logic.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, urlunparse
from uuid import uuid4
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .evolution_client import validate_phone_number
from ..models.message import (
    WhatsAppMessage,
    WhatsAppContact,
    MessageRequest,
    MessageResponse,
    MessageStatus,
    MessageType,
)
from app.resilience.circuit_breaker import CircuitBreaker, CircuitOpenError
from app.core.tracing import get_tracer, trace
from app.core.distributed_lock import acquire_lock, LockAcquisitionError, LockKeys
from app.config import settings
from app.core.redis_manager import get_async_redis_client, get_redis_connection_kwargs
from app.integrations.wuzapi.media import fetch_and_encode_media
from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive

logger = logging.getLogger(__name__)


def _normalize_redis_url(redis_url: str) -> str:
    """Normalize Redis URL so equivalent URLs compare consistently."""
    parsed = urlparse(redis_url)
    if not parsed.scheme or not parsed.netloc:
        return redis_url

    normalized_path = parsed.path
    if not normalized_path or normalized_path == "/":
        normalized_path = "/0"

    return urlunparse(parsed._replace(path=normalized_path))


def _coerce_redis_url_scheme(redis_url: str) -> str:
    """Normalize Redis URL scheme to match REDIS_ENABLE_SSL setting."""
    if not redis_url:
        return redis_url

    if getattr(settings, "REDIS_ENABLE_SSL", False) and redis_url.startswith("redis://"):
        return "rediss://" + redis_url[8:]

    if (not getattr(settings, "REDIS_ENABLE_SSL", False)) and redis_url.startswith("rediss://"):
        return "redis://" + redis_url[9:]

    return redis_url


class MessageQueue:
    """Redis-based message queue for reliable delivery."""

    def __init__(self, redis_url: Optional[str] = None):
        # Use REDIS_URL from settings (Redis Cloud URL)
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis_client: Optional[redis.Redis] = None
        self._uses_shared_client = False
        self.queue_name = "whatsapp:messages"
        self.retry_queue_name = "whatsapp:messages:retry"
        self.dlq_name = "whatsapp:messages:dlq"  # Dead letter queue

    async def connect(self):
        """Connect to Redis."""
        if not self.redis_client:
            if _normalize_redis_url(self.redis_url) == _normalize_redis_url(settings.REDIS_URL):
                self.redis_client = await get_async_redis_client()
                self._uses_shared_client = True
            else:
                connection_kwargs = get_redis_connection_kwargs(
                    mode="async",
                    decode_responses=getattr(settings, "REDIS_ENABLE_DECODE_RESPONSES", True),
                    socket_timeout=getattr(settings, "REDIS_SOCKET_TIMEOUT_SECONDS", 10.0),
                    socket_connect_timeout=getattr(
                        settings, "REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS", 5.0
                    ),
                    max_connections=getattr(settings, "REDIS_POOL_MAX_CONNECTIONS", 20),
                    retry_on_timeout=getattr(settings, "REDIS_ENABLE_RETRY_ON_TIMEOUT", True),
                )
                self.redis_client = redis.from_url(
                    _coerce_redis_url_scheme(self.redis_url), **connection_kwargs
                )
                self._uses_shared_client = False

    async def disconnect(self):
        """Disconnect from Redis."""
        if not self.redis_client:
            return

        # Shared client lifecycle is managed by RedisManager at application scope.
        if self._uses_shared_client:
            self.redis_client = None
            self._uses_shared_client = False
            return

        if self.redis_client:
            await self.redis_client.aclose()  # Redis 5.x uses aclose() for async
            self.redis_client = None
            self._uses_shared_client = False

    async def enqueue_message(
        self, message_data: Dict[str, Any], priority: int = 0, delay_seconds: int = 0
    ):
        """Enqueue message for processing."""
        await self.connect()

        message_payload = {
            "id": str(uuid4()),
            "data": message_data,
            "priority": priority,
            "enqueued_at": now_sao_paulo().isoformat(),
            "retry_count": 0,
            "max_retries": 3,
        }

        if delay_seconds > 0:
            # Schedule for future processing
            execute_at = now_sao_paulo() + timedelta(seconds=delay_seconds)
            await self.redis_client.zadd(
                f"{self.queue_name}:scheduled",
                {json.dumps(message_payload): execute_at.timestamp()},
            )
        else:
            # Immediate processing
            await self.redis_client.lpush(self.queue_name, json.dumps(message_payload))

    async def dequeue_message(self, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """
        Dequeue message for processing.

        Returns:
            Dict with message data if available
            None if queue is empty (timeout)

        Raises:
            redis.ConnectionError: If Redis is unavailable (caller should handle)
        """
        await self.connect()

        # Ensure blocking timeout stays below socket timeout to prevent Redis timeouts.
        socket_timeout = getattr(settings, "REDIS_SOCKET_TIMEOUT_SECONDS", None)
        if socket_timeout:
            try:
                safe_timeout = max(1, int(float(socket_timeout)) - 1)
                if timeout > safe_timeout:
                    timeout = safe_timeout
            except (TypeError, ValueError):
                pass

        # First check for scheduled messages that are ready
        try:
            await self._process_scheduled_messages()
        except Exception as e:
            # Log but continue - scheduled processing is optional
            logger.warning(f"Failed to process scheduled messages: {e}")

        # Then get next message from main queue
        # FIX: Distinguish between timeout (queue empty) and Redis error
        try:
            result = await self.redis_client.brpop(self.queue_name, timeout=timeout)
            if result:
                _, message_data = result
                return json.loads(message_data)
            # Timeout - queue is empty, this is normal
            return None
        except redis.ConnectionError as e:
            # Redis connection lost - raise to caller for proper handling
            logger.error(f"Redis connection error in dequeue: {e}")
            raise
        except redis.TimeoutError as e:
            # Redis operation timeout - raise to caller
            logger.warning(f"Redis timeout in dequeue: {e}")
            raise

    async def retry_message(
        self, message_payload: Dict[str, Any], delay_seconds: int = 60
    ):
        """Retry failed message with exponential backoff."""
        await self.connect()

        retry_count = message_payload.get("retry_count", 0) + 1
        max_retries = message_payload.get("max_retries", 3)

        # FIX: Off-by-one bug - should be >= not >
        # Previous code used > which allowed one extra retry beyond max_retries
        if retry_count >= max_retries:
            # Move to dead letter queue
            message_id = message_payload.get("id", "unknown")
            await self.redis_client.lpush(
                self.dlq_name,
                json.dumps(
                    {**message_payload, "failed_at": now_sao_paulo().isoformat()}
                ),
            )
            logger.error(
                "Message moved to DLQ after max retries",
                extra={
                    "message_id": message_id,
                    "retry_count": retry_count,
                    "max_retries": max_retries,
                    "action": "dlq_moved",
                },
            )
            return False

        # Calculate exponential backoff delay
        backoff_delay = delay_seconds * (2 ** (retry_count - 1))
        execute_at = now_sao_paulo() + timedelta(seconds=backoff_delay)

        retry_payload = {
            **message_payload,
            "retry_count": retry_count,
            "retried_at": now_sao_paulo().isoformat(),
        }

        await self.redis_client.zadd(
            f"{self.retry_queue_name}:scheduled",
            {json.dumps(retry_payload): execute_at.timestamp()},
        )

        logger.info(
            "Message scheduled for retry with exponential backoff",
            extra={
                "message_id": message_payload.get("id", "unknown"),
                "retry_count": retry_count,
                "max_retries": max_retries,
                "backoff_delay_seconds": backoff_delay,
                "execute_at": execute_at.isoformat(),
            },
        )
        return True

    async def _process_scheduled_messages(self):
        """Move ready scheduled messages to main queue."""
        now = now_sao_paulo().timestamp()

        # Process main scheduled queue
        ready_messages = await self.redis_client.zrangebyscore(
            f"{self.queue_name}:scheduled", 0, now, withscores=True
        )

        for message_data, score in ready_messages:
            await self.redis_client.lpush(self.queue_name, message_data)
            await self.redis_client.zrem(f"{self.queue_name}:scheduled", message_data)

        # Process retry scheduled queue
        ready_retries = await self.redis_client.zrangebyscore(
            f"{self.retry_queue_name}:scheduled", 0, now, withscores=True
        )

        for message_data, score in ready_retries:
            await self.redis_client.lpush(self.queue_name, message_data)
            await self.redis_client.zrem(
                f"{self.retry_queue_name}:scheduled", message_data
            )

    async def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics."""
        await self.connect()

        return {
            "pending": await self.redis_client.llen(self.queue_name),
            "scheduled": await self.redis_client.zcard(f"{self.queue_name}:scheduled"),
            "retry_scheduled": await self.redis_client.zcard(
                f"{self.retry_queue_name}:scheduled"
            ),
            "dead_letter": await self.redis_client.llen(self.dlq_name),
        }


class WhatsAppMessageService:
    """
    WhatsApp message service with ULTRATHINK approach:
    - Message delivery guarantees
    - Queue-based processing
    - Status tracking
    - Contact management
    """

    def __init__(
        self,
        wuzapi_client,
        db_session: AsyncSession,
        message_queue: MessageQueue,
        message_status_handler: Optional[Any] = None,  # Avoid circular import
    ):
        self.wuzapi_client = wuzapi_client
        self.db_session = db_session
        self.message_queue = message_queue
        self.message_status_handler = message_status_handler
        self._processing = False

        # Circuit breaker for WuzAPI
        self.evolution_breaker = CircuitBreaker(
            name="wuzapi_queue",
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=Exception,
        )

        # Tracer for distributed tracing
        self.tracer = get_tracer()

    async def send_message(self, request: MessageRequest) -> MessageResponse:
        """Send WhatsApp message with queue processing."""
        # Validate phone number
        is_valid, formatted_number = await validate_phone_number(request.to)
        if not is_valid:
            raise ValueError(f"Invalid phone number: {formatted_number}")

        # Ensure we send using the normalized number (prevents mismatched delivery)
        request = request.copy(update={"to": formatted_number})

        # Create message record
        message_id = str(uuid4())
        message = WhatsAppMessage(
            id=message_id,
            instance_name=request.instance_name,
            chat_id=f"{formatted_number}@s.whatsapp.net",
            sender_id="",  # Will be set when message is sent
            recipient_id=formatted_number,
            message_type=request.message_type.value,
            content=request.text,
            media_url=request.media_url,
            media_caption=request.media_caption,
            status=MessageStatus.PENDING,
            message_data=request.message_data or {},
        )

        self.db_session.add(message)
        await self.db_session.commit()

        # Queue message for processing
        await self.message_queue.enqueue_message(
            {
                "message_id": message_id,
                "action": "send_message",
                "request": request.dict(),
            }
        )

        return MessageResponse(
            id=message_id,
            status=MessageStatus.PENDING,
            message="Message queued for delivery",
            timestamp=now_sao_paulo(),
        )

    async def process_queue_batch(self, max_messages: int = 100) -> Dict[str, int]:
        """
        Process a bounded number of queue messages.

        This is used by HTTP endpoints and one-off batch jobs where an unmanaged
        infinite worker loop is not acceptable.
        """
        if max_messages < 1:
            raise ValueError("max_messages must be >= 1")

        processed = 0
        failed = 0
        retried = 0
        empty_polls = 0

        consecutive_redis_errors = 0
        max_consecutive_redis_errors = 3

        for _ in range(max_messages):
            try:
                message_payload = await self.message_queue.dequeue_message(timeout=1)
                consecutive_redis_errors = 0
            except (redis.ConnectionError, redis.TimeoutError) as redis_err:
                consecutive_redis_errors += 1
                logger.error(
                    "Redis error while processing queue batch (attempt %s/%s): %s",
                    consecutive_redis_errors,
                    max_consecutive_redis_errors,
                    redis_err,
                )
                if consecutive_redis_errors >= max_consecutive_redis_errors:
                    raise
                await asyncio.sleep(min(2**consecutive_redis_errors, 5))
                continue

            if not message_payload:
                empty_polls += 1
                break

            try:
                await self._process_message(message_payload)
                processed += 1
            except Exception as process_error:
                failed += 1
                logger.error(
                    "Error processing queued message %s in batch: %s",
                    message_payload.get("id"),
                    process_error,
                    exc_info=True,
                )
                try:
                    was_retried = await self.message_queue.retry_message(message_payload)
                    if was_retried:
                        retried += 1
                except Exception as retry_error:
                    logger.error(
                        "Failed to schedule retry for message %s: %s",
                        message_payload.get("id"),
                        retry_error,
                        exc_info=True,
                    )

        queue_stats = await self.message_queue.get_queue_stats()
        return {
            "processed": processed,
            "failed": failed,
            "retried": retried,
            "empty_polls": empty_polls,
            "max_messages": max_messages,
            "queue_pending": queue_stats.get("pending", 0),
            "queue_scheduled": queue_stats.get("scheduled", 0),
            "queue_retry_scheduled": queue_stats.get("retry_scheduled", 0),
            "queue_dead_letter": queue_stats.get("dead_letter", 0),
        }

    async def process_message_queue(self):
        """Process messages from queue with proper error handling."""
        if self._processing:
            return

        self._processing = True
        logger.info("Starting message queue processing")

        # Backoff configuration for Redis connection errors
        base_backoff = 1.0  # seconds
        max_backoff = 60.0  # seconds
        current_backoff = base_backoff
        consecutive_errors = 0
        max_consecutive_errors = 10

        try:
            while True:
                try:
                    message_payload = await self.message_queue.dequeue_message()

                    # Reset backoff on successful dequeue (even if None)
                    current_backoff = base_backoff
                    consecutive_errors = 0

                    if not message_payload:
                        # Queue is empty, wait briefly before checking again
                        await asyncio.sleep(0.1)
                        continue

                    try:
                        await self._process_message(message_payload)
                    except Exception as e:
                        logger.error(
                            f"Error processing message {message_payload.get('id')}: {e}"
                        )
                        await self.message_queue.retry_message(message_payload)

                except (redis.ConnectionError, redis.TimeoutError) as redis_err:
                    # FIX: Handle Redis errors with exponential backoff
                    # instead of spinning in a busy loop
                    consecutive_errors += 1
                    logger.error(
                        f"Redis error in queue processing (attempt {consecutive_errors}): {redis_err}"
                    )

                    if consecutive_errors >= max_consecutive_errors:
                        logger.critical(
                            f"Too many consecutive Redis errors ({consecutive_errors}), stopping queue processor"
                        )
                        raise

                    # Exponential backoff
                    await asyncio.sleep(current_backoff)
                    current_backoff = min(current_backoff * 2, max_backoff)

        except asyncio.CancelledError:
            logger.info("Message queue processing cancelled")
            raise
        except Exception as e:
            logger.error(f"Fatal error in message queue processing: {e}")
            raise
        finally:
            self._processing = False

    async def _process_message(self, message_payload: Dict[str, Any]):
        """
        Process individual message with distributed lock to prevent concurrent processing.

        Uses distributed lock to ensure only one worker processes a given message,
        preventing race conditions when multiple workers dequeue the same message.
        """
        message_id = message_payload["data"]["message_id"]
        action = message_payload["data"]["action"]

        # Acquire distributed lock per message to prevent concurrent processing
        lock_key = LockKeys.message_processing(message_id)
        try:
            async with acquire_lock(lock_key, timeout=5.0, ttl=120):
                await self._process_message_internal(
                    message_payload, message_id, action
                )
        except LockAcquisitionError:
            # Another worker is processing this message, skip
            logger.info(
                f"Message {message_id} already being processed by another worker"
            )
            return

    async def _process_message_internal(
        self, message_payload: Dict[str, Any], message_id: str, action: str
    ):
        """Internal message processing (called within lock context)."""
        # Get message from database
        stmt = select(WhatsAppMessage).where(WhatsAppMessage.id == message_id)
        result = await self.db_session.execute(stmt)
        message = result.scalar_one_or_none()

        if not message:
            logger.error(f"Message {message_id} not found in database")
            return

        # Check if already processed (idempotency)
        if message.status in [MessageStatus.SENT, MessageStatus.DELIVERED]:
            logger.info(f"Message {message_id} already processed, skipping")
            return

        try:
            if action == "send_message":
                await self._send_message_impl(
                    message, message_payload["data"]["request"]
                )

            # Update retry count
            message.retry_count = message_payload.get("retry_count", 0)
            await self.db_session.commit()

        except Exception as e:
            # Update message status to failed
            message.status = MessageStatus.FAILED
            message.error_message = str(e)
            message.failed_at = now_sao_paulo_naive()
            await self.db_session.commit()

            # Sync failure status to domain if handler is present
            if self.message_status_handler and message.message_data:
                domain_id = message.message_data.get("domain_message_id")
                if domain_id:
                    from app.models.message import MessageStatus as DomainMessageStatus

                    await self.message_status_handler.handle_status_update(
                        domain_message_id=domain_id,
                        new_status=DomainMessageStatus.FAILED,
                        error_message=str(e),
                    )
            raise

    @trace(name="send_message_impl", attributes={"service": "wuzapi"})
    async def _send_message_impl(
        self, message: WhatsAppMessage, request_data: Dict[str, Any]
    ):
        """Implementation of message sending with circuit breaker and retry."""
        request = MessageRequest(**request_data)

        async def _send_with_breaker():
            """Send via WuzAPI with circuit breaker."""
            phone = request.to
            if "@" in phone:
                phone = phone.split("@")[0]

            if request.message_type == MessageType.TEXT:
                return await self.wuzapi_client.send_text(
                    phone=phone,
                    message=request.text or "",
                )

            data_uri = await fetch_and_encode_media(request.media_url or "")
            media_type_str = request.message_type.value.lower()
            return await self.wuzapi_client.send_media(
                media_type=media_type_str,
                phone=phone,
                data_uri=data_uri,
                caption=request.media_caption,
                filename=request.filename,
            )

        try:
            # Use circuit breaker with retry
            response = await self.evolution_breaker.call(_send_with_breaker)

            # Update message with WuzAPI response
            message.external_id = response.get("data", {}).get("Id")
            message.status = MessageStatus.SENT
            message.sent_at = now_sao_paulo_naive()

            logger.info(f"Message {message.id} sent successfully")

            # Sync sent status to domain if handler is present
            if self.message_status_handler and message.message_data:
                domain_id = message.message_data.get("domain_message_id")
                if domain_id:
                    from app.models.message import MessageStatus as DomainMessageStatus

                    await self.message_status_handler.handle_status_update(
                        domain_message_id=domain_id, new_status=DomainMessageStatus.SENT
                    )

        except CircuitOpenError:
            logger.error(
                f"Circuit breaker open for WuzAPI, message {message.id} cannot be sent"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to send message {message.id}: {e}")
            raise

    async def update_message_status(
        self,
        external_id: str,
        status: MessageStatus,
        error_message: Optional[str] = None,
    ):
        """Update message status from webhook."""
        stmt = select(WhatsAppMessage).where(WhatsAppMessage.external_id == external_id)
        result = await self.db_session.execute(stmt)
        message = result.scalar_one_or_none()

        if not message:
            logger.warning(f"Message with external_id {external_id} not found")
            return

        message.status = status
        if error_message:
            message.error_message = error_message

        # Update timestamp based on status
        now = now_sao_paulo_naive()
        if status == MessageStatus.DELIVERED:
            message.delivered_at = now
        elif status == MessageStatus.READ:
            message.read_at = now
        elif status == MessageStatus.FAILED:
            message.failed_at = now

        message.updated_at = now
        await self.db_session.commit()

        logger.info(f"Updated message {message.id} status to {status}")

        # Sync status to domain if handler is present
        if self.message_status_handler and message.message_data:
            domain_id = message.message_data.get("domain_message_id")
            if domain_id:
                from app.models.message import MessageStatus as DomainMessageStatus

                # Map WhatsApp status to Domain status
                domain_status = None
                if status == MessageStatus.DELIVERED:
                    domain_status = DomainMessageStatus.DELIVERED
                elif status == MessageStatus.READ:
                    domain_status = DomainMessageStatus.READ
                elif status == MessageStatus.FAILED:
                    domain_status = DomainMessageStatus.FAILED

                if domain_status:
                    await self.message_status_handler.handle_status_update(
                        domain_message_id=domain_id,
                        new_status=domain_status,
                        error_message=error_message,
                    )

    async def get_message_history(
        self, instance_name: str, chat_id: str, limit: int = 50, offset: int = 0
    ) -> List[WhatsAppMessage]:
        """Get message history for a chat."""
        stmt = (
            select(WhatsAppMessage)
            .where(
                WhatsAppMessage.instance_name == instance_name,
                WhatsAppMessage.chat_id == chat_id,
            )
            .order_by(WhatsAppMessage.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db_session.execute(stmt)
        return result.scalars().all()

    async def get_instance_messages(
        self, instance_name: str, limit: int = 50, offset: int = 0
    ) -> List[WhatsAppMessage]:
        """Get recent messages for an instance across all chats."""
        stmt = (
            select(WhatsAppMessage)
            .where(WhatsAppMessage.instance_name == instance_name)
            .order_by(WhatsAppMessage.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db_session.execute(stmt)
        return result.scalars().all()

    async def get_message_statistics(
        self,
        instance_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Get message statistics."""
        stmt = select(WhatsAppMessage).where(
            WhatsAppMessage.instance_name == instance_name
        )

        if start_date:
            stmt = stmt.where(WhatsAppMessage.created_at >= start_date)
        if end_date:
            stmt = stmt.where(WhatsAppMessage.created_at <= end_date)

        result = await self.db_session.execute(stmt)
        messages = result.scalars().all()

        stats = {
            "total": len(messages),
            "sent": sum(1 for m in messages if m.status == MessageStatus.SENT),
            "delivered": sum(
                1 for m in messages if m.status == MessageStatus.DELIVERED
            ),
            "read": sum(1 for m in messages if m.status == MessageStatus.READ),
            "failed": sum(1 for m in messages if m.status == MessageStatus.FAILED),
            "pending": sum(1 for m in messages if m.status == MessageStatus.PENDING),
        }

        return stats

    async def sync_contacts(self, instance_name: str) -> int:
        """Synchronize contacts from WhatsApp.

        NOTE: WuzAPI does not have a contacts API equivalent to Evolution.
        Stubbed out pending Phase 37 removal.
        """
        logger.warning(
            "sync_contacts called but WuzAPI has no contacts API -- returning 0",
            extra={"instance_name": instance_name},
        )
        raise NotImplementedError(
            "sync_contacts is not supported with WuzAPI. "
            "This method will be removed in Phase 37."
        )
