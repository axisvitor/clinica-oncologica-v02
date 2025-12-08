"""
Reports API v2 Schemas
Comprehensive schemas for report generation, scheduling, and templates.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any, Literal
from uuid import UUID
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class ReportFormat(str, Enum):
    """Report output formats."""
    CSV = "csv"
    JSON = "json"
    PDF = "pdf"
    EXCEL = "excel"


class ReportStatus(str, Enum):
    """Report generation status."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReportType(str, Enum):
    """Pre-defined report types."""
    PATIENT_SUMMARY = "patient_summary"
    PATIENT_ACTIVITY = "patient_activity"
    FLOW_PERFORMANCE = "flow_performance"
    MESSAGE_DELIVERY = "message_delivery"
    QUIZ_COMPLETION = "quiz_completion"
    ANALYTICS_OVERVIEW = "analytics_overview"
    CUSTOM = "custom"


class ScheduleFrequency(str, Enum):
    """Report scheduling frequency."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


# ============================================================================
# Report Generation Schemas
# ============================================================================

class ReportGenerateRequest(BaseModel):
    """Request to generate a custom report."""
    report_type: ReportType
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    format: ReportFormat = ReportFormat.JSON

    # Filters
    patient_ids: Optional[List[UUID]] = Field(None, max_items=1000)
    doctor_ids: Optional[List[UUID]] = Field(None, max_items=100)
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    flow_states: Optional[List[str]] = None

    # Additional parameters
    include_charts: bool = True
    include_raw_data: bool = False
    aggregation_level: Literal["day", "week", "month"] = "day"

    # Template
    template_id: Optional[UUID] = None

    @field_validator("date_to")
    @classmethod
    def validate_dates(cls, v, info):
        """Ensure date_to is after date_from."""
        if v and info.data.get("date_from"):
            if v < info.data["date_from"]:
                raise ValueError("date_to must be after date_from")
        return v

    @field_validator("patient_ids")
    @classmethod
    def validate_patient_ids_unique(cls, v):
        """Ensure patient IDs are unique."""
        if v and len(v) != len(set(v)):
            raise ValueError("patient_ids must be unique")
        return v


class ReportResponse(BaseModel):
    """Report response with generation details."""
    id: UUID
    title: str
    description: Optional[str]
    report_type: ReportType
    format: ReportFormat
    status: ReportStatus

    # Generation info
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    generated_by: UUID

    # File info
    file_url: Optional[str] = None
    file_size_bytes: Optional[int] = None
    download_url: Optional[str] = None

    # Statistics
    record_count: Optional[int] = None
    generation_time_seconds: Optional[float] = None

    # Error info
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class ReportStatusResponse(BaseModel):
    """Report generation status."""
    id: UUID
    status: ReportStatus
    progress_percentage: int = Field(ge=0, le=100)
    current_step: Optional[str] = None
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None


class ReportListResponse(BaseModel):
    """Paginated list of reports."""
    items: List[ReportResponse]
    total: int
    cursor: Optional[str] = None
    has_more: bool


# ============================================================================
# Pre-defined Report Schemas
# ============================================================================

class PatientSummaryReport(BaseModel):
    """Patient summary report data."""
    total_patients: int
    active_patients: int
    inactive_patients: int
    new_patients_period: int
    by_treatment_type: Dict[str, int]
    by_flow_state: Dict[str, int]
    by_doctor: Optional[List[Dict[str, Any]]] = None
    generated_at: datetime


class PatientActivityReport(BaseModel):
    """Patient activity report data."""
    total_interactions: int
    average_response_time_hours: float
    engagement_rate: float
    messages_sent: int
    messages_received: int
    quizzes_completed: int
    by_patient: List[Dict[str, Any]]
    activity_timeline: List[Dict[str, Any]]
    generated_at: datetime


class FlowPerformanceReport(BaseModel):
    """Flow performance metrics report."""
    total_flows: int
    active_flows: int
    completion_rate: float
    average_flow_duration_days: float
    flows_by_state: Dict[str, int]
    bottlenecks: List[Dict[str, Any]]
    performance_timeline: List[Dict[str, Any]]
    generated_at: datetime


class MessageDeliveryReport(BaseModel):
    """Message delivery statistics report."""
    total_messages: int
    delivered: int
    failed: int
    pending: int
    delivery_rate: float
    average_delivery_time_seconds: float
    failures_by_reason: Dict[str, int]
    delivery_timeline: List[Dict[str, Any]]
    generated_at: datetime


class QuizCompletionReport(BaseModel):
    """Quiz completion statistics report."""
    total_quizzes: int
    completed: int
    in_progress: int
    cancelled: int
    completion_rate: float
    average_completion_time_minutes: float
    by_template: List[Dict[str, Any]]
    completion_timeline: List[Dict[str, Any]]
    generated_at: datetime


class AnalyticsOverviewReport(BaseModel):
    """Comprehensive analytics overview."""
    period_start: date
    period_end: date
    patient_metrics: PatientSummaryReport
    activity_metrics: PatientActivityReport
    flow_metrics: FlowPerformanceReport
    message_metrics: MessageDeliveryReport
    quiz_metrics: QuizCompletionReport
    key_insights: List[str]
    recommendations: List[str]
    generated_at: datetime


# ============================================================================
# Scheduled Report Schemas
# ============================================================================

class ScheduledReportCreate(BaseModel):
    """Create a scheduled report."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    report_type: ReportType
    format: ReportFormat = ReportFormat.PDF

    # Schedule
    frequency: ScheduleFrequency
    start_date: date
    end_date: Optional[date] = None
    time_of_day: str = Field(..., pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")  # HH:MM
    timezone: str = "UTC"

    # Filters (same as ReportGenerateRequest)
    patient_ids: Optional[List[UUID]] = None
    doctor_ids: Optional[List[UUID]] = None
    flow_states: Optional[List[str]] = None

    # Recipients
    recipient_emails: List[str] = Field(..., min_items=1, max_items=10)

    # Options
    include_charts: bool = True
    is_active: bool = True

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v, info):
        """Ensure end_date is after start_date."""
        if v and info.data.get("start_date"):
            if v <= info.data["start_date"]:
                raise ValueError("end_date must be after start_date")
        return v


