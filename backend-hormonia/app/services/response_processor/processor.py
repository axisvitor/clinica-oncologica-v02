"""
Main response processor logic.
"""

import asyncio
import hashlib
import logging
import time
from typing import Optional, Any, Dict
from uuid import UUID

from app.models.message import Message, MessageDirection, MessageType, MessageStatus
from app.models.flow import PatientFlowState
from app.repositories.message import MessageRepository
from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository
from app.services.flow.event_broadcaster import flow_event_broadcaster
from app.services.platform_synchronization import get_platform_sync_service
from app.domain.quizzes.integration.flow_integration.utils import (
    get_conversational_quiz_service,
)
from app.exceptions import NotFoundError, ValidationError
from app.monitoring.metrics import (
    response_processing_duration_seconds,
    response_medical_concerns_total,
    response_escalations_total,
)

from .models import (
    ResponseProcessorConfig,
    ResponseProcessingResult,
    InboundMessage,
    InteractiveResponse,
    ResponseType,
    ResponseFactory,
)
from .validators import ResponseValidator
from .extractors import DataExtractor
from .handlers import ResponseHandlers, QuizResponseHandler
from .flow_helpers import FlowHelpers
from app.utils.timezone import now_sao_paulo
from app.services.flow.sequential_response_gate import (
    evaluate_sequential_gate,
    should_record_processed_response,
)
from app.services.flow.context_parsing import parse_optional_int, parse_optional_str
# FollowUpSystemService imported lazily to avoid circular import
# (follow_up_system.context.manager imports StructuredResponse from this module)

