"""
FlowEngine - AI-powered flow execution engine.
Pure execution engine inheriting shared functionality from FlowCore.
Focuses only on AI/ML operations: message generation, response processing, and conversation memory.

Architecture note (QW-021 consolidation):
    This file provides *unique* AI/ML functionality that does NOT exist in
    ``app.services.flow``.  It inherits from FlowCore and adds:
    - Gemini AI client integration for message personalization
    - LangGraph humanization / sentiment graphs
    - Conversation memory and anti-repetition
    - Patient response processing with engagement scoring

    NOT a duplicate of ``app.services.flow.core.engine.FlowEngine`` which is the
    QW-021 step-execution engine (stateless executor + scheduler + state machine).

    Canonical FlowType enum: ``app.services.flow.types.FlowType``
"""

import logging
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.services.flow_core import FlowCore
from app.services.flow.context_parsing import parse_optional_int, parse_optional_str
from app.services.flow.flags import message_expects_response
from app.services.flow.types import FlowType, normalize_flow_type
from app.services.template_loader_pkg import MessageTemplate, EnhancedTemplateLoader
from app.models.patient import Patient
from app.models.flow import PatientFlowState, FlowKind, FlowTemplateVersion
from app.models.message import Message, MessageDirection
from app.ai.client import GeminiClient, get_gemini_client
import sentry_sdk
from app.core.exceptions import FeatureNotAvailableError
from app.services.ai.output_profiles import JSON_SENTIMENT, MESSAGE_HUMANIZED
from app.services.conversation_memory import ConversationMemory, get_conversation_memory
from app.services.platform_synchronization import PlatformSynchronizationService
from app.infrastructure.cache import UnifiedCacheManager as UnifiedCacheService
from app.exceptions import NotFoundError
from app.config import settings
from app.utils.db_retry import with_db_retry
from app.utils.text import clip_text
from app.utils.timezone import now_sao_paulo

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
        recent_interactions: List[Dict[str, Any]] = None,
        communication_preferences: dict[str, Any] = None,
        medical_context: dict[str, Any] = None,
    ):
        self.patient = patient
        self.flow_state = flow_state
        self.current_day = current_day
        self.flow_type = flow_type or "unknown"  # Store flow type
        self.conversation_history = conversation_history or []
        self.recent_interactions = recent_interactions or []
        self.communication_preferences = communication_preferences or {}
        self.medical_context = medical_context or {}
        self.timestamp = now_sao_paulo()

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary."""
        state_data = {}
        if self.flow_state:
            try:
                state_data = self.flow_state.state_data or {}
            except Exception:
                state_data = {}
        flow_kind = state_data.get("flow_kind") or self.flow_type
        send_mode = state_data.get("send_mode") or state_data.get("daily_send_mode")
        message_index = state_data.get("current_day_message_index")
        awaiting_response = state_data.get("awaiting_response")

        return {
            "patient_id": str(self.patient.id),
            "patient_name": self.patient.name,
            "flow_type": self.flow_type,  # Use stored flow type
            "flow_kind": flow_kind,
            "current_day": self.current_day,
            "treatment_day": self._calculate_treatment_day(),
            "conversation_history": self.conversation_history,
            "recent_interactions": self.recent_interactions,
            "communication_preferences": self.communication_preferences,
            "medical_context": self.medical_context,
            "send_mode": send_mode or "single",
            "current_day_message_index": message_index,
            "awaiting_response": awaiting_response,
            "timestamp": self.timestamp.isoformat(),
        }

    def _calculate_treatment_day(self) -> int:
        """Calculate treatment day based on enrollment date."""
        if (
            hasattr(self.patient, "treatment_start_date")
            and self.patient.treatment_start_date
        ):
            delta = (
                now_sao_paulo().date() - self.patient.treatment_start_date
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
        self._reminder_handler = None

        logger.info("Enhanced FlowEngine initialized with AI integration")

        # No extra AI passes; rewrite happens once per message.

    async def _get_flow_type_from_state(self, flow_state: PatientFlowState) -> str:
        """
        Helper method to get flow_type from a PatientFlowState using template_version_id.

        Args:
            flow_state: The patient flow state

        Returns:
            The flow_type string
        """
        # Async select for AsyncSession compat
        result = await self.db.execute(
            select(FlowTemplateVersion).filter(
                FlowTemplateVersion.id == flow_state.flow_template_version_id
            )
        )
        template_version = result.scalar_one_or_none()

        if not template_version:
            logger.error(f"Template version not found for flow state {flow_state.id}")
            return "unknown"

        result = await self.db.execute(
            select(FlowKind).filter(FlowKind.id == template_version.flow_kind_id)
        )
        flow_kind = result.scalar_one_or_none()

        if not flow_kind:
            logger.error(
                f"Flow kind not found for template version {template_version.id}"
            )
            return "unknown"

        return flow_kind.flow_type

    def _get_reminder_handler(self):
        if self._reminder_handler is None:
            from app.services.reminders import ReminderHandler

            self._reminder_handler = ReminderHandler(self.db, self.gemini_client)
        return self._reminder_handler

    def _normalize_response_context(
        self, response_context: Optional[Dict[str, Any]]
    ) -> dict[str, Any]:
        """Normalize inbound response context for downstream correlation."""
        context = dict(response_context or {})
        prompt_message_id = parse_optional_str(context.get("prompt_message_id"))
        response_message_id = parse_optional_str(context.get("response_message_id"))
        normalized_context = {
            "prompt_message_id": prompt_message_id,
            "response_message_id": response_message_id,
            "flow_day": parse_optional_int(
                context.get("flow_day", context.get("current_flow_day"))
            ),
            "flow_kind": parse_optional_str(context.get("flow_kind")),
            "message_index": parse_optional_int(
                context.get(
                    "message_index",
                    context.get("current_message_index", context.get("current_day_message_index")),
                )
            ),
            "awaiting_response": context.get("awaiting_response"),
        }
        for key, value in context.items():
            normalized_context.setdefault(key, value)
        return {key: value for key, value in normalized_context.items() if value is not None}

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
        strict: bool = False,
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
            # Get patient and flow context (inlined from repos for async compat)
            result = await self.db.execute(
                select(Patient).filter(Patient.id == patient_id)
            )
            patient = result.scalar_one_or_none()
            if not patient:
                raise NotFoundError(f"Patient {patient_id} not found")

            # Inlined from FlowStateRepository.get_active_flow() for async compat
            result = await self.db.execute(
                select(PatientFlowState).filter(
                    PatientFlowState.patient_id == patient_id,
                    PatientFlowState.status == "active",
                )
            )
            flow_state = result.scalar_one_or_none()
            if not flow_state:
                raise NotFoundError(f"No active flow for patient {patient_id}")

            # Determine current day if not provided
            if day is None:
                day = await self.calculate_patient_day(patient_id)

            # Get flow type from state
            flow_type_str = await self._get_flow_type_from_state(flow_state)

            # Load message template from database if not provided
            if message_template is None:
                flow_type = normalize_flow_type(flow_type_str)
                if flow_type == FlowType.CUSTOM:
                    flow_type = FlowType.ONBOARDING
                message_template = await self.get_message_template_for_day(
                    flow_type, day
                )
                if not message_template:
                    raise NotFoundError(
                        f"Message template not found for flow {flow_type_str} day {day}"
                    )

            # Build flow context
            conversation_history = await self._get_conversation_history(patient_id)
            recent_interactions = await self._get_recent_interactions(patient_id)
            communication_preferences = (
                await self.conversation_memory.get_communication_preferences(patient_id)
            )

            flow_context = FlowContext(
                patient=patient,
                flow_state=flow_state,
                current_day=day,
                flow_type=flow_type_str,  # Pass the resolved flow type
                conversation_history=conversation_history,
                recent_interactions=recent_interactions,
                communication_preferences=communication_preferences,
                medical_context={
                    "treatment_type": getattr(
                        patient, "treatment_type", "hormone_therapy"
                    )
                },
            )

            ai_humanization_enabled = bool(
                getattr(settings, "AI_ENABLE_HUMANIZATION", True)
            )

            if not ai_humanization_enabled:
                personalized_message = message_template.base_content
            else:
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

                    personalized_message = await self.gemini_client.generate_varied_question(
                        base_content,
                        conversation_history[-5:],  # Last 5 messages
                        flow_context.to_dict(),
                        few_shot_examples=few_shot_examples,
                        ai_instructions=getattr(message_template, "ai_instructions", None),
                        strict=strict,
                    )
                else:
                    # Call generate_content directly — no LangGraph intermediary (Phase 8 AI-03)
                    from app.ai.langgraph.nodes_ai import _coerce_recent_interactions, _replace_patient_name
                    from app.ai.langgraph.prompts import build_humanization_prompt
                    recent_interactions = _coerce_recent_interactions(
                        flow_context.to_dict().get("recent_interactions"),
                        fallback_history=conversation_history,
                    )
                    template_text = _replace_patient_name(
                        message_template.base_content, patient.name
                    )
                    prompt = build_humanization_prompt(
                        template=template_text,
                        ai_instructions=getattr(message_template, "ai_instructions", None),
                        recent_interactions=recent_interactions,
                    )
                    try:
                        personalized_message = await self.gemini_client.generate_content(
                            prompt,
                            profile=MESSAGE_HUMANIZED,
                        )
                        if not personalized_message:
                            raise FeatureNotAvailableError(
                                "humanization returned no output",
                                "humanization",
                                "generate_flow_message",
                            )
                    except FeatureNotAvailableError as exc:
                        sentry_sdk.capture_exception(exc)
                        logger.error(
                            "Humanization failed, using unhumanized template: %s",
                            exc,
                            extra={"feature": "humanization"},
                        )
                        personalized_message = message_template.base_content

            # Single AI pass only: do not apply extra variation after the rewrite.

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
            raise

    @with_db_retry(max_retries=3)
    async def process_patient_response(
        self,
        patient_id: UUID,
        response_text: str,
        response_context: Optional[Dict[str, Any]] = None,
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
            # Get patient context (inlined from PatientRepository.get() for async compat)
            result = await self.db.execute(
                select(Patient).filter(Patient.id == patient_id)
            )
            patient = result.scalar_one_or_none()
            if not patient:
                raise NotFoundError(f"Patient {patient_id} not found")

            # Inlined from FlowStateRepository.get_active_flow() for async compat
            result = await self.db.execute(
                select(PatientFlowState).filter(
                    PatientFlowState.patient_id == patient_id,
                    PatientFlowState.status == "active",
                )
            )
            flow_state = result.scalar_one_or_none()
            if not flow_state:
                logger.warning(
                    f"No active flow for patient {patient_id}, processing response anyway"
                )

            context = self._normalize_response_context(response_context)
            flow_day = context.get("flow_day")
            flow_day = parse_optional_int(flow_day)

            message_index = context.get("message_index")
            message_index = parse_optional_int(message_index)
            flow_kind = context.get("flow_kind")
            if flow_state:
                state_data_snapshot = flow_state.state_data or {}
                if flow_day is None:
                    flow_day = state_data_snapshot.get("current_flow_day")
                if message_index is None:
                    message_index = state_data_snapshot.get("current_day_message_index")
                if flow_kind is None:
                    flow_kind = state_data_snapshot.get("flow_kind")
            if flow_day is not None:
                context["flow_day"] = flow_day
            if message_index is not None:
                context["message_index"] = message_index
            if flow_kind is not None:
                context["flow_kind"] = flow_kind

            # Analyze response sentiment
            patient_context = {
                "name": patient.name,
                "treatment_type": getattr(patient, "treatment_type", "hormone_therapy"),
                "current_day": flow_day or await self.calculate_patient_day(patient_id),
            }

            sentiment_analysis: Dict[str, Any] | None = None
            sentiment_analyzer = getattr(
                self.gemini_client, "analyze_response_sentiment", None
            )
            if callable(sentiment_analyzer):
                try:
                    sentiment_analysis = await sentiment_analyzer(
                        response_text, patient_context
                    )
                except TypeError:
                    # Backward compatibility for alternate adapter signatures.
                    sentiment_analysis = await sentiment_analyzer(response_text)
                except Exception:
                    logger.warning(
                        "Gemini sentiment analysis failed; falling back to LangGraph node",
                        exc_info=True,
                    )

            if not isinstance(sentiment_analysis, dict):
                # Call generate_content directly — no LangGraph intermediary (Phase 8 AI-03)
                from app.ai.langgraph.nodes_ai import _parse_sentiment_analysis
                from app.ai.langgraph.prompts import build_sentiment_prompt
                from app.ai.context_compactor import compact_patient_context
                try:
                    context_snapshot = compact_patient_context(patient_context)
                    sentiment_prompt = build_sentiment_prompt(
                        response=response_text,
                        context_snapshot=context_snapshot,
                    )
                    analysis_text = await self.gemini_client.generate_content(
                        sentiment_prompt,
                        profile=JSON_SENTIMENT,
                    )
                    if not analysis_text:
                        raise FeatureNotAvailableError(
                            "sentiment analysis returned no output",
                            "sentiment",
                            "analyze_flow_sentiment",
                        )
                    sentiment_analysis = _parse_sentiment_analysis(analysis_text)
                except FeatureNotAvailableError as exc:
                    sentry_sdk.capture_exception(exc)
                    logger.error(
                        "Sentiment analysis failed, using neutral fallback: %s",
                        exc,
                        extra={"feature": "sentiment"},
                    )
                    sentiment_analysis = {"sentiment": "neutral", "confidence": 0.0}

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
            commit_needed = False
            state_data = {}
            if flow_state:
                state_data = dict(flow_state.state_data or {})
                state_data.setdefault("responses", {})
                state_data.setdefault("step_timestamps", {})
                state_data.setdefault("flags", {})

                current_step = flow_state.current_step
                if current_step is None or current_step == 0:
                    current_step = state_data.get("current_step") or flow_day
                if current_step:
                    state_data["responses"][
                        f"step_{current_step}"
                    ] = response_text
                    state_data["step_timestamps"][
                        f"step_{current_step}"
                    ] = now_sao_paulo().isoformat()

                response_key = None
                if flow_day is not None:
                    response_key = (
                        f"day_{flow_day}_msg_{message_index}"
                        if message_index is not None
                        else f"day_{flow_day}"
                    )
                else:
                    response_key = f"msg_{message_index}" if message_index is not None else "latest"

                state_data.setdefault("responses_by_message", {})
                state_data["responses_by_message"][response_key] = {
                    "prompt_message_id": context.get("prompt_message_id"),
                    "response_message_id": context.get("response_message_id"),
                    "timestamp": now_sao_paulo().isoformat(),
                    "flow_day": flow_day,
                    "flow_kind": flow_kind,
                    "message_index": message_index,
                    "response_text": response_text,
                    "sentiment": sentiment_analysis,
                }

                state_data["flags"]["needs_attention"] = sentiment_analysis.get(
                    "requires_attention", False
                )
                state_data["flags"]["high_risk"] = bool(
                    sentiment_analysis.get("medical_concerns", [])
                )

                state_data["last_response"] = {
                    "prompt_message_id": context.get("prompt_message_id"),
                    "response_message_id": context.get("response_message_id"),
                    "timestamp": now_sao_paulo().isoformat(),
                    "sentiment": sentiment_analysis,
                    "text_length": len(response_text),
                    "engagement_score": engagement_score,
                }
                flow_state.state_data = state_data
                flow_state.last_interaction_at = now_sao_paulo()
                commit_needed = True

            reminder_result = None
            try:
                reminder_result = await self._get_reminder_handler().handle_response(
                    patient=patient,
                    response_text=response_text,
                    flow_state=flow_state,
                    state_data=state_data if flow_state else {},
                    response_context=context,
                )
            except Exception as exc:
                logger.warning("Reminder handling failed: %s", exc)

            if reminder_result and reminder_result.follow_up_message:
                deferred = False
                if flow_state and reminder_result.action == "pending":
                    current_step_data = flow_state.step_data or {}
                    if not current_step_data.get("day_complete"):
                        current_step_data = dict(current_step_data)
                        current_step_data.setdefault("deferred_followups", [])
                        dedupe_key = (
                            "reminder",
                            reminder_result.reminder_id,
                            reminder_result.follow_up_message,
                        )
                        exists = False
                        for existing in current_step_data["deferred_followups"]:
                            existing_key = (
                                (existing or {}).get("type"),
                                (existing or {}).get("reminder_id"),
                                (existing or {}).get("message"),
                            )
                            if existing_key == dedupe_key:
                                exists = True
                                break
                        if not exists:
                            current_step_data["deferred_followups"].append(
                            {
                                "type": "reminder",
                                "message": reminder_result.follow_up_message,
                                "reminder_id": reminder_result.reminder_id,
                                "flow_day": flow_day,
                                "flow_kind": flow_kind,
                                "created_at": now_sao_paulo().isoformat(),
                            }
                            )
                        flow_state.step_data = current_step_data
                        commit_needed = True
                        deferred = True

                if not deferred and not follow_up_message:
                    follow_up_message = reminder_result.follow_up_message

            if reminder_result and flow_state:
                # Re-assign to ensure MutableDict tracks reminder mutations
                flow_state.state_data = state_data
            if reminder_result and reminder_result.commit_needed:
                commit_needed = True

            if commit_needed:
                await self.db.commit()

            return {
                "status": "processed",
                "patient_id": str(patient_id),
                "sentiment_analysis": sentiment_analysis,
                "engagement_score": engagement_score,
                "follow_up_message": follow_up_message,
                "requires_attention": sentiment_analysis.get(
                    "requires_attention", False
                ),
                "medical_concerns": sentiment_analysis.get("medical_concerns", []),
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
            # Query recent messages for this patient (async select for AsyncSession compat)
            result = await self.db.execute(
                select(Message)
                .filter(
                    Message.patient_id == patient_id,
                    Message.content.isnot(None),  # Only messages with text content
                    Message.content != "",  # Exclude empty messages
                )
                .order_by(Message.created_at.desc())  # Most recent first
                .limit(limit)
            )
            messages = result.scalars().all()

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

    @with_db_retry(max_retries=3)
    async def _get_recent_interactions(
        self,
        patient_id: UUID,
        *,
        interaction_limit: int = 2,
        scan_limit: int = 40,
    ) -> List[Dict[str, Any]]:
        """
        Get the most recent question/answer interactions for the patient.

        Interactions are derived from outbound flow messages that expect a response
        and the subsequent inbound reply(ies). Returns the last N completed pairs.
        """
        try:
            # Async select for AsyncSession compat
            result = await self.db.execute(
                select(Message)
                .filter(
                    Message.patient_id == patient_id,
                    Message.content.isnot(None),
                    Message.content != "",
                )
                .order_by(Message.created_at.desc())
                .limit(scan_limit)
            )
            messages = result.scalars().all()
            if not messages:
                return []

            def _build_interaction(
                question_msg: Message, response_msgs: List[Message]
            ) -> Dict[str, Any]:
                metadata = question_msg.message_metadata or {}
                answered_at = response_msgs[-1].created_at if response_msgs else None
                response_texts = [
                    msg.content for msg in response_msgs if msg.content
                ]
                response_text = "\n".join(response_texts).strip()
                return {
                    "question": clip_text(question_msg.content or "", max_len=360, ellipsis="…"),
                    "answer": clip_text(response_text, max_len=360, ellipsis="…"),
                    "flow_kind": metadata.get("flow_kind"),
                    "flow_day": metadata.get("flow_day"),
                    "message_index": metadata.get("message_index"),
                    "asked_at": (
                        question_msg.sent_at or question_msg.created_at
                    ).isoformat()
                    if (question_msg.sent_at or question_msg.created_at)
                    else None,
                    "answered_at": answered_at.isoformat() if answered_at else None,
                }

            interactions: List[Dict[str, Any]] = []
            current_question: Optional[Message] = None
            current_responses: List[Message] = []

            for msg in reversed(messages):
                if msg.direction == MessageDirection.OUTBOUND and message_expects_response(msg):
                    if current_question and current_responses:
                        interactions.append(
                            _build_interaction(current_question, current_responses)
                        )
                    current_question = msg
                    current_responses = []
                    continue

                if msg.direction == MessageDirection.INBOUND and current_question:
                    current_responses.append(msg)

            if current_question and current_responses:
                interactions.append(
                    _build_interaction(current_question, current_responses)
                )

            if not interactions:
                return []

            return interactions[-interaction_limit:]

        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "Failed to get recent interactions for %s: %s", patient_id, e
            )
            return []

    def _tone_for_time_of_day(self) -> str:
        """Derive a gentle tone based on time of day to help variation."""
        hour = now_sao_paulo().hour
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
        from app.database import get_scoped_session

        with get_scoped_session() as db:
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
