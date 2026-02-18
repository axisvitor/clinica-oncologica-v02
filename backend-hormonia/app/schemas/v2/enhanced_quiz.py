"""
Enhanced Quiz schemas for API v2
Advanced quiz models with branching logic, risk scoring, and adaptive flows.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, model_validator, field_validator, ConfigDict

from .common import CursorPaginatedResponse


class QuizCategory(str, Enum):
    """Quiz category types."""

    SYMPTOMS = "symptoms"
    SIDE_EFFECTS = "side_effects"
    QUALITY_OF_LIFE = "quality_of_life"
    MEDICATION_ADHERENCE = "medication_adherence"
    PSYCHOLOGICAL = "psychological"
    NUTRITION = "nutrition"
    EXERCISE = "exercise"
    PAIN_ASSESSMENT = "pain_assessment"
    GENERAL_HEALTH = "general_health"


class QuizDifficulty(str, Enum):
    """Quiz difficulty levels."""

    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    COMPREHENSIVE = "comprehensive"


class RiskLevel(str, Enum):
    """Patient risk levels based on quiz responses."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class QuestionType(str, Enum):
    """Question types for quiz questions."""

    TEXT = "text"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    SCALE = "scale"
    DATE = "date"
    TIME = "time"
    BOOLEAN = "boolean"
    NUMBER = "number"


class BranchingCondition(BaseModel):
    """Branching logic condition for adaptive quiz flow."""

    field: str = Field(..., description="Field name to evaluate")
    operator: str = Field(
        ..., description="Comparison operator (eq, neq, gt, lt, gte, lte, in, contains)"
    )
    value: Union[str, int, float, bool, List[Any]] = Field(
        ..., description="Value to compare against"
    )

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v):
        allowed = ["eq", "neq", "gt", "lt", "gte", "lte", "in", "contains"]
        if v not in allowed:
            raise ValueError(f"Operator must be one of: {allowed}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"field": "pain_level", "operator": "gte", "value": 7}
        }
    )


class BranchingRule(BaseModel):
    """Branching rule for conditional quiz flow."""

    conditions: List[BranchingCondition] = Field(
        ..., description="List of conditions (AND logic)"
    )
    logic: str = Field(default="AND", description="Logic operator for conditions")
    next_question_id: Optional[str] = Field(
        None, description="Next question if condition matches"
    )
    skip_to_section: Optional[str] = Field(
        None, description="Skip to section if condition matches"
    )
    show_alert: Optional[str] = Field(None, description="Alert message to display")

    @field_validator("logic")
    @classmethod
    def validate_logic(cls, v):
        if v not in ["AND", "OR"]:
            raise ValueError("Logic must be AND or OR")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "conditions": [{"field": "pain_level", "operator": "gte", "value": 7}],
                "logic": "AND",
                "next_question_id": "q_pain_followup",
                "show_alert": "High pain level detected - immediate follow-up recommended",
            }
        }
    )


class QuizQuestion(BaseModel):
    """Enhanced quiz question with branching logic."""

    id: str = Field(..., description="Unique question identifier")
    question_text: str = Field(..., min_length=1, description="Question text")
    question_type: QuestionType = Field(..., description="Type of question")
    options: Optional[List[str]] = Field(
        None, description="Answer options for choice questions"
    )
    required: bool = Field(default=True, description="Whether question is required")
    validation_rules: Optional[Dict[str, Any]] = Field(
        None, description="Validation rules"
    )
    scoring_weight: float = Field(default=1.0, ge=0, description="Weight for scoring")
    category: Optional[str] = Field(None, description="Question category")
    help_text: Optional[str] = Field(None, description="Help text for question")
    branching_rules: Optional[List[BranchingRule]] = Field(
        None, description="Branching logic rules"
    )
    risk_factors: Optional[Dict[str, float]] = Field(
        None, description="Risk factor mappings"
    )

    @field_validator("options")
    @classmethod
    def validate_options(cls, v, values):
        question_type = values.get("question_type")
        if question_type in [QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE]:
            if not v or len(v) < 2:
                raise ValueError("Choice questions require at least 2 options")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "q1_pain_assessment",
                "question_text": "How would you rate your pain level today?",
                "question_type": "scale",
                "required": True,
                "scoring_weight": 2.0,
                "category": "pain",
                "help_text": "Rate from 0 (no pain) to 10 (worst pain)",
                "branching_rules": [
                    {
                        "conditions": [
                            {"field": "pain_level", "operator": "gte", "value": 7}
                        ],
                        "next_question_id": "q_pain_location",
                    }
                ],
                "risk_factors": {"high_pain": 0.8},
            }
        }
    )


