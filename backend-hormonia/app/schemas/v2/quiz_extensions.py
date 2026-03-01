"""
Quiz Extensions schemas for API v2

Enhanced quiz extension models with:
- Pydantic V2 validation and field constraints
- Comprehensive type hints and documentation
- Quiz response tracking and analytics
- Alert rule engine schemas
- Monthly quiz management
- Public quiz access with token validation
- Risk scoring and trend detection
- Template management

CRITICAL: These schemas handle quiz data used for patient monitoring and alerts.
All validation rules must be thorough to prevent data integrity issues.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, field_validator, ConfigDict, constr, confloat

from app.models.alert import AlertSeverity as ModelAlertSeverity, AlertStatus as ModelAlertStatus
from .common import CursorPaginatedResponse
from app.utils.timezone import now_sao_paulo_naive


# ============================================================================
# Enums and Constants
# ============================================================================


class QuizResponseTypeEnum(str, Enum):
    """Quiz response types."""

    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TEXT = "text"
    SCALE = "scale"
    DATE = "date"
    BOOLEAN = "boolean"


class QuizSessionStatusEnum(str, Enum):
    """Quiz session status types."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    EXPIRED = "expired"


class AlertRuleTriggerEnum(str, Enum):
    """Alert rule trigger types."""

    SCORE_THRESHOLD = "score_threshold"
    ANSWER_PATTERN = "answer_pattern"
    MISSING_RESPONSE = "missing_response"
    TREND_DECLINING = "trend_declining"


class AlertSeverityEnum(str, Enum):
    """API alert severity representation (uppercase)."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatusEnum(str, Enum):
    """API alert status representation (uppercase)."""

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class MonthlyQuizStatusEnum(str, Enum):
    """Monthly quiz status."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class DeliveryMethodEnum(str, Enum):
    """Quiz delivery methods."""

    WHATSAPP = "whatsapp"
    EMAIL = "email"
    SMS = "sms"


# ============================================================================
# Quiz Response Schemas
# ============================================================================


class QuizResponseV2Base(BaseModel):
    """Base quiz response schema."""

    question_id: constr(min_length=1, max_length=255) = Field(
        ..., description="Unique identifier for the question"
    )
    question_text: constr(min_length=1, max_length=2000) = Field(
        ..., description="Text of the question"
    )
    response_type: QuizResponseTypeEnum = Field(
        ..., description="Type of response (single_choice, multiple_choice, text, etc.)"
    )
    response_value: Any = Field(..., description="Patient's response value")
    response_metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata (AI analysis, risk scores)"
    )
    other_text: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Additional text for 'other' responses",
    )


class QuizResponseV2Detail(QuizResponseV2Base):
    """Detailed quiz response with context."""

    id: UUID = Field(..., description="Response ID")
    patient_id: UUID = Field(..., description="Patient ID")
    quiz_template_id: UUID = Field(..., description="Quiz template ID")
    quiz_session_id: Optional[UUID] = Field(None, description="Quiz session ID")
    responded_at: datetime = Field(..., description="Response timestamp")
    created_at: datetime = Field(..., description="Record creation timestamp")

    # Additional context
    template_name: Optional[str] = Field(None, description="Template name")
    template_version: Optional[str] = Field(None, description="Template version")
    session_status: Optional[str] = Field(None, description="Session status")

    model_config = ConfigDict(from_attributes=True)


class QuizResponseV2List(CursorPaginatedResponse[QuizResponseV2Detail]):
    """Paginated quiz response list."""

    pass


class ResponseAnalyticsV2(BaseModel):
    """Quiz response analytics and aggregates."""

    total_responses: int = Field(..., description="Total number of responses")
    completion_rate: confloat(ge=0.0, le=100.0) = Field(
        ..., description="Completion rate percentage"
    )
    average_score: Optional[confloat(ge=0.0, le=100.0)] = Field(
        None, description="Average quiz score"
    )
    response_trends: List[Dict[str, Any]] = Field(
        default_factory=list, description="Response trends over time"
    )
    common_patterns: List[str] = Field(
        default_factory=list, description="Common response patterns identified"
    )
    flagged_count: int = Field(0, description="Number of responses flagged for review")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_responses": 150,
                "completion_rate": 87.5,
                "average_score": 75.2,
                "response_trends": [
                    {"date": "2025-01", "score": 78.0},
                    {"date": "2025-02", "score": 75.2},
                ],
                "common_patterns": ["improving", "consistent"],
                "flagged_count": 5,
            }
        }
    )


