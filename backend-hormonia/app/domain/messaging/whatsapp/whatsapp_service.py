"""
WhatsApp Service - Consolidated WhatsApp Integration (QW-022).

This module consolidates WhatsApp-related services:
- WhatsApp message sending
- Idempotent message delivery
- Queue-based messaging
- Retry and backoff policies

Consolidation: 5 files → 1 file

Legacy Files:
    - app/services/message_sender.py (MessageSender - DEPRECATED)
    - app/services/idempotent_message_sender.py (IdempotentMessageSender)
    - app/services/unified_whatsapp_service.py (UnifiedWhatsAppService)
    - app/integrations/whatsapp/services/message_service.py (Queue service)
    - app/services/monthly_quiz_message_integration.py (Partial)
"""

import logging
import hashlib
import uuid
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timedelta
from enum import Enum

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.message import Message, MessageStatus, MessageType, MessageDirection
from app.models.patient import Patient
from app.integrations.evolution import get_evolution_client, EvolutionAPIError
from app.repositories.message import MessageRepository
from app.repositories.patient import PatientRepository
from app.services.websocket_events import websocket_events
from app.schemas.websocket import WebSocketEventType
from app.exceptions import ExternalServiceError, NotFoundError
from app.utils.db_retry import with_db_retry


logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Config
# ============================================================================


class MessagingMode(str, Enum):
    """Messaging mode for WhatsApp service."""

    QUEUE = "queue"  # Queue-based with retry/backoff
    DIRECT = "direct"  # Direct sending without queue
    LEGACY = "legacy"  # Legacy mode (deprecated)


class WhatsAppServiceError(Exception):
    """Base exception for WhatsApp service errors."""

    pass


class MessageDeliveryError(WhatsAppServiceError):
    """Exception for message delivery failures."""

    pass


class IdempotencyError(WhatsAppServiceError):
    """Exception for idempotency errors."""

    pass


# ============================================================================
# WhatsAppService - Main Service
# ============================================================================


