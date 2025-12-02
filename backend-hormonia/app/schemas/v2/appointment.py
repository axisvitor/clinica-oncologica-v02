"""
Appointment schemas for API v2
Enhanced appointment models with field selection and eager loading support.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict

from .common import CursorPaginatedResponse


class PatientV2Brief(BaseModel):
    """Brief patient information for appointment response"""

    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PractitionerV2Brief(BaseModel):
    """Brief practitioner information for appointment response"""

    id: str
    name: str
    email: Optional[str] = None
    specialty: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AppointmentV2Base(BaseModel):
    """Base appointment schema"""

    patient_id: str = Field(..., description="Patient UUID")
    practitioner_id: Optional[str] = Field(None, description="Practitioner UUID")
    appointment_type: str = Field(..., max_length=50, description="Type of appointment")
    status: str = Field(default="scheduled", max_length=50, description="Appointment status")
    scheduled_at: Optional[datetime] = Field(None, description="Scheduled date and time")
    duration_minutes: Optional[int] = Field(None, ge=1, le=480, description="Duration in minutes")
    pre_appointment_notes: Optional[str] = Field(None, description="Notes before appointment")
    post_appointment_notes: Optional[str] = Field(None, description="Notes after appointment")


class AppointmentV2Create(AppointmentV2Base):
    """Schema for creating an appointment"""

    patient_id: str = Field(..., description="Patient UUID")
    appointment_type: str = Field(..., description="consultation|followup|treatment|exam|emergency|telemedicine")
    scheduled_at: datetime = Field(..., description="Scheduled date and time")
    duration_minutes: int = Field(default=30, ge=15, le=480, description="Duration in minutes")

    @field_validator("appointment_type")
    @classmethod
    def validate_appointment_type(cls, v):
        valid_types = ["consultation", "followup", "treatment", "exam", "emergency", "telemedicine"]
        if v not in valid_types:
            raise ValueError(f"appointment_type must be one of: {', '.join(valid_types)}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid_statuses = ["scheduled", "confirmed", "in_progress", "completed", "cancelled", "no_show"]
        if v and v not in valid_statuses:
            raise ValueError(f"status must be one of: {', '.join(valid_statuses)}")
        return v or "scheduled"

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "practitioner_id": "123e4567-e89b-12d3-a456-426614174001",
                "appointment_type": "consultation",
                "status": "scheduled",
                "scheduled_at": "2025-11-10T10:00:00Z",
                "duration_minutes": 30,
                "pre_appointment_notes": "First consultation for new patient"
            }
        }
    )


class AppointmentV2Update(BaseModel):
    """Schema for updating an appointment"""

    practitioner_id: Optional[str] = Field(None, description="Practitioner UUID")
    appointment_type: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = Field(None, max_length=50)
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=1, le=480)
    pre_appointment_notes: Optional[str] = None
    post_appointment_notes: Optional[str] = None

    @field_validator("appointment_type")
    @classmethod
    def validate_appointment_type(cls, v):
        if v:
            valid_types = ["consultation", "followup", "treatment", "exam", "emergency", "telemedicine"]
            if v not in valid_types:
                raise ValueError(f"appointment_type must be one of: {', '.join(valid_types)}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v:
            valid_statuses = ["scheduled", "confirmed", "in_progress", "completed", "cancelled", "no_show"]
            if v not in valid_statuses:
                raise ValueError(f"status must be one of: {', '.join(valid_statuses)}")
        return v


class AppointmentV2Response(BaseModel):
    """Schema for appointment response"""

    id: str
    patient_id: str
    practitioner_id: Optional[str] = None
    appointment_type: str
    status: str
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    cancelled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    pre_appointment_notes: Optional[str] = None
    post_appointment_notes: Optional[str] = None
    reminder_sent: bool = False
    confirmation_sent: bool = False
    created_at: datetime
    updated_at: datetime

    # Optional relationships (included based on query params)
    patient: Optional[PatientV2Brief] = None
    practitioner: Optional[PractitionerV2Brief] = None

    model_config = ConfigDict(from_attributes=True)


class AppointmentV2List(CursorPaginatedResponse):
    """Paginated list of appointments"""

    items: List[AppointmentV2Response]