# ============================================================================
# Quiz Alert Schemas
# ============================================================================


class QuizAlertV2Base(BaseModel):
    """Base quiz alert schema."""

    alert_type: constr(min_length=1, max_length=100) = Field(
        ..., description="Type of alert (quiz_response, quiz_score, etc.)"
    )
    severity: AlertSeverityEnum = Field(
        ..., description="Alert severity (LOW, MEDIUM, HIGH, CRITICAL)"
    )
    description: constr(min_length=1, max_length=2000) = Field(
        ..., description="Alert description"
    )
    trigger_data: Optional[Dict[str, Any]] = Field(
        None, description="Data that triggered the alert"
    )

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, value):
        if isinstance(value, AlertSeverityEnum):
            return value
        if isinstance(value, ModelAlertSeverity):
            return AlertSeverityEnum[value.name]
        if isinstance(value, str):
            normalized = value.strip().upper()
            if normalized in AlertSeverityEnum.__members__:
                return AlertSeverityEnum[normalized]
        raise ValueError("severity must be one of LOW, MEDIUM, HIGH, CRITICAL")


class QuizAlertV2Detail(QuizAlertV2Base):
    """Detailed quiz alert with full context."""

    id: UUID = Field(..., description="Alert ID")
    patient_id: UUID = Field(..., description="Patient ID")
    quiz_session_id: Optional[UUID] = Field(None, description="Quiz session ID")
    response_id: Optional[UUID] = Field(
        None, description="Response ID that triggered alert"
    )
    status: AlertStatusEnum = Field(..., description="Alert status")
    created_at: datetime = Field(..., description="Alert creation time")
    acknowledged_at: Optional[datetime] = Field(
        None, description="Acknowledgement time"
    )
    acknowledged_by: Optional[UUID] = Field(None, description="User who acknowledged")
    resolved_at: Optional[datetime] = Field(None, description="Resolution time")

    # Patient context
    patient_name: Optional[str] = Field(None, description="Patient name")

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value):
        if isinstance(value, AlertStatusEnum):
            return value
        if isinstance(value, ModelAlertStatus):
            return AlertStatusEnum[value.name]
        if isinstance(value, str):
            normalized = value.strip().upper()
            if normalized in AlertStatusEnum.__members__:
                return AlertStatusEnum[normalized]
        raise ValueError(
            "status must be one of PENDING, ACTIVE, ACKNOWLEDGED, RESOLVED, DISMISSED"
        )

    model_config = ConfigDict(from_attributes=True)


class QuizAlertV2List(CursorPaginatedResponse[QuizAlertV2Detail]):
    """Paginated quiz alert list."""

    pass


class AlertAcknowledgementV2(BaseModel):
    """Alert acknowledgement request."""

    notes: Optional[str] = Field(
        None, max_length=2000, description="Optional acknowledgement notes"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"notes": "Reviewed patient responses, scheduling follow-up"}
        }
    )


class AlertStatisticsV2(BaseModel):
    """Quiz alert statistics."""

    total_alerts: int = Field(..., description="Total alerts generated")
    by_severity: Dict[str, int] = Field(..., description="Alert count by severity")
    by_status: Dict[str, int] = Field(..., description="Alert count by status")
    acknowledgement_rate: confloat(ge=0.0, le=100.0) = Field(
        ..., description="Percentage of acknowledged alerts"
    )
    avg_response_time_hours: Optional[float] = Field(
        None, description="Average time to acknowledge (hours)"
    )
    triggered_rules: List[Dict[str, Any]] = Field(
        default_factory=list, description="Most frequently triggered rules"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_alerts": 45,
                "by_severity": {"CRITICAL": 5, "HIGH": 15, "MEDIUM": 20, "LOW": 5},
                "by_status": {"PENDING": 10, "ACKNOWLEDGED": 25, "RESOLVED": 10},
                "acknowledgement_rate": 77.8,
                "avg_response_time_hours": 2.5,
                "triggered_rules": [{"rule_name": "low_score_threshold", "count": 12}],
            }
        }
    )


