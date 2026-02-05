"""
Data models for data extraction service.
Contains enums and data classes for structured extraction.
"""

from typing import Any, List, Dict, Optional
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from app.services.ai import ConcernLevel


class ResponseCategory(str, Enum):
    """Categories of patient responses."""

    SYMPTOM_REPORT = "symptom_report"
    MEDICATION_INQUIRY = "medication_inquiry"
    SIDE_EFFECT_REPORT = "side_effect_report"
    EMOTIONAL_EXPRESSION = "emotional_expression"
    QUESTION_ANSWER = "question_answer"
    APPOINTMENT_REQUEST = "appointment_request"
    GENERAL_CONVERSATION = "general_conversation"
    EMERGENCY_CONCERN = "emergency_concern"
    TREATMENT_FEEDBACK = "treatment_feedback"
    LIFESTYLE_UPDATE = "lifestyle_update"


class ExtractionConfidence(str, Enum):
    """Confidence levels for data extraction."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


class MedicalConcernType(str, Enum):
    """Types of medical concerns."""

    PAIN = "pain"
    SIDE_EFFECT = "side_effect"
    SYMPTOM_WORSENING = "symptom_worsening"
    MEDICATION_ISSUE = "medication_issue"
    EMOTIONAL_DISTRESS = "emotional_distress"
    TREATMENT_ADHERENCE = "treatment_adherence"
    EMERGENCY = "emergency"
    GENERAL_HEALTH = "general_health"


class ExtractedEntity:
    """Extracted entity from patient response."""

    def __init__(
        self,
        entity_type: str,
        value: Any,
        confidence: float,
        context: str,
        source_text: str,
    ):
        self.entity_type = entity_type
        self.value = value
        self.confidence = confidence
        self.context = context
        self.source_text = source_text
        self.extracted_at = datetime.now(timezone.utc)


class MedicalConcern:
    """Medical concern extracted from patient response."""

    def __init__(
        self,
        concern_type: MedicalConcernType,
        description: str,
        severity: ConcernLevel,
        keywords: List[str],
        confidence: float,
        requires_immediate_attention: bool = False,
        severity_score: Optional[int] = None,
    ):
        self.concern_type = concern_type
        self.description = description
        self.severity = severity
        self.keywords = keywords
        self.confidence = confidence
        self.requires_immediate_attention = requires_immediate_attention
        self.severity_score = severity_score
        self.detected_at = datetime.now(timezone.utc)


class PatientPreference:
    """Patient preference extracted from response."""

    def __init__(
        self, preference_type: str, value: Any, confidence: float, context: str
    ):
        self.preference_type = preference_type
        self.value = value
        self.confidence = confidence
        self.context = context
        self.extracted_at = datetime.now(timezone.utc)


class StructuredExtractionResult:
    """Complete structured extraction result."""

    def __init__(
        self,
        patient_id: UUID,
        original_message: str,
        response_category: ResponseCategory,
        extracted_entities: List[ExtractedEntity],
        medical_concerns: List[MedicalConcern],
        patient_preferences: List[PatientPreference],
        sentiment_analysis: Dict[str, Any],
        confidence_score: float,
        processing_notes: List[str],
    ):
        self.patient_id = patient_id
        self.original_message = original_message
        self.response_category = response_category
        self.extracted_entities = extracted_entities
        self.medical_concerns = medical_concerns
        self.patient_preferences = patient_preferences
        self.sentiment_analysis = sentiment_analysis
        self.confidence_score = confidence_score
        self.processing_notes = processing_notes
        self.extracted_at = datetime.now(timezone.utc)
