"""
Enhanced Monitoring Schemas for API v2
Comprehensive schemas for monitoring endpoints with field validation.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field, field_validator, ConfigDict

from .common import CursorPaginatedResponse


# ============================================================================
# ENUMS
# ============================================================================


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MetricType(str, Enum):
    """Business metric types."""

    QUIZ_COMPLETION = "quiz_completion"
    MESSAGE_SENT = "message_sent"
    PATIENT_INTERACTION = "patient_interaction"
    FLOW_EXECUTION = "flow_execution"
    AI_REQUEST = "ai_request"


class TimeRange(str, Enum):
    """Predefined time ranges."""

    HOUR_1 = "1h"
    HOURS_6 = "6h"
    HOURS_24 = "24h"
    DAYS_7 = "7d"
    DAYS_30 = "30d"


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
                "timestamp": "2025-11-07T12:00:00Z",
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
                "timestamp": "2025-11-07T12:00:00Z",
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


# ============================================================================
# APM SCHEMAS
# ============================================================================


class APMGlobalStatsResponse(BaseModel):
    """Global APM statistics."""

    timestamp: datetime = Field(..., description="Statistics timestamp")
    total_requests: int = Field(..., ge=0, description="Total request count")
    total_errors: int = Field(..., ge=0, description="Total error count")
    error_rate: float = Field(..., ge=0, le=100, description="Error rate percentage")
    avg_response_time: float = Field(..., ge=0, description="Average response time (ms)")
    p50: float = Field(..., ge=0, description="50th percentile latency (ms)")
    p95: float = Field(..., ge=0, description="95th percentile latency (ms)")
    p99: float = Field(..., ge=0, description="99th percentile latency (ms)")
    requests_per_second: float = Field(..., ge=0, description="Current throughput")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2025-11-07T12:00:00Z",
                "total_requests": 10000,
                "total_errors": 250,
                "error_rate": 2.5,
                "avg_response_time": 125.5,
                "p50": 85.0,
                "p95": 350.0,
                "p99": 850.0,
                "requests_per_second": 25.5,
            }
        }
    )


class APMEndpointStatsResponse(BaseModel):
    """APM statistics for a single endpoint."""

    endpoint: str = Field(..., description="Endpoint path")
    total_requests: int = Field(..., ge=0, description="Total request count")
    total_errors: int = Field(..., ge=0, description="Total error count")
    error_rate: float = Field(..., ge=0, le=100, description="Error rate percentage")
    avg_response_time: float = Field(..., ge=0, description="Average response time (ms)")
    p95: float = Field(..., ge=0, description="95th percentile latency (ms)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "endpoint": "/api/v2/patients",
                "total_requests": 1500,
                "total_errors": 15,
                "error_rate": 1.0,
                "avg_response_time": 95.5,
                "p95": 250.0,
            }
        }
    )


class APMEndpointDetailResponse(BaseModel):
    """Detailed APM statistics for a specific endpoint."""

    endpoint: str = Field(..., description="Endpoint path")
    timestamp: datetime = Field(..., description="Statistics timestamp")
    total_requests: int = Field(..., ge=0, description="Total request count")
    total_errors: int = Field(..., ge=0, description="Total error count")
    error_rate: float = Field(..., ge=0, le=100, description="Error rate percentage")
    avg_response_time: float = Field(..., ge=0, description="Average response time (ms)")
    min_response_time: float = Field(..., ge=0, description="Minimum response time (ms)")
    max_response_time: float = Field(..., ge=0, description="Maximum response time (ms)")
    p50: float = Field(..., ge=0, description="50th percentile latency (ms)")
    p95: float = Field(..., ge=0, description="95th percentile latency (ms)")
    p99: float = Field(..., ge=0, description="99th percentile latency (ms)")
    recent_errors: List[Dict[str, Any]] = Field(
        default_factory=list, description="Recent error details"
    )
    status_code_distribution: Dict[str, int] = Field(
        default_factory=dict, description="HTTP status code counts"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "endpoint": "/api/v2/patients/123",
                "timestamp": "2025-11-07T12:00:00Z",
                "total_requests": 500,
                "total_errors": 5,
                "error_rate": 1.0,
                "avg_response_time": 85.5,
                "min_response_time": 25.0,
                "max_response_time": 850.0,
                "p50": 75.0,
                "p95": 200.0,
                "p99": 450.0,
                "recent_errors": [
                    {"timestamp": "2025-11-07T11:55:00Z", "error": "Not Found"}
                ],
                "status_code_distribution": {"200": 495, "404": 5},
            }
        }
    )


class APMEndpointListResponse(CursorPaginatedResponse[APMEndpointStatsResponse]):
    """Cursor-paginated APM endpoint list."""

    pass


# ============================================================================
# DATABASE SCHEMAS
# ============================================================================


class ConnectionPoolStatsResponse(BaseModel):
    """Connection pool statistics."""

    size: int = Field(..., ge=0, description="Pool size")
    checked_out: int = Field(..., ge=0, description="Checked out connections")
    overflow: int = Field(..., ge=0, description="Overflow connections")
    checked_in: int = Field(..., ge=0, description="Available connections")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"size": 20, "checked_out": 5, "overflow": 0, "checked_in": 15}
        }
    )


class DatabaseOverviewResponse(BaseModel):
    """Database performance overview."""

    timestamp: datetime = Field(..., description="Statistics timestamp")
    query_statistics: Dict[str, Any] = Field(..., description="Query statistics")
    connection_pool: ConnectionPoolStatsResponse = Field(
        ..., description="Connection pool stats"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2025-11-07T12:00:00Z",
                "query_statistics": {
                    "total_queries": 5000,
                    "slow_queries": 25,
                    "avg_duration_ms": 15.5,
                },
                "connection_pool": {
                    "size": 20,
                    "checked_out": 5,
                    "overflow": 0,
                    "checked_in": 15,
                },
            }
        }
    )


class SlowQueryResponse(BaseModel):
    """Slow query information."""

    query: str = Field(..., description="SQL query text (truncated if long)")
    duration_ms: float = Field(..., ge=0, description="Query duration in milliseconds")
    timestamp: datetime = Field(..., description="Query execution timestamp")
    table: Optional[str] = Field(None, description="Primary table accessed")
    rows_examined: Optional[int] = Field(None, description="Rows examined")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "SELECT * FROM patients WHERE...",
                "duration_ms": 850.5,
                "timestamp": "2025-11-07T11:55:00Z",
                "table": "patients",
                "rows_examined": 15000,
            }
        }
    )


class SlowQueryListResponse(CursorPaginatedResponse[SlowQueryResponse]):
    """Cursor-paginated slow query list."""

    pass


class TableStatsResponse(BaseModel):
    """Statistics for a database table."""

    table: str = Field(..., description="Table name")
    query_count: int = Field(..., ge=0, description="Number of queries")
    avg_duration_ms: float = Field(..., ge=0, description="Average query duration (ms)")
    total_duration_ms: float = Field(..., ge=0, description="Total query duration (ms)")
    slow_query_count: int = Field(..., ge=0, description="Number of slow queries")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "table": "patients",
                "query_count": 1500,
                "avg_duration_ms": 25.5,
                "total_duration_ms": 38250.0,
                "slow_query_count": 15,
            }
        }
    )


class TableStatsListResponse(BaseModel):
    """List of table statistics."""

    data: List[TableStatsResponse] = Field(..., description="Table statistics")
    timestamp: datetime = Field(..., description="Statistics timestamp")
    total_tables: int = Field(..., ge=0, description="Total number of tables")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {
                        "table": "patients",
                        "query_count": 1500,
                        "avg_duration_ms": 25.5,
                        "total_duration_ms": 38250.0,
                        "slow_query_count": 15,
                    }
                ],
                "timestamp": "2025-11-07T12:00:00Z",
                "total_tables": 10,
            }
        }
    )


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
    data_points: List[ResourceTimeSeriesPoint] = Field(..., description="Time series data")
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

    metric_type: MetricType = Field(..., description="Metric type")
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


# ============================================================================
# ANOMALY SCHEMAS
# ============================================================================


class AnomalyRecord(BaseModel):
    """Single anomaly record."""

    timestamp: datetime = Field(..., description="Anomaly detection timestamp")
    metric: str = Field(..., description="Metric name")
    value: float = Field(..., description="Observed value")
    expected_value: float = Field(..., description="Expected value")
    severity: str = Field(..., description="Anomaly severity")
    description: str = Field(..., description="Human-readable description")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2025-11-07T12:00:00Z",
                "metric": "cpu_usage",
                "value": 95.5,
                "expected_value": 45.0,
                "severity": "high",
                "description": "CPU usage significantly above normal",
            }
        }
    )


class AnomalyListResponse(CursorPaginatedResponse[AnomalyRecord]):
    """Cursor-paginated anomaly list."""

    pass


class AnomalySummaryResponse(BaseModel):
    """Anomaly summary statistics."""

    time_range_hours: int = Field(..., ge=1, description="Time range in hours")
    timestamp: datetime = Field(..., description="Summary timestamp")
    total_anomalies: int = Field(..., ge=0, description="Total anomaly count")
    by_severity: Dict[str, int] = Field(..., description="Anomalies by severity")
    by_metric: Dict[str, int] = Field(..., description="Anomalies by metric")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "time_range_hours": 24,
                "timestamp": "2025-11-07T12:00:00Z",
                "total_anomalies": 15,
                "by_severity": {"high": 3, "medium": 8, "low": 4},
                "by_metric": {"cpu_usage": 5, "memory_usage": 7, "error_rate": 3},
            }
        }
    )


# ============================================================================
# DASHBOARD SCHEMAS
# ============================================================================


class DashboardMetricsSnapshot(BaseModel):
    """Snapshot of key metrics for dashboard."""

    apm_error_rate: float = Field(..., ge=0, le=100, description="APM error rate")
    apm_avg_latency: float = Field(..., ge=0, description="Average latency (ms)")
    db_query_count: int = Field(..., ge=0, description="Database query count")
    db_slow_queries: int = Field(..., ge=0, description="Slow query count")
    cpu_percent: float = Field(..., ge=0, le=100, description="CPU usage")
    memory_percent: float = Field(..., ge=0, le=100, description="Memory usage")
    active_anomalies: int = Field(..., ge=0, description="Active anomaly count")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "apm_error_rate": 2.5,
                "apm_avg_latency": 125.5,
                "db_query_count": 5000,
                "db_slow_queries": 25,
                "cpu_percent": 45.2,
                "memory_percent": 62.8,
                "active_anomalies": 3,
            }
        }
    )


class DashboardStatusResponse(BaseModel):
    """Dashboard status with metrics snapshot."""

    timestamp: datetime = Field(..., description="Status timestamp")
    active_connections: int = Field(..., ge=0, description="Active WebSocket connections")
    metrics_snapshot: DashboardMetricsSnapshot = Field(..., description="Metrics snapshot")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2025-11-07T12:00:00Z",
                "active_connections": 5,
                "metrics_snapshot": {
                    "apm_error_rate": 2.5,
                    "apm_avg_latency": 125.5,
                    "db_query_count": 5000,
                    "db_slow_queries": 25,
                    "cpu_percent": 45.2,
                    "memory_percent": 62.8,
                    "active_anomalies": 3,
                },
            }
        }
    )


# ============================================================================
# ALERT SCHEMAS
# ============================================================================


class AlertRecord(BaseModel):
    """Active alert record."""

    type: str = Field(..., description="Alert type (apm, database, resource)")
    severity: str = Field(..., description="Alert severity")
    message: str = Field(..., description="Alert message")
    value: float = Field(..., description="Current value")
    threshold: float = Field(..., description="Alert threshold")
    timestamp: datetime = Field(..., description="Alert timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "resource",
                "severity": "high",
                "message": "High CPU usage: 92.5%",
                "value": 92.5,
                "threshold": 80.0,
                "timestamp": "2025-11-07T12:00:00Z",
            }
        }
    )


class AlertListResponse(BaseModel):
    """List of active alerts."""

    alerts: List[AlertRecord] = Field(..., description="Active alerts")
    count: int = Field(..., ge=0, description="Total alert count")
    timestamp: datetime = Field(..., description="Response timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "alerts": [
                    {
                        "type": "resource",
                        "severity": "high",
                        "message": "High CPU usage: 92.5%",
                        "value": 92.5,
                        "threshold": 80.0,
                        "timestamp": "2025-11-07T12:00:00Z",
                    }
                ],
                "count": 1,
                "timestamp": "2025-11-07T12:00:00Z",
            }
        }
    )


# ============================================================================
# PERFORMANCE SCHEMAS
# ============================================================================


class PerformanceScore(BaseModel):
    """Performance score calculation."""

    score: float = Field(..., ge=0, le=100, description="Performance score (0-100)")
    status: str = Field(..., description="Status (excellent, good, degraded, critical)")
    deductions: List[Dict[str, Any]] = Field(
        default_factory=list, description="Score deductions"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "score": 85.5,
                "status": "good",
                "deductions": [
                    {"reason": "high_error_rate", "deduction": 10.0},
                    {"reason": "slow_queries", "deduction": 4.5},
                ],
            }
        }
    )


class PerformanceOverviewResponse(BaseModel):
    """Enhanced performance overview."""

    timestamp: datetime = Field(..., description="Overview timestamp")
    performance_score: PerformanceScore = Field(..., description="Performance score")
    apm: Dict[str, Any] = Field(..., description="APM metrics")
    database: Dict[str, Any] = Field(..., description="Database metrics")
    resources: Dict[str, Any] = Field(..., description="Resource metrics")
    system_health: Dict[str, Any] = Field(..., description="System health status")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2025-11-07T12:00:00Z",
                "performance_score": {
                    "score": 85.5,
                    "status": "good",
                    "deductions": [{"reason": "high_error_rate", "deduction": 10.0}],
                },
                "apm": {"error_rate": 2.5, "avg_latency": 125.5},
                "database": {"slow_queries": 25, "avg_duration_ms": 15.5},
                "resources": {"cpu_percent": 45.2, "memory_percent": 62.8},
                "system_health": {"status": "healthy", "uptime": 86400},
            }
        }
    )


# ============================================================================
# EXPORT SCHEMAS
# ============================================================================


class PrometheusExportResponse(BaseModel):
    """Prometheus export format response."""

    metrics: str = Field(..., description="Metrics in Prometheus format")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "metrics": "# TYPE http_requests_total counter\nhttp_requests_total 10000\n"
            }
        }
    )


class GrafanaTimeRange(BaseModel):
    """Grafana time range."""

    from_time: datetime = Field(..., alias="from", description="Start time")
    to_time: datetime = Field(..., alias="to", description="End time")

    model_config = ConfigDict(populate_by_name=True)


class GrafanaQueryRequest(BaseModel):
    """Grafana query request."""

    targets: List[str] = Field(..., description="Metric targets")
    range: GrafanaTimeRange = Field(..., description="Time range")
    max_data_points: int = Field(1000, ge=1, le=10000, description="Max data points")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "targets": ["cpu_usage", "memory_usage"],
                "range": {
                    "from": "2025-11-07T11:00:00Z",
                    "to": "2025-11-07T12:00:00Z",
                },
                "max_data_points": 1000,
            }
        }
    )


class GrafanaQueryResponse(BaseModel):
    """Grafana query response."""

    data: List[Dict[str, Any]] = Field(..., description="Time series data")
    timestamp: datetime = Field(..., description="Response timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {
                        "target": "cpu_usage",
                        "datapoints": [[45.2, 1699363200000], [46.5, 1699363260000]],
                    }
                ],
                "timestamp": "2025-11-07T12:00:00Z",
            }
        }
    )


# ============================================================================
# CONFIGURATION SCHEMAS
# ============================================================================


class MonitoringConfigResponse(BaseModel):
    """Monitoring configuration."""

    apm_enabled: bool = Field(..., description="APM monitoring enabled")
    db_monitoring_enabled: bool = Field(..., description="Database monitoring enabled")
    resource_monitoring_enabled: bool = Field(
        ..., description="Resource monitoring enabled"
    )
    business_metrics_enabled: bool = Field(
        ..., description="Business metrics enabled"
    )
    anomaly_detection_enabled: bool = Field(
        ..., description="Anomaly detection enabled"
    )
    export_enabled: bool = Field(..., description="Metrics export enabled")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "apm_enabled": True,
                "db_monitoring_enabled": True,
                "resource_monitoring_enabled": True,
                "business_metrics_enabled": True,
                "anomaly_detection_enabled": True,
                "export_enabled": True,
            }
        }
    )


class MonitoringConfigUpdateRequest(BaseModel):
    """Monitoring configuration update."""

    apm_enabled: Optional[bool] = Field(None, description="APM monitoring enabled")
    db_monitoring_enabled: Optional[bool] = Field(
        None, description="Database monitoring enabled"
    )
    resource_monitoring_enabled: Optional[bool] = Field(
        None, description="Resource monitoring enabled"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"apm_enabled": True, "db_monitoring_enabled": False}
        }
    )


# ============================================================================
# ACTION SCHEMAS
# ============================================================================


class ServiceActionResponse(BaseModel):
    """Service action result."""

    success: bool = Field(..., description="Action success status")
    message: str = Field(..., description="Action result message")
    timestamp: datetime = Field(..., description="Action timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Monitoring services started successfully",
                "timestamp": "2025-11-07T12:00:00Z",
            }
        }
    )


class StatsResetResponse(BaseModel):
    """Statistics reset result."""

    message: str = Field(..., description="Reset result message")
    timestamp: datetime = Field(..., description="Reset timestamp")
    reset_by: str = Field(..., description="User who performed reset")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "All monitoring statistics have been reset",
                "timestamp": "2025-11-07T12:00:00Z",
                "reset_by": "admin-user-123",
            }
        }
    )
