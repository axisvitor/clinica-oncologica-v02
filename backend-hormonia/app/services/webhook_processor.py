"""
Webhook processor for Evolution API integration.
Handles incoming messages from WhatsApp and processes them through the flow engine.
"""
import logging
import hashlib
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
from uuid import UUID, uuid4
# from sqlalchemy.orm import
from sqlalchemy.exc import IntegrityError
import redis.asyncio as redis

from app.config.settings.cache import cache_settings
from app.models.message import Message, MessageType, MessageStatus, MessageDirection
from app.models.patient import Patient
from app.models.flow import PatientFlowState, FlowKind, FlowTemplateVersion
from app.domain.messaging.core import MessageService
from app.repositories.patient import PatientRepository
from app.services.flow import FlowEngine
from app.services.enhanced_flow_engine import EnhancedFlowEngine
from app.services.websocket_events import websocket_events
from app.schemas.websocket import WebSocketEventType
from app.schemas.message import MessageCreate
from app.integrations.openai_client import get_langchain_orchestrator, OpenAIClientError
from app.integrations.evolution import WebhookEvent
from app.repositories.connection_state import ConnectionStateRepository
from app.repositories.flow import FlowStateRepository
from app.exceptions import ValidationError, NotFoundError
from app.utils.db_retry import with_db_retry
from app.core.redis_unified import get_async_redis

logger = logging.getLogger(__name__)


