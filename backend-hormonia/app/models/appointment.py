"""
Appointment model for patient appointments.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, Enum as SQLEnum, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.user import User


class AppointmentStatus(str, enum.Enum):
    """Appointment status enumeration."""
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class AppointmentType(str, enum.Enum):
    """Appointment type enumeration."""
    CONSULTATION = "consultation"
    FOLLOWUP = "followup"
    TREATMENT = "treatment"
    EXAM = "exam"
    EMERGENCY = "emergency"
    TELEMEDICINE = "telemedicine"


class Appointment(BaseModel):
    """
    Appointment model representing patient appointments.

    Relationships (configured for eager loading):
    - patient: Many-to-one with Patient (joinedload)
    - practitioner: Many-to-one with User (joinedload)
    - location: Many-to-one with Location (selectinload)
    """
    __tablename__ = "appointments"

    # Foreign Keys
    patient_id = Column(PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    practitioner_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Appointment Details
    appointment_type = Column(String(50), nullable=False, index=True)
    status = Column(String(50), nullable=False, default=AppointmentStatus.SCHEDULED.value, index=True)

    # Date and Time
    scheduled_at = Column(DateTime(timezone=True), nullable=True, index=True)
    duration_minutes = Column(Integer, nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Additional Information
    pre_appointment_notes = Column(Text, nullable=True)
    post_appointment_notes = Column(Text, nullable=True)
    appointment_metadata = Column("appointment_metadata", Text, nullable=True)

    # Contact Information
    # Flags kept for potential future use
    reminder_sent = Column(Boolean, default=False, nullable=False)
    confirmation_sent = Column(Boolean, default=False, nullable=False)

    # Relationships (optimized for eager loading)
    patient = relationship("Patient", back_populates="appointments", lazy="select")
    practitioner = relationship("User", back_populates="appointments_managed", foreign_keys=[practitioner_id], lazy="select")
    # location relationship will be added when Location model is implemented

    def __repr__(self) -> str:
        return f"<Appointment(id={self.id}, patient_id={self.patient_id}, type={self.appointment_type}, status={self.status}, start={self.scheduled_at})>"
