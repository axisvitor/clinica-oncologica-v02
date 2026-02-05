"""
Enhanced Reports API v2 Schemas
Advanced reporting features with custom builders, visualizations, and dashboards.

Features:
- Custom report builder with drag-and-drop fields
- Advanced data visualization configurations
- Report sharing and permissions
- Multi-format export (PDF, Excel, PowerPoint)
- Report versioning and history
- Interactive report dashboards
"""

from datetime import datetime, date, timezone
from typing import Optional, List, Dict, Any, Literal
from uuid import UUID
from enum import Enum
from pydantic import BaseModel, Field, model_validator, field_validator, ConfigDict


# ============================================================================
# Enums
# ============================================================================


class VisualizationType(str, Enum):
    """Types of data visualizations."""

    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    SCATTER_PLOT = "scatter_plot"
    HEATMAP = "heatmap"
    GAUGE = "gauge"
    TABLE = "table"
    CARD = "card"
    FUNNEL = "funnel"
    AREA_CHART = "area_chart"


class ReportPermissionLevel(str, Enum):
    """Permission levels for report sharing."""

    VIEW = "view"
    EDIT = "edit"
    ADMIN = "admin"


class DeliveryMethod(str, Enum):
    """Report delivery methods."""

    EMAIL = "email"
    WEBHOOK = "webhook"
    DOWNLOAD = "download"
    API = "api"


class ExportFormat(str, Enum):
    """Enhanced export formats."""

    PDF = "pdf"
    EXCEL = "excel"
    POWERPOINT = "powerpoint"
    CSV = "csv"
    JSON = "json"
    HTML = "html"


class DashboardLayout(str, Enum):
    """Dashboard layout types."""

    GRID = "grid"
    ROWS = "rows"
    COLUMNS = "columns"
    FREE = "free"


# ============================================================================
# Report Builder Schemas
# ============================================================================


class ReportFieldConfig(BaseModel):
    """Configuration for a report field."""

    field_name: str = Field(..., description="Field identifier")
    display_name: str = Field(..., description="Display label")
    field_type: Literal["text", "number", "date", "boolean", "enum", "calculated"] = (
        "text"
    )
    data_source: str = Field(..., description="Data source (table/model)")
    aggregation: Optional[Literal["sum", "avg", "count", "min", "max", "distinct"]] = (
        None
    )
    filter_enabled: bool = True
    sortable: bool = True
    format_string: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "field_name": "patient_count",
                "display_name": "Total Patients",
                "field_type": "number",
                "data_source": "patients",
                "aggregation": "count",
                "filter_enabled": True,
                "sortable": True,
            }
        }
    )


class ReportBuilderCreate(BaseModel):
    """Create a custom report using the builder."""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)

    # Selected fields
    fields: List[ReportFieldConfig] = Field(..., min_items=1, max_items=50)

    # Filters
    filters: Dict[str, Any] = Field(default_factory=dict)
    date_range: Optional[Dict[str, date]] = None

    # Grouping and sorting
    group_by: Optional[List[str]] = Field(None, max_items=5)
    sort_by: Optional[List[Dict[str, Literal["asc", "desc"]]]] = None

    # Display options
    include_totals: bool = True
    include_subtotals: bool = False
    page_size: int = Field(100, ge=10, le=10000)

    # Save as template
    save_as_template: bool = False
    template_name: Optional[str] = None

    @field_validator("date_range")
    @classmethod
    def validate_date_range(cls, v):
        """Ensure valid date range."""
        if v and "start" in v and "end" in v:
            if v["start"] > v["end"]:
                raise ValueError("start date must be before end date")
        return v


class ReportBuilderResponse(BaseModel):
    """Response from report builder."""

    id: UUID
    name: str
    description: Optional[str]
    fields: List[ReportFieldConfig]
    filters: Dict[str, Any]
    created_at: datetime
    created_by: UUID
    row_count: int
    generation_time_seconds: float
    download_url: str

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Visualization Schemas
# ============================================================================


