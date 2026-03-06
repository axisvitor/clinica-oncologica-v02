"""
Admin Extensions Schemas for API v2
Comprehensive schemas for Dead Letter Queue and Audit Log Management.

These schemas support:
- DLQ item management (failures, retries, statistics)
- Audit log management (compliance, security tracking)
- Cursor-based pagination
- Field selection
- Export functionality
- HIPAA/LGPD compliance
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, field_validator, ConfigDict

from .common import CursorPaginatedResponse


# ============================================================================
# DLQ (DEAD LETTER QUEUE) SCHEMAS
# ============================================================================


class DLQItemStatus(str, Enum):
    """Status of DLQ items."""

    PENDING = "pending"
    RETRY_SCHEDULED = "retry_scheduled"
    RETRYING = "retrying"
    RESOLVED = "resolved"
    DISCARDED = "discarded"
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"


class DLQErrorCategory(str, Enum):
    """Error categories for intelligent retry."""

    TRANSIENT = "transient"  # Temporary error - automatic retry
    PERMANENT = "permanent"  # Permanent error - requires manual intervention
    UNKNOWN = "unknown"  # Unknown error - needs analysis


class DLQItemResponse(BaseModel):
    """Schema for DLQ item response."""

    id: UUID = Field(..., description="DLQ item ID")
    patient_id: UUID = Field(..., description="Patient ID")
    phone_number: str = Field(..., description="Phone number")
    message_type: str = Field(..., description="Message type")
    message_content: Optional[str] = Field(None, description="Message content")
    error_message: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    retry_count: int = Field(..., description="Number of retry attempts")
    max_retries: int = Field(..., description="Maximum retry attempts allowed")
    next_retry_at: Optional[datetime] = Field(
        None, description="Next retry scheduled at"
    )
    last_retry_at: Optional[datetime] = Field(None, description="Last retry attempt at")
    status: str = Field(..., description="DLQ item status")
    resolved_at: Optional[datetime] = Field(None, description="Resolution timestamp")
    dlq_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="DLQ metadata"
    )
    reviewed_by: Optional[UUID] = Field(None, description="Reviewer user ID")
    original_message_id: Optional[UUID] = Field(None, description="Original message ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "patient_id": "660e8400-e29b-41d4-a716-446655440000",
                "phone_number": "+5511999999999",
                "message_type": "appointment_reminder",
                "message_content": "Your appointment is tomorrow at 10 AM",
                "error_message": "Failed to deliver: Network timeout",
                "error_code": "TIMEOUT",
                "retry_count": 2,
                "max_retries": 5,
                "next_retry_at": "2025-01-17T16:00:00-03:00",
                "last_retry_at": "2025-01-17T15:00:00-03:00",
                "status": "retry_scheduled",
                "resolved_at": None,
                "dlq_metadata": {"category": "transient", "source": "whatsapp"},
                "reviewed_by": None,
                "original_message_id": "770e8400-e29b-41d4-a716-446655440000",
                "created_at": "2025-01-17T14:00:00-03:00",
                "updated_at": "2025-01-17T15:00:00-03:00",
            }
        },
    )


class DLQItemListResponse(CursorPaginatedResponse[DLQItemResponse]):
    """Cursor-paginated DLQ item list response."""

    pass


class DLQRetryResponse(BaseModel):
    """Schema for DLQ retry operation response."""

    success: bool = Field(..., description="Whether retry was successful")
    message: str = Field(..., description="Result message")
    dlq_id: UUID = Field(..., description="DLQ item ID")
    error: Optional[str] = Field(None, description="Error message if failed")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Message reprocessed successfully",
                "dlq_id": "550e8400-e29b-41d4-a716-446655440000",
                "error": None,
            }
        }
    )


class DLQBulkRetryRequest(BaseModel):
    """Schema for bulk retry request."""

    dlq_ids: List[UUID] = Field(
        ...,
        min_length=1,
        description="List of DLQ item IDs to retry (max 50)",
    )

    @field_validator("dlq_ids")
    @classmethod
    def validate_unique_ids(cls, v):
        if len(v) != len(set(v)):
            raise ValueError("DLQ IDs must be unique")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "dlq_ids": [
                    "550e8400-e29b-41d4-a716-446655440000",
                    "660e8400-e29b-41d4-a716-446655440001",
                    "770e8400-e29b-41d4-a716-446655440002",
                ]
            }
        }
    )


class DLQBulkRetryResponse(BaseModel):
    """Schema for bulk retry operation response."""

    success: bool = Field(..., description="Whether operation fully succeeded")
    total_requested: int = Field(..., description="Total items requested")
    successful: int = Field(..., description="Successfully processed items")
    failed: int = Field(..., description="Failed items")
    errors: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of errors"
    )
    message: str = Field(..., description="Operation result message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "total_requested": 10,
                "successful": 9,
                "failed": 1,
                "errors": [
                    {
                        "dlq_id": "550e8400-e29b-41d4-a716-446655440000",
                        "error": "Item not found",
                    }
                ],
                "message": "Bulk retry completed: 9 successful, 1 failed",
            }
        }
    )


class DLQStatsResponse(BaseModel):
    """Schema for DLQ statistics response."""

    total: int = Field(..., description="Total messages in DLQ")
    pending: int = Field(..., description="Pending messages")
    retry_scheduled: int = Field(..., description="Retries scheduled")
    retrying: int = Field(..., description="Currently retrying")
    resolved: int = Field(..., description="Resolved messages")
    discarded: int = Field(..., description="Discarded messages")
    max_retries_exceeded: int = Field(
        ..., description="Messages that exceeded max retries"
    )
    transient_errors_24h: int = Field(..., description="Transient errors in last 24h")
    permanent_errors_24h: int = Field(..., description="Permanent errors in last 24h")
    unknown_errors_24h: int = Field(..., description="Unknown errors in last 24h")
    retry_success_rate: float = Field(..., description="Retry success rate (%)")
    top_errors: List[Dict[str, Any]] = Field(
        default_factory=list, description="Top error types"
    )
    by_module: Dict[str, int] = Field(
        default_factory=dict, description="Errors by module/source"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 150,
                "pending": 20,
                "retry_scheduled": 30,
                "retrying": 5,
                "resolved": 80,
                "discarded": 10,
                "max_retries_exceeded": 5,
                "transient_errors_24h": 25,
                "permanent_errors_24h": 8,
                "unknown_errors_24h": 2,
                "retry_success_rate": 75.5,
                "top_errors": [
                    {"error_code": "TIMEOUT", "count": 45},
                    {"error_code": "INVALID_PHONE", "count": 15},
                ],
                "by_module": {"whatsapp": 100, "email": 30, "sms": 20},
            }
        }
    )


class DLQPurgeRequest(BaseModel):
    """Schema for DLQ purge request."""

    days: int = Field(
        90, ge=30, le=365, description="Delete items older than this many days"
    )
    dry_run: bool = Field(False, description="Preview without deleting")

    model_config = ConfigDict(
        json_schema_extra={"example": {"days": 90, "dry_run": True}}
    )


class DLQPurgeResponse(BaseModel):
    """Schema for DLQ purge operation response."""

    success: bool = Field(..., description="Whether operation succeeded")
    message: str = Field(..., description="Result message")
    count: int = Field(..., description="Number of items affected")
    days: int = Field(..., description="Days threshold used")
    cutoff_date: datetime = Field(..., description="Cutoff date used")
    dry_run: bool = Field(..., description="Whether this was a dry run")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Would delete 45 DLQ items",
                "count": 45,
                "days": 90,
                "cutoff_date": "2024-10-17T00:00:00-03:00",
                "dry_run": True,
            }
        }
    )


# ============================================================================
# AUDIT LOG SCHEMAS
# ============================================================================


class AuditLogEventType(str, Enum):
    """Audit log event types."""

    # Authentication
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    SESSION_CREATED = "session_created"
    SESSION_EXPIRED = "session_expired"
    TOKEN_REFRESH = "token_refresh"

    # Authorization
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGED = "permission_changed"
    ROLE_CHANGED = "role_changed"

    # Account Management
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET = "password_reset"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"

    # Admin Actions
    ADMIN_USER_CREATE = "admin_user_create"
    ADMIN_USER_UPDATE = "admin_user_update"
    ADMIN_USER_DELETE = "admin_user_delete"
    ADMIN_DLQ_RETRY = "admin_dlq_retry"
    ADMIN_DLQ_PURGE = "admin_dlq_purge"
    ADMIN_AUDIT_EXPORT = "admin_audit_export"

    # Security Events
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_TOKEN = "invalid_token"


class AuditLogStatus(str, Enum):
    """Audit log status."""

    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"


class AuditLogResponse(BaseModel):
    """Schema for audit log response."""

    id: UUID = Field(..., description="Audit log ID")
    event_type: str = Field(..., description="Event type")
    event_status: str = Field(..., description="Event status (success/failure/error)")
    user_id: Optional[UUID] = Field(None, description="User ID")
    user_email: Optional[str] = Field(None, description="User email")
    firebase_uid: Optional[str] = Field(None, description="Firebase UID")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="User agent string")
    resource: Optional[str] = Field(None, description="Resource accessed")
    action: Optional[str] = Field(None, description="Action performed")
    event_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Event metadata"
    )
    message: Optional[str] = Field(None, description="Event description")
    error_details: Optional[str] = Field(None, description="Error details")
    created_at: datetime = Field(..., description="Event timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "event_type": "login_success",
                "event_status": "success",
                "user_id": "660e8400-e29b-41d4-a716-446655440000",
                "user_email": "doctor@example.com",
                "firebase_uid": "firebase_uid_123",
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0...",
                "resource": "/api/v2/auth/login",
                "action": "login",
                "event_metadata": {"device": "desktop", "browser": "Chrome"},
                "message": "User logged in successfully",
                "error_details": None,
                "created_at": "2025-01-17T14:00:00-03:00",
                "updated_at": "2025-01-17T14:00:00-03:00",
            }
        },
    )


class AuditLogListResponse(CursorPaginatedResponse[AuditLogResponse]):
    """Cursor-paginated audit log list response."""

    pass


class AuditLogExportFormat(str, Enum):
    """Export format options."""

    CSV = "csv"
    JSON = "json"


class AuditLogExportRequest(BaseModel):
    """Schema for audit log export request."""

    format: AuditLogExportFormat = Field(..., description="Export format (csv or json)")
    fields: Optional[List[str]] = Field(
        None, description="Fields to include (None = all)"
    )
    redact_sensitive: bool = Field(True, description="Redact sensitive data")

    @field_validator("format")
    @classmethod
    def validate_format(cls, v):
        if not isinstance(v, AuditLogExportFormat):
            try:
                return AuditLogExportFormat(v.lower())
            except ValueError:
                raise ValueError(
                    f"Format must be one of: {', '.join([f.value for f in AuditLogExportFormat])}"
                )
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "format": "csv",
                "fields": [
                    "id",
                    "event_type",
                    "user_email",
                    "ip_address",
                    "created_at",
                ],
                "redact_sensitive": True,
            }
        }
    )


class AuditLogStatisticsResponse(BaseModel):
    """Schema for audit log statistics response."""

    total_events: int = Field(..., description="Total events")
    events_today: int = Field(..., description="Events today")
    events_this_week: int = Field(..., description="Events this week")
    events_this_month: int = Field(..., description="Events this month")
    by_event_type: Dict[str, int] = Field(..., description="Event counts by type")
    by_status: Dict[str, int] = Field(..., description="Event counts by status")
    by_user: List[Dict[str, Any]] = Field(
        default_factory=list, description="Top users by activity"
    )
    security_events: int = Field(..., description="Security-related events")
    failed_logins: int = Field(..., description="Failed login attempts")
    success_rate: float = Field(..., description="Success rate (%)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_events": 15420,
                "events_today": 234,
                "events_this_week": 1852,
                "events_this_month": 7890,
                "by_event_type": {
                    "login_success": 4500,
                    "login_failure": 120,
                    "admin_user_create": 45,
                },
                "by_status": {"success": 14200, "failure": 980, "error": 240},
                "by_user": [{"user_email": "admin@example.com", "event_count": 450}],
                "security_events": 360,
                "failed_logins": 120,
                "success_rate": 92.1,
            }
        }
    )


# ============================================================================
# COMMON/SHARED SCHEMAS
# ============================================================================


class BulkOperationResult(BaseModel):
    """Schema for bulk operation results."""

    success: bool = Field(..., description="Whether operation fully succeeded")
    total_requested: int = Field(..., description="Total items requested")
    successful: int = Field(..., description="Successfully processed items")
    failed: int = Field(..., description="Failed items")
    errors: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of errors"
    )
    message: str = Field(..., description="Operation result message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "total_requested": 50,
                "successful": 48,
                "failed": 2,
                "errors": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "error": "Item not found",
                    },
                    {
                        "id": "660e8400-e29b-41d4-a716-446655440001",
                        "error": "Permission denied",
                    },
                ],
                "message": "Bulk operation completed: 48 successful, 2 failed",
            }
        }
    )


class AdminExtensionHealthResponse(BaseModel):
    """Schema for admin extensions health check."""

    status: str = Field(..., description="Health status")
    dlq_health: Dict[str, Any] = Field(..., description="DLQ subsystem health")
    audit_health: Dict[str, Any] = Field(..., description="Audit subsystem health")
    cache_health: Dict[str, Any] = Field(..., description="Cache health")
    database_health: Dict[str, Any] = Field(..., description="Database health")
    timestamp: datetime = Field(..., description="Health check timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "dlq_health": {
                    "status": "healthy",
                    "pending_items": 25,
                    "oldest_item_age_hours": 12.5,
                },
                "audit_health": {
                    "status": "healthy",
                    "total_logs": 15420,
                    "logs_today": 234,
                },
                "cache_health": {"status": "healthy", "hit_rate": 87.5},
                "database_health": {
                    "status": "healthy",
                    "connection_pool": "available",
                },
                "timestamp": "2025-01-17T15:00:00-03:00",
            }
        }
    )


# ============================================================================
# FILTER AND SEARCH SCHEMAS
# ============================================================================


class DLQFilterRequest(BaseModel):
    """Schema for DLQ filter parameters."""

    status: Optional[DLQItemStatus] = Field(None, description="Filter by status")
    error_category: Optional[DLQErrorCategory] = Field(
        None, description="Filter by error category"
    )
    patient_id: Optional[UUID] = Field(None, description="Filter by patient")
    error_code: Optional[str] = Field(None, description="Filter by error code")
    date_from: Optional[datetime] = Field(None, description="Filter from date")
    date_to: Optional[datetime] = Field(None, description="Filter to date")
    search: Optional[str] = Field(None, description="Search in error messages")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "retry_scheduled",
                "error_category": "transient",
                "patient_id": "660e8400-e29b-41d4-a716-446655440000",
                "error_code": "TIMEOUT",
                "date_from": "2025-01-01T00:00:00-03:00",
                "date_to": "2025-01-31T23:59:59-03:00",
                "search": "network",
            }
        }
    )


class AuditLogFilterRequest(BaseModel):
    """Schema for audit log filter parameters."""

    event_type: Optional[str] = Field(None, description="Filter by event type")
    event_status: Optional[AuditLogStatus] = Field(None, description="Filter by status")
    user_id: Optional[UUID] = Field(None, description="Filter by user")
    user_email: Optional[str] = Field(None, description="Filter by user email")
    ip_address: Optional[str] = Field(None, description="Filter by IP address")
    date_from: Optional[datetime] = Field(None, description="Filter from date")
    date_to: Optional[datetime] = Field(None, description="Filter to date")
    search: Optional[str] = Field(None, description="Search in messages")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_type": "login_success",
                "event_status": "success",
                "user_email": "doctor@example.com",
                "ip_address": "192.168.1.100",
                "date_from": "2025-01-01T00:00:00-03:00",
                "date_to": "2025-01-31T23:59:59-03:00",
                "search": "admin",
            }
        }
    )


# ============================================================================
# FLOW OPS SCHEMAS
# ============================================================================


class FlowOpsResetResponse(BaseModel):
    patient_id: UUID
    flow_state_id: UUID
    action: str = "reset"
    cleared_fields: list[str]


class FlowOpsAdvanceResponse(BaseModel):
    patient_id: UUID
    flow_state_id: UUID
    action: str = "advance"
    new_day: int


class FlowOpsUnstickResponse(BaseModel):
    patient_id: UUID
    flow_state_id: UUID
    action: str = "unstick"
    cleared_fields: list[str]


class FailedFlowOperation(BaseModel):
    flow_state_id: UUID
    patient_id: UUID
    patient_name: str | None
    current_step: int | None
    failure_type: str
    failure_details: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime | None


class FailedFlowOperationsResponse(BaseModel):
    items: list[FailedFlowOperation] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class FlowHealthSummaryResponse(BaseModel):
    active: int
    stalled: int
    failed: int
    completed: int


class StalledFlowInfo(BaseModel):
    patient_id: str
    flow_state_id: str
    hours_stuck: float
    last_interaction_at: str | None


class FlowStallCheckResponse(BaseModel):
    stalled_count: int
    alerts_fired: bool
    stalled_flows: list[StalledFlowInfo] = Field(default_factory=list)
