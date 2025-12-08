"""
Alert and anomaly detection schemas.
Alert records, anomaly detection, severity levels.
"""

from datetime import datetime
from typing import List, Dict

from pydantic import BaseModel, Field, ConfigDict

from ..common import CursorPaginatedResponse


# ============================================================================
# ANOMALY SCHEMAS
# ============================================================================


class AnomalyRecord(BaseModel):
    """Single anomaly record."""

    timestamp: datetime = Field(..., description="Anomaly detection timestamp")
    metric: str = Field(..., description="Metric name")
    value: float = Field(..., description="Observed value")
    expected_value: float = Field(..., description="Expected value")
    severity: str = Field(..., description="Anomaly severity")
    description: str = Field(..., description="Human-readable description")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2025-11-07T12:00:00Z",
                "metric": "cpu_usage",
                "value": 95.5,
                "expected_value": 45.0,
                "severity": "high",
                "description": "CPU usage significantly above normal",
            }
        }
    )


class AnomalyListResponse(CursorPaginatedResponse[AnomalyRecord]):
    """Cursor-paginated anomaly list."""

    pass


class AnomalySummaryResponse(BaseModel):
    """Anomaly summary statistics."""

    time_range_hours: int = Field(..., ge=1, description="Time range in hours")
    timestamp: datetime = Field(..., description="Summary timestamp")
    total_anomalies: int = Field(..., ge=0, description="Total anomaly count")
    by_severity: Dict[str, int] = Field(..., description="Anomalies by severity")
    by_metric: Dict[str, int] = Field(..., description="Anomalies by metric")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "time_range_hours": 24,
                "timestamp": "2025-11-07T12:00:00Z",
                "total_anomalies": 15,
                "by_severity": {"high": 3, "medium": 8, "low": 4},
                "by_metric": {"cpu_usage": 5, "memory_usage": 7, "error_rate": 3},
            }
        }
    )


# ============================================================================
# ALERT SCHEMAS
# ============================================================================


class AlertRecord(BaseModel):
    """Active alert record."""

    type: str = Field(..., description="Alert type (apm, database, resource)")
    severity: str = Field(..., description="Alert severity")
    message: str = Field(..., description="Alert message")
    value: float = Field(..., description="Current value")
    threshold: float = Field(..., description="Alert threshold")
    timestamp: datetime = Field(..., description="Alert timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "resource",
                "severity": "high",
                "message": "High CPU usage: 92.5%",
                "value": 92.5,
                "threshold": 80.0,
                "timestamp": "2025-11-07T12:00:00Z",
            }
        }
    )


class AlertListResponse(BaseModel):
    """List of active alerts."""

    alerts: List[AlertRecord] = Field(..., description="Active alerts")
    count: int = Field(..., ge=0, description="Total alert count")
    timestamp: datetime = Field(..., description="Response timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "alerts": [
                    {
                        "type": "resource",
                        "severity": "high",
                        "message": "High CPU usage: 92.5%",
                        "value": 92.5,
                        "threshold": 80.0,
                        "timestamp": "2025-11-07T12:00:00Z",
                    }
                ],
                "count": 1,
                "timestamp": "2025-11-07T12:00:00Z",
            }
        }
    )
