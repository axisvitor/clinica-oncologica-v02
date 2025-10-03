from typing import Optional, Dict, Any
from datetime import date
from uuid import UUID
import re

from pydantic import BaseModel, Field, validator

from app.models.patient import FlowState


def validate_cpf(cpf: str) -> bool:
    """Validate Brazilian CPF number with check digits."""
    if not cpf:
        return True  # CPF is optional

    # Remove non-digits
    cpf_clean = re.sub(r'\D', '', cpf)

    # Check length
    if len(cpf_clean) != 11:
        return False

    # Check for known invalid patterns
    if cpf_clean in ['00000000000', '11111111111', '22222222222', '33333333333',
                      '44444444444', '55555555555', '66666666666', '77777777777',
                      '88888888888', '99999999999']:
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
    treatment_start_date: Optional[date] = Field(None, description="Treatment start date")

    # Brazilian healthcare specific fields (now as dedicated columns)
    cpf: Optional[str] = Field(None, description="Brazilian CPF (11 digits)", max_length=11)
    diagnosis: Optional[str] = Field(None, description="Medical diagnosis", max_length=500)
    treatment_phase: Optional[str] = Field(
        None,
        description="Current treatment phase",
        pattern="^(initial|adjustment|maintenance|monitoring|followup|completed)$"
    )
    doctor_notes: Optional[str] = Field(None, description="Doctor's notes about the patient")

    @validator('phone')
    def validate_phone(cls, v):
        # Basic phone validation - can be enhanced
        if not v.startswith('+'):
            raise ValueError('Phone number must start with country code (+)')
        return v

    @validator('cpf')
    def validate_cpf_number(cls, v):
        """Validate Brazilian CPF format and check digits."""
        if v and not validate_cpf(v):
            raise ValueError('Invalid CPF number')
        # Clean CPF to store only digits
        if v:
            v = re.sub(r'\D', '', v)
        return v


class PatientCreate(PatientBase):
    """Schema for creating a patient"""
    # Additional metadata that doesn't fit in dedicated columns
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional patient metadata"
    )


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
        pattern="^(initial|adjustment|maintenance|monitoring|followup|completed)$"
    )
    doctor_notes: Optional[str] = None

    # Additional metadata
    metadata: Optional[Dict[str, Any]] = None

    @validator('phone')
    def validate_phone(cls, v):
        if v and not v.startswith('+'):
            raise ValueError('Phone number must start with country code (+)')
        return v

    @validator('cpf')
    def validate_cpf_number(cls, v):
        """Validate Brazilian CPF format and check digits."""
        if v and not validate_cpf(v):
            raise ValueError('Invalid CPF number')
        # Clean CPF to store only digits
        if v:
            v = re.sub(r'\D', '', v)
        return v


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
        None,
        alias="metadata",
        description="Additional patient metadata"
    )

    class Config:
        from_attributes = True
        populate_by_name = True  # Allow both field name and alias


class PatientListResponse(BaseModel):
    """Schema for patient list response with pagination metadata."""
    data: list[PatientResponse] = Field(..., description="Current page of patients")
    total: int = Field(..., description="Total number of patients matching filters")
    page: int = Field(..., ge=1, description="Current page number")
    limit: int = Field(..., ge=1, description="Number of records per page")
    pages: int = Field(..., ge=0, description="Total page count")
    has_more: bool = Field(..., description="Whether additional pages are available")
    has_previous: bool = Field(..., description="Whether a previous page exists")

    class Config:
        from_attributes = True
