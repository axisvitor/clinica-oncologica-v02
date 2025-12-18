"""
Patient preference extraction functionality.
Handles extraction of patient preferences from messages.
"""

import logging
import re
import json
from typing import List

from app.services.ai import PatientContext
from app.integrations.openai_client import LangChainOrchestrator

from .models import PatientPreference
from .patterns import MedicalPatterns

logger = logging.getLogger(__name__)


class PreferenceExtractor:
    """Handles patient preference extraction from messages."""

    def __init__(self, langchain_orchestrator: LangChainOrchestrator):
        """
        Initialize preference extractor.

        Args:
            langchain_orchestrator: LangChain orchestrator for AI extraction
        """
        self.langchain_orchestrator = langchain_orchestrator
        self.patterns = MedicalPatterns()

    async def extract_patient_preferences(
        self, message_text: str, patient_context: PatientContext
    ) -> List[PatientPreference]:
        """
        Extract patient preferences from message.

        Args:
            message_text: Patient message text
            patient_context: Patient context

        Returns:
            List of extracted patient preferences
        """
        preferences = []

        try:
            # Pattern-based preference extraction
            pattern_preferences = self.extract_preferences_by_patterns(message_text)
            preferences.extend(pattern_preferences)

            # AI-based preference extraction
            ai_preferences = await self.extract_preferences_by_ai(
                message_text, patient_context
            )
            preferences.extend(ai_preferences)

            return preferences

        except Exception as e:
            logger.error(f"Preference extraction failed: {e}")
            return preferences

    def extract_preferences_by_patterns(
        self, message_text: str
    ) -> List[PatientPreference]:
        """
        Extract preferences using pattern matching.

        Args:
            message_text: Patient message text

        Returns:
            List of extracted preferences
        """
        preferences = []
        text_lower = message_text.lower()

        try:
            # Communication time preferences
            time_preferences = [
                (r"\b(manhã|morning)\b", "morning"),
                (r"\b(tarde|afternoon)\b", "afternoon"),
                (r"\b(noite|evening|night)\b", "evening"),
            ]

            for pattern, time_period in time_preferences:
                if re.search(pattern, text_lower):
                    preferences.append(
                        PatientPreference(
                            preference_type="communication_time",
                            value=time_period,
                            confidence=0.7,
                            context=f"prefers {time_period} communication",
                        )
                    )

            # Communication frequency preferences
            frequency_patterns = [
                (r"\b(diário|daily|todos os dias)\b", "daily"),
                (r"\b(semanal|weekly|uma vez por semana)\b", "weekly"),
                (r"\b(menos mensagens|fewer messages)\b", "less_frequent"),
            ]

            for pattern, frequency in frequency_patterns:
                if re.search(pattern, text_lower):
                    preferences.append(
                        PatientPreference(
                            preference_type="communication_frequency",
                            value=frequency,
                            confidence=0.6,
                            context=f"prefers {frequency} communication",
                        )
                    )

            # Language preferences
            if re.search(r"\b(english|inglês)\b", text_lower):
                preferences.append(
                    PatientPreference(
                        preference_type="language",
                        value="english",
                        confidence=0.8,
                        context="prefers English communication",
                    )
                )

            return preferences

        except Exception as e:
            logger.error(f"Pattern-based preference extraction failed: {e}")
            return preferences

    async def extract_preferences_by_ai(
        self, message_text: str, patient_context: PatientContext
    ) -> List[PatientPreference]:
        """
        Extract preferences using AI.

        Args:
            message_text: Patient message text
            patient_context: Patient context

        Returns:
            List of extracted preferences
        """
        preferences = []

        try:
            preference_prompt = f"""
            Extract patient preferences and requests from this message.

            Patient context: {patient_context.treatment_type} treatment, day {patient_context.treatment_day}
            Message: "{message_text}"

            Look for preferences about:
            - Communication timing (morning, afternoon, evening)
            - Communication frequency (daily, weekly, less often)
            - Information detail level (brief, detailed)
            - Language preferences
            - Contact methods
            - Treatment approach preferences

            Format as JSON:
            {{
                "preferences": [
                    {{
                        "type": "preference_type",
                        "value": "preference_value",
                        "confidence": 0.0-1.0,
                        "context": "explanation"
                    }}
                ]
            }}
            """

            ai_response = await self.langchain_orchestrator.generate_text(
                preference_prompt
            )

            # Parse AI response
            try:
                parsed_response = json.loads(ai_response)
                for pref_data in parsed_response.get("preferences", []):
                    preferences.append(
                        PatientPreference(
                            preference_type=pref_data.get("type", "general"),
                            value=pref_data.get("value"),
                            confidence=float(pref_data.get("confidence", 0.5)),
                            context=pref_data.get("context", "AI extracted preference"),
                        )
                    )

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(
                    f"Failed to parse AI preference extraction response: {e}"
                )

            return preferences

        except Exception as e:
            logger.error(f"AI preference extraction failed: {e}")
            return preferences
