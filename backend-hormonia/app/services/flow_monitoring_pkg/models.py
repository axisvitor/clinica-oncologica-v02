"""Data models for flow monitoring services."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from app.models.alert import AlertSeverity


class HealthStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"


@dataclass
class PerformanceMetrics:
    """Performance metrics for flow operations."""

    total_active_flows: int
    messages_sent_last_hour: int
    messages_sent_last_24h: int
    average_response_time: float
    error_rate: float
    success_rate: float
    queue_depth: int
    redis_memory_usage: float
    database_connection_count: int


@dataclass
class SystemAlert:
    """System alert for flow operations."""

    id: str
    severity: AlertSeverity
    title: str
    message: str
    component: str
    metric_value: Optional[float]
    threshold: Optional[float]
    created_at: datetime
    resolved_at: Optional[datetime]
    metadata: dict[str, Any]