logger = logging.getLogger(__name__)
_follow_up_rehydrated = False
_follow_up_rehydrate_lock = asyncio.Lock()



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
        self.validator = ResponseValidator(
            self.config.message_limit,
            lenient_validation=self.config.lenient_validation,
        )
        self.extractor = DataExtractor(db, self.config)
        self.handlers = ResponseHandlers()
        self.quiz_handler = QuizResponseHandler(self.quiz_service)
        self.flow_helpers = FlowHelpers()

        # Follow-up system integration (ISSUE: FollowUpSystemService não integrado)
        # Lazy initialization to avoid circular import
        self._follow_up_service = None
        
        # Sequential message handler for multi-message flows
        self._sequential_handler = None

        logger.info(f"Response Processor initialized with config: {self.config}")

    def update_db(self, db: Any) -> None:
        """Refresh database-bound dependencies for a new session."""
        if self.db is db:
            return

        self.db = db
        self.message_repo = MessageRepository(db)
        self.flow_state_repo = FlowStateRepository(db)
        self.patient_repo = PatientRepository(db)
        self.platform_sync = get_platform_sync_service(db)
        self.quiz_service = get_conversational_quiz_service(db)
        self.extractor = DataExtractor(db, self.config)
        self._follow_up_service = None
        self._sequential_handler = None

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
        start_time = time.monotonic()
        processing_status = "success"
        structured_response = None
        message = None
        response_type = None

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
            stored_message = await self._store_inbound_message(
                patient.id, inbound_message, flow_state
            )
            if isinstance(stored_message, tuple):
                message, is_duplicate = stored_message
            else:
                # Backward compatibility for older mocks/adapters returning only Message.
                message, is_duplicate = stored_message, False
            if is_duplicate:
                logger.info(
                    "Duplicate inbound message ignored",
                    extra={
                        "patient_id": str(patient.id),
                        "whatsapp_id": inbound_message.whatsapp_id,
                        "message_id": str(message.id),
                    },
                )
                return ResponseProcessingResult(
                    patient_id=patient.id,
                    structured_response=ResponseFactory.create_error_response(
                        patient_id=patient.id,
                        original_message=inbound_message.content,
                        response_type=ResponseType.TEXT,
                        validation_errors=["duplicate_message"],
                    ),
                    flow_actions=[],
                    follow_up_message=None,
                    state_updates=None,
                    escalation_required=False,
                )

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

            if message and flow_state:
                state_updates = self._augment_state_updates(
                    state_updates, message, inbound_message
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
                        "timestamp": now_sao_paulo().isoformat(),
                    }
                },
            )

            if structured_response and structured_response.medical_concerns:
                response_medical_concerns_total.labels(
                    concern_level=getattr(structured_response.concern_level, "value", "unknown")
                ).inc(len(structured_response.medical_concerns))

            if escalation_required:
                response_escalations_total.labels(
                    escalation_level=getattr(structured_response.concern_level, "value", "unknown")
                    if structured_response
                    else "unknown"
                ).inc()

            logger.info(
                "Processed inbound message",
                extra={
                    "patient_id": str(patient.id),
                    "message_id": str(message.id),
                    "response_type": response_type.value if response_type else None,
                    "concern_level": getattr(structured_response.concern_level, "value", None)
                    if structured_response
                    else None,
                    "severity_score": getattr(structured_response, "severity_score", None)
                    if structured_response
                    else None,
                    "escalation_required": escalation_required,
                },
            )
            
            # Trigger next sequential message only when inbound context matches
            # the pending response state.
            await self._trigger_sequential_continuation(
                patient.id,
                flow_state,
                response_context=self._build_response_context(
                    flow_state=flow_state,
                    message=message,
                    inbound_message=inbound_message,
                ),
            )
            
            return result

        except Exception as e:
            processing_status = "failed"
            logger.error(
                "Failed to process inbound message",
                exc_info=True,
                extra={
                    "patient_phone": inbound_message.patient_phone,
                    "response_type": response_type.value if response_type else None,
                    "error_type": type(e).__name__,
                },
            )
            raise
        finally:
            duration = time.monotonic() - start_time
            response_processing_duration_seconds.labels(
                status=processing_status
            ).observe(duration)

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
        start_time = time.monotonic()
        processing_status = "success"
        structured_response = None
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

            interactive_metadata = dict(interactive_response.metadata or {})
            if (
                interactive_response.original_message_id
                and not interactive_metadata.get("prompt_message_id")
            ):
                interactive_metadata["prompt_message_id"] = str(
                    interactive_response.original_message_id
                )

            # Create inbound message equivalent for processing
            inbound_message = InboundMessage(
                patient_phone="",  # Not needed for interactive responses
                content=interactive_response.response_value,
                whatsapp_id="",  # Not needed for interactive responses
                message_type=MessageType.BUTTON
                if interactive_response.response_type == ResponseType.BUTTON
                else MessageType.TEXT,
                metadata=interactive_metadata,
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

            # Keep wait_response / wait_each progression behavior consistent for
            # interactive replies (buttons/quick-replies) as well.
            await self._trigger_sequential_continuation(
                patient_id,
                flow_state,
                response_context=self._build_response_context(
                    flow_state=flow_state,
                    message=None,
                    inbound_message=inbound_message,
                ),
            )

            if structured_response and structured_response.medical_concerns:
                response_medical_concerns_total.labels(
                    concern_level=getattr(structured_response.concern_level, "value", "unknown")
                ).inc(len(structured_response.medical_concerns))

            if result.escalation_required:
                response_escalations_total.labels(
                    escalation_level=getattr(structured_response.concern_level, "value", "unknown")
                    if structured_response
                    else "unknown"
                ).inc()

            logger.info(
                "Processed interactive response",
                extra={
                    "patient_id": str(patient_id),
                    "response_type": interactive_response.response_type.value,
                    "concern_level": getattr(structured_response.concern_level, "value", None)
                    if structured_response
                    else None,
                    "severity_score": getattr(structured_response, "severity_score", None)
                    if structured_response
                    else None,
                    "escalation_required": result.escalation_required,
                },
            )
            return result

        except Exception as e:
            processing_status = "failed"
            logger.error(f"Failed to process interactive response: {e}")
            raise
        finally:
            duration = time.monotonic() - start_time
            response_processing_duration_seconds.labels(
                status=processing_status
            ).observe(duration)

    async def _store_inbound_message(
        self, patient_id: UUID, inbound_message: InboundMessage,
        flow_state: Optional[PatientFlowState] = None
    ) -> tuple[Message, bool]:
        """
        Store inbound message in database with enriched metadata.
        
        Includes flow context (day, question index) and idempotency key.
        """
        try:
            # Build enriched metadata with flow context
            metadata = dict(inbound_message.metadata) if inbound_message.metadata else {}
            
            # Add flow context if available
            if flow_state and flow_state.step_data:
                step_data = flow_state.step_data

                existing_flow_context = metadata.get("flow_context")
                merged_flow_context = (
                    dict(existing_flow_context) if isinstance(existing_flow_context, dict) else {}
                )
                merged_flow_context.update(
                    {
                    "flow_kind": step_data.get("flow_kind"),
                    "current_flow_day": step_data.get("current_flow_day"),
                    "current_message_index": step_data.get("current_day_message_index", 0),
                    "awaiting_response": step_data.get("awaiting_response", False),
                    "flow_state_id": str(flow_state.id) if flow_state.id else None,
                    }
                )
                metadata["flow_context"] = merged_flow_context
            
            # Generate idempotency key from content + media + whatsapp_id
            message_type = inbound_message.message_type or MessageType.TEXT
            media_url = metadata.get("media_url") or metadata.get("url") or ""
            content = inbound_message.content or ""
            idempotency_source = (
                f"{patient_id}:{message_type}:{content}:{media_url}:{inbound_message.whatsapp_id or ''}"
            )
            idempotency_key = hashlib.sha256(idempotency_source.encode()).hexdigest()[:32]
            
            # Check for duplicate message
            existing = self.message_repo.get_by_idempotency_key(patient_id, idempotency_key)
            if existing:
                logger.warning(f"Duplicate inbound message detected: {idempotency_key}")
                return existing, True
            
            message = Message(
                patient_id=patient_id,
                direction=MessageDirection.INBOUND,
                type=message_type,
                content=content,
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

            return message, False

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
        elif inbound_message.message_type in [
            MessageType.IMAGE,
            MessageType.AUDIO,
            MessageType.VIDEO,
            MessageType.DOCUMENT,
            MessageType.MEDIA,
        ]:
            return ResponseType.MEDIA
        elif inbound_message.message_type == MessageType.LOCATION:
            return ResponseType.LOCATION
        elif inbound_message.message_type == MessageType.BUTTON:
            return ResponseType.BUTTON
        elif inbound_message.message_type == MessageType.LIST:
            return ResponseType.LIST_SELECTION
        else:
            return ResponseType.TEXT

    def _augment_state_updates(
        self,
        state_updates: Optional[dict[str, Any]],
        message: Message,
        inbound_message: InboundMessage,
    ) -> dict[str, Any]:
        """Augment state updates with message identifiers and idempotency."""
        updates = dict(state_updates or {})
        last_response = dict(updates.get("last_response", {}))
        last_response.update(
            {
                "message_id": str(message.id),
                "whatsapp_id": inbound_message.whatsapp_id,
                "idempotency_key": getattr(message, "idempotency_key", None),
                "received_at": now_sao_paulo().isoformat(),
            }
        )
        updates["last_response"] = last_response
        return updates

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
            flow_state.last_interaction_at = now_sao_paulo()

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

    @staticmethod
    def _should_record_processed_response(
        *,
        status: Optional[str],
        reason: Optional[str],
    ) -> bool:
        """Return whether the inbound response should be marked as consumed."""
        return should_record_processed_response(status=status, reason=reason)

    def _build_response_context(
        self,
        *,
        flow_state: Optional[PatientFlowState],
        message: Optional[Message],
        inbound_message: InboundMessage,
    ) -> dict[str, Any]:
        """Build the response context used by sequential continuation gates."""
        step_data = flow_state.step_data or {} if flow_state else {}
        pending_response_context = step_data.get("pending_response_context")
        if not isinstance(pending_response_context, dict):
            pending_response_context = {}
        metadata = dict(inbound_message.metadata or {})
        raw_flow_context = metadata.get("flow_context")
        flow_context = raw_flow_context if isinstance(raw_flow_context, dict) else {}
        prompt_message_id = parse_optional_str(
            flow_context.get("prompt_message_id")
            or metadata.get("prompt_message_id")
            or pending_response_context.get("prompt_message_id")
        )

        response_message_id = None
        if message and getattr(message, "id", None):
            response_message_id = str(message.id)
        else:
            response_message_id = parse_optional_str(
                metadata.get("response_message_id")
                or metadata.get("whatsapp_id")
                or inbound_message.whatsapp_id
            )
        if response_message_id is None:
            response_message_id = self._build_deterministic_response_message_id(
                flow_state=flow_state,
                inbound_message=inbound_message,
                flow_context=flow_context,
                prompt_message_id=prompt_message_id,
            )

        context = {
            "prompt_message_id": prompt_message_id,
            "response_message_id": response_message_id,
            "flow_day": flow_context.get(
                "flow_day",
                flow_context.get("current_flow_day", step_data.get("current_flow_day")),
            ),
            "flow_kind": flow_context.get("flow_kind", step_data.get("flow_kind")),
            "message_index": flow_context.get(
                "message_index",
                flow_context.get(
                    "current_message_index", step_data.get("current_day_message_index")
                ),
            ),
            "awaiting_response": flow_context.get(
                "awaiting_response", step_data.get("awaiting_response")
            ),
        }
        return {key: value for key, value in context.items() if value is not None}

    def _build_deterministic_response_message_id(
        self,
        *,
        flow_state: Optional[PatientFlowState],
        inbound_message: InboundMessage,
        flow_context: dict[str, Any],
        prompt_message_id: Optional[str],
    ) -> str:
        """Build a stable fallback ID used for dedupe when provider ID is absent."""
        metadata = dict(inbound_message.metadata or {})
        flow_day = parse_optional_int(
            flow_context.get("flow_day", flow_context.get("current_flow_day"))
        )
        message_index = parse_optional_int(
            flow_context.get(
                "message_index",
                flow_context.get("current_message_index", flow_context.get("current_day_message_index")),
            )
        )
        fingerprint_parts = (
            parse_optional_str(getattr(flow_state, "patient_id", None)) or "",
            parse_optional_str(getattr(flow_state, "id", None)) or "",
            parse_optional_str(metadata.get("timestamp")) or "",
            parse_optional_str(metadata.get("reply_timestamp")) or "",
            parse_optional_str(metadata.get("button_reply_id")) or "",
            parse_optional_str(metadata.get("list_reply_id")) or "",
            parse_optional_str(flow_context.get("flow_kind")) or "",
            str(flow_day) if flow_day is not None else "",
            str(message_index) if message_index is not None else "",
            prompt_message_id or "",
            parse_optional_str(inbound_message.content) or "",
            parse_optional_str(inbound_message.message_type) or "",
        )
        source = "|".join(fingerprint_parts)
        return f"interactive-{hashlib.sha256(source.encode('utf-8')).hexdigest()[:32]}"

    def _evaluate_sequential_gate(
        self, step_data: dict[str, Any], response_context: Optional[dict[str, Any]]
    ) -> tuple[bool, str, dict[str, Any]]:
        """Validate that a response can continue the pending sequential step."""
        return evaluate_sequential_gate(step_data, response_context)

    async def _trigger_sequential_continuation(
        self,
        patient_id: UUID,
        flow_state: Optional[PatientFlowState],
        response_context: Optional[dict[str, Any]] = None,
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
            if not step_data.get("current_flow_day") or not step_data.get("flow_kind"):
                return

            gate_allowed, gate_reason, normalized_context = self._evaluate_sequential_gate(
                step_data, response_context
            )
            if not gate_allowed:
                logger.info(
                    "Skipping sequential continuation due to progression gate",
                    extra={
                        "patient_id": str(patient_id),
                        "reason": gate_reason,
                        "response_context": normalized_context,
                    },
                )
                return
            
            # Get handler and trigger continuation
            handler = self._get_sequential_handler()
            result = await handler.handle_response_and_continue(
                patient_id, response_context=normalized_context
            )
            
            status = result.get("status") if isinstance(result, dict) else None
            if status == "waiting":
                logger.info(f"Sent next sequential message to patient {patient_id}")
            elif status == "day_complete":
                logger.info(f"Sequential flow day complete for patient {patient_id}")

            result_reason = result.get("reason") if isinstance(result, dict) else None
            response_message_id = normalized_context.get("response_message_id")
            if response_message_id and self._should_record_processed_response(
                status=status,
                reason=result_reason,
            ):
                latest_step_data = dict(flow_state.step_data or {})
                latest_step_data["last_processed_response_message_id"] = response_message_id
                flow_state.step_data = latest_step_data
                self.db.commit()
        
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
            global _follow_up_rehydrated
            if not _follow_up_rehydrated:
                async with _follow_up_rehydrate_lock:
                    if not _follow_up_rehydrated:
                        rehydration_result = (
                            await follow_up_service.rehydrate_from_redis()
                        )
                        _follow_up_rehydrated = True
                        logger.info(
                            "Follow-up service rehydrated: "
                            f"{rehydration_result['pending_actions']} actions, "
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
    global _response_processor

    if _response_processor is None:
        _response_processor = ResponseProcessor(db)
    else:
        _response_processor.update_db(db)

    return _response_processor
