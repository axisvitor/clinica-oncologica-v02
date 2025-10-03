"""
Medical report models.
"""
from sqlalchemy import Column, String, Text, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class MedicalReport(BaseModel):
    """Medical reports for patients."""
    __tablename__ = "medical_reports"
    
    # References
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    generated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Report period
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    
    # Report content
    summary = Column(Text, nullable=True)  # AI-generated summary
    insights = Column(JSONB, nullable=True, default=dict)  # Structured insights
    charts_data = Column(JSONB, nullable=True, default=dict)  # Data for charts
    alerts = Column(JSONB, nullable=True, default=dict)  # Identified alerts
    
    # Relationships
    patient = relationship("Patient", back_populates="medical_reports")
    generated_by_user = relationship("User", back_populates="generated_reports")
    
    def __repr__(self):
        return f"<MedicalReport(patient_id='{self.patient_id}', period='{self.period_start}-{self.period_end}')>"