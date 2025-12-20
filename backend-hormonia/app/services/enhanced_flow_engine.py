"""
FlowEngine - AI-powered flow execution engine.
Pure execution engine inheriting shared functionality from FlowCore.
Focuses only on AI/ML operations: message generation, response processing, and conversation memory.
"""

import logging
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone
from uuid import UUID

from app.services.flow_core import FlowCore
from app.services.flow.types import FlowType
from app.services.template_loader import MessageTemplate, EnhancedTemplateLoader
from app.models.patient import Patient
from app.models.flow import PatientFlowState, FlowKind, FlowTemplateVersion
from app.models.message import Message, MessageDirection
from app.integrations.gemini_client import GeminiClient, get_gemini_client
from app.services.conversation_memory import ConversationMemory, get_conversation_memory
from app.services.platform_synchronization import PlatformSynchronizationService
from app.services.unified_cache import UnifiedCacheService
from app.exceptions import NotFoundError
from app.utils.db_retry import with_db_retry

logger = logging.getLogger(__name__)


class FlowContext:
    """Context for flow execution with patient and conversation data."""

    def __init__(
        self,
        patient: Patient,
        flow_state: PatientFlowState,
        current_day: int,
        flow_type: str = None,  # New parameter for flow type
        conversation_history: List[str] = None,
        communication_preferences: dict[str, Any] = None,
        medical_context: dict[str, Any] = None,
    ):
        self.patient = patient
        self.flow_state = flow_state
        self.current_day = current_day
        self.flow_type = flow_type or "unknown"  # Store flow type
        self.conversation_history = conversation_history or []
        self.communication_preferences = communication_preferences or {}
        self.medical_context = medical_context or {}
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "patient_id": str(self.patient.id),
            "patient_name": self.patient.name,
            "flow_type": self.flow_type,  # Use stored flow type
            "current_day": self.current_day,
            "treatment_day": self._calculate_treatment_day(),
            "conversation_history": self.conversation_history,
            "communication_preferences": self.communication_preferences,
            "medical_context": self.medical_context,
            "timestamp": self.timestamp.isoformat(),
        }

    def _calculate_treatment_day(self) -> int:
        """Calculate treatment day based on enrollment date."""
        if (
            hasattr(self.patient, "treatment_start_date")
            and self.patient.treatment_start_date
        ):
            delta = (
                datetime.now(timezone.utc).date() - self.patient.treatment_start_date
            )
            return delta.days + 1
        return 1


