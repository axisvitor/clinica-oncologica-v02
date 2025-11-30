"""
Database configuration module: PostgreSQL (AWS RDS) and Redis settings.
ENV Variable Naming Convention: {CATEGORY}_{SUBCATEGORY}_{ATTRIBUTE}_{UNIT}
"""

from pydantic import Field
from typing import Optional
from .base import BaseAppSettings


class DatabaseSettings(BaseAppSettings):
    """Database configuration for PostgreSQL and Redis."""

    # ============================================================================
    # PostgreSQL (AWS RDS)
    # ============================================================================
    DATABASE_URL: str = Field(..., description="AWS RDS PostgreSQL connection string")

    # Pool Settings - Direct ENV names
    DATABASE_POOL_SIZE: int = Field(
        default=30,
        description="Database connection pool size"
    )
    DATABASE_POOL_MAX_OVERFLOW: int = Field(
        default=40,
        description="Maximum overflow connections beyond pool size"
    )
    DATABASE_POOL_TIMEOUT_SECONDS: int = Field(
        default=30,
        description="Pool connection timeout in seconds"
    )
    DATABASE_POOL_RECYCLE_SECONDS: int = Field(
        default=3600,
        description="Connection recycle time in seconds"
    )
    DATABASE_STATEMENT_TIMEOUT_MS: int = Field(
        default=30000,
        description="Statement timeout in milliseconds"
    )
    DATABASE_SLOW_QUERY_THRESHOLD_SECONDS: float = Field(
        default=1.0,
        description="Database slow query threshold in seconds"
    )

    # ============================================================================
    # Redis Configuration
    # ============================================================================

    # Connection Settings
    REDIS_URL: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL (use redis:// or rediss:// for SSL)",
    )
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redis password")
    REDIS_HOST: str = Field(default="localhost", description="Redis host")
    REDIS_PORT: int = Field(default=6379, description="Redis port")

    # Service Enable - Direct ENV name
    REDIS_ENABLE_SERVICE: bool = Field(
        default=True,
        description="Enable Redis service"
    )

    # SSL/TLS Configuration - Direct ENV name
    REDIS_ENABLE_SSL: bool = Field(
        default=False,
        description="Enable SSL/TLS for Redis connection (use rediss:// URL or set to True)",
    )
    REDIS_SSL_CERT_REQS: str = Field(
        default="required",
        description="Redis SSL certificate requirements: none, optional, required (SECURITY: Use 'required' for production)",
    )
    REDIS_SSL_MIN_VERSION: Optional[str] = Field(
        default=None,
        description="Minimum TLS version: 'TLSV1_2' or 'TLSV1_3'. Leave empty for auto-negotiation.",
    )
    REDIS_SSL_CA_CERTS: Optional[str] = Field(
        default=None,
        description="Path to CA certificate bundle (absolute or relative to BASE_DIR). If not specified with CERT_REQUIRED, will use certifi.",
    )

    # Connection Pool Settings - Direct ENV names
    REDIS_POOL_MAX_CONNECTIONS: int = Field(
        default=50,
        description="Redis maximum connections in pool"
    )
    REDIS_SOCKET_TIMEOUT_SECONDS: float = Field(
        default=10.0,
        description="Redis socket timeout in seconds"
    )
    REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS: float = Field(
        default=5.0,
        description="Redis connection timeout in seconds"
    )
    REDIS_ENABLE_RETRY_ON_TIMEOUT: bool = Field(
        default=True,
        description="Retry Redis operations on timeout"
    )
    REDIS_HEALTH_CHECK_INTERVAL_SECONDS: int = Field(
        default=30,
        description="Redis connection health check interval in seconds"
    )
    REDIS_ENABLE_DECODE_RESPONSES: bool = Field(
        default=True,
        description="Redis decode responses to strings"
    )

    # Redis Database Isolation - Direct ENV names
    REDIS_ENABLE_DB_ISOLATION: bool = Field(
        default=True, description="Enable separate DBs for cache vs broker"
    )
    REDIS_CACHE_DB_NUMBER: int = Field(
        default=1,
        description="Redis database number for cache (0-15)"
    )
    REDIS_BROKER_DB_NUMBER: int = Field(
        default=0,
        description="Redis database number for Celery broker (0-15)"
    )
    REDIS_SESSION_DB_NUMBER: int = Field(
        default=2,
        description="Redis database number for sessions (0-15)"
    )
    REDIS_RATE_LIMIT_DB_NUMBER: int = Field(
        default=3,
        description="Redis database number for rate limiting (0-15)"
    )
