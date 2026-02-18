"""
Message Archive model for storing historical messages.
"""

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
    Integer,
    Boolean
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum
from datetime import datetime, timezone

from app.models.base import BaseModel
from app.models.message import MessageDirection, MessageType, MessageStatus, DeliveryStatus, MessagePriority
from app.utils.timezone import now_sao_paulo

class MessageArchive(BaseModel):
    """
    Archive for Message model.
    Stores messages removed from the main 'messages' table for performance.
    """

    __tablename__ = "message_archives"

    # Original ID from messages table (preserved)
    original_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Patient reference - We keep the FK to allow cascading deletes 
    # if the patient is hard deleted (though we use soft delete).
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
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            validate_strings=True,
        ),
        nullable=False,
    )
    type = Column(
        SAEnum(
            MessageType,
            name="messagetype",
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            validate_strings=True,
        ),
        nullable=False,
    )
    content = Column(Text, nullable=True)

    # Metadata
    message_metadata = Column(JSONB, nullable=True)
    priority = Column(
        SAEnum(
            MessagePriority,
            name="message_priority",
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            validate_strings=True,
        ),
        nullable=False,
        default=MessagePriority.NORMAL,
    )

    # Idempotency key - kept for audit, but uniqueness constraint might be relaxed in archive
    # to avoid conflicts if we re-archive somehow (though rare).
    idempotency_key = Column(String(255), nullable=True)

    # WhatsApp integration
    whatsapp_id = Column(String(255), nullable=True, index=True)
    status = Column(
        SAEnum(
            MessageStatus,
            name="message_status",
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            validate_strings=True,
        ),
        nullable=False,
    )

    # Timestamps
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    # Delivery tracking
    delivery_status = Column(
        SAEnum(
            DeliveryStatus,
            name="message_delivery_status",
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            validate_strings=True,
        ),
        nullable=True,
    )
    retry_count = Column(Integer, nullable=False, default=0)
    last_retry_at = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(Text, nullable=True)
    
    # Archival Metadata
    archived_at = Column(DateTime(timezone=True), default=lambda: now_sao_paulo(), nullable=False)
    
    # We do not define relationships back to Patient to avoid bloating the Patient model
    # with an archive relationship unless needed.

    def __repr__(self):
        return f"<MessageArchive(original_id='{self.original_id}', archived_at='{self.archived_at}')>"
