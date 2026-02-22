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

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, INET, UUID
from sqlalchemy.orm import synonym, validates
from sqlalchemy.sql import func
from uuid import UUID as UUIDType
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

    # Admin events
    ADMIN_USER_CREATE = "admin_user_create"
    ADMIN_USER_UPDATE = "admin_user_update"
    ADMIN_USER_DELETE = "admin_user_delete"
    ADMIN_DLQ_RETRY = "admin_dlq_retry"
    ADMIN_DLQ_PURGE = "admin_dlq_purge"
    ADMIN_AUDIT_EXPORT = "admin_audit_export"

    # AI events (LGPD-03 — audit trail for Gemini/LangGraph processing)
    AI_QUERY = "ai_query"
    AI_HUMANIZATION = "ai_humanization"
    AI_SENTIMENT = "ai_sentiment"
    AI_FOLLOW_UP = "ai_follow_up"


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
        SQLEnum(AuditEventType, name="audit_event_type", native_enum=True),
        nullable=False,
        index=True,
        comment="Type of security event",
    )
    event_category = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Event category (AUTHENTICATION, PHI_ACCESS, ADMIN, etc.)",
    )
    event_status = Column(
        String(50),
        nullable=False,
        default="success",
        comment="Event outcome: success, failure, error",
    )
    status = Column(
        String(20),
        nullable=True,
        default="SUCCESS",
        comment="HIPAA status (SUCCESS, FAILURE, ERROR, BLOCKED)",
    )

    # User identification
    user_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="User ID (may be null for failed login attempts)",
    )
    user_email = Column(
        String(255),
        nullable=True,
        index=True,
        comment="User email (for tracking failed login attempts)",
    )
    user_role = Column(String(50), nullable=True, comment="User role at event time")
    firebase_uid = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Firebase UID for Firebase-authenticated users",
    )

    # Session tracking
    session_id = Column(String(255), nullable=True, comment="Session identifier")
    session_token_hash = Column(
        String(64), nullable=True, comment="Hashed session token"
    )
    device_fingerprint = Column(
        String(64), nullable=True, comment="Client device fingerprint"
    )
    geolocation = Column(JSONB, nullable=True, comment="Geo location payload")

    # Network information
    ip_address = Column(INET, nullable=True, index=True, comment="Client IP address")
    user_agent = Column(Text, nullable=True, comment="Client user agent string")

    # Event details
    resource = Column(
        String(255), nullable=True, comment="Resource accessed (endpoint, action)"
    )
    action = Column(String(255), nullable=True, comment="Action performed")
    resource_type = Column(String(50), nullable=True, comment="Resource type")
    resource_id = Column(UUID(as_uuid=True), nullable=True, comment="Resource ID")
    resource_identifiers = Column(
        JSONB, nullable=True, comment="Additional resource identifiers"
    )

    operation = Column(
        String(20), nullable=True, comment="Operation type (CREATE, READ, UPDATE, etc.)"
    )
    http_method = Column(String(10), nullable=True, comment="HTTP method")
    endpoint = Column(String(500), nullable=True, comment="Request endpoint")

    # Additional context
    event_metadata = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Additional event metadata (device info, session ID, etc.)",
    )
    query_params = Column(JSONB, nullable=True, comment="Query parameters payload")
    request_body_hash = Column(String(64), nullable=True, comment="Request body hash")

    # Change tracking
    changes_before = Column(JSONB, nullable=True, comment="State before change")
    changes_after = Column(JSONB, nullable=True, comment="State after change")
    changed_fields = Column(ARRAY(Text), nullable=True, comment="Fields changed")
    description = Column(Text, nullable=True, comment="Event description")

    # Result information
    message = Column(Text, nullable=True, comment="Human-readable event description")
    error_details = Column(
        Text, nullable=True, comment="Error details for failed events"
    )
    http_status_code = Column(Integer, nullable=True, comment="HTTP status code")
    error_code = Column(String(50), nullable=True, comment="Error code")
    error_stack_trace = Column(Text, nullable=True, comment="Error stack trace")
    duration_ms = Column(Integer, nullable=True, comment="Duration in milliseconds")

    # Integrity & review
    checksum = Column(String(64), nullable=True, comment="Integrity checksum")
    previous_checksum = Column(String(64), nullable=True, comment="Previous checksum")
    integrity_verified = Column(
        Boolean, nullable=True, default=True, comment="Integrity verification status"
    )
    reviewed = Column(Boolean, nullable=True, default=False, comment="Reviewed flag")
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(UUID(as_uuid=True), nullable=True)
    review_notes = Column(Text, nullable=True)

    # Anomaly detection
    is_anomalous = Column(
        Boolean, nullable=True, default=False, comment="Anomaly detection flag"
    )
    anomaly_score = Column(Numeric(5, 2), nullable=True)
    anomaly_reasons = Column(ARRAY(Text), nullable=True)

    # Alert generation
    alert_generated = Column(Boolean, nullable=True, default=False)
    alert_sent_at = Column(DateTime(timezone=True), nullable=True)
    alert_recipients = Column(ARRAY(Text), nullable=True)

    # Retention & archival
    retention_period_years = Column(Integer, nullable=True, default=6)
    archive_eligible_at = Column(DateTime(timezone=True), nullable=True)
    archived = Column(Boolean, nullable=True, default=False)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    archive_location = Column(String(500), nullable=True)

    # Convenience aliases for legacy/admin schemas
    event_data = synonym("event_metadata")
    result = synonym("event_status")
    timestamp = synonym("created_at")

    def __init__(self, **kwargs):
        metadata_payload = kwargs.pop("metadata", None)
        event_data = kwargs.pop("event_data", None)

        if event_data is not None and "event_metadata" not in kwargs:
            kwargs["event_metadata"] = event_data

        if metadata_payload is not None:
            merged = dict(kwargs.get("event_metadata") or {})
            merged.update(metadata_payload)
            kwargs["event_metadata"] = merged

        super().__init__(**kwargs)

    # Performance indexes
    __table_args__ = (
        # Composite index for user activity queries
        Index("idx_audit_user_event_time", "user_id", "event_type", "created_at"),
        # Index for security monitoring queries
        Index("idx_audit_ip_time", "ip_address", "created_at"),
        # Index for event type filtering with time range
        Index(
            "idx_audit_event_status_time", "event_type", "event_status", "created_at"
        ),
        # Index for Firebase UID lookups
        Index("idx_audit_firebase_time", "firebase_uid", "created_at"),
        # Index for email-based queries (failed login tracking)
        Index("idx_audit_email_time", "user_email", "created_at"),
    )

    def __repr__(self):
        event_type = (
            self.event_type.value
            if hasattr(self.event_type, "value")
            else str(self.event_type)
        )
        return (
            f"<AuditLog("
            f"event_type='{event_type}', "
            f"user_id='{self.user_id}', "
            f"ip_address='{self.ip_address}', "
            f"created_at='{self.created_at}'"
            f")>"
        )

    @property
    def severity(self) -> str:
        """Expose severity from metadata for admin schemas."""
        metadata = self.event_metadata or {}
        return metadata.get("severity", "info")

    @severity.setter
    def severity(self, value: str) -> None:
        metadata = dict(self.event_metadata or {})
        metadata["severity"] = value
        self.event_metadata = metadata

    @validates("event_metadata")
    def _normalize_event_metadata(self, key, value):
        return value or {}

    @validates("event_type")
    def _normalize_event_type(self, key, value):
        if isinstance(value, AuditEventType):
            return value
        if isinstance(value, str):
            try:
                return AuditEventType(value)
            except ValueError:
                return value
        return value

    @validates("user_id", "resource_id")
    def _normalize_uuid_fields(self, key, value):
        if value is None or isinstance(value, UUIDType):
            return value
        if isinstance(value, str):
            return UUIDType(value)
        return value

    @property
    def is_failure(self) -> bool:
        """Check if event represents a failure."""
        return self.event_status in ["failure", "error"]

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
