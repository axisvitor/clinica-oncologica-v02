"""
Main data extraction service.
Orchestrates entity extraction, concern detection, and preference extraction.
"""
import logging
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import UUID

from app.services.ai import (
    get_ai_service,
    PatientContext,
    ConcernLevel
)
from app.integrations.openai_client import (
    get_langchain_orchestrator,
    LangChainOrchestrator
)
from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.repositories.patient import PatientRepository
from app.repositories.flow import FlowStateRepository
from app.repositories.message import MessageRepository
from app.exceptions import ExternalServiceError

from .models import (
    ResponseCategory,
    ExtractedEntity,
    MedicalConcern,
    PatientPreference,
    StructuredExtractionResult
)
from .entity_extractor import EntityExtractor
from .concern_detector import ConcernDetector
from .preference_extractor import PreferenceExtractor

logger = logging.getLogger(__name__)


class DataExtractionService:
    """
    AI-powered structured data extraction service for patient responses.
    Handles categorization, entity extraction, medical concern detection,
    and patient preference identification.
    """

    def __init__(self, db: Any):
        """
        Initialize data extraction service.

        Args:
            db: Database session
        """
        self.db = db
        self.patient_repo = PatientRepository(db)
        self.flow_state_repo = FlowStateRepository(db)
        self.message_repo = MessageRepository(db)
        self.sentiment_analyzer = get_ai_service()  # Returns coroutine, will be awaited when used
        self.langchain_orchestrator = get_langchain_orchestrator()

        # Initialize specialized extractors
        self.entity_extractor = EntityExtractor(self.langchain_orchestrator)
        self.concern_detector = ConcernDetector(self.langchain_orchestrator)
        self.preference_extractor = PreferenceExtractor(self.langchain_orchestrator)

        logger.info("Data Extraction Service initialized")

    async def extract_structured_data(self,
                                    patient_id: UUID,
                                    message_text: str,
                                    flow_context: Optional[PatientFlowState] = None) -> StructuredExtractionResult:
        """
        Extract structured data from patient message using AI and pattern matching.

        Args:
            patient_id: Patient UUID
            message_text: Patient message text
            flow_context: Optional flow context

        Returns:
            Structured extraction result

        Raises:
            ExternalServiceError: If AI service fails
        """
        try:
            processing_notes = []

            # Get patient context
            patient_context = await self._build_patient_context(patient_id, flow_context)

            # Categorize response
            response_category = await self._categorize_response(message_text, patient_context)
            processing_notes.append(f"Categorized as: {response_category.value}")

            # Extract entities using multiple methods
            extracted_entities = await self.entity_extractor.extract_entities(
                message_text, patient_context
            )
            processing_notes.append(f"Extracted {len(extracted_entities)} entities")

            # Detect medical concerns
            medical_concerns = await self.concern_detector.detect_medical_concerns(
                message_text, patient_context
            )
            processing_notes.append(f"Detected {len(medical_concerns)} medical concerns")

            # Extract patient preferences
            patient_preferences = await self.preference_extractor.extract_patient_preferences(
                message_text, patient_context
            )
            processing_notes.append(f"Extracted {len(patient_preferences)} preferences")

            # Perform sentiment analysis
            sentiment_response, concern_level = await self.sentiment_analyzer.analyze_sentiment(  # type: ignore[attr-defined]
                message_text, patient_context
            )

            sentiment_analysis = {
                "sentiment": sentiment_response.sentiment.value,
                "confidence": sentiment_response.confidence,
                "concern_level": concern_level.value,
                "key_phrases": sentiment_response.key_phrases,
                "emotional_indicators": sentiment_response.emotional_indicators,
                "medical_concerns": sentiment_response.medical_concerns
            }

            # Calculate overall confidence score
            confidence_score = self._calculate_confidence_score(
                extracted_entities, medical_concerns, sentiment_response.confidence
            )

            return StructuredExtractionResult(
                patient_id=patient_id,
                original_message=message_text,
                response_category=response_category,
                extracted_entities=extracted_entities,
                medical_concerns=medical_concerns,
                patient_preferences=patient_preferences,
                sentiment_analysis=sentiment_analysis,
                confidence_score=confidence_score,
                processing_notes=processing_notes
            )

        except Exception as e:
            logger.error(f"Failed to extract structured data: {e}")
            raise ExternalServiceError(f"Data extraction failed: {str(e)}")

    async def _build_patient_context(self,
                                   patient_id: UUID,
                                   flow_context: Optional[PatientFlowState]) -> PatientContext:
        """Build comprehensive patient context for AI processing."""
        try:
            patient = self.patient_repo.get(patient_id)
            if not patient:
                raise ValueError(f"Patient {patient_id} not found")

            # Get recent message history
            recent_messages = self.message_repo.get_conversation_history(patient_id, limit=10)
            recent_message_data = [
                {
                    "content": msg.content,
                    "direction": msg.direction.value,
                    "timestamp": msg.created_at.isoformat()
                }
                for msg in recent_messages
            ]

            # Build context - context_builder is AIService instance
            ai_service = await get_ai_service()
            return await ai_service.build_patient_context(  # type: ignore[attr-defined]
                patient_id=str(patient_id),
                patient_data={
                    "name": patient.name,
                    "treatment_type": getattr(patient, 'treatment_type', 'general'),
                    "current_day": flow_context.current_step if flow_context else 1,
                    "treatment_start_date": flow_context.started_at.isoformat() if flow_context else None,
                    "age": getattr(patient, 'age', None),
                    "preferences": getattr(patient, 'preferences', {})
                },
                recent_messages=recent_message_data,
                medical_data=getattr(patient, 'medical_history', {})
            )

        except Exception as e:
            logger.error(f"Failed to build patient context: {e}")
            raise

    async def _categorize_response(self,
                                 message_text: str,
                                 patient_context: PatientContext) -> ResponseCategory:
        """Categorize patient response using AI and pattern matching."""
        try:
            # Use AI for categorization
            categorization_prompt = f"""
            Categorize this patient message into one of these categories:
            - symptom_report: Patient reporting symptoms or health changes
            - medication_inquiry: Questions about medications or dosage
            - side_effect_report: Reporting medication side effects
            - emotional_expression: Expressing emotions or mental state
            - question_answer: Answering a specific question
            - appointment_request: Requesting appointment or consultation
            - general_conversation: General conversation or greeting
            - emergency_concern: Urgent medical concern
            - treatment_feedback: Feedback about treatment progress
            - lifestyle_update: Updates about lifestyle, diet, exercise

            Patient context: {patient_context.treatment_type} treatment, day {patient_context.treatment_day}
            Message: "{message_text}"

            Return only the category name.
            """

            try:
                ai_category = await self.langchain_orchestrator.generate_text(categorization_prompt)
                ai_category = ai_category.strip().lower()

                # Validate AI response
                for category in ResponseCategory:
                    if category.value in ai_category:
                        return category
            except Exception as e:
                logger.warning(f"AI categorization failed, using pattern matching: {e}")

            # Fallback to pattern matching
            return self._categorize_by_patterns(message_text)

        except Exception as e:
            logger.error(f"Response categorization failed: {e}")
            return ResponseCategory.GENERAL_CONVERSATION

    def _categorize_by_patterns(self, message_text: str) -> ResponseCategory:
        """Categorize response using pattern matching."""
        text_lower = message_text.lower()

        # Emergency patterns
        emergency_patterns = [
            r'\b(emergência|emergency|urgent|urgente|help|ajuda|hospital)\b',
            r'\b(não consigo respirar|can\'t breathe|chest pain|dor no peito)\b'
        ]
        if any(re.search(pattern, text_lower) for pattern in emergency_patterns):
            return ResponseCategory.EMERGENCY_CONCERN

        # Symptom patterns
        symptom_patterns = [
            r'\b(sintoma|symptom|sinto|feeling|dor|pain|náusea|nausea)\b',
            r'\b(febre|fever|cansaço|tired|tontura|dizzy)\b'
        ]
        if any(re.search(pattern, text_lower) for pattern in symptom_patterns):
            return ResponseCategory.SYMPTOM_REPORT

        # Medication patterns
        medication_patterns = [
            r'\b(medicamento|medication|remédio|medicine|comprimido|tablet)\b',
            r'\b(dosagem|dosage|quando tomar|when to take)\b'
        ]
        if any(re.search(pattern, text_lower) for pattern in medication_patterns):
            return ResponseCategory.MEDICATION_INQUIRY

        # Emotional patterns
        emotional_patterns = [
            r'\b(sinto|feel|emoção|emotion|triste|sad|feliz|happy|ansiosa|anxious)\b',
            r'\b(preocupada|worried|medo|fear|esperança|hope)\b'
        ]
        if any(re.search(pattern, text_lower) for pattern in emotional_patterns):
            return ResponseCategory.EMOTIONAL_EXPRESSION

        # Question patterns
        question_patterns = [r'\?', r'\b(sim|yes|não|no|talvez|maybe)\b']
        if any(re.search(pattern, text_lower) for pattern in question_patterns):
            return ResponseCategory.QUESTION_ANSWER

        return ResponseCategory.GENERAL_CONVERSATION

    def _calculate_confidence_score(self,
                                  entities: List[ExtractedEntity],
                                  concerns: List[MedicalConcern],
                                  sentiment_confidence: float) -> float:
        """Calculate overall confidence score for extraction."""
        try:
            if not entities and not concerns:
                return sentiment_confidence

            # Calculate average entity confidence
            entity_confidence = 0.0
            if entities:
                entity_confidence = sum(e.confidence for e in entities) / len(entities)

            # Calculate average concern confidence
            concern_confidence = 0.0
            if concerns:
                concern_confidence = sum(c.confidence for c in concerns) / len(concerns)

            # Weight the scores
            weights = []
            scores = []

            if entities:
                weights.append(0.4)
                scores.append(entity_confidence)

            if concerns:
                weights.append(0.4)
                scores.append(concern_confidence)

            weights.append(0.2)
            scores.append(sentiment_confidence)

            # Calculate weighted average
            total_weight = sum(weights)
            weighted_sum = sum(w * s for w, s in zip(weights, scores))

            return weighted_sum / total_weight if total_weight > 0 else 0.0

        except Exception as e:
            logger.error(f"Confidence calculation failed: {e}")
            return 0.5  # Default medium confidence

    async def analyze_response_accuracy(self,
                                      extraction_results: List[StructuredExtractionResult],
                                      ground_truth_data: Optional[List[Dict[str, Any]]] = None) -> Dict[str, float]:
        """
        Analyze accuracy of extraction results (for testing and improvement).

        Args:
            extraction_results: List of extraction results
            ground_truth_data: Optional ground truth for comparison

        Returns:
            Accuracy metrics
        """
        try:
            metrics = {
                "total_extractions": len(extraction_results),
                "avg_confidence": 0.0,
                "entity_extraction_rate": 0.0,
                "concern_detection_rate": 0.0,
                "preference_extraction_rate": 0.0,
                "high_confidence_rate": 0.0
            }

            if not extraction_results:
                return metrics

            # Calculate average confidence
            total_confidence = sum(result.confidence_score for result in extraction_results)
            metrics["avg_confidence"] = total_confidence / len(extraction_results)

            # Calculate extraction rates
            with_entities = sum(1 for result in extraction_results if result.extracted_entities)
            metrics["entity_extraction_rate"] = with_entities / len(extraction_results)

            with_concerns = sum(1 for result in extraction_results if result.medical_concerns)
            metrics["concern_detection_rate"] = with_concerns / len(extraction_results)

            with_preferences = sum(1 for result in extraction_results if result.patient_preferences)
            metrics["preference_extraction_rate"] = with_preferences / len(extraction_results)

            # High confidence rate (>0.7)
            high_confidence = sum(1 for result in extraction_results if result.confidence_score > 0.7)
            metrics["high_confidence_rate"] = high_confidence / len(extraction_results)

            return metrics

        except Exception as e:
            logger.error(f"Accuracy analysis failed: {e}")
            return {"error": str(e)}  # type: ignore[dict-item]

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on data extraction service."""
        try:
            health_status = {
                "service": "DataExtractionService",
                "timestamp": datetime.utcnow().isoformat(),
                "healthy": True,
                "components": {}
            }

            # Check AI services
            try:
                test_response = await self.langchain_orchestrator.generate_text("Test message")
                health_status["components"]["ai_service"] = {  # type: ignore[index]
                    "healthy": True,
                    "response_received": bool(test_response)
                }
            except Exception as e:
                health_status["components"]["ai_service"] = {  # type: ignore[index]
                    "healthy": False,
                    "error": str(e)
                }
                health_status["healthy"] = False

            # Check sentiment analyzer
            try:
                # Create dummy context for test
                test_context = PatientContext(
                    patient_id="test",
                    name="Test",
                    treatment_type="test",
                    treatment_day=1
                )
                ai_service = await get_ai_service()
                sentiment_result, _ = await ai_service.analyze_sentiment(  # type: ignore[attr-defined]
                    "Test message", test_context
                )
                health_status["components"]["sentiment_analyzer"] = {  # type: ignore[index]
                    "healthy": True,
                    "sentiment_detected": bool(sentiment_result.sentiment)
                }
            except Exception as e:
                health_status["components"]["sentiment_analyzer"] = {  # type: ignore[index]
                    "healthy": False,
                    "error": str(e)
                }
                health_status["healthy"] = False

            # Check database connectivity
            try:
                self.db.execute("SELECT 1")
                health_status["components"]["database"] = {"healthy": True}  # type: ignore[index]
            except Exception as e:
                health_status["components"]["database"] = {  # type: ignore[index]
                    "healthy": False,
                    "error": str(e)
                }
                health_status["healthy"] = False

            return health_status

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "service": "DataExtractionService",
                "timestamp": datetime.utcnow().isoformat(),
                "healthy": False,
                "error": str(e)
            }


# Global service instance
_data_extraction_service: Optional[DataExtractionService] = None


def get_data_extraction_service(db: Any) -> DataExtractionService:
    """
    Get data extraction service instance.

    Args:
        db: Database session

    Returns:
        DataExtractionService instance
    """
    return DataExtractionService(db)
