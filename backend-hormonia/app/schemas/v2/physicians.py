"""
Physicians schemas for API v2
Enhanced physician models with statistics, workload tracking, and patient assignments.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict
from enum import Enum

from .common import CursorPaginatedResponse
from app.utils.timezone import now_sao_paulo_naive


class PhysicianStatus(str, Enum):
    """Physician availability status"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"
    RETIRED = "retired"


class WorkloadLevel(str, Enum):
    """Physician workload classification"""

    LOW = "low"  # 0-20 patients
    MEDIUM = "medium"  # 21-50 patients
    HIGH = "high"  # 51-100 patients
    OVERLOADED = "overloaded"  # 100+ patients


class Specialty(str, Enum):
    """Medical specialties"""

    ONCOLOGY = "oncology"
    CARDIOLOGY = "cardiology"
    ENDOCRINOLOGY = "endocrinology"
    GENERAL_PRACTICE = "general_practice"
    GYNECOLOGY = "gynecology"
    HEMATOLOGY = "hematology"
    OTHER = "other"


# ============================================================================
# Statistics Models
# ============================================================================


class MessageStats(BaseModel):
    """Message statistics for physician"""

    total_sent: int = Field(0, description="Total messages sent")
    total_received: int = Field(0, description="Total messages received")
    unread_count: int = Field(0, description="Unread messages")
    response_rate: float = Field(0.0, ge=0.0, le=1.0, description="Response rate (0-1)")
    avg_response_time_minutes: Optional[float] = Field(
        None, description="Average response time in minutes"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_sent": 245,
                "total_received": 312,
                "unread_count": 8,
                "response_rate": 0.87,
                "avg_response_time_minutes": 45.2,
            }
        }
    )


class AppointmentStats(BaseModel):
    """Appointment statistics for physician"""

    total_scheduled: int = Field(0, description="Total appointments scheduled")
    completed: int = Field(0, description="Completed appointments")
    cancelled: int = Field(0, description="Cancelled appointments")
    upcoming: int = Field(0, description="Upcoming appointments")
    today: int = Field(0, description="Appointments today")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_scheduled": 156,
                "completed": 142,
                "cancelled": 8,
                "upcoming": 6,
                "today": 3,
            }
        }
    )


class AlertStats(BaseModel):
    """Alert statistics for physician's patients"""

    total: int = Field(0, description="Total active alerts")
    critical: int = Field(0, description="Critical severity alerts")
    high: int = Field(0, description="High severity alerts")
    medium: int = Field(0, description="Medium severity alerts")
    low: int = Field(0, description="Low severity alerts")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"total": 15, "critical": 2, "high": 5, "medium": 6, "low": 2}
        }
    )


class PhysicianStatistics(BaseModel):
    """Comprehensive physician statistics"""

    # Patient metrics
    total_patients: int = Field(0, description="Total assigned patients")
    active_patients: int = Field(0, description="Active patients")
    inactive_patients: int = Field(0, description="Inactive patients")
    new_patients_this_month: int = Field(0, description="New patients this month")

    # Workload
    workload_level: WorkloadLevel = Field(
        WorkloadLevel.LOW, description="Current workload level"
    )

    # Communication
    messages: MessageStats = Field(
        default_factory=MessageStats, description="Message statistics"
    )

    # Appointments
    appointments: AppointmentStats = Field(
        default_factory=AppointmentStats, description="Appointment statistics"
    )

    # Alerts
    alerts: AlertStats = Field(
        default_factory=AlertStats, description="Alert statistics"
    )

    # Performance
    patient_satisfaction_score: Optional[float] = Field(
        None, ge=0.0, le=5.0, description="Patient satisfaction (0-5)"
    )
    avg_treatment_duration_days: Optional[float] = Field(
        None, description="Average treatment duration"
    )

    # Timestamps
    calculated_at: datetime = Field(
        default_factory=now_sao_paulo_naive, description="When stats were calculated"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_patients": 45,
                "active_patients": 38,
                "inactive_patients": 7,
                "new_patients_this_month": 3,
                "workload_level": "medium",
                "messages": {
                    "total_sent": 245,
                    "total_received": 312,
                    "unread_count": 8,
                    "response_rate": 0.87,
                    "avg_response_time_minutes": 45.2,
                },
                "appointments": {
                    "total_scheduled": 156,
                    "completed": 142,
                    "cancelled": 8,
                    "upcoming": 6,
                    "today": 3,
                },
                "alerts": {
                    "total": 15,
                    "critical": 2,
                    "high": 5,
                    "medium": 6,
                    "low": 2,
                },
                "patient_satisfaction_score": 4.5,
                "avg_treatment_duration_days": 87.3,
                "calculated_at": "2025-11-07T12:00:00-03:00",
            }
        }
    )


# ============================================================================
# Physician Models
# ============================================================================