class AlertRuleV2Create(BaseModel):
    """Create alert rule request."""

    rule_name: constr(min_length=1, max_length=255) = Field(
        ..., description="Unique rule name"
    )
    trigger_type: AlertRuleTriggerEnum = Field(
        ..., description="Type of trigger (score_threshold, answer_pattern, etc.)"
    )
    trigger_condition: Dict[str, Any] = Field(
        ..., description="Trigger condition parameters"
    )
    severity: AlertSeverityEnum = Field(
        ..., description="Severity of alerts generated by this rule"
    )
    notification_type: List[str] = Field(
        ..., description="Notification methods (email, sms, in_app)"
    )
    enabled: bool = Field(True, description="Whether rule is active")

    @field_validator("trigger_condition")
    @classmethod
    def validate_trigger_condition(cls, v, info):
        """Validate trigger condition based on trigger type."""
        trigger_type = info.data.get("trigger_type")

        if trigger_type == AlertRuleTriggerEnum.SCORE_THRESHOLD:
            if "threshold" not in v or "operator" not in v:
                raise ValueError("score_threshold requires 'threshold' and 'operator'")
            if not isinstance(v["threshold"], (int, float)):
                raise ValueError("threshold must be a number")
            if v["operator"] not in ["<", "<=", ">", ">=", "=="]:
                raise ValueError("operator must be <, <=, >, >=, or ==")

        elif trigger_type == AlertRuleTriggerEnum.ANSWER_PATTERN:
            if "pattern" not in v:
                raise ValueError("answer_pattern requires 'pattern'")

        return v

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_rule_severity(cls, value):
        if isinstance(value, AlertSeverityEnum):
            return value
        if isinstance(value, ModelAlertSeverity):
            return AlertSeverityEnum[value.name]
        if isinstance(value, str):
            normalized = value.strip().upper()
            if normalized in AlertSeverityEnum.__members__:
                return AlertSeverityEnum[normalized]
        raise ValueError("severity must be one of LOW, MEDIUM, HIGH, CRITICAL")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "rule_name": "critical_score_alert",
                "trigger_type": "score_threshold",
                "trigger_condition": {"threshold": 30, "operator": "<"},
                "severity": "CRITICAL",
                "notification_type": ["email", "sms"],
                "enabled": True,
            }
        }
    )


class AlertRuleV2Detail(AlertRuleV2Create):
    """Detailed alert rule with metadata."""

    id: UUID = Field(..., description="Rule ID")
    created_by: UUID = Field(..., description="User who created the rule")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    triggered_count: int = Field(0, description="Number of times triggered")
    last_triggered_at: Optional[datetime] = Field(None, description="Last trigger time")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Monthly Quiz Schemas
# ============================================================================


class MonthlyQuizV2Base(BaseModel):
    """Base monthly quiz schema."""

    name: constr(min_length=1, max_length=255) = Field(..., description="Quiz name")
    description: Optional[str] = Field(
        None, max_length=2000, description="Quiz description"
    )
    quiz_template_id: UUID = Field(..., description="Template to use for this quiz")
    scheduled_for: Optional[datetime] = Field(
        None, description="Scheduled publication date"
    )
    expires_at: Optional[datetime] = Field(None, description="Expiration date")


class MonthlyQuizV2Create(MonthlyQuizV2Base):
    """Create monthly quiz request."""

    target_patient_ids: Optional[List[UUID]] = Field(
        None, description="Specific patients to target (None = all active patients)"
    )
    auto_send: bool = Field(False, description="Automatically send when published")
    delivery_method: DeliveryMethodEnum = Field(
        default=DeliveryMethodEnum.WHATSAPP, description="Default delivery method"
    )


