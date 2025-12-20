"""
Idempotent Message Sender Service.

CRITICAL FIX #5: Implement idempotency for message sending to prevent duplicates.

This service ensures that messages are sent exactly once, even with retries or
concurrent requests, by using:
1. Idempotency keys (unique per message intent)
2. Redis cache for fast duplicate detection
3. Database constraints for persistence
4. Automatic retry with same idempotency key

Features:
- Generates or accepts idempotency keys
- Checks Redis cache before sending
- Stores sent messages in database with unique constraint
- Handles retries gracefully
- Cleans up old idempotency records

Usage:
    sender = IdempotentMessageSender(db, redis, evolution_client)
    message = await sender.send_message(
        patient_id=patient_id,
        content="Hello!",
        idempotency_key="optional-custom-key"
    )
"""

import logging
import uuid
import hashlib
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from app.models.message import Message, MessageStatus, MessageDirection, MessageType
from app.models.patient import Patient
from app.integrations.evolution import EvolutionClient

logger = logging.getLogger(__name__)


class IdempotencyError(Exception):
    """Raised when idempotency check fails."""

    pass


class IdempotentMessageSender:
    """
    Service for sending messages with idempotency guarantees.

    Idempotency is achieved through:
    1. Unique idempotency_key per message intent
    2. Redis cache (fast path) - TTL 24 hours
    3. Database unique constraint (persistent)
    4. Automatic key generation if not provided
    """

    def __init__(
        self,
        db: Session,
        redis: Optional[Redis] = None,
        evolution_client: Optional[EvolutionClient] = None,
        cache_ttl: int = 86400,  # 24 hours
        enable_cache: bool = True,
    ):
        """
        Initialize idempotent message sender.

        Args:
            db: Database session
            redis: Redis client (optional, lazy-loaded if not provided)
            evolution_client: Evolution API client (optional, lazy-loaded if not provided)
            cache_ttl: Cache TTL in seconds (default: 24 hours)
            enable_cache: Enable Redis cache (default: True)
        """
        self.db = db
        self._redis = redis
        self._evolution_client = evolution_client
        self.cache_ttl = cache_ttl
        self.enable_cache = enable_cache
        self.cache_prefix = "idempotency:message"

    @property
    def redis(self) -> Redis:
        """Lazy-load Redis client if not provided."""
        if self._redis is None:
            from app.core.redis_unified import get_sync_redis
            self._redis = get_sync_redis()
        return self._redis

    @property
    def evolution_client(self) -> EvolutionClient:
        """Lazy-load Evolution client if not provided."""
        if self._evolution_client is None:
            self._evolution_client = EvolutionClient()
        return self._evolution_client

    def _generate_idempotency_key(
        self,
        patient_id: uuid.UUID,
        content: str,
        message_type: MessageType,
        timestamp: Optional[datetime] = None,
    ) -> str:
        """
        Generate deterministic idempotency key.

        The key is based on:
        - Patient ID
        - Message content
        - Message type
        - Timestamp (optional, for time-based uniqueness)

        Args:
            patient_id: Patient UUID
            content: Message content
            message_type: Message type
            timestamp: Optional timestamp for uniqueness

        Returns:
            Idempotency key (hex string)
        """
        # Use current time if not provided (minute precision)
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Round timestamp to minute for some tolerance
        timestamp_str = timestamp.strftime("%Y%m%d%H%M")

        # Create deterministic hash
        components = f"{patient_id}:{content}:{message_type.value}:{timestamp_str}"
        hash_digest = hashlib.sha256(components.encode("utf-8")).hexdigest()

        return f"msg_{hash_digest[:32]}"

    def _get_cache_key(self, idempotency_key: str) -> str:
        """
        Get Redis cache key for idempotency.

        Args:
            idempotency_key: Idempotency key

        Returns:
            Redis cache key
        """
        return f"{self.cache_prefix}:{idempotency_key}"

    async def _check_cache(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """
        Check Redis cache for existing message.

        Args:
            idempotency_key: Idempotency key

        Returns:
            Cached message data if exists, None otherwise
        """
        if not self.enable_cache:
            return None

        try:
            cache_key = self._get_cache_key(idempotency_key)
            cached = self.redis.get(cache_key)

            if cached:
                import json

                logger.info(f"Cache hit for idempotency key: {idempotency_key[:16]}...")
                return json.loads(cached)

            return None

        except RedisError as e:
            logger.warning(f"Redis cache check failed: {e}")
            return None

    async def _set_cache(
        self, idempotency_key: str, message_data: Dict[str, Any]
    ) -> None:
        """
        Store message in Redis cache.

        Args:
            idempotency_key: Idempotency key
            message_data: Message data to cache
        """
        if not self.enable_cache:
            return

        try:
            import json

            cache_key = self._get_cache_key(idempotency_key)
            self.redis.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(message_data, default=str),
            )
            logger.debug(f"Cached message with key: {idempotency_key[:16]}...")

        except RedisError as e:
            logger.warning(f"Redis cache set failed: {e}")

    async def _check_database(
        self, patient_id: uuid.UUID, idempotency_key: str
    ) -> Optional[Message]:
        """
        Check database for existing message by idempotency key.

        Args:
            patient_id: Patient UUID
            idempotency_key: Idempotency key

        Returns:
            Existing message if found, None otherwise
        """
        try:
            # Query for message with same idempotency_key
            stmt = select(Message).where(
                Message.patient_id == patient_id,
                Message.idempotency_key == idempotency_key,
            )
            result = self.db.execute(stmt)
            message = result.scalar_one_or_none()

            if message:
                logger.info(
                    f"Database hit for idempotency key: {idempotency_key[:16]}... "
                    f"(message_id: {message.id})"
                )

            return message

        except Exception as e:
            logger.error(f"Database idempotency check failed: {e}", exc_info=True)
            return None

    def _serialize_message(self, message: Message) -> Dict[str, Any]:
        """
        Serialize message to dictionary (for cache and response).

        Args:
            message: Message object

        Returns:
            Serialized message
        """
        return {
            "id": str(message.id),
            "patient_id": str(message.patient_id),
            "direction": message.direction.value,
            "type": message.type.value,
            "content": message.content,
            "status": message.status.value,
            "whatsapp_id": message.whatsapp_id,
            "idempotency_key": message.idempotency_key,
            "sent_at": message.sent_at.isoformat() if message.sent_at else None,
            "created_at": message.created_at.isoformat(),
        }

    async def send_message(
        self,
        patient_id: uuid.UUID,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        scheduled_for: Optional[datetime] = None,
    ) -> Tuple[Message, bool]:
        """
        Send message with idempotency guarantee.

        This method ensures that even if called multiple times with the same
        parameters, the message is only sent once.

        Args:
            patient_id: Patient UUID
            content: Message content
            message_type: Message type (default: TEXT)
            metadata: Optional metadata (buttons, media, etc.)
            idempotency_key: Optional custom idempotency key
            scheduled_for: Optional scheduled time

        Returns:
            Tuple of (Message object, is_duplicate boolean)
            - is_duplicate=True means message was already sent (idempotent return)
            - is_duplicate=False means message was newly sent

        Raises:
            IdempotencyError: If idempotency check fails critically
            ValueError: If content is empty
            Exception: If sending fails
        """
        # 0. Validate content is not empty
        if not content or not content.strip():
            raise ValueError(
                f"Cannot send empty message to patient {patient_id}. "
                f"Content must be a non-empty string. Received: {repr(content)}"
            )

        # 1. Generate or use provided idempotency key
        if idempotency_key is None:
            idempotency_key = self._generate_idempotency_key(
                patient_id=patient_id,
                content=content,
                message_type=message_type,
                timestamp=scheduled_for,
            )

        logger.info(
            f"Attempting to send message to patient {patient_id} "
            f"with idempotency key: {idempotency_key[:16]}..."
        )

        # 2. Check Redis cache (fast path)
        cached = await self._check_cache(idempotency_key)
        if cached:
            # Return cached message (already sent)
            logger.info("Message already sent (cache hit), returning cached result")

            # Reconstruct message object from cache
            existing_message = await self._check_database(patient_id, idempotency_key)
            if existing_message:
                return existing_message, True

            # If not in DB, continue to send (cache invalidation case)
            logger.warning("Cache hit but DB miss, proceeding to send")

        # 3. Check database (persistent check)
        existing_message = await self._check_database(patient_id, idempotency_key)
        if existing_message:
            # Message already sent
            logger.info(
                f"Message already sent (DB hit), returning existing message "
                f"(id: {existing_message.id})"
            )

            # Update cache
            await self._set_cache(
                idempotency_key, self._serialize_message(existing_message)
            )

            return existing_message, True

        # 4. Verify patient exists
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise ValueError(f"Patient {patient_id} not found")

        # 5. Create message in database
        try:
            message = Message(
                patient_id=patient_id,
                direction=MessageDirection.OUTBOUND,
                type=message_type,
                content=content,
                message_metadata=metadata or {},
                status=MessageStatus.PENDING,
                scheduled_for=scheduled_for,
                idempotency_key=idempotency_key,
            )

            self.db.add(message)
            self.db.flush()  # Get ID without committing

            logger.info(f"Created message in DB with id: {message.id}")

        except IntegrityError as e:
            # Another process/thread created the message concurrently
            self.db.rollback()
            logger.warning(f"Concurrent creation detected: {e}")

            # Re-fetch the message
            existing_message = await self._check_database(patient_id, idempotency_key)
            if existing_message:
                return existing_message, True

            # If still not found, re-raise
            raise IdempotencyError(
                f"Concurrent message creation failed for key: {idempotency_key}"
            )

        # 6. Send message via Evolution API
        try:
            logger.info(f"Sending message {message.id} via Evolution API")

            # Update status to SENDING
            message.status = MessageStatus.SENDING
            self.db.flush()

            # Send via Evolution API
            evolution_response = await self.evolution_client.send_text_message(
                phone_number=patient.phone,
                message=content,
            )

            # Update message with Evolution API response
            if evolution_response and evolution_response.get("key", {}).get("id"):
                message.whatsapp_id = evolution_response["key"]["id"]
                message.status = MessageStatus.SENT
                message.sent_at = datetime.now(timezone.utc)
                logger.info(
                    f"Message {message.id} sent successfully "
                    f"(whatsapp_id: {message.whatsapp_id})"
                )
            else:
                # Sending initiated but no immediate confirmation
                message.status = MessageStatus.SENT
                message.sent_at = datetime.now(timezone.utc)
                logger.warning(f"Message {message.id} sent but no whatsapp_id received")

            # Commit transaction
            self.db.commit()

            # Cache the result
            await self._set_cache(idempotency_key, self._serialize_message(message))

            return message, False

        except Exception as e:
            # Sending failed
            logger.error(f"Failed to send message {message.id}: {e}", exc_info=True)

            # Update message status
            message.status = MessageStatus.FAILED
            message.failure_reason = str(e)
            message.retry_count += 1
            message.last_retry_at = datetime.now(timezone.utc)

            # Calculate next retry (exponential backoff)
            retry_delay = min(300, 60 * (2**message.retry_count))  # Max 5 minutes
            message.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)

            self.db.commit()

            # Don't cache failures
            raise

    async def retry_failed_message(self, message_id: uuid.UUID) -> Tuple[Message, bool]:
        """
        Retry a failed message with same idempotency key.

        Args:
            message_id: Message UUID to retry

        Returns:
            Tuple of (Message object, is_duplicate boolean)

        Raises:
            ValueError: If message not found or not in failed state
        """
        # Fetch message
        message = self.db.query(Message).filter(Message.id == message_id).first()
        if not message:
            raise ValueError(f"Message {message_id} not found")

        if message.status not in [MessageStatus.FAILED, MessageStatus.PENDING]:
            raise ValueError(
                f"Message {message_id} is not in retryable state "
                f"(status: {message.status})"
            )

        logger.info(
            f"Retrying message {message_id} (attempt {message.retry_count + 1})"
        )

        # Retry with same idempotency_key
        return await self.send_message(
            patient_id=message.patient_id,
            content=message.content,
            message_type=message.type,
            metadata=message.message_metadata,
            idempotency_key=message.idempotency_key,
            scheduled_for=message.scheduled_for,
        )

    async def cleanup_old_keys(self, days: int = 7) -> int:
        """
        Clean up old idempotency keys from Redis cache.

        This is normally handled by TTL, but this method can be used for
        manual cleanup or to free memory.

        Args:
            days: Clean up keys older than this many days

        Returns:
            Number of keys deleted
        """
        try:
            pattern = f"{self.cache_prefix}:*"
            cursor = 0
            deleted = 0

            while True:
                cursor, keys = self.redis.scan(cursor, match=pattern, count=100)

                for key in keys:
                    # Check TTL
                    ttl = self.redis.ttl(key)
                    if ttl < 0 or ttl > self.cache_ttl - (days * 86400):
                        self.redis.delete(key)
                        deleted += 1

                if cursor == 0:
                    break

            logger.info(f"Cleaned up {deleted} old idempotency keys")
            return deleted

        except RedisError as e:
            logger.error(f"Failed to cleanup idempotency keys: {e}")
            return 0


# Export public API
__all__ = [
    "IdempotentMessageSender",
    "IdempotencyError",
]
