"""
Auth schemas for API v2
Enhanced authentication models with field selection and eager loading support.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict

from .common import CursorPaginatedResponse


# ============================================================================
# User Role & Permissions
# ============================================================================

class RoleV2Brief(BaseModel):
    """Brief role information for user response"""

    id: str
    name: str
    permissions: Optional[List[str]] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# User Preferences
# ============================================================================

class UserPreferencesV2(BaseModel):
    """User preferences schema for V2 API"""

    notification_email: bool = Field(True, description="Enable email notifications")
    notification_sms: bool = Field(True, description="Enable SMS notifications")
    notification_whatsapp: bool = Field(True, description="Enable WhatsApp notifications")
    language: str = Field("pt-BR", description="Preferred language (ISO 639-1)")
    timezone: str = Field("America/Sao_Paulo", description="User timezone (IANA)")
    theme: str = Field("light", description="UI theme preference")
    dashboard_widgets: Optional[Dict[str, Any]] = Field(None, description="Dashboard widget configuration")
    email_digest_frequency: str = Field("daily", description="Email digest frequency")
    data_sharing_consent: bool = Field(True, description="Data sharing consent")
    marketing_consent: bool = Field(False, description="Marketing communications consent")

    @field_validator("language")
    @classmethod
    def validate_language(cls, v):
        allowed = ["pt-BR", "en-US", "es-ES"]
        if v not in allowed:
            raise ValueError(f"Language must be one of: {', '.join(allowed)}")
        return v

    @field_validator("email_digest_frequency")
    @classmethod
    def validate_digest_frequency(cls, v):
        allowed = ["daily", "weekly", "monthly", "never"]
        if v not in allowed:
            raise ValueError(f"Frequency must be one of: {', '.join(allowed)}")
        return v

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v):
        allowed = ["light", "dark", "auto"]
        if v not in allowed:
            raise ValueError(f"Theme must be one of: {', '.join(allowed)}")
        return v

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "notification_email": True,
                "notification_sms": True,
                "notification_whatsapp": True,
                "language": "pt-BR",
                "timezone": "America/Sao_Paulo",
                "theme": "dark",
                "email_digest_frequency": "weekly",
                "data_sharing_consent": True,
                "marketing_consent": False
            }
        }
    )


class UserPreferencesV2Update(BaseModel):
    """Schema for partially updating user preferences"""

    notification_email: Optional[bool] = None
    notification_sms: Optional[bool] = None
    notification_whatsapp: Optional[bool] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    theme: Optional[str] = None
    dashboard_widgets: Optional[Dict[str, Any]] = None
    email_digest_frequency: Optional[str] = None
    data_sharing_consent: Optional[bool] = None
    marketing_consent: Optional[bool] = None

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "theme": "dark",
                "language": "en-US",
                "email_digest_frequency": "weekly"
            }
        }
    )


class UserPreferencesV2Response(BaseModel):
    """User preferences response with metadata"""

    user_id: str
    preferences: UserPreferencesV2
    updated_at: datetime

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "preferences": {
                    "notification_email": True,
                    "theme": "dark",
                    "language": "pt-BR"
                },
                "updated_at": "2025-11-07T10:30:00Z"
            }
        }
    )


# ============================================================================
# Notifications
# ============================================================================

class NotificationV2Response(BaseModel):
    """Notification response schema for V2 API"""

    id: str
    title: str = Field(..., max_length=200)
    message: str = Field(..., max_length=2000)
    type: str = Field(..., description="Notification type: info, warning, error, success")
    read: bool = Field(False, description="Read status")
    created_at: datetime
    updated_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional notification metadata")
    action_url: Optional[str] = Field(None, description="URL for notification action")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        allowed = ["info", "warning", "error", "success"]
        if v not in allowed:
            raise ValueError(f"Type must be one of: {', '.join(allowed)}")
        return v

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra = {
            "example": {
                "id": "notif_123abc",
                "title": "New message received",
                "message": "You have a new message from Dr. Silva",
                "type": "info",
                "read": False,
                "created_at": "2025-11-07T09:00:00Z",
                "action_url": "/messages/msg_456def"
            }
        }
    )


class NotificationV2List(CursorPaginatedResponse[NotificationV2Response]):
    """Paginated list of notifications with unread count"""

    unread_count: int = Field(0, description="Total unread notifications")

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "data": [
                    {
                        "id": "notif_123",
                        "title": "New message",
                        "message": "You have a new message",
                        "type": "info",
                        "read": False,
                        "created_at": "2025-11-07T09:00:00Z"
                    }
                ],
                "next_cursor": "eyJpZCI6Im5vdGlmXzEyMyJ9",
                "has_more": True,
                "total": 45,
                "unread_count": 12
            }
        }
    )


class NotificationMarkReadRequest(BaseModel):
    """Request to mark notification(s) as read"""

    notification_ids: List[str] = Field(..., min_length=1, max_length=100)

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "notification_ids": ["notif_123", "notif_456", "notif_789"]
            }
        }
    )


class NotificationMarkReadResponse(BaseModel):
    """Response after marking notifications as read"""

    marked_count: int = Field(..., description="Number of notifications marked as read")
    success: bool = True

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "marked_count": 3,
                "success": True
            }
        }
    )


# ============================================================================
# User Base Models
# ============================================================================

class UserV2Base(BaseModel):
    """Base user schema with common fields"""

    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=200)
    role: str = Field(..., description="User role: admin, doctor, patient, nurse")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        allowed = ["admin", "doctor", "patient", "nurse", "receptionist"]
        if v not in allowed:
            raise ValueError(f"Role must be one of: {', '.join(allowed)}")
        return v


class UserV2Create(UserV2Base):
    """Schema for creating a user (admin only)"""

    password: str = Field(..., min_length=8, max_length=128)
    is_active: bool = Field(True, description="Account active status")

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "email": "doctor@example.com",
                "full_name": "Dr. Maria Silva",
                "role": "doctor",
                "password": "SecureP@ssw0rd",
                "is_active": True
            }
        }
    )


class UserV2Update(BaseModel):
    """Schema for updating a user"""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=200)
    role: Optional[str] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "full_name": "Dr. Maria Silva Santos",
                "is_active": True
            }
        }
    )


class UserV2Response(UserV2Base):
    """Full user response with optional relationships"""

    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")

    # Optional eager-loaded relationships
    role_details: Optional[RoleV2Brief] = Field(None, description="Detailed role information")
    preferences: Optional[UserPreferencesV2] = Field(None, description="User preferences")

    # Computed fields
    patient_count: Optional[int] = Field(None, description="Number of patients (for doctors)")
    notification_count: Optional[int] = Field(None, description="Unread notification count")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "doctor@example.com",
                "full_name": "Dr. Maria Silva",
                "role": "doctor",
                "is_active": True,
                "created_at": "2025-01-01T10:00:00Z",
                "updated_at": "2025-11-07T09:00:00Z",
                "last_login": "2025-11-07T08:30:00Z",
                "patient_count": 45,
                "notification_count": 3
            }
        }
    )


class UserV2List(CursorPaginatedResponse[UserV2Response]):
    """Paginated list of users"""

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "data": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "email": "doctor@example.com",
                        "full_name": "Dr. Maria Silva",
                        "role": "doctor",
                        "is_active": True,
                        "created_at": "2025-01-01T10:00:00Z",
                        "updated_at": "2025-11-07T09:00:00Z"
                    }
                ],
                "next_cursor": "eyJpZCI6IjEyM2U0NTY3In0=",
                "has_more": True,
                "total": 120
            }
        }
    )


# ============================================================================
# Session Management
# ============================================================================

class SessionV2Response(BaseModel):
    """Active session information"""

    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_current: bool = Field(False, description="Whether this is the current session")
    valid: bool = Field(True, description="Session validity status")
    user: Optional["UserV2Response"] = None

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "session_id": "sess_abc123def456",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "created_at": "2025-11-07T08:00:00Z",
                "expires_at": "2025-11-08T08:00:00Z",
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0...",
                "is_current": True
            }
        }
    )


class SessionV2List(BaseModel):
    """List of active sessions"""

    sessions: List[SessionV2Response]
    total: int

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "sessions": [
                    {
                        "session_id": "sess_abc123",
                        "user_id": "123e4567-e89b-12d3-a456-426614174000",
                        "created_at": "2025-11-07T08:00:00Z",
                        "is_current": True
                    }
                ],
                "total": 1
            }
        }
    )


class SessionRevokeRequest(BaseModel):
    """Request to revoke a session"""

    session_id: str = Field(..., description="Session ID to revoke")

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "session_id": "sess_abc123def456"
            }
        }
    )


class SessionRevokeResponse(BaseModel):
    """Response after revoking a session"""

    session_id: str
    revoked: bool = True
    message: str = "Session revoked successfully"

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "session_id": "sess_abc123",
                "revoked": True,
                "message": "Session revoked successfully"
            }
        }
    )


# ============================================================================
# Authentication (Firebase-based)
# ============================================================================

class FirebaseTokenVerifyRequest(BaseModel):
    """Request to verify Firebase ID token"""

    id_token: str = Field(..., description="Firebase ID token from client")

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "id_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjFlOWdkazcifQ..."
            }
        }
    )


class FirebaseTokenVerifyResponse(BaseModel):
    """Response after verifying Firebase token"""

    valid: bool
    # user: Optional[UserV2Response] = None
    session_id: Optional[str] = None
    message: Optional[str] = None

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "valid": True,
                "user": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "email": "doctor@example.com",
                    "full_name": "Dr. Maria Silva",
                    "role": "doctor"
                },
                "session_id": "sess_abc123"
            }
        }
    )


# ============================================================================
# Password Management (Legacy - Firebase handles this)
# ============================================================================

class PasswordChangeRequest(BaseModel):
    """Request to change password"""

    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v):
            raise ValueError("Password must contain at least one special character")
        return v

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "current_password": "OldP@ssw0rd",
                "new_password": "NewSecureP@ssw0rd123"
            }
        }
    )


class PasswordResetRequest(BaseModel):
    """Request to reset password (send email)"""

    email: EmailStr

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "email": "doctor@example.com"
            }
        }
    )


class PasswordResetConfirm(BaseModel):
    """Confirm password reset with token"""

    token: str = Field(..., description="Reset token from email")
    new_password: str = Field(..., min_length=8, max_length=128)

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "token": "reset_token_abc123",
                "new_password": "NewSecureP@ssw0rd123"
            }
        }
    )
