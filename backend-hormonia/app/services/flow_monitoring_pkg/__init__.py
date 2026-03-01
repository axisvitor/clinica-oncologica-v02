"""Split flow monitoring package with compatibility re-exports."""

from app.models.alert import AlertSeverity

from .metrics import (
    FLOW_ACTIVE_PATIENTS,
    FLOW_ERRORS,
    FLOW_MESSAGES_SENT,
    FLOW_PROCESSING_TIME,
    flow_active_count,
    flow_completed_count,
    flow_completion_rate,
    flow_duration_seconds,
)
from .models import HealthStatus, PerformanceMetrics, SystemAlert
from .service import FlowMonitoringService

__all__ = [
    "FlowMonitoringService",
    "HealthStatus",
    "PerformanceMetrics",
    "SystemAlert",
    "AlertSeverity",
    "FLOW_MESSAGES_SENT",
    "FLOW_ERRORS",
    "FLOW_PROCESSING_TIME",
    "FLOW_ACTIVE_PATIENTS",
    "flow_active_count",
    "flow_completed_count",
    "flow_completion_rate",
    "flow_duration_seconds",
]
