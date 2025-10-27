"""
Patient model for hormone therapy patients.
Corresponds to the actual Supabase schema structure.
"""
from sqlalchemy import Column, String, Date, Integer, ForeignKey, Enum, Text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum
from typing import Dict, Any, Optional, TYPE_CHECKING

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.patient_onboarding_saga import PatientOnboardingSaga


class FlowState(enum.Enum):
    """Patient flow state enumeration - matches Supabase enum."""
    ONBOARDING = "onboarding"
    ONBOARDING_START = "onboarding"  # Alias for saga orchestrator compatibility
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    INACTIVE = "cancelled"  # Legacy alias maintained for backward compatibility


class Patient(BaseModel):
    """
    Patient model for hormone therapy patients.

    This model corresponds exactly to the Supabase patients table schema:
    - id (uuid, PK)
    - doctor_id (uuid, FK to users)
    - phone (varchar, unique, not null)
    - name (varchar, not null)
    - email (varchar, nullable)
    - birth_date (date, nullable)
    - treatment_type (varchar, nullable)
    - treatment_start_date (date, nullable)
    - flow_state (enum, not null, default: onboarding)
    - current_day (integer, not null, default: 0)
    - cpf (varchar(11), nullable, indexed)
    - diagnosis (varchar(500), nullable, indexed)
    - treatment_phase (varchar(100), nullable, indexed)
    - doctor_notes (text, nullable)
    - metadata (jsonb, nullable, default: {}) [accessed via patient_data attribute]
    - created_at (timestamptz, not null)
    - updated_at (timestamptz, not null)

    Migration: add_dedicated_patient_columns
    """
    __tablename__ = "patients"
    
    # Basic information (matches Supabase schema exactly)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    phone = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    birth_date = Column(Date, nullable=True)
    
    # Treatment information
    treatment_type = Column(String, nullable=True)
    treatment_start_date = Column(Date, nullable=True)
    
    # Flow control
    # Use values_callable to ensure enum values (not names) are used in database
    # name='flow_state' specifies the PostgreSQL ENUM type name (with underscore)
    flow_state = Column(Enum(FlowState, values_callable=lambda x: [e.value for e in x], name='flow_state'), default=FlowState.ONBOARDING, nullable=False)
    current_day = Column(Integer, default=0, nullable=False)

    # Brazilian healthcare specific fields (now in dedicated columns after migration)
    # Migration: add_dedicated_patient_columns
    cpf = Column(String(11), nullable=True, index=True)
    diagnosis = Column(Text, nullable=True, index=True)
    treatment_phase = Column(String(100), nullable=True, index=True)
    doctor_notes = Column(Text, nullable=True)

    # Flexible metadata storage (matches Supabase column name)
    # Note: Using 'patient_data' as attribute name since 'metadata' is reserved by SQLAlchemy
    # Now only stores additional/dynamic fields not covered by dedicated columns
    patient_data = Column('metadata', JSONB, nullable=True, default=dict)
    # Legacy alias present in DB
    patient_metadata = Column('patient_metadata', JSONB, nullable=True)

    # Relationships
    doctor = relationship("User", back_populates="patients")
    messages = relationship(
        "Message",
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    flow_states = relationship(
        "PatientFlowState",
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    quiz_responses = relationship("QuizResponse", back_populates="patient")
    quiz_sessions = relationship(
        "QuizSession",
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    medical_reports = relationship("MedicalReport", back_populates="patient")
    alerts = relationship("Alert", back_populates="patient")

    # Saga orchestrator relationship
    onboarding_sagas = relationship(
        "PatientOnboardingSaga",
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    # New relationships for Sprint 1 eager loading optimization
    treatments = relationship("Treatment", back_populates="patient", lazy="select", passive_deletes=True)
    appointments = relationship("Appointment", back_populates="patient", lazy="select", passive_deletes=True)
    medications = relationship("Medication", back_populates="patient", lazy="select", passive_deletes=True)
    notifications = relationship("Notification", back_populates="related_patient", lazy="select", passive_deletes=True)
    consents = relationship("Consent", back_populates="patient", foreign_keys="[Consent.patient_id]", lazy="select", passive_deletes=True)
    analytics = relationship("FlowAnalytics", back_populates="patient", lazy="select", passive_deletes=True)

    # Constraints and indexes to match DB uniques
    __table_args__ = (
        UniqueConstraint('cpf', name='patients_cpf_key'),
        UniqueConstraint('phone', name='patients_phone_key'),
    )

    # NOTE: cpf, diagnosis, treatment_phase, doctor_notes are now dedicated columns
    # No property accessors needed - they are direct column attributes

    # Legacy compatibility methods for backward compatibility with old code
    @property
    def cpf_from_metadata(self) -> Optional[str]:
        """Legacy: Get CPF (now from dedicated column, not metadata)."""
        return self.cpf

    @property
    def diagnosis_from_metadata(self) -> Optional[str]:
        """Legacy: Get diagnosis (now from dedicated column, not metadata)."""
        return self.diagnosis

    @property
    def treatment_phase_from_metadata(self) -> Optional[str]:
        """Legacy: Get treatment phase (now from dedicated column, not metadata)."""
        return self.treatment_phase

    @property
    def doctor_name(self) -> Optional[str]:
        """Get doctor name from metadata (cache for performance)."""
        return self.patient_data.get('doctor_name') if self.patient_data else None
    
    @doctor_name.setter
    def doctor_name(self, value: Optional[str]):
        """Set doctor name in metadata."""
        if not self.patient_data:
            self.patient_data = {}
        self.patient_data['doctor_name'] = value
    
    def get_metadata_field(self, field: str, default: Any = None) -> Any:
        """Get any field from metadata with default value."""
        return self.patient_data.get(field, default) if self.patient_data else default
    
    def set_metadata_field(self, field: str, value: Any) -> None:
        """Set any field in metadata."""
        if not self.patient_data:
            self.patient_data = {}
        self.patient_data[field] = value
    
    def update_metadata(self, updates: Dict[str, Any]) -> None:
        """Update multiple metadata fields at once."""
        if not self.patient_data:
            self.patient_data = {}
        self.patient_data.update(updates)
    
    # Compatibility methods for legacy code
    @property
    def patient_metadata(self) -> Optional[Dict[str, Any]]:
        """Compatibility property for legacy code that uses patient_metadata."""
        return self.patient_data
    
    @patient_metadata.setter
    def patient_metadata(self, value: Optional[Dict[str, Any]]):
        """Compatibility setter for legacy code."""
        self.patient_data = value
    
    # NOTE: 'metadata' property removed due to SQLAlchemy conflict
    # Use patient_data directly or patient_metadata for compatibility
    
    # Alternative field names for backwards compatibility
    @property
    def date_of_birth(self) -> Optional[Date]:
        """Compatibility property for date_of_birth."""
        return self.birth_date
    
    @date_of_birth.setter
    def date_of_birth(self, value: Optional[Date]):
        """Compatibility setter for date_of_birth."""
        self.birth_date = value
    
    @property
    def cancer_type(self) -> Optional[str]:
        """Compatibility property for cancer_type (maps to treatment_type)."""
        return self.treatment_type
    
    @cancer_type.setter
    def cancer_type(self, value: Optional[str]):
        """Compatibility setter for cancer_type."""
        self.treatment_type = value
    
    @property
    def treatment_stage(self) -> Optional[str]:
        """Compatibility property for treatment_stage (maps to treatment_phase in metadata)."""
        return self.treatment_phase
    
    @treatment_stage.setter
    def treatment_stage(self, value: Optional[str]):
        """Compatibility setter for treatment_stage."""
        self.treatment_phase = value
    
    def __repr__(self):
        return f"<Patient(name='{self.name}', phone='{self.phone}')>"
