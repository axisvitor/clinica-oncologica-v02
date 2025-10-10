"""
Consent model for patient consent records.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.user import User


class ConsentType(str, enum.Enum):
    """Consent type enumeration."""
    TREATMENT = "treatment"
    DATA_SHARING = "data_sharing"
    RESEARCH = "research"
    COMMUNICATION = "communication"
    TELEMEDICINE = "telemedicine"
    PHOTOGRAPHY = "photography"
    GENERAL = "general"


class ConsentStatus(str, enum.Enum):
    """Consent status enumeration."""
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    REVOKED = "revoked"
    EXPIRED = "expired"


class Consent(BaseModel):
    """
    Consent model representing patient consent records.

    Relationships (configured for eager loading):
    - patient: Many-to-one with Patient (joinedload)
    - consented_by: Many-to-one with User (joinedload)
    """
    __tablename__ = "consents"

    # Foreign Keys
    patient_id = Column(PGUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    consented_by_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Consent Details
    consent_type = Column(SQLEnum(ConsentType), nullable=False, index=True)
    status = Column(SQLEnum(ConsentStatus), nullable=False, default=ConsentStatus.PENDING, index=True)

    # Content
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    legal_text = Column(Text, nullable=True)

    # Dates
    granted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Version Control
    version = Column(String(20), nullable=True)
    previous_consent_id = Column(PGUUID(as_uuid=True), nullable=True, index=True)

    # Signature
    signature_data = Column(JSONB, nullable=True)  # Digital signature information
    witness_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Revocation
    revocation_reason = Column(Text, nullable=True)

    # Flags
    is_required = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Metadata
    metadata = Column(JSONB, nullable=True)

    # Relationships (optimized for eager loading)
    patient = relationship("Patient", back_populates="consents", foreign_keys=[patient_id], lazy="select")
    consented_by = relationship("User", back_populates="consents_managed", foreign_keys=[consented_by_id], lazy="select")
    witness = relationship("User", foreign_keys=[witness_id], lazy="select")

    def __repr__(self) -> str:
        return f"<Consent(id={self.id}, patient_id={self.patient_id}, type={self.consent_type}, status={self.status})>"
