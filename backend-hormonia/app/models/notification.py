"""
Notification model for system notifications.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.patient import Patient


class NotificationType(str, enum.Enum):
    """Notification type enumeration."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"
    ALERT = "alert"
    REMINDER = "reminder"


class NotificationPriority(str, enum.Enum):
    """Notification priority enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Notification(BaseModel):
    """
    Notification model representing system notifications.

    Relationships (configured for eager loading):
    - user: Many-to-one with User (selectinload)
    - related_patient: Many-to-one with Patient (selectinload)
    """
    __tablename__ = "notifications"

    # Foreign Keys
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    related_patient_id = Column(PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=True, index=True)

    # Notification Details
    notification_type = Column(SQLEnum(NotificationType), nullable=False, index=True)
    priority = Column(SQLEnum(NotificationPriority), nullable=False, default=NotificationPriority.MEDIUM, index=True)

    # Content
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    action_url = Column(String(500), nullable=True)
    action_label = Column(String(100), nullable=True)

    # Metadata (renamed from 'metadata' to avoid SQLAlchemy reserved name conflict)
    notification_metadata = Column(JSONB, nullable=True)

    # Status
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    is_archived = Column(Boolean, default=False, nullable=False, index=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships (optimized for eager loading)
    user = relationship("User", back_populates="notifications", lazy="select")
    related_patient = relationship("Patient", back_populates="notifications", lazy="select")

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, user_id={self.user_id}, type={self.notification_type}, is_read={self.is_read}, title={self.title[:30]})>"
