"""Database connection and session management for AWS RDS PostgreSQL with performance optimizations.

CRITICAL FIX #3: Dynamic pool configuration based on environment to prevent connection exhaustion.
FIX #5: Enhanced database optimization with comprehensive indexing strategy."""

from sqlalchemy import text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool
from typing import Generator
import logging
from contextlib import contextmanager
from fastapi import HTTPException

from app.config import settings
from app.core.exceptions import APIException
from app.utils.database_optimization import (
    create_optimized_engine,
    ConnectionPoolMonitor,
)
from app.core.database_config import (
    get_pool_config,
    validate_pool_config,
    detect_environment,
)

logger = logging.getLogger(__name__)

# ============================================================================
# CRITICAL FIX #3: Dynamic Pool Configuration Based on Environment
# ============================================================================
# Get environment-aware pool configuration
pool_config = get_pool_config()

# Validate configuration against database limits
if not validate_pool_config(pool_config, settings.DATABASE_URL):
    logger.warning("⚠️  Pool configuration validation failed, using defaults")

logger.info(
    f"🔧 Initializing database with environment-aware pool: "
    f"environment={detect_environment()}, "
    f"pool_size={pool_config.pool_size}, "
    f"max_overflow={pool_config.max_overflow}, "
    f"total_max={pool_config.total_connections}"
)

# SQLAlchemy engine for AWS RDS PostgreSQL with enhanced optimizations
# Configuration optimized for thread-safe multi-worker production deployment
engine = create_optimized_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    # CRITICAL FIX: Environment-aware pool configuration
    pool_size=pool_config.pool_size,
    max_overflow=pool_config.max_overflow,
    pool_pre_ping=pool_config.pool_pre_ping,
    pool_recycle=pool_config.pool_recycle,
    pool_timeout=pool_config.pool_timeout,
    # Advanced connection health and performance settings
    pool_reset_on_return="commit",  # Reset connection state on return
    pool_logging_name="hormonia_db",  # Named logging for debugging
    # Connection validation and cleanup with environment-aware timeouts
    connect_args=pool_config.get_connect_args(),
    echo=settings.APP_ENABLE_DEBUG,
    echo_pool=settings.APP_ENABLE_DEBUG if hasattr(settings, "DEBUG") else False,
)

# Connection pool monitor
pool_monitor = ConnectionPoolMonitor(engine)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency to get a database session for FastAPI."""
    db = SessionLocal()
    try:
        yield db
    except HTTPException:
        db.rollback()
        raise
    except APIException as e:
        if e.status_code >= 500:
            logger.error(f"Database session error: {e}", exc_info=True)
        db.rollback()
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database session error: {e}", exc_info=True)
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Database session error: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


def create_tables():
    """Create all database tables."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


def drop_tables():
    """Drop all database tables (use with caution)."""
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("Database tables dropped successfully")
    except Exception as e:
        logger.error(f"Error dropping database tables: {e}")
        raise


# Legacy Supabase client REMOVED - migrated to AWS RDS PostgreSQL (2025-10-07)
# This module now delegates to SQLAlchemy sessions only. Authentication flows
# rely on Firebase Admin SDK rather than Supabase Auth.


def get_pool_status(use_service_role: bool | None = None):
    """Get database connection pool status."""
    if use_service_role is not None:
        logger.debug(
            "get_pool_status called with use_service_role=%s; single pool in use",
            use_service_role,
        )
    return pool_monitor.get_pool_status()


def is_pool_healthy(use_service_role: bool | None = None):
    """Check if database connection pool is healthy."""
    if use_service_role is not None:
        logger.debug(
            "is_pool_healthy called with use_service_role=%s; single pool in use",
            use_service_role,
        )
    return pool_monitor.is_pool_healthy()


# ==============================================================================
# THREAD-SAFE SESSION UTILITIES
# ==============================================================================


