"""
Webhook Event Model for Idempotency Tracking

Stores webhook events to prevent duplicate processing using idempotency keys.
Events expire after 24 hours for automatic cleanup.
"""

from datetime import datetime, timedelta
from sqlalchemy import Column, String, DateTime, Integer, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import Base


class WebhookEvent(Base):
    """
    Model for tracking webhook events to ensure idempotent processing.

    Prevents duplicate webhook processing by storing event IDs and detecting
    replays within the idempotency window (24 hours).

    Note: Uses table 'webhook_idempotency' to avoid conflict with the existing
    'webhook_events' table (created in migration 019) which stores full event history.
    """

    __tablename__ = "webhook_idempotency"

    # Primary key - webhook event ID (from provider)
    event_id = Column(
        String(255),
        primary_key=True,
        nullable=False,
        comment="Unique event ID from webhook provider",
    )

    # Event metadata
    provider = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Webhook provider (e.g., 'whatsapp', 'twilio')",
    )

    event_type = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Type of webhook event (e.g., 'message.received')",
    )

    # Timestamps
    received_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="When webhook was first received",
    )

    processed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When webhook processing completed",
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When idempotency record expires (24h from received_at)",
    )

    # Processing metadata
    status = Column(
        String(20),
        nullable=False,
        default="processing",
        comment="Processing status: processing, completed, failed",
    )

    retry_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of duplicate webhook attempts detected",
    )

    # Store original webhook payload for debugging
    payload = Column(
        JSONB, nullable=True, comment="Original webhook payload (for debugging)"
    )

    # Response data
    response_data = Column(
        JSONB, nullable=True, comment="Processing result or error details"
    )

    # Indexes for efficient queries
    __table_args__ = (
        Index("idx_webhook_idempotency_provider_type", "provider", "event_type"),
        Index("idx_webhook_idempotency_expires_at", "expires_at"),
        Index("idx_webhook_idempotency_received_at", "received_at"),
        Index("idx_webhook_idempotency_status", "status"),
    )

    @classmethod
    def create_event(
        cls,
        event_id: str,
        provider: str,
        event_type: str,
        payload: dict | None = None,
        ttl_hours: int = 24,
    ) -> "WebhookEvent":
        """
        Create a new webhook event record.

        Args:
            event_id: Unique event ID from provider
            provider: Webhook provider name
            event_type: Type of event
            payload: Original webhook payload
            ttl_hours: Time-to-live in hours (default 24)

        Returns:
            WebhookEvent instance
        """
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=ttl_hours)

        return cls(
            event_id=event_id,
            provider=provider,
            event_type=event_type,
            payload=payload,
            received_at=now,
            expires_at=expires_at,
            status="processing",
            retry_count=0,
        )

    def mark_completed(self, response_data: dict | None = None) -> None:
        """Mark event as successfully processed."""
        self.status = "completed"
        self.processed_at = datetime.utcnow()
        if response_data:
            self.response_data = response_data

    def mark_failed(self, error_data: dict | None = None) -> None:
        """Mark event as failed processing."""
        self.status = "failed"
        self.processed_at = datetime.utcnow()
        if error_data:
            self.response_data = error_data

    def increment_retry(self) -> None:
        """Increment retry counter for duplicate detection."""
        self.retry_count += 1

    def is_expired(self) -> bool:
        """Check if idempotency record has expired."""
        return datetime.utcnow() > self.expires_at

    def __repr__(self) -> str:
        return (
            f"<WebhookEvent(event_id='{self.event_id}', "
            f"provider='{self.provider}', "
            f"event_type='{self.event_type}', "
            f"status='{self.status}', "
            f"retry_count={self.retry_count})>"
        )
