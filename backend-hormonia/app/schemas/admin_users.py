"""
Pydantic schemas for admin user management.

This module contains comprehensive schemas for managing users in the admin interface,
including creation, updates, responses, filtering, and specialized operations.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
import enum

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from app.schemas.common import PaginatedResponse


class UserRole(str, enum.Enum):
    """User role enumeration for admin management."""

    ADMIN = "admin"
    DOCTOR = "doctor"


# Core User Schemas

class UserCreate(BaseModel):
    """Schema for creating a new user."""
    name: str = Field(..., min_length=2, max_length=255, description="Full name of the user")
    email: EmailStr = Field(..., description="Email address (must be unique)")
    password: str = Field(..., min_length=8, max_length=128, description="Password (minimum 8 characters)")
    role: UserRole = Field(default=UserRole.DOCTOR, description="User role")
    phone_number: Optional[str] = Field(None, max_length=20, description="Phone number (optional)")

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c.isalpha() for c in v):
            raise ValueError('Password must contain at least one letter')
        return v

    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v):
        """Validate phone number format."""
        if v is not None:
            # Remove common phone number characters for validation
            cleaned = ''.join(c for c in v if c.isdigit() or c in '+()-. ')
            if len(cleaned.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('+', '')) < 10:
                raise ValueError('Phone number must contain at least 10 digits')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Dr. João Silva",
                "email": "joao.silva@clinica.com",
                "password": "SecurePass123",
                "role": "doctor",
                "phone_number": "+55 11 99999-9999"
            }
        }


class UserUpdate(BaseModel):
    """Schema for updating user information."""
    name: Optional[str] = Field(None, min_length=2, max_length=255, description="Full name of the user")
    email: Optional[EmailStr] = Field(None, description="Email address (must be unique)")
    role: Optional[UserRole] = Field(None, description="User role")
    phone_number: Optional[str] = Field(None, max_length=20, description="Phone number")
    is_active: Optional[bool] = Field(None, description="Whether the user is active")

    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v):
        """Validate phone number format."""
        if v is not None:
            # Remove common phone number characters for validation
            cleaned = ''.join(c for c in v if c.isdigit() or c in '+()-. ')
            if len(cleaned.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('+', '')) < 10:
                raise ValueError('Phone number must contain at least 10 digits')
        return v

    @model_validator(mode='after')
    def validate_at_least_one_field(self):
        """Ensure at least one field is provided for update."""
        if not any(getattr(self, field) is not None for field in self.model_fields):
            raise ValueError('At least one field must be provided for update')
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Dr. João Silva Santos",
                "email": "joao.santos@clinica.com",
                "role": "admin",
                "phone_number": "+55 11 88888-8888",
                "is_active": True
            }
        }


class UserResponse(BaseModel):
    """Schema for user response (excludes password)."""
    id: UUID = Field(..., description="User unique identifier")
    name: Optional[str] = Field(None, description="Full name of the user")
    email: str = Field(..., description="Email address")
    role: UserRole = Field(..., description="User role")
    phone_number: Optional[str] = Field(None, description="Phone number")
    is_active: bool = Field(..., description="Whether the user is active")
    created_at: datetime = Field(..., description="User creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    # Computed fields
    total_patients: Optional[int] = Field(None, description="Total patients for doctors")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Dr. João Silva",
                "email": "joao.silva@clinica.com",
                "role": "doctor",
                "phone_number": "+55 11 99999-9999",
                "is_active": True,
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
                "total_patients": 25,
                "last_login": "2024-01-20T14:30:00Z"
            }
        }


class UserListResponse(PaginatedResponse):
    """Schema for paginated user list response."""
    data: List[UserResponse] = Field(..., description="List of users")

    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "name": "Dr. João Silva",
                        "email": "joao.silva@clinica.com",
                        "role": "doctor",
                        "phone_number": "+55 11 99999-9999",
                        "is_active": True,
                        "created_at": "2024-01-15T10:30:00Z",
                        "updated_at": "2024-01-15T10:30:00Z",
                        "total_patients": 25,
                        "last_login": "2024-01-20T14:30:00Z"
                    }
                ],
                "total": 150,
                "skip": 0,
                "limit": 20,
                "has_next": True,
                "has_previous": False
            }
        }


# Specialized Update Schemas

class RoleUpdate(BaseModel):
    """Schema for updating user role."""
    role: UserRole = Field(..., description="New role to assign to the user")

    class Config:
        json_schema_extra = {
            "example": {
                "role": "admin"
            }
        }


class PermissionsUpdate(BaseModel):
    """Schema for updating user permissions."""
    permissions: List[str] = Field(..., description="List of permissions to assign")

    @field_validator('permissions')
    @classmethod
    def validate_permissions(cls, v):
        """Validate permissions list."""
        if not v:
            raise ValueError('At least one permission must be provided')

        # Define valid permissions
        valid_permissions = [
            'read_patients', 'write_patients', 'delete_patients',
            'read_reports', 'write_reports', 'delete_reports',
            'read_users', 'write_users', 'delete_users',
            'read_analytics', 'write_analytics',
            'manage_system', 'audit_logs'
        ]

        for permission in v:
            if permission not in valid_permissions:
                raise ValueError(f'Invalid permission: {permission}')

        return v

    class Config:
        json_schema_extra = {
            "example": {
                "permissions": [
                    "read_patients",
                    "write_patients",
                    "read_reports",
                    "write_reports"
                ]
            }
        }


class PasswordReset(BaseModel):
    """Schema for resetting user password."""
    new_password: str = Field(..., min_length=8, max_length=128, description="New password (minimum 8 characters)")

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v):
        """Validate new password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c.isalpha() for c in v):
            raise ValueError('Password must contain at least one letter')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "new_password": "NewSecurePass123"
            }
        }


