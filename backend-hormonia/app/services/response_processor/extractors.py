"""
Data extraction logic for response processing.
"""

import logging
import re
import unicodedata
from typing import Optional, Any
from uuid import UUID

from app.repositories.message import MessageRepository
from app.repositories.patient import PatientRepository
from app.models.flow import PatientFlowState
from app.services.ai import get_sentiment_analyzer, get_context_builder, ConcernLevel
from app.integrations import get_langchain_orchestrator
from app.services.analytics.data_extraction.concern_detector import ConcernDetector
from app.services.analytics.data_extraction.severity import (
    concern_level_from_score,
    concern_level_rank,
)
from app.exceptions import NotFoundError
from app.utils.constants import (
    URGENT_KEYWORDS,
    YES_PATTERNS,
    NO_PATTERNS,
    TIME_PATTERNS,
    MEDICATION_PATTERNS,
    PAIN_SCALE_PATTERN,
    POSITIVE_MOOD_PATTERNS,
    NEGATIVE_MOOD_PATTERNS,
)

from .models import (
    StructuredResponse,
    InboundMessage,
    ResponseType,
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

        # Lazy-initialized AI services (get_sentiment_analyzer is async)
        self._sentiment_analyzer = None
        self._sentiment_analyzer_enabled = config.enable_sentiment_analysis
        self.context_builder = (
            get_context_builder() if config.enable_ai_processing else None
        )
        self._concern_detector_ai_available = False
        orchestrator = None
        if config.enable_ai_processing:
            try:
                orchestrator = get_langchain_orchestrator()
                self._concern_detector_ai_available = True
            except Exception as exc:
                logger.warning(f"ConcernDetector unavailable: {exc}")
        self.concern_detector = ConcernDetector(orchestrator)

    @property
    def sentiment_analyzer(self):
        """Property for backward compatibility with tests that set this directly."""
        return self._sentiment_analyzer

    @sentiment_analyzer.setter
    def sentiment_analyzer(self, value):
        """Allow tests to set sentiment_analyzer directly."""
        self._sentiment_analyzer = value

    async def _get_sentiment_analyzer(self):
        """Lazy initialization of sentiment analyzer."""
        if self._sentiment_analyzer is None and self._sentiment_analyzer_enabled:
            self._sentiment_analyzer = await get_sentiment_analyzer()
        return self._sentiment_analyzer

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
            normalized_text = self._normalize_text(inbound_message.content)
            extracted_data = await self.extract_type_specific_data(
                inbound_message, response_type, flow_state
            )
            extracted_data["normalized_text"] = normalized_text

            # Early exit if AI processing is disabled
            if (
                not self.config.enable_ai_processing
                or not self.context_builder
                or not self._sentiment_analyzer_enabled
            ):
                return await self._build_fallback_structured_response(
                    patient_id,
                    inbound_message,
                    response_type,
                    normalized_text,
                    extracted_data,
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

            # Perform sentiment analysis (lazy-load service and keep flow explicit)
            try:
                sentiment_service = await self._get_sentiment_analyzer()
                (
                    sentiment_response,
                    concern_level,
                ) = await sentiment_service.analyze_sentiment(
                    inbound_message.content, patient_context
                )
            except Exception:
                logger.warning(
                    "Sentiment analysis failed; falling back to heuristic extraction",
                    exc_info=True,
                    extra={"patient_id": str(patient_id)},
                )
                return await self._build_fallback_structured_response(
                    patient_id,
                    inbound_message,
                    response_type,
                    normalized_text,
                    extracted_data,
                )

            sentiment_attr = getattr(sentiment_response, "sentiment", "neutral")
            sentiment_value = (
                sentiment_attr.value if hasattr(sentiment_attr, "value") else sentiment_attr
            )
            sentiment_confidence = getattr(sentiment_response, "confidence", 0.0)
            key_phrases = getattr(sentiment_response, "key_phrases", [])
            emotional_indicators = getattr(sentiment_response, "emotional_indicators", [])

            detector_concerns, detector_score = (
                await self._detect_concerns_with_detector(
                    inbound_message.content or normalized_text,
                    patient_context,
                )
            )
            keyword_concerns = self._extract_medical_concerns(normalized_text)
            sentiment_concerns = (
                getattr(sentiment_response, "medical_concerns", []) or []
            )
            medical_concerns = self._merge_concern_lists(
                sentiment_concerns,
                keyword_concerns,
                detector_concerns,
            )

            severity_score = self._calculate_severity_score(
                normalized_text,
                concern_level,
                medical_concerns,
                extracted_data,
            )
            severity_score = max(severity_score, detector_score)
            concern_level = self._dominant_concern_level(
                concern_level, severity_score
            )
            extracted_data["concern_detector_severity_score"] = detector_score
            extracted_data["severity_score"] = severity_score

            # Determine if attention is required
            requires_attention = (
                concern_level in [ConcernLevel.HIGH, ConcernLevel.CRITICAL]
                or medical_concerns
                or severity_score >= 7
                or self.contains_urgent_keywords(normalized_text)
            )

            return StructuredResponse(
                patient_id=patient_id,
                original_message=inbound_message.content,
                response_type=response_type,
                extracted_data=extracted_data,
                sentiment_analysis={
                    "sentiment": sentiment_value,
                    "confidence": sentiment_confidence,
                    "key_phrases": key_phrases,
                    "emotional_indicators": emotional_indicators,
                    "severity_score": severity_score,
                },
                medical_concerns=medical_concerns,
                concern_level=concern_level,
                requires_attention=requires_attention,
                severity_score=severity_score,
                confidence_score=sentiment_confidence,
            )

        except Exception as e:
            logger.error(f"Failed to extract structured data: {e}")
            raise

    async def _build_fallback_structured_response(
        self,
        patient_id: UUID,
        inbound_message: InboundMessage,
        response_type: ResponseType,
        normalized_text: str,
        extracted_data: dict[str, Any],
    ) -> StructuredResponse:
        """Build a safe, heuristic-based structured response."""
        detector_concerns, detector_score = await self._detect_concerns_with_detector(
            inbound_message.content or normalized_text, None
        )
        keyword_concerns = self._extract_medical_concerns(normalized_text)
        medical_concerns = self._merge_concern_lists(
            keyword_concerns, detector_concerns
        )
        severity_score = self._calculate_severity_score(
            normalized_text,
            ConcernLevel.LOW,
            medical_concerns,
            extracted_data,
        )
        severity_score = max(severity_score, detector_score)
        concern_level = self._dominant_concern_level(
            ConcernLevel.LOW, severity_score
        )
        requires_attention = (
            severity_score >= 7
            or bool(medical_concerns)
            or self.contains_urgent_keywords(normalized_text)
        )

        extracted_data["concern_detector_severity_score"] = detector_score
        extracted_data["severity_score"] = severity_score

        return StructuredResponse(
            patient_id=patient_id,
            original_message=inbound_message.content,
            response_type=response_type,
            extracted_data=extracted_data,
            sentiment_analysis={
                "sentiment": "neutral",
                "confidence": 0.0,
                "severity_score": severity_score,
            },
            medical_concerns=medical_concerns,
            concern_level=concern_level,
            requires_attention=requires_attention,
            severity_score=severity_score,
            confidence_score=0.0,
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
        normalized_text = self._normalize_text(inbound_message.content)
        extracted_data = {
            "raw_text": inbound_message.content,
            "normalized_text": normalized_text,
        }

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
                    await self.extract_text_patterns(normalized_text)
                )

            elif response_type == ResponseType.MEDIA:
                media_type = inbound_message.metadata.get("media_type")
                if not media_type and inbound_message.message_type:
                    media_type = getattr(inbound_message.message_type, "value", None)
                media_url = inbound_message.metadata.get("media_url") or inbound_message.metadata.get("url", "")
                extracted_data.update(
                    {
                        "media_type": media_type or "unknown",
                        "media_url": media_url or "",
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
                    "current_flow_day": flow_state.state_data.get(
                        "current_flow_day"
                    ),
                    "current_day_message_index": flow_state.state_data.get(
                        "current_day_message_index"
                    ),
                    "expected_response_type": flow_state.state_data.get(
                        "expected_response_type"
                    ),
                    "expected_response_format": flow_state.state_data.get(
                        "expected_response_format"
                    )
                    or flow_state.state_data.get("expected_format")
                    or flow_state.state_data.get("response_format"),
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
            normalized_text = self._normalize_text(text)
            text_lower = normalized_text.casefold()
            cleaned_text = re.sub(r"[^\w\s/.-]", " ", normalized_text)
            cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()

            # Extract yes/no responses
            if re.search(YES_PATTERNS, text_lower):
                patterns["boolean_response"] = True
            elif re.search(NO_PATTERNS, text_lower):
                patterns["boolean_response"] = False

            # Extract numbers
            numbers = re.findall(r"\b\d+(?:[.,]\d+)?\b", normalized_text)
            if numbers:
                parsed_numbers = []
                for number in numbers:
                    parsed_numbers.append(float(number.replace(",", ".")))
                patterns["numbers"] = parsed_numbers

            # Extract numeric response when message is only a number
            numeric_only = re.fullmatch(r"\d+(?:[.,]\d+)?", cleaned_text)
            if numeric_only:
                patterns["numeric_response"] = float(
                    numeric_only.group(0).replace(",", ".")
                )

            # Extract date references (basic formats)
            date_match = re.search(
                r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", cleaned_text
            )
            if date_match:
                patterns["date_response"] = date_match.group(0)

            # Extract numeric ranges (e.g., 1-10, 1 a 10)
            range_match = re.search(
                r"\b(\d+(?:[.,]\d+)?)\s*(?:-|a|ate|até)\s*(\d+(?:[.,]\d+)?)\b",
                text_lower,
            )
            if range_match:
                start_value = float(range_match.group(1).replace(",", "."))
                end_value = float(range_match.group(2).replace(",", "."))
                patterns["range_response"] = {"min": start_value, "max": end_value}

            # Extract time references
            time_matches = re.findall(TIME_PATTERNS, text_lower)
            if time_matches:
                patterns["time_references"] = time_matches

            # Extract medication names (basic pattern)
            if re.search(MEDICATION_PATTERNS, text_lower):
                patterns["medication_mentioned"] = True

            # Extract pain scale (1-10)
            pain_scale = re.search(PAIN_SCALE_PATTERN, text_lower)
            if pain_scale:
                patterns["pain_scale"] = int(pain_scale.group(1))

            # Extract mood indicators
            if re.search(POSITIVE_MOOD_PATTERNS, text_lower):
                patterns["mood_indicator"] = "positive"
            elif re.search(NEGATIVE_MOOD_PATTERNS, text_lower):
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
        text_lower = self._normalize_text(text).casefold()
        return any(keyword in text_lower for keyword in URGENT_KEYWORDS)

    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent matching."""
        normalized = unicodedata.normalize("NFKC", text or "")
        normalized = normalized.replace("\u00a0", " ")
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    async def _detect_concerns_with_detector(
        self, message_text: str, patient_context: Optional[Any]
    ) -> tuple[list[str], int]:
        """Detect medical concerns using ConcernDetector with safe fallbacks."""
        if not self.concern_detector:
            return [], 0

        use_ai = (
            self._concern_detector_ai_available
            and self.config.enable_ai_processing
            and patient_context is not None
        )

        try:
            if use_ai:
                concerns = await self.concern_detector.detect_medical_concerns(
                    message_text, patient_context
                )
            else:
                concerns = self.concern_detector.detect_concerns_by_patterns(
                    message_text
                )
        except Exception as exc:
            logger.warning(
                "ConcernDetector failed, falling back to pattern detection: %s",
                exc,
            )
            try:
                concerns = self.concern_detector.detect_concerns_by_patterns(
                    message_text
                )
            except Exception as fallback_exc:
                logger.warning(
                    "ConcernDetector pattern fallback failed: %s",
                    fallback_exc,
                )
                return [], 0

        return self._extract_detector_details(concerns)

    def _extract_detector_details(
        self, concerns: list[Any]
    ) -> tuple[list[str], int]:
        """Extract concern descriptions and max severity score."""
        descriptions: list[str] = []
        scores: list[int] = []

        for concern in concerns or []:
            description = getattr(concern, "description", "") or ""
            description = description.strip()
            if description:
                descriptions.append(description)

            severity_score = getattr(concern, "severity_score", None)
            if severity_score is None:
                severity = getattr(concern, "severity", None)
                if severity is not None:
                    severity_score = self._severity_score_from_level(severity)

            if severity_score is not None:
                try:
                    scores.append(int(severity_score))
                except (TypeError, ValueError):
                    continue

        max_score = max(scores) if scores else 0
        return descriptions, max_score

    def _severity_score_from_level(self, severity: Any) -> int:
        """Map concern level to a numeric score."""
        level_value = (
            severity.value if hasattr(severity, "value") else str(severity)
        )
        mapping = {
            ConcernLevel.LOW.value: 2,
            ConcernLevel.MEDIUM.value: 5,
            ConcernLevel.HIGH.value: 7,
            ConcernLevel.CRITICAL.value: 9,
        }
        return mapping.get(level_value, 0)

    def _merge_concern_lists(self, *concern_lists: list[str]) -> list[str]:
        """Merge and deduplicate concern strings."""
        merged: list[str] = []
        for concerns in concern_lists:
            if not concerns or isinstance(concerns, bool):
                continue
            if isinstance(concerns, (str, bytes)):
                concerns_iterable = [concerns]
            else:
                try:
                    concerns_iterable = list(concerns)
                except TypeError:
                    continue
            for concern in concerns_iterable:
                if not concern:
                    continue
                merged.append(concern.strip())

        return list(
            {concern.casefold(): concern for concern in merged}.values()
        )

    def _extract_medical_concerns(self, text: str) -> list[str]:
        """Extract medical concern keywords without AI dependencies."""
        concerns = []
        text_lower = text.casefold()

        keyword_patterns = {
            "dor forte": [
                r"\bdor (muito )?forte\b",
                r"\bdor intensa\b",
                r"\bdor insuportavel\b",
                r"\bdor insuportável\b",
            ],
            "dor no peito": [
                r"\bdor no peito\b",
                r"\bchest pain\b",
            ],
            "falta de ar": [
                r"\bfalta de ar\b",
                r"\bnao consigo respirar\b",
                r"\bnão consigo respirar\b",
                r"\bdificuldade para respirar\b",
            ],
            "sangramento": [
                r"\bsangramento\b",
                r"\bhemorragia\b",
                r"\bsangrando\b",
            ],
            "febre alta": [
                r"\bfebre alta\b",
                r"\bfebre muito alta\b",
                r"\btemperatura alta\b",
                r"\bfebre [3-4]\d\b",
            ],
            "vomito": [
                r"\bvomito\b",
                r"\bvomitando\b",
                r"\bvomiting\b",
            ],
        }

        for label, patterns in keyword_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    concerns.append(label)
                    break

        return concerns

    def _calculate_severity_score(
        self,
        text: str,
        concern_level: ConcernLevel,
        medical_concerns: list[str],
        extracted_data: dict[str, Any],
    ) -> int:
        """Calculate a 1-10 severity score from keywords and context."""
        score = 1
        text_lower = text.casefold()

        if self.contains_urgent_keywords(text_lower):
            score = max(score, 9)

        if any(
            keyword in text_lower
            for keyword in [
                "dor insuportavel",
                "dor muito forte",
                "falta de ar",
                "nao consigo respirar",
                "sangramento intenso",
                "desmaio",
            ]
        ):
            score = max(score, 8)

        if any(keyword in text_lower for keyword in ["febre alta", "febre 39", "febre 40"]):
            score = max(score, 7)

        pain_scale = extracted_data.get("pain_scale")
        if isinstance(pain_scale, int):
            score = max(score, min(10, pain_scale))

        if medical_concerns:
            score = max(score, 4)

        concern_rank = self._concern_rank(concern_level)
        if concern_rank >= 4:
            score = max(score, 9)
        elif concern_rank == 3:
            score = max(score, 7)
        elif concern_rank == 2:
            score = max(score, 5)

        return min(score, 10)

    def _concern_level_from_score(self, severity_score: int) -> ConcernLevel:
        """Map numeric severity score to concern level."""
        return concern_level_from_score(severity_score)

    def _concern_rank(self, concern_level: ConcernLevel) -> int:
        """Rank concern levels for comparison."""
        return concern_level_rank(concern_level)

    def _dominant_concern_level(
        self, concern_level: ConcernLevel, severity_score: int
    ) -> ConcernLevel:
        """Choose the highest concern level between AI and score."""
        score_level = self._concern_level_from_score(severity_score)
        if self._concern_rank(score_level) > self._concern_rank(concern_level):
            return score_level
        return concern_level
