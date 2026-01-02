"""
Main response processor logic.
"""

import logging
from typing import Optional, Any
from datetime import datetime, timezone
from uuid import UUID

from app.models.message import Message, MessageDirection, MessageType, MessageStatus
from app.models.flow import PatientFlowState
from app.repositories.message import MessageRepository
from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository
from app.services.flow.event_broadcaster import flow_event_broadcaster
from app.services.platform_synchronization import get_platform_sync_service
from app.domain.quizzes.integration.flow_integration import (
    get_conversational_quiz_service,
)
from app.exceptions import NotFoundError, ValidationError

from .models import (
    ResponseProcessorConfig,
    ResponseProcessingResult,
    InboundMessage,
    InteractiveResponse,
    ResponseType,
)
from .validators import ResponseValidator
from .extractors import DataExtractor
from .handlers import ResponseHandlers, QuizResponseHandler
from .flow_helpers import FlowHelpers
# FollowUpSystemService imported lazily to avoid circular import
# (follow_up_system.context.manager imports StructuredResponse from this module)

logger = logging.getLogger(__name__)


def get_ai_service():
    """Placeholder for AI service - returns None if not available."""
    try:
        from app.services.ai import get_sentiment_analyzer

        return get_sentiment_analyzer()
    except ImportError:
        return None


