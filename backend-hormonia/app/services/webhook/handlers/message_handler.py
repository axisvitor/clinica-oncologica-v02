"""
Message webhook handler for Evolution API integration.
Processes incoming WhatsApp messages through the flow engine.
"""

import logging
from typing import Any, Optional, Dict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.config.settings.cache import cache_settings
from app.models.message import Message, MessageType, MessageStatus, MessageDirection
from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.domain.messaging.core import MessageService
from app.repositories.patient import PatientRepository
from app.repositories.flow import FlowStateRepository
from app.services.flow import FlowEngine

# NOTE: EnhancedFlowEngine imported lazily to avoid circular import
from app.services.websocket_events import websocket_events
from app.schemas.websocket import WebSocketEventType
from app.schemas.message import MessageCreate
from app.integrations.openai_client import get_langchain_orchestrator
from app.core.redis_unified import get_async_redis
from app.utils.db_retry import with_db_retry
from app.services.webhook.utils.phone_normalizer import PhoneNormalizer
from app.services.webhook.utils.message_extractor import extract_message_data

logger = logging.getLogger(__name__)


class MessageWebhookHandler:
    """
    Handler for incoming message webhooks from Evolution API.

    Responsibilities:
    1. Extract and validate message data
    2. Check idempotency (deduplicate by whatsapp_id)
    3. Find patient by phone number
    4. Create inbound message record
    5. Publish WebSocket events
    6. Route to flow or general chat handler
    """

    def __init__(self, db: Any):
        """
        Initialize message handler with required services.

        Args:
            db: Database session
        """
        self.db = db
        self.message_service = MessageService(db)
        self.patient_repo = PatientRepository(db)
        self.flow_engine = FlowEngine(db)
        # Lazy import to avoid circular dependency
        from app.services.enhanced_flow_engine import EnhancedFlowEngine

        self.enhanced_flow_engine = EnhancedFlowEngine(db)
        self.flow_state_repo = FlowStateRepository(db)
        self.ai_client = get_langchain_orchestrator()
        self.phone_normalizer = PhoneNormalizer(self.patient_repo)

        logger.info("MessageWebhookHandler initialized")

    @with_db_retry(max_retries=3)
    async def process_message(
        self, event_data: Dict[str, Any], webhook_store: Optional[Any] = None
    ) -> Optional[str]:
        """
        Process incoming message webhook from Evolution API.

        Args:
            event_data: Webhook event data
            webhook_store: Optional webhook persistence store

        Returns:
            Message ID if processed successfully, None otherwise
        """
        webhook_id = None
        try:
            # Step 0: Persist webhook event
            if webhook_store:
                webhook_id = await webhook_store.persist_event(
                    event_type="message.received",
                    source="evolution_api",
                    payload=event_data,
                )

            # Step 1: Extract message data
            message_data = extract_message_data(event_data)
            if not message_data:
                logger.warning("No valid message data found in webhook")
                if webhook_id and webhook_store:
                    await webhook_store.mark_processed(
                        webhook_id, False, "No valid message data"
                    )
                return None

            whatsapp_id = message_data["whatsapp_id"]

            # FIX: Validate whatsapp_id to prevent key collision with "None"
            if not whatsapp_id:
                logger.warning("WhatsApp ID is None or empty, skipping message")
                if webhook_id and webhook_store:
                    await webhook_store.mark_processed(
                        webhook_id, False, "Missing WhatsApp ID"
                    )
                return None

            # Step 2: Idempotency check via atomic SET NX + DB fallback
            # FIX: Use atomic SET NX BEFORE any database operation to prevent race conditions
            redis_client = await get_async_redis()
            idempotency_key = f"webhook:message:{whatsapp_id}"

            # First, try to atomically acquire processing lock
            acquired = await redis_client.set(
                idempotency_key,
                "processing",
                nx=True,  # Only set if doesn't exist
                ex=cache_settings.CACHE_WEBHOOK_IDEMPOTENCY_TTL_SECONDS
            )

            if not acquired:
                # Key exists - check if it's completed or still processing
                existing_value = await redis_client.get(idempotency_key)
                if existing_value:
                    existing_str = existing_value.decode() if isinstance(existing_value, bytes) else str(existing_value)
                    if existing_str != "processing":
                        # Already completed, return the message ID
                        logger.info(
                            f"Duplicate webhook message detected (Redis): {whatsapp_id}"
                        )
                        return existing_str
                    else:
                        # Another worker is processing, wait briefly and check DB
                        logger.info(
                            f"Message {whatsapp_id} being processed by another worker, checking DB"
                        )

            # DB fallback check (also catches race condition edge cases)
            existing_message = (
                self.db.query(Message)
                .filter(Message.whatsapp_id == whatsapp_id)
                .first()
            )

            if existing_message:
                logger.info(f"Duplicate webhook message detected (DB): {whatsapp_id}")
                # Update Redis with actual message ID
                await redis_client.set(
                    idempotency_key,
                    str(existing_message.id),
                    ex=cache_settings.CACHE_WEBHOOK_IDEMPOTENCY_TTL_SECONDS
                )
                return str(existing_message.id)

            # Step 3: Find patient with security monitoring
            patient = await self._find_patient_with_security(
                message_data, webhook_id, webhook_store
            )
            if not patient:
                return None

            # Step 4: Check flow status and add context
            active_flow = self.flow_state_repo.get_active_flow(patient.id)
            metadata = message_data.get("metadata", {})

            if active_flow:
                metadata["context"] = "flow"
                metadata["flow_state_id"] = str(active_flow.id)
                metadata["current_step"] = active_flow.current_step
            else:
                metadata["context"] = "general_chat"

            # Step 5: Create inbound message record
            message = self.message_service.process_inbound_message(
                patient_id=patient.id,
                content=message_data["content"],
                whatsapp_id=whatsapp_id,
                message_type=message_data["type"],
                message_metadata=metadata,
            )

            # FIX: Update Redis key with message ID (replacing "processing" value)
            # This marks the message as fully processed with its actual ID
            await redis_client.set(
                idempotency_key,
                str(message.id),
                ex=cache_settings.CACHE_WEBHOOK_IDEMPOTENCY_TTL_SECONDS
            )

            logger.info(
                f"Processed inbound message {message.id} from patient {patient.id}",
                extra={
                    "message_id": str(message.id),
                    "patient_id": str(patient.id),
                    "context": metadata["context"],
                },
            )

            # Step 6: Publish WebSocket event
            await self._publish_message_event(message, patient.id)

            # Step 7: Route to appropriate handler
            if active_flow:
                await self._handle_flow_message(patient, message, active_flow)
            else:
                await self._handle_general_chat(patient, message)

            # Step 8: Mark webhook as processed
            if webhook_id and webhook_store:
                await webhook_store.mark_processed(webhook_id, True)

            return str(message.id)

        except Exception as e:
            logger.error(f"Error processing message webhook: {e}", exc_info=True)
            if webhook_id and webhook_store:
                await webhook_store.mark_processed(webhook_id, False, str(e))
            return None

    async def _find_patient_with_security(
        self,
        message_data: Dict[str, Any],
        webhook_id: Optional[UUID],
        webhook_store: Optional[Any],
    ) -> Optional[Patient]:
        """
        Find patient by phone with security monitoring for unauthorized access.

        Args:
            message_data: Extracted message data
            webhook_id: Webhook event ID
            webhook_store: Webhook persistence store

        Returns:
            Patient or None if not found/blocked
        """
        phone = self.phone_normalizer.clean_phone_number(message_data["phone"])
        patient = self.phone_normalizer.find_patient_by_phone(phone)

        if patient:
            return patient

        # Patient not found - handle unauthorized access
        from app.services.security_monitor import SecurityMonitor

        security_monitor = SecurityMonitor(self.db)

        # Log unauthorized access attempt
        await security_monitor.log_unauthorized_access(
            phone=message_data["phone"],
            message_content=message_data["content"][:100],
            source_metadata={
                "whatsapp_id": message_data["whatsapp_id"],
                "timestamp": message_data.get("metadata", {}).get("timestamp"),
                "push_name": message_data.get("metadata", {}).get("pushName"),
            },
        )

        # Check if phone should be blocked
        should_block = await security_monitor.should_block_phone(message_data["phone"])
        if should_block:
            logger.warning(
                "Phone blocked due to repeated unauthorized attempts",
                extra={"phone": message_data["phone"][:6] + "****"},
            )
            if webhook_id and webhook_store:
                await webhook_store.mark_processed(
                    webhook_id, False, "Phone blocked - too many unauthorized attempts"
                )
            return None

        # Get attempt count and send appropriate response
        attempt_count = await security_monitor.get_attempt_count(message_data["phone"])

        logger.warning(
            f"Unauthorized access attempt (#{attempt_count})",
            extra={
                "phone": message_data["phone"][:6] + "****",
                "content_preview": message_data["content"][:30] + "...",
            },
        )

        # Send response only for first 3 attempts
        if attempt_count <= 3:
            await self._send_unauthorized_response(message_data["phone"], attempt_count)

        if webhook_id and webhook_store:
            await webhook_store.mark_processed(
                webhook_id,
                False,
                f"Unauthorized: patient not found (attempt {attempt_count})",
            )

        return None

    async def _handle_flow_message(
        self, patient: Patient, message: Message, flow_state: PatientFlowState
    ) -> None:
        """
        Handle message within active flow context.

        Args:
            patient: Patient record
            message: Inbound message
            flow_state: Active flow state
        """
        try:
            # Check for active quiz session
            from app.services.quiz import QuizSessionService

            quiz_session_service = QuizSessionService(self.db)
            active_quiz_session = quiz_session_service.get_active_session(patient.id)

            if active_quiz_session:
                logger.info(f"Routing message to quiz handler for patient {patient.id}")
                await self._handle_quiz_message(patient, message, active_quiz_session)
                return

            # Calculate current day
            current_day = await self.enhanced_flow_engine.calculate_patient_day(
                patient.id
            )

            # Process response through enhanced flow engine
            response = await self.enhanced_flow_engine.process_patient_response(
                patient_id=patient.id,
                response_text=message.content,
                current_day=current_day,
            )

            if response.get("should_advance"):
                advancement = await self.enhanced_flow_engine.advance_patient_flow(
                    patient_id=patient.id
                )
                logger.info(f"Flow advanced for patient {patient.id}: {advancement}")

            # Send response if available
            if response.get("ai_response"):
                await self._send_response(
                    patient_id=patient.id,
                    content=response["ai_response"],
                    metadata={
                        "context": "flow",
                        "flow_state_id": str(flow_state.id),
                        "current_day": current_day,
                        "response_to": str(message.id),
                    },
                )

        except Exception as e:
            logger.error(
                f"Error handling flow message for patient {patient.id}: {e}",
                exc_info=True,
            )

    async def _handle_quiz_message(
        self, patient: Patient, message: Message, quiz_session: Any
    ) -> None:
        """
        Handle message within active quiz context with debouncing.

        HIGH-005 FIX: Implements debouncing to prevent duplicate responses.

        Args:
            patient: Patient record
            message: Inbound message
            quiz_session: Active quiz session
        """
        try:
            from app.domain.quizzes.integration.flow_integration import (
                ConversationalQuizService,
            )
            from app.services.quiz_response_debounce import get_quiz_debouncer

            # HIGH-005 FIX: Check debounce before processing
            debouncer = get_quiz_debouncer(debounce_window_seconds=3)

            current_question_id = (
                quiz_session.current_question
                if hasattr(quiz_session, "current_question")
                and quiz_session.current_question
                else str(quiz_session.current_question_index)
                if hasattr(quiz_session, "current_question_index")
                else "unknown"
            )

            should_process = await debouncer.should_process_response(
                session_id=quiz_session.id,
                question_id=current_question_id,
                message_metadata={
                    "message_id": str(message.id),
                    "whatsapp_id": message.whatsapp_id,
                    "patient_id": str(patient.id),
                },
            )

            if not should_process:
                logger.info(
                    f"Quiz response debounced for patient {patient.id}",
                    extra={
                        "patient_id": str(patient.id),
                        "session_id": str(quiz_session.id),
                        "reason": "duplicate_within_3s_window",
                    },
                )
                return

            # Process quiz response
            quiz_service = ConversationalQuizService(self.db)
            result = await quiz_service.process_quiz_response(
                patient_id=patient.id,
                response_text=message.content,
                message_metadata={
                    "message_id": str(message.id),
                    "whatsapp_id": message.whatsapp_id,
                },
            )

            logger.info(
                f"Quiz response processed for patient {patient.id}: action={result.get('action')}"
            )

            # Handle result actions
            if result.get("action") == "quiz_completed":
                await debouncer.clear_debounce(quiz_session.id)
            elif result.get("action") == "request_clarification":
                await debouncer.clear_debounce(quiz_session.id, current_question_id)

        except Exception as e:
            logger.error(
                f"Error handling quiz message for patient {patient.id}: {e}",
                exc_info=True,
            )

    async def _handle_general_chat(self, patient: Patient, message: Message) -> None:
        """
        Handle general chat message (no active flow).

        Args:
            patient: Patient record
            message: Inbound message
        """
        try:
            # Get conversation history for context
            history = self.message_service.get_conversation_history(
                patient_id=patient.id, limit=10
            )
            conversation_history = [m.content for m in history if m.content]

            # Build patient context
            patient_context = {
                "patient_id": str(patient.id),
                "name": patient.name,
                "phone": patient.phone,
                "treatment_type": getattr(patient, "treatment_type", None),
                "diagnosis": getattr(patient, "diagnosis", None),
            }

            # Generate AI response
            ai_response = await self.ai_client.generate_contextual_response(
                patient_message=message.content,
                patient_context=patient_context,
                conversation_history=conversation_history,
            )

            # Send response
            await self._send_response(
                patient_id=patient.id,
                content=ai_response,
                metadata={"context": "general_chat", "response_to": str(message.id)},
            )

        except Exception as e:
            logger.error(
                f"Error handling general chat for patient {patient.id}: {e}",
                exc_info=True,
            )

    async def _send_response(
        self, patient_id: UUID, content: str, metadata: Dict[str, Any]
    ) -> Optional[Message]:
        """
        Create and send response message.

        FIX P0-2: Creates ONE message, then schedules it.

        Args:
            patient_id: Patient ID
            content: Response content
            metadata: Message metadata

        Returns:
            Created message or None
        """
        try:
            # Step 1: Create outbound message
            response_data = MessageCreate(
                patient_id=patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=content,
                message_metadata=metadata,
                status=MessageStatus.PENDING,
            )

            response_message = self.message_service.create_message(response_data)
            logger.info(
                f"Created message {response_message.id} for patient {patient_id}"
            )

            # Step 2: Publish WebSocket event
            await self._publish_message_event(response_message, patient_id)

            # Step 3: Schedule for delivery
            from app.domain.messaging.scheduling import MessageScheduler

            scheduler = MessageScheduler(self.db)

            send_time = datetime.now(timezone.utc) + timedelta(seconds=1)
            await scheduler.schedule_existing_message(
                message_id=response_message.id, send_time=send_time, priority="high"
            )

            logger.info(f"Scheduled message {response_message.id} for delivery")
            return response_message

        except Exception as e:
            logger.error(f"Error sending response: {e}", exc_info=True)
            try:
                self.db.rollback()
            except Exception as rollback_error:
                logger.error(
                    f"Failed to rollback transaction after error: {rollback_error}",
                    exc_info=True,
                )
            return None

    async def _send_unauthorized_response(
        self, phone: str, attempt_count: int = 1
    ) -> None:
        """
        Send escalating unauthorized messages to non-registered numbers.

        Args:
            phone: Phone number
            attempt_count: Number of attempts (1-3)
        """
        try:
            from app.integrations.evolution import get_evolution_client

            client = await get_evolution_client()
            if not client:
                logger.warning("Evolution client unavailable")
                return

            # Escalating messages based on attempt count
            messages = {
                1: (
                    "Olá! Este número não está cadastrado no sistema de acompanhamento da clínica. "
                    "Para informações sobre cadastro, entre em contato com a recepção pelos telefones oficiais."
                ),
                2: (
                    "ATENÇÃO: Este número não tem autorização para acessar o sistema da clínica. "
                    "Se você é paciente, verifique se está usando o número correto cadastrado."
                ),
                3: (
                    "ALERTA DE SEGURANÇA: Múltiplas tentativas de acesso não autorizado detectadas. "
                    "Este número será temporariamente bloqueado."
                ),
            }

            message = messages.get(attempt_count, messages[3])
            delay = min(1000 * attempt_count, 5000)

            await client.send_text_message(phone, message, delay=delay)

            logger.info(
                f"Sent unauthorized response (attempt #{attempt_count})",
                extra={"phone": phone[:6] + "****", "attempt": attempt_count},
            )

        except Exception as e:
            logger.error(f"Failed to send unauthorized response: {e}")

    async def _publish_message_event(self, message: Message, patient_id: UUID) -> None:
        """
        Publish WebSocket event for message.

        Args:
            message: Message to publish
            patient_id: Patient ID
        """
        await websocket_events.publish_message_event(
            event_type=WebSocketEventType.NEW_MESSAGE,
            message_id=message.id,
            patient_id=patient_id,
            direction=message.direction.value,
            message_type=message.type.value,
            content=message.content,
            whatsapp_id=message.whatsapp_id,
            metadata=message.metadata,
        )
