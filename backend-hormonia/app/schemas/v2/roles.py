"""
Roles & Permissions Management Schemas for API v2
Comprehensive schemas for role management, assignment, and validation.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict

from .common import CursorPaginatedResponse


# ============================================================================
# ROLE INFORMATION SCHEMAS
# ============================================================================

class RoleBase(BaseModel):
    """Base role information."""
    name: str = Field(..., description="Role name (ADMIN, DOCTOR)")
    value: str = Field(..., description="Role value")
    description: str = Field(..., description="Role description")
    permissions: List[str] = Field(..., description="List of permissions")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "ADMIN",
            "value": "admin",
            "description": "Full system access with user management capabilities",
            "permissions": ["user_management", "role_assignment", "system_configuration"]
        }
    })


class RoleResponse(BaseModel):
    """Role response with full details."""
    name: str = Field(..., description="Role name")
    value: str = Field(..., description="Role value")
    description: str = Field(..., description="Role description")
    permissions: List[str] = Field(..., description="List of permissions")
    user_count: Optional[int] = Field(None, description="Number of users with this role")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "DOCTOR",
            "value": "doctor",
            "description": "Medical professional with patient management access",
            "permissions": ["patient_management", "medical_records"],
            "user_count": 45
        }
    })


class RoleListResponse(BaseModel):
    """List of available roles."""
    data: List[RoleResponse] = Field(..., description="List of roles")
    total: int = Field(..., description="Total number of roles")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "data": [],
            "total": 2
        }
    })


# ============================================================================
# USER ROLE INFORMATION SCHEMAS
# ============================================================================

class UserRoleInfo(BaseModel):
    """User role information."""
    user_id: UUID = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    full_name: Optional[str] = Field(None, description="User full name")
    current_role: str = Field(..., description="Current user role")
    is_active: bool = Field(..., description="Whether user is active")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "doctor@example.com",
                "full_name": "Dr. Jane Smith",
                "current_role": "doctor",
                "is_active": True,
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-15T12:00:00Z",
                "last_login": "2025-01-15T10:30:00Z"
            }
        }
    )


class UserRoleListResponse(CursorPaginatedResponse[UserRoleInfo]):
    """Cursor-paginated user role list response."""
    pass


# ============================================================================
# ROLE ASSIGNMENT SCHEMAS
# ============================================================================

class RoleAssignmentRequest(BaseModel):
    """Request to assign a role to a user."""
    role: str = Field(..., description="Role to assign (admin, doctor)")
    reason: Optional[str] = Field(None, description="Reason for role assignment")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        allowed_roles = ['admin', 'doctor']
        if v.lower() not in allowed_roles:
            raise ValueError(f"Role must be one of {allowed_roles}")
        return v.lower()

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "role": "admin",
            "reason": "Promoted to admin for system management duties"
        }
    })


class RoleRevocationRequest(BaseModel):
    """Request to revoke a role from a user."""
    reason: Optional[str] = Field(None, description="Reason for role revocation")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "reason": "User changed departments"
        }
    })


class RoleAssignmentResponse(BaseModel):
    """Response after role assignment."""
    user_id: UUID = Field(..., description="User ID")
    previous_role: str = Field(..., description="Previous role")
    new_role: str = Field(..., description="New role")
    assigned_by: UUID = Field(..., description="Admin who assigned the role")
    assigned_at: datetime = Field(..., description="Assignment timestamp")
    reason: Optional[str] = Field(None, description="Reason for assignment")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "previous_role": "doctor",
            "new_role": "admin",
            "assigned_by": "660e8400-e29b-41d4-a716-446655440000",
            "assigned_at": "2025-01-15T12:00:00Z",
            "reason": "Promoted to admin"
        }
    })


# ============================================================================
# BULK ROLE ASSIGNMENT SCHEMAS
# ============================================================================

class BulkRoleAssignmentRequest(BaseModel):
    """Request to assign roles to multiple users."""
    user_ids: List[UUID] = Field(..., description="List of user IDs (max 50)")
    role: str = Field(..., description="Role to assign")
    reason: Optional[str] = Field(None, description="Reason for bulk assignment")

    @field_validator('user_ids')
    @classmethod
    def validate_user_ids(cls, v):
        if not v:
            raise ValueError("user_ids cannot be empty")
        if len(v) > 50:
            raise ValueError("Cannot assign roles to more than 50 users at once")
        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("user_ids contains duplicates")
        return v

    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        allowed_roles = ['admin', 'doctor']
        if v.lower() not in allowed_roles:
            raise ValueError(f"Role must be one of {allowed_roles}")
        return v.lower()

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "user_ids": [
                "550e8400-e29b-41d4-a716-446655440000",
                "660e8400-e29b-41d4-a716-446655440001"
            ],
            "role": "doctor",
            "reason": "Department restructuring"
        }
    })


class BulkRoleAssignmentResult(BaseModel):
    """Result of bulk role assignment."""
    success_count: int = Field(..., description="Number of successful assignments")
    failure_count: int = Field(..., description="Number of failed assignments")
    successful_users: List[UserRoleInfo] = Field(..., description="Successfully updated users")
    failed_users: List[Dict[str, Any]] = Field(..., description="Failed users with reasons")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success_count": 2,
            "failure_count": 0,
            "successful_users": [],
            "failed_users": []
        }
    })


# ============================================================================
# ROLE STATISTICS SCHEMAS
# ============================================================================

class RoleStatistics(BaseModel):
    """Role distribution and usage statistics."""
    total_users: int = Field(..., description="Total number of users")
    role_distribution: Dict[str, int] = Field(..., description="Users per role")
    active_users_by_role: Dict[str, int] = Field(..., description="Active users per role")
    inactive_users_by_role: Dict[str, int] = Field(..., description="Inactive users per role")
    role_changes_last_30_days: int = Field(default=0, description="Role changes in last 30 days")
    most_assigned_role: Optional[str] = Field(None, description="Most commonly assigned role")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "total_users": 100,
            "role_distribution": {
                "admin": 5,
                "doctor": 95
            },
            "active_users_by_role": {
                "admin": 5,
                "doctor": 90
            },
            "inactive_users_by_role": {
                "admin": 0,
                "doctor": 5
            },
            "role_changes_last_30_days": 12,
            "most_assigned_role": "doctor"
        }
    })


# ============================================================================
# ROLE PERMISSIONS SCHEMAS
# ============================================================================

class RolePermissions(BaseModel):
    """Detailed permissions for a specific role."""
    role: str = Field(..., description="Role name")
    permissions: List[str] = Field(..., description="List of permission strings")
    permission_groups: Dict[str, List[str]] = Field(..., description="Permissions grouped by category")
    description: str = Field(..., description="Role description")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "role": "admin",
            "permissions": [
                "user_management", "role_assignment", "system_configuration"
            ],
            "permission_groups": {
                "user_management": ["users.read", "users.write", "users.delete"],
                "system": ["settings.read", "settings.write"]
            },
            "description": "Full system access with user management capabilities"
        }
    })


# ============================================================================
# ROLE VALIDATION SCHEMAS
# ============================================================================

class RoleValidationRequest(BaseModel):
    """Request to validate a role assignment."""
    user_id: UUID = Field(..., description="User ID to validate")
    target_role: str = Field(..., description="Target role to validate")

    @field_validator('target_role')
    @classmethod
    def validate_role(cls, v):
        allowed_roles = ['admin', 'doctor']
        if v.lower() not in allowed_roles:
            raise ValueError(f"Role must be one of {allowed_roles}")
        return v.lower()

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "target_role": "admin"
        }
    })


class RoleValidationResponse(BaseModel):
    """Response from role validation."""
    valid: bool = Field(..., description="Whether the role assignment is valid")
    user_id: UUID = Field(..., description="User ID")
    current_role: Optional[str] = Field(None, description="User's current role")
    target_role: str = Field(..., description="Target role being validated")
    reason: Optional[str] = Field(None, description="Validation failure reason")
    message: str = Field(..., description="Human-readable message")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "valid": True,
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "current_role": "doctor",
            "target_role": "admin",
            "reason": None,
            "message": "Role assignment is valid",
            "warnings": []
        }
    })


# ============================================================================
# ROLE HIERARCHY SCHEMAS (For Future Enhancement)
# ============================================================================

class RoleHierarchy(BaseModel):
    """Role hierarchy information."""
    role: str = Field(..., description="Role name")
    level: int = Field(..., description="Hierarchy level (higher = more privileges)")
    can_manage_roles: List[str] = Field(..., description="Roles this role can manage")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "role": "admin",
            "level": 10,
            "can_manage_roles": ["admin", "doctor"]
        }
    })
