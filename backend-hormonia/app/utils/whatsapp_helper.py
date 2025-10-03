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
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Union, Callable, Any, Tuple
from uuid import uuid4
import backoff
from redis.asyncio import Redis

# Import existing models and services
from app.integrations.whatsapp.services.message_service import WhatsAppMessageService
from app.integrations.whatsapp.services.evolution_client import EvolutionAPIClient
from app.integrations.whatsapp.models.message import (
    MessageRequest, MessageResponse, MessageStatus, MessageType,
    WhatsAppMessage, WebhookPayload
)

logger = logging.getLogger(__name__)


class Priority(Enum):
    """Message priority levels for queue processing."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class DeliveryMode(Enum):
    """Message delivery modes."""
    IMMEDIATE = "immediate"
    QUEUED = "queued"
    SCHEDULED = "scheduled"


@dataclass
class MessageTemplate:
    """Predefined message template for common scenarios."""
    name: str
    content: str
    message_type: MessageType = MessageType.TEXT
    variables: List[str] = field(default_factory=list)
    media_url: Optional[str] = None

    def format(self, **kwargs) -> str:
        """Format template with provided variables."""
        try:
            return self.content.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing template variable: {e}")


@dataclass
class QueuedMessage:
    """Queued message with metadata."""
    id: str
    request: MessageRequest
    priority: Priority
    retry_count: int = 0
    max_retries: int = 3
    scheduled_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    callback: Optional[Callable] = None


@dataclass
class DeliveryReport:
    """Message delivery status report."""
    message_id: str
    status: MessageStatus
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0


class RateLimiter:
    """Rate limiter for WhatsApp API calls."""

    def __init__(self, max_requests: int = 50, time_window: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire rate limit permission."""
        async with self._lock:
            now = time.time()
            # Remove old requests outside the time window
            while self.requests and self.requests[0] <= now - self.time_window:
                self.requests.popleft()

            # Check if we're at the limit
            if len(self.requests) >= self.max_requests:
                # Calculate wait time
                oldest_request = self.requests[0]
                wait_time = self.time_window - (now - oldest_request)
                if wait_time > 0:
                    logger.info(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                    await asyncio.sleep(wait_time)
                    return await self.acquire()

            # Record this request
            self.requests.append(now)


class MessageQueue:
    """Advanced message queue with priority and batch processing."""

    def __init__(self, redis_client: Optional[Redis] = None):
        """Initialize message queue."""
        self.redis_client = redis_client
        self.local_queue: Dict[Priority, List[QueuedMessage]] = {
            priority: [] for priority in Priority
        }
        self._lock = asyncio.Lock()
        self._processing = False

    async def enqueue(self, message: QueuedMessage) -> None:
        """Add message to queue."""
        async with self._lock:
            if self.redis_client:
                # Use Redis for persistent queue
                queue_key = f"whatsapp_queue:{message.priority.name}"
                await self.redis_client.lpush(queue_key, message.id)
                await self.redis_client.hset(
                    f"whatsapp_message:{message.id}",
                    mapping={
                        "data": json.dumps({
                            "request": message.request.dict(),
                            "priority": message.priority.value,
                            "retry_count": message.retry_count,
                            "max_retries": message.max_retries,
                            "scheduled_at": message.scheduled_at.isoformat() if message.scheduled_at else None,
                            "created_at": message.created_at.isoformat()
                        })
                    }
                )
            else:
                # Use local queue
                self.local_queue[message.priority].append(message)

    async def dequeue(self, priority: Optional[Priority] = None) -> Optional[QueuedMessage]:
        """Get next message from queue."""
        async with self._lock:
            if self.redis_client:
                # Try Redis queue
                priorities = [priority] if priority else list(Priority)[::-1]  # High to low
                for p in priorities:
                    queue_key = f"whatsapp_queue:{p.name}"
                    message_id = await self.redis_client.rpop(queue_key)
                    if message_id:
                        data = await self.redis_client.hget(f"whatsapp_message:{message_id}", "data")
                        if data:
                            message_data = json.loads(data)
                            return QueuedMessage(
                                id=message_id,
                                request=MessageRequest(**message_data["request"]),
                                priority=Priority(message_data["priority"]),
                                retry_count=message_data["retry_count"],
                                max_retries=message_data["max_retries"],
                                scheduled_at=datetime.fromisoformat(message_data["scheduled_at"]) if message_data["scheduled_at"] else None,
                                created_at=datetime.fromisoformat(message_data["created_at"])
                            )
            else:
                # Try local queue
                priorities = [priority] if priority else list(Priority)[::-1]
                for p in priorities:
                    if self.local_queue[p]:
                        return self.local_queue[p].pop(0)

            return None

    async def size(self, priority: Optional[Priority] = None) -> int:
        """Get queue size."""
        if self.redis_client:
            if priority:
                return await self.redis_client.llen(f"whatsapp_queue:{priority.name}")
            else:
                total = 0
                for p in Priority:
                    total += await self.redis_client.llen(f"whatsapp_queue:{p.name}")
                return total
        else:
            if priority:
                return len(self.local_queue[priority])
            else:
                return sum(len(queue) for queue in self.local_queue.values())


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
            id=message_id,
            status=MessageStatus.SENT,
            timestamp=datetime.utcnow()
        )

        self.sent_messages.append({
            "request": request,
            "response": response,
            "timestamp": datetime.utcnow()
        })

        return response


