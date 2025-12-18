"""
Base generator for follow-up messages.
Provides common utilities for message generation.
"""

import logging
from typing import List

from app.services.analytics.data_extraction import ConcernLevel, MedicalConcernType

logger = logging.getLogger(__name__)


class BaseGenerator:
    """Base class for follow-up message generators."""

    def calculate_response_delay(self, concern_level: ConcernLevel) -> int:
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

    def classify_concern_type(self, concern: str) -> MedicalConcernType:
        """
        Classify type of medical concern.

        Args:
            concern: Medical concern text

        Returns:
            MedicalConcernType
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
