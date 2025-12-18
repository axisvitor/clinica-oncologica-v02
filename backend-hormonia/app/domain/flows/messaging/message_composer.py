"""
Message Composition Module - AI-Powered Message Personalization

Handles message generation using AI services with circuit breaker protection.
"""

import logging

from app.models.patient import Patient
from app.services.template_loader import MessageTemplate
from app.services.ai import AIService, PatientContext
from app.resilience.circuit_breaker.breaker import CircuitBreaker


logger = logging.getLogger(__name__)


class MessageComposer:
    """
    Composes personalized messages using AI services.

    Responsibilities:
    - Generate personalized messages from templates
    - Apply AI humanization with circuit breaker protection
    - Fallback to template content on AI failure
    - Build patient context for AI processing
    """

    def __init__(self, ai_service: AIService, ai_circuit_breaker: CircuitBreaker):
        """
        Initialize MessageComposer.

        Args:
            ai_service: AI service for message personalization
            ai_circuit_breaker: Circuit breaker for AI service calls
        """
        self.ai_service = ai_service
        self.ai_circuit_breaker = ai_circuit_breaker

        logger.info("MessageComposer initialized")

    async def generate_personalized_message(
        self,
        patient: Patient,
        message_template: MessageTemplate,
        current_day: int,
        flow_type: str,
    ) -> str:
        """
        Generate personalized message using AI service with circuit breaker.

        Args:
            patient: Patient object
            message_template: Message template
            current_day: Current treatment day
            flow_type: Current flow type

        Returns:
            Personalized message content
        """
        try:
            # Create patient context for AI
            patient_context = self._build_patient_context(
                patient, current_day, flow_type
            )

            # Use circuit breaker for AI service call
            async def ai_call():
                response = await self.ai_service.humanize_message(
                    template_message=message_template.base_content,
                    patient_context=patient_context,
                    message_type=message_template.intent,
                )
                return response.personalized_message

            personalized_content = await self.ai_circuit_breaker.call(ai_call)

            logger.info(f"Generated personalized message for patient {patient.id}")
            return personalized_content

        except Exception as e:
            logger.warning(f"AI personalization failed, using template: {e}")
            # Fallback to template content with basic personalization
            return self._apply_basic_personalization(
                message_template.base_content, patient
            )

    def _build_patient_context(
        self, patient: Patient, current_day: int, flow_type: str
    ) -> PatientContext:
        """
        Build patient context for AI processing.

        Args:
            patient: Patient object
            current_day: Current treatment day
            flow_type: Current flow type

        Returns:
            PatientContext object
        """
        return PatientContext(
            patient_id=str(patient.id),
            name=patient.name,
            treatment_type=patient.treatment_type or "general",
            treatment_day=current_day,
            age=patient.age,
            recent_responses=[],  # Could be populated from message history
            medical_history={},
            preferences={},
        )

    def _apply_basic_personalization(
        self, template_content: str, patient: Patient
    ) -> str:
        """
        Apply basic personalization to template (fallback).

        Args:
            template_content: Template content
            patient: Patient object

        Returns:
            Personalized content
        """
        personalized = template_content.replace(
            "{patient_name}", patient.name or "paciente"
        )

        # Add more basic replacements as needed
        return personalized