class PhysicianBase(BaseModel):
    """Base physician schema"""

    full_name: Optional[str] = Field(
        None, min_length=1, max_length=255, description="Full name"
    )
    email: Optional[EmailStr] = Field(None, description="Email address")
    specialties: Optional[List[Specialty]] = Field(
        None, description="Medical specialties"
    )
    status: Optional[PhysicianStatus] = Field(
        PhysicianStatus.ACTIVE, description="Current status"
    )
    license_number: Optional[str] = Field(
        None, max_length=50, description="Medical license number (CRM)"
    )
    phone: Optional[str] = Field(None, max_length=20, description="Contact phone")
    bio: Optional[str] = Field(
        None, max_length=1000, description="Professional biography"
    )

    @field_validator("license_number")
    @classmethod
    def validate_license_number(cls, v):
        """Validate CRM format (Brazilian medical license)"""
        if v and not v.replace("-", "").replace("/", "").isalnum():
            raise ValueError(
                "License number must contain only letters, numbers, dashes, and slashes"
            )
        return v


class PhysicianResponse(BaseModel):
    """Full physician response"""

    id: str = Field(..., description="Physician UUID")
    email: str = Field(..., description="Email address")
    full_name: Optional[str] = Field(None, description="Full name")
    role: str = Field("doctor", description="User role")
    is_active: bool = Field(True, description="Account active status")

    # Firebase fields
    firebase_uid: Optional[str] = Field(None, description="Firebase UID")
    firebase_email_verified: bool = Field(False, description="Email verified status")
    firebase_display_name: Optional[str] = Field(
        None, description="Firebase display name"
    )
    firebase_photo_url: Optional[str] = Field(None, description="Profile photo URL")

    # Professional info
    specialties: List[Specialty] = Field(
        default_factory=list, description="Medical specialties"
    )
    status: PhysicianStatus = Field(
        PhysicianStatus.ACTIVE, description="Current status"
    )
    license_number: Optional[str] = Field(None, description="Medical license (CRM)")
    phone: Optional[str] = Field(None, description="Contact phone")
    bio: Optional[str] = Field(None, description="Professional bio")

    # Patient assignment
    assigned_patients_count: int = Field(0, description="Number of assigned patients")
    active_patients_count: int = Field(0, description="Number of active patients")
    workload_level: WorkloadLevel = Field(
        WorkloadLevel.LOW, description="Current workload"
    )

    # Statistics (optional, included when ?include=statistics)
    statistics: Optional[PhysicianStatistics] = Field(
        None, description="Detailed statistics"
    )

    # Timestamps
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "dr.maria@clinic.com",
                "full_name": "Dr. Maria Santos",
                "role": "doctor",
                "is_active": True,
                "firebase_email_verified": True,
                "specialties": ["oncology", "endocrinology"],
                "status": "active",
                "license_number": "CRM/SP-123456",
                "phone": "+55 11 98765-4321",
                "assigned_patients_count": 45,
                "active_patients_count": 38,
                "workload_level": "medium",
                "created_at": "2024-01-15T10:00:00-03:00",
                "updated_at": "2025-11-07T12:00:00-03:00",
                "last_login": "2025-11-07T08:30:00-03:00",
            }
        },
    )


class PhysicianUpdate(BaseModel):
    """Schema for updating physician information"""

    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    specialties: Optional[List[Specialty]] = None
    status: Optional[PhysicianStatus] = None
    license_number: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    bio: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Dr. Maria Santos Silva",
                "specialties": ["oncology", "endocrinology"],
                "phone": "+55 11 98765-4321",
                "bio": "Especialista em oncologia com 15 anos de experiência",
            }
        }
    )


class PhysicianList(CursorPaginatedResponse[PhysicianResponse]):
    """Paginated list of physicians"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "email": "dr.maria@clinic.com",
                        "full_name": "Dr. Maria Santos",
                        "role": "doctor",
                        "is_active": True,
                        "specialties": ["oncology"],
                        "status": "active",
                        "assigned_patients_count": 45,
                        "active_patients_count": 38,
                        "workload_level": "medium",
                        "created_at": "2024-01-15T10:00:00-03:00",
                        "updated_at": "2025-11-07T12:00:00-03:00",
                    }
                ],
                "next_cursor": "eyJpZCI6IjEyM2U0NTY3LWU4OWItMTJkMy1hNDU2LTQyNjYxNDE3NDAwMCJ9",
                "has_more": True,
                "total": 12,
            }
        }
    )


# ============================================================================
# Filter Models
# ============================================================================


class PhysicianFilter(BaseModel):
    """Physician filtering parameters"""

    specialty: Optional[Specialty] = Field(None, description="Filter by specialty")
    status: Optional[PhysicianStatus] = Field(None, description="Filter by status")
    workload: Optional[WorkloadLevel] = Field(
        None, description="Filter by workload level"
    )
    min_patients: Optional[int] = Field(None, ge=0, description="Minimum patient count")
    max_patients: Optional[int] = Field(None, ge=0, description="Maximum patient count")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    search: Optional[str] = Field(
        None, min_length=1, description="Search by name or email"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "specialty": "oncology",
                "status": "active",
                "workload": "medium",
                "min_patients": 10,
                "max_patients": 50,
                "is_active": True,
                "search": "maria",
            }
        }
    )


# ============================================================================
# Brief Models (for relationships)
# ============================================================================


class PhysicianBrief(BaseModel):
    """Brief physician information for use in other resources"""

    id: str
    full_name: Optional[str]
    email: str
    specialties: List[Specialty] = Field(default_factory=list)
    license_number: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "full_name": "Dr. Maria Santos",
                "email": "dr.maria@clinic.com",
                "specialties": ["oncology"],
                "license_number": "CRM/SP-123456",
            }
        },
    )
