"""
Pydantic models for physician-specific endpoints.

These models are used for API responses and requests specific to physician workflows,
including risk assessments, patient dashboards, and aggregated views.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from uuid import UUID


class RiskAssessment(BaseModel):
    """Individual risk assessment for a specific category."""

    category: str = Field(
        ...,
        description="Risk category (medication_adherence, vital_signs, symptoms, etc.)",
    )
    risk_level: str = Field(..., description="Risk level: low, medium, high, critical")
    severity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Numeric severity score from 0.0 (no risk) to 1.0 (critical)",
    )
    last_updated: datetime = Field(
        ..., description="When this assessment was last calculated"
    )
    description: Optional[str] = Field(
        None, description="Human-readable description of the risk"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "category": "medication_adherence",
                "risk_level": "high",
                "severity_score": 0.75,
                "last_updated": "2025-10-06T14:30:00-03:00",
                "description": "Patient has missed 3 consecutive medication doses",
            }
        }
    )


class PatientRiskProfile(BaseModel):
    """Complete risk profile for a single patient."""

    patient_id: UUID = Field(..., description="Patient unique identifier")
    patient_name: str = Field(..., description="Patient full name")
    overall_risk: str = Field(
        ..., description="Overall risk level: low, medium, high, critical"
    )
    risk_score: float = Field(
        ..., ge=0.0, le=1.0, description="Calculated overall risk score (0.0 - 1.0)"
    )
    assessments: List[RiskAssessment] = Field(
        default_factory=list,
        description="List of individual risk assessments by category",
    )
    alert_count: int = Field(
        ..., ge=0, description="Number of active unresolved alerts"
    )
    last_assessment: datetime = Field(
        ..., description="When the last assessment was performed"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "patient_name": "João Silva",
                "overall_risk": "high",
                "risk_score": 0.65,
                "assessments": [
                    {
                        "category": "medication_adherence",
                        "risk_level": "high",
                        "severity_score": 0.75,
                        "last_updated": "2025-10-06T14:30:00-03:00",
                        "description": "Missed doses detected",
                    }
                ],
                "alert_count": 3,
                "last_assessment": "2025-10-06T14:30:00-03:00",
            }
        }
    )


class RiskAssessmentsResponse(BaseModel):
    """Response containing aggregated risk assessments for multiple patients."""

    patients: List[PatientRiskProfile] = Field(
        ..., description="List of patient risk profiles"
    )
    total_count: int = Field(..., ge=0, description="Total number of patients")
    high_risk_count: int = Field(
        ..., ge=0, description="Number of patients with high or critical risk"
    )
    timestamp: str = Field(
        ..., description="When this response was generated (ISO 8601)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patients": [
                    {
                        "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                        "patient_name": "João Silva",
                        "overall_risk": "high",
                        "risk_score": 0.65,
                        "assessments": [],
                        "alert_count": 3,
                        "last_assessment": "2025-10-06T14:30:00-03:00",
                    }
                ],
                "total_count": 50,
                "high_risk_count": 8,
                "timestamp": "2025-10-06T14:30:00-03:00",
            }
        }
    )
