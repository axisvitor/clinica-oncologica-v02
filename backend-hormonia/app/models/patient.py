"""
Patient model for hormone therapy patients.
Corresponds to the actual Supabase schema structure.
"""

from sqlalchemy import (
    Column,
    String,
    Date,
    Integer,
    ForeignKey,
    Enum,
    Text,
    UniqueConstraint,
    Index,
    DateTime,
    event,
)
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, validates
import enum
from typing import Dict, Any, Optional, TYPE_CHECKING
from datetime import date, timedelta

from app.models.base import BaseModel

if TYPE_CHECKING:
    pass


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
    - name (varchar, not null)
    - birth_date (date, nullable)
    - treatment_type (varchar, nullable)
    - treatment_start_date (date, nullable)
    - flow_state (enum, not null, default: onboarding)
    - current_day (integer, not null, default: 0)
    - cpf_encrypted (text, nullable) - LGPD encrypted CPF
    - cpf_hash (varchar(64), nullable, indexed) - Searchable hash
    - email_encrypted (bytea, nullable) - LGPD encrypted email
    - email_hash (varchar(64), nullable, indexed) - Searchable hash
    - phone_encrypted (bytea, nullable) - LGPD encrypted phone
    - phone_hash (varchar(64), nullable, indexed) - Searchable hash
    - diagnosis (varchar(500), nullable, indexed)
    - treatment_phase (varchar(100), nullable, indexed)
    - doctor_notes (text, nullable)
    - metadata (jsonb, nullable, default: {}) [accessed via patient_data attribute]
    - created_at (timestamptz, not null)
    - updated_at (timestamptz, not null)

    LGPD Compliance (Post-Migration 030):
    - Plaintext cpf, email, phone columns REMOVED
    - All PII stored encrypted with AES-256-GCM
    """

    __tablename__ = "patients"

    # Basic information (matches Supabase schema exactly)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # NOTE: phone and email plaintext columns REMOVED in migration 030 (LGPD compliance)
    # Use phone_encrypted/phone_hash and email_encrypted/email_hash instead
    name = Column(String, nullable=False)
    birth_date = Column(Date, nullable=True)

    # Treatment information
    treatment_type = Column(String, nullable=True)
    treatment_start_date = Column(Date, nullable=True)

    # Flow control
    # Use values_callable to ensure enum values (not names) are used in database
    # name='flow_state' specifies the PostgreSQL ENUM type name (with underscore)
    flow_state = Column(
        Enum(
            FlowState, values_callable=lambda x: [e.value for e in x], name="flow_state"
        ),
        default=FlowState.ONBOARDING,
        nullable=False,
    )
    current_day = Column(Integer, default=0, nullable=False)

    # Brazilian healthcare specific fields (now in dedicated columns after migration)
    # Migration: add_dedicated_patient_columns
    # LGPD Compliance: CPF encryption fields (migration 020 + 024)
    # - cpf_encrypted: AES-256 encrypted CPF value
    # - cpf_hash: SHA-256 searchable hash for queries
    # NOTE: Plaintext 'cpf' column removed in migration 024 for LGPD compliance
    cpf_encrypted = Column(Text, nullable=True)  # Encrypted CPF
    cpf_hash = Column(String(64), nullable=True, index=True)  # Searchable hash

    # LGPD Compliance: Email/Phone encryption fields (migration 028)
    # - email_encrypted: AES-256 encrypted email value
    # - email_hash: SHA-256 searchable hash for queries
    # - phone_encrypted: AES-256 encrypted phone value
    # - phone_hash: SHA-256 searchable hash for queries
    email_encrypted = Column(sa.LargeBinary, nullable=True)  # Encrypted email
    email_hash = Column(String(64), nullable=True, index=True)  # Searchable hash
    phone_encrypted = Column(sa.LargeBinary, nullable=True)  # Encrypted phone
    phone_hash = Column(String(64), nullable=True, index=True)  # Searchable hash

    diagnosis = Column(Text, nullable=True, index=True)
    treatment_phase = Column(String(100), nullable=True, index=True)
    doctor_notes = Column(Text, nullable=True)

    # Flexible metadata storage (matches Supabase column name)
    # Note: Using 'patient_data' as attribute name since 'metadata' is reserved by SQLAlchemy
    # Now only stores additional/dynamic fields not covered by dedicated columns
    patient_data = Column("metadata", JSONB, nullable=True, default=dict)
    # Legacy alias present in DB

    # QW-004: Idempotency key for duplicate request prevention
    # Used to prevent duplicate patient creation from retried API requests
    idempotency_key = Column(String(64), unique=True, nullable=True, index=True)

    # Soft delete support
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    doctor = relationship("User", back_populates="patients")
    messages = relationship(
        "Message",
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    flow_states = relationship(
        "PatientFlowState",
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    quiz_responses = relationship("QuizResponse", back_populates="patient")
    quiz_sessions = relationship(
        "QuizSession",
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    medical_reports = relationship("MedicalReport", back_populates="patient")
    reports = relationship("Report", back_populates="patient")
    alerts = relationship("Alert", back_populates="patient")

    # Saga orchestrator relationship
    onboarding_sagas = relationship(
        "PatientOnboardingSaga",
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # New relationships for Sprint 1 eager loading optimization
    treatments = relationship(
        "Treatment", back_populates="patient", lazy="select", passive_deletes=True
    )
    appointments = relationship(
        "Appointment", back_populates="patient", lazy="select", passive_deletes=True
    )
    medications = relationship(
        "Medication", back_populates="patient", lazy="select", passive_deletes=True
    )
    notifications = relationship(
        "Notification",
        back_populates="related_patient",
        lazy="select",
        passive_deletes=True,
    )
    consents = relationship(
        "Consent",
        back_populates="patient",
        foreign_keys="[Consent.patient_id]",
        lazy="select",
        passive_deletes=True,
    )
    analytics = relationship(
        "FlowAnalytics", back_populates="patient", lazy="select", passive_deletes=True
    )
    summaries = relationship(
        "PatientSummary", back_populates="patient", lazy="select", passive_deletes=True
    )

    # Constraints and indexes to match DB uniques
    # After migrations 009, 020 (CPF encryption), 024 (CPF plaintext removal), 028 (email/phone encryption)
    #
    # LGPD Compliance Note (Post-Migration 030):
    # - email and phone plaintext columns REMOVED in migration 030 ✅
    # - All unique constraints use hash columns for encrypted data
    # - Indexes defined here must match database schema
    __table_args__ = (
        # LGPD: Hash-based unique constraints
        UniqueConstraint("cpf_hash", "doctor_id", name="uq_patient_cpf_hash_doctor"),
        # Composite indexes for faster lookups (hash-based only)
        Index(
            "ix_patients_cpf_hash_doctor",
            "cpf_hash",
            "doctor_id",
            postgresql_where=sa.text("cpf_hash IS NOT NULL"),
        ),
        # LGPD: Email/Phone hash indexes (primary search indexes)
        Index("ix_patients_email_hash", "email_hash"),
        Index("ix_patients_phone_hash", "phone_hash"),
        # Unique partial indexes on hash columns (enforces uniqueness per doctor)
        Index(
            "ix_patients_email_hash_doctor",
            "email_hash",
            "doctor_id",
            unique=True,
            postgresql_where=sa.text("email_hash IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index(
            "ix_patients_phone_hash_doctor",
            "phone_hash",
            "doctor_id",
            unique=True,
            postgresql_where=sa.text("phone_hash IS NOT NULL AND deleted_at IS NULL"),
        ),
        # QW-004: Idempotency key index
        Index(
            "ix_patients_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        ),
    )

    # =========================================================================
    # VALIDATION METHODS (LOW-004, LOW-007)
    # =========================================================================

    @validates("birth_date")
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

    @validates("patient_data")
    def validate_metadata_schema(
        self, key, value: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
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

        Returns decrypted CPF from encrypted storage.

        Returns:
            Decrypted CPF (11 digits) or None
        """
        if self.cpf_encrypted:
            from app.services.encryption import get_cpf_encryption_service

            service = get_cpf_encryption_service()
            return service.decrypt_cpf(self.cpf_encrypted)
        return None

    @property
    def cpf(self) -> Optional[str]:
        """
        Backward compatibility alias for cpf_decrypted.

        LGPD: Returns decrypted CPF for backward compatibility.
        New code should use cpf_decrypted directly.
        """
        return self.cpf_decrypted

    def set_cpf(self, cpf_value: Optional[str]) -> None:
        """
        Set CPF with automatic encryption.

        Encrypts the CPF and generates searchable hash.

        Args:
            cpf_value: CPF to encrypt (with or without formatting)
        """
        if not cpf_value:
            self.cpf_encrypted = None
            self.cpf_hash = None
            return

        from app.services.encryption import get_cpf_encryption_service

        service = get_cpf_encryption_service()

        # Encrypt and hash
        encrypted_cpf, cpf_hash = service.encrypt_cpf(cpf_value)

        # Store encrypted values (plaintext column removed in migration 030)
        self.cpf_encrypted = encrypted_cpf
        self.cpf_hash = cpf_hash

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

        from app.services.encryption import get_cpf_encryption_service

        service = get_cpf_encryption_service()
        return service.format_cpf_for_display(cpf_value, mask=mask)

    # =========================================================================
    # EMAIL/PHONE ENCRYPTION PROPERTIES (LGPD Compliance - Migration 028)
    # =========================================================================

    @property
    def email_decrypted(self) -> Optional[str]:
        """
        Get decrypted email value.

        Returns decrypted email from encrypted storage.

        Returns:
            Decrypted email or None
        """
        if self.email_encrypted:
            from app.services.encryption import get_lgpd_encryption_service

            service = get_lgpd_encryption_service()
            return service.decrypt_email(self.email_encrypted)
        return None  # No plaintext fallback (column removed in migration 030)

    @property
    def email(self) -> Optional[str]:
        """
        Backward compatibility alias for email_decrypted.

        LGPD: Returns decrypted email for backward compatibility.
        New code should use email_decrypted directly.
        """
        return self.email_decrypted

    def set_email(self, email_value: Optional[str]) -> None:
        """
        Set email with automatic encryption.

        Encrypts the email and generates searchable hash.
        NOTE: Plaintext email column removed in migration 030 (LGPD compliance).

        Args:
            email_value: Email to encrypt
        """
        if not email_value:
            self.email_encrypted = None
            self.email_hash = None
            return

        from app.services.encryption import get_lgpd_encryption_service

        service = get_lgpd_encryption_service()

        # Encrypt and hash
        encrypted_email, email_hash = service.encrypt_email(email_value)

        # Store encrypted values only (plaintext column removed in migration 030)
        self.email_encrypted = encrypted_email
        self.email_hash = email_hash

    @property
    def phone_decrypted(self) -> Optional[str]:
        """
        Get decrypted phone value.

        Returns decrypted phone from encrypted storage.

        Returns:
            Decrypted phone or None
        """
        if self.phone_encrypted:
            from app.services.encryption import get_lgpd_encryption_service

            service = get_lgpd_encryption_service()
            return service.decrypt_phone(self.phone_encrypted)
        return None  # No plaintext fallback (column removed in migration 030)

    @property
    def phone(self) -> Optional[str]:
        """
        Backward compatibility alias for phone_decrypted.

        LGPD: Returns decrypted phone for backward compatibility.
        New code should use phone_decrypted directly.
        """
        return self.phone_decrypted

    def set_phone(self, phone_value: Optional[str]) -> None:
        """
        Set phone with automatic encryption.

        Encrypts the phone and generates searchable hash.
        NOTE: Plaintext phone column removed in migration 030 (LGPD compliance).

        Args:
            phone_value: Phone to encrypt
        """
        if not phone_value:
            self.phone_encrypted = None
            self.phone_hash = None
            return

        from app.services.encryption import get_lgpd_encryption_service

        service = get_lgpd_encryption_service()

        # Encrypt and hash
        encrypted_phone, phone_hash = service.encrypt_phone(phone_value)

        # Store encrypted values only (plaintext column removed in migration 030)
        self.phone_encrypted = encrypted_phone
        self.phone_hash = phone_hash

    # NOTE: diagnosis, treatment_phase, doctor_notes are dedicated columns
    # No property accessors needed - they are direct column attributes

    @property
    def doctor_name(self) -> Optional[str]:
        """Get doctor name from metadata (cache for performance)."""
        return self.patient_data.get("doctor_name") if self.patient_data else None

    @doctor_name.setter
    def doctor_name(self, value: Optional[str]):
        """Set doctor name in metadata."""
        if not self.patient_data:
            self.patient_data = {}
        self.patient_data["doctor_name"] = value

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
        if not self.patient_data:
            return "America/Sao_Paulo"

        preferences = self.patient_data.get("preferences")
        if isinstance(preferences, dict) and preferences.get("timezone"):
            return preferences.get("timezone")

        legacy_timezone = self.patient_data.get("timezone")
        return legacy_timezone or "America/Sao_Paulo"

    @timezone.setter
    def timezone(self, value: str):
        """Set patient timezone in metadata."""
        if not self.patient_data:
            self.patient_data = {}

        preferences = self.patient_data.get("preferences")
        if not isinstance(preferences, dict):
            preferences = {}

        preferences["timezone"] = value
        self.patient_data["preferences"] = preferences
        self.patient_data.pop("timezone", None)

    def __repr__(self):
        # Use phone_hash for repr (phone column removed in migration 030)
        phone_display = self.phone_hash[:8] + "..." if self.phone_hash else "N/A"
        return f"<Patient(name='{self.name}', phone_hash='{phone_display}')>"


