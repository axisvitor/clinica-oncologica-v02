from typing import Optional, Dict, Any
from datetime import date, datetime
from uuid import UUID
import re

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.models.patient import FlowState
from app.schemas.validators.cpf import (
    is_valid_cpf,
    normalize_cpf as normalize_cpf_value,
    sanitize_persisted_cpf,
)
from app.schemas.validators.birth_date import validate_birth_date_min_age


def validate_cpf(cpf: str) -> bool:
    """
    Compatibility wrapper for CPF validation.

    Canonical implementation lives in ``app.schemas.validators.cpf``.
    """
    return is_valid_cpf(cpf, allow_none=True)


def _normalize_phone_to_e164(
    phone: Optional[str], *, allow_none: bool, preserve_falsy: bool = False
) -> Optional[str]:
    """Normalize phone using canonical BR-to-E.164 validator."""
    if preserve_falsy and not phone:
        return phone

    from app.schemas.validators.phone import normalize_phone, PhoneValidationMode

    return normalize_phone(
        phone, mode=PhoneValidationMode.BR_TO_E164, allow_none=allow_none
    )


def _validate_and_normalize_cpf(value: Optional[str]) -> Optional[str]:
    """Validate CPF and return normalized digits-only value."""
    if not value:
        return value

    if not validate_cpf(value):
        raise ValueError("Invalid CPF number")
    return normalize_cpf_value(value, allow_none=False)


class PatientBase(BaseModel):
    """Base patient schema with Brazilian healthcare fields"""

    phone: str = Field(..., description="Patient phone number")
    name: str = Field(..., description="Patient full name")
    email: Optional[str] = Field(None, description="Patient email address")
    birth_date: Optional[date] = Field(None, description="Patient birth date")
    treatment_type: Optional[str] = Field(None, description="Type of treatment")
    treatment_start_date: Optional[date] = Field(
        None, description="Treatment start date"
    )

    # Brazilian healthcare specific fields (now as dedicated columns)
    cpf: Optional[str] = Field(
        None, description="Brazilian CPF (11 digits)", max_length=11
    )
    diagnosis: Optional[str] = Field(
        None, description="Medical diagnosis", max_length=500
    )
    treatment_phase: Optional[str] = Field(
        None,
        description="Current treatment phase",
        pattern="^(onboarding|initial|adjustment|maintenance|monitoring|followup|completed|inicial|ajuste|manutenção|monitoramento|acompanhamento|concluído)$",
    )
    doctor_notes: Optional[str] = Field(
        None, description="Doctor's notes about the patient"
    )

    # Clinical information (optional - backward compatible)
    allergies: Optional[list[str]] = Field(
        None, description="Known allergies (e.g., medications, foods)"
    )
    current_medications: Optional[list[str]] = Field(
        None, description="Current medications"
    )
    comorbidities: Optional[list[str]] = Field(
        None, description="Comorbidities (e.g., diabetes, hypertension)"
    )
    blood_type: Optional[str] = Field(
        None,
        pattern="^(A|B|AB|O)[+-]$",
        description="Blood type (A+, A-, B+, B-, AB+, AB-, O+, O-)",
    )
    emergency_contact_name: Optional[str] = Field(
        None, max_length=200, description="Emergency contact name"
    )
    emergency_contact_phone: Optional[str] = Field(
        None, description="Emergency contact phone"
    )
    timezone: str = Field(
        "America/Sao_Paulo", description="Patient timezone (e.g., America/Sao_Paulo)"
    )

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v):
        if v:
            # Basic email validation
            email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(email_regex, v):
                raise ValueError("Invalid email format")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        """
        Validate phone number and normalize to E.164 format.

        This validator accepts Brazilian formats for compatibility and
        normalizes to E.164 for storage and duplicate checks.

        Examples:
            - Valid: "+5511987654321"
            - Valid: "11987654321"
            - Valid: "(11) 98765-4321"

        See: app/schemas/validators/phone.py for implementation details
        """
        return _normalize_phone_to_e164(v, allow_none=False)

    @field_validator("emergency_contact_phone")
    @classmethod
    def validate_emergency_phone(cls, v):
        """Validate emergency contact phone and normalize to E.164."""
        return _normalize_phone_to_e164(v, allow_none=True, preserve_falsy=True)

    @field_validator("birth_date")
    @classmethod
    def validate_min_age(cls, v: Optional[date]) -> Optional[date]:
        """
        Validate patient is at least 18 years old.

        Reference: LOW-004 - birth_date Minimum Age Validation

        Raises:
            ValueError: If patient is under 18 or over 120 years old
        """
        return validate_birth_date_min_age(v)

    @field_validator("treatment_phase", mode="before")
    @classmethod
    def normalize_treatment_phase(cls, v):
        # Normalize to lowercase to satisfy pattern and handle legacy uppercase values
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("cpf")
    @classmethod
    def validate_cpf_number(cls, v):
        """Validate Brazilian CPF format and check digits."""
        return _validate_and_normalize_cpf(v)


