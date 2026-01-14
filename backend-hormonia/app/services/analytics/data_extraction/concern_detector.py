"""
Medical concern detection functionality.
Handles detection of medical concerns from patient messages.
"""

import logging
import re
import json
from typing import List

from app.services.ai import PatientContext, ConcernLevel

from .models import MedicalConcern, MedicalConcernType
from .patterns import MedicalPatterns
from app.integrations.openai_client import LangChainOrchestrator

logger = logging.getLogger(__name__)


class ConcernDetector:
    """Handles medical concern detection from patient messages."""

    def __init__(self, langchain_orchestrator: LangChainOrchestrator):
        """
        Initialize concern detector.

        Args:
            langchain_orchestrator: LangChain orchestrator for AI detection
        """
        self.langchain_orchestrator = langchain_orchestrator
        self.patterns = MedicalPatterns()

    def _severity_rank(self, severity: ConcernLevel) -> int:
        """Rank concern levels for comparison."""
        ranks = {
            ConcernLevel.LOW: 1,
            ConcernLevel.MEDIUM: 2,
            ConcernLevel.HIGH: 3,
            ConcernLevel.CRITICAL: 4,
        }
        return ranks.get(severity, 1)

    def _level_from_score(self, severity_score: int) -> ConcernLevel:
        """Map numeric severity score to concern level."""
        if severity_score >= 9:
            return ConcernLevel.CRITICAL
        if severity_score >= 7:
            return ConcernLevel.HIGH
        if severity_score >= 4:
            return ConcernLevel.MEDIUM
        return ConcernLevel.LOW

    async def detect_medical_concerns(
        self, message_text: str, patient_context: PatientContext
    ) -> List[MedicalConcern]:
        """
        Detect medical concerns from patient message.

        Args:
            message_text: Patient message text
            patient_context: Patient context

        Returns:
            List of detected medical concerns
        """
        concerns = []

        try:
            # Pattern-based detection
            pattern_concerns = self.detect_concerns_by_patterns(message_text)
            concerns.extend(pattern_concerns)

            # AI-based detection
            ai_concerns = await self.detect_concerns_by_ai(
                message_text, patient_context
            )
            concerns.extend(ai_concerns)

            # Remove duplicates
            concerns = self.deduplicate_concerns(concerns)

            return concerns

        except Exception as e:
            logger.error(f"Medical concern detection failed: {e}")
            return concerns

    def detect_concerns_by_patterns(self, message_text: str) -> List[MedicalConcern]:
        """
        Detect medical concerns using pattern matching.

        Args:
            message_text: Patient message text

        Returns:
            List of detected concerns
        """
        concerns = []
        text_lower = message_text.lower()

        try:
            # Emergency concerns
            emergency_patterns = [
                (
                    r"\b(não consigo respirar|nao consigo respirar|falta de ar|can't breathe|dificuldade para respirar)\b",
                    "breathing difficulty",
                    10,
                ),
                (r"\b(dor no peito|chest pain)\b", "chest pain", 9),
                (r"\b(sangramento intenso|hemorragia|bleeding)\b", "severe bleeding", 9),
                (r"\b(desmaiei|desmaio|fainted|unconscious)\b", "loss of consciousness", 10),
                (r"\b(febre (muito )?alta|febre 39|febre 40)\b", "high fever", 8),
            ]

            for pattern, description, severity_score in emergency_patterns:
                if re.search(pattern, text_lower):
                    concerns.append(
                        MedicalConcern(
                            concern_type=MedicalConcernType.EMERGENCY,
                            description=description,
                            severity=self._level_from_score(severity_score),
                            keywords=re.findall(pattern, text_lower),
                            confidence=0.9,
                            requires_immediate_attention=True,
                            severity_score=severity_score,
                        )
                    )

            # Pain concerns
            pain_patterns = [
                (r"\b(dor insuportável|dor insuportavel|unbearable pain)\b", "severe pain", 8),
                (r"\b(dor forte|dor muito forte|severe pain|intense pain)\b", "intense pain", 7),
                (r"\b(dor de cabeça|headache)\b", "headache", 5),
                (r"\b(dor nas costas|back pain)\b", "back pain", 5),
            ]

            for pattern, description, severity_score in pain_patterns:
                if re.search(pattern, text_lower):
                    severity = self._level_from_score(severity_score)
                    concerns.append(
                        MedicalConcern(
                            concern_type=MedicalConcernType.PAIN,
                            description=description,
                            severity=severity,
                            keywords=re.findall(pattern, text_lower),
                            confidence=0.8,
                            severity_score=severity_score,
                        )
                    )

            # Side effect concerns
            side_effect_patterns = [
                (r"\b(náusea|nausea|enjoo)\b", "nausea", 5),
                (r"\b(tontura|dizziness|dizzy)\b", "dizziness", 5),
                (r"\b(vômito|vomiting)\b", "vomiting", 6),
                (r"\b(erupção|rash|alergia|allergy)\b", "allergic reaction", 6),
            ]

            for pattern, description, severity_score in side_effect_patterns:
                if re.search(pattern, text_lower):
                    concerns.append(
                        MedicalConcern(
                            concern_type=MedicalConcernType.SIDE_EFFECT,
                            description=description,
                            severity=self._level_from_score(severity_score),
                            keywords=re.findall(pattern, text_lower),
                            confidence=0.7,
                            severity_score=severity_score,
                        )
                    )

            # Emotional distress
            emotional_patterns = [
                (
                    r"\b(muito triste|very sad|deprimida|depressed)\b",
                    "depression symptoms",
                    5,
                ),
                (r"\b(ansiosa|anxious|panic|pânico)\b", "anxiety symptoms", 4),
                (
                    r"\b(não consigo dormir|can\'t sleep|insomnia|insônia)\b",
                    "sleep issues",
                    4,
                ),
            ]

            for pattern, description, severity_score in emotional_patterns:
                if re.search(pattern, text_lower):
                    concerns.append(
                        MedicalConcern(
                            concern_type=MedicalConcernType.EMOTIONAL_DISTRESS,
                            description=description,
                            severity=self._level_from_score(severity_score),
                            keywords=re.findall(pattern, text_lower),
                            confidence=0.6,
                            severity_score=severity_score,
                        )
                    )

            return concerns

        except Exception as e:
            logger.error(f"Pattern-based concern detection failed: {e}")
            return concerns

    async def detect_concerns_by_ai(
        self, message_text: str, patient_context: PatientContext
    ) -> List[MedicalConcern]:
        """
        Detect medical concerns using AI.

        Args:
            message_text: Patient message text
            patient_context: Patient context

        Returns:
            List of detected concerns
        """
        concerns = []

        try:
            concern_detection_prompt = f"""
            Analyze this patient message for medical concerns that require healthcare provider attention.

            Patient context: {patient_context.treatment_type} treatment, day {patient_context.treatment_day}
            Message: "{message_text}"

            Identify concerns and format as JSON:
            {{
                "concerns": [
                    {{
                        "type": "concern_type",
                        "description": "brief description",
                        "severity": "low|medium|high|critical",
                        "keywords": ["keyword1", "keyword2"],
                        "confidence": 0.0-1.0,
                        "immediate_attention": true/false
                    }}
                ]
            }}

            Concern types:
            - pain: pain-related issues
            - side_effect: medication side effects
            - symptom_worsening: worsening symptoms
            - medication_issue: medication problems
            - emotional_distress: mental health concerns
            - treatment_adherence: compliance issues
            - emergency: urgent medical situations
            - general_health: other health concerns
            """

            ai_response = await self.langchain_orchestrator.generate_text(
                concern_detection_prompt
            )

            # Parse AI response
            try:
                parsed_response = json.loads(ai_response)
                for concern_data in parsed_response.get("concerns", []):
                    concern_type_str = concern_data.get("type", "general_health")
                    concern_type = MedicalConcernType.GENERAL_HEALTH

                    # Map string to enum
                    for ct in MedicalConcernType:
                        if ct.value == concern_type_str:
                            concern_type = ct
                            break

                    severity_str = concern_data.get("severity", "low")
                    severity = ConcernLevel.LOW

                    # Map string to enum
                    for sev in ConcernLevel:
                        if sev.value == severity_str:
                            severity = sev
                            break
                    severity_score_map = {
                        ConcernLevel.LOW: 2,
                        ConcernLevel.MEDIUM: 5,
                        ConcernLevel.HIGH: 7,
                        ConcernLevel.CRITICAL: 9,
                    }
                    severity_score = severity_score_map.get(severity, 2)

                    concerns.append(
                        MedicalConcern(
                            concern_type=concern_type,
                            description=concern_data.get(
                                "description", "AI detected concern"
                            ),
                            severity=severity,
                            keywords=concern_data.get("keywords", []),
                            confidence=float(concern_data.get("confidence", 0.5)),
                            requires_immediate_attention=concern_data.get(
                                "immediate_attention", False
                            ),
                            severity_score=severity_score,
                        )
                    )

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Failed to parse AI concern detection response: {e}")

            return concerns

        except Exception as e:
            logger.error(f"AI concern detection failed: {e}")
            return concerns

    def deduplicate_concerns(
        self, concerns: List[MedicalConcern]
    ) -> List[MedicalConcern]:
        """
        Remove duplicate medical concerns.

        Args:
            concerns: List of medical concerns

        Returns:
            Deduplicated list of concerns
        """
        seen_concerns: dict[str, MedicalConcern] = {}

        for concern in concerns:
            key = f"{concern.concern_type.value}_{concern.description}"

            if key in seen_concerns:
                # Keep the one with higher severity or confidence
                existing = seen_concerns[key]
                concern_score = (
                    concern.severity_score
                    if concern.severity_score is not None
                    else self._severity_rank(concern.severity)
                )
                existing_score = (
                    existing.severity_score
                    if existing.severity_score is not None
                    else self._severity_rank(existing.severity)
                )
                if concern_score > existing_score or (
                    concern_score == existing_score
                    and concern.confidence > existing.confidence
                ):
                    seen_concerns[key] = concern
            else:
                seen_concerns[key] = concern

        return list(seen_concerns.values())
