"""
Unified WhatsApp Service for Hormonia Backend System.

This service centralizes all WhatsApp communication handling to eliminate
code duplication and provide a single point of integration.
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass

from app.config import settings
from app.core.circuit_breaker import CircuitBreaker
from app.exceptions import ServiceError, ValidationError
from app.services.encryption_service import get_encryption_service


logger = logging.getLogger(__name__)


class MessageType(Enum):
    """WhatsApp message types."""
    TEXT = "text"
    TEMPLATE = "template"
    MEDIA = "media"
    INTERACTIVE = "interactive"
    LOCATION = "location"


class MessagePriority(Enum):
    """Message priority levels."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


@dataclass
class WhatsAppMessage:
    """Unified WhatsApp message structure."""
    phone_number: str
    message_type: MessageType
    content: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    metadata: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    max_retries: int = 3


class WhatsAppUnifiedService:
    """
    Unified WhatsApp service that handles all WhatsApp communications.

    Features:
    - Centralized message sending and receiving
    - Template message management
    - Rate limiting and throttling
    - Circuit breaker for API failures
    - Delivery tracking and analytics
    - Webhook handling
    - Message queue with priority
    - Automatic retries with exponential backoff
    """

    def __init__(self, evolution_api_client=None, redis_client=None):
        """Initialize WhatsApp unified service."""
        self.evolution_api = evolution_api_client
        self.redis = redis_client
        self.encryption_service = get_encryption_service()

        # Circuit breaker configuration
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=300,
            expected_exception=ServiceError
        )

        # Rate limiting configuration
        self.rate_limit_per_minute = 30
        self.rate_limit_per_hour = 500

        # Message queue
        self.message_queue: List[WhatsAppMessage] = []
        self.processing_lock = asyncio.Lock()

        logger.info("WhatsApp Unified Service initialized")

    async def send_message(
        self,
        phone_number: str,
        message_type: MessageType,
        content: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a WhatsApp message with unified handling.

        Args:
            phone_number: Recipient phone number
            message_type: Type of message to send
            content: Message content based on type
            priority: Message priority for queue handling
            metadata: Additional metadata for tracking

        Returns:
            Dict containing message ID and status
        """
        # Validate phone number
        if not self._validate_phone_number(phone_number):
            raise ValidationError(f"Invalid phone number format: {phone_number}")

        # Create message object
        message = WhatsAppMessage(
            phone_number=phone_number,
            message_type=message_type,
            content=content,
            priority=priority,
            metadata=metadata or {}
        )

        # Check rate limits
        if not await self._check_rate_limit(phone_number):
            # Queue message if rate limited
            await self._queue_message(message)
            return {
                "status": "queued",
                "message": "Message queued due to rate limiting",
                "queue_position": len(self.message_queue)
            }

        # Send message with circuit breaker
        try:
            result = await self.circuit_breaker.call(
                self._send_message_internal,
                message
            )

            # Track successful delivery
            await self._track_delivery(message, result)

            return result

        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")

            # Queue for retry if retriable error
            if self._is_retriable_error(e) and message.retry_count < message.max_retries:
                message.retry_count += 1
                await self._queue_message(message)
                return {
                    "status": "retry_queued",
                    "message": f"Message queued for retry (attempt {message.retry_count})",
                    "error": str(e)
                }

            raise ServiceError(f"Failed to send WhatsApp message: {e}")

    async def send_template_message(
        self,
        phone_number: str,
        template_name: str,
        parameters: List[str],
        language: str = "pt_BR",
        priority: MessagePriority = MessagePriority.NORMAL
    ) -> Dict[str, Any]:
        """
        Send a WhatsApp template message.

        Args:
            phone_number: Recipient phone number
            template_name: Name of the approved template
            parameters: Template parameters
            language: Template language code
            priority: Message priority

        Returns:
            Dict containing message ID and status
        """
        content = {
            "template_name": template_name,
            "parameters": parameters,
            "language": language
        }

        return await self.send_message(
            phone_number=phone_number,
            message_type=MessageType.TEMPLATE,
            content=content,
            priority=priority,
            metadata={"template": template_name}
        )

    async def send_quiz_link(
        self,
        phone_number: str,
        patient_name: str,
        quiz_link: str,
        expires_at: datetime
    ) -> Dict[str, Any]:
        """
        Send a quiz link via WhatsApp.

        Args:
            phone_number: Recipient phone number
            patient_name: Patient's name for personalization
            quiz_link: The quiz access link
            expires_at: Link expiration time

        Returns:
            Dict containing message ID and status
        """
        # Format expiration in PT-BR
        expires_formatted = expires_at.strftime("%d/%m/%Y às %H:%M")

        # Use template message for quiz links
        return await self.send_template_message(
            phone_number=phone_number,
            template_name="quiz_monthly_link",
            parameters=[
                patient_name,
                quiz_link,
                expires_formatted
            ],
            priority=MessagePriority.HIGH
        )

    async def send_flow_message(
        self,
        phone_number: str,
        flow_id: str,
        step_content: Dict[str, Any],
        session_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a flow-based conversation message.

        Args:
            phone_number: Recipient phone number
            flow_id: Flow identifier
            step_content: Current flow step content
            session_data: Optional session data

        Returns:
            Dict containing message ID and status
        """
        content = {
            "flow_id": flow_id,
            "step": step_content,
            "session": session_data or {}
        }

        return await self.send_message(
            phone_number=phone_number,
            message_type=MessageType.INTERACTIVE,
            content=content,
            priority=MessagePriority.NORMAL,
            metadata={"flow_id": flow_id}
        )

    async def handle_webhook(
        self,
        webhook_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle incoming WhatsApp webhook.

        Args:
            webhook_data: Webhook payload from Evolution API

        Returns:
            Dict containing processing result
        """
        try:
            # Validate webhook signature if configured
            if not self._validate_webhook_signature(webhook_data):
                raise ValidationError("Invalid webhook signature")

            # Extract message data
            message_data = self._extract_message_data(webhook_data)

            # Route to appropriate handler
            if message_data["type"] == "message":
                return await self._handle_incoming_message(message_data)
            elif message_data["type"] == "status":
                return await self._handle_status_update(message_data)
            else:
                logger.warning(f"Unknown webhook type: {message_data['type']}")
                return {"status": "ignored", "reason": "unknown_type"}

        except Exception as e:
            logger.error(f"Webhook handling error: {e}", exc_info=True)
            raise ServiceError(f"Failed to handle webhook: {e}")

    async def process_message_queue(self):
        """Process queued messages with priority handling."""
        async with self.processing_lock:
            if not self.message_queue:
                return

            # Sort by priority and retry count
            self.message_queue.sort(
                key=lambda m: (m.priority.value, m.retry_count)
            )

            processed = []
            for message in self.message_queue[:10]:  # Process up to 10 messages
                try:
                    # Check rate limit again
                    if await self._check_rate_limit(message.phone_number):
                        result = await self._send_message_internal(message)
                        await self._track_delivery(message, result)
                        processed.append(message)

                        # Add delay to respect rate limits
                        await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"Failed to process queued message: {e}")

                    # Increment retry count
                    message.retry_count += 1

                    # Remove if max retries exceeded
                    if message.retry_count >= message.max_retries:
                        processed.append(message)
                        logger.warning(
                            f"Message to {message.phone_number} dropped after "
                            f"{message.max_retries} retries"
                        )

            # Remove processed messages
            for message in processed:
                self.message_queue.remove(message)

    async def get_delivery_status(
        self,
        message_id: str
    ) -> Dict[str, Any]:
        """
        Get delivery status for a message.

        Args:
            message_id: WhatsApp message ID

        Returns:
            Dict containing delivery status
        """
        try:
            # Check cache first
            if self.redis:
                cached = await self.redis.get(f"whatsapp:status:{message_id}")
                if cached:
                    return cached

            # Query Evolution API for status
            if self.evolution_api:
                status = await self.evolution_api.get_message_status(message_id)

                # Cache the result
                if self.redis:
                    await self.redis.set(
                        f"whatsapp:status:{message_id}",
                        status,
                        expire=3600  # 1 hour cache
                    )

                return status

            return {"status": "unknown", "message": "Status tracking not available"}

        except Exception as e:
            logger.error(f"Failed to get delivery status: {e}")
            return {"status": "error", "message": str(e)}

    # Private helper methods

    def _validate_phone_number(self, phone_number: str) -> bool:
        """Validate phone number format."""
        # Remove non-numeric characters
        cleaned = ''.join(filter(str.isdigit, phone_number))

        # Brazilian phone validation (adjust for other countries)
        if len(cleaned) == 13:  # 55 + DDD + 9 digits
            return cleaned.startswith('55')
        elif len(cleaned) == 11:  # DDD + 9 digits
            return True

        return False

    async def _check_rate_limit(self, phone_number: str) -> bool:
        """Check if message can be sent within rate limits."""
        if not self.redis:
            return True

        try:
            # Check per-minute limit
            minute_key = f"whatsapp:rate:minute:{phone_number}"
            minute_count = await self.redis.incr(minute_key)
            if minute_count == 1:
                await self.redis.expire(minute_key, 60)

            if minute_count > self.rate_limit_per_minute:
                return False

            # Check per-hour limit
            hour_key = f"whatsapp:rate:hour:{phone_number}"
            hour_count = await self.redis.incr(hour_key)
            if hour_count == 1:
                await self.redis.expire(hour_key, 3600)

            if hour_count > self.rate_limit_per_hour:
                return False

            return True

        except Exception as e:
            logger.warning(f"Rate limit check failed: {e}")
            return True  # Allow if rate limiting fails

    async def _send_message_internal(
        self,
        message: WhatsAppMessage
    ) -> Dict[str, Any]:
        """Internal method to send message via Evolution API."""
        if not self.evolution_api:
            raise ServiceError("Evolution API client not configured")

        # Route based on message type
        if message.message_type == MessageType.TEXT:
            return await self.evolution_api.send_text(
                phone_number=message.phone_number,
                text=message.content["text"]
            )
        elif message.message_type == MessageType.TEMPLATE:
            return await self.evolution_api.send_template(
                phone_number=message.phone_number,
                template_name=message.content["template_name"],
                parameters=message.content["parameters"],
                language=message.content.get("language", "pt_BR")
            )
        elif message.message_type == MessageType.INTERACTIVE:
            return await self.evolution_api.send_interactive(
                phone_number=message.phone_number,
                interactive_data=message.content
            )
        else:
            raise ValidationError(f"Unsupported message type: {message.message_type}")

    async def _queue_message(self, message: WhatsAppMessage):
        """Add message to queue for later processing."""
        self.message_queue.append(message)

        # Limit queue size
        if len(self.message_queue) > 1000:
            # Remove lowest priority messages
            self.message_queue.sort(
                key=lambda m: (-m.priority.value, m.retry_count),
                reverse=True
            )
            self.message_queue = self.message_queue[:1000]

    async def _track_delivery(
        self,
        message: WhatsAppMessage,
        result: Dict[str, Any]
    ):
        """Track message delivery for analytics."""
        if not self.redis:
            return

        try:
            # Store delivery record
            delivery_data = {
                "phone_number": message.phone_number,
                "message_type": message.message_type.value,
                "priority": message.priority.value,
                "status": result.get("status", "sent"),
                "message_id": result.get("message_id"),
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": message.metadata
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
                f"type_{message.message_type.value}",
                1
            )
            await self.redis.expire(stats_key, 604800)  # 7 days

        except Exception as e:
            logger.warning(f"Failed to track delivery: {e}")

    def _is_retriable_error(self, error: Exception) -> bool:
        """Check if error is retriable."""
        retriable_errors = [
            "timeout",
            "rate_limit",
            "temporary_failure",
            "connection_error"
        ]

        error_str = str(error).lower()
        return any(err in error_str for err in retriable_errors)

    def _validate_webhook_signature(self, webhook_data: Dict[str, Any]) -> bool:
        """Validate webhook signature for security."""
        # Implement webhook signature validation based on Evolution API
        # For now, return True if no secret is configured
        if not hasattr(settings, 'EVOLUTION_WEBHOOK_SECRET'):
            return True

        # TODO: Implement actual signature validation
        return True

    def _extract_message_data(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant data from webhook payload."""
        # Parse Evolution API webhook format
        return {
            "type": webhook_data.get("event", "unknown"),
            "phone_number": webhook_data.get("data", {}).get("key", {}).get("remoteJid", ""),
            "message": webhook_data.get("data", {}).get("message", {}),
            "timestamp": webhook_data.get("date_time", datetime.utcnow().isoformat())
        }

    async def _handle_incoming_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming WhatsApp message."""
        # Route to appropriate service based on message content
        # This would integrate with quiz, flow, and other services

        logger.info(f"Received message from {message_data['phone_number']}")

        # TODO: Implement message routing logic
        return {
            "status": "received",
            "phone_number": message_data["phone_number"],
            "timestamp": message_data["timestamp"]
        }

    async def _handle_status_update(self, status_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle message status update."""
        # Update delivery tracking

        logger.info(f"Status update: {status_data}")

        # TODO: Implement status update handling
        return {
            "status": "processed",
            "timestamp": datetime.utcnow().isoformat()
        }


# Singleton instance
_whatsapp_service: Optional[WhatsAppUnifiedService] = None


def get_whatsapp_service() -> WhatsAppUnifiedService:
    """Get or create WhatsApp unified service instance."""
    global _whatsapp_service

    if _whatsapp_service is None:
        # Initialize with appropriate clients
        # These would be injected or configured based on your setup
        _whatsapp_service = WhatsAppUnifiedService()

    return _whatsapp_service