class VisualizationConfig(BaseModel):
    """Configuration for a data visualization."""

    type: VisualizationType
    title: str = Field(..., max_length=200)

    # Data configuration
    data_field_x: Optional[str] = None
    data_field_y: Optional[str] = None
    data_fields: Optional[List[str]] = None

    # Display options
    colors: Optional[List[str]] = None
    show_legend: bool = True
    show_labels: bool = True
    show_grid: bool = True

    # Dimensions
    width: Optional[int] = Field(None, ge=100, le=2000)
    height: Optional[int] = Field(None, ge=100, le=2000)

    # Additional options
    options: Dict[str, Any] = Field(default_factory=dict)


class VisualizationCreate(BaseModel):
    """Create a visualization for a report."""

    report_id: UUID
    visualization: VisualizationConfig

    # Data source
    query_filters: Optional[Dict[str, Any]] = None
    aggregation_method: Optional[Literal["sum", "avg", "count", "min", "max"]] = "count"


class VisualizationResponse(BaseModel):
    """Visualization response with generated data."""

    id: UUID
    report_id: UUID
    config: VisualizationConfig
    data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VisualizationListResponse(BaseModel):
    """List of visualizations."""

    items: List[VisualizationResponse]
    total: int
    cursor: Optional[str] = None
    has_more: bool


# ============================================================================
# Scheduled Delivery Schemas
# ============================================================================


class DeliverySchedule(BaseModel):
    """Schedule for report delivery."""

    frequency: Literal["once", "daily", "weekly", "monthly", "quarterly", "custom"]
    start_date: date
    end_date: Optional[date] = None
    time_of_day: str = Field(..., pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    timezone: str = "UTC"

    # For weekly: day of week (0=Monday, 6=Sunday)
    day_of_week: Optional[int] = Field(None, ge=0, le=6)

    # For monthly: day of month (1-31)
    day_of_month: Optional[int] = Field(None, ge=1, le=31)

    # For custom: cron expression
    cron_expression: Optional[str] = None

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v, values):
        """Ensure end_date is after start_date."""
        if v and "start_date" in values and values["start_date"]:
            if v <= values["start_date"]:
                raise ValueError("end_date must be after start_date")
        return v


class EmailDeliveryConfig(BaseModel):
    """Email delivery configuration."""

    recipients: List[str] = Field(..., min_items=1, max_items=20)
    cc: Optional[List[str]] = Field(None, max_items=10)
    subject: str = Field(..., max_length=200)
    body_template: Optional[str] = None
    attach_report: bool = True
    inline_preview: bool = True


class WebhookDeliveryConfig(BaseModel):
    """Webhook delivery configuration."""

    url: str = Field(..., pattern=r"^https?://")
    method: Literal["POST", "PUT"] = "POST"
    headers: Dict[str, str] = Field(default_factory=dict)
    auth_type: Optional[Literal["none", "basic", "bearer", "api_key"]] = "none"
    auth_credentials: Optional[Dict[str, str]] = None
    retry_count: int = Field(3, ge=0, le=10)
    timeout_seconds: int = Field(30, ge=5, le=300)


class DeliveryConfigCreate(BaseModel):
    """Create delivery configuration for a report."""

    report_id: UUID
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None

    # Delivery method
    method: DeliveryMethod

    # Schedule
    schedule: DeliverySchedule

    # Method-specific configuration
    email_config: Optional[EmailDeliveryConfig] = None
    webhook_config: Optional[WebhookDeliveryConfig] = None

    # Export format
    export_format: ExportFormat = ExportFormat.PDF

    # Options
    is_active: bool = True
    send_on_error: bool = False

    @model_validator(mode="after")
    def validate_config(self):
        """Ensure method-specific config is provided."""
        if self.method == DeliveryMethod.EMAIL and not self.email_config:
            raise ValueError("email_config is required for email delivery")
        if self.method == DeliveryMethod.WEBHOOK and not self.webhook_config:
            raise ValueError("webhook_config is required for webhook delivery")
        return self


