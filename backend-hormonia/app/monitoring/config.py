"""
Monitoring System Configuration.

Configuration for all monitoring components including thresholds,
intervals, and feature flags.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import timedelta
import os


class APMConfig(BaseModel):
    """APM monitoring configuration."""
    enabled: bool = Field(default=True, description="Enable APM monitoring")
    apdex_threshold: float = Field(default=0.5, description="Apdex threshold in seconds")
    apdex_toleration: float = Field(default=2.0, description="Apdex toleration in seconds")
    slow_request_threshold: float = Field(default=1.0, description="Slow request threshold in seconds")
    error_rate_threshold: float = Field(default=5.0, description="Error rate threshold percentage")
    max_stored_requests: int = Field(default=10000, description="Maximum stored request metrics")

    # Endpoint-specific thresholds
    endpoint_thresholds: Dict[str, Dict[str, float]] = Field(
        default_factory=lambda: {
            "POST /api/v2/messages": {"response_time": 2.0, "error_rate": 3.0},
            "POST /api/v2/quiz": {"response_time": 1.5, "error_rate": 2.0},
            "GET /api/v2/patients": {"response_time": 0.5, "error_rate": 1.0},
            "POST /api/v2/auth/login": {"response_time": 1.0, "error_rate": 5.0}
        }
    )


class DatabaseMonitorConfig(BaseModel):
    """Database monitoring configuration."""
    enabled: bool = Field(default=True, description="Enable database monitoring")
    slow_query_threshold: float = Field(default=1.0, description="Slow query threshold in seconds")
    very_slow_query_threshold: float = Field(default=5.0, description="Very slow query threshold")
    connection_pool_utilization_threshold: float = Field(default=80.0, description="Pool utilization threshold")
    max_stored_queries: int = Field(default=5000, description="Maximum stored query metrics")

    # Query type thresholds
    query_thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "SELECT": 0.5,
            "INSERT": 1.0,
            "UPDATE": 1.5,
            "DELETE": 2.0
        }
    )


class ResourceMonitorConfig(BaseModel):
    """Resource monitoring configuration."""
    enabled: bool = Field(default=True, description="Enable resource monitoring")
    sample_interval: float = Field(default=10.0, description="Sampling interval in seconds")
    cpu_threshold: float = Field(default=80.0, description="CPU usage threshold percentage")
    memory_threshold: float = Field(default=85.0, description="Memory usage threshold percentage")
    disk_threshold: float = Field(default=90.0, description="Disk usage threshold percentage")
    network_threshold: float = Field(default=100.0, description="Network usage threshold MB/s")
    max_snapshots: int = Field(default=720, description="Maximum stored snapshots (2 hours at 10s)")

    # Alert thresholds by severity
    alert_thresholds: Dict[str, Dict[str, float]] = Field(
        default_factory=lambda: {
            "warning": {"cpu": 70.0, "memory": 75.0, "disk": 80.0},
            "critical": {"cpu": 90.0, "memory": 95.0, "disk": 95.0}
        }
    )


class BusinessMetricsConfig(BaseModel):
    """Business metrics configuration."""
    enabled: bool = Field(default=True, description="Enable business metrics")
    patient_flow_timeout: float = Field(default=30.0, description="Patient flow timeout in minutes")
    message_delivery_timeout: float = Field(default=30.0, description="Message delivery timeout in seconds")
    ai_response_timeout: float = Field(default=10.0, description="AI response timeout in seconds")
    max_stored_metrics: int = Field(default=10000, description="Maximum stored business metrics")

    # Success rate thresholds
    success_rate_thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "patient_flow": 95.0,
            "message_delivery": 98.0,
            "ai_response": 90.0,
            "quiz_completion": 85.0,
            "treatment_adherence": 80.0
        }
    )


class DashboardConfig(BaseModel):
    """Real-time dashboard configuration."""
    enabled: bool = Field(default=True, description="Enable real-time dashboard")
    update_interval: float = Field(default=5.0, description="Dashboard update interval in seconds")
    max_connections: int = Field(default=100, description="Maximum WebSocket connections")
    websocket_timeout: float = Field(default=300.0, description="WebSocket timeout in seconds")

    # Dashboard features
    features: Dict[str, bool] = Field(
        default_factory=lambda: {
            "real_time_metrics": True,
            "alerts": True,
            "anomaly_detection": True,
            "historical_charts": True,
            "export_metrics": True
        }
    )


class AnomalyDetectionConfig(BaseModel):
    """Anomaly detection configuration."""
    enabled: bool = Field(default=True, description="Enable anomaly detection")
    z_score_threshold: float = Field(default=3.0, description="Z-score threshold for anomalies")
    trend_threshold: float = Field(default=0.3, description="Trend change threshold")
    minimum_data_points: int = Field(default=30, description="Minimum data points for detection")
    window_size: int = Field(default=100, description="Window size for statistical analysis")

    # Metric-specific configurations
    metric_configs: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
            "response_time_p95": {"z_threshold": 2.5, "enable_trend": True},
            "error_rate": {"z_threshold": 2.0, "enable_trend": True},
            "cpu_percent": {"z_threshold": 2.0, "enable_trend": True},
            "memory_percent": {"z_threshold": 2.0, "enable_trend": True},
            "db_query_time": {"z_threshold": 3.0, "enable_trend": True}
        }
    )


class ExportConfig(BaseModel):
    """Metrics export configuration."""
    enabled: bool = Field(default=True, description="Enable metrics export")
    prometheus_enabled: bool = Field(default=True, description="Enable Prometheus export")
    grafana_enabled: bool = Field(default=True, description="Enable Grafana compatibility")
    export_interval: float = Field(default=30.0, description="Export interval in seconds")

    # Export endpoints
    prometheus_endpoint: str = Field(default="/metrics", description="Prometheus metrics endpoint")
    grafana_endpoint: str = Field(default="/api/v2/monitoring/grafana", description="Grafana API endpoint")

    # Retention settings
    retention_days: int = Field(default=7, description="Metrics retention in days")
    max_data_points: int = Field(default=1000, description="Maximum data points per query")


class RedisConfig(BaseModel):
    """Redis configuration for monitoring."""
    enabled: bool = Field(default=True, description="Enable Redis for monitoring")
    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    db: int = Field(default=1, description="Redis database for monitoring")
    password: Optional[str] = Field(default=None, description="Redis password")
    socket_timeout: float = Field(default=30.0, description="Redis socket timeout")

    # Key prefixes
    key_prefixes: Dict[str, str] = Field(
        default_factory=lambda: {
            "apm": "monitoring:apm:",
            "database": "monitoring:db:",
            "resources": "monitoring:resources:",
            "business": "monitoring:business:",
            "anomalies": "monitoring:anomalies:",
            "alerts": "monitoring:alerts:"
        }
    )


class MonitoringConfig(BaseModel):
    """Main monitoring system configuration."""
    enabled: bool = Field(default=True, description="Enable monitoring system")
    debug: bool = Field(default=False, description="Enable debug mode")

    # Component configurations
    apm: APMConfig = Field(default_factory=APMConfig)
    database: DatabaseMonitorConfig = Field(default_factory=DatabaseMonitorConfig)
    resources: ResourceMonitorConfig = Field(default_factory=ResourceMonitorConfig)
    business_metrics: BusinessMetricsConfig = Field(default_factory=BusinessMetricsConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    anomaly_detection: AnomalyDetectionConfig = Field(default_factory=AnomalyDetectionConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)

    # Global settings
    log_level: str = Field(default="INFO", description="Monitoring log level")
    startup_checks: bool = Field(default=True, description="Run startup health checks")
    graceful_shutdown: bool = Field(default=True, description="Enable graceful shutdown")

    @classmethod
    def from_env(cls) -> "MonitoringConfig":
        """Create configuration from environment variables."""
        config = cls()

        # Override with environment variables
        if os.getenv("MONITORING_ENABLED"):
            config.enabled = os.getenv("MONITORING_ENABLED").lower() == "true"

        if os.getenv("MONITORING_DEBUG"):
            config.debug = os.getenv("MONITORING_DEBUG").lower() == "true"

        # APM configuration
        if os.getenv("APM_APDEX_THRESHOLD"):
            config.apm.apdex_threshold = float(os.getenv("APM_APDEX_THRESHOLD"))

        if os.getenv("APM_SLOW_REQUEST_THRESHOLD"):
            config.apm.slow_request_threshold = float(os.getenv("APM_SLOW_REQUEST_THRESHOLD"))

        # Database configuration
        if os.getenv("DB_SLOW_QUERY_THRESHOLD"):
            config.database.slow_query_threshold = float(os.getenv("DB_SLOW_QUERY_THRESHOLD"))

        # Resource configuration
        if os.getenv("RESOURCE_SAMPLE_INTERVAL"):
            config.resources.sample_interval = float(os.getenv("RESOURCE_SAMPLE_INTERVAL"))

        if os.getenv("RESOURCE_CPU_THRESHOLD"):
            config.resources.cpu_threshold = float(os.getenv("RESOURCE_CPU_THRESHOLD"))

        if os.getenv("RESOURCE_MEMORY_THRESHOLD"):
            config.resources.memory_threshold = float(os.getenv("RESOURCE_MEMORY_THRESHOLD"))

        # Dashboard configuration
        if os.getenv("DASHBOARD_UPDATE_INTERVAL"):
            config.dashboard.update_interval = float(os.getenv("DASHBOARD_UPDATE_INTERVAL"))

        # Redis configuration
        if os.getenv("MONITORING_REDIS_HOST"):
            config.redis.host = os.getenv("MONITORING_REDIS_HOST")

        if os.getenv("MONITORING_REDIS_PORT"):
            config.redis.port = int(os.getenv("MONITORING_REDIS_PORT"))

        if os.getenv("MONITORING_REDIS_PASSWORD"):
            config.redis.password = os.getenv("MONITORING_REDIS_PASSWORD")

        return config

    def get_redis_url(self) -> str:
        """Get Redis connection URL with proper environment variable handling."""
        from urllib.parse import urlparse, urlunparse
        from app.config import settings

        # First priority: Use REDIS_URL environment variable if available (from settings)
        redis_url = settings.REDIS_URL
        if redis_url and not redis_url.startswith('redis://localhost'):
            # Parse URL to safely replace database number
            parsed = urlparse(redis_url)

            # Extract path and replace/add database number
            path = parsed.path or ''
            # Remove existing /N suffix if present
            if '/' in path and path.split('/')[-1].isdigit():
                path = '/'.join(path.split('/')[:-1])

            # Add monitoring DB (1)
            new_path = f"{path}/{self.redis.db}" if path else f"/{self.redis.db}"

            # Reconstruct URL with new path
            new_parsed = parsed._replace(path=new_path)
            return urlunparse(new_parsed)

        # Fallback: Construct URL from individual components for local development
        auth = f":{self.redis.password}@" if self.redis.password else ""
        return f"redis://{auth}{self.redis.host}:{self.redis.port}/{self.redis.db}"

    def is_feature_enabled(self, component: str, feature: str) -> bool:
        """Check if a specific feature is enabled."""
        if not self.enabled:
            return False

        component_config = getattr(self, component, None)
        if not component_config or not getattr(component_config, "enabled", True):
            return False

        if hasattr(component_config, "features"):
            return component_config.features.get(feature, False)

        return True

    def get_threshold(self, component: str, metric: str, default: float = 0.0) -> float:
        """Get threshold value for a metric."""
        component_config = getattr(self, component, None)
        if not component_config:
            return default

        # Try different threshold structures
        if hasattr(component_config, "alert_thresholds"):
            thresholds = component_config.alert_thresholds
            if isinstance(thresholds, dict):
                # Handle nested thresholds (e.g., by severity)
                for level, values in thresholds.items():
                    if metric in values:
                        return values[metric]

        if hasattr(component_config, f"{metric}_threshold"):
            return getattr(component_config, f"{metric}_threshold")

        return default


# Global configuration instance
monitoring_config = MonitoringConfig.from_env()


def get_monitoring_config() -> MonitoringConfig:
    """Get monitoring configuration instance."""
    return monitoring_config


def update_config_from_dict(updates: Dict[str, Any]) -> None:
    """Update configuration from dictionary."""
    global monitoring_config

    for key, value in updates.items():
        if hasattr(monitoring_config, key):
            if isinstance(getattr(monitoring_config, key), BaseModel):
                # Update nested configuration
                nested_config = getattr(monitoring_config, key)
                for nested_key, nested_value in value.items():
                    if hasattr(nested_config, nested_key):
                        setattr(nested_config, nested_key, nested_value)
            else:
                setattr(monitoring_config, key, value)


def validate_config() -> List[str]:
    """Validate configuration and return list of issues."""
    issues = []

    # Check required settings
    if monitoring_config.apm.apdex_threshold <= 0:
        issues.append("APM Apdex threshold must be positive")

    if monitoring_config.database.slow_query_threshold <= 0:
        issues.append("Database slow query threshold must be positive")

    if monitoring_config.resources.sample_interval <= 0:
        issues.append("Resource monitoring sample interval must be positive")

    if monitoring_config.dashboard.update_interval <= 0:
        issues.append("Dashboard update interval must be positive")

    # Check threshold ranges
    if not 0 <= monitoring_config.resources.cpu_threshold <= 100:
        issues.append("CPU threshold must be between 0 and 100")

    if not 0 <= monitoring_config.resources.memory_threshold <= 100:
        issues.append("Memory threshold must be between 0 and 100")

    # Check Redis configuration
    if monitoring_config.redis.enabled:
        if not monitoring_config.redis.host:
            issues.append("Redis host must be specified when Redis is enabled")

        if not 1 <= monitoring_config.redis.port <= 65535:
            issues.append("Redis port must be between 1 and 65535")

    return issues
