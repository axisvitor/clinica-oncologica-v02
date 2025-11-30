"""
Unified WhatsApp Service - Consolidates Legacy and New WhatsApp Pipelines

This service unifies two previously separate WhatsApp messaging pipelines:
1. Legacy: MessageSender using Evolution client directly
2. New: WhatsAppMessageService with queue management

Key Benefits:
- Single point of entry for all WhatsApp messaging
- Consistent error handling and retry logic
- Unified metrics collection
- Consolidated queue management
- Backward compatibility with existing code
"""
import asyncio
import logging
from typing import Any, Optional, Callable, Dict, List, Union
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.evolution import get_evolution_client, EvolutionAPIError
from app.integrations.whatsapp.services.evolution_client import EvolutionAPIClient
from app.integrations.whatsapp.services.message_service import MessageQueue, WhatsAppMessageService
from app.integrations.whatsapp.models.message import (
    MessageRequest, MessageResponse, MessageStatus as WhatsAppMessageStatus,
    MessageType as WhatsAppMessageType, WhatsAppMessage
)
from app.models.message import Message, MessageType, MessageStatus, MessageDirection
from app.models.patient import Patient
from app.domain.messaging.core import MessageService
from app.services.websocket_events import websocket_events
from app.schemas.websocket import WebSocketEventType
from app.exceptions import ExternalServiceError, NotFoundError
from app.config import settings
from app.services.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitBreakerOpenError
from app.core.retry import retry_with_backoff, RetryStrategies, RetryExhaustedError
from app.core.tracing import get_tracer, trace
from app.domain.analytics.quiz import get_quiz_metrics_collector


logger = logging.getLogger(__name__)


class MessagingMode(Enum):
    """Messaging mode configuration."""
    LEGACY = "legacy"  # Direct Evolution API calls
    QUEUE = "queue"    # Queue-based processing
    HYBRID = "hybrid"  # Auto-select based on message type


