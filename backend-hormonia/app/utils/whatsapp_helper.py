"""
WhatsApp Helper Abstraction for Clinica Oncológica V01

This module provides a comprehensive abstraction layer for WhatsApp message handling
that simplifies the MessageService and Evolution API integration while providing
advanced features like retry logic, queueing, rate limiting, and testing support.

Features:
- Simple interface for different message types (text, images, documents, interactive)
- Retry logic with exponential backoff for failed sends
- Message queueing for batch sending
- Webhook processing and response parsing
- Message templates for common scenarios
- Rate limiting to respect WhatsApp API limits
- Delivery status tracking and reporting
- Mock mode for testing without actual API calls
- Backward compatibility with existing MessageService usage
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from uuid import uuid4
from redis.asyncio import Redis

from app.utils.whatsapp_queue import (
    Priority,
    DeliveryMode,
    QueuedMessage,
    DeliveryReport,
    RateLimiter,
    MessageQueue,
)

# Import existing models and services
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.integrations.whatsapp.services.message_service import (
        WhatsAppMessageService,
    )
    from app.integrations.whatsapp.services.evolution_client import EvolutionAPIClient

from app.integrations.whatsapp.models.message import (
    MessageRequest,
    MessageResponse,
    MessageStatus,
    MessageType,
    WebhookPayload,
)

logger = logging.getLogger(__name__)


from app.models.template import MessageTemplate
from app.database import get_scoped_session
from app.repositories.template import TemplateRepository

# ... (imports remain the same, but remove local MessageTemplate dataclass if possible or alias it)
# Actually, I need to remove the local MessageTemplate dataclass definition and use the one from app.models.template
# But wait, the local dataclass has `message_type: MessageType = MessageType.TEXT`.
# The DB model has `message_type = Column(String, default="text")`.
# I need to ensure compatibility. The DB model's message_type is a string.
# The local dataclass uses Enum.
# I should probably keep using the DB model but handle the type conversion if needed.
# Or adapt the DB model to use Enum if I can, but String is safer for DB.

# Let's modify the imports and the class.


class MockEvolutionClient:
    """Mock Evolution API client for testing."""

    def __init__(self, simulate_failures: bool = False, failure_rate: float = 0.1):
        """
        Initialize mock client.

        Args:
            simulate_failures: Whether to simulate random failures
            failure_rate: Rate of simulated failures (0.0 to 1.0)
        """
        self.simulate_failures = simulate_failures
        self.failure_rate = failure_rate
        self.sent_messages = []

    async def send_message(self, request: MessageRequest) -> MessageResponse:
        """Mock send message."""
        # Simulate processing delay
        await asyncio.sleep(0.1)

        # Simulate failures
        if self.simulate_failures and time.time() % 1 < self.failure_rate:
            raise Exception("Simulated API failure")

        message_id = str(uuid4())
        response = MessageResponse(
            id=message_id, status=MessageStatus.SENT, timestamp=datetime.utcnow()
        )

        self.sent_messages.append(
            {"request": request, "response": response, "timestamp": datetime.utcnow()}
        )

        return response


class WhatsAppHelper:
    """
    Comprehensive WhatsApp helper abstraction.

    This class provides a simplified interface for WhatsApp messaging while
    maintaining backward compatibility with the existing MessageService.
    """

    def __init__(
        self,
        message_service: Optional["WhatsAppMessageService"] = None,
        evolution_client: Optional["EvolutionAPIClient"] = None,
        redis_client: Optional[Redis] = None,
        mock_mode: bool = False,
        rate_limit_requests: int = 50,
        rate_limit_window: int = 60,
    ):
        """
        Initialize WhatsApp helper.

        Args:
            message_service: Existing WhatsApp message service (for backward compatibility)
            evolution_client: Direct Evolution API client
            redis_client: Redis client for persistent queue
            mock_mode: Enable mock mode for testing
            rate_limit_requests: Max requests per time window
            rate_limit_window: Rate limit time window in seconds
        """
        self.message_service = message_service
        self.evolution_client = (
            evolution_client if not mock_mode else MockEvolutionClient()
        )
        self.mock_mode = mock_mode

        # Initialize components
        self.queue = MessageQueue(redis_client)
        self.rate_limiter = RateLimiter(rate_limit_requests, rate_limit_window)
        self.delivery_reports: Dict[str, DeliveryReport] = {}
        self.templates: Dict[str, MessageTemplate] = {}
        self.webhook_handlers: Dict[str, Callable] = {}
        self.last_template_refresh = datetime.min

        # Load templates from DB
        self._load_templates()

        # Start queue processor
        self._queue_processor_task = None
        self._start_queue_processor()

    def _load_templates(self) -> None:
        """Load message templates from database."""
        try:
            with get_scoped_session() as db:
                repo = TemplateRepository(db)
                templates = repo.list_active()
                for template in templates:
                    self.templates[template.name] = template
            self.last_template_refresh = datetime.utcnow()
            logger.info(f"Loaded {len(self.templates)} templates from database")
        except Exception as e:
            logger.error(f"Error loading templates from database: {e}")
            # If DB fails, we might want to fallback to hardcoded defaults or just fail
            # For now, we'll log error and proceed (templates dict might be empty)

    def _start_queue_processor(self) -> None:
        """Start the queue processor task."""
        if not self._queue_processor_task or self._queue_processor_task.done():
            self._queue_processor_task = asyncio.create_task(self._process_queue())

    async def _process_queue(self) -> None:
        """Process messages from the queue."""
        while True:
            try:
                message = await self.queue.dequeue()
                if message:
                    # Check if message is scheduled for future
                    if (
                        message.scheduled_at
                        and message.scheduled_at > datetime.utcnow()
                    ):
                        # Re-queue for later processing
                        await self.queue.enqueue(message)
                        await asyncio.sleep(1)
                        continue

                    await self._process_queued_message(message)
                else:
                    # No messages in queue, wait a bit
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error processing queue: {e}")
                await asyncio.sleep(5)

    async def _process_queued_message(self, message: QueuedMessage) -> None:
        """Process a single queued message."""
        try:
            # Apply rate limiting
            await self.rate_limiter.acquire()

            # Send message
            if self.message_service:
                response = await self.message_service.send_message(message.request)
            elif self.evolution_client:
                response = await self.evolution_client.send_message(message.request)
            else:
                raise ValueError("No message service or evolution client configured")

            # Update delivery report
            self._update_delivery_report(message.id, MessageStatus.SENT, response)

            # Execute callback if provided
            if message.callback:
                try:
                    await message.callback(message, response)
                except Exception as e:
                    logger.error(
                        f"Error executing callback for message {message.id}: {e}"
                    )

        except Exception as e:
            logger.error(f"Failed to send message {message.id}: {e}")
            await self._handle_message_failure(message, str(e))

    async def _handle_message_failure(self, message: QueuedMessage, error: str) -> None:
        """Handle message sending failure with retry logic."""
        message.retry_count += 1

        if message.retry_count <= message.max_retries:
            # Calculate exponential backoff delay
            delay = min(300, 2**message.retry_count)  # Max 5 minutes
            message.scheduled_at = datetime.utcnow() + timedelta(seconds=delay)

            logger.info(
                f"Retrying message {message.id} in {delay} seconds (attempt {message.retry_count}/{message.max_retries})"
            )
            await self.queue.enqueue(message)
        else:
            logger.error(
                f"Message {message.id} failed permanently after {message.retry_count} attempts"
            )
            self._update_delivery_report(message.id, MessageStatus.FAILED, None, error)

    def _update_delivery_report(
        self,
        message_id: str,
        status: MessageStatus,
        response: Optional[MessageResponse],
        error: Optional[str] = None,
    ) -> None:
        """Update delivery report for a message."""
        if message_id not in self.delivery_reports:
            self.delivery_reports[message_id] = DeliveryReport(
                message_id=message_id, status=status
            )

        report = self.delivery_reports[message_id]
        report.status = status

        if status == MessageStatus.SENT and response:
            report.sent_at = response.timestamp
        elif status == MessageStatus.DELIVERED:
            report.delivered_at = datetime.utcnow()
        elif status == MessageStatus.READ:
            report.read_at = datetime.utcnow()
        elif status == MessageStatus.FAILED:
            report.failed_at = datetime.utcnow()
            report.error_message = error

    # Public API Methods

    async def send_text(
        self,
        to: str,
        message: str,
        priority: Priority = Priority.NORMAL,
        delivery_mode: DeliveryMode = DeliveryMode.IMMEDIATE,
        scheduled_at: Optional[datetime] = None,
        callback: Optional[Callable] = None,
    ) -> str:
        """
        Send a text message.

        Args:
            to: Recipient phone number
            message: Text message content
            priority: Message priority
            delivery_mode: How to deliver the message
            scheduled_at: When to send the message (for scheduled delivery)
            callback: Optional callback function for delivery status

        Returns:
            Message ID
        """
        request = MessageRequest(to=to, message_type=MessageType.TEXT, content=message)

        return await self._send_message(
            request, priority, delivery_mode, scheduled_at, callback
        )

    async def send_image(
        self,
        to: str,
        image_url: str,
        caption: Optional[str] = None,
        priority: Priority = Priority.NORMAL,
        delivery_mode: DeliveryMode = DeliveryMode.IMMEDIATE,
        scheduled_at: Optional[datetime] = None,
        callback: Optional[Callable] = None,
    ) -> str:
        """Send an image message."""
        request = MessageRequest(
            to=to, message_type=MessageType.IMAGE, media_url=image_url, content=caption
        )

        return await self._send_message(
            request, priority, delivery_mode, scheduled_at, callback
        )

    async def send_document(
        self,
        to: str,
        document_url: str,
        filename: Optional[str] = None,
        priority: Priority = Priority.NORMAL,
        delivery_mode: DeliveryMode = DeliveryMode.IMMEDIATE,
        scheduled_at: Optional[datetime] = None,
        callback: Optional[Callable] = None,
    ) -> str:
        """Send a document message."""
        request = MessageRequest(
            to=to,
            message_type=MessageType.DOCUMENT,
            media_url=document_url,
            content=filename,
        )

        return await self._send_message(
            request, priority, delivery_mode, scheduled_at, callback
        )

    def _serialize_template(self, template: MessageTemplate) -> str:
        """Serialize template to JSON string."""
        data = {
            "name": template.name,
            "content": template.content,
            "variables": template.variables,
            "message_type": template.message_type,
            "media_url": template.media_url,
            "is_active": template.is_active,
        }
        return json.dumps(data)

    def _deserialize_template(self, data: str) -> MessageTemplate:
        """Deserialize template from JSON string."""
        template_dict = json.loads(data)
        return MessageTemplate(**template_dict)

    async def _get_cached_template(self, name: str) -> Optional[MessageTemplate]:
        """Get template from Redis cache."""
        if not self.queue.redis_client:
            return None

        try:
            key = f"whatsapp:template:{name}"
            data = await self.queue.redis_client.get(key)
            if data:
                return self._deserialize_template(data)
        except Exception as e:
            logger.warning(f"Error fetching template {name} from cache: {e}")

        return None

    async def _cache_template(self, template: MessageTemplate, ttl: int = 3600) -> None:
        """Cache template in Redis."""
        if not self.queue.redis_client:
            return

        try:
            key = f"whatsapp:template:{template.name}"
            data = self._serialize_template(template)
            await self.queue.redis_client.setex(key, ttl, data)
        except Exception as e:
            logger.warning(f"Error caching template {template.name}: {e}")

    async def refresh_template_cache(self) -> None:
        """Force refresh of all templates from DB to memory and Redis."""
        try:
            with get_scoped_session() as db:
                repo = TemplateRepository(db)
                templates = repo.list_active()

                # Update memory cache
                self.templates.clear()
                for template in templates:
                    self.templates[template.name] = template
                    # Update Redis cache
                    await self._cache_template(template)

            self.last_template_refresh = datetime.utcnow()
            logger.info(f"Refreshed {len(self.templates)} templates from database")
        except Exception as e:
            logger.error(f"Error refreshing template cache: {e}")

    async def send_template(
        self,
        to: str,
        template_name: str,
        variables: Optional[Dict[str, str]] = None,
        priority: Priority = Priority.NORMAL,
        delivery_mode: DeliveryMode = DeliveryMode.IMMEDIATE,
        scheduled_at: Optional[datetime] = None,
        callback: Optional[Callable] = None,
    ) -> str:
        """
        Send a message using a predefined template.

        Args:
            to: Recipient phone number
            template_name: Name of the template to use
            variables: Variables to substitute in the template
            priority: Message priority
            delivery_mode: How to deliver the message
            scheduled_at: When to send the message
            callback: Optional callback function

        Returns:
            Message ID
        """
        # L1 Cache: Memory
        template = self.templates.get(template_name)

        # L2 Cache: Redis (if missing from memory)
        if not template:
            template = await self._get_cached_template(template_name)
            if template:
                # Populate L1 from L2
                self.templates[template_name] = template

        # L3: Database (if missing from Redis)
        if not template:
            try:
                with get_scoped_session() as db:
                    repo = TemplateRepository(db)
                    template = repo.get_by_name(template_name)
                    if template:
                        # Populate L1 and L2
                        self.templates[template_name] = template
                        await self._cache_template(template)
            except Exception as e:
                logger.error(f"Error fetching template {template_name} from DB: {e}")

        if not template:
            raise ValueError(f"Template '{template_name}' not found")

        content = template.format(**(variables or {}))

        request = MessageRequest(
            to=to,
            message_type=template.message_type,
            content=content,
            media_url=template.media_url,
        )

        return await self._send_message(
            request, priority, delivery_mode, scheduled_at, callback
        )

    async def _send_message(
        self,
        request: MessageRequest,
        priority: Priority,
        delivery_mode: DeliveryMode,
        scheduled_at: Optional[datetime],
        callback: Optional[Callable],
    ) -> str:
        """Internal method to send a message."""
        message_id = str(uuid4())

        if delivery_mode == DeliveryMode.IMMEDIATE and not scheduled_at:
            try:
                # Send immediately
                await self.rate_limiter.acquire()

                if self.message_service:
                    response = await self.message_service.send_message(request)
                elif self.evolution_client:
                    response = await self.evolution_client.send_message(request)
                else:
                    raise ValueError(
                        "No message service or evolution client configured"
                    )

                self._update_delivery_report(message_id, MessageStatus.SENT, response)

                if callback:
                    try:
                        await callback(message_id, response)
                    except Exception as e:
                        logger.error(
                            f"Error executing callback for message {message_id}: {e}"
                        )

                return message_id

            except Exception as e:
                logger.error(f"Failed to send immediate message: {e}")
                # Fall back to queued delivery for retry
                delivery_mode = DeliveryMode.QUEUED

        if delivery_mode in [DeliveryMode.QUEUED, DeliveryMode.SCHEDULED]:
            # Queue message for processing
            queued_message = QueuedMessage(
                id=message_id,
                request=request,
                priority=priority,
                scheduled_at=scheduled_at,
                callback=callback,
            )

            await self.queue.enqueue(queued_message)
            self._update_delivery_report(message_id, MessageStatus.PENDING, None)

            return message_id

        raise ValueError(f"Unsupported delivery mode: {delivery_mode}")

    async def send_batch(
        self,
        messages: List[Dict[str, Any]],
        priority: Priority = Priority.NORMAL,
        batch_size: int = 10,
        delay_between_batches: float = 1.0,
    ) -> List[str]:
        """
        Send multiple messages in batches.

        Args:
            messages: List of message dictionaries
            priority: Priority for all messages
            batch_size: Number of messages per batch
            delay_between_batches: Delay between batches in seconds

        Returns:
            List of message IDs
        """
        message_ids = []

        for i in range(0, len(messages), batch_size):
            batch = messages[i : i + batch_size]
            batch_ids = []

            for msg in batch:
                try:
                    if msg.get("template_name"):
                        message_id = await self.send_template(
                            to=msg["to"],
                            template_name=msg["template_name"],
                            variables=msg.get("variables"),
                            priority=priority,
                            delivery_mode=DeliveryMode.QUEUED,
                        )
                    else:
                        message_id = await self.send_text(
                            to=msg["to"],
                            message=msg["message"],
                            priority=priority,
                            delivery_mode=DeliveryMode.QUEUED,
                        )
                    batch_ids.append(message_id)
                except Exception as e:
                    logger.error(f"Failed to queue batch message: {e}")

            message_ids.extend(batch_ids)

            # Delay between batches
            if i + batch_size < len(messages):
                await asyncio.sleep(delay_between_batches)

        return message_ids

    def add_template(self, template: MessageTemplate) -> None:
        """Add a custom message template."""
        self.templates[template.name] = template
        # Also cache it
        # Note: This is a sync method, so we can't await _cache_template here easily
        # without an event loop. For now, just updating memory is fine.

    def remove_template(self, template_name: str) -> None:
        """Remove a message template."""
        if template_name in self.templates:
            del self.templates[template_name]
        # Ideally we should also remove from Redis, but again, sync method.

    def get_template(self, template_name: str) -> Optional[MessageTemplate]:
        """Get a message template by name."""
        return self.templates.get(template_name)

    def list_templates(self) -> List[str]:
        """List all available template names."""
        return list(self.templates.keys())

    def add_webhook_handler(self, event_type: str, handler: Callable) -> None:
        """Add a webhook event handler."""
        self.webhook_handlers[event_type] = handler

    async def process_webhook(self, payload: WebhookPayload) -> None:
        """Process incoming webhook payload."""
        try:
            # Update delivery reports based on webhook
            if hasattr(payload, "message_id") and hasattr(payload, "status"):
                if payload.message_id in self.delivery_reports:
                    self._update_delivery_report(
                        payload.message_id, payload.status, None
                    )

            # Call registered handlers
            event_type = getattr(payload, "event_type", "unknown")
            if event_type in self.webhook_handlers:
                await self.webhook_handlers[event_type](payload)

        except Exception as e:
            logger.error(f"Error processing webhook: {e}")

    def get_delivery_report(self, message_id: str) -> Optional[DeliveryReport]:
        """Get delivery report for a message."""
        return self.delivery_reports.get(message_id)

    def get_delivery_reports(
        self, status: Optional[MessageStatus] = None
    ) -> List[DeliveryReport]:
        """Get delivery reports, optionally filtered by status."""
        reports = list(self.delivery_reports.values())
        if status:
            reports = [r for r in reports if r.status == status]
        return reports

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        stats = {}
        for priority in Priority:
            stats[priority.name] = await self.queue.size(priority)
        stats["total"] = await self.queue.size()
        return stats

    def get_sent_messages(self) -> List[Dict[str, Any]]:
        """Get sent messages (only available in mock mode)."""
        if self.mock_mode and isinstance(self.evolution_client, MockEvolutionClient):
            return self.evolution_client.sent_messages
        return []

    async def close(self) -> None:
        """Clean up resources."""
        if self._queue_processor_task and not self._queue_processor_task.done():
            self._queue_processor_task.cancel()
            try:
                await self._queue_processor_task
            except asyncio.CancelledError:
                pass


# Factory function for easy initialization
def create_whatsapp_helper(
    message_service: Optional["WhatsAppMessageService"] = None,
    evolution_client: Optional["EvolutionAPIClient"] = None,
    redis_client: Optional[Redis] = None,
    mock_mode: bool = False,
    **kwargs,
) -> WhatsAppHelper:
    """
    Factory function to create a WhatsApp helper instance.

    Args:
        message_service: Existing message service
        evolution_client: Evolution API client
        redis_client: Redis client for queue persistence
        mock_mode: Enable mock mode for testing
        **kwargs: Additional configuration options

    Returns:
        Configured WhatsAppHelper instance
    """
    return WhatsAppHelper(
        message_service=message_service,
        evolution_client=evolution_client,
        redis_client=redis_client,
        mock_mode=mock_mode,
        **kwargs,
    )
