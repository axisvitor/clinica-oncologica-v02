"""
Patient schemas for API v2
Enhanced patient models with field selection and eager loading support.
"""

import re
from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict

from .common import CursorPaginatedResponse

# Import robust CPF validator from v1 schema
from app.schemas.patient import validate_cpf as validate_cpf_check_digits


class DoctorV2Brief(BaseModel):
    """Brief doctor information for patient response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: Optional[str] = None


class QuizV2Brief(BaseModel):
    """Brief quiz session information for patient response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
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
    treatment_phase: Optional[str] = Field(None, max_length=100)
    timezone: str = Field(
        "America/Sao_Paulo", description="Patient timezone (e.g., America/Sao_Paulo)"
    )

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

        return v

    @field_validator("phone")
    @classmethod
    def validate_phone_format(cls, v):
        """Validate phone number for E.164 or Brazilian format."""
        if not v:
            return v

        # Remove common formatting characters
        cleaned = re.sub(r"[\s\-\(\)]", "", v)

        # Check if it's E.164 format (starts with +)
        if cleaned.startswith("+"):
            # E.164 should be 10-15 digits after the +
            digits_only = cleaned[1:]
            if not digits_only.isdigit():
                raise ValueError("Telefone E.164 deve conter apenas + e dígitos")
            if len(digits_only) < 10 or len(digits_only) > 15:
                raise ValueError("Telefone E.164 deve ter entre 10-15 dígitos")
            return cleaned  # Return normalized E.164

        # Brazilian format (without +55)
        digits_only = re.sub(r"\D", "", v)
        if len(digits_only) < 10 or len(digits_only) > 11:
            raise ValueError(
                "Telefone brasileiro deve ter 10-11 dígitos (DDD + número)"
            )

        # Return original format for backwards compatibility
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
            }
        }
    )

    phone: str = Field(..., max_length=20, description="Patient phone number (E.164)")
    doctor_id: str = Field(..., description="Doctor UUID")


class PatientV2Update(BaseModel):
    """Schema for updating a patient"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone": "(11) 91234-5678",
                "email": "joao.novo@example.com",
                "treatment_type": "Tratamento Personalizado",
                "doctor_notes": "Ajuste de dosagem realizado em 12/02.",
            }
        }
    )

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    birth_date: Optional[date] = None
    cpf: Optional[str] = Field(None, max_length=14)
    doctor_id: Optional[str] = Field(None, description="Doctor UUID")
    treatment_type: Optional[str] = Field(None, max_length=150)
    treatment_start_date: Optional[date] = None
    doctor_notes: Optional[str] = Field(None, max_length=2000)
    diagnosis: Optional[str] = Field(None, max_length=500)
    treatment_phase: Optional[str] = Field(None, max_length=100)


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
                "doctor": {
                    "id": "223e4567-e89b-12d3-a456-426614174001",
                    "name": "Dr. Maria Santos",
                    "email": "maria@example.com",
                },
            }
        },
    )

    id: str
    doctor_id: str
    created_at: datetime
    updated_at: datetime
    current_day: Optional[int] = None
    flow_state: Optional[str] = Field(None, description="Patient flow state/status")

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
