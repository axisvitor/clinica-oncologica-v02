"""
Response generators for the Follow-up Action System.
Handles generation of empathetic messages, clarifications, and support responses.
"""

import logging
from typing import Optional
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from ..enums import FollowUpType
from ..models import FollowUpAction
from .base import BaseGenerator
from .threading import sanitize_thread_component
from app.services.response_processor import StructuredResponse
from app.services.ai import ConcernLevel
from app.services.ai.ai_service import PatientContext
from app.services.ai.output_profiles import MESSAGE_HUMANIZED
from app.models.patient import Patient
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class ResponseGenerator(BaseGenerator):
    """Generates various types of follow-up responses."""

    def __init__(self, ai_service):
        """
        Initialize response generator.

        Args:
            ai_service: AI service instance for message generation
        """
        self._ai_service = ai_service

    async def create_empathetic_follow_up(
        self,
        patient_id: UUID,
        patient: Patient,
        structured_response: StructuredResponse,
        patient_context: PatientContext,
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
                structured_response, patient_context
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
                if structured_response.concern_level == ConcernLevel.LOW
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
        self, structured_response: StructuredResponse, patient_context: PatientContext
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

            client = get_gemini_client()
            context_snapshot = compact_patient_context(patient_context.to_dict())
            prompt = build_empathetic_prompt(
                patient_response=structured_response.original_message,
                conversation_history=list(patient_context.recent_responses or []),
                context_snapshot=context_snapshot,
                examples=[],
                allow_questions=False,
                day_complete=False,
            )
            response_text = await client.generate_content(
                prompt,
                profile=MESSAGE_HUMANIZED,
            )
            return response_text or None

        except Exception as e:
            logger.error(f"Failed to generate empathetic message: {e}")
            return None

    def _build_thread_id(
        self, structured_response: StructuredResponse, patient_context: PatientContext
    ) -> str:
        """Build deterministic thread_id for follow-up response generation."""
        patient_key = sanitize_thread_component(patient_context.patient_id)
        concern_key = sanitize_thread_component(structured_response.concern_level.value)
        treatment_day = sanitize_thread_component(patient_context.treatment_day)
        return (
            f"follow_up:response:"
            f"patient:{patient_key}:day:{treatment_day}:concern:{concern_key}"
        )