class WhatsAppService:
    """
    Unified WhatsApp service for message sending.

    Features:
    - Multiple messaging modes (queue, direct, legacy)
    - Retry and backoff policies
    - WebSocket event notifications
    - Flow integration callbacks

    Consolidates:
        - MessageSender (deprecated)
        - UnifiedWhatsAppService
        - WhatsAppMessageService (queue)
    """

    def __init__(
        self,
        db: Session,
        messaging_mode: MessagingMode = MessagingMode.QUEUE,
        redis: Optional[Redis] = None,
    ):
        """
        Initialize WhatsAppService.

        Args:
            db: Database session
            messaging_mode: Messaging mode (default: QUEUE)
            redis: Optional Redis client for caching
        """
        self.db = db
        self.messaging_mode = messaging_mode
        self.redis = redis

        # Initialize repositories
        self.message_repo = MessageRepository(db)
        self.patient_repo = PatientRepository(db)

        # Initialize Evolution API client
        self.evolution_client = get_evolution_client()

        # Callback registry for flow messages
        self.flow_message_callbacks: Dict[str, Callable] = {}

        # Retry policies
        self.retry_policies = {
            "default": {
                "max_retries": 3,
                "backoff_factor": 2,
                "base_delay": 300,  # 5 minutes
            },
            "flow_message": {
                "max_retries": 5,
                "backoff_factor": 1.5,
                "base_delay": 180,  # 3 minutes
            },
            "quiz_message": {"max_retries": 3, "backoff_factor": 2, "base_delay": 300},
        }

        logger.info(f"WhatsAppService initialized with mode={messaging_mode.value}")

    async def send_message(
        self,
        message: Message,
        retry_count: int = 0,
        callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Send a WhatsApp message.

        Args:
            message: Message object to send
            retry_count: Current retry attempt
            callback: Optional callback after sending

        Returns:
            Send result dictionary

        Raises:
            MessageDeliveryError: If delivery fails
        """
        try:
            # Get patient
            patient = self.patient_repo.get_by_id(message.patient_id)
            if not patient:
                raise NotFoundError(f"Patient {message.patient_id} not found")

            # Get patient phone number
            phone_number = self._get_patient_phone(patient)

            # Send via Evolution API
            result = await self._send_via_evolution(
                phone_number=phone_number,
                content=message.content,
                message_type=message.type,
            )

            # Update message status
            message.status = MessageStatus.SENT
            message.whatsapp_id = result.get("key", {}).get("id")
            message.sent_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(message)

            # Broadcast WebSocket event
            self._broadcast_message_sent(message)

            # Execute callback if provided
            if callback:
                await callback(message, result)

            logger.info(
                f"Message {message.id} sent successfully to patient {patient.id}"
            )

            return {
                "success": True,
                "message_id": str(message.id),
                "whatsapp_id": message.whatsapp_id,
            }

        except EvolutionAPIError as e:
            logger.error(f"Evolution API error sending message {message.id}: {e}")

            # Handle retry
            if retry_count < self._get_max_retries(message):
                await self._schedule_retry(message, retry_count + 1)
                return {
                    "success": False,
                    "retry_scheduled": True,
                    "retry_count": retry_count + 1,
                }
            else:
                # Mark as failed
                message.status = MessageStatus.FAILED
                message.message_metadata["error"] = str(e)
                self.db.commit()

                raise MessageDeliveryError(f"Failed to send message after retries: {e}")

        except Exception as e:
            logger.error(
                f"Unexpected error sending message {message.id}: {e}", exc_info=True
            )
            message.status = MessageStatus.FAILED
            message.message_metadata["error"] = str(e)
            self.db.commit()

            raise MessageDeliveryError(f"Failed to send message: {e}")

    async def send_message_to_patient(
        self,
        patient_id: uuid.UUID,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """
        Send a message to a patient (convenience method).

        Args:
            patient_id: Patient UUID
            content: Message content
            message_type: Type of message
            metadata: Optional metadata

        Returns:
            Sent Message object
        """
        # Create message
        message = Message(
            patient_id=patient_id,
            direction=MessageDirection.OUTBOUND,
            type=message_type,
            content=content,
            message_metadata=metadata or {},
            status=MessageStatus.PENDING,
        )

        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)

        # Send immediately or queue
        if self.messaging_mode == MessagingMode.DIRECT:
            await self.send_message(message)
        else:
            # Queue for async processing
            self._queue_message(message)

        return message

    def register_flow_callback(self, flow_type: str, callback: Callable) -> None:
        """
        Register callback for flow message delivery.

        Args:
            flow_type: Flow type identifier
            callback: Callback function
        """
        self.flow_message_callbacks[flow_type] = callback
        logger.info(f"Registered flow callback for type: {flow_type}")

    def _get_patient_phone(self, patient: Patient) -> str:
        """
        Get patient phone number.

        Args:
            patient: Patient object

        Returns:
            Phone number string

        Raises:
            ValueError: If phone number not found
        """
        phone = patient.phone_number
        if not phone:
            raise ValueError(f"Patient {patient.id} has no phone number")

        # Format for WhatsApp (remove non-digits, ensure country code)
        phone = "".join(filter(str.isdigit, phone))
        if not phone.startswith("55"):  # Brazil
            phone = "55" + phone

        return phone

    async def _send_via_evolution(
        self, phone_number: str, content: str, message_type: MessageType
    ) -> Dict[str, Any]:
        """
        Send message via Evolution API.

        Args:
            phone_number: Recipient phone number
            content: Message content
            message_type: Type of message

        Returns:
            Evolution API response
        """
        if message_type == MessageType.TEXT:
            return await self.evolution_client.send_text(phone_number, content)
        elif message_type == MessageType.IMAGE:
            # Extract image URL from content or metadata
            return await self.evolution_client.send_image(phone_number, content)
        else:
            # Default to text
            return await self.evolution_client.send_text(phone_number, content)

    def _get_max_retries(self, message: Message) -> int:
        """
        Get max retries for a message based on type.

        Args:
            message: Message object

        Returns:
            Max retry count
        """
        if message.type in [MessageType.FLOW_MESSAGE, MessageType.FLOW_QUESTION]:
            policy = self.retry_policies.get("flow_message")
        elif message.type in [MessageType.QUIZ_QUESTION, MessageType.QUIZ_START]:
            policy = self.retry_policies.get("quiz_message")
        else:
            policy = self.retry_policies.get("default")

        return policy["max_retries"]

    async def _schedule_retry(self, message: Message, retry_count: int) -> None:
        """
        Schedule message retry.

        Args:
            message: Message to retry
            retry_count: Current retry count
        """
        policy = self.retry_policies.get("default")
        delay = policy["base_delay"] * (policy["backoff_factor"] ** (retry_count - 1))

        scheduled_for = datetime.utcnow() + timedelta(seconds=delay)

        message.status = MessageStatus.PENDING
        message.scheduled_for = scheduled_for
        message.message_metadata["retry_count"] = retry_count

        self.db.commit()

        logger.info(
            f"Scheduled retry {retry_count} for message {message.id} at {scheduled_for}"
        )

    def _queue_message(self, message: Message) -> None:
        """
        Queue message for async processing.

        Args:
            message: Message to queue
        """
        # In queue mode, messages are picked up by background worker
        # For now, just log (actual queue implementation would use Celery/RQ)
        logger.info(f"Message {message.id} queued for delivery")

    def _broadcast_message_sent(self, message: Message) -> None:
        """
        Broadcast message sent event via WebSocket.

        Args:
            message: Sent message
        """
        try:
            websocket_events.broadcast_event(
                event_type=WebSocketEventType.MESSAGE_SENT,
                data={
                    "message_id": str(message.id),
                    "patient_id": str(message.patient_id),
                    "content": message.content,
                    "sent_at": message.sent_at.isoformat() if message.sent_at else None,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast message sent event: {e}")


# ============================================================================
# IdempotentMessageSender - Idempotent Delivery
# ============================================================================


class IdempotentMessageSender:
    """
    Service for sending messages with idempotency guarantees.

    Idempotency is achieved through:
    1. Unique idempotency_key per message intent
    2. Redis cache (fast path) - TTL 24 hours
    3. Database unique constraint (persistent)
    4. Automatic key generation if not provided

    Consolidates: app/services/idempotent_message_sender.py
    """

    def __init__(
        self,
        db: Session,
        redis: Optional[Redis] = None,
        cache_ttl: int = 86400,  # 24 hours
        enable_cache: bool = True,
    ):
        """
        Initialize idempotent message sender.

        Args:
            db: Database session
            redis: Optional Redis client
            cache_ttl: Cache TTL in seconds
            enable_cache: Whether to use Redis cache
        """
        self.db = db
        self.redis = redis
        self.cache_ttl = cache_ttl
        self.enable_cache = enable_cache and redis is not None

        # Initialize WhatsApp service
        self.whatsapp_service = WhatsAppService(db, redis=redis)

        logger.info(
            f"IdempotentMessageSender initialized (cache={'enabled' if self.enable_cache else 'disabled'})"
        )

    def generate_idempotency_key(
        self,
        patient_id: uuid.UUID,
        content: str,
        message_type: MessageType = MessageType.TEXT,
    ) -> str:
        """
        Generate idempotency key for a message.

        Args:
            patient_id: Patient UUID
            content: Message content
            message_type: Type of message

        Returns:
            Idempotency key (hash)
        """
        # Create deterministic key from message intent
        key_data = f"{patient_id}:{content}:{message_type.value}"
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:32]

        return f"msg_idempotency:{key_hash}"

    async def send_message(
        self,
        patient_id: uuid.UUID,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a message with idempotency guarantee.

        Args:
            patient_id: Patient UUID
            content: Message content
            message_type: Type of message
            metadata: Optional metadata
            idempotency_key: Optional custom idempotency key

        Returns:
            Send result dictionary with 'message_id' and 'was_duplicate'

        Raises:
            IdempotencyError: If idempotency check fails
        """
        # Generate or use provided key
        if not idempotency_key:
            idempotency_key = self.generate_idempotency_key(
                patient_id, content, message_type
            )

        # Check cache first (fast path)
        if self.enable_cache:
            cached_result = self._check_cache(idempotency_key)
            if cached_result:
                logger.info(f"Message already sent (cache hit): {idempotency_key}")
                return {
                    "message_id": cached_result,
                    "was_duplicate": True,
                    "source": "cache",
                }

        # Check database
        existing_message = self._check_database(idempotency_key)
        if existing_message:
            logger.info(f"Message already sent (db hit): {idempotency_key}")

            # Populate cache for future fast path
            if self.enable_cache:
                self._store_in_cache(idempotency_key, str(existing_message.id))

            return {
                "message_id": str(existing_message.id),
                "was_duplicate": True,
                "source": "database",
            }

        # Send new message
        try:
            # Add idempotency key to metadata
            if metadata is None:
                metadata = {}
            metadata["idempotency_key"] = idempotency_key

            message = await self.whatsapp_service.send_message_to_patient(
                patient_id=patient_id,
                content=content,
                message_type=message_type,
                metadata=metadata,
            )

            # Store in cache
            if self.enable_cache:
                self._store_in_cache(idempotency_key, str(message.id))

            return {
                "message_id": str(message.id),
                "was_duplicate": False,
                "source": "new",
            }

        except IntegrityError as e:
            # Race condition: another process sent same message
            self.db.rollback()

            existing_message = self._check_database(idempotency_key)
            if existing_message:
                logger.warning(
                    f"Race condition detected for {idempotency_key}, using existing message"
                )
                return {
                    "message_id": str(existing_message.id),
                    "was_duplicate": True,
                    "source": "race_condition",
                }
            else:
                raise IdempotencyError(f"Idempotency check failed: {e}")

    def _check_cache(self, idempotency_key: str) -> Optional[str]:
        """
        Check Redis cache for idempotency key.

        Args:
            idempotency_key: Idempotency key

        Returns:
            Message ID if found, None otherwise
        """
        if not self.redis:
            return None

        try:
            result = self.redis.get(idempotency_key)
            return result.decode() if result else None
        except RedisError as e:
            logger.warning(f"Redis error checking cache: {e}")
            return None

    def _check_database(self, idempotency_key: str) -> Optional[Message]:
        """
        Check database for existing message with idempotency key.

        Args:
            idempotency_key: Idempotency key

        Returns:
            Message if found, None otherwise
        """
        try:
            result = (
                self.db.query(Message)
                .filter(
                    Message.message_metadata["idempotency_key"].astext
                    == idempotency_key
                )
                .first()
            )

            return result
        except Exception as e:
            logger.error(f"Database error checking idempotency: {e}")
            return None

    def _store_in_cache(self, idempotency_key: str, message_id: str) -> None:
        """
        Store idempotency key in Redis cache.

        Args:
            idempotency_key: Idempotency key
            message_id: Message ID to store
        """
        if not self.redis:
            return

        try:
            self.redis.setex(idempotency_key, self.cache_ttl, message_id)
        except RedisError as e:
            logger.warning(f"Redis error storing cache: {e}")


# ============================================================================
# WhatsAppQueueService - Queue-based Messaging (Stub)
# ============================================================================


class WhatsAppQueueService:
    """
    Queue-based WhatsApp messaging service.

    This is a stub that delegates to WhatsAppService with QUEUE mode.
    Actual queue implementation would use Celery/RQ.

    Consolidates: app/integrations/whatsapp/services/message_service.py
    """

    def __init__(self, db: Session, redis: Optional[Redis] = None):
        """
        Initialize queue service.

        Args:
            db: Database session
            redis: Optional Redis client
        """
        self.service = WhatsAppService(
            db=db, messaging_mode=MessagingMode.QUEUE, redis=redis
        )

    async def queue_message(self, message: Message) -> None:
        """
        Queue message for delivery.

        Args:
            message: Message to queue
        """
        # Delegate to WhatsAppService
        await self.service.send_message(message)


# ============================================================================
# Factory Functions
# ============================================================================


def get_whatsapp_service(
    db: Session,
    messaging_mode: MessagingMode = MessagingMode.QUEUE,
    redis: Optional[Redis] = None,
) -> WhatsAppService:
    """
    Get WhatsAppService instance.

    Args:
        db: Database session
        messaging_mode: Messaging mode
        redis: Optional Redis client

    Returns:
        WhatsAppService instance
    """
    return WhatsAppService(db, messaging_mode, redis)


def get_idempotent_sender(
    db: Session, redis: Optional[Redis] = None
) -> IdempotentMessageSender:
    """
    Get IdempotentMessageSender instance.

    Args:
        db: Database session
        redis: Optional Redis client

    Returns:
        IdempotentMessageSender instance
    """
    return IdempotentMessageSender(db, redis)
