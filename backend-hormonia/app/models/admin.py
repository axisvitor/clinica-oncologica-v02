"""
Pydantic models for admin endpoints.
Provides response models for system statistics and administrative operations.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Dict


class SystemMetrics(BaseModel):
    """System-level metrics (CPU, memory, disk, uptime)."""

    cpu_percent: float = Field(..., description="CPU usage percentage", ge=0, le=100)
    memory_percent: float = Field(
        ..., description="Memory usage percentage", ge=0, le=100
    )
    disk_percent: float = Field(..., description="Disk usage percentage", ge=0, le=100)
    uptime_seconds: int = Field(..., description="System uptime in seconds", ge=0)


class UserMetrics(BaseModel):
    """User statistics and role distribution."""

    total: int = Field(..., description="Total number of users", ge=0)
    active_now: int = Field(..., description="Users active in last 24 hours", ge=0)
    by_role: Dict[str, int] = Field(
        default_factory=dict, description="User count by role (admin, doctor)"
    )


class DatabaseMetrics(BaseModel):
    """Database statistics and connection information."""

    total_records: int = Field(
        ..., description="Total records across main tables", ge=0
    )
    total_patients: int = Field(..., description="Total patients in database", ge=0)
    total_users: int = Field(..., description="Total users in database", ge=0)
    connections: int = Field(..., description="Active database connections", ge=0)


class SystemStatsResponse(BaseModel):
    """
    Complete system statistics response.
    Includes system metrics, user metrics, database metrics, and timestamp.
    """

    system: SystemMetrics = Field(..., description="System-level metrics")
    users: UserMetrics = Field(..., description="User statistics")
    database: DatabaseMetrics = Field(..., description="Database statistics")
    timestamp: str = Field(..., description="ISO 8601 timestamp of data collection")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "system": {
                    "cpu_percent": 15.2,
                    "memory_percent": 45.8,
                    "disk_percent": 62.3,
                    "uptime_seconds": 86400,
                },
                "users": {
                    "total": 125,
                    "active_now": 23,
                    "by_role": {"admin": 5, "doctor": 120},
                },
                "database": {
                    "total_records": 1250,
                    "total_patients": 1000,
                    "total_users": 125,
                    "connections": 12,
                },
                "timestamp": "2025-10-06T14:30:00.000-03:00",
            }
        }
    )