@contextmanager
def get_scoped_session():
    """
    Context manager for scoped database sessions.

    Provides a database session that is automatically closed after use.
    This is useful for background tasks or utilities that need database access
    outside of FastAPI request context.

    Yields:
        Session: SQLAlchemy database session

    Example:
        with get_scoped_session() as db:
            user = db.query(User).first()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def test_connection(use_service_role: bool | None = None):
    """
    Test database connection and return status information.

    Returns:
        dict: Connection status with details

    Raises:
        Exception: If connection test fails
    """
    if use_service_role is not None:
        logger.debug(
            "test_connection called with use_service_role=%s; single pool in use",
            use_service_role,
        )
    try:
        with get_scoped_session() as session:
            # Test basic query
            result = session.execute(text("SELECT 1 as test")).fetchone()

            # Test pool status
            pool_status = get_pool_status()

            return {
                "status": "healthy",
                "test_query_result": result[0] if result else None,
                "pool_info": pool_status,
                "connection_args": {
                    "pool_size": engine.pool.size(),
                    "checked_in": engine.pool.checkedin(),
                    "checked_out": engine.pool.checkedout(),
                    "overflow": engine.pool.overflow(),
                },
            }
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "pool_info": get_pool_status() if pool_monitor else None,
        }


def get_engine(use_service_role: bool = False):
    """
    Backward-compatible accessor for the SQLAlchemy engine.

    Args:
        use_service_role: Kept for signature compatibility; no separate engine pool exists.

    Returns:
        Engine: The primary SQLAlchemy engine instance.
    """
    if use_service_role:
        logger.debug(
            "get_engine called with use_service_role=True; returning primary engine"
        )
    return engine


def force_pool_recreation():
    """
    Force recreation of the database connection pool.

    This can be useful in case of network issues or when database
    credentials change. Use with caution in production.

    Returns:
        bool: True if successful, False otherwise
    """
    global engine, SessionLocal

    try:
        # Dispose of existing connections
        engine.dispose()

        # Recreate engine with environment-aware configuration
        pool_config = get_pool_config()

        engine = create_optimized_engine(
            settings.DATABASE_URL,
            poolclass=QueuePool,
            pool_size=pool_config.pool_size,
            max_overflow=pool_config.max_overflow,
            pool_pre_ping=pool_config.pool_pre_ping,
            pool_recycle=pool_config.pool_recycle,
            pool_timeout=pool_config.pool_timeout,
            pool_reset_on_return="commit",
            pool_logging_name="hormonia_db",
            connect_args=pool_config.get_connect_args(),
            echo=settings.APP_ENABLE_DEBUG,
            echo_pool=settings.APP_ENABLE_DEBUG
            if hasattr(settings, "DEBUG")
            else False,
        )

        # Recreate session factory
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        # Test new connection
        test_result = test_connection()
        if test_result["status"] == "healthy":
            logger.info("Database pool recreated successfully")
            return True
        else:
            logger.error(f"Pool recreation failed: {test_result.get('error')}")
            return False

    except Exception as e:
        logger.error(f"Failed to recreate database pool: {e}")
        return False


def get_engine_info():
    """Get detailed information about the database engine configuration."""
    return {
        "url": str(engine.url).replace(engine.url.password or "", "***"),
        "driver": engine.driver,
        "environment": detect_environment(),
        "pool_class": str(type(engine.pool)),
        "pool_config": {
            "pool_size": engine.pool.size(),
            "max_overflow": engine.pool._max_overflow,
            "pool_timeout": engine.pool._timeout,
            "pool_recycle": engine.pool._recycle,
            "pool_pre_ping": engine.pool._pre_ping,
            "total_max": engine.pool.size() + engine.pool._max_overflow,
        },
        "echo": engine.echo,
        "current_connections": {
            "checked_in": engine.pool.checkedin(),
            "checked_out": engine.pool.checkedout(),
            "overflow": engine.pool.overflow(),
            "total_in_use": engine.pool.checkedout() + engine.pool.overflow(),
        },
    }


# ==============================================================================
# ASYNC DATABASE SUPPORT
# ==============================================================================

_async_engine = None
_async_session_factory = None


class _AsyncSessionFactoryProxy:
    """Lazy proxy that defers async session factory initialization."""

    def __call__(self, *args, **kwargs):
        return get_async_session_factory()(*args, **kwargs)


def get_async_engine():
    """
    Get or create an AsyncEngine for async database operations.

    Lazily initializes the async engine on first call.
    Uses the same DATABASE_URL but with asyncpg driver.

    Returns:
        AsyncEngine instance
    """
    global _async_engine

    if _async_engine is None:
        # Convert sync URL to async URL (asyncpg driver)
        sync_url = settings.DATABASE_URL
        async_url = sync_url.replace(
            "postgresql+psycopg://", "postgresql+asyncpg://"
        ).replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://"
        ).replace(
            "postgresql://", "postgresql+asyncpg://"
        )

        # asyncpg doesn't accept sslmode in URL; configure via connect_args
        import ssl as ssl_module

        connect_args: dict = {}
        if "sslmode=require" in async_url or "sslmode=verify" in async_url:
            async_url = (
                async_url.replace("?sslmode=require", "")
                .replace("&sslmode=require", "")
                .replace("?sslmode=verify-ca", "")
                .replace("?sslmode=verify-full", "")
            )
            ssl_context = ssl_module.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl_module.CERT_NONE
            connect_args["ssl"] = ssl_context

        logger.info(
            "Initializing AsyncEngine (SSL=%s)",
            "enabled" if connect_args.get("ssl") else "disabled",
        )

        _async_engine = create_async_engine(
            async_url,
            pool_size=10,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=1800,
            echo=settings.APP_ENABLE_DEBUG,
            connect_args=connect_args,
        )

    return _async_engine


def get_async_session_factory():
    """
    Get or create an async session factory.

    Returns:
        async_sessionmaker bound to the async engine
    """
    global _async_session_factory

    if _async_session_factory is None:
        engine = get_async_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    return _async_session_factory


AsyncSessionLocal = _AsyncSessionFactoryProxy()


async def get_async_db() -> AsyncSession:
    """
    Dependency to get async database session.

    Yields:
        AsyncSession for async database operations
    """
    async_session_factory = get_async_session_factory()
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Async database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()