class EnhancedFlowEngine(FlowCore):
    """
    AI-powered flow execution engine.
    Inherits all shared flow operations from FlowCore.
    Focuses on AI/ML operations: message generation, response processing, conversation memory.

    **REFACTORED**: Now inherits from FlowCore to eliminate duplication.
    This class now contains only AI/ML specific functionality:
    - AI message generation and personalization
    - Patient response processing and sentiment analysis
    - Conversation memory integration
    - Gemini AI client integration
    """

    def __init__(
        self,
        db: Any,
        gemini_client: Optional[GeminiClient] = None,
        conversation_memory: Optional[ConversationMemory] = None,
        platform_sync: Optional[PlatformSynchronizationService] = None,
        template_loader: Optional[EnhancedTemplateLoader] = None,
        template_cache: Optional[UnifiedCacheService] = None,
    ):
        """
        Initialize FlowEngine with AI services.

        Args:
            db: Database session
            gemini_client: Gemini AI client (optional)
            conversation_memory: Conversation memory system (optional)
            platform_sync: Platform synchronization service (optional)
            template_loader: Template loader service (optional)
            template_cache: Template cache service (optional)
        """
        # Initialize shared functionality from FlowCore
        super().__init__(db, platform_sync, template_loader, template_cache)

        # Initialize AI/ML specific services
        self.gemini_client = gemini_client or get_gemini_client()
        self.conversation_memory = conversation_memory or get_conversation_memory()

        logger.info("Enhanced FlowEngine initialized with AI integration")

        # Intents related to quiz invitation/warmup to enforce light variation
        self.QUIZ_INVITE_INTENTS: set[str] = {
            "quiz_preparation_gentle",
            "quiz_warmup_final",
            "monthly_quiz_trigger",
            "quiz_invitation",
            "quiz_intro",
            "quiz_reminder",
        }

    def _get_flow_type_from_state(self, flow_state: PatientFlowState) -> str:
        """
        Helper method to get flow_type from a PatientFlowState using template_version_id.

        Args:
            flow_state: The patient flow state

        Returns:
            The flow_type string
        """
        template_version = (
            self.db.query(FlowTemplateVersion)
            .filter(FlowTemplateVersion.id == flow_state.template_version_id)
            .first()
        )

        if not template_version:
            logger.error(f"Template version not found for flow state {flow_state.id}")
            return "unknown"

        flow_kind = (
            self.db.query(FlowKind)
            .filter(FlowKind.id == template_version.kind_id)
            .first()
        )

        if not flow_kind:
            logger.error(
                f"Flow kind not found for template version {template_version.id}"
            )
            return "unknown"

        return flow_kind.flow_type

    # =============================================================================
    # AI MESSAGE GENERATION (FlowEngine specific - only AI/ML operations)
    # NOTE: Main generate_flow_message method is defined later after helper methods
    # =============================================================================

    # =============================================================================
    # AI RESPONSE PROCESSING (FlowEngine specific - only AI/ML operations)
    # =============================================================================

    def _calculate_engagement_score(
        self, sentiment_analysis: Dict[str, Any], response_text: str
    ) -> float:
        """
        Calculate engagement score based on sentiment and response characteristics.

        Score range: 0.0 to 1.0
        Base: 0.5
        """
        score = 0.5

        # Sentiment impact
        sentiment = sentiment_analysis.get("sentiment", "neutral")
        if sentiment == "positive":
            score += 0.2
        elif sentiment == "negative":
            score -= 0.1

        # Length impact
        length = len(response_text)
        if length > 50:
            score += 0.1
        elif length > 10:
            score += 0.05

        # Emotional indicators impact
        indicators = sentiment_analysis.get("emotional_indicators", [])
        score += min(len(indicators) * 0.05, 0.2)

        return max(0.0, min(1.0, score))

    def _get_few_shot_examples(self, intent: str) -> List[Dict[str, str]]:
        """Get few-shot examples based on intent."""
        # Placeholder for example management service
        examples = {
            "greeting": [
                {
                    "input": "Olá [nome]",
                    "output": "Oi [nome], que bom falar com você! Como está se sentindo?",
                },
                {
                    "input": "Bom dia [nome]",
                    "output": "Bom dia, [nome]! Espero que seu dia esteja sendo tranquilo.",
                },
            ],
            "check_in": [
                {
                    "input": "Como você está?",
                    "output": "Me conta, como você está se sentindo hoje? Alguma novidade?",
                },
                {
                    "input": "Sentiu algum efeito colateral?",
                    "output": "Você notou algo diferente no seu corpo ou humor desde nossa última conversa?",
                },
            ],
        }
        return examples.get(intent, [])

    @with_db_retry(max_retries=3)
    async def generate_flow_message(
        self,
        patient_id: UUID,
        day: Optional[int] = None,
        message_template: Optional[MessageTemplate] = None,
    ) -> str:
        """
        Generate personalized flow message using AI and database templates.

        Args:
            patient_id: Patient UUID
            day: Specific day to generate message for (optional)
            message_template: Message template to personalize (optional, will load from DB if not provided)

        Returns:
            Personalized message text
        """
        try:
            # Get patient and flow context
            patient = self.patient_repo.get(patient_id)
            if not patient:
                raise NotFoundError(f"Patient {patient_id} not found")

            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            if not flow_state:
                raise NotFoundError(f"No active flow for patient {patient_id}")

            # Determine current day if not provided
            if day is None:
                day = await self.calculate_patient_day(patient_id)

            # Get flow type from state
            flow_type_str = self._get_flow_type_from_state(flow_state)

            # Load message template from database if not provided
            if message_template is None:
                try:
                    flow_type = FlowType(flow_type_str)
                except ValueError:
                    # If flow_type_str doesn't match enum, use a default
                    flow_type = FlowType.INITIAL_15_DAYS
                message_template = await self.get_message_template_for_day(
                    flow_type, day
                )
                if not message_template:
                    # Fallback to simple message
                    return f"Olá {patient.name}, como você está hoje? (Dia {day})"

            # Build flow context
            conversation_history = await self._get_conversation_history(patient_id)
            communication_preferences = (
                await self.conversation_memory.get_communication_preferences(patient_id)
            )

            flow_context = FlowContext(
                patient=patient,
                flow_state=flow_state,
                current_day=day,
                flow_type=flow_type_str,  # Pass the resolved flow type
                conversation_history=conversation_history,
                communication_preferences=communication_preferences,
                medical_context={
                    "treatment_type": getattr(
                        patient, "treatment_type", "hormone_therapy"
                    )
                },
            )

            # Check for repetition before generating
            repetition_check = await self.conversation_memory.check_message_repetition(
                patient_id, message_template.base_content
            )

            # Get few-shot examples based on intent
            intent = getattr(message_template, "intent", "check_in")
            few_shot_examples = self._get_few_shot_examples(intent)

            # Generate personalized message
            if repetition_check["recommendation"] in ["regenerate", "modify"]:
                # Use AI to create variation
                if (
                    hasattr(message_template, "variations")
                    and message_template.variations
                ):
                    # Use one of the pre-defined variations
                    import random

                    base_content = random.choice(message_template.variations)
                else:
                    base_content = message_template.base_content

                personalized_message = (
                    await self.gemini_client.generate_varied_question(
                        base_content,
                        conversation_history[-5:],  # Last 5 messages
                        flow_context.to_dict(),
                        few_shot_examples=few_shot_examples,
                    )
                )
            else:
                # Use AI to humanize the template
                personalized_message = await self.gemini_client.humanize_flow_message(
                    template=message_template.base_content,
                    patient_name=patient.name,
                    patient_context=flow_context.to_dict(),
                    conversation_history=conversation_history,
                    personalization_hints=getattr(
                        message_template, "personalization_hints", []
                    ),
                    few_shot_examples=few_shot_examples,
                )

            # Enforce small variation for quiz invitations to reduce repetition
            if intent in self.QUIZ_INVITE_INTENTS:
                try:
                    tone_hint = self._tone_for_time_of_day()
                    varied = await self.gemini_client.generate_varied_question(
                        personalized_message or message_template.base_content,
                        conversation_history[-5:],
                        {
                            **flow_context.to_dict(),
                            "tone_hint": tone_hint,
                            "variation_target": "quiz_invite",
                        },
                        few_shot_examples=few_shot_examples,
                    )
                    if varied:
                        personalized_message = varied
                except Exception as e:
                    # Keep original personalized_message on any AI variation failure
                    logger.warning(f"AI message variation failed: {e}", exc_info=True)

            # Store message pattern for future anti-repetition
            await self.conversation_memory.store_message_pattern(
                patient_id, personalized_message
            )

            logger.info(
                f"Generated personalized message for patient {patient_id}, day {day}"
            )
            return personalized_message

        except Exception as e:
            logger.error(f"Failed to generate flow message: {e}")
            # Fallback to basic template personalization
            if message_template and hasattr(message_template, "base_content"):
                return message_template.base_content.replace(
                    "[nome]", patient.name if patient else ""
                )
            return f"Olá {patient.name if patient else ''}, como você está hoje?"

    @with_db_retry(max_retries=3)
    async def process_patient_response(
        self, patient_id: UUID, response_text: str
    ) -> dict[str, Any]:
        """
        Process patient response with AI analysis.

        Args:
            patient_id: Patient UUID
            response_text: Patient's response text

        Returns:
            Response processing result
        """
        try:
            # Get patient context
            patient = self.patient_repo.get(patient_id)
            if not patient:
                raise NotFoundError(f"Patient {patient_id} not found")

            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            if not flow_state:
                logger.warning(
                    f"No active flow for patient {patient_id}, processing response anyway"
                )

            # Analyze response sentiment
            patient_context = {
                "name": patient.name,
                "treatment_type": getattr(patient, "treatment_type", "hormone_therapy"),
                "current_day": await self.calculate_patient_day(patient_id),
            }

            sentiment_analysis = await self.gemini_client.analyze_response_sentiment(
                response_text, patient_context
            )

            # Calculate engagement score and update memory
            engagement_score = self._calculate_engagement_score(
                sentiment_analysis, response_text
            )
            await self.conversation_memory.update_last_pattern_engagement(
                patient_id, engagement_score
            )

            # Store response pattern
            await self.conversation_memory.store_message_pattern(
                patient_id, response_text
            )

            # Generate empathetic follow-up if needed
            follow_up_message = None
            if sentiment_analysis.get("requires_attention") or sentiment_analysis.get(
                "medical_concerns"
            ):
                conversation_history = await self._get_conversation_history(patient_id)
                follow_up_message = (
                    await self.gemini_client.create_empathetic_follow_up(
                        response_text, conversation_history, patient_context
                    )
                )

            # Update flow state with response data
            if flow_state:
                flow_state.state_data = flow_state.state_data or {}
                flow_state.state_data["last_response"] = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "sentiment": sentiment_analysis,
                    "text_length": len(response_text),
                    "engagement_score": engagement_score,
                }
                self.db.commit()

            return {
                "status": "processed",
                "patient_id": str(patient_id),
                "sentiment_analysis": sentiment_analysis,
                "engagement_score": engagement_score,
                "follow_up_message": follow_up_message,
                "requires_attention": sentiment_analysis.get(
                    "requires_attention", False
                ),
                "medical_concerns": sentiment_analysis.get("medical_concerns", False),
            }

        except Exception as e:
            logger.error(f"Failed to process patient response: {e}")
            return {"status": "error", "patient_id": str(patient_id), "error": str(e)}

    # =============================================================================
    # AI-ENHANCED HEALTH CHECKS (FlowEngine specific)
    # =============================================================================

    @with_db_retry(max_retries=3)
    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on FlowEngine components.
        Extends FlowCore health check with AI-specific components.

        Returns:
            Health check results
        """
        # Get base health check from FlowCore
        results = await super().health_check()

        # Add AI-specific health checks
        results["service"] = "EnhancedFlowEngine"
        results["gemini_client"] = False
        results["conversation_memory"] = False

        try:
            # Test Gemini client
            results["gemini_client"] = await self.gemini_client.health_check()
        except Exception as e:
            logger.error(f"Gemini client health check failed: {e}")
            results["gemini_client"] = False

        try:
            # Test conversation memory
            results[
                "conversation_memory"
            ] = await self.conversation_memory.health_check()
        except Exception as e:
            logger.error(f"Conversation memory health check failed: {e}")
            results["conversation_memory"] = False

        # Update overall health status
        results["overall_healthy"] = all(
            [
                results["flow_core"],
                results["database"],
                results["template_cache"],
                results["gemini_client"],
                results["conversation_memory"],
            ]
        )

        return results

    # =============================================================================
    # PRIVATE AI HELPER METHODS (FlowEngine specific)
    # =============================================================================

    @with_db_retry(max_retries=3)
    async def _get_conversation_history(
        self, patient_id: UUID, limit: int = 10
    ) -> List[str]:
        """
        Get recent conversation history for patient.

        Retrieves the most recent messages between the clinic and patient,
        formatted for AI context. Messages are ordered newest-first but
        returned in chronological order (oldest-first) for natural context.

        Args:
            patient_id: UUID of the patient
            limit: Maximum number of messages to retrieve (default 10)

        Returns:
            List of formatted message strings, e.g.:
            - "Paciente: Bom dia, estou com uma dúvida..."
            - "Clínica: Olá! Como posso ajudar?"
        """
        try:
            # Query recent messages for this patient
            messages = (
                self.db.query(Message)
                .filter(
                    Message.patient_id == patient_id,
                    Message.content.isnot(None),  # Only messages with text content
                    Message.content != "",  # Exclude empty messages
                )
                .order_by(
                    Message.created_at.desc()  # Most recent first
                )
                .limit(limit)
                .all()
            )

            if not messages:
                logger.debug(f"No conversation history found for patient {patient_id}")
                return []

            # Format messages with direction prefix
            # Reverse to get chronological order (oldest first)
            formatted_history = []
            for msg in reversed(messages):
                if msg.direction == MessageDirection.INBOUND:
                    prefix = "Paciente"
                else:
                    prefix = "Clínica"

                # Truncate very long messages for AI context efficiency
                content = msg.content[:500] if len(msg.content) > 500 else msg.content
                formatted_history.append(f"{prefix}: {content}")

            logger.debug(
                f"Retrieved {len(formatted_history)} messages for patient {patient_id}"
            )
            return formatted_history

        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Failed to get conversation history for {patient_id}: {e}")
            return []

    def _tone_for_time_of_day(self) -> str:
        """Derive a gentle tone based on time of day to help variation."""
        hour = datetime.now(timezone.utc).hour
        if hour < 12:
            return "cheerful"
        if hour < 18:
            return "friendly"
        return "calm"


# =============================================================================
# BACKWARD COMPATIBILITY - Keep existing interface intact
# =============================================================================

# Global enhanced flow engine instance (for backward compatibility)
_enhanced_flow_engine: Optional[EnhancedFlowEngine] = None


def get_enhanced_flow_engine(db: Any) -> EnhancedFlowEngine:
    """
    Get enhanced flow engine instance.

    Args:
        db: Database session

    Returns:
        EnhancedFlowEngine instance
    """
    return EnhancedFlowEngine(db)


async def test_enhanced_flow_engine() -> bool:
    """Test enhanced flow engine functionality."""
    try:
        from app.database import get_db

        db = next(get_db())
        engine = get_enhanced_flow_engine(db)

        # Perform health check
        health_status = await engine.health_check()
        logger.info(f"Enhanced flow engine health check: {health_status}")

        if not health_status["overall_healthy"]:
            logger.warning("Some components are not healthy")
            return False

        logger.info("Enhanced flow engine test completed successfully")
        return True

    except Exception as e:
        logger.error(f"Enhanced flow engine test failed: {e}")
        return False
