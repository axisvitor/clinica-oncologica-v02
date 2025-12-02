"""
Pydantic schemas for user administration.

Contains all request/response models for user administration operations.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole


class UserCreateRequest(BaseModel):
    """Request model for creating a new user with enhanced validation."""
    model_config = ConfigDict(use_enum_values=True)

    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password must be 8-128 characters with mixed case, numbers, and symbols"
    )
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    role: UserRole = UserRole.DOCTOR
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    """Request model for updating a user."""
    model_config = ConfigDict(use_enum_values=True)

    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserPasswordUpdateRequest(BaseModel):
    """Request model for updating user password with validation."""
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password must be 8-128 characters with mixed case, numbers, and symbols"
    )
    confirm_password: str

    @field_validator('confirm_password')
    @classmethod
    def passwords_match(cls, v, info):
        """Ensure passwords match."""
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError('Passwords do not match')
        return v


class UserSearchFilters(BaseModel):
    """Search filters for user queries with enhanced options."""
    model_config = ConfigDict(use_enum_values=True)

    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    last_login_after: Optional[datetime] = None
    last_login_before: Optional[datetime] = None
    has_patients: Optional[bool] = None


class UserSummary(BaseModel):
    """Summary model for user data."""
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: UUID
    email: str
    full_name: Optional[str]
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Add computed fields
    total_patients: int = 0
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0


class PaginatedUsersResponse(BaseModel):
    """Paginated response for user listings."""
    users: List[UserSummary]
    total: int
    page: int
    per_page: int
    total_pages: int


class UserStatistics(BaseModel):
    """User statistics for dashboard."""
    total_users: int
    active_users: int
    inactive_users: int
    users_by_role: Dict[str, int]
    recent_registrations: int
    recent_logins: int


class PasswordResetRequest(BaseModel):
    """Request model for password reset."""
    user_id: UUID
    send_email: bool = True
    temporary_password_length: int = Field(default=12, ge=8, le=32)


class PasswordResetResult(BaseModel):
    """Result of password reset operation."""
    user_id: UUID
    temporary_password: Optional[str] = None
    reset_token: Optional[str] = None
    expires_at: datetime
    email_sent: bool = False


class BulkUserOperationRequest(BaseModel):
    """Request model for bulk user operations."""
    user_ids: List[UUID] = Field(..., min_length=1, max_length=100)
    operation: str = Field(..., pattern="^(activate|deactivate|delete)$")
    reason: Optional[str] = Field(None, max_length=500)


class BulkUserOperationResult(BaseModel):
    """Result of bulk user operation."""
    operation: str
    total_requested: int
    successful: List[UUID]
    failed: List[Dict[str, Any]]
    summary: str


class EmailValidationRequest(BaseModel):
    """Request model for email validation."""
    email: EmailStr
    check_mx: bool = True
    check_deliverability: bool = False


class EmailValidationResult(BaseModel):
    """Result of email validation."""
    email: str
    is_valid: bool
    normalized_email: str
    issues: List[str]
    suggestions: List[str]
