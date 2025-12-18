"""
Health Check Schemas for API V2

Comprehensive Pydantic V2 schemas for unified health monitoring system.
Consolidates all health check, metrics, and monitoring schemas.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


# ============================================================================
# Enums
# ============================================================================


class HealthStatus(str, Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class IncidentSeverity(str, Enum):
    """Incident severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertLevel(str, Enum):
    """Alert levels for health monitoring."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ============================================================================
# Basic Health Responses (PUBLIC endpoints)
# ============================================================================


class HealthResponse(BaseModel):
    """Basic health check response (PUBLIC endpoint)."""

    status: HealthStatus = Field(description="Overall health status")
    timestamp: datetime = Field(description="Response timestamp")
    version: str = Field(description="API version")
    environment: str = Field(description="Environment name")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "timestamp": "2025-01-17T15:00:00Z",
                "version": "2.0.0",
                "environment": "production",
            }
        }
    )


class ReadinessProbe(BaseModel):
    """Kubernetes/Railway readiness probe response."""

    ready: bool = Field(description="Service ready to receive traffic")
    checks: Dict[str, bool] = Field(description="Component readiness checks")
    timestamp: datetime = Field(description="Check timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ready": True,
                "checks": {"database": True, "redis": True, "workers": True},
                "timestamp": "2025-01-17T15:00:00Z",
            }
        }
    )


class LivenessProbe(BaseModel):
    """Kubernetes/Railway liveness probe response."""

    alive: bool = Field(description="Service is alive")
    uptime_seconds: int = Field(description="Service uptime in seconds")
    timestamp: datetime = Field(description="Check timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "alive": True,
                "uptime_seconds": 3600,
                "timestamp": "2025-01-17T15:00:00Z",
            }
        }
    )


# ============================================================================
# Component Health Checks
# ============================================================================


class DatabaseHealth(BaseModel):
    """Database health check details."""

    status: HealthStatus = Field(description="Database status")
    latency_ms: float = Field(description="Query latency in milliseconds")
    pool_size: int = Field(description="Connection pool size")
    active_connections: int = Field(description="Active connections")
    available_connections: int = Field(description="Available connections")
    pool_utilization_percent: float = Field(description="Pool utilization percentage")
    rls_enabled: bool = Field(default=False, description="Row Level Security enabled")
    migrations_current: bool = Field(description="Migrations up to date")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "latency_ms": 5.2,
                "pool_size": 20,
                "active_connections": 5,
                "available_connections": 15,
                "pool_utilization_percent": 25.0,
                "rls_enabled": True,
                "migrations_current": True,
            }
        }
    )


class RedisHealth(BaseModel):
    """Redis/cache health check details."""

    status: HealthStatus = Field(description="Redis status")
    latency_ms: float = Field(description="Ping latency in milliseconds")
    memory_used_mb: float = Field(description="Memory used in MB")
    memory_peak_mb: float = Field(description="Peak memory in MB")
    hit_rate_percent: float = Field(description="Cache hit rate percentage")
    connected_clients: int = Field(description="Number of connected clients")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "latency_ms": 1.5,
                "memory_used_mb": 128.5,
                "memory_peak_mb": 256.0,
                "hit_rate_percent": 85.5,
                "connected_clients": 10,
            }
        }
    )


class WorkerHealth(BaseModel):
    """Background worker health check details."""

    status: HealthStatus = Field(description="Worker status")
    active_workers: int = Field(description="Number of active workers")
    active_tasks: int = Field(description="Number of active tasks")
    failed_tasks_24h: int = Field(description="Failed tasks in last 24 hours")
    pending_tasks: int = Field(description="Number of pending tasks")
    queue_size: int = Field(description="Current queue size")
    avg_task_duration_seconds: float = Field(description="Average task duration")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "active_workers": 4,
                "active_tasks": 12,
                "failed_tasks_24h": 2,
                "pending_tasks": 5,
                "queue_size": 17,
                "avg_task_duration_seconds": 2.5,
            }
        }
    )


class ExternalServiceHealth(BaseModel):
    """External service health check."""

    name: str = Field(description="Service name")
    status: HealthStatus = Field(description="Service status")
    latency_ms: Optional[float] = Field(None, description="Response latency")
    last_check: datetime = Field(description="Last check timestamp")
    error_message: Optional[str] = Field(None, description="Error message if unhealthy")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Evolution API",
                "status": "healthy",
                "latency_ms": 150.0,
                "last_check": "2025-01-17T15:00:00Z",
                "error_message": None,
            }
        }
    )


class StorageHealth(BaseModel):
    """Storage health check details."""

    status: HealthStatus = Field(description="Storage status")
    available_space_gb: float = Field(description="Available space in GB")
    used_space_gb: float = Field(description="Used space in GB")
    total_space_gb: float = Field(description="Total space in GB")
    utilization_percent: float = Field(description="Storage utilization percentage")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "available_space_gb": 450.0,
                "used_space_gb": 50.0,
                "total_space_gb": 500.0,
                "utilization_percent": 10.0,
            }
        }
    )


# ============================================================================
# Detailed Health Response
# ============================================================================


class DetailedHealthResponse(BaseModel):
    """Detailed health check with all components."""

    status: HealthStatus = Field(description="Overall health status")
    health_score: float = Field(ge=0, le=100, description="Health score (0-100)")
    timestamp: datetime = Field(description="Response timestamp")
    version: str = Field(description="API version")
    environment: str = Field(description="Environment name")

    # Component health
    database: DatabaseHealth = Field(description="Database health")
    redis: RedisHealth = Field(description="Redis health")
    workers: WorkerHealth = Field(description="Worker health")
    external_services: List[ExternalServiceHealth] = Field(
        description="External services"
    )
    storage: StorageHealth = Field(description="Storage health")

    # Performance
    response_time_ms: float = Field(description="Health check response time")
    uptime_seconds: int = Field(description="Service uptime")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "health_score": 95.5,
                "timestamp": "2025-01-17T15:00:00Z",
                "version": "2.0.0",
                "environment": "production",
                "database": {"status": "healthy", "latency_ms": 5.2},
                "redis": {"status": "healthy", "latency_ms": 1.5},
                "workers": {"status": "healthy", "active_workers": 4},
                "external_services": [],
                "storage": {"status": "healthy", "utilization_percent": 10.0},
                "response_time_ms": 25.5,
                "uptime_seconds": 3600,
            }
        }
    )


# ============================================================================
# Metrics Responses
# ============================================================================


class SystemMetrics(BaseModel):
    """System resource metrics."""

    cpu_percent: float = Field(description="CPU usage percentage")
    memory_percent: float = Field(description="Memory usage percentage")
    memory_used_mb: float = Field(description="Memory used in MB")
    memory_available_mb: float = Field(description="Memory available in MB")
    disk_usage_percent: float = Field(description="Disk usage percentage")
    disk_free_gb: float = Field(description="Disk free in GB")
    network_bytes_sent: int = Field(description="Network bytes sent")
    network_bytes_recv: int = Field(description="Network bytes received")
    process_count: int = Field(description="Number of processes")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cpu_percent": 45.2,
                "memory_percent": 62.5,
                "memory_used_mb": 2048.0,
                "memory_available_mb": 1280.0,
                "disk_usage_percent": 55.0,
                "disk_free_gb": 450.0,
                "network_bytes_sent": 1048576,
                "network_bytes_recv": 2097152,
                "process_count": 128,
            }
        }
    )


class ApplicationMetrics(BaseModel):
    """Application-level metrics."""

    total_requests: int = Field(description="Total requests processed")
    requests_per_second: float = Field(description="Current request rate")
    avg_response_time_ms: float = Field(description="Average response time")
    error_rate_percent: float = Field(description="Error rate percentage")
    active_sessions: int = Field(description="Active user sessions")
    cache_hit_rate: float = Field(description="Cache hit rate percentage")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_requests": 125000,
                "requests_per_second": 45.5,
                "avg_response_time_ms": 125.5,
                "error_rate_percent": 0.5,
                "active_sessions": 150,
                "cache_hit_rate": 85.5,
            }
        }
    )


class CustomMetrics(BaseModel):
    """Custom business metrics."""

    active_patients: int = Field(description="Number of active patients")
    messages_sent_24h: int = Field(description="Messages sent in last 24h")
    quizzes_completed_24h: int = Field(description="Quizzes completed in last 24h")
    alerts_triggered_24h: int = Field(description="Alerts triggered in last 24h")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "active_patients": 250,
                "messages_sent_24h": 1500,
                "quizzes_completed_24h": 125,
                "alerts_triggered_24h": 5,
            }
        }
    )


class PrometheusMetrics(BaseModel):
    """Prometheus-compatible metrics response."""

    metrics: str = Field(description="Metrics in Prometheus format")
    timestamp: datetime = Field(description="Metrics timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "metrics": '# HELP health_status Current health status\nhealth_status{component="database"} 1.0\n',
                "timestamp": "2025-01-17T15:00:00Z",
            }
        }
    )


class MetricsResponse(BaseModel):
    """Comprehensive metrics response."""

    system: SystemMetrics = Field(description="System metrics")
    application: ApplicationMetrics = Field(description="Application metrics")
    custom: CustomMetrics = Field(description="Custom business metrics")
    timestamp: datetime = Field(description="Metrics timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "system": {"cpu_percent": 45.2, "memory_percent": 62.5},
                "application": {"total_requests": 125000, "error_rate_percent": 0.5},
                "custom": {"active_patients": 250, "messages_sent_24h": 1500},
                "timestamp": "2025-01-17T15:00:00Z",
            }
        }
    )


# ============================================================================
# Platform-Specific Health
# ============================================================================


class RailwayHealth(BaseModel):
    """Railway-specific health check."""

    status: HealthStatus = Field(description="Railway service status")
    service_id: Optional[str] = Field(None, description="Railway service ID")
    deployment_id: Optional[str] = Field(None, description="Deployment ID")
    region: Optional[str] = Field(None, description="Deployment region")
    environment_variables_set: bool = Field(description="Required env vars set")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "service_id": "srv_abc123",
                "deployment_id": "dep_xyz789",
                "region": "us-west1",
                "environment_variables_set": True,
            }
        }
    )


class ProductionHealth(BaseModel):
    """Production environment health."""

    status: HealthStatus = Field(description="Production status")
    environment: str = Field(description="Environment name")
    build_version: Optional[str] = Field(None, description="Build version")
    deployment_time: Optional[datetime] = Field(
        None, description="Deployment timestamp"
    )
    debug_mode: bool = Field(description="Debug mode enabled")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "environment": "production",
                "build_version": "2.0.0-abc123",
                "deployment_time": "2025-01-17T14:00:00Z",
                "debug_mode": False,
            }
        }
    )


class EnvironmentHealth(BaseModel):
    """Environment configuration health."""

    status: HealthStatus = Field(description="Environment status")
    required_vars_set: int = Field(description="Required variables set")
    total_required_vars: int = Field(description="Total required variables")
    missing_vars: List[str] = Field(description="Missing variable names")
    configuration_valid: bool = Field(description="Configuration is valid")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "required_vars_set": 15,
                "total_required_vars": 15,
                "missing_vars": [],
                "configuration_valid": True,
            }
        }
    )


# ============================================================================
# Advanced Monitoring
# ============================================================================


class HealthHistoryEntry(BaseModel):
    """Single health history entry."""

    timestamp: datetime = Field(description="Entry timestamp")
    status: HealthStatus = Field(description="Health status")
    health_score: float = Field(description="Health score (0-100)")
    component_statuses: Dict[str, HealthStatus] = Field(
        description="Component statuses"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2025-01-17T15:00:00Z",
                "status": "healthy",
                "health_score": 95.5,
                "component_statuses": {
                    "database": "healthy",
                    "redis": "healthy",
                    "workers": "healthy",
                },
            }
        }
    )


class HealthHistory(BaseModel):
    """Health check history (last 24 hours)."""

    entries: List[HealthHistoryEntry] = Field(description="History entries")
    period_hours: int = Field(description="History period in hours")
    avg_health_score: float = Field(description="Average health score")
    total_checks: int = Field(description="Total checks performed")
    degraded_periods: int = Field(description="Number of degraded periods")
    unhealthy_periods: int = Field(description="Number of unhealthy periods")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entries": [],
                "period_hours": 24,
                "avg_health_score": 95.0,
                "total_checks": 288,
                "degraded_periods": 2,
                "unhealthy_periods": 0,
            }
        }
    )


class HealthIncident(BaseModel):
    """Health incident log entry."""

    id: str = Field(description="Incident ID")
    timestamp: datetime = Field(description="Incident timestamp")
    component: str = Field(description="Affected component")
    severity: IncidentSeverity = Field(description="Incident severity")
    message: str = Field(description="Incident description")
    resolved: bool = Field(description="Incident resolved")
    resolved_at: Optional[datetime] = Field(None, description="Resolution timestamp")
    duration_seconds: Optional[int] = Field(None, description="Incident duration")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "inc_abc123",
                "timestamp": "2025-01-17T14:30:00Z",
                "component": "database",
                "severity": "high",
                "message": "Database connection pool exhausted",
                "resolved": True,
                "resolved_at": "2025-01-17T14:35:00Z",
                "duration_seconds": 300,
            }
        }
    )


class HealthIncidentsResponse(BaseModel):
    """Health incidents log response."""

    incidents: List[HealthIncident] = Field(description="Incident entries")
    total_incidents: int = Field(description="Total incidents")
    active_incidents: int = Field(description="Active incidents")
    resolved_incidents: int = Field(description="Resolved incidents")
    period_hours: int = Field(description="Reporting period")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "incidents": [],
                "total_incidents": 5,
                "active_incidents": 1,
                "resolved_incidents": 4,
                "period_hours": 24,
            }
        }
    )


class HealthAlert(BaseModel):
    """Active health alert."""

    id: str = Field(description="Alert ID")
    level: AlertLevel = Field(description="Alert level")
    component: str = Field(description="Affected component")
    message: str = Field(description="Alert message")
    threshold: float = Field(description="Threshold value")
    current_value: float = Field(description="Current value")
    triggered_at: datetime = Field(description="Alert trigger timestamp")
    acknowledged: bool = Field(default=False, description="Alert acknowledged")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "alert_xyz789",
                "level": "warning",
                "component": "redis",
                "message": "Redis memory usage exceeds threshold",
                "threshold": 80.0,
                "current_value": 85.5,
                "triggered_at": "2025-01-17T15:00:00Z",
                "acknowledged": False,
            }
        }
    )


class HealthAlertsResponse(BaseModel):
    """Active health alerts response."""

    alerts: List[HealthAlert] = Field(description="Active alerts")
    total_alerts: int = Field(description="Total active alerts")
    critical_count: int = Field(description="Critical alerts")
    warning_count: int = Field(description="Warning alerts")
    info_count: int = Field(description="Info alerts")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "alerts": [],
                "total_alerts": 3,
                "critical_count": 0,
                "warning_count": 2,
                "info_count": 1,
            }
        }
    )


# ============================================================================
# Manual Test Response
# ============================================================================


class HealthTestRequest(BaseModel):
    """Manual health test request."""

    components: Optional[List[str]] = Field(
        None, description="Specific components to test (null = all)"
    )
    include_detailed: bool = Field(
        default=True, description="Include detailed diagnostics"
    )
    force_refresh: bool = Field(default=False, description="Force cache refresh")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "components": ["database", "redis"],
                "include_detailed": True,
                "force_refresh": True,
            }
        }
    )


class HealthTestResponse(BaseModel):
    """Manual health test response."""

    test_id: str = Field(description="Test execution ID")
    timestamp: datetime = Field(description="Test timestamp")
    status: HealthStatus = Field(description="Overall test status")
    components_tested: List[str] = Field(description="Components tested")
    results: Dict[str, Any] = Field(description="Detailed test results")
    duration_ms: float = Field(description="Test duration in milliseconds")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "test_id": "test_abc123",
                "timestamp": "2025-01-17T15:00:00Z",
                "status": "healthy",
                "components_tested": ["database", "redis", "workers"],
                "results": {},
                "duration_ms": 125.5,
            }
        }
    )