class AdvancedQuizTemplate(BaseModel):
    """Advanced quiz template with branching logic and risk scoring."""

    title: str = Field(..., min_length=1, description="Template title")
    description: Optional[str] = Field(None, description="Template description")
    category: QuizCategory = Field(..., description="Quiz category")
    difficulty: QuizDifficulty = Field(
        default=QuizDifficulty.BASIC, description="Difficulty level"
    )
    questions: List[QuizQuestion] = Field(
        ..., min_items=1, description="List of questions"
    )
    time_limit_minutes: Optional[int] = Field(
        None, ge=1, description="Time limit in minutes"
    )
    max_attempts: int = Field(default=1, ge=1, description="Maximum attempts allowed")
    randomize_questions: bool = Field(
        default=False, description="Randomize question order"
    )
    show_results_immediately: bool = Field(
        default=True, description="Show results after completion"
    )
    passing_score: Optional[float] = Field(
        None, ge=0, le=100, description="Passing score percentage"
    )
    tags: List[str] = Field(default_factory=list, description="Template tags")
    is_active: bool = Field(default=True, description="Whether template is active")
    risk_scoring_enabled: bool = Field(default=False, description="Enable risk scoring")
    risk_thresholds: Optional[Dict[str, float]] = Field(
        None, description="Risk level thresholds"
    )
    adaptive_flow_enabled: bool = Field(
        default=False, description="Enable adaptive question flow"
    )

    @field_validator("questions")
    @classmethod
    def validate_questions(cls, v):
        if not v:
            raise ValueError("Template must have at least one question")
        # Validate unique question IDs
        question_ids = [q.id for q in v]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Question IDs must be unique")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Comprehensive Pain Assessment",
                "description": "Advanced pain assessment with adaptive flow",
                "category": "pain_assessment",
                "difficulty": "advanced",
                "questions": [
                    {
                        "id": "q1",
                        "question_text": "Rate your pain level",
                        "question_type": "scale",
                        "required": True,
                        "scoring_weight": 2.0,
                    }
                ],
                "time_limit_minutes": 30,
                "risk_scoring_enabled": True,
                "adaptive_flow_enabled": True,
            }
        }
    )


class QuizAnalyticsTrend(BaseModel):
    """Quiz analytics trend data point."""

    date: str = Field(..., description="Date in ISO format")
    total_sessions: int = Field(ge=0, description="Total quiz sessions")
    completed_sessions: int = Field(ge=0, description="Completed sessions")
    completion_rate: float = Field(
        ge=0, le=100, description="Completion rate percentage"
    )
    average_score: Optional[float] = Field(None, ge=0, description="Average score")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2025-01-01",
                "total_sessions": 150,
                "completed_sessions": 135,
                "completion_rate": 90.0,
                "average_score": 78.5,
            }
        }
    )


class QuizAnalyticsResponse(BaseModel):
    """Advanced quiz analytics response."""

    total_sessions: int = Field(ge=0, description="Total quiz sessions")
    completed_sessions: int = Field(ge=0, description="Completed sessions")
    completion_rate: float = Field(ge=0, le=100, description="Completion rate")
    average_score: Optional[float] = Field(None, ge=0, description="Average score")
    average_time_minutes: Optional[float] = Field(
        None, ge=0, description="Average completion time"
    )
    trends: List[QuizAnalyticsTrend] = Field(
        default_factory=list, description="Trend data"
    )
    category_breakdown: Dict[str, int] = Field(
        default_factory=dict, description="Sessions by category"
    )
    risk_distribution: Dict[str, int] = Field(
        default_factory=dict, description="Risk level distribution"
    )
    top_templates: List[Dict[str, Any]] = Field(
        default_factory=list, description="Most used templates"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_sessions": 500,
                "completed_sessions": 450,
                "completion_rate": 90.0,
                "average_score": 82.3,
                "average_time_minutes": 12.5,
                "trends": [],
                "category_breakdown": {"symptoms": 200, "pain_assessment": 150},
                "risk_distribution": {"low": 300, "medium": 150, "high": 50},
            }
        }
    )


class AdaptiveQuizFlowRequest(BaseModel):
    """Request for adaptive quiz flow."""

    session_id: str = Field(..., description="Quiz session UUID")
    current_question_id: str = Field(..., description="Current question ID")
    response_value: Union[str, int, float, bool, List[Any]] = Field(
        ..., description="Response value"
    )
    response_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional response metadata"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
                "current_question_id": "q1_pain_level",
                "response_value": 8,
                "response_metadata": {"answered_at": "2025-01-17T15:00:00-03:00"},
            }
        }
    )


