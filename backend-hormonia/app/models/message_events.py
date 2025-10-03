"""
Message Event Tracking Models for WhatsApp Status and Webhook Events.

Tracks message delivery status changes and Evolution API webhook events for debugging.
"""
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import BaseModel


class MessageStatusEvent(BaseModel):
    """
    Track WhatsApp message delivery status changes.

    Provides detailed audit trail of message lifecycle including:
    - Status transitions (pending -> sent -> delivered -> read)
    - Evolution API acknowledgements
    - Error tracking and retry attempts
    - WhatsApp message ID mapping
    """
    __tablename__ = "message_status_events"

    # Message reference
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Status tracking
    status = Column(String(50), nullable=False, index=True)  # sent, delivered, read, failed
    previous_status = Column(String(50), nullable=True)  # Previous status for audit trail

    # WhatsApp integration
    whatsapp_id = Column(String(255), nullable=True, index=True)  # WhatsApp message ID
    whatsapp_timestamp = Column(DateTime(timezone=True), nullable=True)  # WhatsApp event timestamp

    # Error tracking
    error_code = Column(String(50), nullable=True, index=True)  # Error code from Evolution API
    error_message = Column(Text, nullable=True)  # Detailed error message
    retry_count = Column(Integer, default=0, nullable=False)  # Number of retry attempts

    # Event metadata
    event_metadata = Column("metadata", JSONB, nullable=True, default=dict)  # Additional event data

    # Evolution API data
    evolution_event_type = Column(String(100), nullable=True)  # Raw Evolution API event type
    evolution_payload = Column(JSONB, nullable=True)  # Full Evolution API payload for debugging

    # Timestamp - indexed for performance
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )

    # Relationships
    message = relationship("Message", back_populates="status_events")

    # Composite indexes for common queries
    __table_args__ = (
        # Query messages by status timeline
        Index('ix_msg_status_msg_created', 'message_id', 'created_at'),
        # Query recent status changes by type
        Index('ix_msg_status_type_time', 'status', 'created_at'),
        # Track errors by code and time
        Index('ix_msg_status_error_time', 'error_code', 'created_at'),
        # WhatsApp ID lookup
        Index('ix_msg_status_whatsapp', 'whatsapp_id', 'status'),
    )

    def __repr__(self):
        return f"<MessageStatusEvent(message_id='{self.message_id}', status='{self.status}')>"

    @property
    def is_error_state(self) -> bool:
        """Check if this event represents an error state."""
        return self.status == 'failed' or self.error_code is not None

    @property
    def is_final_state(self) -> bool:
        """Check if this is a final delivery state."""
        return self.status in ['read', 'failed']


class WebhookEvent(BaseModel):
    """
    Store Evolution API webhook events for debugging and audit purposes.

    Captures all webhook events from Evolution API to enable:
    - Debugging message delivery issues
    - Replay of events for testing
    - Audit trail for compliance
    - Performance monitoring
    """
    __tablename__ = "webhook_events"

    # Event classification
    event_type = Column(String(100), nullable=False, index=True)  # message.sent, message.delivered, etc.
    source = Column(String(100), nullable=False, index=True)  # evolution_api, whatsapp, system

    # Event payload
    payload = Column(JSONB, nullable=False)  # Full webhook payload

    # Processing status
    processed = Column(Boolean, default=False, index=True, nullable=False)  # Has event been processed
    processed_at = Column(DateTime(timezone=True), nullable=True)  # When was it processed

    # Retry mechanism
    retry_count = Column(Integer, default=0, nullable=False)  # Number of processing attempts
    max_retries = Column(Integer, default=3, nullable=False)  # Maximum retry attempts
    next_retry_at = Column(DateTime(timezone=True), nullable=True, index=True)  # Scheduled retry time

    # Error tracking
    error_message = Column(Text, nullable=True)  # Processing error details
    error_stack_trace = Column(Text, nullable=True)  # Full error stack trace for debugging

    # Related records (optional references)
    related_message_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Related message if identified
    related_patient_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Related patient if identified

    # Deduplication
    event_hash = Column(String(64), nullable=True, unique=True, index=True)  # SHA-256 hash for deduplication
    is_duplicate = Column(Boolean, default=False, index=True)  # Marked as duplicate
    original_event_id = Column(UUID(as_uuid=True), nullable=True)  # Reference to original if duplicate

    # Timestamp - indexed for performance
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )

    # Composite indexes for common queries
    __table_args__ = (
        # Query unprocessed events by type
        Index('ix_webhook_type_processed', 'event_type', 'processed', 'created_at'),
        # Query events ready for retry
        Index('ix_webhook_retry_schedule', 'processed', 'next_retry_at'),
        # Query events by source and time
        Index('ix_webhook_source_time', 'source', 'created_at'),
        # Query events needing processing
        Index('ix_webhook_pending', 'processed', 'retry_count', 'created_at'),
        # Query related records
        Index('ix_webhook_related_msg', 'related_message_id', 'event_type'),
        Index('ix_webhook_related_patient', 'related_patient_id', 'event_type'),
    )

    def __repr__(self):
        return f"<WebhookEvent(event_type='{self.event_type}', processed={self.processed})>"

    @property
    def can_retry(self) -> bool:
        """Check if event can be retried."""
        return not self.processed and self.retry_count < self.max_retries

    @property
    def is_failed(self) -> bool:
        """Check if event processing has permanently failed."""
        return not self.processed and self.retry_count >= self.max_retries

    @property
    def should_retry_now(self) -> bool:
        """Check if event should be retried now."""
        if not self.can_retry or not self.next_retry_at:
            return False
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) >= self.next_retry_at