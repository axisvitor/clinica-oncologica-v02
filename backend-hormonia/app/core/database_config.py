"""
Dynamic database pool configuration based on environment.

CRITICAL FIX #3: Optimize pool size based on environment to prevent connection exhaustion.

This module provides environment-aware database connection pool configuration
to prevent connection exhaustion on AWS RDS while maintaining performance.

Environment Detection:
- Production: Conservative pool settings (RDS connection limits)
- Staging: Moderate pool settings
- Development: Generous pool settings (local PostgreSQL)

Connection Pool Calculation:
- Base formula: pool_size + max_overflow = total_connections
- AWS RDS t3.micro: ~100 max connections
- Reserved connections: ~20 (monitoring, admin, etc.)
- Available for app: ~80 connections
- Multiple workers: total_connections / worker_count

Best Practices:
1. Monitor connection usage with pool_monitor
2. Set proper timeouts to prevent connection hogging
3. Use connection pooling at application level only
4. Test with realistic concurrent load
"""

import os
from dataclasses import dataclass
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class DatabasePoolConfig:
    """Database connection pool configuration."""

    pool_size: int
    max_overflow: int
    pool_timeout: int
    pool_recycle: int
    pool_pre_ping: bool
    connect_timeout: int
    statement_timeout: int
    idle_in_transaction_session_timeout: int

    @property
    def total_connections(self) -> int:
        """Total maximum connections (pool_size + max_overflow)."""
        return self.pool_size + self.max_overflow

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for SQLAlchemy engine."""
        return {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "pool_pre_ping": self.pool_pre_ping,
        }

    def get_connect_args(self) -> Dict[str, Any]:
        """Get connection arguments for PostgreSQL."""
        return {
            "connect_timeout": self.connect_timeout,
            "application_name": "hormonia_backend",
            "options": f"-c statement_timeout={self.statement_timeout * 1000} "
            f"-c idle_in_transaction_session_timeout={self.idle_in_transaction_session_timeout * 1000}",
        }


class EnvironmentType:
    """Environment type constants."""

    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    TEST = "test"


def detect_environment() -> str:
    """
    Detect current environment from environment variables.

    Detection order:
    1. ENVIRONMENT variable (explicit)
    2. RAILWAY_ENVIRONMENT (Railway deployment)
    3. VERCEL_ENV (Vercel deployment)
    4. Check for production indicators
    5. Default to development

    Returns:
        str: Environment type (production, staging, development, test)
    """
    # Explicit environment variable
    env = os.getenv("ENVIRONMENT", "").lower()
    if env in [
        EnvironmentType.PRODUCTION,
        EnvironmentType.STAGING,
        EnvironmentType.DEVELOPMENT,
        EnvironmentType.TEST,
    ]:
        return env

    # Railway environment
    railway_env = os.getenv("RAILWAY_ENVIRONMENT", "").lower()
    if railway_env == "production":
        return EnvironmentType.PRODUCTION
    elif railway_env:
        return EnvironmentType.STAGING

    # Vercel environment
    vercel_env = os.getenv("VERCEL_ENV", "").lower()
    if vercel_env == "production":
        return EnvironmentType.PRODUCTION
    elif vercel_env in ["preview", "development"]:
        return EnvironmentType.STAGING

    # Production indicators
    if any(
        [
            os.getenv("PROD"),
            os.getenv("PRODUCTION"),
            "prod" in os.getenv("DATABASE_URL", "").lower(),
            "rds.amazonaws.com" in os.getenv("DATABASE_URL", ""),
        ]
    ):
        return EnvironmentType.PRODUCTION

    # Test environment
    if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("TESTING"):
        return EnvironmentType.TEST

    # Default to development
    return EnvironmentType.DEVELOPMENT


def get_worker_count() -> int:
    """
    Get the number of workers/processes.

    Detection order:
    1. WEB_CONCURRENCY (Gunicorn/Uvicorn)
    2. WORKER_COUNT (custom)
    3. Environment-aware default:
       - Production/Staging: Default to 4 (requires explicit config recommended)
       - Development/Test: Default to 1 (single process)

    Returns:
        int: Number of workers

    Note: In production, this MUST be set explicitly via WEB_CONCURRENCY or WORKER_COUNT
    to ensure proper connection pool calculation. The default of 4 is a fallback only.
    """
    try:
        explicit_workers = os.getenv("WEB_CONCURRENCY") or os.getenv("WORKER_COUNT")
        if explicit_workers:
            return int(explicit_workers)

        # Environment-aware defaults to prevent pool exhaustion
        env = detect_environment()
        if env in [EnvironmentType.DEVELOPMENT, EnvironmentType.TEST]:
            return 1  # Single worker for local dev - prevents 200 connection issue
        else:
            # CRITICAL: Production should set WEB_CONCURRENCY explicitly
            # This fallback of 4 workers assumes proper pool configuration
            logger.warning(
                "⚠️  WEB_CONCURRENCY not set in production. Defaulting to 4 workers. "
                "Please set WEB_CONCURRENCY explicitly to ensure proper connection pool sizing."
            )
            return 4  # Production/staging default
    except (ValueError, TypeError):
        logger.error("Invalid worker count configuration. Defaulting to 1 worker.")
        return 1  # Safe default


def calculate_pool_config(
    environment: str, worker_count: Optional[int] = None
) -> DatabasePoolConfig:
    """
    Calculate optimal pool configuration based on environment and worker count.

    Connection Pool Strategy:
    - Each worker needs pool_size + max_overflow connections
    - Total connections = (pool_size + max_overflow) * worker_count
    - Must stay under database max_connections limit

    AWS RDS Limits (t3.micro):
    - max_connections: ~100
    - Reserved: ~20 (for monitoring, admin, PgBouncer, etc.)
    - Available: ~80
    - Per worker: 80 / worker_count

    Args:
        environment: Environment type (production, staging, development, test)
        worker_count: Number of workers (auto-detected if None)

    Returns:
        DatabasePoolConfig: Optimized pool configuration
    """
    if worker_count is None:
        worker_count = get_worker_count()

    if environment == EnvironmentType.PRODUCTION:
        # Production: Conservative settings for AWS RDS
        # Calculation: 80 connections / 4 workers = 20 per worker
        # Split: 10 pool + 10 overflow = 20 total per worker
        return DatabasePoolConfig(
            pool_size=10,  # Base connections per worker
            max_overflow=10,  # Additional connections under load
            pool_timeout=30,  # Wait 30s for connection
            pool_recycle=3600,  # Recycle every 1 hour
            pool_pre_ping=True,  # Test connection health
            connect_timeout=10,  # TCP connection timeout
            statement_timeout=30,  # Query timeout (30s)
            idle_in_transaction_session_timeout=300,  # Idle transaction timeout (5min)
        )

    elif environment == EnvironmentType.STAGING:
        # Staging: Moderate settings
        # Usually fewer workers and lighter load
        return DatabasePoolConfig(
            pool_size=15,  # Slightly larger pool
            max_overflow=15,  # More overflow capacity
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
            connect_timeout=10,
            statement_timeout=60,  # Longer queries allowed
            idle_in_transaction_session_timeout=600,  # 10 minutes
        )

    elif environment == EnvironmentType.TEST:
        # Test: Minimal settings
        # Fast creation/teardown, no pre-ping needed
        return DatabasePoolConfig(
            pool_size=2,  # Minimal pool for tests
            max_overflow=3,  # Small overflow
            pool_timeout=10,
            pool_recycle=300,  # Recycle more frequently
            pool_pre_ping=False,  # Skip pre-ping in tests
            connect_timeout=5,
            statement_timeout=10,  # Fast timeout for tests
            idle_in_transaction_session_timeout=60,
        )

    else:  # DEVELOPMENT
        # Development: Moderate settings
        # Local PostgreSQL OR RDS - stay within limits
        # With 1 worker default: 10 + 15 = 25 connections (safe for RDS)
        return DatabasePoolConfig(
            pool_size=10,  # Reduced from 20 - sufficient for dev
            max_overflow=15,  # Reduced from 30 - prevents connection exhaustion
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
            connect_timeout=10,
            statement_timeout=300,  # 5 minutes for debugging
            idle_in_transaction_session_timeout=1800,  # 30 minutes
        )


def get_pool_config(
    environment: Optional[str] = None, worker_count: Optional[int] = None
) -> DatabasePoolConfig:
    """
    Get database pool configuration for current environment.

    Args:
        environment: Environment type (auto-detected if None)
        worker_count: Number of workers (auto-detected if None)

    Returns:
        DatabasePoolConfig: Optimized pool configuration
    """
    if environment is None:
        environment = detect_environment()

    if worker_count is None:
        worker_count = get_worker_count()

    config = calculate_pool_config(environment, worker_count)

    logger.info(
        f"Database pool configuration: "
        f"environment={environment}, "
        f"workers={worker_count}, "
        f"pool_size={config.pool_size}, "
        f"max_overflow={config.max_overflow}, "
        f"total_per_worker={config.total_connections}, "
        f"total_all_workers={config.total_connections * worker_count}"
    )

    # Validate and warn if total connections might exceed limits
    total_connections = config.total_connections * worker_count

    if environment == EnvironmentType.PRODUCTION:
        if total_connections > 80:
            logger.error(
                f"❌ CRITICAL: Total connections ({total_connections}) exceeds "
                f"AWS RDS t3.micro limit (~80 available). "
                f"Current: {worker_count} workers × {config.total_connections} = {total_connections} connections. "
                f"REQUIRED ACTION: Reduce workers or pool size to prevent connection exhaustion. "
                f"Recommended: Set WEB_CONCURRENCY=4 or lower."
            )
        elif total_connections > 60:
            logger.warning(
                f"⚠️  Total connections ({total_connections}) approaching "
                f"AWS RDS limits (~80). Monitor connection usage closely."
            )
        else:
            logger.info(
                f"✅ Connection pool within safe limits: {total_connections}/80 connections"
            )

    # Additional validation for development to prevent misconfiguration
    if environment == EnvironmentType.DEVELOPMENT and total_connections > 100:
        logger.warning(
            f"⚠️  Development environment using {total_connections} connections. "
            f"This may indicate misconfiguration. Verify worker count is correct."
        )

    return config


def validate_pool_config(config: DatabasePoolConfig, database_url: str) -> bool:
    """
    Validate pool configuration against database limits.

    Args:
        config: Pool configuration to validate
        database_url: Database URL (for connection limit check)

    Returns:
        bool: True if valid, False if issues detected
    """
    issues = []

    # Check pool size
    if config.pool_size < 2:
        issues.append("pool_size too small (< 2)")

    if config.pool_size > 50:
        issues.append("pool_size too large (> 50)")

    # Check overflow
    if config.max_overflow < config.pool_size * 0.5:
        issues.append("max_overflow too small (< 50% of pool_size)")

    # Check timeouts
    if config.pool_timeout < 10:
        issues.append("pool_timeout too small (< 10s)")

    if config.connect_timeout < 5:
        issues.append("connect_timeout too small (< 5s)")

    # Check total connections for production
    if "rds.amazonaws.com" in database_url or "prod" in database_url.lower():
        worker_count = get_worker_count()
        total = config.total_connections * worker_count
        if total > 80:
            issues.append(f"total_connections ({total}) exceeds AWS RDS limits (~80)")

    if issues:
        logger.error(f"❌ Pool configuration validation failed: {', '.join(issues)}")
        return False

    logger.info("✅ Pool configuration validation passed")
    return True


# Export for easy import
__all__ = [
    "DatabasePoolConfig",
    "EnvironmentType",
    "detect_environment",
    "get_worker_count",
    "calculate_pool_config",
    "get_pool_config",
    "validate_pool_config",
]
