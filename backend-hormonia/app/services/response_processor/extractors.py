"""
Data extraction logic for response processing.
"""

import logging
import re
from typing import Optional, Any
from uuid import UUID

from app.repositories.message import MessageRepository
from app.repositories.patient import PatientRepository
from app.models.flow import PatientFlowState
from app.services.ai import get_sentiment_analyzer, get_context_builder
from app.exceptions import NotFoundError

from .models import (
    StructuredResponse,
    InboundMessage,
    ResponseType,
    ResponseFactory,
    ResponseProcessorConfig,
)

logger = logging.getLogger(__name__)


class DataExtractor:
    """Extracts structured data from patient responses."""

    def __init__(self, db: Any, config: ResponseProcessorConfig):
        """
        Initialize data extractor.

        Args:
            db: Database session
            config: Processor configuration
        """
        self.db = db
        self.config = config
        self.patient_repo = PatientRepository(db)
        self.message_repo = MessageRepository(db)

        # Initialize AI services only if enabled
        self.sentiment_analyzer = (
            get_sentiment_analyzer() if config.enable_sentiment_analysis else None
        )
        self.context_builder = (
            get_context_builder() if config.enable_ai_processing else None
        )

    async def extract_structured_data(
        self,
        patient_id: UUID,
        inbound_message: InboundMessage,
        response_type: ResponseType,
        flow_state: Optional[PatientFlowState],
    ) -> StructuredResponse:
        """
        Extract structured data from patient response using AI.

        Args:
            patient_id: Patient identifier
            inbound_message: Inbound message data
            response_type: Type of response
            flow_state: Optional current flow state

        Returns:
            Structured response with extracted data
        """
        try:
            # Early exit if AI processing is disabled
            if (
                not self.config.enable_ai_processing
                or not self.context_builder
                or not self.sentiment_analyzer
            ):
                return ResponseFactory.create_fallback_response(
                    patient_id=patient_id,
                    original_message=inbound_message.content,
                    response_type=response_type,
                )

            # Get patient context for AI analysis
            patient = self.patient_repo.get(patient_id)
            if not patient:
                raise NotFoundError(f"Patient {patient_id} not found")

            # Get recent message history
            recent_messages = self.message_repo.get_conversation_history(
                patient_id, limit=10
            )
            recent_message_data = [
                {
                    "content": msg.content,
                    "direction": msg.direction.value,
                    "timestamp": msg.created_at.isoformat(),
                }
                for msg in recent_messages
            ]

            # Build patient context
            patient_context = await self.context_builder.build_patient_context(
                patient_id=str(patient_id),
                patient_data={
                    "name": patient.name,
                    "treatment_type": getattr(patient, "treatment_type", "general"),
                    "current_day": flow_state.current_step if flow_state else 1,
                    "treatment_start_date": flow_state.started_at.isoformat()
                    if flow_state
                    else None,
                    "age": getattr(patient, "age", None),
                    "preferences": getattr(patient, "preferences", {}),
                },
                recent_messages=recent_message_data,
                medical_data=getattr(patient, "medical_history", {}),
            )

            # Check Redis cache for similar sentiment analysis
            import hashlib
            import json
            from app.core.redis_manager import get_sync_redis_client
            
            # Create cache key from message content hash (short messages may have similar analyses)
            content_hash = hashlib.sha256(inbound_message.content.encode()).hexdigest()[:16]
            sentiment_cache_key = f"sentiment_analysis:{content_hash}"
            sentiment_cache_ttl = 3600  # 1 hour
            
            cached_sentiment = None
            try:
                redis_client = get_sync_redis_client()
                if redis_client:
                    cached_data = redis_client.get(sentiment_cache_key)
                    if cached_data:
                        cached_sentiment = json.loads(cached_data)
                        logger.debug(f"Sentiment cache hit for {sentiment_cache_key}")
            except Exception as e:
                logger.warning(f"Redis sentiment cache error: {e}")
            
            if cached_sentiment:
                # Use cached result
                from app.services.ai import ConcernLevel
                sentiment_response = type('SentimentResponse', (), cached_sentiment['response'])()
                concern_level = ConcernLevel(cached_sentiment['concern_level'])
            else:
                # Perform sentiment analysis
                (
                    sentiment_response,
                    concern_level,
                ) = await self.sentiment_analyzer.analyze_response(
                    inbound_message.content, patient_context
                )
                
                # Cache the result
                try:
                    if redis_client:
                        cache_data = {
                            "response": {
                                "sentiment": sentiment_response.sentiment.value,
                                "confidence": sentiment_response.confidence,
                                "key_phrases": sentiment_response.key_phrases,
                                "emotional_indicators": sentiment_response.emotional_indicators,
                                "medical_concerns": sentiment_response.medical_concerns,
                            },
                            "concern_level": concern_level.value
                        }
                        redis_client.setex(sentiment_cache_key, sentiment_cache_ttl, json.dumps(cache_data))
                        logger.debug(f"Cached sentiment analysis for {sentiment_cache_key}")
                except Exception as e:
                    logger.warning(f"Failed to cache sentiment analysis: {e}")

            # Extract data based on response type
            extracted_data = await self.extract_type_specific_data(
                inbound_message, response_type, flow_state
            )

            # Determine if attention is required
            requires_attention = (
                concern_level in [ConcernLevel.HIGH, ConcernLevel.CRITICAL]
                or sentiment_response.medical_concerns
                or self.contains_urgent_keywords(inbound_message.content)
            )

            return StructuredResponse(
                patient_id=patient_id,
                original_message=inbound_message.content,
                response_type=response_type,
                extracted_data=extracted_data,
                sentiment_analysis={
                    "sentiment": sentiment_response.sentiment.value,
                    "confidence": sentiment_response.confidence,
                    "key_phrases": sentiment_response.key_phrases,
                    "emotional_indicators": sentiment_response.emotional_indicators,
                },
                medical_concerns=sentiment_response.medical_concerns,
                concern_level=concern_level,
                requires_attention=requires_attention,
                confidence_score=sentiment_response.confidence,
            )

        except Exception as e:
            logger.error(f"Failed to extract structured data: {e}")
            # Return fallback response on failure
            return ResponseFactory.create_fallback_response(
                patient_id=patient_id,
                original_message=inbound_message.content,
                response_type=response_type,
            )

    async def extract_type_specific_data(
        self,
        inbound_message: InboundMessage,
        response_type: ResponseType,
        flow_state: Optional[PatientFlowState],
    ) -> dict[str, Any]:
        """
        Extract data specific to response type.

        Args:
            inbound_message: Inbound message data
            response_type: Type of response
            flow_state: Optional current flow state

        Returns:
            Dictionary of extracted data
        """
        extracted_data = {"raw_text": inbound_message.content}

        try:
            if response_type == ResponseType.BUTTON:
                extracted_data.update(
                    {
                        "button_value": inbound_message.content,
                        "button_metadata": inbound_message.metadata.get(
                            "button_data", {}
                        ),
                    }
                )

            elif response_type == ResponseType.QUICK_REPLY:
                extracted_data.update(
                    {
                        "quick_reply_value": inbound_message.content,
                        "quick_reply_payload": inbound_message.metadata.get(
                            "payload", ""
                        ),
                    }
                )

            elif response_type == ResponseType.LIST_SELECTION:
                extracted_data.update(
                    {
                        "selected_option": inbound_message.content,
                        "list_metadata": inbound_message.metadata.get("list_data", {}),
                    }
                )

            elif response_type == ResponseType.TEXT:
                # Extract common patterns from free text
                extracted_data.update(
                    await self.extract_text_patterns(inbound_message.content)
                )

            elif response_type == ResponseType.MEDIA:
                extracted_data.update(
                    {
                        "media_type": inbound_message.metadata.get(
                            "media_type", "unknown"
                        ),
                        "media_url": inbound_message.metadata.get("media_url", ""),
                        "caption": inbound_message.content,
                    }
                )

            elif response_type == ResponseType.LOCATION:
                extracted_data.update(
                    {
                        "latitude": inbound_message.metadata.get("latitude"),
                        "longitude": inbound_message.metadata.get("longitude"),
                        "address": inbound_message.content,
                    }
                )

            # Add flow context data
            if flow_state:
                extracted_data["flow_context"] = {
                    "flow_type": flow_state.flow_type,
                    "current_step": flow_state.current_step,
                    "expected_response_type": flow_state.state_data.get(
                        "expected_response_type"
                    ),
                    "question_context": flow_state.state_data.get("last_question", ""),
                }

            return extracted_data

        except Exception as e:
            logger.error(f"Failed to extract type-specific data: {e}")
            return extracted_data

    async def extract_text_patterns(self, text: str) -> dict[str, Any]:
        """
        Extract common patterns from free text responses.

        Args:
            text: Text to analyze

        Returns:
            Dictionary of extracted patterns
        """
        patterns = {}

        try:
            # Extract yes/no responses
            yes_patterns = r"\b(sim|yes|yeah|ok|okay|claro|certo|positivo)\b"
            no_patterns = r"\b(não|no|nope|never|negativo|jamais)\b"

            if re.search(yes_patterns, text.lower()):
                patterns["boolean_response"] = True
            elif re.search(no_patterns, text.lower()):
                patterns["boolean_response"] = False

            # Extract numbers
            numbers = re.findall(r"\b\d+(?:\.\d+)?\b", text)
            if numbers:
                patterns["numbers"] = [float(n) for n in numbers]

            # Extract time references
            time_patterns = r"\b(\d{1,2}):(\d{2})\b|(\d{1,2})\s*(am|pm|h|horas?)\b"
            time_matches = re.findall(time_patterns, text.lower())
            if time_matches:
                patterns["time_references"] = time_matches

            # Extract medication names (basic pattern)
            med_patterns = r"\b(mg|ml|comprimido|cápsula|medicamento|remédio)\b"
            if re.search(med_patterns, text.lower()):
                patterns["medication_mentioned"] = True

            # Extract pain scale (1-10)
            pain_scale = re.search(
                r"\b([1-9]|10)\b.*\b(dor|pain|scale|escala)\b", text.lower()
            )
            if pain_scale:
                patterns["pain_scale"] = int(pain_scale.group(1))

            # Extract mood indicators
            positive_mood = r"\b(bem|good|great|ótimo|feliz|happy|melhor|better)\b"
            negative_mood = r"\b(mal|bad|terrible|péssimo|triste|sad|pior|worse)\b"

            if re.search(positive_mood, text.lower()):
                patterns["mood_indicator"] = "positive"
            elif re.search(negative_mood, text.lower()):
                patterns["mood_indicator"] = "negative"

            return patterns

        except Exception as e:
            logger.error(f"Failed to extract text patterns: {e}")
            return {}

    def contains_urgent_keywords(self, text: str) -> bool:
        """
        Check if text contains urgent keywords requiring immediate attention.

        Args:
            text: Text to check

        Returns:
            True if urgent keywords found
        """
        urgent_keywords = [
            "emergency",
            "emergência",
            "urgent",
            "urgente",
            "help",
            "ajuda",
            "hospital",
            "ambulance",
            "ambulância",
            "severe",
            "severo",
            "can't breathe",
            "não consigo respirar",
            "chest pain",
            "dor no peito",
            "bleeding",
            "sangramento",
            "unconscious",
            "inconsciente",
        ]

        text_lower = text.lower()
        return any(keyword in text_lower for keyword in urgent_keywords)
