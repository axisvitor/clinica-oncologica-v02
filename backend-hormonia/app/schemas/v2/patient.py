"""
Patient schemas for API v2
Enhanced patient models with field selection and eager loading support.
"""

import re
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date, timedelta
from uuid import UUID
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict

from .common import CursorPaginatedResponse

# Import robust CPF validator from v1 schema
from app.schemas.patient import validate_cpf as validate_cpf_check_digits
from app.models.patient import FlowState


class DoctorV2Brief(BaseModel):
    """Brief doctor information for patient response"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: Optional[str] = None


class QuizV2Brief(BaseModel):
    """Brief quiz session information for patient response"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    score: Optional[float] = None
    passed: Optional[bool] = None


class PatientV2Base(BaseModel):
    """Base patient schema"""

    name: str = Field(..., min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    birth_date: Optional[date] = None
    cpf: Optional[str] = Field(None, max_length=14)
    treatment_type: Optional[str] = Field(None, max_length=150)
    treatment_start_date: Optional[date] = None
    doctor_notes: Optional[str] = Field(None, max_length=2000)
    diagnosis: Optional[str] = Field(None, max_length=500)
    treatment_phase: Optional[str] = Field(
        None,
        max_length=100,
        pattern="^(initial|adjustment|maintenance|monitoring|followup|completed|inicial|ajuste|manutenção|monitoramento|acompanhamento|concluído)$"
    )
    timezone: str = Field(
        "America/Sao_Paulo", description="Patient timezone (e.g., America/Sao_Paulo)"
    )

    # Clinical information fields (from v1 schema)
    allergies: Optional[str] = Field(
        None,
        description="Known allergies (e.g., 'Penicilina, Dipirona' or 'Penicilina; Dipirona')",
    )
    medications: Optional[str] = Field(
        None, description="Current medications (e.g., 'Levotiroxina 100mcg, Metformina 500mg')"
    )
    blood_type: Optional[str] = Field(
        None,
        pattern="^(A|B|AB|O)[+-]$",
        description="Blood type (A+, A-, B+, B-, AB+, AB-, O+, O-)"
    )
    emergency_contact: Optional[str] = Field(
        None,
        max_length=200,
        description="Emergency contact (e.g., 'Nome - Telefone' or 'Nome: Telefone')",
    )

    # Metadata JSONB field for additional dynamic data
    patient_data: Optional[Dict[str, Any]] = Field(None, description="Additional patient metadata")

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, v):
        """Validate CPF with check digits verification."""
        if not v:
            return v

        # Check format: only digits, dots, dashes
        if not v.replace(".", "").replace("-", "").isdigit():
            raise ValueError("CPF deve conter apenas dígitos, pontos e traços")

        # Validate check digits
        if not validate_cpf_check_digits(v):
            raise ValueError("CPF inválido: dígitos verificadores incorretos")

        # Clean CPF to store only digits
        return re.sub(r"\D", "", v)

    @field_validator("phone")
    @classmethod
    def validate_phone_format(cls, v):
        """
        Validate phone number and normalize to E.164.

        This validator accepts both formats for v2 API flexibility:
        - E.164 format: +5511987654321
        - Brazilian format: 11987654321, (11) 98765-4321

        The BR_TO_E164 mode standardizes storage to E.164 while
        preserving input flexibility.

        See: app/schemas/validators/phone.py for implementation details
        """
        if not v:
            return v

        from app.schemas.validators.phone import normalize_phone, PhoneValidationMode

        return normalize_phone(v, mode=PhoneValidationMode.BR_TO_E164, allow_none=True)

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
        """Normalize treatment_phase to lowercase."""
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("blood_type", mode="before")
    @classmethod
    def normalize_blood_type(cls, v):
        """Normalize blood type to uppercase."""
        if isinstance(v, str):
            return v.strip().upper()
        return v


