"""
Audit Log Model for tracking critical security events.

This model stores authentication and security-related events for compliance,
security monitoring, and forensic analysis.

Events tracked:
- Authentication (login, logout, token refresh)
- Authorization (access denied, permission changes)
- Account management (password change, account lock, unlock)
- Session management (session created, expired, invalidated)
"""
from sqlalchemy import Column, String, Text, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, INET, UUID
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class AuditEventType(str, enum.Enum):
    """Audit event types for security tracking."""
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    SESSION_CREATED = "session_created"
    SESSION_EXPIRED = "session_expired"
    SESSION_INVALIDATED = "session_invalidated"
    TOKEN_REFRESH = "token_refresh"

    # Authorization events
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGED = "permission_changed"
    ROLE_CHANGED = "role_changed"

    # Account management events
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    ACCOUNT_DISABLED = "account_disabled"
    ACCOUNT_ENABLED = "account_enabled"

    # Profile events
    PROFILE_UPDATED = "profile_updated"
    EMAIL_CHANGED = "email_changed"

    # Security events
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_TOKEN = "invalid_token"
    CSRF_VIOLATION = "csrf_violation"


class AuditLog(BaseModel):
    """
    Audit log model for security event tracking.

    Stores comprehensive information about security events including:
    - User identity
    - Event type and status
    - Network information (IP, user agent)
    - Additional context in metadata
    """
    __tablename__ = "audit_logs"

    # Event information
    event_type = Column(
        SQLEnum(AuditEventType, name='audit_event_type', native_enum=True),
        nullable=False,
        index=True,
        comment="Type of security event"
    )
    event_status = Column(
        String(50),
        nullable=False,
        default="success",
        comment="Event outcome: success, failure, error"
    )

    # User identification
    user_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="User ID (may be null for failed login attempts)"
    )
    user_email = Column(
        String(255),
        nullable=True,
        index=True,
        comment="User email (for tracking failed login attempts)"
    )
    firebase_uid = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Firebase UID for Firebase-authenticated users"
    )

    # Network information
    ip_address = Column(
        INET,
        nullable=True,
        index=True,
        comment="Client IP address"
    )
    user_agent = Column(
        Text,
        nullable=True,
        comment="Client user agent string"
    )

    # Event details
    resource = Column(
        String(255),
        nullable=True,
        comment="Resource accessed (endpoint, action)"
    )
    action = Column(
        String(255),
        nullable=True,
        comment="Action performed"
    )

    # Additional context
    event_metadata = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Additional event metadata (device info, session ID, etc.)"
    )

    # Result information
    message = Column(
        Text,
        nullable=True,
        comment="Human-readable event description"
    )
    error_details = Column(
        Text,
        nullable=True,
        comment="Error details for failed events"
    )

    # Performance indexes
    __table_args__ = (
        # Composite index for user activity queries
        Index('idx_audit_user_event_time', 'user_id', 'event_type', 'created_at'),

        # Index for security monitoring queries
        Index('idx_audit_ip_time', 'ip_address', 'created_at'),

        # Index for event type filtering with time range
        Index('idx_audit_event_status_time', 'event_type', 'event_status', 'created_at'),

        # Index for Firebase UID lookups
        Index('idx_audit_firebase_time', 'firebase_uid', 'created_at'),

        # Index for email-based queries (failed login tracking)
        Index('idx_audit_email_time', 'user_email', 'created_at'),
    )

    def __repr__(self):
        return (
            f"<AuditLog("
            f"event_type='{self.event_type.value}', "
            f"user_id='{self.user_id}', "
            f"ip_address='{self.ip_address}', "
            f"created_at='{self.created_at}'"
            f")>"
        )

    @property
    def is_failure(self) -> bool:
        """Check if event represents a failure."""
        return self.event_status in ['failure', 'error']

    @property
    def is_authentication_event(self) -> bool:
        """Check if event is authentication-related."""
        auth_events = {
            AuditEventType.LOGIN_SUCCESS,
            AuditEventType.LOGIN_FAILURE,
            AuditEventType.LOGOUT,
            AuditEventType.SESSION_CREATED,
            AuditEventType.TOKEN_REFRESH,
        }
        return self.event_type in auth_events

    @property
    def is_security_event(self) -> bool:
        """Check if event represents a security concern."""
        security_events = {
            AuditEventType.SUSPICIOUS_ACTIVITY,
            AuditEventType.RATE_LIMIT_EXCEEDED,
            AuditEventType.INVALID_TOKEN,
            AuditEventType.CSRF_VIOLATION,
            AuditEventType.ACCESS_DENIED,
        }
        return self.event_type in security_events
