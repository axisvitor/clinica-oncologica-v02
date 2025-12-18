"""
Pydantic schemas for API validation and serialization.
"""

# Authentication schemas
from .auth import (
    TokenData,
    Token,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    UserResponse,
)

# Patient schemas
from .patient import (
    PatientBase,
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    PatientListResponse,
)

# Message schemas
from .message import (
    MessageBase,
    MessageCreate,
    MessageUpdate,
    MessageResponse,
    MessageListResponse,
    ScheduleMessageRequest,
    InboundMessageRequest,
)

# Flow schemas
from .flow import (
    FlowTemplateBase,
    FlowTemplateCreate,
    FlowTemplateUpdate,
    FlowTemplateResponse,
    PatientFlowStateBase,
    PatientFlowStateCreate,
    PatientFlowStateUpdate,
    PatientFlowStateResponse,
    FlowProgressionRequest,
    FlowProgressionResponse,
    FlowResetRequest,
    FlowHistoryResponse,
    FlowStepDefinition,
    FlowTemplateValidationResult,
    FlowAnalytics,
    FlowTemplateListResponse,
    PatientFlowStateListResponse,
    FlowOverrideRequest,
    FlowOverrideResponse,
)

# Quiz schemas
from .quiz import (
    QuestionType,
    ValidationRule,
    QuestionOption,
    QuizQuestion,
    QuizTemplateCreate,
    QuizTemplateUpdate,
    QuizTemplateResponse,
    QuizResponseCreate,
    QuizResponseResponse,
    QuizSessionCreate,
    QuizSessionResponse,
    QuizAnalytics,
    QuizValidationResult,
    QuizTemplateListResponse,
    QuizResponseListResponse,
    QuizSessionListResponse,
    PatientQuizAnalytics,
)

# Report schemas
from .report import (
    ReportSectionSchema,
    ReportGenerationRequest,
    ReportPreviewResponse,
    MedicalReportResponse,
    ReportListResponse,
    AnalyticsRequest,
    PatientAnalytics,
    SystemAnalytics,
    AnalyticsResponse,
    DashboardResponse,
)

# Alert schemas
from .alert import (
    AlertBase,
    AlertCreate,
    AlertUpdate,
    AlertResponse,
    AlertAcknowledge,
    AlertRuleConfig,
    AlertStatistics,
    AlertListResponse,
    PatientAlertSummary,
)

# WebSocket schemas
from .websocket import (
    WebSocketEventType,
    WebSocketMessage,
    AuthenticationRequest,
    AuthenticationResponse,
    JoinRoomRequest,
    JoinRoomResponse,
    PatientEventData,
    MessageEventData,
    QuizEventData,
    ReportEventData,
    AlertEventData,
    SystemEventData,
    ConnectionStatsResponse,
    ErrorResponse as WebSocketErrorResponse,
    create_websocket_message,
)

# Common schemas
from .common import (
    PaginationParams,
    PaginatedResponse,
    ErrorResponse,
    ValidationErrorResponse,
    NotFoundErrorResponse,
    UnauthorizedErrorResponse,
    ForbiddenErrorResponse,
    ConflictErrorResponse,
    RateLimitErrorResponse,
    ServiceUnavailableErrorResponse,
    SuccessResponse,
    HealthCheckResponse,
)

# Example data
from .examples import ALL_EXAMPLES

__all__ = [
    # Authentication
    "TokenData",
    "Token",
    "LoginRequest",
    "LoginResponse",
    "RefreshTokenRequest",
    "UserResponse",
    # Patient
    "PatientBase",
    "PatientCreate",
    "PatientUpdate",
    "PatientResponse",
    "PatientListResponse",
    # Message
    "MessageBase",
    "MessageCreate",
    "MessageUpdate",
    "MessageResponse",
    "MessageListResponse",
    "ScheduleMessageRequest",
    "InboundMessageRequest",
    # Flow
    "FlowTemplateBase",
    "FlowTemplateCreate",
    "FlowTemplateUpdate",
    "FlowTemplateResponse",
    "PatientFlowStateBase",
    "PatientFlowStateCreate",
    "PatientFlowStateUpdate",
    "PatientFlowStateResponse",
    "FlowProgressionRequest",
    "FlowProgressionResponse",
    "FlowResetRequest",
    "FlowHistoryResponse",
    "FlowStepDefinition",
    "FlowTemplateValidationResult",
    "FlowAnalytics",
    "FlowTemplateListResponse",
    "PatientFlowStateListResponse",
    "FlowOverrideRequest",
    "FlowOverrideResponse",
    # Quiz
    "QuestionType",
    "ValidationRule",
    "QuestionOption",
    "QuizQuestion",
    "QuizTemplateCreate",
    "QuizTemplateUpdate",
    "QuizTemplateResponse",
    "QuizResponseCreate",
    "QuizResponseResponse",
    "QuizSessionCreate",
    "QuizSessionResponse",
    "QuizAnalytics",
    "QuizValidationResult",
    "QuizTemplateListResponse",
    "QuizResponseListResponse",
    "QuizSessionListResponse",
    "PatientQuizAnalytics",
    # Report
    "ReportSectionSchema",
    "ReportGenerationRequest",
    "ReportPreviewResponse",
    "MedicalReportResponse",
    "ReportListResponse",
    "AnalyticsRequest",
    "PatientAnalytics",
    "SystemAnalytics",
    "AnalyticsResponse",
    "DashboardResponse",
    # Alert
    "AlertBase",
    "AlertCreate",
    "AlertUpdate",
    "AlertResponse",
    "AlertAcknowledge",
    "AlertRuleConfig",
    "AlertStatistics",
    "AlertListResponse",
    "PatientAlertSummary",
    # WebSocket
    "WebSocketEventType",
    "WebSocketMessage",
    "AuthenticationRequest",
    "AuthenticationResponse",
    "JoinRoomRequest",
    "JoinRoomResponse",
    "PatientEventData",
    "MessageEventData",
    "QuizEventData",
    "ReportEventData",
    "AlertEventData",
    "SystemEventData",
    "ConnectionStatsResponse",
    "WebSocketErrorResponse",
    "create_websocket_message",
    # Common
    "PaginationParams",
    "PaginatedResponse",
    "ErrorResponse",
    "ValidationErrorResponse",
    "NotFoundErrorResponse",
    "UnauthorizedErrorResponse",
    "ForbiddenErrorResponse",
    "ConflictErrorResponse",
    "RateLimitErrorResponse",
    "ServiceUnavailableErrorResponse",
    "SuccessResponse",
    "HealthCheckResponse",
    # Examples
    "ALL_EXAMPLES",
]