class WebhookProcessor:
    """
    Process webhooks from Evolution API for WhatsApp messages.

    Responsibilities:
    1. Normalize and validate incoming webhook data
    2. Find or create patient based on phone number
    3. Create inbound message record
    4. Publish WebSocket events
    5. Route to appropriate handler (Flow Engine or General Chat)
    6. Generate and send responses
    """

    def __init__(
        self,
        db: Any,
        connection_state_repository: Optional[ConnectionStateRepository] = None,
    ):
        """
        Initialize webhook processor with required services.

        Args:
            db: Database session
            connection_state_repository: Optional connection state repository
        """
        self.db = db
        self.message_service = MessageService(db)
        self.patient_repo = PatientRepository(db)
        self.flow_engine = FlowEngine(db)
        self.enhanced_flow_engine = EnhancedFlowEngine(db)
        self.flow_state_repo = FlowStateRepository(db)
        self.ai_client = get_langchain_orchestrator()
        self.connection_state_repo = (
            connection_state_repository or ConnectionStateRepository()
        )

        logger.info("WebhookProcessor initialized")

    @with_db_retry(max_retries=3)
    async def process_message_webhook(self, event_data: dict[str, Any]) -> Optional[str]:
        """
        Process incoming message webhook from Evolution API.

        Flow:
        1. Persist webhook event to database (P0 FIX #2)
        2. Extract and validate message data
        3. Check idempotency (deduplicate by whatsapp_id)
        4. Find patient by phone number
        5. Create inbound message record
        6. Publish WebSocket event
        7. Check for active flow
        8. Route to flow processing or general chat
        9. Generate and send response

        Args:
            event_data: Webhook event data from Evolution API

        Returns:
            Message ID if processed successfully, None otherwise
        """
        webhook_id = None
        try:
            # Step 0: Persist webhook event first (P0 FIX #2)
            webhook_id = await self._persist_webhook_event(
                event_type="message.received",
                source="evolution_api",
                payload=event_data
            )

            # Step 1: Extract message data from webhook
            message_data = self._extract_message_data(event_data)
            if not message_data:
                logger.warning("No valid message data found in webhook")
                if webhook_id:
                    await self._mark_webhook_processed(webhook_id, False, "No valid message data")
                return None

            whatsapp_id = message_data["whatsapp_id"]

            # Step 2: Idempotency check via Redis (fast path) + DB fallback
            redis_client = await get_async_redis()
            idempotency_key = f"webhook:message:{whatsapp_id}"

            # Try Redis first (fast)
            is_duplicate = await redis_client.exists(idempotency_key)
            if is_duplicate:
                logger.info(f"Duplicate webhook message detected (Redis): {whatsapp_id}")
                # Return existing message_id if stored
                existing_id = await redis_client.get(idempotency_key)
                return existing_id.decode() if existing_id else None

            # DB fallback: check if whatsapp_id already exists
            existing_message = self.db.query(Message).filter(
                Message.whatsapp_id == whatsapp_id
            ).first()

            if existing_message:
                logger.info(f"Duplicate webhook message detected (DB): {whatsapp_id}")
                # Cache in Redis for future fast-path
                await redis_client.setex(
                    idempotency_key,
                    cache_settings.WEBHOOK_IDEMPOTENCY_TTL,
                    str(existing_message.id)
                )
                return str(existing_message.id)

            # Step 3: Enhanced patient validation with security monitoring
            patient = self._find_patient_by_phone(message_data["phone"])
            if not patient:
                # Import security monitor for tracking unauthorized access
                from app.services.security_monitor import SecurityMonitor
                security_monitor = SecurityMonitor(self.db)

                # Log and track unauthorized access attempt
                await security_monitor.log_unauthorized_access(
                    phone=message_data["phone"],
                    message_content=message_data["content"][:100],  # First 100 chars for analysis
                    source_metadata={
                        "whatsapp_id": message_data["whatsapp_id"],
                        "timestamp": message_data.get("metadata", {}).get("timestamp"),
                        "push_name": message_data.get("metadata", {}).get("pushName")
                    }
                )

                # Check if phone should be blocked (too many attempts)
                should_block = await security_monitor.should_block_phone(message_data["phone"])
                if should_block:
                    logger.warning(
                        f"Phone {message_data['phone']} blocked due to repeated unauthorized attempts"
                    )
                    if webhook_id:
                        await self._mark_webhook_processed(
                            webhook_id, False, "Phone blocked - too many unauthorized attempts"
                        )
                    return None

                # Get attempt count for rate limiting
                attempt_count = await security_monitor.get_attempt_count(message_data["phone"])

                logger.warning(
                    f"Unauthorized access attempt from {message_data['phone']} "
                    f"(attempt #{attempt_count}). Content: {message_data['content'][:50]}..."
                )

                # Send response only for first 3 attempts with escalating messages
                if attempt_count <= 3:
                    await self._send_unauthorized_response(
                        message_data["phone"],
                        attempt_count=attempt_count
                    )

                # Mark webhook as processed with enhanced failure info
                if webhook_id:
                    await self._mark_webhook_processed(
                        webhook_id, False,
                        f"Unauthorized: patient not found (attempt {attempt_count}, blocked={should_block})"
                    )

                return None

            # Step 4: Check flow status and add context
            active_flow = self.flow_state_repo.get_active_flow(patient.id)
            metadata = message_data.get("metadata", {})

            if active_flow:
                # Get flow type for context
                flow_type = self._get_flow_type_from_state(active_flow)
                metadata["context"] = "flow"
                metadata["flow_type"] = flow_type
                metadata["flow_state_id"] = str(active_flow.id)
                metadata["current_step"] = active_flow.current_step
            else:
                metadata["context"] = "general_chat"

            # Step 5: Create inbound message record
            message = self.message_service.process_inbound_message(
                patient_id=patient.id,
                content=message_data["content"],
                whatsapp_id=message_data["whatsapp_id"],
                message_type=message_data["type"],
                message_metadata=metadata,
            )

            # Cache message_id in Redis for idempotency
            await redis_client.setex(
                idempotency_key,
                cache_settings.WEBHOOK_IDEMPOTENCY_TTL,
                str(message.id)
            )

            logger.info(
                f"Processed inbound message {message.id} from patient {patient.id} "
                f"(context: {metadata['context']})"
            )

            # Step 6: Publish WebSocket event for UI updates
            await self._publish_message_event(message, patient.id)

            # Step 7: Route to appropriate handler
            if active_flow:
                await self._handle_flow_message(patient, message, active_flow)
            else:
                await self._handle_general_chat(patient, message)

            # Step 8: Mark webhook as processed (P0 FIX #2)
            if webhook_id:
                await self._mark_webhook_processed(webhook_id, True)

            return str(message.id)

        except Exception as e:
            logger.error(f"Error processing message webhook: {e}", exc_info=True)
            if webhook_id:
                await self._mark_webhook_processed(webhook_id, False, str(e))
            return None

    @with_db_retry(max_retries=3)
    async def process_status_webhook(self, event_data: dict[str, Any]) -> bool:
        """
        Process message status update webhook (delivered, read, etc).

        P0 FIX #2: Now persists webhook event to database.

        Args:
            event_data: Webhook event data

        Returns:
            True if processed successfully
        """
        webhook_id = None
        try:
            # Persist webhook event first (P0 FIX #2)
            webhook_id = await self._persist_webhook_event(
                event_type="message.status",
                source="evolution_api",
                payload=event_data
            )

            # Extract status data
            whatsapp_id = event_data.get("key", {}).get("id")
            status = event_data.get("update", {}).get("status")

            if not whatsapp_id or not status:
                logger.warning("Missing required fields in status webhook")
                if webhook_id:
                    await self._mark_webhook_processed(webhook_id, False, "Missing required fields")
                return False

            # Idempotency check
            redis_client = await get_async_redis()
            idempotency_key = f"webhook:status:{whatsapp_id}:{status}"
            
            is_duplicate = await redis_client.exists(idempotency_key)
            if is_duplicate:
                logger.info(f"Duplicate status webhook detected: {whatsapp_id} -> {status}")
                if webhook_id:
                    await self._mark_webhook_processed(webhook_id, True, "Duplicate status event")
                return True

            # Update message status
            message = self.message_service.update_message_status_by_whatsapp_id(
                whatsapp_id=whatsapp_id,
                status=self._map_evolution_status(status)
            )

            if message:
                # Publish WebSocket event for status update
                await websocket_events.publish_message_event(
                    event_type=WebSocketEventType.MESSAGE_STATUS_UPDATED,
                    message_id=message.id,
                    patient_id=message.patient_id,
                    direction=message.direction.value,
                    message_type=message.type.value,
                    status=message.status.value,
                    metadata={"whatsapp_id": whatsapp_id}
                )

                logger.info(f"Updated message {message.id} status to {status}")

                # Cache status update in Redis
                await redis_client.setex(
                    idempotency_key,
                    cache_settings.WEBHOOK_IDEMPOTENCY_TTL,
                    "1"
                )

                # Mark webhook as processed (P0 FIX #2)
                if webhook_id:
                    await self._mark_webhook_processed(webhook_id, True)
                return True

            logger.warning(f"Message not found for WhatsApp ID: {whatsapp_id}")
            if webhook_id:
                await self._mark_webhook_processed(webhook_id, False, "Message not found")
            return False

        except Exception as e:
            logger.error(f"Error processing status webhook: {e}", exc_info=True)
            if webhook_id:
                await self._mark_webhook_processed(webhook_id, False, str(e))
            return False

    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================

    async def _handle_flow_message(
        self,
        patient: Patient,
        message: Message,
        flow_state: PatientFlowState
    ) -> None:
        """
        Handle message within active flow context.

        Args:
            patient: Patient record
            message: Inbound message
            flow_state: Active flow state
        """
        try:
            # Check if patient has an active quiz session
            from app.services.quiz import QuizSessionService
            quiz_session_service = QuizSessionService(self.db)
            active_quiz_session = quiz_session_service.get_active_session(patient.id)

            if active_quiz_session:
                # Route to conversational quiz handler
                logger.info(f"Routing message to quiz handler for patient {patient.id}")
                await self._handle_quiz_message(patient, message, active_quiz_session)
                return

            # Calculate current day
            current_day = await self.enhanced_flow_engine.calculate_patient_day(patient.id)

            # Process response through enhanced flow engine
            response = await self.enhanced_flow_engine.process_patient_response(
                patient_id=patient.id,
                response_text=message.content,
                current_day=current_day
            )

            if response.get("should_advance"):
                # Advance flow if needed
                advancement = await self.enhanced_flow_engine.advance_patient_flow(
                    patient_id=patient.id
                )
                logger.info(f"Flow advanced for patient {patient.id}: {advancement}")

            # Generate and send response if available
            if response.get("ai_response"):
                await self._send_response(
                    patient_id=patient.id,
                    content=response["ai_response"],
                    metadata={
                        "context": "flow",
                        "flow_state_id": str(flow_state.id),
                        "current_day": current_day,
                        "response_to": str(message.id)
                    }
                )

        except Exception as e:
            logger.error(
                f"Error handling flow message for patient {patient.id}: {e}",
                exc_info=True
            )

    async def _handle_quiz_message(
        self,
        patient: Patient,
        message: Message,
        quiz_session: Any
    ) -> None:
        """
        Handle message within active quiz context.

        HIGH-005 FIX: Implements debouncing to prevent duplicate quiz responses
        from rapid messages within a 3-second window.

        Args:
            patient: Patient record
            message: Inbound message
            quiz_session: Active quiz session
        """
        try:
            from app.domain.quizzes.integration.flow_integration import ConversationalQuizService
            from app.services.quiz_response_debounce import get_quiz_debouncer

            # HIGH-005 FIX: Check debounce before processing
            debouncer = get_quiz_debouncer(debounce_window_seconds=3)

            # Get current question ID from session
            current_question_id = (
                quiz_session.current_question
                if hasattr(quiz_session, 'current_question') and quiz_session.current_question
                else str(quiz_session.current_question_index) if hasattr(quiz_session, 'current_question_index')
                else "unknown"
            )

            # Check if we should process this response (debounce check)
            should_process = await debouncer.should_process_response(
                session_id=quiz_session.id,
                question_id=current_question_id,
                message_metadata={
                    'message_id': str(message.id),
                    'whatsapp_id': message.whatsapp_id,
                    'timestamp': message.timestamp.isoformat() if message.timestamp else None,
                    'patient_id': str(patient.id)
                }
            )

            if not should_process:
                # Message is within debounce window - ignore
                logger.info(
                    f"Quiz response debounced for patient {patient.id}",
                    extra={
                        "patient_id": str(patient.id),
                        "session_id": str(quiz_session.id),
                        "question_id": current_question_id,
                        "message_id": str(message.id),
                        "whatsapp_id": message.whatsapp_id,
                        "debounce_reason": "duplicate_within_3s_window"
                    }
                )
                return

            # Process quiz response (not debounced)
            quiz_service = ConversationalQuizService(self.db)

            result = await quiz_service.process_quiz_response(
                patient_id=patient.id,
                response_text=message.content,
                message_metadata={
                    'message_id': str(message.id),
                    'timestamp': message.timestamp,
                    'whatsapp_id': message.whatsapp_id
                }
            )

            logger.info(
                f"Quiz response processed for patient {patient.id}: "
                f"action={result.get('action')}, success={result.get('success')}"
            )

            # Handle result actions
            if result.get('action') == 'quiz_completed':
                logger.info(f"Quiz completed for patient {patient.id}")
                # Clear all debounce state for session on completion
                await debouncer.clear_debounce(quiz_session.id)
            elif result.get('action') == 'next_question':
                logger.info(f"Advanced to next question for patient {patient.id}")
                # Debounce state automatically expires, no need to clear
            elif result.get('action') == 'request_clarification':
                logger.info(f"Clarification requested for patient {patient.id}")
                # Clear debounce to allow immediate retry
                await debouncer.clear_debounce(quiz_session.id, current_question_id)

        except Exception as e:
            logger.error(
                f"Error handling quiz message for patient {patient.id}: {e}",
                exc_info=True
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
                patient_id=patient.id,
                limit=10
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
                conversation_history=conversation_history
            )

            # Send response
            await self._send_response(
                patient_id=patient.id,
                content=ai_response,
                metadata={
                    "context": "general_chat",
                    "response_to": str(message.id)
                }
            )

        except Exception as e:
            logger.error(
                f"Error handling general chat for patient {patient.id}: {e}",
                exc_info=True
            )

    async def _send_response(
        self,
        patient_id: UUID,
        content: str,
        metadata: Dict[str, Any]
    ) -> Optional[Message]:
        """
        Create and send response message.

        FIX P0-2: Creates ONE message only, then schedules it using schedule_existing_message().
        This prevents ghost message duplication where UI shows Message #1 but scheduler works on Message #2.

        Flow:
        1. Create single message with PENDING status
        2. Persist to database
        3. Publish via WebSocket (UI shows this message)
        4. Schedule the SAME message using schedule_existing_message()
        5. Status transitions: PENDING → SCHEDULED → SENT/DELIVERED

        Args:
            patient_id: Patient ID
            content: Response content
            metadata: Message metadata

        Returns:
            Created message or None
        """
        try:
            # Step 1: Create ONE outbound message with PENDING status
            response_data = MessageCreate(
                patient_id=patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=content,
                message_metadata=metadata,
                status=MessageStatus.PENDING  # Explicit PENDING status
            )

            # Step 2: Persist to database
            response_message = self.message_service.create_message(response_data)
            logger.info(f"Created message {response_message.id} for patient {patient_id}")

            # Step 3: Publish WebSocket event (UI will show this message)
            await self._publish_message_event(response_message, patient_id)
            logger.debug(f"Published WebSocket event for message {response_message.id}")

            # Step 4: Schedule the SAME message for immediate delivery
            # Import MessageScheduler
            from app.domain.messaging.scheduling import MessageScheduler
            scheduler = MessageScheduler(self.db)

            # Schedule the existing message (status: PENDING → SCHEDULED)
            send_time = datetime.utcnow() + timedelta(seconds=1)  # Send almost immediately
            scheduling_success = await scheduler.schedule_existing_message(
                message_id=response_message.id,
                send_time=send_time,
                priority='high'  # Auto-responses are high priority
            )

            if scheduling_success:
                logger.info(
                    f"Successfully scheduled message {response_message.id} for delivery at {send_time.isoformat()}"
                )
            else:
                logger.error(
                    f"Failed to schedule message {response_message.id}, status remains PENDING"
                )
                # Message stays in PENDING state, can be picked up by retry mechanisms

            return response_message

        except Exception as e:
            logger.error(f"Error sending response: {e}", exc_info=True)
            # Rollback on failure to maintain consistency
            try:
                self.db.rollback()
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}", exc_info=True)
            return None

    async def _send_unauthorized_response(self, phone: str, attempt_count: int = 1) -> None:
        """
        Send escalating unauthorized messages to non-registered numbers.

        Enhanced security implementation with escalating responses:
        - Different messages based on attempt count
        - Clear instructions for legitimate users
        - Security warnings for repeated attempts
        - Fails silently if Evolution API is unavailable

        Args:
            phone: Phone number that attempted access
            attempt_count: Number of unauthorized attempts (1-3)
        """
        try:
            from app.integrations.evolution import get_evolution_client

            # Get Evolution client
            client = await get_evolution_client()
            if not client:
                logger.warning(f"Evolution client unavailable, cannot send unauthorized response to {phone}")
                return

            # Escalating messages based on attempt count
            if attempt_count == 1:
                message = (
                    "Olá! Este número não está cadastrado no sistema de acompanhamento da clínica. "
                    "Para informações sobre cadastro, entre em contato com a recepção pelos telefones oficiais."
                )
            elif attempt_count == 2:
                message = (
                    "ATENÇÃO: Este número não tem autorização para acessar o sistema da clínica. "
                    "Se você é paciente, verifique se está usando o número correto cadastrado. "
                    "Contate a recepção se precisar atualizar seus dados."
                )
            else:  # attempt_count >= 3
                message = (
                    "ALERTA DE SEGURANÇA: Múltiplas tentativas de acesso não autorizado detectadas. "
                    "Este número será temporariamente bloqueado. "
                    "Entre em contato com a clínica pelos canais oficiais se esta for uma tentativa legítima."
                )

            # Send message with increasing delay to rate limit aggressive attempts
            delay = min(1000 * attempt_count, 5000)  # 1s, 2s, 3s+ (max 5s)
            await client.send_text_message(phone, message, delay=delay)

            logger.info(
                f"Sent unauthorized response (attempt #{attempt_count}) to {phone}. "
                f"Message type: {'warning' if attempt_count > 1 else 'info'}"
            )

        except Exception as e:
            # Fail silently but log for security monitoring
            logger.error(
                f"Failed to send unauthorized response to {phone} (attempt #{attempt_count}): {e}"
            )

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
            metadata=message.metadata
        )

    def _extract_message_data(self, event_data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """
        Extract relevant message data from Evolution API webhook.

        Args:
            event_data: Raw webhook event data

        Returns:
            Extracted message data or None if invalid
        """
        try:
            data = event_data.get("data", {})

            # Check for required fields
            if not data.get("message") or not data.get("key"):
                return None

            message = data["message"]
            key = data["key"]

            # Extract phone number from remoteJid
            remote_jid = key.get("remoteJid", "")
            phone = self._clean_phone_number(remote_jid)

            if not phone:
                return None

            # Extract message content
            content = None
            message_type = MessageType.TEXT

            if "extendedTextMessage" in message:
                content = message["extendedTextMessage"].get("text")
            elif "conversation" in message:
                content = message["conversation"]
            elif "imageMessage" in message:
                content = message["imageMessage"].get("caption", "[Image]")
                message_type = MessageType.IMAGE
            elif "audioMessage" in message:
                content = "[Audio message]"
                message_type = MessageType.AUDIO

            if not content:
                return None

            return {
                "phone": phone,
                "content": content,
                "type": message_type,
                "whatsapp_id": key.get("id"),
                "metadata": {
                    "from_me": key.get("fromMe", False),
                    "timestamp": message.get("messageTimestamp"),
                    "pushName": data.get("pushName"),
                }
            }

        except Exception as e:
            logger.error(f"Error extracting message data: {e}")
            return None

    def _normalize_phone_e164(self, phone: str) -> str:
        """
        Normalize phone number to E.164 format (+55...).

        Args:
            phone: Raw phone number (may have +, 55, or neither)

        Returns:
            E.164 formatted phone (+55...)
        """
        # Remove all non-digit characters except +
        cleaned = "".join(c for c in phone if c.isdigit() or c == "+")

        # Remove leading zeros
        cleaned = cleaned.lstrip("0")

        # If already has +, return as-is
        if cleaned.startswith("+"):
            return cleaned

        # If starts with country code (55), add +
        if cleaned.startswith("55"):
            return f"+{cleaned}"

        # Otherwise, assume Brazilian number and add +55
        return f"+55{cleaned}"

    def _find_patient_by_phone(self, phone: str) -> Optional[Patient]:
        """
        Find patient by phone number with E.164 normalization and fallback strategies.

        Tries multiple formats for maximum compatibility:
        1. E.164 format with + prefix (+55...)
        2. Without + prefix (55...)
        3. Add country code if missing (+55{phone})
        4. Remove country code (last 10-11 digits)

        Args:
            phone: Cleaned phone number (from _clean_phone_number)

        Returns:
            Patient or None if not found
        """
        try:
            # Strategy 1: Normalize to E.164 and try with +
            normalized = self._normalize_phone_e164(phone)
            logger.info(f"Phone lookup attempt 1: E.164 format '{normalized}'")
            patient = self.patient_repo.get_by_phone(normalized)
            if patient:
                logger.info(f"Patient found with E.164 format: {normalized}")
                return patient

            # Strategy 2: Try without + prefix
            without_plus = normalized.lstrip("+")
            logger.info(f"Phone lookup attempt 2: Without + prefix '{without_plus}'")
            patient = self.patient_repo.get_by_phone(without_plus)
            if patient:
                logger.info(f"Patient found without + prefix: {without_plus}")
                return patient
                local_10 = without_plus[-10:]

                logger.info(f"Phone lookup attempt 5: Local 11 digits '{local_11}'")
                patient = self.patient_service.get_by_phone(local_11)
                if patient:
                    logger.info(f"Patient found with local 11 digits: {local_11}")
                    return patient

                logger.info(f"Phone lookup attempt 6: Local 10 digits '{local_10}'")
                patient = self.patient_service.get_by_phone(local_10)
                if patient:
                    logger.info(f"Patient found with local 10 digits: {local_10}")
                    return patient

            logger.warning(
                f"Patient not found after all phone lookup strategies. "
                f"Original: {phone}, Normalized: {normalized}, Tried: "
                f"[{normalized}, {without_plus}, +55{phone}, 55{phone}]"
            )
            return None

        except Exception as e:
            logger.error(f"Error finding patient by phone {phone}: {e}", exc_info=True)
            return None

    def _clean_phone_number(self, phone: str) -> str:
        """
        Clean and normalize phone number from WhatsApp format.

        Preserves + prefix for E.164 format compatibility.
        WhatsApp sends numbers like: "5511987654321@s.whatsapp.net"

        Args:
            phone: Raw phone number from WhatsApp (e.g., "5511987654321@s.whatsapp.net")

        Returns:
            Cleaned phone number with + prefix if valid (e.g., "+5511987654321")
        """
        # Remove @s.whatsapp.net suffix
        if "@" in phone:
            phone = phone.split("@")[0]

        # Remove non-digit characters except +
        cleaned = "".join(c for c in phone if c.isdigit() or c == "+")

        # Remove leading zeros (but preserve +)
        if cleaned.startswith("+"):
            # Keep the +, remove zeros after it
            cleaned = "+" + cleaned[1:].lstrip("0")
        else:
            cleaned = cleaned.lstrip("0")

        logger.debug(f"Phone number cleaned: '{phone}' -> '{cleaned}'")
        return cleaned

    def _get_flow_type_from_state(self, flow_state: PatientFlowState) -> str:
        """
        Get flow type from flow state using template version.

        Args:
            flow_state: Patient flow state

        Returns:
            Flow type string
        """
        try:
            template_version = self.db.query(FlowTemplateVersion).filter(
                FlowTemplateVersion.id == flow_state.template_version_id
            ).first()

            if not template_version:
                return "unknown"

            flow_kind = self.db.query(FlowKind).filter(
                FlowKind.id == template_version.kind_id
            ).first()

            return flow_kind.flow_type if flow_kind else "unknown"

        except Exception as e:
            logger.error(f"Error getting flow type: {e}")
            return "unknown"

    def _map_evolution_status(self, evolution_status: str) -> MessageStatus:
        """
        Map Evolution API status to internal MessageStatus.

        Args:
            evolution_status: Status from Evolution API

        Returns:
            Internal MessageStatus enum
        """
        status_mapping = {
            "PENDING": MessageStatus.PENDING,
            "SENT": MessageStatus.SENT,
            "DELIVERED": MessageStatus.DELIVERED,
            "READ": MessageStatus.READ,
            "FAILED": MessageStatus.FAILED,
            "ERROR": MessageStatus.FAILED,
        }

        return status_mapping.get(
            evolution_status.upper(),
            MessageStatus.PENDING
        )

    # =========================================================================
    # P0 FIXES: WEBHOOK PERSISTENCE, CONNECTION HANDLER, QR CODE, RETRY
    # =========================================================================

    async def _persist_webhook_event(
        self,
        event_type: str,
        source: str,
        payload: Dict[str, Any],
        related_message_id: Optional[UUID] = None,
        related_patient_id: Optional[UUID] = None
    ) -> Optional[UUID]:
        """
        P0 FIX #2: Persist webhook event to database for audit trail and retry.

        Args:
            event_type: Type of webhook event (e.g., 'message.received', 'connection.update')
            source: Source of webhook (e.g., 'evolution_api')
            payload: Raw webhook payload
            related_message_id: Optional related message ID
            related_patient_id: Optional related patient ID

        Returns:
            UUID of created webhook event, or None if failed
        """
        try:
            # Import WebhookEvent model from the correct location
            from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, text
            from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
            from app.models.base import Base

            # Generate event hash for idempotency
            payload_str = str(sorted(payload.items()))
            event_hash = hashlib.sha256(payload_str.encode()).hexdigest()

            # Check if event already exists (idempotency via event_hash)
            from sqlalchemy import select
            stmt = text("""
                SELECT id FROM webhook_events
                WHERE event_hash = :event_hash
                LIMIT 1
            """)
            result = self.db.execute(stmt, {"event_hash": event_hash}).fetchone()

            if result:
                logger.info(f"Duplicate webhook event detected via hash: {event_hash}")
                return UUID(result[0]) if result[0] else None

            # Create new webhook event record
            event_id = uuid4()
            insert_stmt = text("""
                INSERT INTO webhook_events (
                    id, event_type, source, payload, processed, retry_count, max_retries,
                    related_message_id, related_patient_id, event_hash, is_duplicate,
                    created_at
                )
                VALUES (
                    :id, :event_type, :source, :payload, :processed, :retry_count, :max_retries,
                    :related_message_id, :related_patient_id, :event_hash, :is_duplicate,
                    NOW()
                )
                RETURNING id
            """)

            result = self.db.execute(insert_stmt, {
                "id": str(event_id),
                "event_type": event_type,
                "source": source,
                "payload": payload,
                "processed": False,
                "retry_count": 0,
                "max_retries": 3,
                "related_message_id": str(related_message_id) if related_message_id else None,
                "related_patient_id": str(related_patient_id) if related_patient_id else None,
                "event_hash": event_hash,
                "is_duplicate": False
            })

            self.db.commit()

            logger.info(
                f"Persisted webhook event: {event_id} "
                f"(type={event_type}, source={source}, hash={event_hash[:8]}...)"
            )

            return event_id

        except IntegrityError as e:
            self.db.rollback()
            logger.warning(f"Duplicate webhook event (integrity error): {e}")
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to persist webhook event: {e}", exc_info=True)
            return None

    async def _mark_webhook_processed(
        self,
        event_id: UUID,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """
        Mark webhook event as processed.

        Args:
            event_id: Webhook event ID
            success: Whether processing succeeded
            error_message: Optional error message if failed
        """
        try:
            update_stmt = text("""
                UPDATE webhook_events
                SET processed = :processed,
                    processed_at = NOW(),
                    error_message = :error_message
                WHERE id = :event_id
            """)

            self.db.execute(update_stmt, {
                "event_id": str(event_id),
                "processed": success,
                "error_message": error_message
            })
            self.db.commit()

            logger.debug(f"Marked webhook {event_id} as processed (success={success})")

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to mark webhook as processed: {e}")

    @with_db_retry(max_retries=3)
    async def process_connection_webhook(self, event_data: dict[str, Any]) -> bool:
        """
        P0 FIX #3: Process connection status webhook (connection.update events).

        Handles WhatsApp instance connection state changes:
        - open: Instance is connected
        - close: Instance disconnected
        - connecting: Instance is connecting

        Args:
            event_data: Webhook event data

        Returns:
            True if processed successfully
        """
        try:
            # Persist webhook event first
            webhook_id = await self._persist_webhook_event(
                event_type="connection.update",
                source="evolution_api",
                payload=event_data
            )

            # Extract connection data
            instance = event_data.get("instance")
            state = event_data.get("state") or event_data.get("data", {}).get("state")

            if not instance or not state:
                logger.warning("Missing instance or state in connection webhook")
                if webhook_id:
                    await self._mark_webhook_processed(webhook_id, False, "Missing required fields")
                return False

            # Update connection state in Redis
            await self.connection_state_repo.set_state(instance, state)

            logger.info(
                f"Updated connection state for instance '{instance}': {state}",
                extra={"instance": instance, "state": state}
            )

            # Mark webhook as processed
            if webhook_id:
                await self._mark_webhook_processed(webhook_id, True)

            return True

        except Exception as e:
            logger.error(f"Error processing connection webhook: {e}", exc_info=True)
            if webhook_id:
                await self._mark_webhook_processed(webhook_id, False, str(e))
            return False

    @with_db_retry(max_retries=3)
    async def process_qrcode_webhook(self, event_data: dict[str, Any]) -> bool:
        """
        P0 FIX #5: Process QR code webhook (qrcode.updated events).

        Stores QR code data in connection state metadata for UI display.

        Args:
            event_data: Webhook event data containing QR code

        Returns:
            True if processed successfully
        """
        try:
            # Persist webhook event
            webhook_id = await self._persist_webhook_event(
                event_type="qrcode.updated",
                source="evolution_api",
                payload=event_data
            )

            # Extract QR code data
            instance = event_data.get("instance")
            qr_code = event_data.get("qrcode") or event_data.get("data", {}).get("qrcode")

            if not instance:
                logger.warning("Missing instance in QR code webhook")
                if webhook_id:
                    await self._mark_webhook_processed(webhook_id, False, "Missing instance")
                return False

            # Store QR code in Redis with metadata
            redis_client = await get_async_redis()
            qr_key = f"qrcode:{instance}"
            qr_data = {
                "instance": instance,
                "qrcode": qr_code,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "pending"
            }

            # Store with QR code TTL (QR codes expire quickly)
            await redis_client.setex(
                qr_key,
                cache_settings.QRCODE_TTL,
                str(qr_data)
            )

            logger.info(
                f"Stored QR code for instance '{instance}'",
                extra={"instance": instance, "has_qrcode": bool(qr_code)}
            )

            # Mark webhook as processed
            if webhook_id:
                await self._mark_webhook_processed(webhook_id, True)

            return True

        except Exception as e:
            logger.error(f"Error processing QR code webhook: {e}", exc_info=True)
            if webhook_id:
                await self._mark_webhook_processed(webhook_id, False, str(e))
            return False

    async def retry_failed_webhooks(self) -> int:
        """
        P0 FIX #4: Retry failed webhook events with exponential backoff.

        Simple retry mechanism:
        - Retry webhooks where processed=false and retry_count < max_retries
        - Exponential backoff: 60s, 120s, 240s
        - Update next_retry_at for scheduling

        Returns:
            Number of webhooks retried
        """
        try:
            # Find webhooks eligible for retry
            select_stmt = text("""
                SELECT id, event_type, payload, retry_count, related_message_id, related_patient_id
                FROM webhook_events
                WHERE processed = false
                  AND retry_count < max_retries
                  AND (next_retry_at IS NULL OR next_retry_at <= NOW())
                ORDER BY created_at ASC
                LIMIT 50
            """)

            results = self.db.execute(select_stmt).fetchall()
            retried_count = 0

            for row in results:
                event_id = UUID(row[0])
                event_type = row[1]
                payload = row[2]
                retry_count = row[3]
                related_message_id = UUID(row[4]) if row[4] else None
                related_patient_id = UUID(row[5]) if row[5] else None

                try:
                    # Route to appropriate handler based on event type
                    success = False

                    if event_type == "message.received":
                        message_id = await self.process_message_webhook(payload)
                        success = bool(message_id)
                    elif event_type == "message.status":
                        success = await self.process_status_webhook(payload)
                    elif event_type == "connection.update":
                        success = await self.process_connection_webhook(payload)
                    elif event_type == "qrcode.updated":
                        success = await self.process_qrcode_webhook(payload)
                    else:
                        logger.warning(f"Unknown event type for retry: {event_type}")
                        success = False

                    if success:
                        # Mark as processed
                        await self._mark_webhook_processed(event_id, True)
                        retried_count += 1
                        logger.info(f"Successfully retried webhook {event_id} (type={event_type})")
                    else:
                        # Increment retry count and schedule next retry
                        next_retry_delay = 60 * (2 ** retry_count)  # 60s, 120s, 240s
                        next_retry_at = datetime.utcnow() + timedelta(seconds=next_retry_delay)

                        update_stmt = text("""
                            UPDATE webhook_events
                            SET retry_count = retry_count + 1,
                                next_retry_at = :next_retry_at,
                                error_message = 'Retry failed, will retry again'
                            WHERE id = :event_id
                        """)

                        self.db.execute(update_stmt, {
                            "event_id": str(event_id),
                            "next_retry_at": next_retry_at
                        })
                        self.db.commit()

                        logger.warning(
                            f"Webhook retry failed: {event_id} "
                            f"(retry_count={retry_count + 1}, next_retry_at={next_retry_at})"
                        )

                except Exception as retry_error:
                    logger.error(f"Error retrying webhook {event_id}: {retry_error}", exc_info=True)

                    # Update retry count and schedule next retry
                    next_retry_delay = 60 * (2 ** retry_count)
                    next_retry_at = datetime.utcnow() + timedelta(seconds=next_retry_delay)

                    update_stmt = text("""
                        UPDATE webhook_events
                        SET retry_count = retry_count + 1,
                            next_retry_at = :next_retry_at,
                            error_message = :error_message
                        WHERE id = :event_id
                    """)

                    self.db.execute(update_stmt, {
                        "event_id": str(event_id),
                        "next_retry_at": next_retry_at,
                        "error_message": str(retry_error)
                    })
                    self.db.commit()

            logger.info(f"Webhook retry completed: {retried_count}/{len(results)} succeeded")
            return retried_count

        except Exception as e:
            logger.error(f"Error in retry_failed_webhooks: {e}", exc_info=True)
            return 0
