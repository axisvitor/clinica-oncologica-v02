"""
Entity extraction functionality.
Handles extraction of structured entities from patient messages.
"""

import logging
import re
import json
from typing import List

from app.services.ai import PatientContext
from app.integrations.openai_client import LangChainOrchestrator

from .models import ExtractedEntity
from .patterns import MedicalPatterns

logger = logging.getLogger(__name__)


class EntityExtractor:
    """Handles entity extraction from patient messages."""

    def __init__(self, langchain_orchestrator: LangChainOrchestrator):
        """
        Initialize entity extractor.

        Args:
            langchain_orchestrator: LangChain orchestrator for AI extraction
        """
        self.langchain_orchestrator = langchain_orchestrator
        self.patterns = MedicalPatterns()

    async def extract_entities(
        self, message_text: str, patient_context: PatientContext
    ) -> List[ExtractedEntity]:
        """
        Extract entities from message using AI and pattern matching.

        Args:
            message_text: Patient message text
            patient_context: Patient context

        Returns:
            List of extracted entities
        """
        entities = []

        try:
            # Extract using pattern matching
            pattern_entities = self.extract_entities_by_patterns(message_text)
            entities.extend(pattern_entities)

            # Extract using AI
            ai_entities = await self.extract_entities_by_ai(
                message_text, patient_context
            )
            entities.extend(ai_entities)

            # Remove duplicates and merge similar entities
            entities = self.deduplicate_entities(entities)

            return entities

        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return entities

    def extract_entities_by_patterns(self, message_text: str) -> List[ExtractedEntity]:
        """
        Extract entities using regex patterns.

        Args:
            message_text: Patient message text

        Returns:
            List of extracted entities
        """
        entities = []
        text_lower = message_text.lower()

        try:
            # Extract pain scale
            pain_scale_match = re.search(
                self.patterns.pain_patterns["pain_scale"], text_lower
            )
            if pain_scale_match:
                entities.append(
                    ExtractedEntity(
                        entity_type="pain_scale",
                        value=int(pain_scale_match.group(1)),
                        confidence=0.9,
                        context="pain scale rating",
                        source_text=pain_scale_match.group(0),
                    )
                )

            # Extract medication dosage
            dosage_matches = re.finditer(
                self.patterns.medication_patterns["dosage"], text_lower
            )
            for match in dosage_matches:
                entities.append(
                    ExtractedEntity(
                        entity_type="medication_dosage",
                        value={"amount": float(match.group(1)), "unit": match.group(2)},
                        confidence=0.8,
                        context="medication dosage",
                        source_text=match.group(0),
                    )
                )

            # Extract numbers
            numbers = re.findall(r"\b\d+(?:\.\d+)?\b", message_text)
            for number in numbers:
                entities.append(
                    ExtractedEntity(
                        entity_type="numeric_value",
                        value=float(number),
                        confidence=0.6,
                        context="numeric mention",
                        source_text=number,
                    )
                )

            # Extract time references
            time_patterns = [
                r"\b(\d{1,2}):(\d{2})\b",
                r"\b(\d{1,2})\s*(am|pm|h|horas?)\b",
                r"\b(manhã|morning|tarde|afternoon|noite|night|evening)\b",
            ]

            for pattern in time_patterns:
                matches = re.finditer(pattern, text_lower)
                for match in matches:
                    entities.append(
                        ExtractedEntity(
                            entity_type="time_reference",
                            value=match.group(0),
                            confidence=0.7,
                            context="time mention",
                            source_text=match.group(0),
                        )
                    )

            # Extract yes/no responses
            yes_pattern = r"\b(sim|yes|yeah|ok|okay|claro|certo|positivo)\b"
            no_pattern = r"\b(não|no|nope|never|negativo|jamais)\b"

            yes_match = re.search(yes_pattern, text_lower)
            no_match = re.search(no_pattern, text_lower)

            if yes_match:
                entities.append(
                    ExtractedEntity(
                        entity_type="boolean_response",
                        value=True,
                        confidence=0.8,
                        context="affirmative response",
                        source_text=yes_match.group(0),
                    )
                )
            elif no_match:
                entities.append(
                    ExtractedEntity(
                        entity_type="boolean_response",
                        value=False,
                        confidence=0.8,
                        context="negative response",
                        source_text=no_match.group(0),
                    )
                )

            return entities

        except Exception as e:
            logger.error(f"Pattern-based entity extraction failed: {e}")
            return entities

    async def extract_entities_by_ai(
        self, message_text: str, patient_context: PatientContext
    ) -> List[ExtractedEntity]:
        """
        Extract entities using AI.

        Args:
            message_text: Patient message text
            patient_context: Patient context

        Returns:
            List of extracted entities
        """
        entities = []

        try:
            extraction_prompt = f"""
            Extract structured entities from this patient message. Focus on medical information, measurements, and preferences.

            Patient context: {patient_context.treatment_type} treatment, day {patient_context.treatment_day}
            Message: "{message_text}"

            Extract and format as JSON:
            {{
                "entities": [
                    {{
                        "type": "entity_type",
                        "value": "extracted_value",
                        "confidence": 0.0-1.0,
                        "context": "description"
                    }}
                ]
            }}

            Entity types to look for:
            - symptoms: any health symptoms mentioned
            - medications: medication names or references
            - side_effects: reported side effects
            - pain_level: pain descriptions or ratings
            - mood_state: emotional state indicators
            - preferences: patient preferences or requests
            - measurements: any numeric health measurements
            - time_references: time-related information
            """

            ai_response = await self.langchain_orchestrator.generate_text(
                extraction_prompt
            )

            # Parse AI response (simplified - in production, use proper JSON parsing)
            try:
                parsed_response = json.loads(ai_response)
                for entity_data in parsed_response.get("entities", []):
                    entities.append(
                        ExtractedEntity(
                            entity_type=entity_data.get("type", "unknown"),
                            value=entity_data.get("value"),
                            confidence=float(entity_data.get("confidence", 0.5)),
                            context=entity_data.get("context", "AI extracted"),
                            source_text=message_text[:50],  # First 50 chars as source
                        )
                    )
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Failed to parse AI entity extraction response: {e}")

            return entities

        except Exception as e:
            logger.error(f"AI entity extraction failed: {e}")
            return entities

    def deduplicate_entities(
        self, entities: List[ExtractedEntity]
    ) -> List[ExtractedEntity]:
        """
        Remove duplicate entities and merge similar ones.

        Args:
            entities: List of extracted entities

        Returns:
            Deduplicated list of entities
        """
        seen_entities: dict[str, ExtractedEntity] = {}

        for entity in entities:
            key = f"{entity.entity_type}_{str(entity.value)}"

            if key in seen_entities:
                # Keep the one with higher confidence
                existing = seen_entities[key]
                if entity.confidence > existing.confidence:
                    seen_entities[key] = entity
            else:
                seen_entities[key] = entity

        return list(seen_entities.values())
