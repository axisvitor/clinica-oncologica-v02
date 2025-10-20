"""
Follow-up Action System for patient responses.
Implements automatic follow-up message generation, escalation logic,
healthcare provider notifications, and conversation continuity.
"""
import logging
from typing import List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID, uuid4
from sqlalchemy.orm import Session

from app.services.response_processor import (
    ResponseProcessingResult,
    StructuredResponse,
    FlowAction
)
from app.services.data_extraction import (
    StructuredExtractionResult,
    MedicalConcern,
    MedicalConcernType,
    ConcernLevel
)
from app.services.ai import (
    get_ai_humanizer,
    get_sentiment_analyzer,
    PatientContext,
    AIHumanizer
)
from app.models.message import Message, MessageDirection, MessageType, MessageStatus
from app.models.flow import PatientFlowState
from app.models.patient import Patient
from app.repositories.message import MessageRepository
from app.repositories.flow import FlowStateRepository
from app.repositories.patient import PatientRepository
from app.services.message_sender import MessageSender
from app.services.message_scheduler import MessageScheduler
from app.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class FollowUpType(str, Enum):
    """Types of follow-up actions."""
    EMPATHETIC_RESPONSE = "empathetic_response"
    MEDICAL_CLARIFICATION = "medical_clarification"
    ESCALATION_NOTIFICATION = "escalation_notification"
    PROVIDER_ALERT = "provider_alert"
    APPOINTMENT_SCHEDULING = "appointment_scheduling"
    MEDICATION_GUIDANCE = "medication_guidance"
    EMOTIONAL_SUPPORT = "emotional_support"
    TREATMENT_ENCOURAGEMENT = "treatment_encouragement"
    INFORMATION_REQUEST = "information_request"
    CONVERSATION_CONTINUATION = "conversation_continuation"


