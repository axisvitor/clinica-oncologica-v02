"""
Dashboard and aggregation schemas.
Dashboard snapshots, combined metrics, real-time status.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field, ConfigDict


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
    active_connections: int = Field(
        ..., ge=0, description="Active WebSocket connections"
    )
    metrics_snapshot: DashboardMetricsSnapshot = Field(
        ..., description="Metrics snapshot"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2025-11-07T12:00:00-03:00",
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
                    "from": "2025-11-07T11:00:00-03:00",
                    "to": "2025-11-07T12:00:00-03:00",
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
                "timestamp": "2025-11-07T12:00:00-03:00",
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
    business_metrics_enabled: bool = Field(..., description="Business metrics enabled")
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
                "timestamp": "2025-11-07T12:00:00-03:00",
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
                "timestamp": "2025-11-07T12:00:00-03:00",
                "reset_by": "admin-user-123",
            }
        }
    )
