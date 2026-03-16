"""
Unified WhatsApp Service - Consolidates Direct API and Queue WhatsApp Pipelines

This service unifies two previously separate WhatsApp messaging pipelines:
1. Direct API: MessageSender using provider client directly
2. Queue: WhatsAppMessageService with queue management

Key Benefits:
- Single point of entry for all WhatsApp messaging
- Consistent error handling and retry logic
- Unified metrics collection
- Consolidated queue management
"""

import asyncio
import json
import logging
from typing import Any, Optional, Callable, Dict, cast
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from app.database import get_async_session_factory
from app.integrations.wuzapi import get_wuzapi_client, WuzAPIClient
from app.integrations.wuzapi.media import fetch_and_encode_media
from app.integrations.whatsapp.services.message_service import (
    MessageQueue,
    WhatsAppMessageService,
)
from app.integrations.whatsapp.models.message import (
    MessageRequest,
    MessageStatus as WhatsAppMessageStatus,
    MessageType as WhatsAppMessageType,
)
from app.models.message import Message, MessageType, MessageStatus
from app.models.patient import Patient

# MessageService for marking messages as failed
from app.domain.messaging.core import MessageService
from app.services import websocket_events as ws_events_module
from app.schemas.websocket import WebSocketEventType
from app.exceptions import ExternalServiceError
from app.config import settings
# Use Redis-backed circuit breaker for cross-worker consistency
from app.core.redis_circuit_breaker import (
    RedisCircuitBreaker as CircuitBreaker,
    CircuitOpenError,
)
from app.domain.analytics.quiz import get_quiz_metrics_collector
from app.integrations.whatsapp.metrics import whatsapp_metrics
from app.utils.timezone import now_sao_paulo
from app.schemas.validators.phone import normalize_phone, PhoneValidationMode


logger = logging.getLogger(__name__)


