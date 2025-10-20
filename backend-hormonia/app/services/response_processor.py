"""
Response Processing Service for patient message handling.
Handles inbound message routing, interactive response validation,
and AI-powered response processing within flow contexts.
"""
import logging
from typing import List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from app.models.message import Message, MessageDirection, MessageType, MessageStatus
from app.models.flow import PatientFlowState
from app.models.patient import Patient
from app.repositories.message import MessageRepository
from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository
from app.services.ai import (
    get_sentiment_analyzer, 
    get_context_builder,
    PatientContext,
    ConcernLevel
)
from app.services.flow_event_broadcaster import flow_event_broadcaster
from app.services.platform_synchronization import get_platform_sync_service
from app.services.quiz_flow_integration import get_conversational_quiz_service
from app.utils.constants import (
    WHATSAPP_MESSAGE_LIMIT,
    URGENT_KEYWORDS,
    POSITIVE_MOOD_PATTERNS,
    NEGATIVE_MOOD_PATTERNS,
    YES_PATTERNS,
    NO_PATTERNS,
    MEDICATION_PATTERNS,
    PAIN_SCALE_PATTERN,
    TIME_PATTERNS,
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_NORMAL,
    ERROR_MESSAGES,
    DEFAULT_CONFIDENCE_SCORE,
    ESCALATION_DELAY_SECONDS,
    MAX_CONVERSATION_HISTORY
)

from app.exceptions import NotFoundError, ValidationError
from app.exceptions.response_processing import (
    ResponseValidationError,
    ResponseProcessingError,
    AIProcessingError,
    FlowStateError
)

logger = logging.getLogger(__name__)


@dataclass
class ResponseProcessorConfig:
    """Configuration for ResponseProcessor."""
    max_conversation_history: int = MAX_CONVERSATION_HISTORY
    message_limit: int = WHATSAPP_MESSAGE_LIMIT
    default_confidence_score: float = DEFAULT_CONFIDENCE_SCORE
    escalation_delay_seconds: int = ESCALATION_DELAY_SECONDS
    enable_ai_processing: bool = True
    enable_pattern_extraction: bool = True
    enable_sentiment_analysis: bool = True


class ResponseType(str, Enum):
    """Types of patient responses."""
    TEXT = "text"
    BUTTON = "button"
    QUICK_REPLY = "quick_reply"
    LIST_SELECTION = "list_selection"
    MEDIA = "media"
    LOCATION = "location"
    CONTACT = "contact"
    UNKNOWN = "unknown"


@dataclass
class ResponseValidationResult:
    """Result of response validation."""
    is_valid: bool
    response_type: ResponseType
    extracted_value: Any = None
    validation_errors: List[str] = field(default_factory=list)


@dataclass
class StructuredResponse:
    """Structured data extracted from patient response."""
    patient_id: UUID
    original_message: str
    response_type: ResponseType
    extracted_data: dict[str, Any]
    sentiment_analysis: dict[str, Any]
    medical_concerns: List[str]
    concern_level: ConcernLevel
    requires_attention: bool
    confidence_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ResponseFactory:
    """Factory for creating response objects."""
    
    @staticmethod
    def create_error_response(patient_id: UUID, 
                            original_message: str,
                            response_type: ResponseType,
                            validation_errors: List[str]) -> StructuredResponse:
        """Create a structured response for validation errors."""
        return StructuredResponse(
            patient_id=patient_id,
            original_message=original_message,
            response_type=response_type,
            extracted_data={"validation_errors": validation_errors},
            sentiment_analysis={"sentiment": "neutral", "confidence": 0.0},
            medical_concerns=[],
            concern_level=ConcernLevel.LOW,
            requires_attention=False,
            confidence_score=DEFAULT_CONFIDENCE_SCORE
        )
    
    @staticmethod
    def create_fallback_response(patient_id: UUID,
                               original_message: str,
                               response_type: ResponseType) -> StructuredResponse:
        """Create a fallback structured response when AI processing fails."""
        return StructuredResponse(
            patient_id=patient_id,
            original_message=original_message,
            response_type=response_type,
            extracted_data={"raw_text": original_message},
            sentiment_analysis={"sentiment": "neutral", "confidence": 0.0},
            medical_concerns=[],
            concern_level=ConcernLevel.LOW,
            requires_attention=False,
            confidence_score=DEFAULT_CONFIDENCE_SCORE
        )