# Filtering and Search Schemas

class UserFilter(BaseModel):
    """Schema for filtering users in list endpoints."""
    name: Optional[str] = Field(None, description="Filter by name (partial match)")
    email: Optional[str] = Field(None, description="Filter by email (partial match)")
    role: Optional[UserRole] = Field(None, description="Filter by specific role")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    phone_number: Optional[str] = Field(None, description="Filter by phone number (partial match)")
    created_after: Optional[datetime] = Field(None, description="Filter users created after this date")
    created_before: Optional[datetime] = Field(None, description="Filter users created before this date")
    has_patients: Optional[bool] = Field(None, description="Filter doctors by whether they have patients")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "João",
                "role": "doctor",
                "is_active": True,
                "created_after": "2024-01-01T00:00:00Z",
                "has_patients": True
            }
        }


# Additional Response Schemas

class UserStatsResponse(BaseModel):
    """Schema for user statistics response."""
    total_users: int = Field(..., description="Total number of users")
    active_users: int = Field(..., description="Number of active users")
    inactive_users: int = Field(..., description="Number of inactive users")
    users_by_role: Dict[str, int] = Field(..., description="User count by role")
    recent_registrations: int = Field(..., description="Recent registrations count")
    recent_logins: int = Field(..., description="Recent logins count")

    class Config:
        json_schema_extra = {
            "example": {
                "total_users": 150,
                "active_users": 142,
                "inactive_users": 8,
                "users_by_role": {

                    "admin": 15,
                    "doctor": 90,
                    "nurse": 25,
                    "patient": 1200,
                    "researcher": 8,
                    "coordinator": 12
                },
                "recent_registrations": 12,
                "recent_logins": 89
            }
        }


class UserActivityResponse(BaseModel):
    """Schema for user activity response."""
    user_id: UUID = Field(..., description="User identifier")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    login_count: int = Field(0, description="Total login count")
    last_activity: Optional[datetime] = Field(None, description="Last activity timestamp")
    active_sessions: int = Field(0, description="Number of active sessions")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "last_login": "2024-01-20T14:30:00Z",
                "login_count": 45,
                "last_activity": "2024-01-20T16:45:00Z",
                "active_sessions": 1
            }
        }


class BulkUserOperation(BaseModel):
    """Schema for bulk user operations."""
    user_ids: List[UUID] = Field(..., min_length=1, max_length=100, description="List of user IDs (max 100)")
    operation: str = Field(..., description="Operation to perform (activate, deactivate, delete)")

    @field_validator('operation')
    @classmethod
    def validate_operation(cls, v):
        """Validate operation type."""
        valid_operations = ['activate', 'deactivate', 'delete']
        if v not in valid_operations:
            raise ValueError(f'Invalid operation. Must be one of: {valid_operations}')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "user_ids": [
                    "123e4567-e89b-12d3-a456-426614174000",
                    "456e7890-e89b-12d3-a456-426614174001"
                ],
                "operation": "activate"
            }
        }


class BulkOperationResult(BaseModel):
    """Schema for bulk operation results."""
    successful: List[UUID] = Field(..., description="Successfully processed user IDs")
    failed: List[Dict[str, Any]] = Field(..., description="Failed operations with error details")
    total_processed: int = Field(..., description="Total number of users processed")

    class Config:
        json_schema_extra = {
            "example": {
                "successful": [
                    "123e4567-e89b-12d3-a456-426614174000"
                ],
                "failed": [
                    {
                        "user_id": "456e7890-e89b-12d3-a456-426614174001",
                        "error": "User not found"
                    }
                ],
                "total_processed": 2
            }
        }


# Export all schemas
__all__ = [
    "UserRole",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserListResponse",
    "RoleUpdate",
    "PermissionsUpdate",
    "PasswordReset",
    "UserFilter",
    "UserStatsResponse",
    "UserActivityResponse",
    "BulkUserOperation",
    "BulkOperationResult"
]