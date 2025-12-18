"""
Response processing schemas for patient message handling.
"""

from typing import List, Optional, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.models.message import MessageType


class ResponseTypeEnum(str, Enum):
    """Types of patient responses."""

    TEXT = "text"
    BUTTON = "button"
    QUICK_REPLY = "quick_reply"
    LIST_SELECTION = "list_selection"
    MEDIA = "media"
    LOCATION = "location"


class ConcernLevelEnum(str, Enum):
    """Medical concern severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class InboundMessageRequest(BaseModel):
    """Schema for processing inbound messages."""

    patient_phone: str = Field(..., description="Patient phone number")
    content: str = Field(..., description="Message content")
    whatsapp_id: str = Field(..., description="WhatsApp message ID")
    message_type: MessageType = Field(
        default=MessageType.TEXT, description="Message type"
    )
    metadata: Optional[dict[str, Any]] = Field(
        default_factory=dict, description="Message metadata"
    )
    timestamp: Optional[datetime] = Field(None, description="Message timestamp")

    @field_validator("patient_phone")
    @classmethod
    def validate_phone(cls, v):
        if not v or not v.strip():
            raise ValueError("Patient phone cannot be empty")
        return v.strip()

    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        if not v or not v.strip():
            raise ValueError("Message content cannot be empty")
        if len(v) > 4000:
            raise ValueError("Message content too long (max 4000 characters)")
        return v.strip()


class InteractiveResponseRequest(BaseModel):
    """Schema for processing interactive responses."""

    patient_id: UUID = Field(..., description="Patient ID")
    response_value: str = Field(..., description="Response value")
    response_type: ResponseTypeEnum = Field(..., description="Response type")
    original_message_id: Optional[UUID] = Field(None, description="Original message ID")
    metadata: Optional[dict[str, Any]] = Field(
        default_factory=dict, description="Response metadata"
    )

    @field_validator("response_value")
    @classmethod
    def validate_response_value(cls, v):
        if not v or not v.strip():
            raise ValueError("Response value cannot be empty")
        return v.strip()


class SentimentAnalysisResult(BaseModel):
    """Sentiment analysis result."""

    sentiment: str = Field(..., description="Detected sentiment")
    confidence: float = Field(..., description="Confidence score")
    key_phrases: List[str] = Field(default_factory=list, description="Key phrases")
    emotional_indicators: List[str] = Field(
        default_factory=list, description="Emotional indicators"
    )


class StructuredResponseData(BaseModel):
    """Structured data extracted from patient response."""

    patient_id: UUID = Field(..., description="Patient ID")
    original_message: str = Field(..., description="Original message")
    response_type: ResponseTypeEnum = Field(..., description="Response type")
    extracted_data: dict[str, Any] = Field(..., description="Extracted data")
    sentiment_analysis: SentimentAnalysisResult = Field(
        ..., description="Sentiment analysis"
    )
    medical_concerns: List[str] = Field(
        default_factory=list, description="Medical concerns"
    )
    concern_level: ConcernLevelEnum = Field(..., description="Concern level")
    requires_attention: bool = Field(..., description="Requires attention flag")
    confidence_score: float = Field(..., description="Overall confidence score")
    timestamp: datetime = Field(..., description="Processing timestamp")


class FlowActionData(BaseModel):
    """Flow action data."""

    action_type: str = Field(..., description="Action type")
    parameters: dict[str, Any] = Field(..., description="Action parameters")
    priority: str = Field(default="normal", description="Action priority")
    delay_seconds: int = Field(default=0, description="Delay before execution")


class ResponseProcessingResult(BaseModel):
    """Result of response processing."""

    patient_id: UUID = Field(..., description="Patient ID")
    structured_response: StructuredResponseData = Field(
        ..., description="Structured response data"
    )
    flow_actions: List[FlowActionData] = Field(
        ..., description="Flow actions to execute"
    )
    follow_up_message: Optional[str] = Field(None, description="Follow-up message")
    state_updates: Optional[dict[str, Any]] = Field(None, description="State updates")
    escalation_required: bool = Field(..., description="Escalation required flag")
    processed_at: datetime = Field(..., description="Processing timestamp")


class ResponseValidationResult(BaseModel):
    """Response validation result."""

    is_valid: bool = Field(..., description="Validation result")
    response_type: ResponseTypeEnum = Field(..., description="Response type")
    extracted_value: Optional[Any] = Field(None, description="Extracted value")
    validation_errors: List[str] = Field(
        default_factory=list, description="Validation errors"
    )


class PatientResponseSummary(BaseModel):
    """Summary of patient responses."""

    patient_id: UUID = Field(..., description="Patient ID")
    total_responses: int = Field(..., description="Total responses")
    last_response_time: Optional[datetime] = Field(
        None, description="Last response time"
    )
    avg_response_time_minutes: Optional[float] = Field(
        None, description="Average response time"
    )
    sentiment_distribution: dict[str, int] = Field(
        ..., description="Sentiment distribution"
    )
    concern_levels: dict[str, int] = Field(
        ..., description="Concern level distribution"
    )
    medical_concerns_count: int = Field(..., description="Total medical concerns")
    escalations_count: int = Field(..., description="Total escalations")


class ResponseAnalyticsRequest(BaseModel):
    """Request for response analytics."""

    patient_id: Optional[UUID] = Field(None, description="Patient ID filter")
    start_date: Optional[datetime] = Field(None, description="Start date filter")
    end_date: Optional[datetime] = Field(None, description="End date filter")
    concern_level: Optional[ConcernLevelEnum] = Field(
        None, description="Concern level filter"
    )
    response_type: Optional[ResponseTypeEnum] = Field(
        None, description="Response type filter"
    )
    limit: int = Field(default=100, description="Result limit")
    skip: int = Field(default=0, description="Result offset")


class ResponseAnalyticsResult(BaseModel):
    """Response analytics result."""

    total_responses: int = Field(..., description="Total responses")
    response_summaries: List[PatientResponseSummary] = Field(
        ..., description="Patient summaries"
    )
    sentiment_trends: dict[str, List[dict[str, Any]]] = Field(
        ..., description="Sentiment trends"
    )
    concern_trends: dict[str, List[dict[str, Any]]] = Field(
        ..., description="Concern trends"
    )
    escalation_summary: dict[str, Any] = Field(..., description="Escalation summary")
    processing_metrics: dict[str, Any] = Field(..., description="Processing metrics")


class TextPatternExtractionResult(BaseModel):
    """Result of text pattern extraction."""

    boolean_response: Optional[bool] = Field(None, description="Boolean response")
    numbers: Optional[List[float]] = Field(None, description="Extracted numbers")
    time_references: Optional[List[str]] = Field(None, description="Time references")
    medication_mentioned: Optional[bool] = Field(
        None, description="Medication mentioned"
    )
    pain_scale: Optional[int] = Field(None, description="Pain scale (1-10)")
    mood_indicator: Optional[str] = Field(None, description="Mood indicator")


class MedicalConcernAlert(BaseModel):
    """Medical concern alert."""

    patient_id: UUID = Field(..., description="Patient ID")
    concern_level: ConcernLevelEnum = Field(..., description="Concern level")
    medical_concerns: List[str] = Field(..., description="Medical concerns")
    original_message: str = Field(..., description="Original message")
    sentiment_analysis: SentimentAnalysisResult = Field(
        ..., description="Sentiment analysis"
    )
    recommended_actions: List[str] = Field(..., description="Recommended actions")
    created_at: datetime = Field(..., description="Alert creation time")
    requires_immediate_attention: bool = Field(
        ..., description="Immediate attention flag"
    )


class ResponseProcessingStats(BaseModel):
    """Response processing statistics."""

    total_processed: int = Field(..., description="Total responses processed")
    processing_success_rate: float = Field(..., description="Processing success rate")
    avg_processing_time_ms: float = Field(..., description="Average processing time")
    sentiment_accuracy: float = Field(..., description="Sentiment analysis accuracy")
    concern_detection_rate: float = Field(..., description="Concern detection rate")
    escalation_rate: float = Field(..., description="Escalation rate")
    ai_confidence_avg: float = Field(..., description="Average AI confidence")


class ResponseProcessingHealthCheck(BaseModel):
    """Response processing health check."""

    service_name: str = Field(..., description="Service name")
    healthy: bool = Field(..., description="Health status")
    timestamp: datetime = Field(..., description="Check timestamp")
    components: dict[str, dict[str, Any]] = Field(..., description="Component health")
    processing_stats: ResponseProcessingStats = Field(
        ..., description="Processing statistics"
    )
    error_details: Optional[List[str]] = Field(None, description="Error details")


class BulkResponseProcessingRequest(BaseModel):
    """Request for bulk response processing."""

    responses: List[InboundMessageRequest] = Field(
        ..., description="Responses to process"
    )
    batch_id: Optional[str] = Field(None, description="Batch identifier")
    priority: str = Field(default="normal", description="Processing priority")

    @field_validator("responses")
    @classmethod
    def validate_responses(cls, v):
        if not v:
            raise ValueError("At least one response required")
        if len(v) > 100:
            raise ValueError("Maximum 100 responses per batch")
        return v


class BulkResponseProcessingResult(BaseModel):
    """Result of bulk response processing."""

    batch_id: Optional[str] = Field(None, description="Batch identifier")
    total_responses: int = Field(..., description="Total responses")
    successful_processing: int = Field(..., description="Successfully processed")
    failed_processing: int = Field(..., description="Failed processing")
    processing_time_seconds: float = Field(..., description="Total processing time")
    results: List[ResponseProcessingResult] = Field(
        ..., description="Individual results"
    )
    errors: List[dict[str, Any]] = Field(
        default_factory=list, description="Processing errors"
    )
