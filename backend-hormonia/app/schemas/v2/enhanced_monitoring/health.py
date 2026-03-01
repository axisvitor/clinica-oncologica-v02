"""
Health check and system information schemas.
System health, uptime, and component status.
"""

from datetime import datetime
from typing import Dict, Any

from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# HEALTH & SYSTEM SCHEMAS
# ============================================================================


class MonitoringHealthResponse(BaseModel):
    """Monitoring system health status."""

    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(..., description="Response timestamp")
    components: Dict[str, Any] = Field(..., description="Component health details")
    uptime_seconds: int = Field(..., description="System uptime in seconds")
    version: str = Field(..., description="Monitoring system version")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "timestamp": "2025-11-07T12:00:00-03:00",
                "components": {
                    "apm": "healthy",
                    "database": "healthy",
                    "resources": "healthy",
                },
                "uptime_seconds": 86400,
                "version": "2.0.0",
            }
        }
    )


class SystemMetricsResponse(BaseModel):
    """Comprehensive system metrics overview."""

    timestamp: datetime = Field(..., description="Metrics timestamp")
    apm: Dict[str, Any] = Field(..., description="APM metrics")
    database: Dict[str, Any] = Field(..., description="Database metrics")
    resources: Dict[str, Any] = Field(..., description="Resource metrics")
    business: Dict[str, Any] = Field(..., description="Business metrics")
    health_score: float = Field(..., ge=0, le=100, description="Overall health score")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2025-11-07T12:00:00-03:00",
                "apm": {"total_requests": 10000, "error_rate": 2.5},
                "database": {"query_count": 5000, "avg_duration_ms": 15.5},
                "resources": {"cpu_percent": 45.2, "memory_percent": 62.8},
                "business": {"active_patients": 150, "quiz_completions": 45},
                "health_score": 92.5,
            }
        }
    )


class SystemInfoResponse(BaseModel):
    """Static system information."""

    hostname: str = Field(..., description="System hostname")
    platform: str = Field(..., description="Operating system platform")
    architecture: str = Field(..., description="CPU architecture")
    cpu_count: int = Field(..., description="Number of CPU cores")
    total_memory_gb: float = Field(..., description="Total system memory in GB")
    python_version: str = Field(..., description="Python version")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hostname": "app-server-01",
                "platform": "Linux",
                "architecture": "x86_64",
                "cpu_count": 8,
                "total_memory_gb": 16.0,
                "python_version": "3.11.5",
            }
        }
    )
