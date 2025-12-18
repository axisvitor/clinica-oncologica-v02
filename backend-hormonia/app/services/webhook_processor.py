"""
Webhook processor for Evolution API integration.
Handles incoming messages from WhatsApp and processes them through the flow engine.

REFACTORED (Phase 2):
This module now serves as a facade that delegates to specialized handlers:
- app.services.webhook.handlers.message_handler.MessageWebhookHandler
- app.services.webhook.handlers.status_handler.StatusWebhookHandler
- app.services.webhook.handlers.connection_handler.ConnectionWebhookHandler
- app.services.webhook.persistence.webhook_store.WebhookEventStore

The original monolithic implementation (1,291 lines) has been decomposed into:
- handlers/ (message, status, connection) - ~880 lines
- utils/ (phone_normalizer, message_extractor) - ~320 lines
- persistence/ (webhook_store) - ~320 lines

This facade maintains backward compatibility while delegating to the new modules.
"""

import logging
from typing import Any, Optional, Dict
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy import text

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
from app.integrations.openai_client import get_langchain_orchestrator
from app.repositories.connection_state import ConnectionStateRepository
from app.repositories.flow import FlowStateRepository
from app.utils.db_retry import with_db_retry

# New modular imports (Phase 2 refactoring)
from app.services.webhook.handlers import (
    MessageWebhookHandler,
    StatusWebhookHandler,
    ConnectionWebhookHandler,
)
from app.services.webhook.persistence import WebhookEventStore

logger = logging.getLogger(__name__)


