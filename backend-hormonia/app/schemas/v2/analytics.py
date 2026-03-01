"""
Analytics schemas for API v2
Response models for analytics endpoints.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class AnalyticsOverview(BaseModel):
    """Overall system analytics overview."""

    total_patients: int = Field(..., description="Total active patients")
    total_quizzes: int = Field(..., description="Total quizzes sent")
    completed_quizzes: int = Field(..., description="Completed quizzes")
    completion_rate: float = Field(
        ..., ge=0, le=100, description="Completion rate percentage"
    )
    active_patients_30d: int = Field(..., description="Active patients in last 30 days")
    period: Dict[str, Optional[str]] = Field(
        ..., description="Date range for filtering"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_patients": 150,
                "total_quizzes": 450,
                "completed_quizzes": 380,
                "completion_rate": 84.44,
                "active_patients_30d": 120,
                "period": {
                    "start_date": "2025-01-01T00:00:00-03:00",
                    "end_date": "2025-01-31T23:59:59-03:00",
                },
            }
        }
    )


class QuizStatusDistribution(BaseModel):
    """Quiz status distribution statistics."""

    distribution: Dict[str, int] = Field(..., description="Count by status")
    total: int = Field(..., description="Total quizzes")
    filters: Dict[str, Optional[int]] = Field(..., description="Applied filters")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "distribution": {"started": 45, "completed": 380, "cancelled": 25},
                "total": 450,
                "filters": {"month": 1, "year": 2025},
            }
        }
    )


class CompletionTrendPoint(BaseModel):
    """Single point in completion trend time series."""

    year: int = Field(..., description="Year")
    month: int = Field(..., ge=1, le=12, description="Month (1-12)")
    total: int = Field(..., description="Total quizzes")
    completed: int = Field(..., description="Completed quizzes")
    completion_rate: float = Field(
        ..., ge=0, le=100, description="Completion rate percentage"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "year": 2025,
                "month": 1,
                "total": 75,
                "completed": 63,
                "completion_rate": 84.0,
            }
        }
    )


class CompletionTrend(BaseModel):
    """Quiz completion trend over time."""

    trend: List[CompletionTrendPoint] = Field(..., description="Monthly trend data")
    period: Dict[str, Any] = Field(..., description="Period information")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "trend": [
                    {
                        "year": 2024,
                        "month": 12,
                        "total": 70,
                        "completed": 58,
                        "completion_rate": 82.86,
                    },
                    {
                        "year": 2025,
                        "month": 1,
                        "total": 75,
                        "completed": 63,
                        "completion_rate": 84.0,
                    },
                ],
                "period": {
                    "months": 6,
                    "start_date": "2024-08-01T00:00:00-03:00",
                    "end_date": "2025-01-31T23:59:59-03:00",
                },
            }
        }
    )


class EngagementLevels(BaseModel):
    """Patient engagement level distribution."""

    no_quizzes: int = Field(..., description="Patients with 0 quizzes")
    low_engagement: int = Field(..., description="Patients with 1-5 quizzes")
    high_engagement: int = Field(..., description="Patients with 6+ quizzes")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"no_quizzes": 15, "low_engagement": 85, "high_engagement": 50}
        }
    )


class PatientEngagement(BaseModel):
    """Patient engagement metrics."""

    engagement_levels: EngagementLevels = Field(
        ..., description="Engagement distribution"
    )
    average_quizzes_per_patient: float = Field(
        ..., description="Average quizzes per patient"
    )
    total_active_patients: int = Field(..., description="Total active patients")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "engagement_levels": {
                    "no_quizzes": 15,
                    "low_engagement": 85,
                    "high_engagement": 50,
                },
                "average_quizzes_per_patient": 3.2,
                "total_active_patients": 150,
            }
        }
    )


class TreatmentDistributionItem(BaseModel):
    """Single treatment distribution entry."""

    treatment_type: str = Field(..., description="Treatment type or label")
    count: int = Field(..., ge=0, description="Number of patients")
    percentage: float = Field(
        ..., ge=0, le=100, description="Percentage of total patients"
    )
    color: Optional[str] = Field(None, description="Hex color code for visualization")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "treatment_type": "Quimioterapia",
                "count": 45,
                "percentage": 32.14,
                "color": "#2563eb",
            }
        }
    )


class TreatmentDistribution(BaseModel):
    """Treatment distribution summary."""

    period: str = Field(..., description="Selected period (7d, 30d, 90d, all)")
    total_patients: int = Field(..., ge=0, description="Total patients in analysis")
    distribution: List[TreatmentDistributionItem] = Field(
        ..., description="Distribution data"
    )
    trend_data: List[Dict[str, Any]] = Field(
        default_factory=list, description="Weekly trend data"
    )
    last_updated: datetime = Field(..., description="Last generated timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "period": "30d",
                "total_patients": 140,
                "distribution": [
                    {
                        "treatment_type": "Quimioterapia",
                        "count": 45,
                        "percentage": 32.14,
                        "color": "#2563eb",
                    },
                    {
                        "treatment_type": "Radioterapia",
                        "count": 30,
                        "percentage": 21.43,
                        "color": "#10b981",
                    },
                    {
                        "treatment_type": "Imunoterapia",
                        "count": 25,
                        "percentage": 17.86,
                        "color": "#f59e0b",
                    },
                ],
                "trend_data": [
                    {"week": "2025-01-06", "count": 35},
                    {"week": "2025-01-13", "count": 41},
                ],
                "last_updated": "2025-01-31T23:59:59-03:00",
            }
        }
    )
