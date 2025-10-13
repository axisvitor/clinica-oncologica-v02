"""
Treatment model for patient treatment plans.
"""
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Column, String, Date, DateTime, ForeignKey, Text, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.user import User
    from app.models.medication import Medication


class TreatmentStatus(str, enum.Enum):
    """Treatment status enumeration."""
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class TreatmentType(str, enum.Enum):
    """Treatment type enumeration."""
    QUIMIOTERAPIA = "quimioterapia"
    RADIOTERAPIA = "radioterapia"
    HORMONIOTERAPIA = "hormonioterapia"
    IMUNOTERAPIA = "imunoterapia"
    CIRURGIA = "cirurgia"
    OUTROS = "outros"


class Treatment(BaseModel):
    """
    Treatment model representing patient treatment plans.

    Relationships (configured for eager loading):
    - patient: Many-to-one with Patient (joinedload)
    - doctor: Many-to-one with User (joinedload)
    - medications: One-to-many with Medication (selectinload)
    """
    __tablename__ = "treatments"

    # Foreign Keys
    patient_id = Column(PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Treatment Details
    treatment_type = Column(SQLEnum(TreatmentType), nullable=False, index=True)
    status = Column(SQLEnum(TreatmentStatus), nullable=False, default=TreatmentStatus.PLANNED, index=True)

    # Dates
    start_date = Column(Date, nullable=True, index=True)
    end_date = Column(Date, nullable=True)
    planned_sessions = Column(String(100), nullable=True)
    completed_sessions = Column(String(100), nullable=True)

    # Clinical Information
    diagnosis = Column(Text, nullable=True)
    protocol = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)

    # Flags
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Relationships (optimized for eager loading)
    patient = relationship("Patient", back_populates="treatments", lazy="select", passive_deletes=True)
    doctor = relationship("User", back_populates="treatments_managed", foreign_keys=[doctor_id], lazy="select")
    medications = relationship("Medication", back_populates="treatment", cascade="all, delete-orphan", lazy="select")

    def __repr__(self) -> str:
        return f"<Treatment(id={self.id}, patient_id={self.patient_id}, type={self.treatment_type}, status={self.status})>"
