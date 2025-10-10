"""
Message model for WhatsApp communication.
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class MessageDirection(enum.Enum):
    """Message direction enumeration."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageType(enum.Enum):
    """Message type enumeration."""
    TEXT = "text"
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


class MessageStatus(enum.Enum):
    """Message status enumeration."""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    SENDING = "sending"  # Message is being sent by Celery worker
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeliveryStatus(enum.Enum):
    """Detailed delivery status tracking for WhatsApp messages."""
    SCHEDULED = "scheduled"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Message(BaseModel):
    """Message model for WhatsApp communication."""
    __tablename__ = "messages"

    # Patient reference
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)

    # Message details
    direction = Column(Enum(MessageDirection), nullable=False)
    type = Column(Enum(MessageType), default=MessageType.TEXT, nullable=False)
    content = Column(Text, nullable=True)

    # Metadata for buttons, media URLs, etc.
    message_metadata = Column(JSONB, nullable=True, default=dict)

    # WhatsApp integration
    whatsapp_id = Column(String(255), nullable=True, index=True)
    status = Column(Enum(MessageStatus), default=MessageStatus.PENDING, nullable=False)

    # Scheduling and delivery tracking
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    # Delivery status tracking (new fields for P1 fix)
    delivery_status = Column(Enum(DeliveryStatus), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    last_retry_at = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(Text, nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    patient = relationship("Patient", back_populates="messages")
    status_events = relationship(
        "MessageStatusEvent",
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="MessageStatusEvent.created_at"
    )

    def __repr__(self):
        return f"<Message(patient_id='{self.patient_id}', direction='{self.direction.value}')>"