class MonthlyQuizV2Update(BaseModel):
    """Update monthly quiz request."""

    name: Optional[constr(min_length=1, max_length=255)] = Field(
        None, description="Quiz name"
    )
    description: Optional[str] = Field(
        None, max_length=2000, description="Quiz description"
    )
    scheduled_for: Optional[datetime] = Field(
        None, description="Scheduled publication date"
    )
    expires_at: Optional[datetime] = Field(None, description="Expiration date")


class MonthlyQuizV2Detail(MonthlyQuizV2Base):
    """Detailed monthly quiz."""

    id: UUID = Field(..., description="Quiz ID")
    status: MonthlyQuizStatusEnum = Field(..., description="Quiz status")
    created_by: UUID = Field(..., description="Creator user ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    published_at: Optional[datetime] = Field(None, description="Publication timestamp")

    # Statistics
    total_sent: int = Field(0, description="Total quiz links sent")
    total_accessed: int = Field(0, description="Total times accessed")
    total_completed: int = Field(0, description="Total completions")
    completion_rate: confloat(ge=0.0, le=100.0) = Field(
        0.0, description="Completion rate percentage"
    )

    model_config = ConfigDict(from_attributes=True)


class MonthlyQuizV2List(CursorPaginatedResponse[MonthlyQuizV2Detail]):
    """Paginated monthly quiz list."""

    pass


class QuizPublishRequestV2(BaseModel):
    """Publish quiz request."""

    send_immediately: bool = Field(
        True, description="Send links immediately after publishing"
    )
    target_patient_ids: Optional[List[UUID]] = Field(
        None, description="Specific patients (None = all active patients)"
    )


class MonthlyQuizStatisticsV2(BaseModel):
    """Monthly quiz statistics."""

    quiz_id: UUID = Field(..., description="Quiz ID")
    total_sent: int = Field(..., description="Total links sent")
    total_accessed: int = Field(..., description="Total accesses")
    total_completed: int = Field(..., description="Total completions")
    completion_rate: confloat(ge=0.0, le=100.0) = Field(
        ..., description="Completion rate percentage"
    )
    average_score: Optional[confloat(ge=0.0, le=100.0)] = Field(
        None, description="Average quiz score"
    )
    average_completion_time_minutes: Optional[float] = Field(
        None, description="Average time to complete (minutes)"
    )
    responses_by_day: List[Dict[str, Any]] = Field(
        default_factory=list, description="Response counts by day"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "quiz_id": "123e4567-e89b-12d3-a456-426614174000",
                "total_sent": 100,
                "total_accessed": 85,
                "total_completed": 75,
                "completion_rate": 75.0,
                "average_score": 82.5,
                "average_completion_time_minutes": 12.5,
                "responses_by_day": [
                    {"date": "2025-11-01", "count": 25},
                    {"date": "2025-11-02", "count": 30},
                ],
            }
        }
    )


class QuizReminderRequestV2(BaseModel):
    """Send quiz reminder request."""

    custom_message: Optional[str] = Field(
        None, max_length=500, description="Custom reminder message"
    )
    delivery_method: DeliveryMethodEnum = Field(
        default=DeliveryMethodEnum.WHATSAPP, description="Delivery method for reminder"
    )


class QuizScheduleV2(BaseModel):
    """Quiz schedule entry."""

    quiz_id: UUID = Field(..., description="Quiz ID")
    quiz_name: str = Field(..., description="Quiz name")
    scheduled_for: datetime = Field(..., description="Scheduled date")
    status: MonthlyQuizStatusEnum = Field(..., description="Quiz status")
    auto_send: bool = Field(..., description="Will auto-send when published")

    model_config = ConfigDict(from_attributes=True)


class QuizGenerateRequestV2(BaseModel):
    """Auto-generate quiz request."""

    template_id: UUID = Field(..., description="Template to use for generation")
    target_month: constr(pattern=r"^\d{4}-\d{2}$") = Field(
        ..., description="Target month (YYYY-MM format)"
    )
    auto_publish: bool = Field(
        default=False, description="Automatically publish after generation"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "template_id": "123e4567-e89b-12d3-a456-426614174000",
                "target_month": "2025-12",
                "auto_publish": False,
            }
        }
    )


