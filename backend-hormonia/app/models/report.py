"""
Medical report models.
"""

from sqlalchemy import (
    Column,
    String,
    Text,
    Date,
    ForeignKey,
    Enum,
    DateTime,
    LargeBinary,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum
from datetime import datetime

from app.models.base import BaseModel
from app.utils.timezone import now_sao_paulo_naive


class ReportType(str, enum.Enum):
    QUIZ_ANALYSIS = "quiz_analysis"
    MONTHLY_SUMMARY = "monthly_summary"
    ALERT_SUMMARY = "alert_summary"
    CUSTOM = "custom"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class MedicalReport(BaseModel):
    """Medical reports for patients (Legacy/Summary)."""

    __tablename__ = "medical_reports"

    # References
    patient_id = Column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    generated_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

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


class Report(BaseModel):
    """Generic report model for system generated reports (Quizzes, etc)."""

    __tablename__ = "reports"

    patient_id = Column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    type = Column(Enum(ReportType), nullable=False)
    title = Column(String, nullable=False)
    content = Column(JSONB, nullable=True)
    pdf_data = Column(
        LargeBinary, nullable=True
    )  # Store PDF bytes directly or use path
    status = Column(Enum(ReportStatus), default=ReportStatus.PENDING)
    generated_at = Column(DateTime, default=now_sao_paulo_naive)
    report_metadata = Column(
        "metadata", JSONB, nullable=True
    )  # metadata is reserved in Base? No, usually metadata in sqlalchemy is Base.metadata.
    # But using "metadata" as column name is tricky. QuizReportGenerator uses metadata=...
    # Let's alias it if needed or use a different name.
    # In sqlalchemy model: Column("metadata", ...) maps db column "metadata" to attribute name.
    # But `BaseModel` might have `metadata`? No, `Base` has `metadata`. `BaseModel` is usually a mixin.

    # Relationships
    patient = relationship("Patient", back_populates="reports")

    def __repr__(self):
        return f"<Report(id='{self.id}', type='{self.type}', title='{self.title}')>"