# =========================================================================
# QW-003: CPF ENCRYPTION VALIDATION HOOKS (LGPD Compliance)
# =========================================================================


@event.listens_for(Patient, "before_insert")
@event.listens_for(Patient, "before_update")
def validate_cpf_encryption(mapper, connection, target):
    """
    Ensure CPF is properly encrypted before database operations.

    QW-003: LGPD Compliance - CPF Encryption Validation Hook

    This hook validates that CPF data is properly encrypted before database insertion
    or update. It prevents incomplete encryption which would violate LGPD requirements.

    Validation checks (Post-Migration 030):
    1. If cpf_encrypted exists, cpf_hash must also exist
    2. NOTE: Legacy plaintext 'cpf' column REMOVED in migration 030

    Args:
        mapper: SQLAlchemy mapper
        connection: Database connection
        target: Patient instance being saved

    Raises:
        ValueError: If CPF encryption validation fails
    """
    # Check if CPF data exists and is properly encrypted
    if target.cpf_encrypted:
        # If encrypted CPF exists, hash must also exist
        if not target.cpf_hash:
            raise ValueError(
                "CPF encryption incomplete: cpf_hash is missing. "
                "Use set_cpf() method to properly encrypt CPF data."
            )

    # NOTE: Legacy 'cpf' column validation removed - column dropped in migration 030
