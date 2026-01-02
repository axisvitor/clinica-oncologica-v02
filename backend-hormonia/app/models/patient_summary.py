"""
Patient Summary model for AI-generated patient summaries.
Stores comprehensive patient summaries for doctor consultations.
"""

from sqlalchemy import Column, String, Date, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, BYTEA
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class PatientSummary(BaseModel):
    """
    AI-generated patient summary for doctor consultations.

    Stores comprehensive summaries including:
    - Quiz responses analysis
    - Health concerns detected
    - Engagement metrics
    - Treatment compliance
    - AI recommendations

    Supports:
    - Date range filtering
    - PDF export
    - Historical tracking
    """

    __tablename__ = "patient_summaries"

    # Foreign keys
    patient_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generated_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Summary period
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    # Summary content (structured JSON)
    content = Column(JSONB, nullable=False, default=dict)
    """
    Content structure:
    {
        "overview": "2-3 paragraphs summary",
        "quiz_findings": {
            "total_completed": int,
            "key_findings": ["finding1", "finding2"],
            "symptom_trends": {"symptom": "trend"}
        },
        "health_concerns": [
            {"concern": str, "severity": "low|medium|high|critical", "date": str}
        ],
        "engagement_metrics": {
            "response_rate": float,
            "avg_response_time_minutes": float,
            "total_messages": int
        },
        "treatment_compliance": {
            "adherence_score": float,
            "notes": str
        },
        "recommendations": ["rec1", "rec2", "rec3"]
    }
    """

    # PDF export (optional, generated on demand)
    pdf_data = Column(BYTEA, nullable=True)

    # AI metadata
    token_usage = Column(Integer, nullable=True)
    model_used = Column(String(100), nullable=True)
    generation_time_ms = Column(Integer, nullable=True)

    # Relationships
    patient = relationship("Patient", back_populates="summaries")
    generated_by_user = relationship("User", foreign_keys=[generated_by])

    # Indexes for common queries
    __table_args__ = (
        Index(
            "idx_patient_summaries_patient_period",
            "patient_id",
            "start_date",
            "end_date",
        ),
        Index("idx_patient_summaries_generated_at", "created_at"),
    )

    def __repr__(self):
        return f"<PatientSummary(patient_id={self.patient_id}, period={self.start_date} to {self.end_date})>"
