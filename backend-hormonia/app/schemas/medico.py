"""
Pydantic schemas for medico (doctor) dashboard and statistics.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class EngagementMetrics(BaseModel):
    """Message engagement metrics for medico dashboard."""

    messages_today: int = Field(..., ge=0, description="Number of messages sent today")
    messages_unread: int = Field(..., ge=0, description="Number of unread messages")
    response_rate: float = Field(
        ..., ge=0.0, le=1.0, description="Response rate (0.0 - 1.0)"
    )
    avg_response_time_minutes: Optional[int] = Field(
        None, ge=0, description="Average response time in minutes"
    )


class AlertMetrics(BaseModel):
    """Alert counts by severity for medico dashboard."""

    total: int = Field(..., ge=0, description="Total active alerts")
    critical: int = Field(..., ge=0, description="Critical severity alerts")
    high: int = Field(..., ge=0, description="High severity alerts")
    medium: int = Field(..., ge=0, description="Medium severity alerts")
    low: int = Field(..., ge=0, description="Low severity alerts")


class MedicoDashboardStats(BaseModel):
    """Complete dashboard statistics for medico panel."""

    pacientes_ativos: int = Field(..., ge=0, description="Active patients count")
    consultas_hoje: int = Field(
        ..., ge=0, description="Today's appointments/consultations"
    )
    pendencias: int = Field(..., ge=0, description="Pending tasks (exams + messages)")
    exames_aguardando: int = Field(..., ge=0, description="Exams awaiting review")
    engagement: EngagementMetrics = Field(..., description="Message engagement metrics")
    alerts: AlertMetrics = Field(..., description="Alert counts by severity")
    timestamp: str = Field(
        ..., description="Timestamp of statistics generation (ISO 8601)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pacientes_ativos": 45,
                "consultas_hoje": 8,
                "pendencias": 12,
                "exames_aguardando": 5,
                "engagement": {
                    "messages_today": 23,
                    "messages_unread": 4,
                    "response_rate": 0.87,
                    "avg_response_time_minutes": 45,
                },
                "alerts": {
                    "total": 15,
                    "critical": 2,
                    "high": 5,
                    "medium": 6,
                    "low": 2,
                },
                "timestamp": "2025-10-06T14:30:00-03:00",
            }
        }
    )
