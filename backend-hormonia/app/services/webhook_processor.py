"""
Webhook processor for Evolution API integration.
Handles incoming messages from WhatsApp and processes them through the flow engine.
"""
import logging
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session
import redis.asyncio as redis

from app.models.message import Message, MessageType, MessageStatus, MessageDirection
from app.models.patient import Patient
from app.models.flow import PatientFlowState, FlowKind, FlowTemplateVersion
from app.services.message import MessageService
from app.services.patient import PatientService
from app.services.flow_engine import FlowEngine
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
        db: Session,
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
        self.patient_service = PatientService(db)
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
        1. Extract and validate message data
        2. Check idempotency (deduplicate by whatsapp_id)
        3. Find patient by phone number
        4. Create inbound message record
        5. Publish WebSocket event
        6. Check for active flow
        7. Route to flow processing or general chat
        8. Generate and send response

        Args:
            event_data: Webhook event data from Evolution API

        Returns:
            Message ID if processed successfully, None otherwise
        """
        try:
            # Step 1: Extract message data from webhook
            message_data = self._extract_message_data(event_data)
            if not message_data:
                logger.warning("No valid message data found in webhook")
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
                # Cache in Redis for future fast-path (TTL 1h)
                await redis_client.setex(idempotency_key, 3600, str(existing_message.id))
                return str(existing_message.id)

            # Step 3: Find patient by phone number
            patient = self._find_patient_by_phone(message_data["phone"])
            if not patient:
                logger.warning(f"Patient not found for phone: {message_data['phone']}")
                # Future: Could implement auto-registration here
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

            # Cache message_id in Redis for idempotency (TTL 1h)
            await redis_client.setex(idempotency_key, 3600, str(message.id))

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

            return str(message.id)

        except Exception as e:
            logger.error(f"Error processing message webhook: {e}", exc_info=True)
            return None

    @with_db_retry(max_retries=3)
    async def process_status_webhook(self, event_data: dict[str, Any]) -> bool:
        """
        Process message status update webhook (delivered, read, etc).

        Args:
            event_data: Webhook event data

        Returns:
            True if processed successfully
        """
        try:
            # Extract status data
            whatsapp_id = event_data.get("key", {}).get("id")
            status = event_data.get("update", {}).get("status")

            if not whatsapp_id or not status:
                logger.warning("Missing required fields in status webhook")
                return False

            # Update message status
            message = self.message_service.update_message_status_by_whatsapp_id(
                whatsapp_id=whatsapp_id,
                status=self._map_evolution_status(status)
            )

            if message:
                # Publish WebSocket event for status update
                await websocket_events.publish_message_event(
                    event_type=WebSocketEventType.MESSAGE_STATUS_UPDATE,
                    message_id=message.id,
                    patient_id=message.patient_id,
                    direction=message.direction.value,
                    message_type=message.type.value,
                    status=message.status.value,
                    metadata={"whatsapp_id": whatsapp_id}
                )

                logger.info(f"Updated message {message.id} status to {status}")
                return True

            logger.warning(f"Message not found for WhatsApp ID: {whatsapp_id}")
            return False

        except Exception as e:
            logger.error(f"Error processing status webhook: {e}", exc_info=True)
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
                advancement = await self.flow_engine.advance_flow(
                    patient_id=patient.id,
                    additional_context={"patient_response": message.content}
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

        Args:
            patient: Patient record
            message: Inbound message
            quiz_session: Active quiz session
        """
        try:
            from app.services.quiz_flow_integration import ConversationalQuizService

            quiz_service = ConversationalQuizService(self.db)

            # Process quiz response
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
            elif result.get('action') == 'next_question':
                logger.info(f"Advanced to next question for patient {patient.id}")
            elif result.get('action') == 'request_clarification':
                logger.info(f"Clarification requested for patient {patient.id}")

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
                "cancer_type": getattr(patient, "cancer_type", None),
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
            from app.services.message_scheduler import get_message_scheduler
            scheduler = get_message_scheduler(self.db)

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
            patient = self.patient_service.get_by_phone(normalized)
            if patient:
                logger.info(f"Patient found with E.164 format: {normalized}")
                return patient

            # Strategy 2: Try without + prefix
            without_plus = normalized.lstrip("+")
            logger.info(f"Phone lookup attempt 2: Without + prefix '{without_plus}'")
            patient = self.patient_service.get_by_phone(without_plus)
            if patient:
                logger.info(f"Patient found without + prefix: {without_plus}")
                return patient

            # Strategy 3: Try adding +55 if not present
            if not phone.startswith("55") and not phone.startswith("+55"):
                with_country_code = f"+55{phone}"
                logger.info(f"Phone lookup attempt 3: With country code '{with_country_code}'")
                patient = self.patient_service.get_by_phone(with_country_code)
                if patient:
                    logger.info(f"Patient found with added country code: {with_country_code}")
                    return patient

                # Also try without +
                logger.info(f"Phone lookup attempt 4: With country code no + '55{phone}'")
                patient = self.patient_service.get_by_phone(f"55{phone}")
                if patient:
                    logger.info(f"Patient found with country code (no +): 55{phone}")
                    return patient

            # Strategy 4: Try removing country code (last 10-11 digits for Brazilian numbers)
            if len(without_plus) > 11:
                # Extract last 11 digits (DDD + 9 digits) or 10 digits (DDD + 8 digits)
                local_11 = without_plus[-11:]
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