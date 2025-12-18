"""
Medication model for patient medications.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Column, String, Date, ForeignKey, Text, Boolean, Numeric, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    pass


class Medication(BaseModel):
    """
    Medication model representing patient medications.

    Relationships (configured for eager loading):
    - patient: Many-to-one with Patient (joinedload)
    - prescribed_by: Many-to-one with User (joinedload)
    - treatment: Many-to-one with Treatment (joinedload)
    """

    __tablename__ = "medications"

    # Foreign Keys
    patient_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prescribed_by_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    treatment_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("treatments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Medication Details
    name = Column(String(200), nullable=False)
    active_ingredient = Column(String(200), nullable=True)
    dosage = Column(String(100), nullable=False)
    frequency = Column(String(100), nullable=False)
    route = Column(String(50), nullable=True)  # oral, intravenous, topical, etc.

    # Prescription Details
    prescription_date = Column(Date, nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)

    # Quantity
    quantity = Column(Numeric(10, 2), nullable=True)
    refills_allowed = Column(Integer, default=0, nullable=False)
    refills_remaining = Column(Integer, default=0, nullable=False)

    # Instructions
    instructions = Column(Text, nullable=True)
    warnings = Column(Text, nullable=True)
    side_effects = Column(Text, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    discontinued_date = Column(Date, nullable=True)
    discontinuation_reason = Column(Text, nullable=True)

    # Relationships (optimized for eager loading)
    patient = relationship("Patient", back_populates="medications", lazy="select")
    prescribed_by = relationship(
        "User",
        back_populates="medications_prescribed",
        foreign_keys=[prescribed_by_id],
        lazy="select",
    )
    treatment = relationship("Treatment", back_populates="medications", lazy="select")

    def __repr__(self) -> str:
        return f"<Medication(id={self.id}, patient_id={self.patient_id}, name={self.name}, dosage={self.dosage}, is_active={self.is_active})>"
