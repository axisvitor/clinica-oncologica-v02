"""
Performance Monitoring System for Hormonia Backend.

Comprehensive monitoring with APM, database performance, resource monitoring,
business metrics, and real-time dashboards.
"""

from .apm import APMCollector
from .database_monitor import DatabasePerformanceMonitor
from .resource_monitor import ResourceMonitor
from .business_metrics import BusinessMetricsCollector
from .dashboard import RealTimeDashboard
from .anomaly_detector import AnomalyDetector
from .metrics_exporter import MetricsExporter

# Infrastructure monitoring components
from .infrastructure_monitor import (
    infrastructure_monitor,
    InfrastructureMonitor,
    ProcessMonitor,
)
from .service_health_monitor import (
    service_health_monitor,
    ServiceHealthMonitor,
    EndpointHealthChecker,
    DatabaseHealthChecker,
    CacheHealthChecker,
)
from .capacity_planner import capacity_planner, CapacityPlanner, TimeSeriesForecaster
from .alert_manager import (
    alert_manager,
    AlertManager,
    Alert,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    NotificationChannel,
)
from .prometheus_exporters import (
    metrics_exporter,
    MetricsExporter as PrometheusExporter,
    PrometheusMiddleware,
)

# Quiz metrics tracking
from .quiz_metrics import (
    QuizMetrics,
    track_quiz_link_created,
    track_quiz_link_completed,
    track_quiz_link_expired,
    track_quiz_reminder_sent,
    track_quiz_fallback_activated,
    track_quiz_link_access,
    update_completion_rate,
)

__all__ = [
    # Original monitoring components
    "APMCollector",
    "DatabasePerformanceMonitor",
    "ResourceMonitor",
    "BusinessMetricsCollector",
    "RealTimeDashboard",
    "AnomalyDetector",
    "MetricsExporter",
    # Infrastructure monitoring
    "infrastructure_monitor",
    "InfrastructureMonitor",
    "ProcessMonitor",
    # Service health monitoring
    "service_health_monitor",
    "ServiceHealthMonitor",
    "EndpointHealthChecker",
    "DatabaseHealthChecker",
    "CacheHealthChecker",
    # Capacity planning
    "capacity_planner",
    "CapacityPlanner",
    "TimeSeriesForecaster",
    # Alert management
    "alert_manager",
    "AlertManager",
    "Alert",
    "AlertRule",
    "AlertSeverity",
    "AlertStatus",
    "NotificationChannel",
    # Prometheus exporters
    "metrics_exporter",
    "PrometheusExporter",
    "PrometheusMiddleware",
    # Quiz metrics
    "QuizMetrics",
    "track_quiz_link_created",
    "track_quiz_link_completed",
    "track_quiz_link_expired",
    "track_quiz_reminder_sent",
    "track_quiz_fallback_activated",
    "track_quiz_link_access",
    "update_completion_rate",
]
