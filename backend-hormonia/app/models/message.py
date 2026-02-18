"""
Message model for WhatsApp communication.
"""

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
    Integer,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum
from uuid import uuid4

from app.models.base import BaseModel


class MessageDirection(str, enum.Enum):
    """Message direction enumeration."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageType(str, enum.Enum):
    """Message type enumeration."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    BUTTON = "button"
    LIST = "list"
    MEDIA = "media"
    LOCATION = "location"
    QUIZ_INTRO = "quiz_intro"
    QUIZ_QUESTION = "quiz_question"
    QUIZ_ENCOURAGEMENT = "quiz_encouragement"
    QUIZ_COMPLETION = "quiz_completion"
    # Monthly quiz link types
    MONTHLY_QUIZ_LINK = "monthly_quiz_link"
    MONTHLY_QUIZ_REMINDER = "monthly_quiz_reminder"
    MONTHLY_QUIZ_EXPIRED = "monthly_quiz_expired"
    MONTHLY_QUIZ_COMPLETED = "monthly_quiz_completed"


class MessageStatus(str, enum.Enum):
    """Message status enumeration."""

    PENDING = "pending"
    SCHEDULED = "scheduled"
    SENDING = "sending"  # Message is being sent by Celery worker
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeliveryStatus(str, enum.Enum):
    """Detailed delivery status tracking for WhatsApp messages."""

    SCHEDULED = "scheduled"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessagePriority(str, enum.Enum):
    """Message priority levels for scheduling and rate limiting."""

    CRITICAL = "critical"
    HIGH = "high"
    URGENT = "high"  # Legacy alias kept for backward compatibility
    NORMAL = "normal"
    LOW = "low"


class Message(BaseModel):
    """Message model for WhatsApp communication."""

    __tablename__ = "messages"

    # Patient reference
    patient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Message details
    direction = Column(
        SAEnum(
            MessageDirection,
            name="message_direction",
            native_enum=True,
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
            validate_strings=True,
        ),
        nullable=False,
    )
    type = Column(
        SAEnum(
            MessageType,
            name="messagetype",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            validate_strings=True,
        ),
        default=MessageType.TEXT,
        nullable=False,
    )
    content = Column(Text, nullable=True)

    # Metadata for buttons, media URLs, etc.
    message_metadata = Column(JSONB, nullable=True, default=dict)

    priority = Column(
        SAEnum(
            MessagePriority,
            name="message_priority",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            validate_strings=True,
        ),
        nullable=False,
        default=MessagePriority.NORMAL,
    )

    # CRITICAL FIX #5: Idempotency key to prevent duplicate sends
    # Unique per (patient_id, idempotency_key) - enforced by database constraint
    idempotency_key = Column(
        String(255),
        nullable=False,
        default=lambda: uuid4().hex,
        index=True,
        comment="Idempotency key to prevent duplicate message sends",
    )

    # WhatsApp integration
    whatsapp_id = Column(String(255), nullable=True, index=True)
    status = Column(
        SAEnum(
            MessageStatus,
            name="message_status",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            validate_strings=True,
        ),
        default=MessageStatus.PENDING,
        nullable=False,
    )

    # Scheduling and delivery tracking
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    # Delivery status tracking (new fields for P1 fix)
    delivery_status = Column(
        SAEnum(
            DeliveryStatus,
            name="message_delivery_status",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            validate_strings=True,
        ),
        nullable=True,
    )
    retry_count = Column(Integer, nullable=False, default=0)
    last_retry_at = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(Text, nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    patient = relationship("Patient", back_populates="messages", passive_deletes=True)
    status_events = relationship(
        "MessageStatusEvent",
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="MessageStatusEvent.created_at",
    )

    @property
    def sender_id(self):
        """
        Legacy compatibility alias.

        Canonical model stores sender context in relationships/metadata and does
        not persist `sender_id` directly in this table.
        """
        metadata = self.message_metadata or {}
        return metadata.get("sender_id")

    @sender_id.setter
    def sender_id(self, value):
        metadata = dict(self.message_metadata or {})
        metadata["sender_id"] = str(value) if value is not None else None
        self.message_metadata = metadata

    @property
    def sender(self):
        """Legacy sender accessor used by repository optimization tests."""
        patient = getattr(self, "patient", None)
        return getattr(patient, "doctor", None) if patient is not None else None

    def __repr__(self):
        direction = self.direction.value if hasattr(self.direction, "value") else self.direction
        return f"<Message(patient_id='{self.patient_id}', direction='{direction}')>"
