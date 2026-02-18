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
from app.services.alerts import (
    get_alert_manager as _get_alert_manager,
    AlertManager,
    Alert,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    NotificationChannel,
)

class _AlertManagerProxy:
    """Thin compatibility proxy to canonical AlertManager singleton."""

    def __call__(self):
        return _get_alert_manager()

    def __getattr__(self, name):
        return getattr(_get_alert_manager(), name)

alert_manager = _AlertManagerProxy()

from .prometheus_exporters import (
    metrics_exporter,
    MetricsExporter as PrometheusExporter,
    PrometheusMiddleware,
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
]