class WebhookProcessor:
    """
    Process webhooks from Evolution API for WhatsApp messages.

    REFACTORED: This class now acts as a facade, delegating to specialized handlers:
    - MessageWebhookHandler: Message processing with flow routing
    - StatusWebhookHandler: Delivery status updates
    - ConnectionWebhookHandler: Connection and QR code events
    - WebhookEventStore: Persistence and retry logic

    Responsibilities (delegated to handlers):
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

        # Legacy services (maintained for backward compatibility)
        self.message_service = MessageService(db)
        self.patient_repo = PatientRepository(db)
        self.flow_engine = FlowEngine(db)
        self.enhanced_flow_engine = EnhancedFlowEngine(db)
        self.flow_state_repo = FlowStateRepository(db)
        self.ai_client = get_langchain_orchestrator()
        self.connection_state_repo = (
            connection_state_repository or ConnectionStateRepository()
        )

        # NEW: Modular handlers (Phase 2 refactoring)
        self.message_handler = MessageWebhookHandler(db)
        self.status_handler = StatusWebhookHandler(db)
        self.connection_handler = ConnectionWebhookHandler(connection_state_repository)
        self.webhook_store = WebhookEventStore(db)

        logger.info("WebhookProcessor initialized (facade mode with modular handlers)")

    @with_db_retry(max_retries=3)
    async def process_message_webhook(
        self, event_data: dict[str, Any]
    ) -> Optional[str]:
        """
        Process incoming message webhook from Evolution API.

        REFACTORED: Delegates to MessageWebhookHandler for all processing.

        The handler implements:
        - Webhook persistence (P0 FIX #2)
        - Message extraction and validation
        - Idempotency checks (Redis + DB)
        - Patient lookup with security monitoring
        - Flow routing and general chat handling
        - Response generation and sending

        Args:
            event_data: Webhook event data from Evolution API

        Returns:
            Message ID if processed successfully, None otherwise
        """
        try:
            return await self.message_handler.process_message(
                event_data=event_data, webhook_store=self.webhook_store
            )
        except Exception as e:
            logger.error(f"Error processing message webhook: {e}", exc_info=True)
            return None

    @with_db_retry(max_retries=3)
    async def process_status_webhook(self, event_data: dict[str, Any]) -> bool:
        """
        Process message status update webhook (delivered, read, etc).

        REFACTORED: Delegates to StatusWebhookHandler.

        The handler implements:
        - Webhook persistence (P0 FIX #2)
        - Status mapping (Evolution API -> Internal)
        - Message record updates

        Args:
            event_data: Webhook event data

        Returns:
            True if processed successfully
        """
        try:
            return await self.status_handler.process_status(
                event_data=event_data, webhook_store=self.webhook_store
            )
        except Exception as e:
            logger.error(f"Error processing status webhook: {e}", exc_info=True)
            return False

    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================

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
        Handle message within active quiz context.

        HIGH-005 FIX: Implements debouncing to prevent duplicate quiz responses
        from rapid messages within a 3-second window.

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

            # Get current question ID from session
            current_question_id = (
                quiz_session.current_question
                if hasattr(quiz_session, "current_question")
                and quiz_session.current_question
                else str(quiz_session.current_question_index)
                if hasattr(quiz_session, "current_question_index")
                else "unknown"
            )

            # Check if we should process this response (debounce check)
            should_process = await debouncer.should_process_response(
                session_id=quiz_session.id,
                question_id=current_question_id,
                message_metadata={
                    "message_id": str(message.id),
                    "whatsapp_id": message.whatsapp_id,
                    "timestamp": message.timestamp.isoformat()
                    if message.timestamp
                    else None,
                    "patient_id": str(patient.id),
                },
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
                        "debounce_reason": "duplicate_within_3s_window",
                    },
                )
                return

            # Process quiz response (not debounced)
            quiz_service = ConversationalQuizService(self.db)

            result = await quiz_service.process_quiz_response(
                patient_id=patient.id,
                response_text=message.content,
                message_metadata={
                    "message_id": str(message.id),
                    "timestamp": message.timestamp,
                    "whatsapp_id": message.whatsapp_id,
                },
            )

            logger.info(
                f"Quiz response processed for patient {patient.id}: "
                f"action={result.get('action')}, success={result.get('success')}"
            )

            # Handle result actions
            if result.get("action") == "quiz_completed":
                logger.info(f"Quiz completed for patient {patient.id}")
                # Clear all debounce state for session on completion
                await debouncer.clear_debounce(quiz_session.id)
            elif result.get("action") == "next_question":
                logger.info(f"Advanced to next question for patient {patient.id}")
                # Debounce state automatically expires, no need to clear
            elif result.get("action") == "request_clarification":
                logger.info(f"Clarification requested for patient {patient.id}")
                # Clear debounce to allow immediate retry
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
                status=MessageStatus.PENDING,  # Explicit PENDING status
            )

            # Step 2: Persist to database
            response_message = self.message_service.create_message(response_data)
            logger.info(
                f"Created message {response_message.id} for patient {patient_id}"
            )

            # Step 3: Publish WebSocket event (UI will show this message)
            await self._publish_message_event(response_message, patient_id)
            logger.debug(f"Published WebSocket event for message {response_message.id}")

            # Step 4: Schedule the SAME message for immediate delivery
            # Import MessageScheduler
            from app.domain.messaging.scheduling import MessageScheduler

            scheduler = MessageScheduler(self.db)

            # Schedule the existing message (status: PENDING → SCHEDULED)
            send_time = datetime.utcnow() + timedelta(
                seconds=1
            )  # Send almost immediately
            scheduling_success = await scheduler.schedule_existing_message(
                message_id=response_message.id,
                send_time=send_time,
                priority="high",  # Auto-responses are high priority
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

    async def _send_unauthorized_response(
        self, phone: str, attempt_count: int = 1
    ) -> None:
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
                logger.warning(
                    f"Evolution client unavailable, cannot send unauthorized response to {phone}"
                )
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
            metadata=message.metadata,
        )

    # NOTE: The following methods have been moved to modular handlers/utils:
    # - _extract_message_data -> app.services.webhook.utils.message_extractor
    # - _normalize_phone_e164 -> app.services.webhook.utils.PhoneNormalizer
    # - _find_patient_by_phone -> app.services.webhook.utils.PhoneNormalizer
    # - _clean_phone_number -> app.services.webhook.utils.PhoneNormalizer

    def _get_flow_type_from_state(self, flow_state: PatientFlowState) -> str:
        """
        Get flow type from flow state using template version.

        Args:
            flow_state: Patient flow state

        Returns:
            Flow type string
        """
        try:
            template_version = (
                self.db.query(FlowTemplateVersion)
                .filter(FlowTemplateVersion.id == flow_state.template_version_id)
                .first()
            )

            if not template_version:
                return "unknown"

            flow_kind = (
                self.db.query(FlowKind)
                .filter(FlowKind.id == template_version.kind_id)
                .first()
            )

            return flow_kind.flow_type if flow_kind else "unknown"

        except Exception as e:
            logger.error(f"Error getting flow type: {e}")
            return "unknown"

    # NOTE: The following methods have been moved to modular handlers:
    # - _map_evolution_status -> app.services.webhook.handlers.StatusWebhookHandler
    # - _persist_webhook_event -> app.services.webhook.persistence.WebhookEventStore
    # - _mark_webhook_processed -> app.services.webhook.persistence.WebhookEventStore

    @with_db_retry(max_retries=3)
    async def process_connection_webhook(self, event_data: dict[str, Any]) -> bool:
        """
        P0 FIX #3: Process connection status webhook (connection.update events).

        REFACTORED: Delegates to ConnectionWebhookHandler.

        The handler implements:
        - Webhook persistence
        - Connection state updates (open, close, connecting)
        - Redis state management

        Args:
            event_data: Webhook event data

        Returns:
            True if processed successfully
        """
        try:
            return await self.connection_handler.process_connection(
                event_data=event_data, webhook_store=self.webhook_store
            )
        except Exception as e:
            logger.error(f"Error processing connection webhook: {e}", exc_info=True)
            return False

    @with_db_retry(max_retries=3)
    async def process_qrcode_webhook(self, event_data: dict[str, Any]) -> bool:
        """
        P0 FIX #5: Process QR code webhook (qrcode.updated events).

        REFACTORED: Delegates to ConnectionWebhookHandler.

        The handler implements:
        - Webhook persistence
        - QR code storage in Redis
        - TTL management

        Args:
            event_data: Webhook event data containing QR code

        Returns:
            True if processed successfully
        """
        try:
            return await self.connection_handler.process_qrcode(
                event_data=event_data, webhook_store=self.webhook_store
            )
        except Exception as e:
            logger.error(f"Error processing QR code webhook: {e}", exc_info=True)
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
                UUID(row[4]) if row[4] else None
                UUID(row[5]) if row[5] else None

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
                        # Mark as processed using WebhookEventStore
                        await self.webhook_store.mark_processed(event_id, success=True)
                        retried_count += 1
                        logger.info(
                            f"Successfully retried webhook {event_id} (type={event_type})"
                        )
                    else:
                        # Increment retry count and schedule next retry
                        next_retry_delay = 60 * (2**retry_count)  # 60s, 120s, 240s
                        next_retry_at = datetime.utcnow() + timedelta(
                            seconds=next_retry_delay
                        )

                        update_stmt = text("""
                            UPDATE webhook_events
                            SET retry_count = retry_count + 1,
                                next_retry_at = :next_retry_at,
                                error_message = 'Retry failed, will retry again'
                            WHERE id = :event_id
                        """)

                        self.db.execute(
                            update_stmt,
                            {"event_id": str(event_id), "next_retry_at": next_retry_at},
                        )
                        self.db.commit()

                        logger.warning(
                            f"Webhook retry failed: {event_id} "
                            f"(retry_count={retry_count + 1}, next_retry_at={next_retry_at})"
                        )

                except Exception as retry_error:
                    logger.error(
                        f"Error retrying webhook {event_id}: {retry_error}",
                        exc_info=True,
                    )

                    # Update retry count and schedule next retry
                    next_retry_delay = 60 * (2**retry_count)
                    next_retry_at = datetime.utcnow() + timedelta(
                        seconds=next_retry_delay
                    )

                    update_stmt = text("""
                        UPDATE webhook_events
                        SET retry_count = retry_count + 1,
                            next_retry_at = :next_retry_at,
                            error_message = :error_message
                        WHERE id = :event_id
                    """)

                    self.db.execute(
                        update_stmt,
                        {
                            "event_id": str(event_id),
                            "next_retry_at": next_retry_at,
                            "error_message": str(retry_error),
                        },
                    )
                    self.db.commit()

            logger.info(
                f"Webhook retry completed: {retried_count}/{len(results)} succeeded"
            )
            return retried_count

        except Exception as e:
            logger.error(f"Error in retry_failed_webhooks: {e}", exc_info=True)
            return 0