class DeliveryConfigResponse(BaseModel):
    """Delivery configuration response."""

    id: UUID
    report_id: UUID
    name: str
    description: Optional[str]
    method: DeliveryMethod
    schedule: DeliverySchedule
    email_config: Optional[EmailDeliveryConfig]
    webhook_config: Optional[WebhookDeliveryConfig]
    export_format: ExportFormat
    is_active: bool
    next_run: Optional[datetime]
    last_run: Optional[datetime]
    last_status: Optional[str]
    run_count: int
    created_at: datetime
    created_by: UUID

    model_config = ConfigDict(from_attributes=True)


class DeliveryHistoryEntry(BaseModel):
    """Single delivery history entry."""

    id: UUID
    delivery_config_id: UUID
    executed_at: datetime
    status: Literal["success", "failed", "partial"]
    recipients_count: int
    error_message: Optional[str]
    response_data: Optional[Dict[str, Any]]


# ============================================================================
# Report Sharing Schemas
# ============================================================================


class ReportShareCreate(BaseModel):
    """Share a report with users."""

    report_id: UUID
    user_ids: List[UUID] = Field(..., min_items=1, max_items=50)
    permission_level: ReportPermissionLevel = ReportPermissionLevel.VIEW
    expires_at: Optional[datetime] = None
    message: Optional[str] = Field(None, max_length=500)

    @field_validator("expires_at")
    @classmethod
    def validate_expiration(cls, v):
        """Ensure expiration is in the future."""
        if v and v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v and v <= datetime.now(timezone.utc):
            raise ValueError("expires_at must be in the future")
        return v


class PublicLinkCreate(BaseModel):
    """Create public link for report sharing."""

    report_id: UUID
    expires_at: Optional[datetime] = None
    password_protected: bool = False
    password: Optional[str] = Field(None, min_length=8, max_length=50)
    max_views: Optional[int] = Field(None, ge=1, le=10000)

    @model_validator(mode="after")
    def validate_password(self):
        """Ensure password is provided if password_protected."""
        if self.password_protected and not self.password:
            raise ValueError("password required when password_protected is True")
        return self


class ReportShareResponse(BaseModel):
    """Report share response."""

    id: UUID
    report_id: UUID
    shared_with: UUID
    permission_level: ReportPermissionLevel
    shared_by: UUID
    shared_at: datetime
    expires_at: Optional[datetime]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class PublicLinkResponse(BaseModel):
    """Public link response."""

    id: UUID
    report_id: UUID
    token: str
    url: str
    expires_at: Optional[datetime]
    password_protected: bool
    max_views: Optional[int]
    view_count: int
    created_at: datetime
    created_by: UUID
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Export Schemas
# ============================================================================


class ExportOptionsAdvanced(BaseModel):
    """Advanced export options for different formats."""

    # PDF options
    pdf_page_size: Literal["A4", "Letter", "Legal", "A3"] = "A4"
    pdf_orientation: Literal["portrait", "landscape"] = "portrait"
    pdf_include_toc: bool = True
    pdf_include_cover: bool = True

    # Excel options
    excel_sheet_name: Optional[str] = None
    excel_freeze_header: bool = True
    excel_autofilter: bool = True
    excel_conditional_formatting: bool = False

    # PowerPoint options
    ppt_template: Optional[str] = None
    ppt_include_notes: bool = False
    ppt_slides_per_chart: int = Field(1, ge=1, le=3)

    # Common options
    include_metadata: bool = True
    include_timestamp: bool = True
    compress: bool = False
    watermark_text: Optional[str] = None


class MultiFormatExportRequest(BaseModel):
    """Request for multi-format export."""

    report_id: UUID
    formats: List[ExportFormat] = Field(..., min_items=1, max_items=5)
    options: ExportOptionsAdvanced = Field(default_factory=ExportOptionsAdvanced)
    zip_results: bool = True


