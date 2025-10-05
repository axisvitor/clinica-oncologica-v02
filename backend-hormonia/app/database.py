"""
Database connection and session management for Supabase PostgreSQL with performance optimizations.
FIX #5: Enhanced database optimization with comprehensive indexing strategy.
"""
from sqlalchemy import create_engine, event, Index, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from typing import Generator
import logging
import time
from contextlib import contextmanager

from app.config import settings
from app.utils.database_optimization import create_optimized_engine, ConnectionPoolMonitor
from app.utils.query_performance import QueryPerformanceMonitor, IndexManager

logger = logging.getLogger(__name__)

# SQLAlchemy engine for Supabase PostgreSQL with enhanced optimizations
# Configuration optimized for thread-safe multi-worker production deployment
engine = create_optimized_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    # Core pool configuration for production workloads
    pool_size=40,          # SECURITY FIX: Increased from 25 to 40 - increased for better concurrency
    max_overflow=60,       # SECURITY FIX: Increased from 35 to 60 under high load
    pool_pre_ping=True,    # Test connections before use (critical for Supabase)
    pool_recycle=3600,     # Recycle connections every hour (network timeouts)
    pool_timeout=30,       # Wait time for connection from pool

    # Advanced connection health and performance settings
    pool_reset_on_return='commit',  # Reset connection state on return
    pool_logging_name='hormonia_db', # Named logging for debugging

    # Connection validation and cleanup
    connect_args={
        'connect_timeout': 10,      # TCP connection timeout
        'sslmode': 'require',        # SECURITY FIX: Enforce SSL to prevent MITM
        'application_name': 'hormonia_backend',  # Identify in pg_stat_activity
        'keepalives_idle': 600,     # Keep-alive settings for network stability
        'keepalives_interval': 30,
        'keepalives_count': 3,
        'options': '-c statement_timeout=30000',  # SECURITY FIX: 30s query timeout as session parameter
    },

    echo=settings.DEBUG,
    echo_pool=settings.DEBUG if hasattr(settings, 'DEBUG') else False
)

# Connection pool monitor
pool_monitor = ConnectionPoolMonitor(engine)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get database session.
    Used with FastAPI's dependency injection system.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
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


# Supabase client for real-time features and additional functionality
# NOTE: Initialization moved to app.core.database to prevent duplication
# This module imports from app.core.database for backward compatibility
supabase_client = None

def init_supabase_client():
    """
    Initialize Supabase client safely (DEPRECATED).

    This function is deprecated. Use app.core.database.init_supabase_client() instead.
    Kept for backward compatibility only.
    """
    global supabase_client

    # Import from core.database to use the same instance
    try:
        from app.core.database import supabase_client as core_client, init_supabase_client as core_init

        if core_client is None:
            # Initialize via core module
            core_init()
            from app.core.database import supabase_client as core_client

        # Share the same instance
        supabase_client = core_client
        return supabase_client is not None

    except ImportError:
        logger.warning("Supabase client not available. Install supabase-py for full functionality.")
        return False
    except Exception as e:
        logger.error(f"Error initializing Supabase client: {e}")
        return False

# Do NOT initialize on import - let app.core.database handle it
# This prevents duplicate "Supabase client initialized successfully" logs


def get_supabase():
    """Get Supabase client instance."""
    if supabase_client is None:
        raise RuntimeError("Supabase client not initialized")
    return supabase_client


def get_pool_status():
    """Get database connection pool status."""
    return pool_monitor.get_pool_status()


def is_pool_healthy():
    """Check if database connection pool is healthy."""
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


def test_connection():
    """
    Test database connection and return status information.

    Returns:
        dict: Connection status with details

    Raises:
        Exception: If connection test fails
    """
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
                }
            }
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "pool_info": get_pool_status() if pool_monitor else None
        }


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

        # Recreate engine with same configuration
        engine = create_optimized_engine(
            settings.DATABASE_URL,
            poolclass=QueuePool,
            pool_size=40,  # SECURITY FIX: Match updated pool size
            max_overflow=60,  # SECURITY FIX: Match updated overflow
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_timeout=30,
            pool_reset_on_return='commit',
            pool_logging_name='hormonia_db',
            connect_args={
                'connect_timeout': 10,
                'application_name': 'hormonia_backend',
                'keepalives_idle': 600,
                'sslmode': 'require',        # SECURITY FIX: Enforce SSL to prevent MITM
                'keepalives_interval': 30,
                'keepalives_count': 3,
                'options': '-c statement_timeout=30000',  # SECURITY FIX: 30s query timeout as session parameter
            },
            echo=settings.DEBUG,
            echo_pool=settings.DEBUG if hasattr(settings, 'DEBUG') else False
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
    """
    Get detailed information about the database engine configuration.

    Returns:
        dict: Engine configuration details
    """
    return {
        "url": str(engine.url).replace(engine.url.password or '', '***'),
        "driver": engine.driver,
        "pool_class": str(type(engine.pool)),
        "pool_size": engine.pool.size(),
        "max_overflow": engine.pool._max_overflow,
        "pool_timeout": engine.pool._timeout,
        "pool_recycle": engine.pool._recycle,
        "pool_pre_ping": engine.pool._pre_ping,
        "echo": engine.echo,
        "current_connections": {
            "checked_in": engine.pool.checkedin(),
            "checked_out": engine.pool.checkedout(),
            "overflow": engine.pool.overflow(),
        }
    }