class EscalationLevel(str, Enum):
    """Escalation levels for healthcare provider notifications."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class NotificationChannel(str, Enum):
    """Channels for healthcare provider notifications."""
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    DASHBOARD_ALERT = "dashboard_alert"
    PUSH_NOTIFICATION = "push_notification"
    PHONE_CALL = "phone_call"


class FollowUpAction:
    """Follow-up action to be executed."""
    
    def __init__(self,
                 action_id: UUID,
                 patient_id: UUID,
                 follow_up_type: FollowUpType,
                 priority: str,
                 scheduled_for: datetime,
                 parameters: dict[str, Any],
                 created_by: str = "system"):
        self.action_id = action_id
        self.patient_id = patient_id
        self.follow_up_type = follow_up_type
        self.priority = priority
        self.scheduled_for = scheduled_for
        self.parameters = parameters
        self.created_by = created_by
        self.created_at = datetime.utcnow()
        self.executed_at: Optional[datetime] = None
        self.execution_result: Optional[dict[str, Any]] = None
        self.status = "pending"


class EscalationAlert:
    """Healthcare provider escalation alert."""
    
    def __init__(self,
                 alert_id: UUID,
                 patient_id: UUID,
                 escalation_level: EscalationLevel,
                 concern_type: MedicalConcernType,
                 description: str,
                 original_message: str,
                 recommended_actions: List[str],
                 notification_channels: List[NotificationChannel],
                 requires_immediate_response: bool = False):
        self.alert_id = alert_id
        self.patient_id = patient_id
        self.escalation_level = escalation_level
        self.concern_type = concern_type
        self.description = description
        self.original_message = original_message
        self.recommended_actions = recommended_actions
        self.notification_channels = notification_channels
        self.requires_immediate_response = requires_immediate_response
        self.created_at = datetime.utcnow()
        self.acknowledged_at: Optional[datetime] = None
        self.resolved_at: Optional[datetime] = None
        self.assigned_to: Optional[str] = None


class ConversationContext:
    """Context for maintaining conversation continuity."""
    
    def __init__(self,
                 patient_id: UUID,
                 conversation_history: List[dict[str, Any]],
                 current_topic: Optional[str],
                 emotional_state: Optional[str],
                 medical_context: dict[str, Any],
                 preferences: dict[str, Any]):
        self.patient_id = patient_id
        self.conversation_history = conversation_history
        self.current_topic = current_topic
        self.emotional_state = emotional_state
        self.medical_context = medical_context
        self.preferences = preferences
        self.last_updated = datetime.utcnow()


class FollowUpSystemService:
    """
    Follow-up action system service for handling patient response follow-ups,
    escalations, and healthcare provider notifications.
    """
    
    def __init__(self, db: Session):
        """
        Initialize follow-up system service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.message_repo = MessageRepository(db)
        self.flow_state_repo = FlowStateRepository(db)
        self.patient_repo = PatientRepository(db)
        self.ai_service = get_ai_service()
        self.sentiment_analyzer = get_ai_service()
        
        # Initialize other services (would be injected in production)
        self.message_sender = MessageSender(db)
        self.message_scheduler = MessageScheduler(db)
        
        # In-memory storage for follow-up actions and alerts (would use database in production)
        self.pending_actions: dict[UUID, FollowUpAction] = {}
        self.active_alerts: dict[UUID, EscalationAlert] = {}
        self.conversation_contexts: dict[UUID, ConversationContext] = {}
        
        logger.info("Follow-up System Service initialized")
    
    async def process_response_follow_up(self,
                                       response_result: ResponseProcessingResult) -> List[FollowUpAction]:
        """
        Process follow-up actions for a patient response.
        
        Args:
            response_result: Response processing result
            
        Returns:
            List of follow-up actions created
        """
        try:
            follow_up_actions = []
            patient_id = response_result.patient_id
            structured_response = response_result.structured_response
            
            # Update conversation context
            await self._update_conversation_context(patient_id, structured_response)
            
            # Generate empathetic follow-up message
            empathetic_action = await self._create_empathetic_follow_up(
                patient_id, structured_response
            )
            if empathetic_action:
                follow_up_actions.append(empathetic_action)
            
            # Handle medical concerns
            if structured_response.medical_concerns:
                concern_actions = await self._handle_medical_concerns(
                    patient_id, structured_response.medical_concerns, structured_response.original_message
                )
                follow_up_actions.extend(concern_actions)
            
            # Handle escalation if required
            if response_result.escalation_required:
                escalation_action = await self._create_escalation_alert(
                    patient_id, structured_response
                )
                if escalation_action:
                    follow_up_actions.append(escalation_action)
            
            # Handle specific response types
            type_specific_actions = await self._handle_response_type_specific_actions(
                patient_id, structured_response
            )
            follow_up_actions.extend(type_specific_actions)
            
            # Schedule all actions
            for action in follow_up_actions:
                await self._schedule_follow_up_action(action)
            
            logger.info(f"Created {len(follow_up_actions)} follow-up actions for patient {patient_id}")
            return follow_up_actions
            
        except Exception as e:
            logger.error(f"Failed to process response follow-up: {e}")
            raise
    
    async def _update_conversation_context(self,
                                         patient_id: UUID,
                                         structured_response: StructuredResponse) -> None:
        """Update conversation context for continuity."""
        try:
            # Get or create conversation context
            if patient_id not in self.conversation_contexts:
                self.conversation_contexts[patient_id] = ConversationContext(
                    patient_id=patient_id,
                    conversation_history=[],
                    current_topic=None,
                    emotional_state=None,
                    medical_context={},
                    preferences={}
                )
            
            context = self.conversation_contexts[patient_id]
            
            # Add to conversation history
            context.conversation_history.append({
                "timestamp": structured_response.timestamp.isoformat(),
                "message": structured_response.original_message,
                "response_type": structured_response.response_type.value,
                "sentiment": structured_response.sentiment_analysis.get("sentiment"),
                "concern_level": structured_response.concern_level.value,
                "medical_concerns": structured_response.medical_concerns
            })
            
            # Keep only last 20 messages
            context.conversation_history = context.conversation_history[-20:]
            
            # Update emotional state
            context.emotional_state = structured_response.sentiment_analysis.get("sentiment")
            
            # Update current topic based on response category
            context.current_topic = structured_response.response_category.value
            
            # Update medical context
            if structured_response.medical_concerns:
                context.medical_context["recent_concerns"] = structured_response.medical_concerns
                context.medical_context["last_concern_time"] = structured_response.timestamp.isoformat()
            
            # Update preferences from extracted data
            if structured_response.patient_preferences:
                for pref in structured_response.patient_preferences:
                    context.preferences[pref.preference_type] = {
                        "value": pref.value,
                        "confidence": pref.confidence,
                        "updated_at": pref.extracted_at.isoformat()
                    }
            
            context.last_updated = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Failed to update conversation context: {e}")
    
    async def _create_empathetic_follow_up(self,
                                         patient_id: UUID,
                                         structured_response: StructuredResponse) -> Optional[FollowUpAction]:
        """Create empathetic follow-up message based on patient response."""
        try:
            # Get patient context
            patient = self.patient_repo.get(patient_id)
            if not patient:
                return None
            
            # Build patient context for AI
            patient_context = await self._build_patient_context(patient_id, patient)
            
            # Generate empathetic response using AI
            empathetic_message = await self._generate_empathetic_message(
                structured_response, patient_context
            )
            
            if not empathetic_message:
                return None
            
            # Determine scheduling delay based on concern level
            delay_minutes = self._calculate_response_delay(structured_response.concern_level)
            scheduled_for = datetime.utcnow() + timedelta(minutes=delay_minutes)
            
            # Create follow-up action
            action = FollowUpAction(
                action_id=uuid4(),
                patient_id=patient_id,
                follow_up_type=FollowUpType.EMPATHETIC_RESPONSE,
                priority="normal" if structured_response.concern_level == ConcernLevel.LOW else "high",
                scheduled_for=scheduled_for,
                parameters={
                    "message_content": empathetic_message,
                    "original_message": structured_response.original_message,
                    "sentiment": structured_response.sentiment_analysis.get("sentiment"),
                    "concern_level": structured_response.concern_level.value
                }
            )
            
            return action
            
        except Exception as e:
            logger.error(f"Failed to create empathetic follow-up: {e}")
            return None
    
    async def _generate_empathetic_message(self,
                                         structured_response: StructuredResponse,
                                         patient_context: PatientContext) -> Optional[str]:
        """Generate empathetic message using AI."""
        try:
            # Build context for AI humanizer
            message_context = {
                "patient_message": structured_response.original_message,
                "sentiment": structured_response.sentiment_analysis.get("sentiment"),
                "concern_level": structured_response.concern_level.value,
                "medical_concerns": structured_response.medical_concerns,
                "emotional_indicators": structured_response.sentiment_analysis.get("emotional_indicators", [])
            }
            
            # Generate empathetic response
            empathetic_response = await self.ai_service.humanize_message(
                template_message="Acknowledge and respond empathetically to the patient's message",
                patient_context=patient_context,
                message_type="empathetic_response"
            )
            
            return empathetic_response.humanized_message
            
        except Exception as e:
            logger.error(f"Failed to generate empathetic message: {e}")
            return None
    
    def _calculate_response_delay(self, concern_level: ConcernLevel) -> int:
        """Calculate appropriate delay for response based on concern level."""
        delay_mapping = {
            ConcernLevel.CRITICAL: 0,      # Immediate
            ConcernLevel.HIGH: 5,          # 5 minutes
            ConcernLevel.MEDIUM: 15,       # 15 minutes
            ConcernLevel.LOW: 30           # 30 minutes
        }
        return delay_mapping.get(concern_level, 30)
    
    async def _handle_medical_concerns(self,
                                     patient_id: UUID,
                                     medical_concerns: List[str],
                                     original_message: str) -> List[FollowUpAction]:
        """Handle medical concerns with appropriate follow-up actions."""
        actions = []
        
        try:
            for concern in medical_concerns:
                # Determine concern severity and type
                concern_level = self._assess_concern_severity(concern)
                concern_type = self._classify_concern_type(concern)
                
                # Create appropriate follow-up action
                if concern_level in [ConcernLevel.HIGH, ConcernLevel.CRITICAL]:
                    # High priority medical clarification
                    action = FollowUpAction(
                        action_id=uuid4(),
                        patient_id=patient_id,
                        follow_up_type=FollowUpType.MEDICAL_CLARIFICATION,
                        priority="high",
                        scheduled_for=datetime.utcnow() + timedelta(minutes=10),
                        parameters={
                            "concern": concern,
                            "concern_type": concern_type.value if concern_type else "general",
                            "original_message": original_message,
                            "clarification_questions": self._generate_clarification_questions(concern)
                        }
                    )
                    actions.append(action)
                
                elif concern_level == ConcernLevel.MEDIUM:
                    # Provider notification
                    action = FollowUpAction(
                        action_id=uuid4(),
                        patient_id=patient_id,
                        follow_up_type=FollowUpType.PROVIDER_ALERT,
                        priority="medium",
                        scheduled_for=datetime.utcnow() + timedelta(minutes=30),
                        parameters={
                            "concern": concern,
                            "concern_type": concern_type.value if concern_type else "general",
                            "original_message": original_message,
                            "review_required": True
                        }
                    )
                    actions.append(action)
            
            return actions
            
        except Exception as e:
            logger.error(f"Failed to handle medical concerns: {e}")
            return actions
    
    def _assess_concern_severity(self, concern: str) -> ConcernLevel:
        """Assess severity of medical concern."""
        concern_lower = concern.lower()
        
        # Critical keywords
        critical_keywords = [
            "emergency", "can't breathe", "chest pain", "severe bleeding",
            "unconscious", "suicide", "overdose"
        ]
        
        # High severity keywords
        high_keywords = [
            "severe", "unbearable", "getting worse", "can't sleep",
            "vomiting", "fever", "dizzy", "confused"
        ]
        
        # Medium severity keywords
        medium_keywords = [
            "pain", "headache", "nausea", "tired", "worried",
            "side effect", "uncomfortable"
        ]
        
        if any(keyword in concern_lower for keyword in critical_keywords):
            return ConcernLevel.CRITICAL
        elif any(keyword in concern_lower for keyword in high_keywords):
            return ConcernLevel.HIGH
        elif any(keyword in concern_lower for keyword in medium_keywords):
            return ConcernLevel.MEDIUM
        else:
            return ConcernLevel.LOW
    
    def _classify_concern_type(self, concern: str) -> Optional[MedicalConcernType]:
        """Classify type of medical concern."""
        concern_lower = concern.lower()
        
        if any(word in concern_lower for word in ["pain", "hurt", "ache"]):
            return MedicalConcernType.PAIN
        elif any(word in concern_lower for word in ["nausea", "vomit", "dizzy", "rash"]):
            return MedicalConcernType.SIDE_EFFECT
        elif any(word in concern_lower for word in ["worse", "worsening", "deteriorating"]):
            return MedicalConcernType.SYMPTOM_WORSENING
        elif any(word in concern_lower for word in ["medication", "medicine", "dose"]):
            return MedicalConcernType.MEDICATION_ISSUE
        elif any(word in concern_lower for word in ["sad", "anxious", "depressed", "worried"]):
            return MedicalConcernType.EMOTIONAL_DISTRESS
        elif any(word in concern_lower for word in ["emergency", "urgent", "severe"]):
            return MedicalConcernType.EMERGENCY
        else:
            return MedicalConcernType.GENERAL_HEALTH
    
    def _generate_clarification_questions(self, concern: str) -> List[str]:
        """Generate clarification questions for medical concerns."""
        concern_lower = concern.lower()
        questions = []
        
        if "pain" in concern_lower:
            questions.extend([
                "Em uma escala de 1 a 10, como você classificaria sua dor?",
                "A dor é constante ou vem e vai?",
                "Quando a dor começou?"
            ])
        
        if "nausea" in concern_lower or "vomit" in concern_lower:
            questions.extend([
                "A náusea está relacionada às refeições?",
                "Você conseguiu manter líquidos?",
                "Isso começou após tomar algum medicamento?"
            ])
        
        if "medication" in concern_lower:
            questions.extend([
                "Qual medicamento está causando preocupação?",
                "Você tomou a dose correta?",
                "Quando foi a última vez que tomou?"
            ])
        
        # Default questions if no specific type identified
        if not questions:
            questions.extend([
                "Pode me contar mais detalhes sobre isso?",
                "Quando isso começou?",
                "Isso está afetando suas atividades diárias?"
            ])
        
        return questions[:3]  # Return max 3 questions
    
    async def _create_escalation_alert(self,
                                     patient_id: UUID,
                                     structured_response: StructuredResponse) -> Optional[FollowUpAction]:
        """Create escalation alert for healthcare providers."""
        try:
            # Determine escalation level
            escalation_level = self._determine_escalation_level(structured_response)
            
            if escalation_level == EscalationLevel.NONE:
                return None
            
            # Create escalation alert
            alert = EscalationAlert(
                alert_id=uuid4(),
                patient_id=patient_id,
                escalation_level=escalation_level,
                concern_type=self._get_primary_concern_type(structured_response.medical_concerns),
                description=self._create_alert_description(structured_response),
                original_message=structured_response.original_message,
                recommended_actions=self._generate_recommended_actions(structured_response),
                notification_channels=self._select_notification_channels(escalation_level),
                requires_immediate_response=(escalation_level in [EscalationLevel.CRITICAL, EscalationLevel.EMERGENCY])
            )
            
            # Store alert
            self.active_alerts[alert.alert_id] = alert
            
            # Create follow-up action for escalation
            action = FollowUpAction(
                action_id=uuid4(),
                patient_id=patient_id,
                follow_up_type=FollowUpType.ESCALATION_NOTIFICATION,
                priority="critical" if escalation_level == EscalationLevel.EMERGENCY else "high",
                scheduled_for=datetime.utcnow(),  # Immediate
                parameters={
                    "alert_id": str(alert.alert_id),
                    "escalation_level": escalation_level.value,
                    "notification_channels": [ch.value for ch in alert.notification_channels],
                    "requires_immediate_response": alert.requires_immediate_response
                }
            )
            
            return action
            
        except Exception as e:
            logger.error(f"Failed to create escalation alert: {e}")
            return None    

    def _determine_escalation_level(self, structured_response: StructuredResponse) -> EscalationLevel:
        """Determine appropriate escalation level."""
        concern_level = structured_response.concern_level
        medical_concerns = structured_response.medical_concerns
        
        # Emergency escalation
        emergency_keywords = ["emergency", "can't breathe", "chest pain", "suicide"]
        if any(keyword in structured_response.original_message.lower() for keyword in emergency_keywords):
            return EscalationLevel.EMERGENCY
        
        # Critical escalation
        if concern_level == ConcernLevel.CRITICAL:
            return EscalationLevel.CRITICAL
        
        # High escalation
        if concern_level == ConcernLevel.HIGH or len(medical_concerns) > 2:
            return EscalationLevel.HIGH
        
        # Medium escalation
        if concern_level == ConcernLevel.MEDIUM or len(medical_concerns) > 0:
            return EscalationLevel.MEDIUM
        
        return EscalationLevel.NONE
    
    def _get_primary_concern_type(self, medical_concerns: List[str]) -> MedicalConcernType:
        """Get primary concern type from list of concerns."""
        if not medical_concerns:
            return MedicalConcernType.GENERAL_HEALTH
        
        # Use the first concern to determine type
        primary_concern = medical_concerns[0]
        return self._classify_concern_type(primary_concern) or MedicalConcernType.GENERAL_HEALTH
    
    def _create_alert_description(self, structured_response: StructuredResponse) -> str:
        """Create description for escalation alert."""
        sentiment = structured_response.sentiment_analysis.get("sentiment", "neutral")
        concern_level = structured_response.concern_level.value
        
        description = f"Patient response with {concern_level} concern level and {sentiment} sentiment. "
        
        if structured_response.medical_concerns:
            concerns_text = ", ".join(structured_response.medical_concerns[:3])
            description += f"Medical concerns: {concerns_text}. "
        
        if structured_response.requires_attention:
            description += "Requires immediate attention. "
        
        return description.strip()
    
    def _generate_recommended_actions(self, structured_response: StructuredResponse) -> List[str]:
        """Generate recommended actions for healthcare providers."""
        actions = []
        
        concern_level = structured_response.concern_level
        medical_concerns = structured_response.medical_concerns
        
        if concern_level == ConcernLevel.CRITICAL:
            actions.extend([
                "Contact patient immediately",
                "Assess need for emergency care",
                "Document response in medical record"
            ])
        elif concern_level == ConcernLevel.HIGH:
            actions.extend([
                "Review patient response within 2 hours",
                "Consider scheduling urgent consultation",
                "Evaluate medication adjustments"
            ])
        elif concern_level == ConcernLevel.MEDIUM:
            actions.extend([
                "Review patient response within 24 hours",
                "Consider follow-up call",
                "Monitor for symptom progression"
            ])
        
        # Add concern-specific actions
        if any("pain" in concern.lower() for concern in medical_concerns):
            actions.append("Assess pain management strategy")
        
        if any("medication" in concern.lower() for concern in medical_concerns):
            actions.append("Review medication compliance and side effects")
        
        if any("emotional" in concern.lower() or "anxious" in concern.lower() for concern in medical_concerns):
            actions.append("Consider mental health support referral")
        
        return actions[:5]  # Return max 5 actions
    
    def _select_notification_channels(self, escalation_level: EscalationLevel) -> List[NotificationChannel]:
        """Select appropriate notification channels based on escalation level."""
        if escalation_level == EscalationLevel.EMERGENCY:
            return [
                NotificationChannel.PHONE_CALL,
                NotificationChannel.SMS,
                NotificationChannel.DASHBOARD_ALERT,
                NotificationChannel.PUSH_NOTIFICATION
            ]
        elif escalation_level == EscalationLevel.CRITICAL:
            return [
                NotificationChannel.SMS,
                NotificationChannel.DASHBOARD_ALERT,
                NotificationChannel.PUSH_NOTIFICATION,
                NotificationChannel.EMAIL
            ]
        elif escalation_level == EscalationLevel.HIGH:
            return [
                NotificationChannel.DASHBOARD_ALERT,
                NotificationChannel.PUSH_NOTIFICATION,
                NotificationChannel.EMAIL
            ]
        elif escalation_level == EscalationLevel.MEDIUM:
            return [
                NotificationChannel.DASHBOARD_ALERT,
                NotificationChannel.EMAIL
            ]
        else:
            return [NotificationChannel.DASHBOARD_ALERT]
    
    async def _handle_response_type_specific_actions(self,
                                                   patient_id: UUID,
                                                   structured_response: StructuredResponse) -> List[FollowUpAction]:
        """Handle response type specific follow-up actions."""
        actions = []
        
        try:
            response_category = structured_response.response_category
            extracted_data = structured_response.extracted_data
            
            # Handle pain scale responses
            if "pain_scale" in extracted_data:
                pain_level = extracted_data["pain_scale"]
                if pain_level >= 7:
                    action = FollowUpAction(
                        action_id=uuid4(),
                        patient_id=patient_id,
                        follow_up_type=FollowUpType.MEDICAL_CLARIFICATION,
                        priority="high",
                        scheduled_for=datetime.utcnow() + timedelta(minutes=15),
                        parameters={
                            "pain_level": pain_level,
                            "follow_up_questions": [
                                "A dor está interferindo em suas atividades?",
                                "Você tomou algum analgésico?",
                                "A dor mudou desde ontem?"
                            ]
                        }
                    )
                    actions.append(action)
            
            # Handle medication mentions
            if extracted_data.get("medication_mentioned"):
                action = FollowUpAction(
                    action_id=uuid4(),
                    patient_id=patient_id,
                    follow_up_type=FollowUpType.MEDICATION_GUIDANCE,
                    priority="normal",
                    scheduled_for=datetime.utcnow() + timedelta(hours=2),
                    parameters={
                        "medication_context": structured_response.original_message,
                        "guidance_type": "general_medication_support"
                    }
                )
                actions.append(action)
            
            # Handle negative mood indicators
            if extracted_data.get("mood_indicator") == "negative":
                action = FollowUpAction(
                    action_id=uuid4(),
                    patient_id=patient_id,
                    follow_up_type=FollowUpType.EMOTIONAL_SUPPORT,
                    priority="normal",
                    scheduled_for=datetime.utcnow() + timedelta(hours=1),
                    parameters={
                        "emotional_state": "negative",
                        "support_type": "encouragement_and_resources"
                    }
                )
                actions.append(action)
            
            # Handle positive responses with encouragement
            elif structured_response.sentiment_analysis.get("sentiment") == "positive":
                action = FollowUpAction(
                    action_id=uuid4(),
                    patient_id=patient_id,
                    follow_up_type=FollowUpType.TREATMENT_ENCOURAGEMENT,
                    priority="low",
                    scheduled_for=datetime.utcnow() + timedelta(hours=4),
                    parameters={
                        "encouragement_type": "positive_reinforcement",
                        "progress_acknowledgment": True
                    }
                )
                actions.append(action)
            
            return actions
            
        except Exception as e:
            logger.error(f"Failed to handle response type specific actions: {e}")
            return actions
    
    async def _schedule_follow_up_action(self, action: FollowUpAction) -> bool:
        """Schedule a follow-up action for execution."""
        try:
            # Store action
            self.pending_actions[action.action_id] = action
            
            # Schedule execution based on action type
            if action.follow_up_type == FollowUpType.EMPATHETIC_RESPONSE:
                await self._schedule_message_action(action)
            elif action.follow_up_type == FollowUpType.ESCALATION_NOTIFICATION:
                await self._schedule_escalation_action(action)
            elif action.follow_up_type == FollowUpType.PROVIDER_ALERT:
                await self._schedule_provider_notification(action)
            else:
                # Generic scheduling
                await self._schedule_generic_action(action)
            
            logger.info(f"Scheduled follow-up action {action.action_id} for patient {action.patient_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to schedule follow-up action: {e}")
            return False
    
    async def _schedule_message_action(self, action: FollowUpAction) -> None:
        """Schedule a message-based follow-up action."""
        try:
            message_content = action.parameters.get("message_content")
            if not message_content:
                return
            
            # Create message
            message = Message(
                patient_id=action.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=message_content,
                status=MessageStatus.PENDING,
                scheduled_for=action.scheduled_for,
                message_metadata={
                    "follow_up_action_id": str(action.action_id),
                    "follow_up_type": action.follow_up_type.value,
                    "priority": action.priority,
                    "ai_generated": True
                }
            )
            
            # Save message
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)
            
            # Schedule with message scheduler
            await self.message_scheduler.schedule_message(
                message_id=message.id,
                send_time=action.scheduled_for,
                priority=action.priority
            )
            
        except Exception as e:
            logger.error(f"Failed to schedule message action: {e}")
            self.db.rollback()
    
    async def _schedule_escalation_action(self, action: FollowUpAction) -> None:
        """Schedule an escalation notification action."""
        try:
            alert_id = action.parameters.get("alert_id")
            if not alert_id:
                return
            
            alert = self.active_alerts.get(UUID(alert_id))
            if not alert:
                return
            
            # Send notifications through configured channels
            for channel in alert.notification_channels:
                await self._send_provider_notification(
                    patient_id=action.patient_id,
                    alert=alert,
                    channel=channel
                )
            
            # Mark action as executed
            action.executed_at = datetime.utcnow()
            action.status = "executed"
            action.execution_result = {
                "notifications_sent": len(alert.notification_channels),
                "channels": [ch.value for ch in alert.notification_channels]
            }
            
        except Exception as e:
            logger.error(f"Failed to schedule escalation action: {e}")
    
    async def _schedule_provider_notification(self, action: FollowUpAction) -> None:
        """Schedule a provider notification action."""
        try:
            # Create provider notification
            notification_data = {
                "patient_id": str(action.patient_id),
                "concern": action.parameters.get("concern"),
                "concern_type": action.parameters.get("concern_type"),
                "original_message": action.parameters.get("original_message"),
                "priority": action.priority,
                "created_at": action.created_at.isoformat()
            }
            
            # Send notification (implementation would depend on notification system)
            await self._send_provider_notification(
                patient_id=action.patient_id,
                notification_data=notification_data,
                channel=NotificationChannel.DASHBOARD_ALERT
            )
            
            # Mark as executed
            action.executed_at = datetime.utcnow()
            action.status = "executed"
            
        except Exception as e:
            logger.error(f"Failed to schedule provider notification: {e}")
    
    async def _schedule_generic_action(self, action: FollowUpAction) -> None:
        """Schedule a generic follow-up action."""
        try:
            # For now, just mark as scheduled
            # In production, this would integrate with task scheduling system
            action.status = "scheduled"
            
            logger.info(f"Generic action {action.action_id} scheduled for {action.scheduled_for}")
            
        except Exception as e:
            logger.error(f"Failed to schedule generic action: {e}")
    
    async def _send_provider_notification(self,
                                        patient_id: UUID,
                                        notification_data: Union[Dict[str, Any], EscalationAlert],
                                        channel: NotificationChannel) -> bool:
        """Send notification to healthcare provider."""
        try:
            # Get patient information
            patient = self.patient_repo.get(patient_id)
            if not patient:
                return False
            
            # Format notification based on channel
            if isinstance(notification_data, EscalationAlert):
                alert = notification_data
                notification_content = self._format_alert_notification(alert, patient)
            else:
                notification_content = self._format_generic_notification(notification_data, patient)
            
            # Send through appropriate channel
            if channel == NotificationChannel.EMAIL:
                success = await self._send_email_notification(notification_content)
            elif channel == NotificationChannel.SMS:
                success = await self._send_sms_notification(notification_content)
            elif channel == NotificationChannel.DASHBOARD_ALERT:
                success = await self._send_dashboard_alert(notification_content)
            elif channel == NotificationChannel.PUSH_NOTIFICATION:
                success = await self._send_push_notification(notification_content)
            else:
                success = False
            
            logger.info(f"Sent {channel.value} notification for patient {patient_id}: {success}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to send provider notification: {e}")
            return False
    
    def _format_alert_notification(self, alert: EscalationAlert, patient: Patient) -> Dict[str, Any]:
        """Format escalation alert for notification."""
        return {
            "type": "escalation_alert",
            "patient_name": patient.name,
            "patient_id": str(alert.patient_id),
            "escalation_level": alert.escalation_level.value,
            "concern_type": alert.concern_type.value,
            "description": alert.description,
            "original_message": alert.original_message,
            "recommended_actions": alert.recommended_actions,
            "requires_immediate_response": alert.requires_immediate_response,
            "created_at": alert.created_at.isoformat()
        }
    
    def _format_generic_notification(self, notification_data: Dict[str, Any], patient: Patient) -> Dict[str, Any]:
        """Format generic notification."""
        return {
            "type": "provider_notification",
            "patient_name": patient.name,
            **notification_data
        }
    
    async def _send_email_notification(self, notification_content: Dict[str, Any]) -> bool:
        """Send email notification (placeholder implementation)."""
        # In production, integrate with email service
        logger.info(f"Email notification: {notification_content['type']} for {notification_content.get('patient_name')}")
        return True
    
    async def _send_sms_notification(self, notification_content: Dict[str, Any]) -> bool:
        """Send SMS notification (placeholder implementation)."""
        # In production, integrate with SMS service
        logger.info(f"SMS notification: {notification_content['type']} for {notification_content.get('patient_name')}")
        return True
    
    async def _send_dashboard_alert(self, notification_content: Dict[str, Any]) -> bool:
        """Send dashboard alert (placeholder implementation)."""
        # In production, integrate with dashboard system
        logger.info(f"Dashboard alert: {notification_content['type']} for {notification_content.get('patient_name')}")
        return True
    
    async def _send_push_notification(self, notification_content: Dict[str, Any]) -> bool:
        """Send push notification (placeholder implementation)."""
        # In production, integrate with push notification service
        logger.info(f"Push notification: {notification_content['type']} for {notification_content.get('patient_name')}")
        return True
    
    async def _build_patient_context(self, patient_id: UUID, patient: Patient) -> PatientContext:
        """Build patient context for AI processing."""
        try:
            # Get recent messages
            recent_messages = self.message_repo.get_conversation_history(patient_id, limit=5)
            recent_responses = [
                msg.content for msg in recent_messages 
                if msg.direction == MessageDirection.INBOUND and msg.content
            ]
            
            # Get flow state
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            treatment_day = flow_state.current_step if flow_state else 1
            
            return PatientContext(
                patient_id=str(patient_id),
                name=patient.name,
                treatment_type=getattr(patient, 'treatment_type', 'general'),
                treatment_day=treatment_day,
                age=getattr(patient, 'age', None),
                recent_responses=recent_responses,
                medical_history=getattr(patient, 'medical_history', {}),
                preferences=getattr(patient, 'preferences', {})
            )
            
        except Exception as e:
            logger.error(f"Failed to build patient context: {e}")
            raise
    
    async def execute_pending_actions(self, limit: int = 100) -> Dict[str, Any]:
        """Execute pending follow-up actions."""
        try:
            executed_count = 0
            failed_count = 0
            current_time = datetime.utcnow()
            
            # Get actions ready for execution
            ready_actions = [
                action for action in self.pending_actions.values()
                if action.status == "pending" and action.scheduled_for <= current_time
            ][:limit]
            
            for action in ready_actions:
                try:
                    success = await self._execute_action(action)
                    if success:
                        executed_count += 1
                        action.status = "executed"
                        action.executed_at = current_time
                    else:
                        failed_count += 1
                        action.status = "failed"
                        
                except Exception as e:
                    logger.error(f"Failed to execute action {action.action_id}: {e}")
                    failed_count += 1
                    action.status = "failed"
            
            return {
                "executed": executed_count,
                "failed": failed_count,
                "total_pending": len([a for a in self.pending_actions.values() if a.status == "pending"])
            }
            
        except Exception as e:
            logger.error(f"Failed to execute pending actions: {e}")
            return {"error": str(e)}
    
    async def _execute_action(self, action: FollowUpAction) -> bool:
        """Execute a specific follow-up action."""
        try:
            if action.follow_up_type == FollowUpType.EMPATHETIC_RESPONSE:
                return await self._execute_message_action(action)
            elif action.follow_up_type == FollowUpType.ESCALATION_NOTIFICATION:
                return await self._execute_escalation_action(action)
            elif action.follow_up_type == FollowUpType.PROVIDER_ALERT:
                return await self._execute_provider_alert(action)
            else:
                # Generic execution
                logger.info(f"Executed generic action {action.action_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to execute action {action.action_id}: {e}")
            return False
    
    async def _execute_message_action(self, action: FollowUpAction) -> bool:
        """Execute message-based action."""
        try:
            # Message should already be scheduled, just mark as executed
            action.execution_result = {"message_scheduled": True}
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute message action: {e}")
            return False
    
    async def _execute_escalation_action(self, action: FollowUpAction) -> bool:
        """Execute escalation action."""
        try:
            # Escalation should already be sent, just mark as executed
            action.execution_result = {"escalation_sent": True}
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute escalation action: {e}")
            return False
    
    async def _execute_provider_alert(self, action: FollowUpAction) -> bool:
        """Execute provider alert action."""
        try:
            # Alert should already be sent, just mark as executed
            action.execution_result = {"alert_sent": True}
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute provider alert: {e}")
            return False
    
    async def get_active_alerts(self, patient_id: Optional[UUID] = None) -> List[EscalationAlert]:
        """Get active escalation alerts."""
        try:
            alerts = list(self.active_alerts.values())
            
            if patient_id:
                alerts = [alert for alert in alerts if alert.patient_id == patient_id]
            
            # Filter for unresolved alerts
            active_alerts = [alert for alert in alerts if alert.resolved_at is None]
            
            return active_alerts
            
        except Exception as e:
            logger.error(f"Failed to get active alerts: {e}")
            return []
    
    async def acknowledge_alert(self, alert_id: UUID, acknowledged_by: str) -> bool:
        """Acknowledge an escalation alert."""
        try:
            alert = self.active_alerts.get(alert_id)
            if not alert:
                return False
            
            alert.acknowledged_at = datetime.utcnow()
            alert.assigned_to = acknowledged_by
            
            logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to acknowledge alert: {e}")
            return False
    
    async def resolve_alert(self, alert_id: UUID, resolved_by: str) -> bool:
        """Resolve an escalation alert."""
        try:
            alert = self.active_alerts.get(alert_id)
            if not alert:
                return False
            
            alert.resolved_at = datetime.utcnow()
            if not alert.assigned_to:
                alert.assigned_to = resolved_by
            
            logger.info(f"Alert {alert_id} resolved by {resolved_by}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to resolve alert: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on follow-up system."""
        try:
            return {
                "service": "FollowUpSystemService",
                "timestamp": datetime.utcnow().isoformat(),
                "healthy": True,
                "stats": {
                    "pending_actions": len([a for a in self.pending_actions.values() if a.status == "pending"]),
                    "active_alerts": len([a for a in self.active_alerts.values() if a.resolved_at is None]),
                    "total_actions": len(self.pending_actions),
                    "total_alerts": len(self.active_alerts)
                }
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "service": "FollowUpSystemService",
                "timestamp": datetime.utcnow().isoformat(),
                "healthy": False,
                "error": str(e)
            }


# Global service instance
_follow_up_system_service: Optional[FollowUpSystemService] = None


def get_follow_up_system_service(db: Session) -> FollowUpSystemService:
    """
    Get follow-up system service instance.
    
    Args:
        db: Database session
        
    Returns:
        FollowUpSystemService instance
    """
    return FollowUpSystemService(db)