class ResponseProcessor:
    """
    Main response processing service for handling patient messages
    within flow contexts with AI-powered analysis and routing.
    """

    def __init__(self, db: Any, config: Optional[ResponseProcessorConfig] = None):
        """
        Initialize response processor.

        Args:
            db: Database session
            config: Optional configuration object
        """
        self.db = db
        self.config = config or ResponseProcessorConfig()
        self.message_repo = MessageRepository(db)
        self.flow_state_repo = FlowStateRepository(db)
        self.patient_repo = PatientRepository(db)
        self.flow_broadcaster = flow_event_broadcaster
        self.platform_sync = get_platform_sync_service(db)
        self.quiz_service = get_conversational_quiz_service(db)

        # Initialize components
        self.validator = ResponseValidator(self.config.message_limit)
        self.extractor = DataExtractor(db, self.config)
        self.handlers = ResponseHandlers()
        self.quiz_handler = QuizResponseHandler(self.quiz_service)
        self.flow_helpers = FlowHelpers()

        # Follow-up system integration (ISSUE: FollowUpSystemService não integrado)
        # Lazy initialization to avoid circular import
        self._follow_up_service = None
        self._follow_up_rehydrated = False
        
        # Sequential message handler for multi-message flows
        self._sequential_handler = None

        logger.info(f"Response Processor initialized with config: {self.config}")

    async def process_inbound_message(
        self, inbound_message: InboundMessage
    ) -> ResponseProcessingResult:
        """
        Process inbound message and route to appropriate flow context.

        Args:
            inbound_message: Inbound message data

        Returns:
            Response processing result

        Raises:
            NotFoundError: If patient not found
            ValidationError: If message validation fails
        """
        try:
            # Find patient by phone number
            patient = self.patient_repo.get_by_phone(inbound_message.patient_phone)
            if not patient:
                raise NotFoundError(
                    f"Patient not found for phone: {inbound_message.patient_phone}"
                )

            # Get current flow context FIRST (for enriched metadata)
            flow_state = self.flow_state_repo.get_active_flow(patient.id)

            # Store inbound message in database with flow context
            message = await self._store_inbound_message(patient.id, inbound_message, flow_state)

            # Check if patient is in quiz mode
            is_quiz_response = await self._is_quiz_response(patient.id, flow_state)

            if is_quiz_response:
                return await self.quiz_handler.handle_quiz_response(
                    patient.id, inbound_message
                )

            # Determine response type
            response_type = self._determine_response_type(inbound_message)

            # Validate response based on expected context
            validation_result = await self.validator.validate_response(
                inbound_message, response_type, flow_state
            )

            if not validation_result.is_valid:
                return await self.handlers.handle_invalid_response(
                    patient.id, inbound_message, validation_result
                )

            # Extract structured data from response
            structured_response = await self.extractor.extract_structured_data(
                patient.id, inbound_message, response_type, flow_state
            )

            # Determine flow actions based on response
            flow_actions = await self.flow_helpers.determine_flow_actions(
                structured_response, flow_state
            )

            # Generate follow-up message if needed
            follow_up_message = await self.flow_helpers.generate_follow_up_message(
                structured_response, flow_state
            )

            # Prepare state updates
            state_updates = await self.flow_helpers.prepare_state_updates(
                structured_response, flow_state
            )

            # Check if escalation is required
            escalation_required = self.flow_helpers.check_escalation_required(
                structured_response
            )

            # Create processing result
            result = ResponseProcessingResult(
                patient_id=patient.id,
                structured_response=structured_response,
                flow_actions=flow_actions,
                follow_up_message=follow_up_message,
                state_updates=state_updates,
                escalation_required=escalation_required,
            )

            # Apply state updates
            if state_updates:
                await self._apply_state_updates(patient.id, state_updates)

            # Process follow-up actions for escalation or medical concerns
            # FIX: FollowUpSystemService was not integrated into response pipeline
            if result.escalation_required or (
                structured_response and structured_response.medical_concerns
            ):
                await self._process_follow_up_actions(result)

            # Broadcast patient interaction event
            await self.flow_broadcaster.broadcast_patient_interaction(
                patient_id=patient.id,
                message=message,
                interaction_type="response_received",
            )

            # Sync patient response to platform
            await self.platform_sync.sync_patient_record_update(
                patient_id=patient.id,
                flow_interaction_data={
                    "patient_response": {
                        "message_id": str(message.id),
                        "content": inbound_message.content[
                            :200
                        ],  # Truncate for privacy
                        "response_type": response_type.value
                        if hasattr(response_type, "value")
                        else str(response_type),
                        "structured_data": structured_response.extracted_data
                        if structured_response
                        else {},
                        "sentiment_score": structured_response.sentiment_analysis.get(
                            "confidence"
                        )
                        if structured_response
                        else None,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                },
            )

            logger.info(f"Processed inbound message for patient {patient.id}")
            
            # Trigger next sequential message if patient is in a multi-message flow
            await self._trigger_sequential_continuation(patient.id, flow_state)
            
            return result

        except Exception as e:
            logger.error(f"Failed to process inbound message: {e}")
            raise

    async def handle_interactive_response(
        self, interactive_response: InteractiveResponse
    ) -> ResponseProcessingResult:
        """
        Handle interactive response (buttons, quick replies, etc.).

        Args:
            interactive_response: Interactive response data

        Returns:
            Response processing result
        """
        try:
            patient_id = interactive_response.patient_id

            # Get flow context
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            if not flow_state:
                raise ValidationError(f"No active flow found for patient {patient_id}")

            # Validate interactive response
            validation_result = await self.validator.validate_interactive_response(
                interactive_response, flow_state
            )

            if not validation_result.is_valid:
                return await self.handlers.handle_invalid_interactive_response(
                    patient_id, interactive_response, validation_result
                )

            # Create inbound message equivalent for processing
            inbound_message = InboundMessage(
                patient_phone="",  # Not needed for interactive responses
                content=interactive_response.response_value,
                whatsapp_id="",  # Not needed for interactive responses
                message_type=MessageType.BUTTON
                if interactive_response.response_type == ResponseType.BUTTON
                else MessageType.TEXT,
                metadata=interactive_response.metadata,
            )

            # Process as structured response
            structured_response = await self.extractor.extract_structured_data(
                patient_id,
                inbound_message,
                interactive_response.response_type,
                flow_state,
            )

            # Determine flow actions
            flow_actions = await self.flow_helpers.determine_flow_actions(
                structured_response, flow_state
            )

            # Generate follow-up
            follow_up_message = await self.flow_helpers.generate_follow_up_message(
                structured_response, flow_state
            )

            # Prepare state updates
            state_updates = await self.flow_helpers.prepare_state_updates(
                structured_response, flow_state
            )

            # Create result
            result = ResponseProcessingResult(
                patient_id=patient_id,
                structured_response=structured_response,
                flow_actions=flow_actions,
                follow_up_message=follow_up_message,
                state_updates=state_updates,
                escalation_required=self.flow_helpers.check_escalation_required(
                    structured_response
                ),
            )

            # Apply state updates
            if state_updates:
                await self._apply_state_updates(patient_id, state_updates)

            # Process follow-up actions for escalation or medical concerns
            if result.escalation_required or (
                structured_response and structured_response.medical_concerns
            ):
                await self._process_follow_up_actions(result)

            logger.info(f"Processed interactive response for patient {patient_id}")
            return result

        except Exception as e:
            logger.error(f"Failed to process interactive response: {e}")
            raise

    async def _store_inbound_message(
        self, patient_id: UUID, inbound_message: InboundMessage,
        flow_state: Optional[PatientFlowState] = None
    ) -> Message:
        """
        Store inbound message in database with enriched metadata.
        
        Includes flow context (day, question index) and idempotency key.
        """
        import hashlib
        
        try:
            # Build enriched metadata with flow context
            metadata = dict(inbound_message.metadata) if inbound_message.metadata else {}
            
            # Add flow context if available
            if flow_state and flow_state.step_data:
                step_data = flow_state.step_data
                metadata["flow_context"] = {
                    "flow_kind": step_data.get("flow_kind"),
                    "current_flow_day": step_data.get("current_flow_day"),
                    "current_message_index": step_data.get("current_day_message_index", 0),
                    "awaiting_response": step_data.get("awaiting_response", False),
                    "flow_state_id": str(flow_state.id) if flow_state.id else None,
                }
            
            # Generate idempotency key from content + timestamp + whatsapp_id
            idempotency_source = f"{patient_id}:{inbound_message.content}:{inbound_message.whatsapp_id or ''}"
            idempotency_key = hashlib.sha256(idempotency_source.encode()).hexdigest()[:32]
            
            # Check for duplicate message
            existing = self.message_repo.get_by_idempotency_key(patient_id, idempotency_key)
            if existing:
                logger.warning(f"Duplicate inbound message detected: {idempotency_key}")
                return existing
            
            message = Message(
                patient_id=patient_id,
                direction=MessageDirection.INBOUND,
                type=inbound_message.message_type,
                content=inbound_message.content,
                whatsapp_id=inbound_message.whatsapp_id,
                status=MessageStatus.READ,
                message_metadata=metadata,
                idempotency_key=idempotency_key,
                sent_at=inbound_message.timestamp,
                delivered_at=inbound_message.timestamp,
                read_at=inbound_message.timestamp,
            )

            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)

            return message

        except Exception as e:
            logger.error(f"Failed to store inbound message: {e}")
            self.db.rollback()
            raise

    def _determine_response_type(self, inbound_message: InboundMessage) -> ResponseType:
        """Determine the type of response based on message content and metadata."""
        # Check metadata for interactive response indicators
        if inbound_message.metadata.get("button_response"):
            return ResponseType.BUTTON
        elif inbound_message.metadata.get("quick_reply"):
            return ResponseType.QUICK_REPLY
        elif inbound_message.metadata.get("list_selection"):
            return ResponseType.LIST_SELECTION
        elif inbound_message.message_type == MessageType.MEDIA:
            return ResponseType.MEDIA
        elif inbound_message.message_type == MessageType.LOCATION:
            return ResponseType.LOCATION
        else:
            return ResponseType.TEXT

    async def _apply_state_updates(
        self, patient_id: UUID, state_updates: dict[str, Any]
    ) -> None:
        """Apply state updates to patient flow state."""
        try:
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            if not flow_state:
                logger.warning(f"No active flow state found for patient {patient_id}")
                return

            # Update state data
            if not flow_state.state_data:
                flow_state.state_data = {}

            flow_state.state_data.update(state_updates)

            # Commit changes
            self.db.commit()

            logger.info(f"Applied state updates for patient {patient_id}")

        except Exception as e:
            logger.error(f"Failed to apply state updates: {e}")
            self.db.rollback()
            raise

    async def _is_quiz_response(
        self, patient_id: UUID, flow_state: Optional[PatientFlowState]
    ) -> bool:
        """Check if patient is currently in quiz mode."""
        try:
            if not flow_state or not flow_state.state_data:
                return False

            # Check if there's an active quiz session
            quiz_state = flow_state.state_data.get("quiz_state")
            quiz_session_id = flow_state.state_data.get("quiz_session_id")

            if quiz_state in ["in_progress", "awaiting_response"] and quiz_session_id:
                # Verify quiz session is still active
                active_session = (
                    self.quiz_service.quiz_session_service.get_active_session(
                        patient_id
                    )
                )
                return active_session is not None

            return False

        except Exception as e:
            logger.error(f"Error checking quiz response status: {e}")
            return False

    def _get_follow_up_service(self):
        """Lazy initialization of FollowUpSystemService to avoid circular imports."""
        if self._follow_up_service is None:
            from app.services.follow_up_system.service import FollowUpSystemService

            self._follow_up_service = FollowUpSystemService(self.db)
        return self._follow_up_service

    def _get_sequential_handler(self):
        """Lazy initialization of SequentialMessageHandler to avoid circular imports."""
        if self._sequential_handler is None:
            from app.services.flow.sequential_message_handler import SequentialMessageHandler
            self._sequential_handler = SequentialMessageHandler(self.db)
        return self._sequential_handler

    async def _trigger_sequential_continuation(
        self, patient_id: UUID, flow_state: Optional[PatientFlowState]
    ) -> None:
        """
        Trigger next sequential message if patient is in a multi-message flow.
        
        Called after processing an inbound message to check if we need to send
        the next message in a sequential/wait_response/wait_each flow.
        """
        try:
            if not flow_state:
                return
            
            step_data = flow_state.step_data or {}
            
            # Check if we're awaiting response and should continue
            if not step_data.get("awaiting_response"):
                return
            
            # Get handler and trigger continuation
            handler = self._get_sequential_handler()
            result = await handler.handle_response_and_continue(patient_id)
            
            if result.get("status") == "waiting":
                logger.info(f"Sent next sequential message to patient {patient_id}")
            elif result.get("status") == "day_complete":
                logger.info(f"Sequential flow day complete for patient {patient_id}")
        
        except Exception as e:
            # Don't let sequential message failures break the main response flow
            logger.error(f"Failed to trigger sequential continuation: {e}", exc_info=True)

    async def _process_follow_up_actions(
        self, result: ResponseProcessingResult
    ) -> None:
        """
        Process follow-up actions through FollowUpSystemService.

        FIX: FollowUpSystemService was built but never connected to the response pipeline.
        This integration ensures:
        - Empathetic follow-up messages are generated
        - Medical concerns trigger appropriate alerts
        - Escalation notifications are sent
        - All follow-up actions are scheduled and tracked
        """
        try:
            # Get follow-up service (lazy initialization)
            follow_up_service = self._get_follow_up_service()

            # Rehydrate Redis state once per processor instance
            if not self._follow_up_rehydrated:
                rehydration_result = await follow_up_service.rehydrate_from_redis()
                self._follow_up_rehydrated = True
                logger.info(
                    f"Follow-up service rehydrated: {rehydration_result['pending_actions']} actions, "
                    f"{rehydration_result['active_alerts']} alerts"
                )

            # Process follow-up actions for this response
            follow_up_actions = await follow_up_service.process_response_follow_up(
                result
            )

            if follow_up_actions:
                logger.info(
                    f"Created {len(follow_up_actions)} follow-up actions for patient {result.patient_id}"
                )

        except Exception as e:
            # Don't let follow-up failures break the main response flow
            logger.error(f"Failed to process follow-up actions: {e}", exc_info=True)


# Global service instance
_response_processor: Optional[ResponseProcessor] = None


def get_response_processor(db: Any) -> ResponseProcessor:
    """
    Get response processor instance.

    Args:
        db: Database session

    Returns:
        ResponseProcessor instance
    """
    return ResponseProcessor(db)