class WhatsAppHelper:
    """
    Comprehensive WhatsApp helper abstraction.

    This class provides a simplified interface for WhatsApp messaging while
    maintaining backward compatibility with the existing MessageService.
    """

    def __init__(
        self,
        message_service: Optional[WhatsAppMessageService] = None,
        evolution_client: Optional[EvolutionAPIClient] = None,
        redis_client: Optional[Redis] = None,
        mock_mode: bool = False,
        rate_limit_requests: int = 50,
        rate_limit_window: int = 60
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
        self.evolution_client = evolution_client if not mock_mode else MockEvolutionClient()
        self.mock_mode = mock_mode

        # Initialize components
        self.queue = MessageQueue(redis_client)
        self.rate_limiter = RateLimiter(rate_limit_requests, rate_limit_window)
        self.delivery_reports: Dict[str, DeliveryReport] = {}
        self.templates: Dict[str, MessageTemplate] = {}
        self.webhook_handlers: Dict[str, Callable] = {}

        # Load default templates
        self._load_default_templates()

        # Start queue processor
        self._queue_processor_task = None
        self._start_queue_processor()

    def _load_default_templates(self) -> None:
        """Load default message templates for common scenarios."""
        default_templates = [
            MessageTemplate(
                name="appointment_reminder",
                content="Olá {patient_name}! Lembramos que você tem uma consulta marcada para {appointment_date} às {appointment_time} com Dr(a). {doctor_name}. Por favor, confirme sua presença.",
                variables=["patient_name", "appointment_date", "appointment_time", "doctor_name"]
            ),
            MessageTemplate(
                name="appointment_confirmation",
                content="Sua consulta foi confirmada para {appointment_date} às {appointment_time}. Endereço: {clinic_address}. Em caso de dúvidas, entre em contato conosco.",
                variables=["appointment_date", "appointment_time", "clinic_address"]
            ),
            MessageTemplate(
                name="test_results",
                content="Olá {patient_name}! Seus exames estão prontos. Por favor, entre em contato conosco para agendar uma consulta para discussão dos resultados.",
                variables=["patient_name"]
            ),
            MessageTemplate(
                name="prescription_ready",
                content="Sua receita médica está pronta para retirada. Horário de funcionamento: Segunda a Sexta das 8h às 18h.",
                variables=[]
            ),
            MessageTemplate(
                name="welcome_message",
                content="Bem-vindo(a) à Clínica Oncológica! Estamos aqui para cuidar de você. Em caso de emergência, ligue para {emergency_phone}.",
                variables=["emergency_phone"]
            ),
            MessageTemplate(
                name="payment_reminder",
                content="Olá {patient_name}! Temos uma pendência financeira em seu nome no valor de R$ {amount}. Por favor, entre em contato para regularização.",
                variables=["patient_name", "amount"]
            )
        ]

        for template in default_templates:
            self.templates[template.name] = template

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
                    if message.scheduled_at and message.scheduled_at > datetime.utcnow():
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
                    logger.error(f"Error executing callback for message {message.id}: {e}")

        except Exception as e:
            logger.error(f"Failed to send message {message.id}: {e}")
            await self._handle_message_failure(message, str(e))

    async def _handle_message_failure(self, message: QueuedMessage, error: str) -> None:
        """Handle message sending failure with retry logic."""
        message.retry_count += 1

        if message.retry_count <= message.max_retries:
            # Calculate exponential backoff delay
            delay = min(300, 2 ** message.retry_count)  # Max 5 minutes
            message.scheduled_at = datetime.utcnow() + timedelta(seconds=delay)

            logger.info(f"Retrying message {message.id} in {delay} seconds (attempt {message.retry_count}/{message.max_retries})")
            await self.queue.enqueue(message)
        else:
            logger.error(f"Message {message.id} failed permanently after {message.retry_count} attempts")
            self._update_delivery_report(message.id, MessageStatus.FAILED, None, error)

    def _update_delivery_report(
        self,
        message_id: str,
        status: MessageStatus,
        response: Optional[MessageResponse],
        error: Optional[str] = None
    ) -> None:
        """Update delivery report for a message."""
        if message_id not in self.delivery_reports:
            self.delivery_reports[message_id] = DeliveryReport(
                message_id=message_id,
                status=status
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
        callback: Optional[Callable] = None
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
        request = MessageRequest(
            to=to,
            message_type=MessageType.TEXT,
            content=message
        )

        return await self._send_message(request, priority, delivery_mode, scheduled_at, callback)

    async def send_image(
        self,
        to: str,
        image_url: str,
        caption: Optional[str] = None,
        priority: Priority = Priority.NORMAL,
        delivery_mode: DeliveryMode = DeliveryMode.IMMEDIATE,
        scheduled_at: Optional[datetime] = None,
        callback: Optional[Callable] = None
    ) -> str:
        """Send an image message."""
        request = MessageRequest(
            to=to,
            message_type=MessageType.IMAGE,
            media_url=image_url,
            content=caption
        )

        return await self._send_message(request, priority, delivery_mode, scheduled_at, callback)

    async def send_document(
        self,
        to: str,
        document_url: str,
        filename: Optional[str] = None,
        priority: Priority = Priority.NORMAL,
        delivery_mode: DeliveryMode = DeliveryMode.IMMEDIATE,
        scheduled_at: Optional[datetime] = None,
        callback: Optional[Callable] = None
    ) -> str:
        """Send a document message."""
        request = MessageRequest(
            to=to,
            message_type=MessageType.DOCUMENT,
            media_url=document_url,
            content=filename
        )

        return await self._send_message(request, priority, delivery_mode, scheduled_at, callback)

    async def send_template(
        self,
        to: str,
        template_name: str,
        variables: Optional[Dict[str, str]] = None,
        priority: Priority = Priority.NORMAL,
        delivery_mode: DeliveryMode = DeliveryMode.IMMEDIATE,
        scheduled_at: Optional[datetime] = None,
        callback: Optional[Callable] = None
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
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found")

        template = self.templates[template_name]
        content = template.format(**(variables or {}))

        request = MessageRequest(
            to=to,
            message_type=template.message_type,
            content=content,
            media_url=template.media_url
        )

        return await self._send_message(request, priority, delivery_mode, scheduled_at, callback)

    async def _send_message(
        self,
        request: MessageRequest,
        priority: Priority,
        delivery_mode: DeliveryMode,
        scheduled_at: Optional[datetime],
        callback: Optional[Callable]
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
                    raise ValueError("No message service or evolution client configured")

                self._update_delivery_report(message_id, MessageStatus.SENT, response)

                if callback:
                    try:
                        await callback(message_id, response)
                    except Exception as e:
                        logger.error(f"Error executing callback for message {message_id}: {e}")

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
                callback=callback
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
        delay_between_batches: float = 1.0
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
            batch = messages[i:i + batch_size]
            batch_ids = []

            for msg in batch:
                try:
                    if msg.get("template_name"):
                        message_id = await self.send_template(
                            to=msg["to"],
                            template_name=msg["template_name"],
                            variables=msg.get("variables"),
                            priority=priority,
                            delivery_mode=DeliveryMode.QUEUED
                        )
                    else:
                        message_id = await self.send_text(
                            to=msg["to"],
                            message=msg["message"],
                            priority=priority,
                            delivery_mode=DeliveryMode.QUEUED
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

    def remove_template(self, template_name: str) -> None:
        """Remove a message template."""
        if template_name in self.templates:
            del self.templates[template_name]

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
            if hasattr(payload, 'message_id') and hasattr(payload, 'status'):
                if payload.message_id in self.delivery_reports:
                    self._update_delivery_report(
                        payload.message_id,
                        payload.status,
                        None
                    )

            # Call registered handlers
            event_type = getattr(payload, 'event_type', 'unknown')
            if event_type in self.webhook_handlers:
                await self.webhook_handlers[event_type](payload)

        except Exception as e:
            logger.error(f"Error processing webhook: {e}")

    def get_delivery_report(self, message_id: str) -> Optional[DeliveryReport]:
        """Get delivery report for a message."""
        return self.delivery_reports.get(message_id)

    def get_delivery_reports(self, status: Optional[MessageStatus] = None) -> List[DeliveryReport]:
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


# Backward compatibility functions
async def send_whatsapp_message(
    to: str,
    message: str,
    message_service: Optional[WhatsAppMessageService] = None,
    **kwargs
) -> str:
    """
    Backward compatible function for sending WhatsApp messages.

    This function maintains compatibility with existing code while
    providing access to the new WhatsApp helper features.
    """
    if message_service:
        # Use existing message service for backward compatibility
        helper = WhatsAppHelper(message_service=message_service)
    else:
        # Use mock mode if no service provided
        helper = WhatsAppHelper(mock_mode=True)

    try:
        return await helper.send_text(to, message, **kwargs)
    finally:
        await helper.close()


# Factory function for easy initialization
def create_whatsapp_helper(
    message_service: Optional[WhatsAppMessageService] = None,
    evolution_client: Optional[EvolutionAPIClient] = None,
    redis_client: Optional[Redis] = None,
    mock_mode: bool = False,
    **kwargs
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
        **kwargs
    )