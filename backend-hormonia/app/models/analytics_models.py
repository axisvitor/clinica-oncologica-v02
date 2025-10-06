"""
Analytics response models for API endpoints.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class TreatmentDistributionItem(BaseModel):
    """Single treatment type distribution data point."""
    treatment_type: str = Field(..., description="Type of treatment")
    count: int = Field(..., description="Number of patients receiving this treatment")
    percentage: float = Field(..., description="Percentage of total patients")
    color: str = Field(..., description="Hex color code for chart rendering")


class TreatmentDistributionResponse(BaseModel):
    """Response model for treatment distribution endpoint."""
    data: List[TreatmentDistributionItem] = Field(..., description="Treatment distribution data")
    period: str = Field(..., description="Period for data aggregation (7d, 30d, 90d, all)")
    total_patients: int = Field(..., description="Total number of patients in analysis")
    timestamp: str = Field(..., description="Timestamp of data generation (ISO 8601)")

    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {
                        "treatment_type": "Quimioterapia",
                        "count": 45,
                        "percentage": 35.71,
                        "color": "#3b82f6"
                    },
                    {
                        "treatment_type": "Radioterapia",
                        "count": 38,
                        "percentage": 30.16,
                        "color": "#10b981"
                    }
                ],
                "period": "30d",
                "total_patients": 126,
                "timestamp": "2025-10-06T14:30:00Z"
            }
        }