class UnifiedWhatsAppService:
    """
    Unified WhatsApp service that consolidates both messaging pipelines.

    Features:
    - Unified message sending interface
    - Consistent error handling and retry logic
    - Centralized metrics collection
    - Queue management for reliability
    - Flow-specific message handling
    - Backward compatibility
    """

    def __init__(self,
                 db: Any,
                 redis_url: Optional[str] = None,
                 default_instance_name: str = "default"):
        """
        Initialize unified WhatsApp service.

        Args:
            db: Database session (sync or async)
            redis_url: Redis URL for queue management
            default_instance_name: Default Evolution instance name (can be overridden per message)
        """
        self.db = db

        # WA-002 FIX: Detect AsyncSession properly without accessing non-existent sync_session
        self._is_async = isinstance(db, AsyncSession)
        self._db_sync = None

        if self._is_async:
            logger.info(
                "UnifiedWhatsAppService initialized with AsyncSession",
                extra={"session_type": "async", "instance": default_instance_name}
            )
        else:
            # Sync session - use directly
            self._db_sync = db
            logger.info(
                "UnifiedWhatsAppService initialized with sync Session",
                extra={"session_type": "sync", "instance": default_instance_name}
            )

        self.redis_url = redis_url or settings.REDIS_URL
        self.default_instance_name = default_instance_name

        # Legacy components (only initialize for sync sessions)
        self.message_service = None
        if self._db_sync:
            try:
                self.message_service = MessageService(self._db_sync)
                logger.info("Legacy MessageService initialized successfully")
            except Exception as e:
                logger.warning(f"Could not initialize legacy MessageService: {e}")

        self.flow_message_callbacks: Dict[str, Callable] = {}

        # Queue components
        self.message_queue = MessageQueue(self.redis_url)
        self._queue_service: Optional[WhatsAppMessageService] = None
        self._queue_client = None
        
        # Status Handler
        self.status_handler = None
        if isinstance(db, AsyncSession):
            from app.services.message_status_handler import MessageStatusHandler
            self.status_handler = MessageStatusHandler(db)

        # Tracer for distributed tracing
        self.tracer = get_tracer()

        # WA-004 FIX: Circuit breaker for Evolution API protection
        self._evolution_breaker = CircuitBreaker(
            name="evolution_api",
            failure_threshold=5,
            recovery_timeout=60,  # 1 minute
            success_threshold=3
        )
        logger.info(
            "Circuit breaker initialized for Evolution API",
            extra={
                "failure_threshold": 5,
                "recovery_timeout": 60,
                "success_threshold": 3
            }
        )

        # Unified retry policies
        self.retry_policies = {
            'default': {
                'max_retries': 3,
                'backoff_factor': 2,
                'base_delay': 300  # 5 minutes
            },
            'flow_message': {
                'max_retries': 5,
                'backoff_factor': 1.5,
                'base_delay': 180  # 3 minutes
            },
            'urgent': {
                'max_retries': 7,
                'backoff_factor': 1.2,
                'base_delay': 60  # 1 minute
            },
            'quiz_link': {
                'max_retries': 4,
                'backoff_factor': 1.8,
                'base_delay': 240  # 4 minutes
            }
        }

        # Metrics tracking
        self.metrics = {
            'messages_sent': 0,
            'messages_failed': 0,
            'queue_processed': 0,
            'retries_attempted': 0,
            'last_reset': datetime.utcnow()
        }

        logger.info("Unified WhatsApp Service initialized in Queue Mode")

    async def _get_queue_client(self) -> EvolutionAPIClient:
        """Get queue-based Evolution client."""
        if not self._queue_client:
            if not settings.WHATSAPP_EVOLUTION_API_URL:
                raise ExternalServiceError("Evolution API not configured")

            # Use mock client for development
            if settings.WHATSAPP_EVOLUTION_API_URL.startswith("http://localhost:8080"):
                from app.integrations.whatsapp.services.mock_evolution import MockEvolutionAPIClient
                self._queue_client = MockEvolutionAPIClient(
                    base_url=settings.WHATSAPP_EVOLUTION_API_URL,
                    api_key=settings.WHATSAPP_EVOLUTION_API_KEY,
                    global_webhook_url=settings.WHATSAPP_EVOLUTION_WEBHOOK_URL
                )
            else:
                self._queue_client = EvolutionAPIClient(
                    base_url=settings.WHATSAPP_EVOLUTION_API_URL,
                    api_key=settings.WHATSAPP_EVOLUTION_API_KEY,
                    global_webhook_url=settings.WHATSAPP_EVOLUTION_WEBHOOK_URL
                )

            await self._queue_client.connect()
        return self._queue_client

    async def _get_queue_service(self) -> WhatsAppMessageService:
        """Get queue-based message service."""
        if not self._queue_service:
            if isinstance(self.db, AsyncSession):
                evolution_client = await self._get_queue_client()
                self._queue_service = WhatsAppMessageService(
                    evolution_client, 
                    self.db, 
                    self.message_queue,
                    message_status_handler=self.status_handler
                )
            else:
                raise ValueError("Queue service requires AsyncSession")
        return self._queue_service

    def register_flow_callback(self, callback_type: str, callback: Callable):
        """Register callback for flow message events."""
        self.flow_message_callbacks[callback_type] = callback
        logger.info(f"Registered flow callback: {callback_type}")

    async def _ensure_patient_loaded(self, message: Message) -> Optional[Patient]:
        """
        Garantir que o paciente esteja disponível para envio (Session sync ou AsyncSession).
        """
        patient = getattr(message, "patient", None)
        if patient:
            return patient
        if not message.patient_id:
            return None
        try:
            if isinstance(self.db, AsyncSession):
                return await self.db.get(Patient, message.patient_id)
            return self._db_sync.query(Patient).get(message.patient_id)
        except Exception as exc:
            logger.error(f"Failed to load patient {message.patient_id}: {exc}")
            return None

    async def send_message(self, message: Message, **kwargs) -> bool:
        """
        Unified message sending interface.

        Args:
            message: Message object to send
            **kwargs: Additional parameters (flow_context, etc.)

        Returns:
            True if message was queued successfully
        """
        try:
            send_start = datetime.utcnow()
            flow_context = kwargs.get('flow_context')

            # Track metrics
            self.metrics['messages_sent'] += 1

            # Add unified metadata
            self._add_unified_metadata(message, **kwargs)

            # Route to queue pipeline
            success = await self._send_via_queue(message, **kwargs)
            if success:
                self.metrics['queue_processed'] += 1

            # Record send latency metric for quiz messages
            if success:
                try:
                    metadata = message.message_metadata or {}
                    template_type = metadata.get('template_type', 'unknown')
                    quiz_template_id = metadata.get('quiz_template_id')

                    if quiz_template_id and template_type.startswith('quiz_'):
                        latency = (datetime.utcnow() - send_start).total_seconds()
                        metrics = await get_quiz_metrics_collector()
                        await metrics.record_send_latency(
                            template_id=UUID(quiz_template_id),
                            latency_seconds=latency,
                            message_type=template_type.replace('quiz_', '')
                        )
                except Exception as e:
                    logger.debug(f"Failed to record send latency metric: {e}")

            # Execute unified callbacks
            if success:
                await self._execute_success_callbacks(message, **kwargs)
            else:
                await self._execute_failure_callbacks(message, **kwargs)
                self.metrics['messages_failed'] += 1

            return success

        except Exception as e:
            logger.error(f"Unified message send failed for {message.id}: {e}")
            self.metrics['messages_failed'] += 1
            await self._execute_failure_callbacks(message, str(e), **kwargs)
            return False

    def _add_unified_metadata(self, message: Message, **kwargs):
        """Add unified metadata to message."""
        if not message.message_metadata:
            message.message_metadata = {}

        message.message_metadata.update({
            'unified_service': {
                'version': '2.0.0',
                'mode': 'queue',
                'timestamp': datetime.utcnow().isoformat()
            },
            'requires_queue': True
        })

        # Add flow context if provided
        flow_context = kwargs.get('flow_context')
        if flow_context:
            message.message_metadata['flow_context'] = flow_context

            # Set retry policy based on flow context
            flow_type = flow_context.get('flow_type', 'default')
            if flow_type in ['initial_15_days', 'days_16_45']:
                message.message_metadata['retry_policy'] = 'flow_message'
            elif flow_context.get('urgent', False):
                message.message_metadata['retry_policy'] = 'urgent'
            elif 'quiz' in flow_type.lower():
                message.message_metadata['retry_policy'] = 'quiz_link'

        # Set default retry policy if not set
        if 'retry_policy' not in message.message_metadata:
            message.message_metadata['retry_policy'] = 'default'

    async def _send_via_queue(self, message: Message, **kwargs) -> bool:
        """
        Send message via queue pipeline with circuit breaker protection.

        WA-004: Circuit breaker protects against Evolution API failures
        """
        # WA-004 FIX: Check circuit breaker before processing
        if not self._evolution_breaker.can_execute():
            logger.warning(
                "Evolution API circuit breaker OPEN - skipping message send",
                extra={
                    "message_id": message.id,
                    "breaker_state": self._evolution_breaker.get_state().value
                }
            )
            await self._mark_message_failed(message, {
                "error": "Circuit breaker open",
                "message": "Evolution API temporarily unavailable"
            })
            return False

        try:
            # Convert legacy message to queue format
            queue_request = await self._convert_to_queue_request(message)

            # Get queue service
            queue_service = await self._get_queue_service()

            # Send via queue
            response = await queue_service.send_message(queue_request)

            # WA-004: Record success in circuit breaker
            self._evolution_breaker.record_success()

            if response.status == WhatsAppMessageStatus.PENDING:
                logger.info(f"Message {message.id} queued successfully")
                return True
            else:
                logger.error(f"Queue send failed for message {message.id}: {response.message}")
                await self._mark_message_failed(message, {"error": f"Queue send failed: {response.message}"})
                return False

        except Exception as e:
            logger.error(f"Queue send failed for message {message.id}: {e}")

            # WA-004: Record failure in circuit breaker
            self._evolution_breaker.record_failure()

            await self._mark_message_failed(message, {
                "error": "Queue send failed",
                "message": str(e)
            })
            return False

    async def _convert_to_queue_request(self, message: Message) -> MessageRequest:
        """
        Convert legacy message to queue request format with proper validation.

        Raises:
            ValueError: If instance_name, patient, or phone is missing
        """
        # WA-003 FIX: Validate instance_name before processing
        metadata = message.message_metadata or {}
        instance_name = metadata.get('instance_name', self.default_instance_name)

        if not instance_name:
            raise ValueError("instance_name is required for queue request")

        # Certifique-se de que o paciente está carregado para obter o telefone
        patient = await self._ensure_patient_loaded(message)
        if not patient:
            raise ValueError(f"Patient {message.patient_id} not found")

        if not patient.phone:
            raise ValueError(f"Patient {message.patient_id} has no phone number")

        # Map legacy message types to queue types
        type_mapping = {
            MessageType.TEXT: WhatsAppMessageType.TEXT,
            MessageType.MEDIA: WhatsAppMessageType.IMAGE,  # Default to image
            MessageType.BUTTON: WhatsAppMessageType.TEXT,  # Buttons as text for now
            MessageType.LIST: WhatsAppMessageType.TEXT,    # Lists as text for now
            MessageType.MONTHLY_QUIZ_LINK: WhatsAppMessageType.TEXT,
            MessageType.MONTHLY_QUIZ_REMINDER: WhatsAppMessageType.TEXT,
            MessageType.MONTHLY_QUIZ_EXPIRED: WhatsAppMessageType.TEXT,
            MessageType.MONTHLY_QUIZ_COMPLETED: WhatsAppMessageType.TEXT
        }

        queue_type = type_mapping.get(message.type, WhatsAppMessageType.TEXT)

        # Handle media-specific metadata
        metadata = message.message_metadata or {}
        media_url = None
        media_caption = None
        
        # Inject domain message ID into metadata for status tracking
        metadata['domain_message_id'] = str(message.id)

        if message.type == MessageType.MEDIA:
            media_url = metadata.get('media_url')
            media_caption = metadata.get('caption')
            media_type = metadata.get('media_type', 'image')

            # Map media types
            if media_type == 'video':
                queue_type = WhatsAppMessageType.VIDEO
            elif media_type == 'audio':
                queue_type = WhatsAppMessageType.AUDIO
            elif media_type == 'document':
                queue_type = WhatsAppMessageType.DOCUMENT

        # Allow per-message instance override via metadata
        instance_name = metadata.get('instance_name', self.default_instance_name)

        return MessageRequest(
            instance_name=instance_name,
            to=patient.phone,
            message_type=queue_type,
            text=message.content,
            media_url=media_url,
            media_caption=media_caption,
            message_data=metadata
        )

    async def _mark_message_failed(self, message: Message, error_info: Dict[str, Any]):
        """Mark message as failed with unified error information."""
        # Add unified error metadata
        unified_error = {
            'unified_service_error': True,
            'timestamp': datetime.utcnow().isoformat(),
            'pipeline': 'queue',
            **error_info
        }

        await self.message_service.mark_as_failed_async(message.id, unified_error)

        # Publish WebSocket event
        await self._publish_message_event(
            WebSocketEventType.MESSAGE_FAILED,
            message,
            metadata=unified_error
        )

    async def _publish_message_event(self, event_type: WebSocketEventType, message: Message, **kwargs):
        """Publish unified WebSocket events."""
        await websocket_events.publish_message_event(
            event_type=event_type,
            message_id=message.id,
            patient_id=message.patient_id,
            direction=message.direction.value,
            message_type=message.type.value,
            content=message.content,
            status=message.status.value,
            **kwargs
        )

    async def _execute_success_callbacks(self, message: Message, **kwargs):
        """Execute success callbacks for flow messages."""
        if 'message_sent' in self.flow_message_callbacks:
            try:
                flow_context = kwargs.get('flow_context')
                await self.flow_message_callbacks['message_sent'](message, flow_context)
            except Exception as e:
                logger.error(f"Success callback error: {e}")

    async def _execute_failure_callbacks(self, message: Message, error: str = None, **kwargs):
        """Execute failure callbacks for flow messages."""
        if 'message_failed' in self.flow_message_callbacks:
            try:
                flow_context = kwargs.get('flow_context')
                await self.flow_message_callbacks['message_failed'](message, flow_context, error)
            except Exception as e:
                logger.error(f"Failure callback error: {e}")

    async def send_flow_message(self, message: Message, flow_context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send a flow-specific message with enhanced tracking.

        Args:
            message: Message object to send
            flow_context: Flow-specific context data

        Returns:
            True if message was sent successfully
        """
        return await self.send_message(message, flow_context=flow_context)

    async def retry_failed_messages(self, limit: int = 50) -> int:
        """
        Retry failed messages using unified retry policies.

        Args:
            limit: Maximum number of messages to retry

        Returns:
            Number of messages successfully retried
        """
        failed_messages = self.message_service.get_failed_messages(limit=limit)
        retry_count = 0

        for message in failed_messages:
            try:
                # Get retry policy for this message
                metadata = message.message_metadata or {}
                retry_policy_name = metadata.get('retry_policy', 'default')
                retry_policy = self.retry_policies.get(retry_policy_name, self.retry_policies['default'])

                retry_attempts = metadata.get('retry_attempts', 0)
                max_retries = retry_policy['max_retries']

                if retry_attempts >= max_retries:
                    logger.info(f"Message {message.id} exceeded max retries ({max_retries}), skipping")
                    continue

                # Calculate backoff delay
                base_delay = retry_policy['base_delay']
                backoff_factor = retry_policy['backoff_factor']
                delay = base_delay * (backoff_factor ** retry_attempts)

                # Check if enough time has passed since last retry
                last_retry_str = metadata.get('last_retry_at')
                if last_retry_str:
                    last_retry = datetime.fromisoformat(last_retry_str)
                    time_since_retry = (datetime.utcnow() - last_retry).total_seconds()
                    if time_since_retry < delay:
                        logger.debug(f"Message {message.id} not ready for retry")
                        continue

                # Update retry metadata
                metadata['retry_attempts'] = retry_attempts + 1
                metadata['last_retry_at'] = datetime.utcnow().isoformat()
                metadata['retry_policy_used'] = retry_policy_name

                # Update message
                self.message_service.update_message(message.id, {
                    'message_metadata': metadata,
                    'status': MessageStatus.PENDING
                })

                # Attempt retry
                flow_context = metadata.get('flow_context')
                success = await self.send_message(message, flow_context=flow_context)

                if success:
                    retry_count += 1
                    self.metrics['retries_attempted'] += 1
                    logger.info(f"Successfully retried message {message.id} (attempt {retry_attempts + 1})")
                else:
                    logger.warning(f"Failed to retry message {message.id} (attempt {retry_attempts + 1})")

            except Exception as e:
                logger.error(f"Error retrying message {message.id}: {e}", exc_info=True)

        logger.info(f"Retry process: {retry_count}/{len(failed_messages)} messages successfully retried")
        return retry_count

    async def get_unified_metrics(self) -> Dict[str, Any]:
        """
        Get unified metrics across both pipelines.

        Returns:
            Comprehensive metrics dictionary
        """
        # Get queue metrics if available
        queue_stats = {}
        try:
            queue_stats = await self.message_queue.get_queue_stats()
        except Exception as e:
            logger.warning(f"Could not get queue stats: {e}")

        # Calculate uptime
        uptime = (datetime.utcnow() - self.metrics['last_reset']).total_seconds()

        return {
            'unified_metrics': {
                'total_sent': self.metrics['messages_sent'],
                'total_failed': self.metrics['messages_failed'],
                'success_rate': (
                    (self.metrics['messages_sent'] - self.metrics['messages_failed']) /
                    max(self.metrics['messages_sent'], 1) * 100
                ),
                'queue_processed': self.metrics['queue_processed'],
                'retries_attempted': self.metrics['retries_attempted'],
                'uptime_seconds': uptime
            },
            'queue_metrics': queue_stats,
            'messaging_mode': 'queue',
            'retry_policies': list(self.retry_policies.keys()),
            'generated_at': datetime.utcnow().isoformat()
        }

    async def process_queue_messages(self, max_messages: int = 100) -> Dict[str, Any]:
        """
        Process messages from the queue.

        Args:
            max_messages: Maximum number of messages to process

        Returns:
            Processing results
        """
        if not isinstance(self.db, AsyncSession):
            raise ValueError("Queue processing requires AsyncSession")

        queue_service = await self._get_queue_service()

        # Start background task for queue processing
        task = asyncio.create_task(queue_service.process_message_queue())

        return {
            'queue_processing_started': True,
            'max_messages': max_messages,
            'started_at': datetime.utcnow().isoformat()
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on unified service.

        Returns:
            Health status information
        """
        health = {
            'service': 'unified_whatsapp',
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'components': {}
        }

        # Check queue client
        try:
            await self._get_queue_client()
            health['components']['queue_client'] = 'healthy'
        except Exception as e:
            health['components']['queue_client'] = f'unhealthy: {str(e)}'
            health['status'] = 'degraded'


        # Check queue connection
        try:
            await self.message_queue.connect()
            health['components']['message_queue'] = 'healthy'
        except Exception as e:
            health['components']['message_queue'] = f'unhealthy: {str(e)}'
            health['status'] = 'degraded'

        return health

    async def shutdown(self):
        """Gracefully shutdown the unified service."""
        try:
            if self._queue_service:
                await self.message_queue.disconnect()

            if self._queue_client:
                # Assuming disconnect method exists
                pass

            logger.info("Unified WhatsApp Service shutdown completed")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


# Factory function for creating unified service instances
def create_unified_whatsapp_service(
    db: Any,
    messaging_mode: MessagingMode = MessagingMode.HYBRID,
    redis_url: Optional[str] = None
) -> UnifiedWhatsAppService:
    """
    Factory function to create unified WhatsApp service instances.

    Args:
        db: Database session
        messaging_mode: Messaging mode configuration
        redis_url: Redis URL for queue management

    Returns:
        Configured UnifiedWhatsAppService instance
    """
    return UnifiedWhatsAppService(
        db=db,
        messaging_mode=messaging_mode,
        redis_url=redis_url
    )