class AdaptiveQuizFlowResponse(BaseModel):
    """Response for adaptive quiz flow."""

    next_question: Optional[QuizQuestion] = Field(
        None, description="Next question to display"
    )
    is_completed: bool = Field(description="Whether quiz is completed")
    alerts: List[str] = Field(default_factory=list, description="Alert messages")
    progress_percentage: float = Field(ge=0, le=100, description="Completion progress")
    estimated_remaining_minutes: Optional[int] = Field(
        None, description="Estimated time remaining"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "next_question": {
                    "id": "q2_pain_location",
                    "question_text": "Where is your pain located?",
                    "question_type": "single_choice",
                    "options": ["Head", "Chest", "Abdomen", "Back", "Limbs"],
                },
                "is_completed": False,
                "alerts": ["High pain level detected"],
                "progress_percentage": 25.0,
                "estimated_remaining_minutes": 8,
            }
        }
    )


class RiskScore(BaseModel):
    """Risk score for a patient based on quiz responses."""

    overall_risk_level: RiskLevel = Field(..., description="Overall risk level")
    risk_score: float = Field(ge=0, le=100, description="Numerical risk score")
    risk_factors: List[str] = Field(
        default_factory=list, description="Identified risk factors"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations"
    )
    urgent_actions: List[str] = Field(
        default_factory=list, description="Urgent actions needed"
    )
    confidence_score: float = Field(
        ge=0, le=1, description="Confidence in risk assessment"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "overall_risk_level": "high",
                "risk_score": 78.5,
                "risk_factors": [
                    "High pain level",
                    "Poor medication adherence",
                    "Weight loss",
                ],
                "recommendations": [
                    "Schedule immediate consultation",
                    "Review pain management plan",
                    "Consider nutritional support",
                ],
                "urgent_actions": ["Contact physician within 24 hours"],
                "confidence_score": 0.85,
            }
        }
    )


class RiskScoringRequest(BaseModel):
    """Request for risk scoring."""

    patient_id: str = Field(..., description="Patient UUID")
    session_id: Optional[str] = Field(None, description="Specific session UUID")
    lookback_days: int = Field(
        default=30, ge=1, le=365, description="Days to look back for data"
    )
    include_historical: bool = Field(
        default=True, description="Include historical data"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "lookback_days": 30,
                "include_historical": True,
            }
        }
    )


class RiskScoringResponse(BaseModel):
    """Response for risk scoring."""

    patient_id: str = Field(..., description="Patient UUID")
    assessment_date: datetime = Field(..., description="Assessment timestamp")
    current_risk: RiskScore = Field(..., description="Current risk assessment")
    trend: str = Field(..., description="Risk trend (improving, stable, worsening)")
    historical_scores: List[Dict[str, Any]] = Field(
        default_factory=list, description="Historical risk scores"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "assessment_date": "2025-01-17T15:00:00-03:00",
                "current_risk": {
                    "overall_risk_level": "high",
                    "risk_score": 78.5,
                    "risk_factors": ["High pain level"],
                    "recommendations": ["Schedule consultation"],
                    "urgent_actions": [],
                    "confidence_score": 0.85,
                },
                "trend": "worsening",
                "historical_scores": [],
            }
        }
    )


class QuizRecommendation(BaseModel):
    """Quiz recommendation for a patient."""

    template_id: str = Field(..., description="Recommended template UUID")
    template_title: str = Field(..., description="Template title")
    category: QuizCategory = Field(..., description="Quiz category")
    priority: str = Field(
        ..., description="Recommendation priority (high, medium, low)"
    )
    reason: str = Field(..., description="Reason for recommendation")
    due_date: Optional[datetime] = Field(None, description="Recommended due date")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "template_id": "223e4567-e89b-12d3-a456-426614174001",
                "template_title": "Pain Management Follow-up",
                "category": "pain_assessment",
                "priority": "high",
                "reason": "Previous quiz indicated high pain levels",
                "due_date": "2025-01-24T15:00:00-03:00",
            }
        }
    )


class QuizRecommendationsResponse(BaseModel):
    """Response with quiz recommendations."""

    patient_id: str = Field(..., description="Patient UUID")
    recommendations: List[QuizRecommendation] = Field(
        ..., description="List of recommendations"
    )
    total_recommendations: int = Field(
        ge=0, description="Total number of recommendations"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "recommendations": [],
                "total_recommendations": 3,
            }
        }
    )


class PerformanceMetric(BaseModel):
    """Performance metric for quiz analysis."""

    metric_name: str = Field(..., description="Metric name")
    current_value: float = Field(..., description="Current metric value")
    previous_value: Optional[float] = Field(None, description="Previous period value")
    change_percentage: Optional[float] = Field(None, description="Percentage change")
    trend: str = Field(..., description="Trend direction (up, down, stable)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "metric_name": "completion_rate",
                "current_value": 92.5,
                "previous_value": 88.0,
                "change_percentage": 5.1,
                "trend": "up",
            }
        }
    )


