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
    # OPTIMIZED: Dynamic pool sizing based on worker count
    # Formula: base_size + (workers * 4) with overflow buffer
    DATABASE_POOL_SIZE: int = Field(
        default=50,  # Increased from 30 (92% utilization fix)
        ge=20,
        le=100,
        description="Database connection pool size (base + worker scaling)",
    )
    DATABASE_POOL_MAX_OVERFLOW: int = Field(
        default=20,  # Reduced from 40 (more predictable sizing)
        ge=10,
        le=50,
        description="Maximum overflow connections beyond pool size",
    )
    DATABASE_POOL_TIMEOUT_SECONDS: int = Field(
        default=30, ge=10, le=60, description="Pool connection timeout in seconds"
    )
    DATABASE_POOL_RECYCLE_SECONDS: int = Field(
        default=1800,  # OPTIMIZED: Reduced from 3600 (30min prevents stale SSL connections)
        ge=600,
        le=7200,
        description="Connection recycle time in seconds (prevents SSL timeout errors)",
    )
    DATABASE_POOL_PRE_PING: bool = Field(
        default=True,
        description="Validate connections before use (prevents SSL errors)",
    )
    DATABASE_POOL_RESET_ON_RETURN: str = Field(
        default="commit",
        description="Reset mode when returning to pool: commit, rollback, or none",
    )
    DATABASE_STATEMENT_TIMEOUT_MS: int = Field(
        default=30000,
        ge=5000,
        le=120000,
        description="Statement timeout in milliseconds",
    )
    DATABASE_SLOW_QUERY_THRESHOLD_SECONDS: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Database slow query threshold in seconds",
    )
    # Query Timeout Settings (for async operations)
    DB_QUERY_TIMEOUT_READ: int = Field(
        default=5,
        ge=1,
        le=30,
        description="Read query timeout in seconds (async operations)",
    )
    DB_QUERY_TIMEOUT_WRITE: int = Field(
        default=10,
        ge=5,
        le=60,
        description="Write query timeout in seconds (async operations)",
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
    REDIS_ENABLE_SERVICE: bool = Field(default=True, description="Enable Redis service")

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
    # OPTIMIZED: Reduced pool size, improved timeouts for SSL/TLS
    REDIS_POOL_MAX_CONNECTIONS: int = Field(
        default=20,  # Reduced from 50 (Redis needs fewer connections than DB)
        ge=10,
        le=100,
        description="Redis maximum connections in pool",
    )
    REDIS_SOCKET_TIMEOUT_SECONDS: float = Field(
        default=5.0,  # OPTIMIZED: Reduced from 10.0 (SSL handshake should be fast)
        ge=1.0,
        le=30.0,
        description="Redis socket operation timeout in seconds",
    )
    REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS: float = Field(
        default=2.0,  # OPTIMIZED: Reduced from 5.0 (connection should be quick)
        ge=1.0,
        le=10.0,
        description="Redis connection timeout in seconds (SSL/TLS optimized)",
    )
    REDIS_ENABLE_RETRY_ON_TIMEOUT: bool = Field(
        default=True, description="Retry Redis operations on timeout"
    )
    REDIS_MAX_RETRY_ATTEMPTS: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for failed operations",
    )
    REDIS_HEALTH_CHECK_INTERVAL_SECONDS: int = Field(
        default=30,
        ge=10,
        le=300,
        description="Redis connection health check interval in seconds",
    )
    REDIS_ENABLE_HEALTH_CHECK: bool = Field(
        default=True, description="Enable periodic connection health checks"
    )
    REDIS_ENABLE_DECODE_RESPONSES: bool = Field(
        default=True, description="Redis decode responses to strings"
    )
    # Redis Operation Timeout
    REDIS_OPERATION_TIMEOUT: int = Field(
        default=5,
        ge=1,
        le=30,
        description="Redis operation timeout in seconds",
    )

    # SSL/TLS Optimization - Direct ENV names
    REDIS_SSL_SESSION_REUSE: bool = Field(
        default=True,
        description="Enable SSL session reuse to reduce handshake overhead",
    )
    REDIS_SSL_CONNECTION_POOL_WARMUP: bool = Field(
        default=True,
        description="Pre-create connections on startup (amortize SSL handshake cost)",
    )
    REDIS_SSL_WARMUP_CONNECTIONS: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of connections to pre-create during warmup",
    )

    # Redis Database Isolation - Direct ENV names
    REDIS_ENABLE_DB_ISOLATION: bool = Field(
        default=True, description="Enable separate DBs for cache vs broker"
    )
    REDIS_CACHE_DB_NUMBER: int = Field(
        default=1, description="Redis database number for cache (0-15)"
    )
    REDIS_BROKER_DB_NUMBER: int = Field(
        default=0, description="Redis database number for Celery broker (0-15)"
    )
    REDIS_SESSION_DB_NUMBER: int = Field(
        default=2, description="Redis database number for sessions (0-15)"
    )
    REDIS_RATE_LIMIT_DB_NUMBER: int = Field(
        default=3, description="Redis database number for rate limiting (0-15)"
    )