class QuizTemplateV2(BaseModel):
    """Quiz template for monthly quizzes."""

    id: UUID = Field(..., description="Template ID")
    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    version: str = Field(..., description="Template version")
    question_count: int = Field(..., description="Number of questions")
    estimated_duration_minutes: Optional[int] = Field(
        None, description="Estimated completion time"
    )
    is_active: bool = Field(..., description="Whether template is active")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Public Quiz Schemas
# ============================================================================


class PublicQuizResponseV2(BaseModel):
    """Public quiz response (sanitized)."""

    quiz_id: UUID = Field(..., description="Quiz ID")
    quiz_name: str = Field(..., description="Quiz name")
    description: Optional[str] = Field(None, description="Quiz description")
    questions: List[Dict[str, Any]] = Field(
        ..., description="Quiz questions (without sensitive data)"
    )
    expires_at: Optional[datetime] = Field(None, description="Quiz expiration time")
    session_id: UUID = Field(..., description="Session ID for submission")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "quiz_id": "123e4567-e89b-12d3-a456-426614174000",
                "quiz_name": "Monthly Health Check - November 2025",
                "description": "Monthly wellness questionnaire",
                "questions": [
                    {
                        "id": "q1",
                        "text": "How are you feeling today?",
                        "type": "scale",
                        "options": {"min": 1, "max": 10},
                    }
                ],
                "expires_at": "2025-11-30T23:59:59-03:00",
                "session_id": "456e7890-e89b-12d3-a456-426614174001",
            }
        }
    )


class PublicSubmissionRequestV2(BaseModel):
    """Public quiz submission request."""

    token: constr(min_length=1) = Field(..., description="Access token from quiz link")
    question_id: constr(min_length=1) = Field(
        ..., description="Question ID being answered"
    )
    response_value: Any = Field(
        ..., description="Response value (string, number, list, etc.)"
    )
    response_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Optional response metadata"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "question_id": "q1",
                "response_value": "8",
                "response_metadata": {"time_taken_seconds": 15},
            }
        }
    )


class PublicQuizResultsV2(BaseModel):
    """Public quiz results (aggregate only)."""

    quiz_id: UUID = Field(..., description="Quiz ID")
    quiz_name: str = Field(..., description="Quiz name")
    total_completions: int = Field(..., description="Total completions")
    average_score: Optional[float] = Field(
        None, description="Average score (if applicable)"
    )
    completion_rate: confloat(ge=0.0, le=100.0) = Field(
        ..., description="Completion rate percentage"
    )
    response_distribution: Optional[Dict[str, Any]] = Field(
        None, description="Aggregate response distribution (no personal data)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "quiz_id": "123e4567-e89b-12d3-a456-426614174000",
                "quiz_name": "Monthly Health Check - November 2025",
                "total_completions": 85,
                "average_score": 82.5,
                "completion_rate": 85.0,
                "response_distribution": {"q1": {"1-3": 5, "4-7": 30, "8-10": 50}},
            }
        }
    )


class SubmissionTokenV2(BaseModel):
    """Time-limited submission token."""

    token: str = Field(..., description="JWT access token")
    expires_at: datetime = Field(..., description="Token expiration time")
    quiz_session_id: UUID = Field(..., description="Associated quiz session")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "expires_at": "2025-11-08T23:59:59-03:00",
                "quiz_session_id": "456e7890-e89b-12d3-a456-426614174001",
            }
        }
    )


# ============================================================================
# Error Response Schemas
# ============================================================================


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error type")
    detail: str = Field(..., description="Error details")
    timestamp: datetime = Field(default_factory=now_sao_paulo_naive)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "VALIDATION_ERROR",
                "detail": "Invalid quiz response format",
                "timestamp": "2025-11-07T12:00:00-03:00",
            }
        }
    )
