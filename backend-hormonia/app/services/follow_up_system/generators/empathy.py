"""
Empathetic follow-up message generator.
Creates personalized, empathetic messages for patient responses.

Phase 8 (AI-03): Migrated from LangGraph ainvoke() to direct generate_content() calls.
"""

import logging
from typing import Optional
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from .base import BaseGenerator
from .threading import sanitize_thread_component
from ..enums import FollowUpType
from ..models import FollowUpAction
from app.services.response_processor import StructuredResponse
from app.ai.models import PatientContext, ConcernLevel as ModelConcernLevel
from app.models.patient import Patient
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class EmpathyGenerator(BaseGenerator):
    """Generates empathetic follow-up messages."""

    def __init__(self, ai_graph=None):
        """
        Initialize empathy generator.

        Args:
            ai_graph: Unused. Kept for backward compatibility (Phase 8 AI-03: removed).
        """
        # ai_graph parameter retained for API compatibility but no longer used.
        # All generation now goes through GeminiClient.generate_content() directly.
        pass

    async def create_empathetic_follow_up(
        self,
        patient_id: UUID,
        patient: Patient,
        structured_response: StructuredResponse,
        patient_context: PatientContext,
        *,
        allow_questions: bool = False,
        day_complete: bool = False,
    ) -> Optional[FollowUpAction]:
        """
        Create empathetic follow-up message based on patient response.

        Args:
            patient_id: Patient UUID
            patient: Patient model instance
            structured_response: Processed response data
            patient_context: Patient context for AI

        Returns:
            FollowUpAction or None if generation failed
        """
        try:
            # Generate empathetic response using AI
            empathetic_message = await self._generate_empathetic_message(
                structured_response,
                patient_context,
                allow_questions=allow_questions,
                day_complete=day_complete,
            )

            if not empathetic_message:
                return None

            # Determine scheduling delay based on concern level
            delay_minutes = self.calculate_response_delay(
                structured_response.concern_level
            )
            scheduled_for = now_sao_paulo() + timedelta(minutes=delay_minutes)

            # Create follow-up action
            action = FollowUpAction(
                action_id=uuid4(),
                patient_id=patient_id,
                follow_up_type=FollowUpType.EMPATHETIC_RESPONSE,
                priority="normal"
                if structured_response.concern_level == ModelConcernLevel.LOW
                else "high",
                scheduled_for=scheduled_for,
                parameters={
                    "message_content": empathetic_message,
                    "original_message": structured_response.original_message,
                    "sentiment": structured_response.sentiment_analysis.get(
                        "sentiment"
                    ),
                    "concern_level": structured_response.concern_level.value,
                },
            )

            return action

        except Exception as e:
            logger.error(f"Failed to create empathetic follow-up: {e}")
            return None

    async def _generate_empathetic_message(
        self,
        structured_response: StructuredResponse,
        patient_context: PatientContext,
        *,
        allow_questions: bool = False,
        day_complete: bool = False,
    ) -> Optional[str]:
        """
        Generate empathetic message using AI.

        Phase 8 (AI-03): calls generate_content() directly — no LangGraph intermediary.

        Args:
            structured_response: Processed response data
            patient_context: Patient context for personalization

        Returns:
            Generated message or None if failed
        """
        try:
            from app.ai.client import get_gemini_client
            from app.ai.agents.helpers import build_empathetic_prompt
            from app.ai.context_compactor import compact_patient_context
            from app.services.ai.output_profiles import MESSAGE_HUMANIZED

            client = get_gemini_client()
            context_snapshot = compact_patient_context(patient_context.to_dict())
            prompt = build_empathetic_prompt(
                patient_response=structured_response.original_message,
                conversation_history=list(patient_context.recent_responses or []),
                context_snapshot=context_snapshot,
                examples=[],
                allow_questions=allow_questions,
                day_complete=day_complete,
            )
            response_text = await client.generate_content(
                prompt,
                profile=MESSAGE_HUMANIZED,
            )

            if not self._is_ai_response_safe(response_text):
                return None

            return response_text

        except Exception as e:
            logger.error(f"Failed to generate empathetic message: {e}")
            return None

    def _select_template_category(self, structured_response: StructuredResponse) -> str:
        """Select empathy template category based on response signals."""
        sentiment = structured_response.sentiment_analysis.get("sentiment", "neutral")
        if structured_response.concern_level in [
            ModelConcernLevel.HIGH,
            ModelConcernLevel.CRITICAL,
        ] or structured_response.medical_concerns:
            return "concern"
        if sentiment == "positive":
            return "positive"
        if sentiment in ["negative", "concerning"]:
            return "negative"
        return "neutral"

    def _is_ai_response_safe(self, text: Optional[str]) -> bool:
        """Basic safety checks to avoid medical advice or empty output."""
        if not text or not text.strip():
            return False
        unsafe_keywords = [
            "dose",
            "mg",
            "ml",
            "tomar",
            "tome",
            "suspender",
            "aumente",
            "reduza",
            "medicacao",
            "medicamento",
            "remedio",
            "prescricao",
        ]
        text_lower = text.casefold()
        return not any(keyword in text_lower for keyword in unsafe_keywords)

    def _build_thread_id(
        self,
        structured_response: StructuredResponse,
        patient_context: PatientContext,
        *,
        allow_questions: bool,
        day_complete: bool,
    ) -> str:
        """Build deterministic thread_id for empathetic follow-up generation."""
        patient_key = sanitize_thread_component(patient_context.patient_id)
        concern_key = sanitize_thread_component(structured_response.concern_level.value)
        treatment_day = sanitize_thread_component(patient_context.treatment_day)
        question_mode = "q1" if allow_questions else "q0"
        day_mode = "done1" if day_complete else "done0"
        return (
            f"follow_up:empathy:"
            f"patient:{patient_key}:day:{treatment_day}:"
            f"concern:{concern_key}:{question_mode}:{day_mode}"
        )