@dataclass
class FlowAction:
    """Action to be taken based on patient response."""
    action_type: str
    parameters: dict[str, Any]
    priority: str = "normal"
    delay_seconds: int = 0


@dataclass
class ResponseProcessingResult:
    """Result of response processing."""
    patient_id: UUID
    structured_response: StructuredResponse
    flow_actions: List[FlowAction]
    follow_up_message: Optional[str] = None
    state_updates: Optional[dict[str, Any]] = None
    escalation_required: bool = False
    processed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class InboundMessage:
    """Inbound message data structure."""
    patient_phone: str
    content: str
    whatsapp_id: str
    message_type: MessageType = MessageType.TEXT
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class InteractiveResponse:
    """Interactive response (buttons, quick replies, etc.)."""
    patient_id: UUID
    response_value: str
    response_type: ResponseType
    original_message_id: Optional[UUID] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ResponseProcessor:
    """
    Main response processing service for handling patient messages
    within flow contexts with AI-powered analysis and routing.
    """
    
    def __init__(self, db: Session, config: Optional[ResponseProcessorConfig] = None):
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
        
        # Initialize AI services only if enabled
        self.sentiment_analyzer = get_ai_service() if self.config.enable_sentiment_analysis else None
        self.context_builder = get_ai_service() if self.config.enable_ai_processing else None
        
        logger.info(f"Response Processor initialized with config: {self.config}")
    
    async def process_inbound_message(self, inbound_message: InboundMessage) -> ResponseProcessingResult:
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
                raise NotFoundError(f"Patient not found for phone: {inbound_message.patient_phone}")
            
            # Store inbound message in database
            message = await self._store_inbound_message(patient.id, inbound_message)
            
            # Get current flow context
            flow_state = self.flow_state_repo.get_active_flow(patient.id)
            
            # Check if patient is in quiz mode
            is_quiz_response = await self._is_quiz_response(patient.id, flow_state)
            
            if is_quiz_response:
                return await self._handle_quiz_response(patient.id, inbound_message, flow_state)
            
            # Determine response type
            response_type = self._determine_response_type(inbound_message)
            
            # Validate response based on expected context
            validation_result = await self._validate_response(
                inbound_message, response_type, flow_state
            )
            
            if not validation_result.is_valid:
                return await self._handle_invalid_response(
                    patient.id, inbound_message, validation_result
                )
            
            # Extract structured data from response
            structured_response = await self._extract_structured_data(
                patient.id, inbound_message, response_type, flow_state
            )
            
            # Determine flow actions based on response
            flow_actions = await self._determine_flow_actions(
                structured_response, flow_state
            )
            
            # Generate follow-up message if needed
            follow_up_message = await self._generate_follow_up_message(
                structured_response, flow_state
            )
            
            # Prepare state updates
            state_updates = await self._prepare_state_updates(
                structured_response, flow_state
            )
            
            # Check if escalation is required
            escalation_required = self._check_escalation_required(structured_response)
            
            # Create processing result
            result = ResponseProcessingResult(
                patient_id=patient.id,
                structured_response=structured_response,
                flow_actions=flow_actions,
                follow_up_message=follow_up_message,
                state_updates=state_updates,
                escalation_required=escalation_required
            )
            
            # Apply state updates
            if state_updates:
                await self._apply_state_updates(patient.id, state_updates)
            
            # Broadcast patient interaction event
            await self.flow_broadcaster.broadcast_patient_interaction(
                patient_id=patient.id,
                message=message,
                interaction_type="response_received"
            )
            
            # Sync patient response to platform
            await self.platform_sync.sync_patient_record_update(
                patient_id=patient.id,
                flow_interaction_data={
                    "patient_response": {
                        "message_id": str(message.id),
                        "content": inbound_message.content[:200],  # Truncate for privacy
                        "response_type": response_type.value if hasattr(response_type, 'value') else str(response_type),
                        "structured_data": structured_response.extracted_data if structured_response else {},
                        "sentiment_score": structured_response.sentiment_analysis.get("confidence") if structured_response else None,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            
            logger.info(f"Processed inbound message for patient {patient.id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process inbound message: {e}")
            raise
    
    async def handle_interactive_response(self, interactive_response: InteractiveResponse) -> ResponseProcessingResult:
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
            validation_result = await self._validate_interactive_response(
                interactive_response, flow_state
            )
            
            if not validation_result.is_valid:
                return await self._handle_invalid_interactive_response(
                    patient_id, interactive_response, validation_result
                )
            
            # Create inbound message equivalent for processing
            inbound_message = InboundMessage(
                patient_phone="",  # Not needed for interactive responses
                content=interactive_response.response_value,
                whatsapp_id="",  # Not needed for interactive responses
                message_type=MessageType.BUTTON if interactive_response.response_type == ResponseType.BUTTON else MessageType.TEXT,
                metadata=interactive_response.metadata
            )
            
            # Process as structured response
            structured_response = await self._extract_structured_data(
                patient_id, inbound_message, interactive_response.response_type, flow_state
            )
            
            # Determine flow actions
            flow_actions = await self._determine_flow_actions(
                structured_response, flow_state
            )
            
            # Generate follow-up
            follow_up_message = await self._generate_follow_up_message(
                structured_response, flow_state
            )
            
            # Prepare state updates
            state_updates = await self._prepare_state_updates(
                structured_response, flow_state
            )
            
            # Create result
            result = ResponseProcessingResult(
                patient_id=patient_id,
                structured_response=structured_response,
                flow_actions=flow_actions,
                follow_up_message=follow_up_message,
                state_updates=state_updates,
                escalation_required=self._check_escalation_required(structured_response)
            )
            
            # Apply state updates
            if state_updates:
                await self._apply_state_updates(patient_id, state_updates)
            
            logger.info(f"Processed interactive response for patient {patient_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process interactive response: {e}")
            raise
    
    async def _store_inbound_message(self, patient_id: UUID, inbound_message: InboundMessage) -> Message:
        """Store inbound message in database."""
        try:
            message = Message(
                patient_id=patient_id,
                direction=MessageDirection.INBOUND,
                type=inbound_message.message_type,
                content=inbound_message.content,
                whatsapp_id=inbound_message.whatsapp_id,
                status=MessageStatus.READ,  # Inbound messages are considered read
                message_metadata=inbound_message.metadata,
                sent_at=inbound_message.timestamp,
                delivered_at=inbound_message.timestamp,
                read_at=inbound_message.timestamp
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
        if inbound_message.metadata.get('button_response'):
            return ResponseType.BUTTON
        elif inbound_message.metadata.get('quick_reply'):
            return ResponseType.QUICK_REPLY
        elif inbound_message.metadata.get('list_selection'):
            return ResponseType.LIST_SELECTION
        elif inbound_message.message_type == MessageType.MEDIA:
            return ResponseType.MEDIA
        elif inbound_message.message_type == MessageType.LOCATION:
            return ResponseType.LOCATION
        else:
            return ResponseType.TEXT
    
    async def _validate_response(self, 
                                inbound_message: InboundMessage,
                                response_type: ResponseType,
                                flow_state: Optional[PatientFlowState]) -> ResponseValidationResult:
        """Validate response based on expected context."""
        try:
            errors = []
            
            # Basic content validation
            if not inbound_message.content or not inbound_message.content.strip():
                errors.append("Empty message content")
            
            # Flow context validation
            if flow_state:
                expected_responses = flow_state.state_data.get('expected_responses', [])
                if expected_responses and response_type == ResponseType.BUTTON:
                    # Validate button response against expected options
                    if inbound_message.content not in expected_responses:
                        errors.append(f"Invalid button response: {inbound_message.content}")
            
            # Content length validation
            if len(inbound_message.content) > WHATSAPP_MESSAGE_LIMIT:
                errors.append("Message too long")
            
            is_valid = len(errors) == 0
            extracted_value = inbound_message.content if is_valid else None
            
            return ResponseValidationResult(
                is_valid=is_valid,
                response_type=response_type,
                extracted_value=extracted_value,
                validation_errors=errors
            )
            
        except Exception as e:
            logger.error(f"Response validation failed: {e}")
            return ResponseValidationResult(
                is_valid=False,
                response_type=response_type,
                validation_errors=[f"Validation error: {str(e)}"]
            )
    
    async def _validate_interactive_response(self,
                                           interactive_response: InteractiveResponse,
                                           flow_state: PatientFlowState) -> ResponseValidationResult:
        """Validate interactive response against flow context."""
        try:
            errors = []
            
            # Check if response value is provided
            if not interactive_response.response_value:
                errors.append("Empty response value")
            
            # Validate against expected responses in flow state
            expected_responses = flow_state.state_data.get('expected_responses', [])
            if expected_responses:
                if interactive_response.response_value not in expected_responses:
                    errors.append(f"Unexpected response: {interactive_response.response_value}")
            
            # Validate response type consistency
            expected_type = flow_state.state_data.get('expected_response_type')
            if expected_type and expected_type != interactive_response.response_type.value:
                errors.append(f"Response type mismatch: expected {expected_type}, got {interactive_response.response_type.value}")
            
            is_valid = len(errors) == 0
            
            return ResponseValidationResult(
                is_valid=is_valid,
                response_type=interactive_response.response_type,
                extracted_value=interactive_response.response_value if is_valid else None,
                validation_errors=errors
            )
            
        except Exception as e:
            logger.error(f"Interactive response validation failed: {e}")
            return ResponseValidationResult(
                is_valid=False,
                response_type=interactive_response.response_type,
                validation_errors=[f"Validation error: {str(e)}"]
            )
    
    async def _handle_invalid_response(self, 
                                     patient_id: UUID, 
                                     inbound_message: InboundMessage, 
                                     validation_result: ResponseValidationResult) -> ResponseProcessingResult:
        """Handle invalid response by creating appropriate error response."""
        try:
            # Create a basic structured response for invalid input
            structured_response = ResponseFactory.create_error_response(
                patient_id=patient_id,
                original_message=inbound_message.content,
                response_type=validation_result.response_type,
                validation_errors=validation_result.validation_errors
            )
            
            # Generate helpful error message
            if "Empty message content" in validation_result.validation_errors:
                error_message = ERROR_MESSAGES.get("empty_content", "Mensagem vazia")
            elif "Invalid button response" in str(validation_result.validation_errors):
                error_message = ERROR_MESSAGES.get("invalid_button", "Resposta inválida")
            else:
                error_message = ERROR_MESSAGES.get("generic_error", "Erro genérico")
            
            return ResponseProcessingResult(
                patient_id=patient_id,
                structured_response=structured_response,
                flow_actions=[],
                follow_up_message=error_message,
                state_updates=None,
                escalation_required=False
            )
            
        except Exception as e:
            logger.error(f"Failed to handle invalid response: {e}")
            raise
    
    async def _handle_invalid_interactive_response(self,
                                                 patient_id: UUID,
                                                 interactive_response: InteractiveResponse,
                                                 validation_result: ResponseValidationResult) -> ResponseProcessingResult:
        """Handle invalid interactive response."""
        try:
            structured_response = StructuredResponse(
                patient_id=patient_id,
                original_message=interactive_response.response_value,
                response_type=interactive_response.response_type,
                extracted_data={"validation_errors": validation_result.validation_errors},
                sentiment_analysis={"sentiment": "neutral", "confidence": 0.0},
                medical_concerns=[],
                concern_level=ConcernLevel.LOW,
                requires_attention=False,
                confidence_score=0.0
            )
            
            error_message = ERROR_MESSAGES.get("invalid_interactive", "Resposta interativa inválida")
            
            return ResponseProcessingResult(
                patient_id=patient_id,
                structured_response=structured_response,
                flow_actions=[],
                follow_up_message=error_message,
                state_updates=None,
                escalation_required=False
            )
            
        except Exception as e:
            logger.error(f"Failed to handle invalid interactive response: {e}")
            raise
    
    async def _extract_structured_data(self,
                                     patient_id: UUID,
                                     inbound_message: InboundMessage,
                                     response_type: ResponseType,
                                     flow_state: Optional[PatientFlowState]) -> StructuredResponse:
        """Extract structured data from patient response using AI."""
        try:
            # Early exit if AI processing is disabled
            if not self.config.enable_ai_processing or not self.context_builder or not self.sentiment_analyzer:
                return ResponseFactory.create_fallback_response(
                    patient_id=patient_id,
                    original_message=inbound_message.content,
                    response_type=response_type
                )
            
            # Get patient context for AI analysis
            patient = self.patient_repo.get(patient_id)
            if not patient:
                raise NotFoundError(f"Patient {patient_id} not found")
            
            # Get recent message history
            recent_messages = self.message_repo.get_conversation_history(patient_id, limit=10)
            recent_message_data = [
                {
                    "content": msg.content,
                    "direction": msg.direction.value,
                    "timestamp": msg.created_at.isoformat()
                }
                for msg in recent_messages
            ]
            
            # Build patient context
            patient_context = await self.context_builder.build_patient_context(
                patient_id=str(patient_id),
                patient_data={
                    "name": patient.name,
                    "treatment_type": getattr(patient, 'treatment_type', 'general'),
                    "current_day": flow_state.current_step if flow_state else 1,
                    "treatment_start_date": flow_state.started_at.isoformat() if flow_state else None,
                    "age": getattr(patient, 'age', None),
                    "preferences": getattr(patient, 'preferences', {})
                },
                recent_messages=recent_message_data,
                medical_data=getattr(patient, 'medical_history', {})
            )
            
            # Perform sentiment analysis
            sentiment_response, concern_level = await self.sentiment_analyzer.analyze_response(
                inbound_message.content, patient_context
            )
            
            # Extract data based on response type
            extracted_data = await self._extract_type_specific_data(
                inbound_message, response_type, flow_state
            )
            
            # Determine if attention is required
            requires_attention = (
                concern_level in [ConcernLevel.HIGH, ConcernLevel.CRITICAL] or
                sentiment_response.medical_concerns or
                self._contains_urgent_keywords(inbound_message.content)
            )
            
            return StructuredResponse(
                patient_id=patient_id,
                original_message=inbound_message.content,
                response_type=response_type,
                extracted_data=extracted_data,
                sentiment_analysis={
                    "sentiment": sentiment_response.sentiment.value,
                    "confidence": sentiment_response.confidence,
                    "key_phrases": sentiment_response.key_phrases,
                    "emotional_indicators": sentiment_response.emotional_indicators
                },
                medical_concerns=sentiment_response.medical_concerns,
                concern_level=concern_level,
                requires_attention=requires_attention,
                confidence_score=sentiment_response.confidence
            )
            
        except Exception as e:
            logger.error(f"Failed to extract structured data: {e}")
            # Return fallback response on failure
            return ResponseFactory.create_fallback_response(
                patient_id=patient_id,
                original_message=inbound_message.content,
                response_type=response_type
            )
    
    async def _extract_type_specific_data(self,
                                        inbound_message: InboundMessage,
                                        response_type: ResponseType,
                                        flow_state: Optional[PatientFlowState]) -> dict[str, Any]:
        """Extract data specific to response type."""
        extracted_data = {"raw_text": inbound_message.content}
        
        try:
            if response_type == ResponseType.BUTTON:
                extracted_data.update({
                    "button_value": inbound_message.content,
                    "button_metadata": inbound_message.metadata.get('button_data', {})
                })
            
            elif response_type == ResponseType.QUICK_REPLY:
                extracted_data.update({
                    "quick_reply_value": inbound_message.content,
                    "quick_reply_payload": inbound_message.metadata.get('payload', '')
                })
            
            elif response_type == ResponseType.LIST_SELECTION:
                extracted_data.update({
                    "selected_option": inbound_message.content,
                    "list_metadata": inbound_message.metadata.get('list_data', {})
                })
            
            elif response_type == ResponseType.TEXT:
                # Extract common patterns from free text
                extracted_data.update(await self._extract_text_patterns(inbound_message.content))
            
            elif response_type == ResponseType.MEDIA:
                extracted_data.update({
                    "media_type": inbound_message.metadata.get('media_type', 'unknown'),
                    "media_url": inbound_message.metadata.get('media_url', ''),
                    "caption": inbound_message.content
                })
            
            elif response_type == ResponseType.LOCATION:
                extracted_data.update({
                    "latitude": inbound_message.metadata.get('latitude'),
                    "longitude": inbound_message.metadata.get('longitude'),
                    "address": inbound_message.content
                })
            
            # Add flow context data
            if flow_state:
                extracted_data["flow_context"] = {
                    "flow_type": flow_state.flow_type,
                    "current_step": flow_state.current_step,
                    "expected_response_type": flow_state.state_data.get('expected_response_type'),
                    "question_context": flow_state.state_data.get('last_question', '')
                }
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"Failed to extract type-specific data: {e}")
            return extracted_data
    
    async def _extract_text_patterns(self, text: str) -> dict[str, Any]:
        """Extract common patterns from free text responses."""
        import re
        
        patterns = {}
        
        try:
            # Extract yes/no responses
            yes_patterns = r'\b(sim|yes|yeah|ok|okay|claro|certo|positivo)\b'
            no_patterns = r'\b(não|no|nope|never|negativo|jamais)\b'
            
            if re.search(yes_patterns, text.lower()):
                patterns["boolean_response"] = True
            elif re.search(no_patterns, text.lower()):
                patterns["boolean_response"] = False
            
            # Extract numbers
            numbers = re.findall(r'\b\d+(?:\.\d+)?\b', text)
            if numbers:
                patterns["numbers"] = [float(n) for n in numbers]
            
            # Extract time references
            time_patterns = r'\b(\d{1,2}):(\d{2})\b|(\d{1,2})\s*(am|pm|h|horas?)\b'
            time_matches = re.findall(time_patterns, text.lower())
            if time_matches:
                patterns["time_references"] = time_matches
            
            # Extract medication names (basic pattern)
            med_patterns = r'\b(mg|ml|comprimido|cápsula|medicamento|remédio)\b'
            if re.search(med_patterns, text.lower()):
                patterns["medication_mentioned"] = True
            
            # Extract pain scale (1-10)
            pain_scale = re.search(r'\b([1-9]|10)\b.*\b(dor|pain|scale|escala)\b', text.lower())
            if pain_scale:
                patterns["pain_scale"] = int(pain_scale.group(1))
            
            # Extract mood indicators
            positive_mood = r'\b(bem|good|great|ótimo|feliz|happy|melhor|better)\b'
            negative_mood = r'\b(mal|bad|terrible|péssimo|triste|sad|pior|worse)\b'
            
            if re.search(positive_mood, text.lower()):
                patterns["mood_indicator"] = "positive"
            elif re.search(negative_mood, text.lower()):
                patterns["mood_indicator"] = "negative"
            
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to extract text patterns: {e}")
            return {}
    
    def _contains_urgent_keywords(self, text: str) -> bool:
        """Check if text contains urgent keywords requiring immediate attention."""
        urgent_keywords = [
            'emergency', 'emergência', 'urgent', 'urgente', 'help', 'ajuda',
            'hospital', 'ambulance', 'ambulância', 'severe', 'severo',
            'can\'t breathe', 'não consigo respirar', 'chest pain', 'dor no peito',
            'bleeding', 'sangramento', 'unconscious', 'inconsciente'
        ]
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in urgent_keywords)
    
    async def _determine_flow_actions(self,
                                    structured_response: StructuredResponse,
                                    flow_state: Optional[PatientFlowState]) -> List[FlowAction]:
        """Determine flow actions based on response analysis."""
        actions = []
        
        try:
            # Action based on concern level
            if structured_response.concern_level == ConcernLevel.CRITICAL:
                actions.append(FlowAction(
                    action_type="escalate_immediately",
                    parameters={
                        "concern_level": "critical",
                        "medical_concerns": structured_response.medical_concerns,
                        "patient_message": structured_response.original_message
                    },
                    priority="critical",
                    delay_seconds=0
                ))
            
            elif structured_response.concern_level == ConcernLevel.HIGH:
                actions.append(FlowAction(
                    action_type="schedule_provider_review",
                    parameters={
                        "concern_level": "high",
                        "medical_concerns": structured_response.medical_concerns,
                        "review_within_hours": 4
                    },
                    priority="high",
                    delay_seconds=300  # 5 minutes
                ))
            
            # Action based on response type
            if structured_response.response_type == ResponseType.BUTTON:
                actions.append(FlowAction(
                    action_type="process_button_response",
                    parameters={
                        "button_value": structured_response.extracted_data.get("button_value"),
                        "flow_context": structured_response.extracted_data.get("flow_context", {})
                    },
                    priority="normal",
                    delay_seconds=0
                ))
            
            # Action based on extracted patterns
            if structured_response.extracted_data.get("boolean_response") is not None:
                actions.append(FlowAction(
                    action_type="process_boolean_response",
                    parameters={
                        "response_value": structured_response.extracted_data["boolean_response"],
                        "context": structured_response.extracted_data.get("flow_context", {})
                    },
                    priority="normal",
                    delay_seconds=0
                ))
            
            return actions
            
        except Exception as e:
            logger.error(f"Failed to determine flow actions: {e}")
            return []
    
    async def _generate_follow_up_message(self,
                                        structured_response: StructuredResponse,
                                        flow_state: Optional[PatientFlowState]) -> Optional[str]:
        """Generate follow-up message based on response analysis."""
        try:
            # Generate empathetic follow-up for high concern responses
            if structured_response.concern_level in [ConcernLevel.HIGH, ConcernLevel.CRITICAL]:
                return "Obrigada por compartilhar isso comigo. Vou conectar você com sua equipe médica."
            
            # Generate acknowledgment for positive responses
            if structured_response.extracted_data.get("mood_indicator") == "positive":
                return "Que bom saber! Continue assim!"
            
            # Generate supportive message for negative responses
            if structured_response.extracted_data.get("mood_indicator") == "negative":
                return "Entendo. Estou aqui para apoiá-la."
            
            # Generate confirmation for boolean responses
            if structured_response.extracted_data.get("boolean_response") is True:
                return "Perfeito! Obrigada por confirmar."
            elif structured_response.extracted_data.get("boolean_response") is False:
                return "Entendi. Obrigada por me avisar."
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to generate follow-up message: {e}")
            return None
    
    async def _prepare_state_updates(self,
                                   structured_response: StructuredResponse,
                                   flow_state: Optional[PatientFlowState]) -> Optional[dict[str, Any]]:
        """Prepare state updates based on response analysis."""
        try:
            if not flow_state:
                return None
            
            updates = {}
            
            # Update last response data
            updates["last_response"] = {
                "timestamp": structured_response.timestamp.isoformat(),
                "type": structured_response.response_type.value,
                "sentiment": structured_response.sentiment_analysis.get("sentiment"),
                "concern_level": structured_response.concern_level.value,
                "requires_attention": structured_response.requires_attention
            }
            
            # Update extracted patterns
            if structured_response.extracted_data:
                updates["extracted_patterns"] = structured_response.extracted_data
            
            # Update medical concerns if any
            if structured_response.medical_concerns:
                updates["medical_concerns"] = structured_response.medical_concerns
            
            return updates
            
        except Exception as e:
            logger.error(f"Failed to prepare state updates: {e}")
            return None
    
    async def _apply_state_updates(self, patient_id: UUID, state_updates: dict[str, Any]) -> None:
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
    
    def _check_escalation_required(self, structured_response: StructuredResponse) -> bool:
        """Check if escalation is required based on response analysis."""
        return (
            structured_response.concern_level in [ConcernLevel.HIGH, ConcernLevel.CRITICAL] or
            structured_response.requires_attention or
            bool(structured_response.medical_concerns)
        )
    
    async def _is_quiz_response(self, patient_id: UUID, flow_state: Optional[PatientFlowState]) -> bool:
        """Check if patient is currently in quiz mode."""
        try:
            if not flow_state or not flow_state.state_data:
                return False
            
            # Check if there's an active quiz session
            quiz_state = flow_state.state_data.get("quiz_state")
            quiz_session_id = flow_state.state_data.get("quiz_session_id")
            
            if quiz_state in ["in_progress", "awaiting_response"] and quiz_session_id:
                # Verify quiz session is still active
                active_session = self.quiz_service.quiz_session_service.get_active_session(patient_id)
                return active_session is not None
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking quiz response status: {e}")
            return False
    
    async def _handle_quiz_response(self, 
                                  patient_id: UUID, 
                                  inbound_message: InboundMessage,
                                  flow_state: PatientFlowState) -> ResponseProcessingResult:
        """Handle patient response during quiz session."""
        try:
            # Process quiz response
            quiz_result = await self.quiz_service.process_quiz_response(
                patient_id=patient_id,
                response_text=inbound_message.content,
                message_metadata=inbound_message.metadata
            )
            
            # Create structured response based on quiz processing result
            structured_response = StructuredResponse(
                patient_id=patient_id,
                original_message=inbound_message.content,
                response_type=ResponseType.TEXT,
                extracted_data={
                    "quiz_response": True,
                    "quiz_result": quiz_result,
                    "raw_text": inbound_message.content
                },
                sentiment_analysis={"sentiment": "neutral", "confidence": 0.8},
                medical_concerns=[],
                concern_level=ConcernLevel.LOW,
                requires_attention=False,
                confidence_score=0.8
            )
            
            # Determine flow actions based on quiz result
            flow_actions = []
            state_updates = {}
            follow_up_message = None
            
            if quiz_result["action"] == "quiz_completed":
                # Quiz completed - return to normal flow
                flow_actions.append(FlowAction(
                    action_type="quiz_completed",
                    parameters={"session_id": quiz_result.get("session_id")},
                    priority="normal"
                ))
                
                state_updates = {
                    "quiz_state": "completed",
                    "quiz_completed_at": datetime.utcnow().isoformat()
                }
                
            elif quiz_result["action"] == "next_question":
                # Continue with quiz
                state_updates = {
                    "quiz_state": "awaiting_response",
                    "current_question_index": quiz_result.get("question_index", 0)
                }
                
            elif quiz_result["action"] == "request_clarification":
                # Invalid response - clarification already sent
                state_updates = {
                    "quiz_state": "awaiting_response",
                    "last_clarification_at": datetime.utcnow().isoformat()
                }
                
            elif quiz_result["action"] == "error":
                # Quiz processing error
                structured_response.requires_attention = True
                structured_response.concern_level = ConcernLevel.MEDIUM
                
                flow_actions.append(FlowAction(
                    action_type="escalate_quiz_error",
                    parameters={"error": quiz_result.get("error")},
                    priority="high"
                ))
            
            return ResponseProcessingResult(
                patient_id=patient_id,
                structured_response=structured_response,
                flow_actions=flow_actions,
                follow_up_message=follow_up_message,
                state_updates=state_updates,
                escalation_required=quiz_result.get("action") == "error"
            )
            
        except Exception as e:
            logger.error(f"Error handling quiz response: {e}")
            
            # Fallback response
            structured_response = ResponseFactory.create_fallback_response(
                patient_id=patient_id,
                original_message=inbound_message.content,
                response_type=ResponseType.TEXT
            )
            
            return ResponseProcessingResult(
                patient_id=patient_id,
                structured_response=structured_response,
                flow_actions=[],
                follow_up_message="Desculpe, houve um problema ao processar sua resposta do quiz. Nossa equipe foi notificada.",
                state_updates=None,
                escalation_required=True
            )


# Global service instance
_response_processor: Optional[ResponseProcessor] = None


def get_response_processor(db: Session) -> ResponseProcessor:
    """
    Get response processor instance.
    
    Args:
        db: Database session
        
    Returns:
        ResponseProcessor instance
    """
    return ResponseProcessor(db)