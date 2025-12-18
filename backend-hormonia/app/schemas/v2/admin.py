"""
Admin Management Schemas for API v2
Comprehensive schemas for user, role, permission, and audit management.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict

from .common import CursorPaginatedResponse


# ============================================================================
# USER MANAGEMENT SCHEMAS
# ============================================================================


class UserCreateRequest(BaseModel):
    """Schema for creating a new user."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ..., min_length=8, description="User password (minimum 8 characters)"
    )
    full_name: str = Field(
        ..., min_length=2, max_length=255, description="User's full name"
    )
    role: str = Field(..., description="User role: admin, doctor")
    is_active: bool = Field(default=True, description="Whether the user is active")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        allowed_roles = ["admin", "doctor"]
        if v.lower() not in allowed_roles:
            raise ValueError(f"Role must be one of {allowed_roles}")
        return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "doctor@example.com",
                "password": "SecureP@ss123",
                "full_name": "Dr. Jane Smith",
                "role": "doctor",
                "is_active": True,
            }
        }
    )


class UserUpdateRequest(BaseModel):
    """Schema for updating user information."""

    email: Optional[EmailStr] = Field(None, description="User email address")
    full_name: Optional[str] = Field(
        None, min_length=2, max_length=255, description="User's full name"
    )
    role: Optional[str] = Field(None, description="User role: admin, doctor")
    is_active: Optional[bool] = Field(None, description="Whether the user is active")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v is None:
            return v
        allowed_roles = ["admin", "doctor"]
        if v.lower() not in allowed_roles:
            raise ValueError(f"Role must be one of {allowed_roles}")
        return v.lower()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"full_name": "Dr. Jane Smith-Jones", "is_active": False}
        }
    )


class UserResponse(BaseModel):
    """Schema for user response."""

    id: UUID = Field(..., description="User ID")
    email: str = Field(..., description="User email address")
    full_name: Optional[str] = Field(None, description="User's full name")
    role: str = Field(..., description="User role")
    is_active: bool = Field(..., description="Whether the user is active")
    created_at: datetime = Field(..., description="User creation timestamp")
    updated_at: datetime = Field(..., description="User last update timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    firebase_uid: Optional[str] = Field(None, description="Firebase UID")

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(CursorPaginatedResponse[UserResponse]):
    """Cursor-paginated user list response."""

    pass


class UserActionResponse(BaseModel):
    """Schema for user action responses."""

    success: bool = Field(..., description="Whether the action was successful")
    message: str = Field(..., description="Action result message")
    user_id: UUID = Field(..., description="Affected user ID")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Action timestamp"
    )


class UserResetPasswordRequest(BaseModel):
    """Schema for resetting user password."""

    new_password: str = Field(
        ..., min_length=8, description="New password (minimum 8 characters)"
    )
    force_change: bool = Field(
        default=True, description="Force user to change password on next login"
    )

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


# ============================================================================
# ROLE MANAGEMENT SCHEMAS
# ============================================================================


class RoleCreateRequest(BaseModel):
    """Schema for creating a new role."""

    name: str = Field(..., min_length=2, max_length=50, description="Role name")
    description: Optional[str] = Field(
        None, max_length=255, description="Role description"
    )
    permissions: List[str] = Field(
        default_factory=list, description="List of permission names"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "nurse",
                "description": "Nursing staff role",
                "permissions": ["read_patients", "update_patients"],
            }
        }
    )


class RoleUpdateRequest(BaseModel):
    """Schema for updating role information."""

    name: Optional[str] = Field(
        None, min_length=2, max_length=50, description="Role name"
    )
    description: Optional[str] = Field(
        None, max_length=255, description="Role description"
    )
    permissions: Optional[List[str]] = Field(
        None, description="List of permission names"
    )


class RoleResponse(BaseModel):
    """Schema for role response."""

    id: UUID = Field(..., description="Role ID")
    name: str = Field(..., description="Role name")
    description: Optional[str] = Field(None, description="Role description")
    permissions: List[str] = Field(
        default_factory=list, description="List of permissions"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class RoleListResponse(CursorPaginatedResponse[RoleResponse]):
    """Cursor-paginated role list response."""

    pass


# ============================================================================
# PERMISSION MANAGEMENT SCHEMAS
# ============================================================================


class PermissionResponse(BaseModel):
    """Schema for permission response."""

    id: UUID = Field(..., description="Permission ID")
    name: str = Field(..., description="Permission name")
    description: Optional[str] = Field(None, description="Permission description")
    resource: str = Field(..., description="Resource type (e.g., 'users', 'patients')")
    action: str = Field(
        ..., description="Action type (e.g., 'read', 'write', 'delete')"
    )

    model_config = ConfigDict(from_attributes=True)


class PermissionListResponse(CursorPaginatedResponse[PermissionResponse]):
    """Cursor-paginated permission list response."""

    pass


class PermissionAssignRequest(BaseModel):
    """Schema for assigning permissions to a user."""

    permissions: List[str] = Field(
        ..., min_length=1, description="List of permission names to assign"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "permissions": ["read_patients", "update_patients", "read_analytics"]
            }
        }
    )


# ============================================================================
# AUDIT LOG SCHEMAS
# ============================================================================


