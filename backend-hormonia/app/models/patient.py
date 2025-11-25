"""
Patient model for hormone therapy patients.
Corresponds to the actual Supabase schema structure.
"""
from sqlalchemy import Column, String, Date, Integer, ForeignKey, Enum, Text, UniqueConstraint, Index, DateTime
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, validates
import enum
from typing import Dict, Any, Optional, TYPE_CHECKING
from datetime import date, timedelta

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.patient_onboarding_saga import PatientOnboardingSaga


class FlowState(enum.Enum):
    """Patient flow state enumeration - matches Supabase enum."""
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


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
    phone = Column(String, nullable=False)
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
    # LGPD Compliance: CPF encryption fields
    # - cpf: DEPRECATED - Legacy plaintext column (kept for rollback)
    # - cpf_encrypted: AES-256 encrypted CPF value
    # - cpf_hash: SHA-256 searchable hash for queries
    cpf = Column(String(11), nullable=True)  # DEPRECATED: Legacy plaintext
    cpf_encrypted = Column(Text, nullable=True)  # Encrypted CPF
    cpf_hash = Column(String(64), nullable=True, index=True)  # Searchable hash
    diagnosis = Column(Text, nullable=True, index=True)
    treatment_phase = Column(String(100), nullable=True, index=True)
    doctor_notes = Column(Text, nullable=True)

    # Flexible metadata storage (matches Supabase column name)
    # Note: Using 'patient_data' as attribute name since 'metadata' is reserved by SQLAlchemy
    # Now only stores additional/dynamic fields not covered by dedicated columns
    patient_data = Column('metadata', JSONB, nullable=True, default=dict)
    # Legacy alias present in DB

    # Soft delete support
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)

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
    reports = relationship("Report", back_populates="patient")
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
    summaries = relationship("PatientSummary", back_populates="patient", lazy="select", passive_deletes=True)

    # Constraints and indexes to match DB uniques
    # After migration 009: Composite unique constraints scoped to doctor_id
    __table_args__ = (
        # Composite unique constraints to prevent duplicates per doctor
        UniqueConstraint('email', 'doctor_id', name='uq_patient_email_doctor'),
        UniqueConstraint('cpf', 'doctor_id', name='uq_patient_cpf_doctor'),
        UniqueConstraint('phone', 'doctor_id', name='uq_patient_phone_doctor'),

        # Composite indexes for faster lookups
        Index('idx_patient_phone_doctor', 'phone', 'doctor_id'),
        Index('idx_patient_email_doctor', 'email', 'doctor_id', postgresql_where=sa.text('email IS NOT NULL')),
        Index('idx_patient_cpf_doctor', 'cpf', 'doctor_id', postgresql_where=sa.text('cpf IS NOT NULL')),
    )

    # =========================================================================
    # VALIDATION METHODS (LOW-004, LOW-007)
    # =========================================================================

    @validates('birth_date')
    def validate_birth_date_age(self, key, value: Optional[date]) -> Optional[date]:
        """
        Validate patient age at ORM level.

        Reference: LOW-004 - birth_date Minimum Age Validation

        Ensures patient is between 18 and 120 years old.
        """
        if value is None:
            return value

        today = date.today()

        # Minimum 18 years old
        min_date = today - timedelta(days=int(18 * 365.25))
        if value > min_date:
            age_years = (today - value).days / 365.25
            raise ValueError(
                f"Patient must be at least 18 years old. "
                f"Birth date {value.isoformat()} indicates age of {age_years:.1f} years."
            )

        # Maximum 120 years old
        max_date = today - timedelta(days=int(120 * 365.25))
        if value < max_date:
            age_years = (today - value).days / 365.25
            raise ValueError(
                f"Birth date {value.isoformat()} seems invalid "
                f"(indicates age of {age_years:.1f} years, over 120 years old)."
            )

        # Not in the future
        if value > today:
            raise ValueError(f"Birth date {value.isoformat()} cannot be in the future.")

        return value

    @validates('patient_data')
    def validate_metadata_schema(self, key, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Validate patient_data (metadata) against JSON schema at ORM level.

        Reference: LOW-007 - JSONB Schema Validation

        Ensures metadata conforms to defined schema.
        """
        if value is None or value == {}:
            return value or {}

        # Import here to avoid circular dependency
        from app.utils.jsonb_validator import validate_patient_metadata

        try:
            return validate_patient_metadata(value)
        except Exception as e:
            raise ValueError(f"Invalid metadata schema: {str(e)}")

    # =========================================================================
    # CPF ENCRYPTION PROPERTIES (LGPD Compliance)
    # =========================================================================

    @property
    def cpf_decrypted(self) -> Optional[str]:
        """
        Get decrypted CPF value.

        Returns decrypted CPF if encrypted, otherwise returns plaintext CPF
        for backward compatibility during migration period.

        Returns:
            Decrypted CPF (11 digits) or None
        """
        if self.cpf_encrypted:
            from app.services.cpf_encryption_service import get_cpf_encryption_service
            service = get_cpf_encryption_service()
            return service.decrypt_cpf(self.cpf_encrypted)
        elif self.cpf:
            # Backward compatibility: return plaintext if not encrypted yet
            return self.cpf
        return None

    def set_cpf(self, cpf_value: Optional[str]) -> None:
        """
        Set CPF with automatic encryption.

        Encrypts the CPF and generates searchable hash.
        Legacy plaintext column is set to None for security.

        Args:
            cpf_value: CPF to encrypt (with or without formatting)
        """
        if not cpf_value:
            self.cpf_encrypted = None
            self.cpf_hash = None
            self.cpf = None
            return

        from app.services.cpf_encryption_service import get_cpf_encryption_service
        service = get_cpf_encryption_service()

        # Encrypt and hash
        encrypted_cpf, cpf_hash = service.encrypt_cpf(cpf_value)

        # Store encrypted values
        self.cpf_encrypted = encrypted_cpf
        self.cpf_hash = cpf_hash

        # Clear legacy plaintext column for security
        self.cpf = None

    def get_cpf_display(self, mask: bool = False) -> Optional[str]:
        """
        Get formatted CPF for display.

        Args:
            mask: If True, mask most digits (***.***.789-**)

        Returns:
            Formatted CPF string
        """
        cpf_value = self.cpf_decrypted
        if not cpf_value:
            return None

        from app.services.cpf_encryption_service import get_cpf_encryption_service
        service = get_cpf_encryption_service()
        return service.format_cpf_for_display(cpf_value, mask=mask)

    # NOTE: diagnosis, treatment_phase, doctor_notes are dedicated columns
    # No property accessors needed - they are direct column attributes

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
    
    @property
    def timezone(self) -> str:
        """Get patient timezone from metadata (default: America/Sao_Paulo)."""
        return self.patient_data.get('timezone', 'America/Sao_Paulo') if self.patient_data else 'America/Sao_Paulo'

    @timezone.setter
    def timezone(self, value: str):
        """Set patient timezone in metadata."""
        if not self.patient_data:
            self.patient_data = {}
        self.patient_data['timezone'] = value
    
    def __repr__(self):
        return f"<Patient(name='{self.name}', phone='{self.phone}')>"