class ScheduledReportUpdate(BaseModel):
    """Update a scheduled report."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    format: Optional[ReportFormat] = None

    # Schedule
    frequency: Optional[ScheduleFrequency] = None
    time_of_day: Optional[str] = Field(None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    timezone: Optional[str] = None
    end_date: Optional[date] = None

    # Recipients
    recipient_emails: Optional[List[str]] = Field(None, min_items=1, max_items=10)

    # Options
    include_charts: Optional[bool] = None
    is_active: Optional[bool] = None


class ScheduledReportResponse(BaseModel):
    """Scheduled report configuration."""
    id: UUID
    name: str
    description: Optional[str]
    report_type: ReportType
    format: ReportFormat

    # Schedule
    frequency: ScheduleFrequency
    start_date: date
    end_date: Optional[date]
    time_of_day: str
    timezone: str
    next_run: Optional[datetime]
    last_run: Optional[datetime]

    # Recipients
    recipient_emails: List[str]

    # Status
    is_active: bool
    run_count: int

    # Metadata
    created_at: datetime
    created_by: UUID

    model_config = ConfigDict(from_attributes=True)


class ScheduledReportListResponse(BaseModel):
    """Paginated list of scheduled reports."""
    items: List[ScheduledReportResponse]
    total: int
    cursor: Optional[str] = None
    has_more: bool


# ============================================================================
# Report Template Schemas
# ============================================================================

class ReportTemplateCreate(BaseModel):
    """Create a report template."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    report_type: ReportType

    # Template configuration
    default_format: ReportFormat = ReportFormat.PDF
    default_filters: Dict[str, Any] = Field(default_factory=dict)
    sections: List[str] = Field(..., min_items=1)

    # Styling
    branding: Optional[Dict[str, Any]] = None
    layout: Optional[Dict[str, Any]] = None

    # Permissions
    is_public: bool = False
    shared_with: Optional[List[UUID]] = None


class ReportTemplateUpdate(BaseModel):
    """Update a report template."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    default_format: Optional[ReportFormat] = None
    default_filters: Optional[Dict[str, Any]] = None
    sections: Optional[List[str]] = Field(None, min_items=1)
    branding: Optional[Dict[str, Any]] = None
    layout: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None
    shared_with: Optional[List[UUID]] = None


class ReportTemplateResponse(BaseModel):
    """Report template details."""
    id: UUID
    name: str
    description: Optional[str]
    report_type: ReportType

    # Configuration
    default_format: ReportFormat
    default_filters: Dict[str, Any]
    sections: List[str]
    branding: Optional[Dict[str, Any]]
    layout: Optional[Dict[str, Any]]

    # Permissions
    is_public: bool
    shared_with: Optional[List[UUID]]

    # Metadata
    created_at: datetime
    created_by: UUID
    updated_at: datetime
    usage_count: int

    model_config = ConfigDict(from_attributes=True)


class ReportTemplateListResponse(BaseModel):
    """Paginated list of templates."""
    items: List[ReportTemplateResponse]
    total: int
    cursor: Optional[str] = None
    has_more: bool


# ============================================================================
# Export Data Schemas (for streaming)
# ============================================================================

class ReportDataRow(BaseModel):
    """Single row of report data for streaming."""
    data: Dict[str, Any]


class ReportDataChunk(BaseModel):
    """Chunk of report data for streaming."""
    rows: List[ReportDataRow]
    chunk_number: int
    total_chunks: Optional[int] = None
    has_more: bool