class PerformanceMetricsResponse(BaseModel):
    """Performance metrics response."""

    period_start: datetime = Field(..., description="Period start date")
    period_end: datetime = Field(..., description="Period end date")
    metrics: List[PerformanceMetric] = Field(..., description="List of metrics")
    insights: List[str] = Field(default_factory=list, description="Key insights")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "period_start": "2025-01-01T00:00:00-03:00",
                "period_end": "2025-01-31T23:59:59-03:00",
                "metrics": [],
                "insights": [
                    "Completion rate improved by 5.1%",
                    "Average response time decreased",
                ],
            }
        }
    )


class BulkQuizOperation(BaseModel):
    """Bulk quiz operation request."""

    operation: str = Field(..., description="Operation type (assign, delete, update)")
    patient_ids: List[str] = Field(
        ..., min_items=1, description="List of patient UUIDs"
    )
    template_id: Optional[str] = Field(
        None, description="Template UUID for assign operation"
    )
    update_data: Optional[Dict[str, Any]] = Field(
        None, description="Update data for update operation"
    )
    scheduled_for: Optional[datetime] = Field(
        None, description="Schedule time for operations"
    )

    @field_validator("operation")
    @classmethod
    def validate_operation(cls, v):
        allowed = ["assign", "delete", "update"]
        if v not in allowed:
            raise ValueError(f"Operation must be one of: {allowed}")
        return v

    @model_validator(mode="after")
    def validate_operation_data(self):
        if self.operation == "assign" and not self.template_id:
            raise ValueError("template_id required for assign operation")
        if self.operation == "update" and not self.update_data:
            raise ValueError("update_data required for update operation")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "operation": "assign",
                "patient_ids": [
                    "123e4567-e89b-12d3-a456-426614174000",
                    "223e4567-e89b-12d3-a456-426614174001",
                ],
                "template_id": "323e4567-e89b-12d3-a456-426614174002",
                "scheduled_for": "2025-01-20T09:00:00-03:00",
            }
        }
    )


class BulkOperationResponse(BaseModel):
    """Bulk operation response."""

    job_id: str = Field(..., description="Bulk operation job ID")
    operation: str = Field(..., description="Operation type")
    total_patients: int = Field(ge=0, description="Total patients in operation")
    status: str = Field(
        ..., description="Job status (pending, processing, completed, failed)"
    )
    successful: int = Field(default=0, ge=0, description="Successful operations")
    failed: int = Field(default=0, ge=0, description="Failed operations")
    errors: List[str] = Field(default_factory=list, description="Error messages")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "bulk-quiz-123e4567",
                "operation": "assign",
                "total_patients": 50,
                "status": "completed",
                "successful": 48,
                "failed": 2,
                "errors": ["Patient not found: 123e4567-e89b-12d3-a456-426614174099"],
            }
        }
    )


class QuizExportRequest(BaseModel):
    """Quiz export request."""

    format: str = Field(..., description="Export format (pdf, csv, json, xlsx)")
    patient_ids: Optional[List[str]] = Field(
        None, description="Filter by patient UUIDs"
    )
    template_ids: Optional[List[str]] = Field(
        None, description="Filter by template UUIDs"
    )
    start_date: Optional[datetime] = Field(None, description="Start date filter")
    end_date: Optional[datetime] = Field(None, description="End date filter")
    include_responses: bool = Field(
        default=True, description="Include response details"
    )
    include_analytics: bool = Field(default=False, description="Include analytics")

    @field_validator("format")
    @classmethod
    def validate_format(cls, v):
        allowed = ["pdf", "csv", "json", "xlsx"]
        if v not in allowed:
            raise ValueError(f"Format must be one of: {allowed}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "format": "pdf",
                "start_date": "2025-01-01T00:00:00-03:00",
                "end_date": "2025-01-31T23:59:59-03:00",
                "include_responses": True,
                "include_analytics": True,
            }
        }
    )


class QuizExportResponse(BaseModel):
    """Quiz export response."""

    export_id: str = Field(..., description="Export job ID")
    format: str = Field(..., description="Export format")
    status: str = Field(
        ..., description="Export status (pending, processing, completed, failed)"
    )
    download_url: Optional[str] = Field(None, description="Download URL when completed")
    expires_at: Optional[datetime] = Field(None, description="URL expiration time")
    file_size_bytes: Optional[int] = Field(None, description="File size in bytes")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "export_id": "export-123e4567",
                "format": "pdf",
                "status": "completed",
                "download_url": "https://example.com/exports/export-123e4567.pdf",
                "expires_at": "2025-01-24T15:00:00-03:00",
                "file_size_bytes": 2048576,
            }
        }
    )


# Paginated responses


class QuizAnalyticsList(CursorPaginatedResponse[QuizAnalyticsTrend]):
    """Paginated quiz analytics list."""

    pass


class QuizRecommendationsList(CursorPaginatedResponse[QuizRecommendation]):
    """Paginated quiz recommendations list."""

    pass
