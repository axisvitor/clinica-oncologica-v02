"""
Enhanced Monitoring Schemas for API v2
Comprehensive schemas for monitoring endpoints with field validation.

This package provides modular schemas for:
- System health and information
- APM (Application Performance Monitoring)
- Database monitoring
- Resource metrics (CPU, memory, disk, network)
- Business metrics
- Anomaly detection and alerts
- Dashboard and exports
"""

# Re-export all schemas for backward compatibility

# Base enums
from .base import (
    AlertSeverity,
    MetricType,
    TimeRange,
)

# Health schemas
from .health import (
    MonitoringHealthResponse,
    SystemMetricsResponse,
    SystemInfoResponse,
)

# Performance/APM schemas
from .performance import (
    APMGlobalStatsResponse,
    APMEndpointStatsResponse,
    APMEndpointDetailResponse,
    APMEndpointListResponse,
    PerformanceScore,
    PerformanceOverviewResponse,
)

# Database schemas
from .database import (
    ConnectionPoolStatsResponse,
    DatabaseOverviewResponse,
    SlowQueryResponse,
    SlowQueryListResponse,
    TableStatsResponse,
    TableStatsListResponse,
)

# Resource/metrics schemas
from .metrics import (
    ResourceStatsResponse,
    ResourceTimeSeriesPoint,
    ResourceHistoricalResponse,
    BusinessMetricsSummaryResponse,
    PatientMetricsResponse,
    MetricTypeStatsResponse,
)

# Alert/anomaly schemas
from .alerts import (
    AnomalyRecord,
    AnomalyListResponse,
    AnomalySummaryResponse,
    AlertRecord,
    AlertListResponse,
)

# Dashboard schemas
from .dashboard import (
    DashboardMetricsSnapshot,
    DashboardStatusResponse,
    PrometheusExportResponse,
    GrafanaTimeRange,
    GrafanaQueryRequest,
    GrafanaQueryResponse,
    MonitoringConfigResponse,
    MonitoringConfigUpdateRequest,
    ServiceActionResponse,
    StatsResetResponse,
)

__all__ = [
    # Enums
    "AlertSeverity",
    "MetricType",
    "TimeRange",
    # Health
    "MonitoringHealthResponse",
    "SystemMetricsResponse",
    "SystemInfoResponse",
    # Performance/APM
    "APMGlobalStatsResponse",
    "APMEndpointStatsResponse",
    "APMEndpointDetailResponse",
    "APMEndpointListResponse",
    "PerformanceScore",
    "PerformanceOverviewResponse",
    # Database
    "ConnectionPoolStatsResponse",
    "DatabaseOverviewResponse",
    "SlowQueryResponse",
    "SlowQueryListResponse",
    "TableStatsResponse",
    "TableStatsListResponse",
    # Metrics
    "ResourceStatsResponse",
    "ResourceTimeSeriesPoint",
    "ResourceHistoricalResponse",
    "BusinessMetricsSummaryResponse",
    "PatientMetricsResponse",
    "MetricTypeStatsResponse",
    # Alerts
    "AnomalyRecord",
    "AnomalyListResponse",
    "AnomalySummaryResponse",
    "AlertRecord",
    "AlertListResponse",
    # Dashboard
    "DashboardMetricsSnapshot",
    "DashboardStatusResponse",
    "PrometheusExportResponse",
    "GrafanaTimeRange",
    "GrafanaQueryRequest",
    "GrafanaQueryResponse",
    "MonitoringConfigResponse",
    "MonitoringConfigUpdateRequest",
    "ServiceActionResponse",
    "StatsResetResponse",
]
