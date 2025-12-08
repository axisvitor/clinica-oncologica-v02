"""
Medication schemas for API v2
Enhanced medication models with field selection and eager loading support.
"""

from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, ConfigDict

from .common import CursorPaginatedResponse


class PatientV2Brief(BaseModel):
    """Brief patient information for medication response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: Optional[str] = None


class PrescribedByV2Brief(BaseModel):
    """Brief prescriber information for medication response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: Optional[str] = None


class TreatmentV2Brief(BaseModel):
    """Brief treatment information for medication response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    treatment_type: str
    status: str
    start_date: Optional[date] = None


class MedicationV2Base(BaseModel):
    """Base medication schema"""

    patient_id: str = Field(..., description="Patient UUID")
    prescribed_by_id: Optional[str] = Field(None, description="Prescriber UUID")
    treatment_id: Optional[str] = Field(None, description="Treatment UUID")
    name: str = Field(..., min_length=1, max_length=200, description="Medication name")
    active_ingredient: Optional[str] = Field(None, max_length=200, description="Active ingredient")
    dosage: str = Field(..., min_length=1, max_length=100, description="Dosage")
    frequency: str = Field(..., min_length=1, max_length=100, description="Frequency")
    route: Optional[str] = Field(None, max_length=50, description="Route of administration")
    prescription_date: date = Field(..., description="Prescription date")
    start_date: date = Field(..., description="Start date")
    end_date: Optional[date] = Field(None, description="End date")
    quantity: Optional[Decimal] = Field(None, ge=0, description="Quantity")
    refills_allowed: int = Field(default=0, ge=0, description="Refills allowed")
    refills_remaining: int = Field(default=0, ge=0, description="Refills remaining")
    instructions: Optional[str] = Field(None, description="Instructions")
    warnings: Optional[str] = Field(None, description="Warnings")
    side_effects: Optional[str] = Field(None, description="Side effects")
    is_active: bool = Field(default=True, description="Active status")
    discontinued_date: Optional[date] = Field(None, description="Discontinuation date")
    discontinuation_reason: Optional[str] = Field(None, description="Discontinuation reason")


class MedicationV2Create(MedicationV2Base):
    """Schema for creating a medication"""

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "prescribed_by_id": "123e4567-e89b-12d3-a456-426614174001",
                "treatment_id": "123e4567-e89b-12d3-a456-426614174002",
                "name": "Anastrozol",
                "active_ingredient": "Anastrozole",
                "dosage": "1mg",
                "frequency": "1x ao dia",
                "route": "oral",
                "prescription_date": "2025-11-07",
                "start_date": "2025-11-08",
                "end_date": "2026-11-08",
                "quantity": "30",
                "refills_allowed": 12,
                "refills_remaining": 12,
                "instructions": "Tomar 1 comprimido pela manhã, após o café",
                "warnings": "Não usar se estiver grávida",
                "side_effects": "Podem ocorrer ondas de calor, dor nas articulações"
            }
        })

    patient_id: str = Field(..., description="Patient UUID")
    name: str = Field(..., min_length=1, max_length=200, description="Medication name")
    dosage: str = Field(..., description="e.g., '50mg', '2 comprimidos'")
    frequency: str = Field(..., description="e.g., '1x ao dia', 'a cada 8 horas'")
    prescription_date: date = Field(..., description="Prescription date")
    start_date: date = Field(..., description="Start date")

    @field_validator("route")
    @classmethod
    def validate_route(cls, v):
        if v:
            valid_routes = ["oral", "intravenous", "topical", "subcutaneous", "intramuscular", "inhalation", "other"]
            if v and v not in valid_routes:
                raise ValueError(f"route must be one of: {', '.join(valid_routes)}")
        return v

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v, info):
        if v and "start_date" in info.data and v < info.data["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v

    @field_validator("refills_remaining")
    @classmethod
    def validate_refills_remaining(cls, v, info):
        if "refills_allowed" in info.data and v > info.data["refills_allowed"]:
            raise ValueError("refills_remaining cannot exceed refills_allowed")
        return v


class MedicationV2Update(BaseModel):
    """Schema for updating a medication"""

    prescribed_by_id: Optional[str] = Field(None, description="Prescriber UUID")
    treatment_id: Optional[str] = Field(None, description="Treatment UUID")
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    active_ingredient: Optional[str] = Field(None, max_length=200)
    dosage: Optional[str] = Field(None, min_length=1, max_length=100)
    frequency: Optional[str] = Field(None, min_length=1, max_length=100)
    route: Optional[str] = Field(None, max_length=50)
    prescription_date: Optional[date] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    quantity: Optional[Decimal] = Field(None, ge=0)
    refills_allowed: Optional[int] = Field(None, ge=0)
    refills_remaining: Optional[int] = Field(None, ge=0)
    instructions: Optional[str] = None
    warnings: Optional[str] = None
    side_effects: Optional[str] = None
    is_active: Optional[bool] = None
    discontinued_date: Optional[date] = None
    discontinuation_reason: Optional[str] = None

    @field_validator("route")
    @classmethod
    def validate_route(cls, v):
        if v:
            valid_routes = ["oral", "intravenous", "topical", "subcutaneous", "intramuscular", "inhalation", "other"]
            if v not in valid_routes:
                raise ValueError(f"route must be one of: {', '.join(valid_routes)}")
        return v


class MedicationV2Response(BaseModel):
    """Schema for medication response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    prescribed_by_id: Optional[str] = None
    treatment_id: Optional[str] = None
    name: str
    active_ingredient: Optional[str] = None
    dosage: str
    frequency: str
    route: Optional[str] = None
    prescription_date: date
    start_date: date
    end_date: Optional[date] = None
    quantity: Optional[Decimal] = None
    refills_allowed: int
    refills_remaining: int
    instructions: Optional[str] = None
    warnings: Optional[str] = None
    side_effects: Optional[str] = None
    is_active: bool
    discontinued_date: Optional[date] = None
    discontinuation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Optional relationships (included based on query params)
    patient: Optional[PatientV2Brief] = None
    prescribed_by: Optional[PrescribedByV2Brief] = None
    treatment: Optional[TreatmentV2Brief] = None


class MedicationV2List(CursorPaginatedResponse):
    """Paginated list of medications"""

    items: List[MedicationV2Response]
