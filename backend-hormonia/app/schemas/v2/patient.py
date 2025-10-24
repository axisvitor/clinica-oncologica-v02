"""
Patient schemas for API v2
Enhanced patient models with field selection and eager loading support.
"""

from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, Field, EmailStr, validator

from .common import CursorPaginatedResponse


class DoctorV2Brief(BaseModel):
    """Brief doctor information for patient response"""
    
    id: str
    name: str
    email: Optional[str] = None
    
    class Config:
        from_attributes = True


class QuizV2Brief(BaseModel):
    """Brief quiz session information for patient response"""
    
    id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    score: Optional[float] = None
    passed: Optional[bool] = None
    
    class Config:
        from_attributes = True


class PatientV2Base(BaseModel):
    """Base patient schema"""
    
    name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    birth_date: Optional[date] = None
    cpf: Optional[str] = Field(None, max_length=14)
    
    @validator("cpf")
    def validate_cpf(cls, v):
        if v and not v.replace(".", "").replace("-", "").isdigit():
            raise ValueError("CPF must contain only digits, dots, and dashes")
        return v


class PatientV2Create(PatientV2Base):
    """Schema for creating a patient"""
    
    doctor_id: str = Field(..., description="Doctor UUID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "João Silva",
                "email": "joao@example.com",
                "phone": "(11) 98765-4321",
                "birth_date": "1980-05-15T00:00:00Z",
                "cpf": "123.456.789-00",
                "doctor_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }


class PatientV2Update(BaseModel):
    """Schema for updating a patient"""
    
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    birth_date: Optional[date] = None
    cpf: Optional[str] = Field(None, max_length=14)
    doctor_id: Optional[str] = Field(None, description="Doctor UUID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "phone": "(11) 91234-5678",
                "email": "joao.novo@example.com"
            }
        }


class PatientV2Response(PatientV2Base):
    """Full patient response with optional relationships"""
    
    id: str
    doctor_id: str
    created_at: datetime
    updated_at: datetime
    
    # Optional eager-loaded relationships
    doctor: Optional[DoctorV2Brief] = None
    quiz_sessions: Optional[List[QuizV2Brief]] = None
    
    class Config:
        from_attributes = True
        json_schema_extra = {
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
                "doctor": {
                    "id": "223e4567-e89b-12d3-a456-426614174001",
                    "name": "Dr. Maria Santos",
                    "email": "maria@example.com"
                }
            }
        }


class PatientV2List(CursorPaginatedResponse[PatientV2Response]):
    """Paginated list of patients"""
    
    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "name": "João Silva",
                        "email": "joao@example.com",
                        "doctor_id": "223e4567-e89b-12d3-a456-426614174001",
                        "created_at": "2025-01-01T10:00:00Z",
                        "updated_at": "2025-01-15T14:30:00Z"
                    }
                ],
                "next_cursor": "eyJpZCI6IjEyM2U0NTY3LWU4OWItMTJkMy1hNDU2LTQyNjYxNDE3NDAwMCJ9",
                "has_more": True,
                "total": 150
            }
        }
