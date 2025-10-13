"""
FailedMessage model for Dead Letter Queue (DLQ).
Stores messages that failed delivery after max retry attempts.
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from typing import Dict, Any

from app.models.base import BaseModel


class FailedMessage(BaseModel):
    """
    Failed message storage for Dead Letter Queue (DLQ).
    Corresponds to the 'whatsapp_delivery_failures' table.
    """
    __tablename__ = "whatsapp_delivery_failures"

    # Fields from the SQL schema
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    phone_number = Column(String(20), nullable=False)
    message_type = Column(String(50), nullable=False)
    message_content = Column(Text, nullable=True)
    error_message = Column(Text, nullable=False)
    error_code = Column(String(50), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    next_retry_at = Column(DateTime, nullable=True)
    last_retry_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default='pending')
    resolved_at = Column(DateTime, nullable=True)
    dlq_metadata = Column(JSONB, nullable=True, default=dict)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    original_message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True)

    @property
    def metadata(self) -> Dict[str, Any]:
        """Access to DLQ metadata."""
        return self.dlq_metadata or {}

    @metadata.setter
    def metadata(self, value: Dict[str, Any]) -> None:
        self.dlq_metadata = value

    # Relationships
    original_message = relationship("Message", foreign_keys=[original_message_id], backref="dlq_entries")
    patient = relationship("Patient", foreign_keys=[patient_id], backref="failed_messages")
    reviewer = relationship("User", foreign_keys=[reviewed_by], backref="reviewed_failures")

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """
        Convert to dictionary for API responses.
        """
        result = {
            "id": str(self.id),
            "patient_id": str(self.patient_id),
            "phone_number": self.phone_number,
            "message_type": self.message_type,
            "message_content": self.message_content,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "last_retry_at": self.last_retry_at.isoformat() if self.last_retry_at else None,
            "status": self.status,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

        if include_sensitive:
            result["metadata"] = self.dlq_metadata

        if self.original_message_id:
            result["original_message_id"] = str(self.original_message_id)

        if self.reviewed_by:
            result["reviewed_by"] = str(self.reviewed_by)

        return result

    def __repr__(self):
        return f"<FailedMessage(id={self.id}, error_message={self.error_message}, status={self.status})>"