class ExportResponse(BaseModel):
    """Export response with download URLs."""

    export_id: UUID
    report_id: UUID
    formats: List[ExportFormat]
    status: Literal["pending", "processing", "completed", "failed"]
    download_urls: Dict[str, str]
    expires_at: datetime
    file_sizes: Dict[str, int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Report Versioning Schemas
# ============================================================================


class ReportVersion(BaseModel):
    """Report version information."""

    version: int
    created_at: datetime
    created_by: UUID
    change_summary: str
    configuration_snapshot: Dict[str, Any]
    data_hash: str


class ReportHistoryResponse(BaseModel):
    """Report version history."""

    report_id: UUID
    current_version: int
    versions: List[ReportVersion]
    total_versions: int

    model_config = ConfigDict(from_attributes=True)


class ReportRestoreRequest(BaseModel):
    """Request to restore a report version."""

    report_id: UUID
    version: int = Field(..., ge=1)
    create_backup: bool = True


# ============================================================================
# Dashboard Schemas
# ============================================================================


class DashboardWidgetConfig(BaseModel):
    """Configuration for a dashboard widget."""

    type: Literal["chart", "metric", "table", "text", "iframe", "card"]
    report_id: Optional[UUID] = None
    visualization_id: Optional[UUID] = None

    # Position and size
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    width: int = Field(..., ge=1, le=12)
    height: int = Field(..., ge=1, le=12)

    # Display options
    title: Optional[str] = None
    refresh_interval_seconds: Optional[int] = Field(None, ge=30, le=3600)

    # Widget-specific config
    config: Dict[str, Any] = Field(default_factory=dict)


class DashboardCreate(BaseModel):
    """Create an interactive dashboard."""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    layout: DashboardLayout = DashboardLayout.GRID

    # Widgets
    widgets: List[DashboardWidgetConfig] = Field(..., min_items=1, max_items=50)

    # Settings
    auto_refresh: bool = False
    refresh_interval_seconds: int = Field(300, ge=30, le=3600)
    is_public: bool = False
    shared_with: Optional[List[UUID]] = None

    # Styling
    theme: Literal["light", "dark", "auto"] = "light"
    custom_css: Optional[str] = None


class DashboardUpdate(BaseModel):
    """Update dashboard configuration."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    layout: Optional[DashboardLayout] = None
    widgets: Optional[List[DashboardWidgetConfig]] = None
    auto_refresh: Optional[bool] = None
    refresh_interval_seconds: Optional[int] = Field(None, ge=30, le=3600)
    is_public: Optional[bool] = None
    shared_with: Optional[List[UUID]] = None
    theme: Optional[Literal["light", "dark", "auto"]] = None


class DashboardResponse(BaseModel):
    """Dashboard response with widget data."""

    id: UUID
    name: str
    description: Optional[str]
    layout: DashboardLayout
    widgets: List[DashboardWidgetConfig]
    auto_refresh: bool
    refresh_interval_seconds: int
    is_public: bool
    shared_with: Optional[List[UUID]]
    theme: str
    created_at: datetime
    created_by: UUID
    updated_at: datetime
    view_count: int

    model_config = ConfigDict(from_attributes=True)


class DashboardListResponse(BaseModel):
    """List of dashboards."""

    items: List[DashboardResponse]
    total: int
    cursor: Optional[str] = None
    has_more: bool


class DashboardSnapshotCreate(BaseModel):
    """Create a dashboard snapshot."""

    dashboard_id: UUID
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    capture_data: bool = True


class DashboardSnapshotResponse(BaseModel):
    """Dashboard snapshot response."""

    id: UUID
    dashboard_id: UUID
    name: str
    description: Optional[str]
    snapshot_data: Dict[str, Any]
    created_at: datetime
    created_by: UUID

    model_config = ConfigDict(from_attributes=True)
