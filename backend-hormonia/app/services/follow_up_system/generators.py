"""
Response generators for the Follow-up Action System.
Handles generation of empathetic messages, clarifications, and support responses.
"""

import logging
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from .enums import FollowUpType
from .models import FollowUpAction
from app.services.response_processor import StructuredResponse
from app.services.analytics.data_extraction import ConcernLevel, MedicalConcernType
from app.services.ai.ai_service import PatientContext
from app.models.patient import Patient

logger = logging.getLogger(__name__)


class ResponseGenerator:
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
            delay_minutes = self._calculate_response_delay(
                structured_response.concern_level
            )
            scheduled_for = datetime.utcnow() + timedelta(minutes=delay_minutes)

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

        Args:
            structured_response: Processed response data
            patient_context: Patient context for personalization

        Returns:
            Generated message or None if failed
        """
        try:
            # Build context for AI humanizer
            {
                "patient_message": structured_response.original_message,
                "sentiment": structured_response.sentiment_analysis.get("sentiment"),
                "concern_level": structured_response.concern_level.value,
                "medical_concerns": structured_response.medical_concerns,
                "emotional_indicators": structured_response.sentiment_analysis.get(
                    "emotional_indicators", []
                ),
            }

            # Generate empathetic response
            empathetic_response = await self._ai_service.humanize_message(
                template_message="Acknowledge and respond empathetically to the patient's message",
                patient_context=patient_context,
                message_type="empathetic_response",
            )

            return empathetic_response.humanized_message

        except Exception as e:
            logger.error(f"Failed to generate empathetic message: {e}")
            return None

    def _calculate_response_delay(self, concern_level: ConcernLevel) -> int:
        """
        Calculate appropriate delay for response based on concern level.

        Args:
            concern_level: Level of concern from response processing

        Returns:
            Delay in minutes
        """
        delay_mapping = {
            ConcernLevel.CRITICAL: 0,  # Immediate
            ConcernLevel.HIGH: 5,  # 5 minutes
            ConcernLevel.MEDIUM: 15,  # 15 minutes
            ConcernLevel.LOW: 30,  # 30 minutes
        }
        return delay_mapping.get(concern_level, 30)

    def generate_clarification_questions(self, concern: str) -> List[str]:
        """
        Generate clarification questions for medical concerns.

        Args:
            concern: Medical concern text

        Returns:
            List of clarification questions (max 3)
        """
        concern_lower = concern.lower()
        questions = []

        if "pain" in concern_lower:
            questions.extend(
                [
                    "Em uma escala de 1 a 10, como você classificaria sua dor?",
                    "A dor é constante ou vem e vai?",
                    "Quando a dor começou?",
                ]
            )

        if "nausea" in concern_lower or "vomit" in concern_lower:
            questions.extend(
                [
                    "A náusea está relacionada às refeições?",
                    "Você conseguiu manter líquidos?",
                    "Isso começou após tomar algum medicamento?",
                ]
            )

        if "medication" in concern_lower:
            questions.extend(
                [
                    "Qual medicamento está causando preocupação?",
                    "Você tomou a dose correta?",
                    "Quando foi a última vez que tomou?",
                ]
            )

        # Default questions if no specific type identified
        if not questions:
            questions.extend(
                [
                    "Pode me contar mais detalhes sobre isso?",
                    "Quando isso começou?",
                    "Isso está afetando suas atividades diárias?",
                ]
            )

        return questions[:3]  # Return max 3 questions

    def classify_concern_type(self, concern: str) -> Optional[MedicalConcernType]:
        """
        Classify type of medical concern.

        Args:
            concern: Medical concern text

        Returns:
            MedicalConcernType or None
        """
        concern_lower = concern.lower()

        if any(word in concern_lower for word in ["pain", "hurt", "ache"]):
            return MedicalConcernType.PAIN
        elif any(
            word in concern_lower for word in ["nausea", "vomit", "dizzy", "rash"]
        ):
            return MedicalConcernType.SIDE_EFFECT
        elif any(
            word in concern_lower for word in ["worse", "worsening", "deteriorating"]
        ):
            return MedicalConcernType.SYMPTOM_WORSENING
        elif any(word in concern_lower for word in ["medication", "medicine", "dose"]):
            return MedicalConcernType.MEDICATION_ISSUE
        elif any(
            word in concern_lower for word in ["sad", "anxious", "depressed", "worried"]
        ):
            return MedicalConcernType.EMOTIONAL_DISTRESS
        elif any(word in concern_lower for word in ["emergency", "urgent", "severe"]):
            return MedicalConcernType.EMERGENCY
        else:
            return MedicalConcernType.GENERAL_HEALTH

    def assess_concern_severity(self, concern: str) -> ConcernLevel:
        """
        Assess severity of medical concern.

        Args:
            concern: Medical concern text

        Returns:
            ConcernLevel indicating severity
        """
        concern_lower = concern.lower()

        # Critical keywords
        critical_keywords = [
            "emergency",
            "can't breathe",
            "chest pain",
            "severe bleeding",
            "unconscious",
            "suicide",
            "overdose",
        ]

        # High severity keywords
        high_keywords = [
            "severe",
            "unbearable",
            "getting worse",
            "can't sleep",
            "vomiting",
            "fever",
            "dizzy",
            "confused",
        ]

        # Medium severity keywords
        medium_keywords = [
            "pain",
            "headache",
            "nausea",
            "tired",
            "worried",
            "side effect",
            "uncomfortable",
        ]

        if any(keyword in concern_lower for keyword in critical_keywords):
            return ConcernLevel.CRITICAL
        elif any(keyword in concern_lower for keyword in high_keywords):
            return ConcernLevel.HIGH
        elif any(keyword in concern_lower for keyword in medium_keywords):
            return ConcernLevel.MEDIUM
        else:
            return ConcernLevel.LOW
