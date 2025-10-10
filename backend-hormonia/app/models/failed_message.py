"""
FailedMessage model for Dead Letter Queue (DLQ).
Stores messages that failed delivery after max retry attempts.
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional

from app.models.base import BaseModel


class FailureReason(str, Enum):
    """Enumeration of failure reasons for messages."""
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    NETWORK_ERROR = "network_error"
    API_ERROR = "api_error"
    INVALID_PHONE = "invalid_phone"
    BLOCKED_NUMBER = "blocked_number"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class DLQStatus(str, Enum):
    """Status of failed message in DLQ."""
    PENDING_REVIEW = "pending_review"
    UNDER_REVIEW = "under_review"
    APPROVED_FOR_RETRY = "approved_for_retry"
    REQUEUED = "requeued"
    PERMANENTLY_FAILED = "permanently_failed"
    RESOLVED = "resolved"


class FailedMessage(BaseModel):
    """
    Failed message storage for Dead Letter Queue (DLQ).

    Tracks messages that failed delivery after exhausting retry attempts.
    Enables manual review, analysis, and re-queue functionality.

    Schema:
    - id (uuid, PK)
    - original_message_id (uuid, FK to messages, nullable - message may be deleted)
    - patient_id (uuid, FK to patients)
    - content (text, not null) - Original message content
    - whatsapp_phone (varchar, not null) - Target phone number
    - failure_reason (enum, not null) - Categorized failure reason
    - failure_details (jsonb) - Detailed error information
    - retry_count (integer, not null) - Number of retry attempts made
    - last_retry_at (timestamptz) - Timestamp of last retry attempt
    - failed_at (timestamptz, not null) - When message entered DLQ
    - dlq_status (enum, not null) - Current DLQ processing status
    - reviewed_by (uuid, FK to users, nullable) - Admin who reviewed
    - reviewed_at (timestamptz, nullable) - Review timestamp
    - review_notes (text, nullable) - Admin review notes
    - requeue_count (integer, default: 0) - Times message was re-queued
    - last_requeue_at (timestamptz, nullable) - Last re-queue timestamp
    - metadata (jsonb) - Additional metadata (flow context, etc.)
    - created_at (timestamptz, not null)
    - updated_at (timestamptz, not null)
    """
    __tablename__ = "whatsapp_delivery_failures"

    # Original message reference (nullable - message may be deleted)
    original_message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True)

    # Patient reference (required)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)

    # Message details
    content = Column(Text, nullable=False)
    whatsapp_phone = Column(String(20), nullable=False, index=True)

    # Failure tracking
    failure_reason = Column(SQLEnum(FailureReason, values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)
    failure_details = Column(JSONB, nullable=True, default=dict)  # Error stack, API response, etc.
    retry_count = Column(Integer, nullable=False, default=0)
    last_retry_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # DLQ management
    dlq_status = Column(SQLEnum(DLQStatus, values_callable=lambda x: [e.value for e in x]), nullable=False, default=DLQStatus.PENDING_REVIEW, index=True)

    # Review workflow
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)

    # Re-queue tracking
    requeue_count = Column(Integer, nullable=False, default=0)
    last_requeue_at = Column(DateTime, nullable=True)

    # Additional context
    dlq_metadata = Column('metadata', JSONB, nullable=True, default=dict)

    # Relationships
    original_message = relationship("Message", foreign_keys=[original_message_id], backref="dlq_entries")
    patient = relationship("Patient", foreign_keys=[patient_id], backref="failed_messages")
    reviewer = relationship("User", foreign_keys=[reviewed_by], backref="reviewed_failures")

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """
        Convert to dictionary for API responses.

        Args:
            include_sensitive: Include sensitive failure details

        Returns:
            Dictionary representation
        """
        result = {
            "id": str(self.id),
            "patient_id": str(self.patient_id),
            "whatsapp_phone": self.whatsapp_phone,
            "content": self.content,
            "failure_reason": self.failure_reason.value,
            "retry_count": self.retry_count,
            "failed_at": self.failed_at.isoformat() if self.failed_at else None,
            "dlq_status": self.dlq_status.value,
            "requeue_count": self.requeue_count,
            "last_requeue_at": self.last_requeue_at.isoformat() if self.last_requeue_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "review_notes": self.review_notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

        if include_sensitive:
            result["failure_details"] = self.failure_details
            result["metadata"] = self.dlq_metadata

        if self.original_message_id:
            result["original_message_id"] = str(self.original_message_id)

        if self.reviewed_by:
            result["reviewed_by"] = str(self.reviewed_by)

        return result

    def can_requeue(self) -> bool:
        """Check if message can be re-queued for retry."""
        return self.dlq_status in [
            DLQStatus.PENDING_REVIEW,
            DLQStatus.APPROVED_FOR_RETRY
        ]

    def mark_reviewed(self, reviewer_id: UUID, notes: Optional[str] = None, approve_retry: bool = False):
        """
        Mark message as reviewed by admin.

        Args:
            reviewer_id: UUID of reviewing admin
            notes: Review notes
            approve_retry: Whether to approve for retry
        """
        self.reviewed_by = reviewer_id
        self.reviewed_at = datetime.utcnow()
        self.review_notes = notes
        self.dlq_status = DLQStatus.APPROVED_FOR_RETRY if approve_retry else DLQStatus.UNDER_REVIEW

    def mark_requeued(self):
        """Mark message as re-queued for delivery."""
        self.requeue_count += 1
        self.last_requeue_at = datetime.utcnow()
        self.dlq_status = DLQStatus.REQUEUED

    def mark_permanently_failed(self, reason: Optional[str] = None):
        """
        Mark message as permanently failed (no more retries).

        Args:
            reason: Reason for permanent failure
        """
        self.dlq_status = DLQStatus.PERMANENTLY_FAILED
        if reason:
            if not self.dlq_metadata:
                self.dlq_metadata = {}
            self.dlq_metadata["permanent_failure_reason"] = reason
            self.dlq_metadata["marked_failed_at"] = datetime.utcnow().isoformat()

    def __repr__(self):
        return f"<FailedMessage(id={self.id}, reason={self.failure_reason.value}, status={self.dlq_status.value})>"
