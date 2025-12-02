"""
User management schemas for admin operations.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict

from app.models.admin import SystemStatsResponse as AdminSystemStatsResponse


class UserCreateRequest(BaseModel):
    """Schema for creating a new user."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password (minimum 8 characters)")
    full_name: str = Field(..., min_length=2, max_length=255, description="User's full name")
    role: str = Field(..., description="User role: admin, doctor")
    is_active: bool = Field(default=True, description="Whether the user is active")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        allowed_roles = ['admin', 'doctor']
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of {allowed_roles}")
        return v

    @field_validator('password')
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


class UserUpdateRequest(BaseModel):
    """Schema for updating user information."""
    email: Optional[EmailStr] = Field(None, description="User email address")
    full_name: Optional[str] = Field(None, min_length=2, max_length=255, description="User's full name")
    role: Optional[str] = Field(None, description="User role: admin, doctor")
    is_active: Optional[bool] = Field(None, description="Whether the user is active")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        if v is None:
            return v
        allowed_roles = ['admin', 'doctor']
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of {allowed_roles}")
        return v


class UserRoleUpdateRequest(BaseModel):
    """Schema for updating user role."""
    role: str = Field(..., description="New user role: admin, doctor")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        allowed_roles = ['admin', 'doctor']
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of {allowed_roles}")
        return v


class UserPermissionsUpdateRequest(BaseModel):
    """Schema for updating user permissions."""
    permissions: List[str] = Field(..., description="List of permission names")


class UserResetPasswordRequest(BaseModel):
    """Schema for resetting user password."""
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")
    force_change: bool = Field(default=True, description="Force user to change password on next login")

    @field_validator('new_password')
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

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    """Schema for paginated user list response."""
    items: List[UserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_previous: bool = Field(..., description="Whether there are previous pages")


class UserFilterParams(BaseModel):
    """Schema for user list filtering parameters."""
    role: Optional[str] = Field(None, description="Filter by role")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    search: Optional[str] = Field(None, description="Search in email and full_name")
    created_after: Optional[datetime] = Field(None, description="Filter users created after this date")
    created_before: Optional[datetime] = Field(None, description="Filter users created before this date")


class UserStatsResponse(BaseModel):
    """Schema for user statistics."""
    total_users: int = Field(..., description="Total number of users")
    active_users: int = Field(..., description="Number of active users")
    inactive_users: int = Field(..., description="Number of inactive users")
    by_role: dict = Field(..., description="User count by role")
    recent_registrations: int = Field(..., description="Registrations in the last 30 days")


class UserActionResponse(BaseModel):
    """Schema for user action responses."""
    success: bool = Field(..., description="Whether the action was successful")
    message: str = Field(..., description="Action result message")
    user_id: UUID = Field(..., description="Affected user ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Action timestamp")


class UserActivityRecord(BaseModel):
    """Schema for individual user activity record."""
    id: str = Field(..., description="Activity record ID")
    user_id: str = Field(..., description="User ID")
    user_email: Optional[str] = Field(None, description="User email")
    action: str = Field(..., description="Action performed")
    resource: str = Field(..., description="Resource affected")
    resource_id: Optional[str] = Field(None, description="Resource ID")
    details: dict = Field(default_factory=dict, description="Activity details")
    timestamp: datetime = Field(..., description="Activity timestamp")
    ip_address: str = Field(..., description="IP address")
    user_agent: Optional[str] = Field(None, description="User agent")

    model_config = ConfigDict(from_attributes=True)


class UserActivityResponse(BaseModel):
    """Schema for paginated user activity response."""
    items: List[UserActivityRecord] = Field(..., description="Activity records")
    total: int = Field(..., description="Total number of records")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_previous: bool = Field(..., description="Whether there is a previous page")

    model_config = ConfigDict(from_attributes=True)


# Backward compatibility aliases for V1 tests
SystemStatsResponse = AdminSystemStatsResponse
UserPermissionsUpdate = UserPermissionsUpdateRequest
