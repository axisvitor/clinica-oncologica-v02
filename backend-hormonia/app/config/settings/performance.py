"""
Performance configuration module: Database and Redis optimization settings.
Configures connection pools, timeouts, and caching strategies.
"""

from pydantic import Field, field_validator
from typing import Optional
from .base import BaseAppSettings


class PerformanceSettings(BaseAppSettings):
    """Performance and optimization configuration."""

    # ============================================================================
    # Database Connection Pool Optimization
    # ============================================================================

    # Dynamic pool sizing based on worker count
    # Formula: base_pool_size = workers * 4 (per worker) + overflow
    # For 8 workers: (8 * 4) + 20 = 52 total connections max
    DATABASE_POOL_SIZE_PER_WORKER: int = Field(
        default=4,
        ge=2,
        le=10,
        description="Connections per worker (multiplied by worker count)",
    )
    DATABASE_POOL_SIZE_BASE: int = Field(
        default=50,
        ge=20,
        le=100,
        description="Base pool size (overridden by dynamic calculation if workers known)",
    )
    DATABASE_POOL_MAX_OVERFLOW: int = Field(
        default=20,
        ge=10,
        le=50,
        description="Max overflow connections beyond pool size",
    )
    DATABASE_POOL_TIMEOUT_SECONDS: int = Field(
        default=30,
        ge=10,
        le=60,
        description="Pool connection acquisition timeout in seconds",
    )
    DATABASE_POOL_RECYCLE_SECONDS: int = Field(
        default=1800,  # 30 minutes (reduced from 1 hour)
        ge=600,
        le=7200,
        description="Recycle connections after this many seconds (prevents stale connections)",
    )
    DATABASE_POOL_PRE_PING: bool = Field(
        default=True,
        description="Test connection validity before using (prevents SSL errors)",
    )
    DATABASE_POOL_RESET_ON_RETURN: str = Field(
        default="commit",
        description="Reset mode when connection returned to pool: commit, rollback, or None",
    )

    # Query Performance
    DATABASE_STATEMENT_TIMEOUT_MS: int = Field(
        default=30000,  # 30 seconds
        ge=5000,
        le=120000,
        description="Statement timeout in milliseconds (kill slow queries)",
    )
    DATABASE_SLOW_QUERY_THRESHOLD_SECONDS: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Log queries slower than this threshold",
    )
    DATABASE_QUERY_CACHE_TTL_SECONDS: int = Field(
        default=60, ge=10, le=600, description="Default TTL for cached query results"
    )

    # Connection Monitoring
    DATABASE_POOL_MONITOR_INTERVAL_SECONDS: int = Field(
        default=60, ge=30, le=300, description="Pool statistics monitoring interval"
    )
    DATABASE_POOL_UTILIZATION_WARNING_THRESHOLD: float = Field(
        default=0.85,
        ge=0.5,
        le=0.95,
        description="Warn when pool utilization exceeds this percentage",
    )
    DATABASE_POOL_UTILIZATION_CRITICAL_THRESHOLD: float = Field(
        default=0.92,
        ge=0.8,
        le=0.99,
        description="Critical alert when pool utilization exceeds this percentage",
    )

    # ============================================================================
    # Redis Connection Pool Optimization
    # ============================================================================

    REDIS_POOL_SIZE: int = Field(
        default=20,
        ge=10,
        le=1000,
        description="Redis connection pool size (lower than DB pool)",
    )
    REDIS_POOL_MAX_CONNECTIONS: int = Field(
        default=50,
        ge=20,
        le=1000,
        description="Redis maximum connections in pool (total limit)",
    )

    # Timeout Configuration (optimized for Redis Cloud SSL/TLS)
    REDIS_SOCKET_TIMEOUT_SECONDS: float = Field(
        default=5.0,  # Reduced from 10s (SSL handshake should be fast)
        ge=1.0,
        le=30.0,
        description="Redis socket operation timeout in seconds",
    )
    REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS: float = Field(
        default=2.0,  # Reduced from 5s (connection should be quick)
        ge=1.0,
        le=10.0,
        description="Redis connection timeout in seconds",
    )
    REDIS_RETRY_ON_TIMEOUT: bool = Field(
        default=True, description="Automatically retry operations on timeout"
    )
    REDIS_MAX_RETRY_ATTEMPTS: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for failed operations",
    )

    # Health Check Configuration
    REDIS_HEALTH_CHECK_INTERVAL_SECONDS: int = Field(
        default=30,
        ge=10,
        le=300,
        description="Redis connection health check interval in seconds",
    )
    REDIS_ENABLE_HEALTH_CHECK: bool = Field(
        default=True, description="Enable periodic connection health checks"
    )

    # SSL/TLS Optimization
    REDIS_SSL_SESSION_REUSE: bool = Field(
        default=True,
        description="Enable SSL session reuse (reduces handshake overhead)",
    )
    REDIS_SSL_CONNECTION_POOL_WARMUP: bool = Field(
        default=True,
        description="Pre-create connections on startup (amortize SSL handshake cost)",
    )
    REDIS_SSL_WARMUP_CONNECTIONS: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of connections to pre-create on startup",
    )

    # ============================================================================
    # Caching Strategy
    # ============================================================================

    CACHE_DEFAULT_TTL_SECONDS: int = Field(
        default=300,  # 5 minutes
        ge=60,
        le=3600,
        description="Default cache TTL for generic data",
    )
    CACHE_QUERY_TTL_SECONDS: int = Field(
        default=60,  # 1 minute
        ge=10,
        le=600,
        description="Cache TTL for database query results",
    )
    CACHE_SESSION_TTL_SECONDS: int = Field(
        default=900,  # 15 minutes
        ge=300,
        le=3600,
        description="Cache TTL for user sessions",
    )
    CACHE_STATIC_DATA_TTL_SECONDS: int = Field(
        default=3600,  # 1 hour
        ge=600,
        le=86400,
        description="Cache TTL for static/rarely changing data",
    )

    # Cache Performance
    CACHE_ENABLE_COMPRESSION: bool = Field(
        default=True,
        description="Enable compression for cached data (reduces memory/network)",
    )
    CACHE_COMPRESSION_THRESHOLD_BYTES: int = Field(
        default=1024,  # 1 KB
        ge=512,
        le=10240,
        description="Only compress cached values larger than this size",
    )
    CACHE_MAX_VALUE_SIZE_BYTES: int = Field(
        default=1048576,  # 1 MB
        ge=102400,
        le=10485760,
        description="Maximum size for a single cached value",
    )

    # ============================================================================
    # Request/Response Optimization
    # ============================================================================

    REQUEST_TIMEOUT_SECONDS: int = Field(
        default=30, ge=10, le=120, description="Default request timeout"
    )
    REQUEST_MAX_SIZE_BYTES: int = Field(
        default=10485760,  # 10 MB
        ge=1048576,
        le=104857600,
        description="Maximum request body size",
    )
    RESPONSE_CACHE_CONTROL_MAX_AGE: int = Field(
        default=300,  # 5 minutes
        ge=0,
        le=3600,
        description="Cache-Control max-age for API responses",
    )

    # ============================================================================
    # Monitoring & Metrics
    # ============================================================================

    METRICS_COLLECTION_INTERVAL_SECONDS: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Interval for collecting performance metrics",
    )
    METRICS_RETENTION_DAYS: int = Field(
        default=7, ge=1, le=90, description="Days to retain performance metrics"
    )
    ENABLE_PERFORMANCE_PROFILING: bool = Field(
        default=False,
        description="Enable detailed performance profiling (adds overhead)",
    )
    ENABLE_QUERY_LOGGING: bool = Field(
        default=True, description="Enable slow query logging"
    )

    @field_validator("DATABASE_POOL_RESET_ON_RETURN")
    @classmethod
    def validate_reset_mode(cls, v: str) -> str:
        """Validate pool reset mode."""
        valid_modes = {"commit", "rollback", "none"}
        if v.lower() not in valid_modes:
            raise ValueError(f"Invalid reset mode: {v}. Must be one of {valid_modes}")
        return v.lower()

    def get_database_pool_size(self, worker_count: Optional[int] = None) -> int:
        """
        Calculate optimal database pool size based on worker count.

        Args:
            worker_count: Number of workers (auto-detected if None)

        Returns:
            Calculated pool size
        """
        if worker_count:
            # Dynamic sizing: workers * connections_per_worker
            calculated_size = worker_count * self.DATABASE_POOL_SIZE_PER_WORKER
            return min(calculated_size, 100)  # Cap at 100
        return self.DATABASE_POOL_SIZE_BASE

    def get_pool_utilization_status(self, checked_out: int, pool_size: int) -> str:
        """
        Get pool utilization status.

        Args:
            checked_out: Number of connections currently in use
            pool_size: Total pool size

        Returns:
            Status: "healthy", "warning", or "critical"
        """
        if pool_size == 0:
            return "unknown"

        utilization = checked_out / pool_size

        if utilization >= self.DATABASE_POOL_UTILIZATION_CRITICAL_THRESHOLD:
            return "critical"
        elif utilization >= self.DATABASE_POOL_UTILIZATION_WARNING_THRESHOLD:
            return "warning"
        return "healthy"

    def should_cache_query_result(self, query_size_bytes: int) -> bool:
        """
        Determine if a query result should be cached based on size.

        Args:
            query_size_bytes: Size of query result in bytes

        Returns:
            True if result should be cached
        """
        return query_size_bytes <= self.CACHE_MAX_VALUE_SIZE_BYTES

    def get_cache_ttl_for_data_type(self, data_type: str) -> int:
        """
        Get appropriate cache TTL for data type.

        Args:
            data_type: Type of data ("query", "session", "static", "default")

        Returns:
            TTL in seconds
        """
        ttl_map = {
            "query": self.CACHE_QUERY_TTL_SECONDS,
            "session": self.CACHE_SESSION_TTL_SECONDS,
            "static": self.CACHE_STATIC_DATA_TTL_SECONDS,
            "default": self.CACHE_DEFAULT_TTL_SECONDS,
        }
        return ttl_map.get(data_type, self.CACHE_DEFAULT_TTL_SECONDS)
