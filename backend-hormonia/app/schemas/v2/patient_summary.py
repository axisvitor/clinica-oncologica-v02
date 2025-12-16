"""
Patient Summary Schemas - Pydantic models for AI-generated summaries.
"""
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class SeverityLevel(str, Enum):
    """Severity level for health concerns."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HealthConcern(BaseModel):
    """Individual health concern detected in summary period."""
    concern: str = Field(..., description="Description of the health concern")
    severity: SeverityLevel = Field(..., description="Severity level")
    detected_date: Optional[date] = Field(None, description="When the concern was detected")
    source: Optional[str] = Field(None, description="Source of detection (quiz, message, etc.)")


class QuizFindings(BaseModel):
    """Summary of quiz responses in the period."""
    total_completed: int = Field(0, description="Total quizzes completed")
    total_questions_answered: int = Field(0, description="Total questions answered")
    key_findings: List[str] = Field(default_factory=list, description="Key findings from responses")
    symptom_trends: Dict[str, str] = Field(default_factory=dict, description="Symptom trends (symptom: trend)")
    concerning_responses: List[str] = Field(default_factory=list, description="Responses that need attention")


class EngagementMetrics(BaseModel):
    """Patient engagement metrics for the period."""
    response_rate: float = Field(0.0, ge=0, le=1, description="Response rate (0-1)")
    avg_response_time_minutes: float = Field(0.0, ge=0, description="Average response time in minutes")
    total_messages_sent: int = Field(0, ge=0, description="Total messages sent to patient")
    total_messages_received: int = Field(0, ge=0, description="Total messages received from patient")
    engagement_score: float = Field(0.0, ge=0, le=100, description="Overall engagement score (0-100)")


class TreatmentCompliance(BaseModel):
    """Treatment compliance metrics."""
    adherence_score: float = Field(0.0, ge=0, le=1, description="Adherence score (0-1)")
    missed_interactions: int = Field(0, ge=0, description="Number of missed interactions")
    notes: Optional[str] = Field(None, description="Compliance notes")


class SummaryContent(BaseModel):
    """Full content structure of a patient summary."""
    overview: str = Field(..., description="2-3 paragraphs overview for doctor")
    quiz_findings: QuizFindings = Field(default_factory=QuizFindings)
    health_concerns: List[HealthConcern] = Field(default_factory=list)
    engagement_metrics: EngagementMetrics = Field(default_factory=EngagementMetrics)
    treatment_compliance: TreatmentCompliance = Field(default_factory=TreatmentCompliance)
    recommendations: List[str] = Field(default_factory=list, description="3-5 actionable recommendations")


# Request schemas
class GenerateSummaryRequest(BaseModel):
    """Request to generate a new patient summary."""
    patient_id: UUID = Field(..., description="Patient UUID")
    start_date: date = Field(..., description="Start date of period to analyze")
    end_date: date = Field(..., description="End date of period to analyze")
    include_sections: Optional[List[str]] = Field(
        None,
        description="Specific sections to include (all if not specified)"
    )
    force_refresh: bool = Field(False, description="Force regeneration even if cached")
    save_summary: bool = Field(True, description="Save summary to database")


class GetSummariesRequest(BaseModel):
    """Request to get saved summaries for a patient."""
    patient_id: UUID
    limit: int = Field(10, ge=1, le=50)
    offset: int = Field(0, ge=0)


# Response schemas
class PatientSummaryResponse(BaseModel):
    """Response containing a generated patient summary."""
    summary_id: UUID = Field(..., description="Unique summary ID")
    patient_id: UUID = Field(..., description="Patient UUID")
    patient_name: str = Field(..., description="Patient name")

    # Period
    start_date: date
    end_date: date

    # Content
    content: SummaryContent

    # Metadata
    generated_at: datetime
    generated_by: Optional[UUID] = None
    token_usage: Optional[int] = None
    model_used: Optional[str] = None
    generation_time_ms: Optional[int] = None

    # Cache info
    from_cache: bool = False

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class PatientSummaryListResponse(BaseModel):
    """Response containing list of summaries."""
    summaries: List[PatientSummaryResponse]
    total: int
    has_more: bool


class SummaryExportResponse(BaseModel):
    """Response for PDF export."""
    summary_id: UUID
    pdf_url: Optional[str] = None
    pdf_base64: Optional[str] = None
    filename: str
    generated_at: datetime


# AI generation schemas
class SummaryGenerationMetrics(BaseModel):
    """Metrics from summary generation."""
    data_points_analyzed: int = Field(0, description="Number of data points analyzed")
    quiz_responses_count: int = Field(0)
    messages_count: int = Field(0)
    alerts_count: int = Field(0)
    generation_time_ms: int = Field(0)
    token_usage: int = Field(0)
    estimated_cost_usd: float = Field(0.0)
