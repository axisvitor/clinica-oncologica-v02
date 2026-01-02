from typing import Optional, Dict, Any
from datetime import date, datetime, timedelta
from uuid import UUID
import re

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.models.patient import FlowState


def validate_cpf(cpf: str) -> bool:
    """Validate Brazilian CPF number with check digits."""
    if not cpf:
        return True  # CPF is optional

    # Remove non-digits
    cpf_clean = re.sub(r"\D", "", cpf)

    # Check length
    if len(cpf_clean) != 11:
        return False

    # Check for known invalid patterns
    if cpf_clean in [
        "00000000000",
        "11111111111",
        "22222222222",
        "33333333333",
        "44444444444",
        "55555555555",
        "66666666666",
        "77777777777",
        "88888888888",
        "99999999999",
    ]:
        return False

    # Calculate first check digit
    sum1 = sum(int(cpf_clean[i]) * (10 - i) for i in range(9))
    digit1 = 11 - (sum1 % 11)
    digit1 = 0 if digit1 >= 10 else digit1

    # Calculate second check digit
    sum2 = sum(int(cpf_clean[i]) * (11 - i) for i in range(10))
    digit2 = 11 - (sum2 % 11)
    digit2 = 0 if digit2 >= 10 else digit2

    # Validate check digits
    return int(cpf_clean[9]) == digit1 and int(cpf_clean[10]) == digit2


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
        pattern="^(initial|adjustment|maintenance|monitoring|followup|completed|inicial|ajuste|manutenção|monitoramento|acompanhamento|concluído)$",
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
        Validate phone number in E.164 format.

        This validator enforces strict E.164 format for v1 API compatibility.
        Phone must start with + followed by country code and digits.

        Examples:
            - Valid: "+5511987654321"
            - Invalid: "11987654321" (missing country code)

        See: app/schemas/validators/phone.py for implementation details
        """
        from app.schemas.validators.phone import validate_phone_e164

        return validate_phone_e164(v, allow_none=False)

    @field_validator("emergency_contact_phone")
    @classmethod
    def validate_emergency_phone(cls, v):
        """Validate emergency contact phone in E.164 format."""
        if not v:
            return v

        from app.schemas.validators.phone import validate_phone_e164

        return validate_phone_e164(v, allow_none=True)

    @field_validator("birth_date")
    @classmethod
    def validate_min_age(cls, v: Optional[date]) -> Optional[date]:
        """
        Validate patient is at least 18 years old.

        Reference: LOW-004 - birth_date Minimum Age Validation

        Raises:
            ValueError: If patient is under 18 or over 120 years old
        """
        if v is None:
            return v

        today = date.today()

        # Calculate minimum allowed birth date (18 years ago)
        # Using 365.25 to account for leap years
        min_date = today - timedelta(days=int(18 * 365.25))

        if v > min_date:
            age_years = (today - v).days / 365.25
            raise ValueError(
                f"Patient must be at least 18 years old. "
                f"Birth date {v.isoformat()} indicates age of {age_years:.1f} years."
            )

        # Also validate not impossibly old (120 years)
        max_date = today - timedelta(days=int(120 * 365.25))
        if v < max_date:
            age_years = (today - v).days / 365.25
            raise ValueError(
                f"Birth date {v.isoformat()} seems invalid "
                f"(indicates age of {age_years:.1f} years, over 120 years old)."
            )

        # Validate not in the future
        if v > today:
            raise ValueError(f"Birth date {v.isoformat()} cannot be in the future.")

        return v

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
        if v and not validate_cpf(v):
            raise ValueError("Invalid CPF number")
        # Clean CPF to store only digits
        if v:
            v = re.sub(r"\D", "", v)
        return v


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
        None, pattern="^(initial|adjustment|maintenance|monitoring|followup|completed|inicial|ajuste|manutenção|monitoramento|acompanhamento|concluído)$"
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
        """Validate emergency contact phone in E.164 format."""
        if not v:
            return v

        from app.schemas.validators.phone import validate_phone_e164

        return validate_phone_e164(v, allow_none=True)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        """Validate phone number in E.164 format."""
        if not v:
            return v

        from app.schemas.validators.phone import validate_phone_e164

        return validate_phone_e164(v, allow_none=True)

    @field_validator("birth_date")
    @classmethod
    def validate_min_age(cls, v: Optional[date]) -> Optional[date]:
        """
        Validate patient is at least 18 years old.

        Reference: LOW-004 - birth_date Minimum Age Validation
        """
        if v is None:
            return v

        today = date.today()
        min_date = today - timedelta(days=int(18 * 365.25))

        if v > min_date:
            age_years = (today - v).days / 365.25
            raise ValueError(
                f"Patient must be at least 18 years old. "
                f"Birth date {v.isoformat()} indicates age of {age_years:.1f} years."
            )

        max_date = today - timedelta(days=int(120 * 365.25))
        if v < max_date:
            age_years = (today - v).days / 365.25
            raise ValueError(
                f"Birth date {v.isoformat()} seems invalid "
                f"(indicates age of {age_years:.1f} years, over 120 years old)."
            )

        if v > today:
            raise ValueError(f"Birth date {v.isoformat()} cannot be in the future.")

        return v

    @field_validator("cpf")
    @classmethod
    def validate_cpf_number(cls, v):
        """Validate Brazilian CPF format and check digits."""
        if v and not validate_cpf(v):
            raise ValueError("Invalid CPF number")
        # Clean CPF to store only digits
        if v:
            v = re.sub(r"\D", "", v)
        return v

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
