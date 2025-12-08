from typing import Any
"""
Monitoring Services - Consolidated Facade.

This module provides a unified interface to the monitoring system,
re-exporting components from app/monitoring/ for backward compatibility.

Architecture:
- app/monitoring/: Main monitoring system (23+ modules)
- app/services/monitoring/: Facade for backward compatibility

Usage:
    from app.services.monitoring import (
        get_monitoring_manager,
        DatabaseMonitor,
        AlertService,
        MetricsCollector
    )
"""

# ============================================================================
# Core Monitoring Components
# ============================================================================

from app.monitoring.manager import (
    MonitoringManager,
    get_monitoring_manager,
)

from app.monitoring.config import (
    MonitoringConfig,
    DatabaseMonitorConfig,
    ResourceMonitorConfig,
    APMConfig,
    BusinessMetricsConfig,
    get_monitoring_config,
)

# ============================================================================
# Database Monitoring
# ============================================================================

from app.monitoring.database_monitor import (
    DatabasePerformanceMonitor,
    QueryMetrics,
    ConnectionPoolStats,
    get_database_monitor,
)

# ============================================================================
# Resource Monitoring
# ============================================================================

from app.monitoring.resource_monitor import (
    ResourceMonitor,
    ResourceSnapshot,
    ResourceAlert,
    get_resource_monitor,
)

# ============================================================================
# Infrastructure Monitoring
# ============================================================================

from app.monitoring.infrastructure_monitor import (
    InfrastructureMonitor,
    ProcessMonitor,
    ServiceHealth,
)

# ============================================================================
# Alert Management
# ============================================================================

from app.monitoring.alert_manager import (
    AlertManager,
    Alert,
    AlertSeverity,
    AlertType,
    AlertRule,
    get_alert_manager,
)

# ============================================================================
# APM (Application Performance Monitoring)
# ============================================================================

from app.monitoring.apm import (
    APMCollector,
    RequestMetrics,
    EndpointStats,
)

# ============================================================================
# Business Metrics
# ============================================================================

from app.monitoring.business_metrics import (
    BusinessMetricsCollector,
    PatientMetrics,
    FlowMetrics,
    QuizMetrics,
    MessageMetrics,
)

# ============================================================================
# Health Monitoring
# ============================================================================

from app.monitoring.service_health_monitor import (
    ServiceHealthMonitor,
    HealthStatus,
    HealthCheck,
)

# ============================================================================
# Metrics Export
# ============================================================================

from app.monitoring.metrics_exporter import (
    MetricsExporter,
    PrometheusExporter,
)

from app.monitoring.prometheus_exporters import (
    setup_prometheus_metrics,
    database_metrics,
    request_metrics,
    business_metrics,
)

# ============================================================================
# Logging & Audit
# ============================================================================

from app.monitoring.audit_logger import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
)

from app.monitoring.log_analyzer import (
    LogAnalyzer,
    LogPattern,
    LogAnomaly,
)

# ============================================================================
# Monitoring Middleware
# ============================================================================

from app.monitoring.middleware import (
    MonitoringMiddleware,
)

# ============================================================================
# Dashboard & Visualization
# ============================================================================

from app.monitoring.dashboard import (
    MonitoringDashboard,
    DashboardMetrics,
)

# ============================================================================
# Advanced Features
# ============================================================================

from app.monitoring.anomaly_detector import (
    AnomalyDetector,
    Anomaly,
    AnomalyType,
)

from app.monitoring.capacity_planner import (
    CapacityPlanner,
    CapacityPrediction,
)

# ============================================================================
# Backward Compatibility Aliases
# ============================================================================

# Legacy names for backward compatibility
DatabaseMonitor = DatabasePerformanceMonitor
AlertService = AlertManager
MetricsCollector = APMCollector

# ============================================================================
# Public API
# ============================================================================

__all__ = [
    # Core
    "MonitoringManager",
    "get_monitoring_manager",
    "MonitoringConfig",
    "get_monitoring_config",
    # Database
    "DatabasePerformanceMonitor",
    "DatabaseMonitor",  # Alias
    "QueryMetrics",
    "ConnectionPoolStats",
    "get_database_monitor",
    "DatabaseMonitorConfig",
    # Resources
    "ResourceMonitor",
    "ResourceSnapshot",
    "ResourceAlert",
    "get_resource_monitor",
    "ResourceMonitorConfig",
    # Infrastructure
    "InfrastructureMonitor",
    "ProcessMonitor",
    "ServiceHealth",
    # Alerts
    "AlertManager",
    "AlertService",  # Alias
    "Alert",
    "AlertSeverity",
    "AlertType",
    "AlertRule",
    "get_alert_manager",
    # APM
    "APMCollector",
    "MetricsCollector",  # Alias
    "RequestMetrics",
    "EndpointStats",
    "APMConfig",
    # Business Metrics
    "BusinessMetricsCollector",
    "PatientMetrics",
    "FlowMetrics",
    "QuizMetrics",
    "MessageMetrics",
    "BusinessMetricsConfig",
    # Health
    "ServiceHealthMonitor",
    "HealthStatus",
    "HealthCheck",
    # Export
    "MetricsExporter",
    "PrometheusExporter",
    "setup_prometheus_metrics",
    "database_metrics",
    "request_metrics",
    "business_metrics",
    # Logging
    "AuditLogger",
    "AuditEvent",
    "AuditEventType",
    "LogAnalyzer",
    "LogPattern",
    "LogAnomaly",
    # Middleware
    "MonitoringMiddleware",
    # Dashboard
    "MonitoringDashboard",
    "DashboardMetrics",
    # Advanced
    "AnomalyDetector",
    "Anomaly",
    "AnomalyType",
    "CapacityPlanner",
    "CapacityPrediction",
]

# ============================================================================
# Convenience Functions
# ============================================================================


def get_all_metrics():
    """
    Get comprehensive metrics from all monitoring components.

    Returns:
        dict: All monitoring metrics
    """
    manager = get_monitoring_manager()
    return manager.get_all_metrics()


def health_check():
    """
    Perform system-wide health check.

    Returns:
        dict: Health check results
    """
    manager = get_monitoring_manager()
    return manager.health_check()


async def start_monitoring(config: MonitoringConfig = None):
    """
    Start all monitoring components.

    Args:
        config: Optional monitoring configuration
    """
    manager = get_monitoring_manager(config)
    await manager.start()


async def stop_monitoring():
    """Stop all monitoring components."""
    manager = get_monitoring_manager()
    await manager.stop()