class PatientMetadataV2(BaseModel):
    """
    Pydantic model for patient_data (metadata) validation.

    Validates metadata structure and types according to jsonb_validator.py schema.
    Unknown keys are moved to custom_fields automatically.
    """

    model_config = ConfigDict(extra="forbid")

    preferences: Optional[Dict[str, Any]] = None
    medical_history: Optional[Dict[str, Any]] = None
    blood_type: Optional[str] = Field(None, pattern="^(A|B|AB|O)[+-]$")
    emergency_contact: Optional[Dict[str, Any]] = None
    insurance: Optional[Dict[str, Any]] = None
    onboarding: Optional[Dict[str, Any]] = None
    custom_fields: Optional[Dict[str, Any]] = None
    doctor_name: Optional[str] = None
    quarantine: Optional[bool] = None
    quarantine_reason: Optional[str] = None
    quarantine_at: Optional[Union[str, datetime]] = None
    saga_id: Optional[str] = Field(None, pattern="^[0-9a-fA-F-]{36}$")
    system: Optional[Dict[str, Any]] = None

    @field_validator(
        "preferences",
        "medical_history",
        "emergency_contact",
        "insurance",
        "onboarding",
        "system",
    )
    @classmethod
    def validate_dict_type(cls, v):
        """Ensure nested fields are dicts."""
        if v is not None and not isinstance(v, dict):
            raise ValueError("Must be a dictionary")
        return v


class PatientV2Create(PatientV2Base):
    """Schema for creating a patient"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "João Silva",
                "email": "joao@example.com",
                "phone": "(11) 98765-4321",
                "birth_date": "1980-05-15T00:00:00Z",
                "cpf": "123.456.789-00",
                "treatment_type": "Reposição Hormonal",
                "treatment_start_date": "2025-01-10",
                "doctor_notes": "Paciente apresentou boa resposta ao tratamento.",
                "doctor_id": "123e4567-e89b-12d3-a456-426614174000",
                "allergies": "Penicilina, Dipirona",
                "medications": "Levotiroxina 100mcg, Metformina 500mg",
                "blood_type": "A+",
                "emergency_contact": "Maria Silva - (11) 99999-9999",
                "patient_data": {
                    "insurance": {"provider": "Unimed"},
                    "preferences": {"communication_channel": "whatsapp"},
                },
            }
        }
    )

    phone: str = Field(..., max_length=20, description="Patient phone number (E.164)")
    doctor_id: UUID = Field(..., description="Doctor UUID")


class PatientV2Update(BaseModel):
    """Schema for updating a patient"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone": "(11) 91234-5678",
                "email": "joao.novo@example.com",
                "treatment_type": "Tratamento Personalizado",
                "doctor_notes": "Ajuste de dosagem realizado em 12/02.",
                "medications": "Levotiroxina 125mcg, Metformina 500mg",
                "blood_type": "O+",
            }
        }
    )

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    birth_date: Optional[date] = None
    cpf: Optional[str] = Field(None, max_length=14)
    doctor_id: Optional[UUID] = Field(None, description="Doctor UUID")
    treatment_type: Optional[str] = Field(None, max_length=150)
    treatment_start_date: Optional[date] = None
    doctor_notes: Optional[str] = Field(None, max_length=2000)
    diagnosis: Optional[str] = Field(None, max_length=500)
    treatment_phase: Optional[str] = Field(
        None,
        max_length=100,
        pattern="^(initial|adjustment|maintenance|monitoring|followup|completed|inicial|ajuste|manutenção|monitoramento|acompanhamento|concluído)$"
    )
    flow_state: Optional[FlowState] = None

    # Clinical information fields
    allergies: Optional[str] = Field(None, description="Known allergies (medications, foods)")
    medications: Optional[str] = Field(None, description="Current medications")
    blood_type: Optional[str] = Field(
        None,
        pattern="^(A|B|AB|O)[+-]$",
        description="Blood type (A+, A-, B+, B-, AB+, AB-, O+, O-)"
    )
    emergency_contact: Optional[str] = Field(None, max_length=200, description="Emergency contact information")

    # Metadata JSONB field
    patient_data: Optional[Dict[str, Any]] = Field(None, description="Additional patient metadata")

    @field_validator("cpf")
    @classmethod
    def validate_cpf(cls, v):
        """Validate CPF with check digits verification."""
        if not v:
            return v

        # Check format: only digits, dots, dashes
        if not v.replace(".", "").replace("-", "").isdigit():
            raise ValueError("CPF deve conter apenas dígitos, pontos e traços")

        # Validate check digits
        if not validate_cpf_check_digits(v):
            raise ValueError("CPF inválido: dígitos verificadores incorretos")

        # Clean CPF to store only digits
        return re.sub(r"\D", "", v)

    @field_validator("phone")
    @classmethod
    def validate_phone_format(cls, v):
        """
        Validate phone number and normalize to E.164.

        This validator accepts both formats for v2 API flexibility:
        - E.164 format: +5511987654321
        - Brazilian format: 11987654321, (11) 98765-4321

        The BR_TO_E164 mode standardizes storage to E.164 while
        preserving input flexibility.

        See: app/schemas/validators/phone.py for implementation details
        """
        if not v:
            return v

        from app.schemas.validators.phone import normalize_phone, PhoneValidationMode

        return normalize_phone(v, mode=PhoneValidationMode.BR_TO_E164, allow_none=True)

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
        """Normalize treatment_phase to lowercase."""
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("blood_type", mode="before")
    @classmethod
    def normalize_blood_type(cls, v):
        """Normalize blood type to uppercase."""
        if isinstance(v, str):
            return v.strip().upper()
        return v


