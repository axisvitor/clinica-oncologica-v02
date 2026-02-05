"""
Empathetic follow-up message generator.
Creates personalized, empathetic messages for patient responses.
"""

import logging
from typing import Optional
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from .base import BaseGenerator
from ..enums import FollowUpType
from ..models import FollowUpAction
from app.services.response_processor import StructuredResponse
from app.services.analytics.data_extraction import ConcernLevel
from app.services.ai.ai_service import PatientContext
from app.models.patient import Patient
from app.templates.whatsapp.empathy import get_empathy_template

logger = logging.getLogger(__name__)


class EmpathyGenerator(BaseGenerator):
    """Generates empathetic follow-up messages."""

    def __init__(self, ai_service):
        """
        Initialize empathy generator.

        Args:
            ai_service: AI service instance for message generation
        """
        self.ai_service = ai_service

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
                structured_response, patient_context, patient.name
            )

            if not empathetic_message:
                return None

            # Determine scheduling delay based on concern level
            delay_minutes = self.calculate_response_delay(
                structured_response.concern_level
            )
            scheduled_for = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)

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
        self,
        structured_response: StructuredResponse,
        patient_context: PatientContext,
        patient_name: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate empathetic message using AI.

        Args:
            structured_response: Processed response data
            patient_context: Patient context for personalization

        Returns:
            Generated message or None if failed
        """
        try:
            template_category = self._select_template_category(structured_response)
            fallback_message = get_empathy_template(template_category, patient_name)

            if not self.ai_service or not hasattr(self.ai_service, "humanize_message"):
                return fallback_message or None

            # Generate empathetic response
            empathetic_response = await self.ai_service.humanize_message(
                template_message="Acknowledge and respond empathetically to the patient's message",
                patient_context=patient_context,
                message_type="empathetic_response",
            )

            response_text = empathetic_response.humanized_message
            if not self._is_ai_response_safe(response_text):
                return fallback_message or None

            return response_text

        except Exception as e:
            logger.error(f"Failed to generate empathetic message: {e}")
            template_category = self._select_template_category(structured_response)
            return get_empathy_template(template_category, patient_name) or None

    def _select_template_category(self, structured_response: StructuredResponse) -> str:
        """Select empathy template category based on response signals."""
        sentiment = structured_response.sentiment_analysis.get("sentiment", "neutral")
        if structured_response.concern_level in [
            ConcernLevel.HIGH,
            ConcernLevel.CRITICAL,
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
