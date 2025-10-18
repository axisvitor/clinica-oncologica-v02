"""
Monitoring configuration module: Sentry, logging, APM, error tracking, and resource monitoring.
"""

from pydantic import Field
from typing import Optional
from .base import BaseAppSettings


class MonitoringSettings(BaseAppSettings):
    """Configuration for monitoring, logging, and error tracking."""

    # ============================================================================
    # Logging Configuration (Enhanced for Critical Bug Fixes)
    # ============================================================================
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format",
    )
    MAX_LOGS_PER_SECOND: int = Field(
        default=100,
        description="Maximum logs per second to prevent rate limiting (Railway limit: 500/sec)",
    )
    ENABLE_REQUEST_LOGGING: bool = Field(
        default=True,
        description="Enable request logging middleware (uses DEBUG level for routine operations)",
    )
    LOG_STACK_TRACES: bool = Field(
        default=True, description="Enable stack trace logging for errors"
    )
    LOG_DEDUPLICATION_WINDOW: int = Field(
        default=300,
        description="Time window in seconds for log deduplication (5 minutes)",
    )

    # ============================================================================
    # Error Tracking Configuration (Critical Bug Fixes)
    # ============================================================================
    ENABLE_ERROR_TRACKING: bool = Field(
        default=True, description="Enable centralized error tracking and logging"
    )
    MAX_ERROR_LOGS: int = Field(
        default=1000,
        description="Maximum number of error logs to store in database",
    )
    ERROR_DEDUPLICATION_WINDOW: int = Field(
        default=3600,
        description="Time window in seconds for error deduplication (1 hour)",
    )
    ERROR_TRACKING_RATE_LIMIT: int = Field(
        default=10,
        description="Maximum error logs per minute for same error type",
    )
    CRITICAL_ERROR_NOTIFICATION: bool = Field(
        default=True,
        description="Enable notifications for critical errors (DI, role enum, schema issues)",
    )

    # ============================================================================
    # Sentry Error Tracking
    # ============================================================================
    SENTRY_DSN: Optional[str] = Field(
        default=None,
        description="Sentry DSN for error tracking and performance monitoring. Get from https://sentry.io",
    )
    SENTRY_TRACES_SAMPLE_RATE: float = Field(
        default=0.1,
        description="Sentry traces sample rate (0.0-1.0). Higher in dev/staging, lower in production",
    )

    # ============================================================================
    # APM Configuration (Application Performance Monitoring)
    # ============================================================================
    APM_APDEX_THRESHOLD: float = Field(
        default=0.5, description="APM Apdex threshold in seconds"
    )
    APM_SLOW_REQUEST_THRESHOLD: float = Field(
        default=1.0, description="Slow request threshold in seconds"
    )

    # ============================================================================
    # Resource Monitoring
    # ============================================================================
    RESOURCE_SAMPLE_INTERVAL: float = Field(
        default=10.0, description="Resource monitoring sample interval"
    )
    RESOURCE_CPU_THRESHOLD: float = Field(
        default=80.0, description="CPU usage threshold percentage"
    )
    RESOURCE_MEMORY_THRESHOLD: float = Field(
        default=85.0, description="Memory usage threshold percentage"
    )

    # ============================================================================
    # Dashboard Configuration
    # ============================================================================
    DASHBOARD_UPDATE_INTERVAL: float = Field(
        default=5.0, description="Dashboard update interval in seconds"
    )

    # ============================================================================
    # Monitoring System Configuration
    # ============================================================================
    MONITORING_ENABLED: bool = Field(
        default=True, description="Enable comprehensive monitoring system"
    )
    MONITORING_DEBUG: bool = Field(
        default=False, description="Enable monitoring debug mode"
    )
    MONITORING_REDIS_HOST: str = Field(
        default="localhost", description="Redis host for monitoring"
    )
    MONITORING_REDIS_PORT: int = Field(
        default=6379, description="Redis port for monitoring"
    )
    MONITORING_REDIS_DB: int = Field(
        default=1, description="Redis database for monitoring"
    )
    MONITORING_REDIS_PASSWORD: Optional[str] = Field(
        default=None, description="Redis password for monitoring"
    )
