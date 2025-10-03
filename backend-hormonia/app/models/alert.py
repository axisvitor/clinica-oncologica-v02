"""
Alert and notification models.
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

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
    """System alerts for patient monitoring."""
    __tablename__ = "alerts"
    
    # Patient reference
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    
    # Alert details
    alert_type = Column(String(100), nullable=False)  # 'urgency', 'adherence', 'symptom'
    severity = Column(Enum(AlertSeverity), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(Enum(AlertStatus), default=AlertStatus.PENDING, nullable=False)
    data = Column(JSONB, nullable=True, default=dict)
    
    # Acknowledgment tracking
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    patient = relationship("Patient", back_populates="alerts")
    acknowledged_by_user = relationship("User", back_populates="acknowledged_alerts")
    
    def __repr__(self):
        return f"<Alert(patient_id='{self.patient_id}', type='{self.alert_type}', severity='{self.severity.value}')>"