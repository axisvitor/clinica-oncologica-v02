"""
Treatment schemas for API v2
Enhanced treatment models with field selection and eager loading support.
"""

from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field, validator

from .common import CursorPaginatedResponse


class PatientV2Brief(BaseModel):
    """Brief patient information for treatment response"""

    id: str
    name: str
    email: Optional[str] = None

    class Config:
        from_attributes = True


class DoctorV2Brief(BaseModel):
    """Brief doctor information for treatment response"""

    id: str
    name: str
    email: Optional[str] = None

    class Config:
        from_attributes = True


class MedicationV2Brief(BaseModel):
    """Brief medication information for treatment response"""

    id: str
    name: str
    dosage: str
    frequency: str
    is_active: bool

    class Config:
        from_attributes = True


class TreatmentV2Base(BaseModel):
    """Base treatment schema"""

    patient_id: str = Field(..., description="Patient UUID")
    doctor_id: Optional[str] = Field(None, description="Doctor UUID")
    treatment_type: str = Field(..., description="Type of treatment")
    status: str = Field(default="planned", description="Treatment status")
    start_date: Optional[date] = Field(None, description="Treatment start date")
    end_date: Optional[date] = Field(None, description="Treatment end date")
    planned_sessions: Optional[str] = Field(None, max_length=100, description="Planned sessions")
    completed_sessions: Optional[str] = Field(None, max_length=100, description="Completed sessions")
    diagnosis: Optional[str] = Field(None, description="Diagnosis")
    protocol: Optional[str] = Field(None, max_length=200, description="Treatment protocol")
    notes: Optional[str] = Field(None, description="Additional notes")
    is_active: bool = Field(default=True, description="Active status")


class TreatmentV2Create(TreatmentV2Base):
    """Schema for creating a treatment"""

    patient_id: str = Field(..., description="Patient UUID")
    treatment_type: str = Field(..., description="quimioterapia|radioterapia|hormonioterapia|imunoterapia|cirurgia|outros")
    start_date: date = Field(..., description="Treatment start date")

    @validator("treatment_type")
    def validate_treatment_type(cls, v):
        valid_types = ["quimioterapia", "radioterapia", "hormonioterapia", "imunoterapia", "cirurgia", "outros"]
        if v not in valid_types:
            raise ValueError(f"treatment_type must be one of: {', '.join(valid_types)}")
        return v

    @validator("status")
    def validate_status(cls, v):
        valid_statuses = ["planned", "active", "completed", "suspended", "cancelled"]
        if v and v not in valid_statuses:
            raise ValueError(f"status must be one of: {', '.join(valid_statuses)}")
        return v or "planned"

    @validator("end_date")
    def validate_end_date(cls, v, values):
        if v and "start_date" in values and v < values["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "doctor_id": "123e4567-e89b-12d3-a456-426614174001",
                "treatment_type": "hormonioterapia",
                "status": "planned",
                "start_date": "2025-11-10",
                "end_date": "2026-05-10",
                "planned_sessions": "12 sessões",
                "diagnosis": "Câncer de próstata hormônio-dependente",
                "protocol": "ADT (Androgen Deprivation Therapy)",
                "notes": "Paciente em bom estado geral"
            }
        }


class TreatmentV2Update(BaseModel):
    """Schema for updating a treatment"""

    doctor_id: Optional[str] = Field(None, description="Doctor UUID")
    treatment_type: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    planned_sessions: Optional[str] = Field(None, max_length=100)
    completed_sessions: Optional[str] = Field(None, max_length=100)
    diagnosis: Optional[str] = None
    protocol: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None
    is_active: Optional[bool] = None

    @validator("treatment_type")
    def validate_treatment_type(cls, v):
        if v:
            valid_types = ["quimioterapia", "radioterapia", "hormonioterapia", "imunoterapia", "cirurgia", "outros"]
            if v not in valid_types:
                raise ValueError(f"treatment_type must be one of: {', '.join(valid_types)}")
        return v

    @validator("status")
    def validate_status(cls, v):
        if v:
            valid_statuses = ["planned", "active", "completed", "suspended", "cancelled"]
            if v not in valid_statuses:
                raise ValueError(f"status must be one of: {', '.join(valid_statuses)}")
        return v


class TreatmentV2Response(BaseModel):
    """Schema for treatment response"""

    id: str
    patient_id: str
    doctor_id: Optional[str] = None
    treatment_type: str
    status: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    planned_sessions: Optional[str] = None
    completed_sessions: Optional[str] = None
    diagnosis: Optional[str] = None
    protocol: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Optional relationships (included based on query params)
    patient: Optional[PatientV2Brief] = None
    doctor: Optional[DoctorV2Brief] = None
    medications: Optional[List[MedicationV2Brief]] = None

    class Config:
        from_attributes = True


class TreatmentV2List(CursorPaginatedResponse):
    """Paginated list of treatments"""

    items: List[TreatmentV2Response]
