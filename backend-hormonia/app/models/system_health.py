"""
System Health Monitoring Models.
Stores historical health checks, incidents, and performance metrics.
"""

from sqlalchemy import Column, String, Text, DateTime, Enum, Float
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
import enum

from app.models.base import BaseModel


class HealthStatus(enum.Enum):
    """System health status enum."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class IncidentSeverity(enum.Enum):
    """Incident severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(enum.Enum):
    """Incident lifecycle status."""

    ACTIVE = "active"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    MONITORING = "monitoring"


class SystemHealthSnapshot(BaseModel):
    """
    Periodic snapshot of system health.
    captured every X minutes to track history.
    """

    __tablename__ = "system_health_snapshots"

    status = Column(Enum(HealthStatus), nullable=False)
    health_score = Column(Float, nullable=False)  # 0.0 to 100.0

    # JSON fields for detailed breakdown
    # Example: {"database": "healthy", "redis": "degraded", "api": "healthy"}
    services_status = Column(JSONB, nullable=False, default=dict)

    # Example: {"cpu_percent": 45, "memory_percent": 60, "active_requests": 120}
    metrics = Column(JSONB, nullable=False, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<SystemHealthSnapshot(status='{self.status.value}', score={self.health_score}, time='{self.created_at}')>"


class SystemIncident(BaseModel):
    """
    Record of system outages or degraded performance events.
    """

    __tablename__ = "system_incidents"

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(Enum(IncidentSeverity), nullable=False)
    status = Column(Enum(IncidentStatus), nullable=False, default=IncidentStatus.ACTIVE)

    service_name = Column(
        String(100), nullable=False
    )  # e.g. "database-primary", "redis-cache"

    started_at = Column(DateTime(timezone=True), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata for root cause analysis
    meta_data = Column(JSONB, nullable=True, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return f"<SystemIncident(title='{self.title}', status='{self.status.value}', severity='{self.severity.value}')>"
