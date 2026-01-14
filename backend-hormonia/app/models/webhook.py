"""
Webhook Management Models
Stores webhook configurations, delivery history, and activity logs.
"""

from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Boolean,
    ForeignKey,
    Index,
    Text,
    Float,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from uuid import uuid4

from app.models.base import Base

# Note: Webhook models use Base (not BaseModel) because they have custom
# id/timestamp columns that differ from BaseModel's standard fields.
# WebhookDelivery has completed_at, next_retry_at; WebhookLog has no updated_at.
# Changing to BaseModel would require database migration.


class WebhookEndpoint(Base):
    """
    Webhook Endpoint Configuration.
    Stores details about where and how to send webhooks.
    """

    __tablename__ = "webhook_endpoints"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    url = Column(String(2048), nullable=False, comment="Target URL")
    description = Column(String(500), nullable=True)
    status = Column(
        String(20),
        default="active",
        nullable=False,
        comment="active, inactive, paused, error",
    )

    # Configuration
    secret = Column(String(255), nullable=True, comment="HMAC secret key")
    events = Column(
        JSONB, nullable=False, default=list, comment="List of subscribed events"
    )
    headers = Column(JSONB, nullable=True, default=dict, comment="Custom headers")

    # Reliability settings
    timeout = Column(
        Integer, default=30, nullable=False, comment="Request timeout in seconds"
    )
    retry_enabled = Column(Boolean, default=True, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)

    # Stats
    success_count = Column(Integer, default=0, nullable=False)
    failure_count = Column(Integer, default=0, nullable=False)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    created_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    deliveries = relationship(
        "WebhookDelivery", back_populates="webhook", cascade="all, delete-orphan"
    )
    logs = relationship(
        "WebhookLog", back_populates="webhook", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_webhook_status", "status"),)


class WebhookDelivery(Base):
    """
    Webhook Delivery History.
    Records every attempt to send a webhook.
    """

    __tablename__ = "webhook_deliveries"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    webhook_id = Column(
        UUID(as_uuid=True),
        ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Event details
    event_type = Column(String(100), nullable=False)
    payload = Column(JSONB, nullable=True)

    # Delivery details
    status = Column(
        String(20), nullable=False, comment="pending, success, failed, retrying"
    )
    attempt = Column(Integer, default=1, nullable=False)
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Float, nullable=True)
    response_body = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    # Timing
    created_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    webhook = relationship("WebhookEndpoint", back_populates="deliveries")

    __table_args__ = (
        Index("idx_webhook_delivery_webhook_id", "webhook_id"),
        Index("idx_webhook_delivery_status", "status"),
        Index("idx_webhook_delivery_created_at", "created_at"),
    )


class WebhookLog(Base):
    """
    Webhook Activity Log.
    Records administrative actions and major state changes.
    """

    __tablename__ = "webhook_logs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    webhook_id = Column(
        UUID(as_uuid=True),
        ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False,
    )

    event_type = Column(
        String(100), nullable=False, comment="e.g., created, updated, secret_rotated"
    )
    action = Column(String(100), nullable=False)
    details = Column(JSONB, nullable=True)

    created_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relationships
    webhook = relationship("WebhookEndpoint", back_populates="logs")

    __table_args__ = (
        Index("idx_webhook_log_webhook_id", "webhook_id"),
        Index("idx_webhook_log_created_at", "created_at"),
    )
