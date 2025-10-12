"""
Alert and notification models.
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from typing import Optional
import enum
import uuid

from app.models.base import BaseModel


class AlertSeverity(enum.Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(enum.Enum):
    """Alert status levels."""
    PENDING = "pending"
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class Alert(BaseModel):
    """System alerts for patient monitoring.
    
    This model maps to the existing database schema:
    - alert_type maps to 'type' column
    - description maps to 'message' column  
    - status maps to 'acknowledged' boolean
    - quiz_session_id stored in 'data' JSONB field
    """
    __tablename__ = "alerts"

    # Patient reference
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)

    # Alert details - mapped to existing DB columns
    alert_type = Column("type", String(100), nullable=False)  # Maps to 'type' column
    severity = Column(Enum(AlertSeverity), nullable=False)
    description = Column("message", Text, nullable=False)  # Maps to 'message' column
    data = Column(JSONB, nullable=True, default=dict)

    # Acknowledgment tracking - maps to existing boolean field
    acknowledged = Column(Boolean, default=False, nullable=False)
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    patient = relationship("Patient", back_populates="alerts")
    acknowledged_by_user = relationship("User", back_populates="acknowledged_alerts")
    
    # Note: quiz_session relationship removed since quiz_session_id is stored in JSONB data field

    # Virtual properties for backward compatibility
    @property
    def status(self) -> str:
        """Map acknowledged boolean to status-like behavior."""
        return "acknowledged" if self.acknowledged else "pending"
    
    @status.setter
    def status(self, value: str):
        """Set acknowledged based on status value."""
        if value == "acknowledged":
            self.acknowledged = True
        else:
            self.acknowledged = False
    
    # Handle quiz_session_id via data JSONB field
    @property
    def quiz_session_id(self) -> Optional[uuid.UUID]:
        """Get quiz_session_id from data JSONB field."""
        if self.data and "quiz_session_id" in self.data:
            try:
                return uuid.UUID(self.data["quiz_session_id"])
            except (ValueError, TypeError):
                return None
        return None
    
    @quiz_session_id.setter
    def quiz_session_id(self, value: Optional[uuid.UUID]):
        """Store quiz_session_id in data JSONB field."""
        if self.data is None:
            self.data = {}
        if value:
            self.data["quiz_session_id"] = str(value)
        elif "quiz_session_id" in self.data:
            del self.data["quiz_session_id"]

    def __repr__(self):
        return f"<Alert(patient_id='{self.patient_id}', type='{self.alert_type}', severity='{self.severity.value}')>"