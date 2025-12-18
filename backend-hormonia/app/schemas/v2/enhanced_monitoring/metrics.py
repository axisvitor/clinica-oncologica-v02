"""
System resource metrics schemas.
CPU, memory, disk, network metrics and time series data.
"""

from datetime import datetime
from typing import List, Dict, Any

from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# RESOURCE SCHEMAS
# ============================================================================


class ResourceStatsResponse(BaseModel):
    """Current resource usage statistics."""

    timestamp: datetime = Field(..., description="Measurement timestamp")
    cpu: Dict[str, Any] = Field(..., description="CPU metrics")
    memory: Dict[str, Any] = Field(..., description="Memory metrics")
    disk: Dict[str, Any] = Field(..., description="Disk metrics")
    network: Dict[str, Any] = Field(..., description="Network metrics")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2025-11-07T12:00:00Z",
                "cpu": {"percent": 45.2, "count": 8},
                "memory": {"percent": 62.8, "used_gb": 10.0, "total_gb": 16.0},
                "disk": {"percent": 55.5, "used_gb": 250.0, "total_gb": 450.0},
                "network": {"bytes_sent": 1000000, "bytes_recv": 2000000},
            }
        }
    )


class ResourceTimeSeriesPoint(BaseModel):
    """Single point in resource time series."""

    timestamp: datetime = Field(..., description="Measurement timestamp")
    cpu_percent: float = Field(..., ge=0, le=100, description="CPU usage percentage")
    memory_percent: float = Field(
        ..., ge=0, le=100, description="Memory usage percentage"
    )
    disk_percent: float = Field(..., ge=0, le=100, description="Disk usage percentage")
    network_bytes_sent: int = Field(..., ge=0, description="Network bytes sent")
    network_bytes_recv: int = Field(..., ge=0, description="Network bytes received")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2025-11-07T12:00:00Z",
                "cpu_percent": 45.2,
                "memory_percent": 62.8,
                "disk_percent": 55.5,
                "network_bytes_sent": 1000000,
                "network_bytes_recv": 2000000,
            }
        }
    )


class ResourceHistoricalResponse(BaseModel):
    """Historical resource usage data."""

    time_range_minutes: int = Field(..., ge=1, description="Time range in minutes")
    data_points: List[ResourceTimeSeriesPoint] = Field(
        ..., description="Time series data"
    )
    summary: Dict[str, Any] = Field(..., description="Summary statistics")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "time_range_minutes": 60,
                "data_points": [
                    {
                        "timestamp": "2025-11-07T12:00:00Z",
                        "cpu_percent": 45.2,
                        "memory_percent": 62.8,
                        "disk_percent": 55.5,
                        "network_bytes_sent": 1000000,
                        "network_bytes_recv": 2000000,
                    }
                ],
                "summary": {
                    "avg_cpu": 42.5,
                    "max_cpu": 75.0,
                    "avg_memory": 60.0,
                    "max_memory": 72.0,
                },
            }
        }
    )


# ============================================================================
# BUSINESS METRICS SCHEMAS
# ============================================================================


class BusinessMetricsSummaryResponse(BaseModel):
    """Business metrics summary."""

    time_range_hours: int = Field(..., ge=1, description="Time range in hours")
    timestamp: datetime = Field(..., description="Summary timestamp")
    metrics: Dict[str, Any] = Field(..., description="Business metrics data")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "time_range_hours": 24,
                "timestamp": "2025-11-07T12:00:00Z",
                "metrics": {
                    "quiz_completions": 45,
                    "messages_sent": 250,
                    "active_patients": 150,
                    "flow_executions": 180,
                },
            }
        }
    )


class PatientMetricsResponse(BaseModel):
    """Patient-specific metrics."""

    patient_id: str = Field(..., description="Patient identifier")
    time_range_hours: int = Field(..., ge=1, description="Time range in hours")
    timestamp: datetime = Field(..., description="Metrics timestamp")
    metrics: Dict[str, Any] = Field(..., description="Patient metrics data")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_id": "patient-123",
                "time_range_hours": 24,
                "timestamp": "2025-11-07T12:00:00Z",
                "metrics": {
                    "quiz_completions": 2,
                    "messages_received": 5,
                    "flow_interactions": 3,
                    "last_activity": "2025-11-07T11:30:00Z",
                },
            }
        }
    )


class MetricTypeStatsResponse(BaseModel):
    """Statistics for specific metric type."""

    metric_type: str = Field(..., description="Metric type")
    time_range_hours: int = Field(..., ge=1, description="Time range in hours")
    timestamp: datetime = Field(..., description="Statistics timestamp")
    statistics: Dict[str, Any] = Field(..., description="Metric statistics")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "metric_type": "quiz_completion",
                "time_range_hours": 24,
                "timestamp": "2025-11-07T12:00:00Z",
                "statistics": {
                    "total": 45,
                    "avg_per_hour": 1.875,
                    "peak_hour": "2025-11-07T10:00:00Z",
                    "peak_count": 8,
                },
            }
        }
    )
