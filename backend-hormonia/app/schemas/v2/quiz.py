"""
Quiz schemas for API v2
Enhanced quiz models with field selection and eager loading support.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator

from .common import CursorPaginatedResponse


class PatientV2Brief(BaseModel):
    """Brief patient information for quiz response"""
    
    id: str  # UUID as string
    name: str
    email: str
    
    class Config:
        from_attributes = True


class QuizV2Base(BaseModel):
    """Base quiz schema"""
    
    status: str = Field(default="started")
    
    @validator("status")
    def validate_status(cls, v):
        allowed = {"started", "completed", "cancelled"}
        if v not in allowed:
            raise ValueError(f"Status must be one of: {allowed}")
        return v


class QuizV2Create(QuizV2Base):
    """Schema for creating a quiz session"""
    
    patient_id: str = Field(..., description="Patient UUID")
    quiz_template_id: str = Field(..., description="Quiz template UUID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "quiz_template_id": "223e4567-e89b-12d3-a456-426614174001",
                "status": "started"
            }
        }


class QuizV2Update(BaseModel):
    """Schema for updating a quiz session"""
    
    status: Optional[str] = None
    score: Optional[float] = None
    max_score: Optional[float] = None
    passed: Optional[bool] = None
    completed_at: Optional[datetime] = None
    
    @validator("status")
    def validate_status(cls, v):
        if v is not None:
            allowed = {"started", "completed", "cancelled"}
            if v not in allowed:
                raise ValueError(f"Status must be one of: {allowed}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "completed",
                "score": 85.5,
                "max_score": 100.0,
                "passed": True,
                "completed_at": "2025-01-17T15:00:00Z"
            }
        }


class QuizV2Response(QuizV2Base):
    """Full quiz session response with optional relationships"""
    
    id: str
    patient_id: str
    quiz_template_id: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime
    completed_at: Optional[datetime] = None
    score: Optional[float] = None
    max_score: Optional[float] = None
    passed: Optional[bool] = None
    
    # Optional eager-loaded relationships
    patient: Optional[PatientV2Brief] = None
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "456e4567-e89b-12d3-a456-426614174002",
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "quiz_template_id": "223e4567-e89b-12d3-a456-426614174001",
                "status": "completed",
                "created_at": "2025-01-01T10:00:00Z",
                "updated_at": "2025-01-17T15:00:00Z",
                "started_at": "2025-01-01T10:00:00Z",
                "completed_at": "2025-01-17T15:00:00Z",
                "score": 85.5,
                "max_score": 100.0,
                "passed": True,
                "patient": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "João Silva",
                    "email": "joao@example.com"
                }
            }
        }


class QuizV2List(CursorPaginatedResponse[QuizV2Response]):
    """Paginated list of quizzes"""
    
    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {
                        "id": "456e4567-e89b-12d3-a456-426614174002",
                        "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                        "quiz_template_id": "223e4567-e89b-12d3-a456-426614174001",
                        "status": "completed",
                        "created_at": "2025-01-01T10:00:00Z",
                        "updated_at": "2025-01-17T15:00:00Z",
                        "started_at": "2025-01-01T10:00:00Z",
                        "completed_at": "2025-01-17T15:00:00Z"
                    }
                ],
                "next_cursor": "eyJpZCI6IjQ1NmU0NTY3LWU4OWItMTJkMy1hNDU2LTQyNjYxNDE3NDAwMiJ9",
                "has_more": True,
                "total": 75
            }
        }