class AuditLogRecord(BaseModel):
    """Schema for individual audit log record."""

    id: UUID = Field(..., description="Audit log ID")
    event_type: str = Field(..., description="Type of event")
    event_category: str = Field(..., description="Event category")
    severity: str = Field(..., description="Event severity")
    user_id: Optional[UUID] = Field(None, description="User who triggered the event")
    user_email: Optional[str] = Field(None, description="User email")
    ip_address: Optional[str] = Field(None, description="IP address")
    user_agent: Optional[str] = Field(None, description="User agent string")
    event_data: Dict[str, Any] = Field(default_factory=dict, description="Event data")
    result: str = Field(..., description="Event result (success/failure)")
    timestamp: datetime = Field(..., description="Event timestamp")

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(CursorPaginatedResponse[AuditLogRecord]):
    """Cursor-paginated audit log list response."""

    pass


class UserActivityRecord(BaseModel):
    """Schema for user activity record."""

    id: str = Field(..., description="Activity record ID")
    user_id: str = Field(..., description="User ID")
    user_email: Optional[str] = Field(None, description="User email")
    action: str = Field(..., description="Action performed")
    resource: str = Field(..., description="Resource affected")
    resource_id: Optional[str] = Field(None, description="Resource ID")
    details: Dict[str, Any] = Field(
        default_factory=dict, description="Activity details"
    )
    timestamp: datetime = Field(..., description="Activity timestamp")
    ip_address: str = Field(..., description="IP address")
    user_agent: Optional[str] = Field(None, description="User agent")

    model_config = ConfigDict(from_attributes=True)


class UserActivityResponse(CursorPaginatedResponse[UserActivityRecord]):
    """Cursor-paginated user activity response."""

    pass


# ============================================================================
# STATISTICS SCHEMAS
# ============================================================================


class UserStatsResponse(BaseModel):
    """Schema for user statistics."""

    total_users: int = Field(..., description="Total number of users")
    active_users: int = Field(..., description="Number of active users")
    inactive_users: int = Field(..., description="Number of inactive users")
    by_role: Dict[str, int] = Field(..., description="User count by role")
    recent_registrations: int = Field(
        ..., description="Registrations in the last 30 days"
    )
    growth_rate: Optional[float] = Field(None, description="Monthly growth rate (%)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_users": 150,
                "active_users": 142,
                "inactive_users": 8,
                "by_role": {"admin": 5, "doctor": 145},
                "recent_registrations": 12,
                "growth_rate": 8.5,
            }
        }
    )


class ActivityStatsResponse(BaseModel):
    """Schema for activity statistics."""

    total_events: int = Field(..., description="Total number of events")
    events_today: int = Field(..., description="Events logged today")
    events_this_week: int = Field(..., description="Events logged this week")
    events_this_month: int = Field(..., description="Events logged this month")
    by_event_type: Dict[str, int] = Field(..., description="Event counts by type")
    by_severity: Dict[str, int] = Field(..., description="Event counts by severity")
    most_active_users: List[Dict[str, Any]] = Field(
        default_factory=list, description="Most active users"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_events": 5420,
                "events_today": 83,
                "events_this_week": 542,
                "events_this_month": 2156,
                "by_event_type": {"admin_user_create": 12, "admin_user_update": 45},
                "by_severity": {"info": 4200, "warning": 180, "error": 40},
                "most_active_users": [
                    {"user_email": "admin@example.com", "event_count": 320}
                ],
            }
        }
    )


# ============================================================================
# BULK OPERATIONS SCHEMAS
# ============================================================================


class BulkUpdateRequest(BaseModel):
    """Schema for bulk update operations."""

    user_ids: List[UUID] = Field(
        ..., min_length=1, max_length=100, description="List of user IDs to update"
    )
    updates: UserUpdateRequest = Field(..., description="Updates to apply")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_ids": ["uuid1", "uuid2", "uuid3"],
                "updates": {"is_active": False},
            }
        }
    )


class BulkDeleteRequest(BaseModel):
    """Schema for bulk delete operations."""

    user_ids: List[UUID] = Field(
        ..., min_length=1, max_length=50, description="List of user IDs to delete"
    )
    reason: Optional[str] = Field(
        None, max_length=500, description="Reason for bulk deletion"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_ids": ["uuid1", "uuid2"],
                "reason": "Account cleanup - inactive users",
            }
        }
    )


class BulkOperationResult(BaseModel):
    """Schema for bulk operation results."""

    success: bool = Field(..., description="Whether the operation succeeded")
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
                "errors": [{"user_id": "uuid1", "error": "User not found"}],
                "message": "Bulk operation completed with 1 error",
            }
        }
    )


class ExportFormat(BaseModel):
    """Schema for export format selection."""

    format: str = Field(..., description="Export format: csv or json")
    fields: Optional[List[str]] = Field(
        None, description="Fields to include (None = all)"
    )

    @field_validator("format")
    @classmethod
    def validate_format(cls, v):
        allowed_formats = ["csv", "json"]
        if v.lower() not in allowed_formats:
            raise ValueError(f"Format must be one of {allowed_formats}")
        return v.lower()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "format": "csv",
                "fields": ["id", "email", "full_name", "role", "is_active"],
            }
        }
    )


# ============================================================================
# SEARCH SCHEMAS
# ============================================================================


class UserSearchRequest(BaseModel):
    """Schema for advanced user search."""

    query: Optional[str] = Field(None, description="Search query (email, name)")
    role: Optional[str] = Field(None, description="Filter by role")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    created_after: Optional[datetime] = Field(
        None, description="Filter users created after"
    )
    created_before: Optional[datetime] = Field(
        None, description="Filter users created before"
    )
    last_login_after: Optional[datetime] = Field(
        None, description="Filter by last login after"
    )
    last_login_before: Optional[datetime] = Field(
        None, description="Filter by last login before"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "john",
                "role": "doctor",
                "is_active": True,
                "created_after": "2024-01-01T00:00:00Z",
            }
        }
    )
