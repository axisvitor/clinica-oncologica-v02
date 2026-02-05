"""
Data models and enums for response processing.
"""

from typing import List, Optional, Any
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID
from dataclasses import dataclass, field

from app.services.ai import ConcernLevel


class ResponseType(str, Enum):
    """Types of patient responses."""

    TEXT = "text"
    BUTTON = "button"
    QUICK_REPLY = "quick_reply"
    LIST_SELECTION = "list_selection"
    MEDIA = "media"
    LOCATION = "location"
    CONTACT = "contact"
    UNKNOWN = "unknown"


@dataclass
class ResponseProcessorConfig:
    """Configuration for ResponseProcessor."""

    max_conversation_history: int = 50
    message_limit: int = 4096
    default_confidence_score: float = 0.5
    escalation_delay_seconds: int = 300
    enable_ai_processing: bool = True
    enable_pattern_extraction: bool = True
    enable_sentiment_analysis: bool = True


@dataclass
class ResponseValidationResult:
    """Result of response validation."""

    is_valid: bool
    response_type: ResponseType
    extracted_value: Any = None
    validation_errors: List[str] = field(default_factory=list)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class StructuredResponse:
    """Structured data extracted from patient response."""

    patient_id: UUID
    original_message: str
    response_type: ResponseType
    extracted_data: dict[str, Any]
    sentiment_analysis: dict[str, Any]
    medical_concerns: List[str]
    concern_level: ConcernLevel
    requires_attention: bool
    response_category: Optional[Any] = None
    patient_preferences: List[Any] = field(default_factory=list)
    severity_score: int = 0
    confidence_score: float = 0.0
    timestamp: datetime = field(default_factory=_utc_now)


@dataclass
class FlowAction:
    """Action to be taken based on patient response."""

    action_type: str
    parameters: dict[str, Any]
    priority: str = "normal"
    delay_seconds: int = 0


@dataclass
class ResponseProcessingResult:
    """Result of response processing."""

    patient_id: UUID
    structured_response: StructuredResponse
    flow_actions: List[FlowAction]
    follow_up_message: Optional[str] = None
    state_updates: Optional[dict[str, Any]] = None
    escalation_required: bool = False
    processed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class InboundMessage:
    """Inbound message data structure."""

    patient_phone: str
    content: str
    whatsapp_id: str
    message_type: Any = None  # MessageType from models
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class InteractiveResponse:
    """Interactive response (buttons, quick replies, etc.)."""

    patient_id: UUID
    response_value: str
    response_type: ResponseType
    original_message_id: Optional[UUID] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ResponseFactory:
    """Factory for creating response objects."""

    @staticmethod
    def create_error_response(
        patient_id: UUID,
        original_message: str,
        response_type: ResponseType,
        validation_errors: List[str],
    ) -> StructuredResponse:
        """Create a structured response for validation errors."""
        return StructuredResponse(
            patient_id=patient_id,
            original_message=original_message,
            response_type=response_type,
            extracted_data={"validation_errors": validation_errors},
            sentiment_analysis={"sentiment": "neutral", "confidence": 0.0},
            medical_concerns=[],
            concern_level=ConcernLevel.LOW,
            requires_attention=False,
            confidence_score=0.5,
        )

    @staticmethod
    def create_fallback_response(
        patient_id: UUID, original_message: str, response_type: ResponseType
    ) -> StructuredResponse:
        """Create a fallback structured response when AI processing fails."""
        return StructuredResponse(
            patient_id=patient_id,
            original_message=original_message,
            response_type=response_type,
            extracted_data={"raw_text": original_message},
            sentiment_analysis={"sentiment": "neutral", "confidence": 0.0},
            medical_concerns=[],
            concern_level=ConcernLevel.LOW,
            requires_attention=False,
            confidence_score=0.5,
        )
