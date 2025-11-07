"""
API v2 Schemas
Pydantic models for API v2 endpoints with enhanced features.
"""

from .common import (
    PaginationParams,
    CursorPaginatedResponse,
    FieldSelection,
    EagerLoadParams,
)
from .patient import (
    PatientV2Response,
    PatientV2List,
    PatientV2Create,
    PatientV2Update,
)
from .quiz import (
    QuizV2Response,
    QuizV2List,
    QuizV2Create,
    QuizV2Update,
)
from .analytics import (
    AnalyticsOverview,
    QuizStatusDistribution,
    CompletionTrend,
    PatientEngagement,
)
from .reports import (
    ReportFormat,
    ReportStatus,
    ReportType,
    ReportGenerateRequest,
    ReportResponse,
    ReportStatusResponse,
    ReportListResponse,
    PatientSummaryReport,
    PatientActivityReport,
    FlowPerformanceReport,
    MessageDeliveryReport,
    QuizCompletionReport,
    AnalyticsOverviewReport,
    ScheduledReportCreate,
    ScheduledReportUpdate,
    ScheduledReportResponse,
    ScheduledReportListResponse,
    ReportTemplateCreate,
    ReportTemplateUpdate,
    ReportTemplateResponse,
    ReportTemplateListResponse,
)

__all__ = [
    "PaginationParams",
    "CursorPaginatedResponse",
    "FieldSelection",
    "EagerLoadParams",
    "PatientV2Response",
    "PatientV2List",
    "PatientV2Create",
    "PatientV2Update",
    "QuizV2Response",
    "QuizV2List",
    "QuizV2Create",
    "QuizV2Update",
    "AnalyticsOverview",
    "QuizStatusDistribution",
    "CompletionTrend",
    "PatientEngagement",
    "ReportFormat",
    "ReportStatus",
    "ReportType",
    "ReportGenerateRequest",
    "ReportResponse",
    "ReportStatusResponse",
    "ReportListResponse",
    "PatientSummaryReport",
    "PatientActivityReport",
    "FlowPerformanceReport",
    "MessageDeliveryReport",
    "QuizCompletionReport",
    "AnalyticsOverviewReport",
    "ScheduledReportCreate",
    "ScheduledReportUpdate",
    "ScheduledReportResponse",
    "ScheduledReportListResponse",
    "ReportTemplateCreate",
    "ReportTemplateUpdate",
    "ReportTemplateResponse",
    "ReportTemplateListResponse",
]