class PatientV2Response(PatientV2Base):
    """Full patient response with optional relationships"""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "João Silva",
                "email": "joao@example.com",
                "phone": "(11) 98765-4321",
                "birth_date": "1980-05-15T00:00:00Z",
                "cpf": "123.456.789-00",
                "doctor_id": "223e4567-e89b-12d3-a456-426614174001",
                "created_at": "2025-01-01T10:00:00Z",
                "updated_at": "2025-01-15T14:30:00Z",
                "treatment_type": "Reposição Hormonal",
                "treatment_start_date": "2025-01-10",
                "doctor_notes": "Paciente apresentou boa resposta ao tratamento.",
                "flow_state": "active",
                "current_day": 12,
                "allergies": "Penicilina, Dipirona",
                "medications": "Levotiroxina 100mcg",
                "blood_type": "A+",
                "emergency_contact": "Maria Silva - (11) 99999-9999",
                "patient_data": {"insurance": "Unimed", "preferred_contact": "whatsapp"},
                "doctor": {
                    "id": "223e4567-e89b-12d3-a456-426614174001",
                    "name": "Dr. Maria Santos",
                    "email": "maria@example.com",
                },
            }
        },
    )

    id: UUID
    doctor_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    current_day: Optional[int] = None
    flow_state: Optional[FlowState] = Field(None, description="Patient flow state/status")

    # Optional eager-loaded relationships
    doctor: Optional[DoctorV2Brief] = None
    quiz_sessions: Optional[List[QuizV2Brief]] = None


class PatientV2List(CursorPaginatedResponse[PatientV2Response]):
    """Paginated list of patients"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "name": "João Silva",
                        "email": "joao@example.com",
                        "doctor_id": "223e4567-e89b-12d3-a456-426614174001",
                        "created_at": "2025-01-01T10:00:00Z",
                        "updated_at": "2025-01-15T14:30:00Z",
                    }
                ],
                "next_cursor": "eyJpZCI6IjEyM2U0NTY3LWU4OWItMTJkMy1hNDU2LTQyNjYxNDE3NDAwMCJ9",
                "has_more": True,
                "total": 150,
            }
        }
    )