class PatientCreate(PatientBase):
    """Schema for creating a patient"""

    # Additional metadata that doesn't fit in dedicated columns
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional patient metadata"
    )

    @field_validator("metadata")
    @classmethod
    def validate_metadata_schema(
        cls, v: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Validate metadata against JSON schema.

        Reference: LOW-007 - JSONB Schema Validation

        Raises:
            ValueError: If metadata doesn't conform to schema
        """
        if v is None:
            return v

        # Import here to avoid circular dependency
        from app.utils.jsonb_validator import validate_patient_metadata

        try:
            return validate_patient_metadata(v)
        except Exception as e:
            # Re-raise as ValueError for Pydantic
            raise ValueError(f"Invalid metadata schema: {str(e)}")

class PatientUpdate(BaseModel):
    """Schema for updating a patient"""

    phone: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    birth_date: Optional[date] = None
    treatment_type: Optional[str] = None
    treatment_start_date: Optional[date] = None
    flow_state: Optional[FlowState] = None
    current_day: Optional[int] = None

    # Brazilian healthcare specific fields
    cpf: Optional[str] = Field(None, max_length=11)
    diagnosis: Optional[str] = Field(None, max_length=500)
    treatment_phase: Optional[str] = Field(
        None,
        pattern="^(onboarding|initial|adjustment|maintenance|monitoring|followup|completed|inicial|ajuste|manutenção|monitoramento|acompanhamento|concluído)$",
    )
    doctor_notes: Optional[str] = None

    # Clinical information (optional - backward compatible)
    allergies: Optional[list[str]] = None
    current_medications: Optional[list[str]] = None
    comorbidities: Optional[list[str]] = None
    blood_type: Optional[str] = Field(None, pattern="^(A|B|AB|O)[+-]$")
    emergency_contact_name: Optional[str] = Field(None, max_length=200)
    emergency_contact_phone: Optional[str] = None
    timezone: Optional[str] = None

    # Additional metadata
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v):
        if v:
            email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(email_regex, v):
                raise ValueError("Invalid email format")
        return v

    @field_validator("emergency_contact_phone")
    @classmethod
    def validate_emergency_phone(cls, v):
        """Validate emergency contact phone and normalize to E.164."""
        return _normalize_phone_to_e164(v, allow_none=True, preserve_falsy=True)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        """Validate phone number and normalize to E.164 format."""
        return _normalize_phone_to_e164(v, allow_none=True, preserve_falsy=True)

    @field_validator("birth_date")
    @classmethod
    def validate_min_age(cls, v: Optional[date]) -> Optional[date]:
        """
        Validate patient is at least 18 years old.

        Reference: LOW-004 - birth_date Minimum Age Validation
        """
        return validate_birth_date_min_age(v)

    @field_validator("cpf")
    @classmethod
    def validate_cpf_number(cls, v):
        """Validate Brazilian CPF format and check digits."""
        return _validate_and_normalize_cpf(v)

    @field_validator("metadata")
    @classmethod
    def validate_metadata_schema(
        cls, v: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Validate metadata against JSON schema.

        Reference: LOW-007 - JSONB Schema Validation
        """
        if v is None:
            return v

        from app.utils.jsonb_validator import validate_patient_metadata

        try:
            return validate_patient_metadata(v)
        except Exception as e:
            raise ValueError(f"Invalid metadata schema: {str(e)}")


class PatientResponse(PatientBase):
    """Schema for patient response"""

    id: UUID
    doctor_id: UUID
    flow_state: FlowState
    current_day: int
    created_at: date
    updated_at: date

    # Include metadata in response (for any additional fields)
    patient_data: Optional[Dict[str, Any]] = Field(
        None, serialization_alias="metadata", description="Additional patient metadata"
    )

    @field_validator("cpf", mode="before")
    @classmethod
    def sanitize_invalid_cpf(cls, value):
        """
        Prevent response serialization failures for invalid persisted CPF values.

        Invalid persisted CPF values are converted to None in API output instead of
        triggering a 500 response validation error.
        """
        return sanitize_persisted_cpf(value)

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def coerce_datetime_to_date(cls, v):
        # Convert datetime to date for response schema compatibility
        if isinstance(v, datetime):
            return v.date()
        return v

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PatientListResponse(BaseModel):
    """Schema for patient list response with pagination metadata."""

    data: list[PatientResponse] = Field(..., description="Current page of patients")
    total: int = Field(..., description="Total number of patients matching filters")
    page: int = Field(..., ge=1, description="Current page number")
    limit: int = Field(..., ge=1, description="Number of records per page")
    pages: int = Field(..., ge=0, description="Total page count")
    has_more: bool = Field(..., description="Whether additional pages are available")
    has_previous: bool = Field(..., description="Whether a previous page exists")

    model_config = ConfigDict(from_attributes=True)
