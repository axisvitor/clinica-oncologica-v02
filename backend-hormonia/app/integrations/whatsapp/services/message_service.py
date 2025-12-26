"""
WhatsApp message service with queue management and retry logic.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from uuid import uuid4
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .evolution_client import EvolutionAPIClient, validate_phone_number
from ..models.message import (
    WhatsAppMessage,
    WhatsAppContact,
    MessageRequest,
    MessageResponse,
    MessageStatus,
    MessageType,
)
from app.services.circuit_breaker import CircuitBreaker, CircuitOpenError
from app.core.tracing import get_tracer, trace
from app.core.distributed_lock import acquire_lock, LockAcquisitionError, LockKeys

logger = logging.getLogger(__name__)


class MessageQueue:
    """Redis-based message queue for reliable delivery."""

    def __init__(self, redis_url: Optional[str] = None):
        # Use REDIS_URL from environment (Redis Cloud URL)
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        self.redis_client: Optional[redis.Redis] = None
        self.queue_name = "whatsapp:messages"
        self.retry_queue_name = "whatsapp:messages:retry"
        self.dlq_name = "whatsapp:messages:dlq"  # Dead letter queue

    async def connect(self):
        """Connect to Redis."""
        if not self.redis_client:
            self.redis_client = redis.from_url(self.redis_url)

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.aclose()  # Redis 5.x uses aclose() for async

    async def enqueue_message(
        self, message_data: Dict[str, Any], priority: int = 0, delay_seconds: int = 0
    ):
        """Enqueue message for processing."""
        await self.connect()

        message_payload = {
            "id": str(uuid4()),
            "data": message_data,
            "priority": priority,
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
            "retry_count": 0,
            "max_retries": 3,
        }

        if delay_seconds > 0:
            # Schedule for future processing
            execute_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
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
                    {**message_payload, "failed_at": datetime.now(timezone.utc).isoformat()}
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
        execute_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_delay)

        retry_payload = {
            **message_payload,
            "retry_count": retry_count,
            "retried_at": datetime.now(timezone.utc).isoformat(),
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
        now = datetime.now(timezone.utc).timestamp()

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
        evolution_client: EvolutionAPIClient,
        db_session: AsyncSession,
        message_queue: MessageQueue,
        message_status_handler: Optional[Any] = None,  # Avoid circular import
    ):
        self.evolution_client = evolution_client
        self.db_session = db_session
        self.message_queue = message_queue
        self.message_status_handler = message_status_handler
        self._processing = False

        # Circuit breaker for Evolution API
        self.evolution_breaker = CircuitBreaker(
            name="evolution_api_queue",
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
            timestamp=datetime.now(timezone.utc),
        )

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
            message.failed_at = datetime.now(timezone.utc)
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

    @trace(name="send_message_impl", attributes={"service": "evolution_api"})
    async def _send_message_impl(
        self, message: WhatsAppMessage, request_data: Dict[str, Any]
    ):
        """Implementation of message sending with circuit breaker and retry."""
        request = MessageRequest(**request_data)

        async def _send_with_breaker():
            """Wrapped send function with circuit breaker."""
            if request.message_type == MessageType.TEXT:
                response = await self.evolution_client.send_text_message(
                    instance_name=request.instance_name,
                    to=request.to,
                    text=request.text,
                    message_data=request.message_data,
                )
            else:
                response = await self.evolution_client.send_media_message(
                    instance_name=request.instance_name,
                    to=request.to,
                    media_url=request.media_url,
                    media_type=request.message_type,
                    caption=request.media_caption,
                    filename=request.filename,
                    message_data=request.message_data,
                )
            return response

        try:
            # Use circuit breaker with retry
            response = await self.evolution_breaker.call(_send_with_breaker)

            # Update message with Evolution API response
            message.external_id = response.external_id
            message.status = MessageStatus.SENT
            message.sent_at = datetime.now(timezone.utc)

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
                f"Circuit breaker open for Evolution API, message {message.id} cannot be sent"
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
        now = datetime.now(timezone.utc)
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
        """Synchronize contacts from WhatsApp."""
        try:
            contacts = await self.evolution_client.get_contacts(instance_name)
            synced_count = 0

            for contact_response in contacts:
                # Check if contact exists
                stmt = select(WhatsAppContact).where(
                    WhatsAppContact.instance_name == instance_name,
                    WhatsAppContact.phone_number == contact_response.phone_number,
                )
                result = await self.db_session.execute(stmt)
                existing_contact = result.scalar_one_or_none()

                if existing_contact:
                    # Update existing contact
                    existing_contact.name = contact_response.name
                    existing_contact.profile_picture_url = (
                        contact_response.profile_picture_url
                    )
                    existing_contact.updated_at = datetime.now(timezone.utc)
                else:
                    # Create new contact
                    contact = WhatsAppContact(
                        id=str(uuid4()),
                        instance_name=instance_name,
                        phone_number=contact_response.phone_number,
                        formatted_number=contact_response.formatted_number,
                        name=contact_response.name,
                        profile_picture_url=contact_response.profile_picture_url,
                    )
                    self.db_session.add(contact)

                synced_count += 1

            await self.db_session.commit()
            logger.info(
                f"Synchronized {synced_count} contacts for instance {instance_name}"
            )
            return synced_count

        except Exception as e:
            logger.error(f"Error syncing contacts for instance {instance_name}: {e}")
            raise