class UnifiedWhatsAppService:
    """
    Unified WhatsApp service that consolidates both messaging pipelines.

    Features:
    - Unified message sending interface
    - Consistent error handling and retry logic
    - Centralized metrics collection
    - Queue management for reliability
    - Flow-specific message handling
    """

    def __init__(
        self,
        db: Any,
        redis_url: Optional[str] = None,
        default_instance_name: Optional[str] = None,
    ):
        """
        Initialize unified WhatsApp service.

        Args:
            db: Database session (sync or async)
            redis_url: Redis URL for queue management
            default_instance_name: Default instance name (falls back to settings)
        """
        self.db = db
        resolved_redis_url = redis_url
        resolved_instance_name = default_instance_name

        configured_instance_name = resolved_instance_name
        if not isinstance(configured_instance_name, str):
            configured_instance_name = None
        resolved_instance_name = (
            (configured_instance_name or "default").strip() or "default"
        )

        # WA-002 FIX: support AsyncSession and async-like mocked sessions in tests.
        execute_method = getattr(db, "execute", None)
        self._is_async = isinstance(db, AsyncSession) or asyncio.iscoroutinefunction(
            execute_method
        )
        self._db_sync = None

        if self._is_async:
            logger.info(
                "UnifiedWhatsAppService initialized with async-compatible session",
                extra={"session_type": "async", "instance": resolved_instance_name},
            )
        else:
            # Sync session - use directly
            self._db_sync = db
            logger.info(
                "UnifiedWhatsAppService initialized with sync Session",
                extra={"session_type": "sync", "instance": resolved_instance_name},
            )

        self.redis_url = resolved_redis_url or settings.REDIS_URL
        self.default_instance_name = resolved_instance_name

        self.flow_message_callbacks: Dict[str, Callable] = {}

        # Queue components
        self.message_queue = MessageQueue(self.redis_url)
        self._queue_service: Optional[WhatsAppMessageService] = None
        self._queue_client = None
        self._wuzapi_client: Optional[WuzAPIClient] = None

        # Status Handler
        self.status_handler = None
        if isinstance(db, AsyncSession):
            from app.services.message_status_handler import MessageStatusHandler

            self.status_handler = MessageStatusHandler(db)

        # Message Service for marking messages as failed (sync sessions only)
        self.message_service = None
        if self._db_sync is not None:
            self.message_service = MessageService(self._db_sync)

        # WA-004 FIX: Circuit breaker for WuzAPI protection
        self._wuzapi_breaker = CircuitBreaker(
            name="wuzapi",
            failure_threshold=5,
            recovery_timeout=60,  # 1 minute
            success_threshold=3,
        )
        logger.info(
            "Circuit breaker initialized for WuzAPI",
            extra={
                "failure_threshold": 5,
                "recovery_timeout": 60,
                "success_threshold": 3,
            },
        )

        # Unified retry policies
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
            "urgent": {
                "max_retries": 7,
                "backoff_factor": 1.2,
                "base_delay": 60,  # 1 minute
            },
            "quiz_link": {
                "max_retries": 4,
                "backoff_factor": 1.8,
                "base_delay": 240,  # 4 minutes
            },
        }

        # Metrics tracking
        self.metrics = {
            "messages_sent": 0,
            "messages_failed": 0,
            "queue_processed": 0,
            "retries_attempted": 0,
            "last_reset": now_sao_paulo(),
        }

        env_name = str(getattr(settings, "APP_ENVIRONMENT", "development")).lower()
        self._messaging_mode = "queue" if env_name == "production" else "direct"
        logger.info(
            "Unified WhatsApp Service initialized",
            extra={
                "messaging_mode": self._messaging_mode,
                "environment": env_name,
            },
        )

    async def _get_wuzapi_client(self) -> WuzAPIClient:
        """Get WuzAPI client for outbound messaging."""
        if not self._wuzapi_client:
            token = getattr(settings, "WHATSAPP_WUZAPI_TOKEN", None)
            base_url = getattr(settings, "WHATSAPP_WUZAPI_BASE_URL", "")
            if not token:
                raise ExternalServiceError(
                    "WuzAPI not configured: WHATSAPP_WUZAPI_TOKEN missing"
                )
            client = get_wuzapi_client(base_url=base_url, token=token)
            self._wuzapi_client = cast(WuzAPIClient, client)
            await self._wuzapi_client.connect()
        return self._wuzapi_client

    async def _get_queue_service(self) -> WhatsAppMessageService:
        """Get queue-based message service."""
        if not self._queue_service:
            if self._is_async:
                wuzapi_client = await self._get_wuzapi_client()
                self._queue_service = WhatsAppMessageService(
                    wuzapi_client,
                    self.db,
                    self.message_queue,
                    message_status_handler=self.status_handler,
                )
            else:
                raise ValueError("Queue service requires AsyncSession")
        return self._queue_service

    async def _execute_async_db(self, statement):
        """Execute statement against async-compatible DB sessions."""
        result = self.db.execute(statement)
        if asyncio.iscoroutine(result):
            return await result
        return result

    async def _commit_async_db(self):
        """Commit changes against async-compatible DB sessions."""
        result = self.db.commit()
        if asyncio.iscoroutine(result):
            await result

    def register_flow_callback(self, callback_type: str, callback: Callable):
        """Register callback for flow message events."""
        self.flow_message_callbacks[callback_type] = callback
        logger.info(f"Registered flow callback: {callback_type}")

    async def _ensure_patient_loaded(self, message: Message) -> Optional[Patient]:
        """
        Garantir que o paciente esteja disponível para envio (Session sync ou AsyncSession).
        """
        # Avoid accessing message.patient directly if it might trigger sync lazy load
        # Check if the relationship is already loaded
        from sqlalchemy import inspect
        ins = inspect(message)
        
        if "patient" not in ins.unloaded:
            return message.patient
            
        if not message.patient_id:
            return None
            
        try:
            if isinstance(self.db, AsyncSession):
                return await self.db.get(Patient, message.patient_id)
            if self._db_sync:
                return self._db_sync.query(Patient).get(message.patient_id)
            return None
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
            
        Raises:
            ExternalServiceError: If sending fails (for Celery retry handling)
        """
        force_send = bool(kwargs.get("force_send"))
        if not force_send and message.status in {
            MessageStatus.SCHEDULED,
            MessageStatus.SENDING,
            MessageStatus.SENT,
            MessageStatus.DELIVERED,
            MessageStatus.READ,
        }:
            logger.info(
                "Skipping send for message with terminal/non-sendable status",
                extra={
                    "message_id": str(message.id),
                    "status": message.status.value,
                    "force_send": force_send,
                },
            )
            return True

        # LGPD Art. 18 — Opt-out guard (last-resort safety net).
        # Refuse to send if the patient has revoked messaging consent.
        # This check fires even if the Celery task scheduler failed to filter
        # the patient earlier.  We load the patient lazily only when needed
        # to avoid adding latency to the common (non-opted-out) path.
        try:
            patient_for_guard = await self._ensure_patient_loaded(message)
            if patient_for_guard is not None and patient_for_guard.messaging_stopped_at is not None:
                logger.warning(
                    "Skipping message to opted-out patient %s (messaging_stopped_at=%s)",
                    message.patient_id,
                    patient_for_guard.messaging_stopped_at.isoformat(),
                    extra={
                        "message_id": str(message.id),
                        "patient_id": str(message.patient_id),
                        "messaging_stopped_at": patient_for_guard.messaging_stopped_at.isoformat(),
                    },
                )
                return False
        except Exception as guard_err:
            # Guard failure must never block legitimate sends — log and continue.
            logger.error(
                "Opt-out guard check failed for message %s (proceeding with send): %s",
                message.id,
                guard_err,
            )

        if not self._is_async:
            # Sync sessions cannot use the queue service directly; rehydrate via async session.
            try:
                async_factory = get_async_session_factory()
            except Exception as factory_err:
                raise ExternalServiceError(
                    f"Async session factory unavailable for queue send: {factory_err}"
                ) from factory_err

            async with async_factory() as async_session:
                from sqlalchemy import select

                result = await async_session.execute(
                    select(Message).where(Message.id == message.id)
                )
                async_message = result.scalar_one_or_none()
                if not async_message:
                    raise ExternalServiceError(
                        f"Message {message.id} not found in async session"
                    )

                async_service = UnifiedWhatsAppService(
                    async_session,
                    redis_url=self.redis_url,
                    default_instance_name=self.default_instance_name,
                )
                try:
                    return await async_service.send_message(async_message, **kwargs)
                finally:
                    await async_service.shutdown()

        send_start = now_sao_paulo()
        kwargs.get("flow_context")

        # Track metrics
        self.metrics["messages_sent"] += 1

        # Add unified metadata
        self._add_unified_metadata(message, **kwargs)

        try:
            if self._messaging_mode == "direct":
                success = await self._send_via_direct_api(message, **kwargs)
            else:
                success = await self._send_via_queue(message, **kwargs)
            
            if success:
                self.metrics["queue_processed"] += 1

                # Record send latency metric for quiz messages
                try:
                    metadata = message.message_metadata or {}
                    template_type = metadata.get("template_type", "unknown")
                    quiz_template_id = metadata.get("quiz_template_id")

                    if quiz_template_id and template_type.startswith("quiz_"):
                        latency = (now_sao_paulo() - send_start).total_seconds()
                        metrics = await get_quiz_metrics_collector()
                        await metrics.record_send_latency(
                            template_id=UUID(quiz_template_id),
                            latency_seconds=latency,
                            message_type=template_type.replace("quiz_", ""),
                        )
                except Exception as e:
                    logger.debug(f"Failed to record send latency metric: {e}")

                # Execute success callbacks
                await self._execute_success_callbacks(message, **kwargs)

            return success

        except ExternalServiceError:
            # Propagate ExternalServiceError for upstream handling
            self.metrics["messages_failed"] += 1
            await self._execute_failure_callbacks(message, **kwargs)
            raise
        except Exception as e:
            logger.error(f"Unified message send failed for {message.id}: {e}")
            self.metrics["messages_failed"] += 1
            await self._execute_failure_callbacks(message, str(e), **kwargs)
            # Wrap in ExternalServiceError for consistent retry handling
            raise ExternalServiceError(f"Message send failed: {e}") from e

    def _add_unified_metadata(self, message: Message, **kwargs):
        """Add unified metadata to message."""
        if not message.message_metadata:
            message.message_metadata = {}

        message.message_metadata.update(
            {
                "unified_service": {
                    "version": "2.0.0",
                    "mode": self._messaging_mode,
                    "timestamp": now_sao_paulo().isoformat(),
                },
                "requires_queue": self._messaging_mode == "queue",
            }
        )

        # Add flow context if provided
        flow_context = kwargs.get("flow_context")
        if flow_context:
            message.message_metadata["flow_context"] = flow_context

            # Set retry policy based on flow context
            flow_type = flow_context.get("flow_type", "default")
            if flow_type in ["onboarding", "daily_follow_up"]:
                message.message_metadata["retry_policy"] = "flow_message"
            elif flow_context.get("urgent", False):
                message.message_metadata["retry_policy"] = "urgent"
            elif "quiz" in flow_type.lower():
                message.message_metadata["retry_policy"] = "quiz_link"

        # Set default retry policy if not set
        if "retry_policy" not in message.message_metadata:
            message.message_metadata["retry_policy"] = "default"

    async def _send_via_queue(self, message: Message, **kwargs) -> bool:
        """
        Send message via queue pipeline with circuit breaker protection.

        WA-004: Circuit breaker protects against WuzAPI failures
        
        Note: This method does NOT mark messages as FAILED on transient failures.
        The Celery task is responsible for marking FAILED only after exhausting retries.
        """
        try:
            # Convert message to queue format
            queue_request = await self._convert_to_queue_request(message)

            # Get queue service
            queue_service = await self._get_queue_service()

            async def _send_request():
                return await queue_service.send_message(queue_request)

            # Send via queue with Redis-backed circuit breaker
            response = await self._wuzapi_breaker.call(_send_request)

            if response.status == WhatsAppMessageStatus.PENDING:
                logger.info(f"Message {message.id} queued successfully")
                return True
            else:
                # Do NOT mark as failed - let Celery retry handle it
                logger.warning(
                    f"Queue send returned non-pending status for message {message.id}: {response.message}"
                )
                raise ExternalServiceError(
                    f"Queue send failed: {response.message}"
                )

        except CircuitOpenError as exc:
            breaker_state = await self._wuzapi_breaker.get_state_async()
            logger.warning(
                "WuzAPI circuit breaker OPEN - skipping message send",
                extra={
                    "message_id": str(message.id),
                    "breaker_state": breaker_state.value,
                },
            )
            raise ExternalServiceError(
                f"Circuit breaker open for WuzAPI (state: {breaker_state.value})"
            ) from exc
        except ExternalServiceError as exc:
            logger.error(f"Queue send failed for message {message.id}: {exc}")
            raise
        except Exception as e:
            logger.error(f"Queue send failed for message {message.id}: {e}")
            # Do NOT mark as failed - propagate error for Celery retry
            raise ExternalServiceError(f"Queue send failed: {e}") from e

    async def _send_via_direct_api(self, message: Message, **kwargs) -> bool:
        """Send message directly via WuzAPI (no queue)."""
        try:
            metadata = message.message_metadata or {}

            patient = await self._ensure_patient_loaded(message)
            if not patient or not patient.phone_decrypted:
                raise ExternalServiceError(
                    f"Patient {message.patient_id} has no phone number"
                )

            phone = normalize_phone(
                patient.phone_decrypted, mode=PhoneValidationMode.BR_TO_E164
            )
            if not phone:
                raise ExternalServiceError(
                    f"Patient {message.patient_id} has invalid phone number"
                )
            if phone.startswith("+"):
                phone = phone[1:]

            wuzapi_client = await self._get_wuzapi_client()

            if message.type == MessageType.TEXT or not message.type:
                response = await wuzapi_client.send_text(
                    phone=phone, message=message.content or ""
                )
            else:
                media_url = metadata.get("media_url", "")
                media_type = metadata.get("media_type", "image")
                if not media_url:
                    raise ExternalServiceError("media_url is required for media send")
                data_uri = await fetch_and_encode_media(media_url)
                response = await wuzapi_client.send_media(
                    media_type=media_type,
                    phone=phone,
                    data_uri=data_uri,
                )

            message.status = MessageStatus.SENT
            message.whatsapp_id = response.get("data", {}).get("Id")
            message.sent_at = now_sao_paulo()

            if self._is_async:
                await self._commit_async_db()
            elif self._db_sync:
                self._db_sync.commit()

            return True
        except Exception as exc:
            logger.error(f"Direct send failed for message {message.id}: {exc}")
            try:
                message.status = MessageStatus.FAILED
                message.message_metadata = {
                    **(message.message_metadata or {}),
                    "error": str(exc),
                }
                if self._is_async:
                    await self._commit_async_db()
                elif self._db_sync:
                    self._db_sync.commit()
            except Exception:
                # Best-effort status update; preserve original error
                pass
            raise ExternalServiceError(f"Direct send failed: {exc}") from exc

    async def _convert_to_queue_request(self, message: Message) -> MessageRequest:
        """
        Convert message to queue request format with proper validation.

        Raises:
            ValueError: If instance_name, patient, or phone is missing
        """
        # WA-003 FIX: Validate instance_name before processing
        metadata = message.message_metadata or {}
        instance_name = metadata.get("instance_name", self.default_instance_name)

        if not instance_name:
            raise ValueError("instance_name is required for queue request")

        # Certifique-se de que o paciente está carregado para obter o telefone
        patient = await self._ensure_patient_loaded(message)
        if not patient:
            raise ValueError(f"Patient {message.patient_id} not found")

        # LGPD: Use decrypted phone accessor
        if not patient.phone_decrypted:
            raise ValueError(f"Patient {message.patient_id} has no phone number")

        # Map message types to queue types
        type_mapping = {
            MessageType.TEXT: WhatsAppMessageType.TEXT,
            MessageType.MEDIA: WhatsAppMessageType.IMAGE,  # Default to image
            MessageType.BUTTON: WhatsAppMessageType.TEXT,  # Buttons as text for now
            MessageType.LIST: WhatsAppMessageType.TEXT,  # Lists as text for now
            MessageType.MONTHLY_QUIZ_LINK: WhatsAppMessageType.TEXT,
            MessageType.MONTHLY_QUIZ_REMINDER: WhatsAppMessageType.TEXT,
            MessageType.MONTHLY_QUIZ_EXPIRED: WhatsAppMessageType.TEXT,
            MessageType.MONTHLY_QUIZ_COMPLETED: WhatsAppMessageType.TEXT,
        }

        queue_type = type_mapping.get(message.type, WhatsAppMessageType.TEXT)

        # Handle media-specific metadata
        metadata = message.message_metadata or {}
        media_url = None
        media_caption = None

        # Inject domain message ID into metadata for status tracking
        metadata["domain_message_id"] = str(message.id)

        if message.type == MessageType.MEDIA:
            media_url = metadata.get("media_url")
            media_caption = metadata.get("caption")
            media_type = metadata.get("media_type", "image")

            # Map media types
            if media_type == "video":
                queue_type = WhatsAppMessageType.VIDEO
            elif media_type == "audio":
                queue_type = WhatsAppMessageType.AUDIO
            elif media_type == "document":
                queue_type = WhatsAppMessageType.DOCUMENT

        # Allow per-message instance override via metadata
        instance_name = metadata.get("instance_name", self.default_instance_name)

        return MessageRequest(
            instance_name=instance_name,
            to=patient.phone_decrypted,  # LGPD: Use decrypted phone
            message_type=queue_type,
            text=message.content,
            media_url=media_url,
            media_caption=media_caption,
            message_data=metadata,
        )

    async def _mark_message_failed(self, message: Message, error_info: Dict[str, Any]):
        """Mark message as failed with unified error information."""
        # Add unified error metadata
        unified_error = {
            "unified_service_error": True,
            "timestamp": now_sao_paulo().isoformat(),
            "pipeline": "queue",
            **error_info,
        }

        # Mark message as failed using message_service (if available)
        error_message = json.dumps(unified_error)

        if self.message_service is not None:
            await self.message_service.mark_as_failed_async(message.id, error_message)
        elif self._is_async:
            # Use existing async session
            try:
                from app.models.message import Message as MessageModel, MessageStatus
                stmt = (
                    update(MessageModel)
                    .where(MessageModel.id == message.id)
                    .values(
                        status=MessageStatus.FAILED,
                        failed_at=now_sao_paulo(),
                        error_message=error_message,
                        updated_at=now_sao_paulo(),
                    )
                )
                await self._execute_async_db(stmt)
                await self._commit_async_db()
                
                logger.info(
                    f"Message {message.id} marked as failed via async update",
                    extra={"unified_error": unified_error},
                )
            except Exception as db_error:
                logger.error(
                    f"Failed to mark message {message.id} as failed (async): {db_error}",
                    extra={"unified_error": unified_error, "db_error": str(db_error)},
                )
        else:
            # Direct database update when message_service not available and using sync db
            try:
                from app.database import get_scoped_session
                from app.models.message import Message as MessageModel, MessageStatus

                with get_scoped_session() as session:
                    stmt = (
                        update(MessageModel)
                        .where(MessageModel.id == message.id)
                        .values(
                            status=MessageStatus.FAILED,
                            failed_at=now_sao_paulo(),
                            error_message=error_message,
                            updated_at=now_sao_paulo(),
                        )
                    )
                    session.execute(stmt)
                    session.commit()
                    # get_scoped_session commits automatically on exit but commit explicitly to be safe during updates

                logger.info(
                    f"Message {message.id} marked as failed via direct update",
                    extra={"unified_error": unified_error},
                )
            except Exception as db_error:
                logger.error(
                    f"Failed to mark message {message.id} as failed: {db_error}",
                    extra={"unified_error": unified_error, "db_error": str(db_error)},
                )

        # Publish WebSocket event
        await self._publish_message_event(
            WebSocketEventType.MESSAGE_FAILED, message, metadata=unified_error
        )

    async def _publish_message_event(
        self, event_type: WebSocketEventType, message: Message, **kwargs
    ):
        """Publish unified WebSocket events."""
        if ws_events_module.websocket_events:
            metadata = kwargs.pop("metadata", None)
            if kwargs:
                metadata = {**(metadata or {}), **kwargs}

            await ws_events_module.websocket_events.broadcast_message_event(
                event_type=event_type,
                message_data={
                    "message_id": message.id,
                    "patient_id": message.patient_id,
                    "direction": message.direction.value,
                    "type": message.type.value,
                    "content": message.content,
                    "status": message.status.value,
                    "whatsapp_id": message.whatsapp_id,
                    "metadata": metadata,
                },
            )

    async def _execute_success_callbacks(self, message: Message, **kwargs):
        """Execute success callbacks for flow messages."""
        if "message_sent" in self.flow_message_callbacks:
            try:
                flow_context = kwargs.get("flow_context")
                await self.flow_message_callbacks["message_sent"](message, flow_context)
            except Exception as e:
                logger.error(f"Success callback error: {e}")

    async def _execute_failure_callbacks(
        self, message: Message, error: str = None, **kwargs
    ):
        """Execute failure callbacks for flow messages."""
        if "message_failed" in self.flow_message_callbacks:
            try:
                flow_context = kwargs.get("flow_context")
                await self.flow_message_callbacks["message_failed"](
                    message, flow_context, error
                )
            except Exception as e:
                logger.error(f"Failure callback error: {e}")

    # NOTE: retry_failed_messages() removed - use Celery task retry_failed_messages_task instead
    # See: app/tasks/messaging.py and beat_schedule["retry-failed-messages"]

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
        uptime = (now_sao_paulo() - self.metrics["last_reset"]).total_seconds()

        return {
            "unified_metrics": {
                "total_sent": self.metrics["messages_sent"],
                "total_failed": self.metrics["messages_failed"],
                "success_rate": (
                    (self.metrics["messages_sent"] - self.metrics["messages_failed"])
                    / max(self.metrics["messages_sent"], 1)
                    * 100
                ),
                "queue_processed": self.metrics["queue_processed"],
                "retries_attempted": self.metrics["retries_attempted"],
                "uptime_seconds": uptime,
            },
            "queue_metrics": queue_stats,
            "messaging_mode": self._messaging_mode,
            "retry_policies": list(self.retry_policies.keys()),
            "generated_at": now_sao_paulo().isoformat(),
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
        asyncio.create_task(queue_service.process_message_queue())

        return {
            "queue_processing_started": True,
            "max_messages": max_messages,
            "started_at": now_sao_paulo().isoformat(),
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on unified service.

        Returns:
            Health status information
        """
        health: Dict[str, Any] = {
            "service": "unified_whatsapp",
            "status": "healthy",
            "timestamp": now_sao_paulo().isoformat(),
            "components": {},
        }

        def _set_component_status(name: str, status: str, details: Any = None) -> None:
            payload = {"status": status}
            if details is not None:
                payload["details"] = details
            health["components"][name] = payload

            if status == "unhealthy":
                health["status"] = "unhealthy"
            elif status == "degraded" and health["status"] != "unhealthy":
                health["status"] = "degraded"

        # Check WuzAPI client
        try:
            await self._get_wuzapi_client()
            _set_component_status("wuzapi_client", "healthy")
        except Exception as e:
            _set_component_status("wuzapi_client", "unhealthy", str(e))

        # Check queue connection
        try:
            await self.message_queue.connect()
            _set_component_status("message_queue", "healthy")
        except Exception as e:
            _set_component_status("message_queue", "unhealthy", str(e))

        # Check WuzAPI session health
        try:
            wuzapi_client = await self._get_wuzapi_client()
            status_resp = await wuzapi_client.get_session_status()
            from app.integrations.wuzapi import normalize_session_status

            normalized = normalize_session_status(status_resp)
            is_connected = normalized["connected"] and normalized["logged_in"]
            instance_status = "healthy" if is_connected else "degraded"
            _set_component_status("wuzapi_session", instance_status, status_resp)
        except Exception as e:
            _set_component_status("wuzapi_session", "unhealthy", str(e))

        # Circuit breaker stats
        try:
            breaker_stats = await self._wuzapi_breaker.get_stats_async()
            breaker_state = breaker_stats.get("state", "unknown")
            breaker_status = (
                "healthy"
                if breaker_state == "closed"
                else "degraded"
                if breaker_state in ("open", "half_open")
                else "unhealthy"
            )
            _set_component_status("circuit_breaker", breaker_status, breaker_stats)
            whatsapp_metrics.set_circuit_breaker_state(
                self.default_instance_name, "wuzapi", breaker_state
            )
        except Exception as e:
            _set_component_status("circuit_breaker", "unhealthy", str(e))

        return health

    async def shutdown(self):
        """Gracefully shutdown the unified service."""
        try:
            if self._queue_service or self.message_queue:
                await self.message_queue.disconnect()

            if self._queue_client:
                disconnect_fn = getattr(self._queue_client, "disconnect", None)
                if callable(disconnect_fn):
                    disconnect_result = disconnect_fn()
                    if asyncio.iscoroutine(disconnect_result):
                        await disconnect_result
                self._queue_client = None

            if self._wuzapi_client:
                try:
                    await self._wuzapi_client.disconnect()
                except Exception:
                    pass
                self._wuzapi_client = None

            self._queue_service = None

            logger.info("Unified WhatsApp Service shutdown completed")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


# Factory function for creating unified service instances
def create_unified_whatsapp_service(
    db: Any,
    redis_url: Optional[str] = None,
) -> UnifiedWhatsAppService:
    """
    Factory function to create unified WhatsApp service instances.

    Args:
        db: Database session
        redis_url: Redis URL for queue management

    Returns:
        Configured UnifiedWhatsAppService instance
    """
    return UnifiedWhatsAppService(db=db, redis_url=redis_url)


__all__ = [
    "UnifiedWhatsAppService",
    "create_unified_whatsapp_service",
]
