"""
Direct Database Connection Utilities for Production Stability.

This module provides simple, direct database connections without the complexity
of session management or connection pooling that can cause issues in production.
Designed as a fallback when the main database system has issues.
"""

import logging
from contextlib import contextmanager
from typing import Generator, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings

logger = logging.getLogger(__name__)


def create_direct_engine():
    """
    Create a direct database engine with minimal configuration.

    This engine is designed for reliability over performance, with simple
    connection settings that avoid complex pooling issues.

    Returns:
        Engine: Simple SQLAlchemy engine
    """
    try:
        # Simple engine configuration - no complex pooling
        engine = create_engine(
            settings.DATABASE_URL,
            # Minimal pool configuration
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=1800,  # 30 minutes
            # Simple connection args
            connect_args={"connect_timeout": 10, "application_name": "hormonia_direct"},
            # Reduced logging for production
            echo=False,
            echo_pool=False,
        )

        logger.info("Direct database engine created successfully")
        return engine

    except Exception as e:
        logger.error(f"Failed to create direct database engine: {e}")
        raise


# Global direct engine instance
_direct_engine: Optional[object] = None
_direct_session_factory: Optional[sessionmaker] = None


def initialize_direct_database():
    """
    Initialize direct database connection.

    This should be called during application startup as a fallback
    initialization method when the main database system fails.

    Returns:
        bool: True if successful, False otherwise
    """
    global _direct_engine, _direct_session_factory

    try:
        _direct_engine = create_direct_engine()
        _direct_session_factory = sessionmaker(
            autocommit=False, autoflush=False, bind=_direct_engine
        )

        # Test connection
        with get_direct_session() as session:
            session.execute(text("SELECT 1"))

        logger.info("Direct database initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize direct database: {e}")
        return False


@contextmanager
def get_direct_session() -> Generator[Session, None, None]:
    """
    Get a direct database session with simple error handling.

    This is a fallback session provider that avoids complex session
    management and context variables.

    Yields:
        Session: Direct SQLAlchemy session

    Raises:
        RuntimeError: If direct database not initialized or connection fails
    """
    if _direct_session_factory is None:
        if not initialize_direct_database():
            raise RuntimeError("Direct database initialization failed")

    session = _direct_session_factory()
    session_id = hex(id(session))
    logger.debug(f"Created direct session: {session_id}")

    try:
        yield session
        session.commit()
        logger.debug(f"Direct session {session_id} committed successfully")

    except Exception as e:
        logger.error(f"Direct session {session_id} error: {e}")
        session.rollback()
        raise

    finally:
        try:
            session.close()
            logger.debug(f"Direct session {session_id} closed")
        except Exception as e:
            logger.warning(f"Error closing direct session {session_id}: {e}")


def test_direct_connection() -> dict:
    """
    Test direct database connection and return status.

    Returns:
        dict: Connection test results
    """
    try:
        if _direct_engine is None:
            return {
                "status": "not_initialized",
                "error": "Direct engine not initialized",
            }

        with get_direct_session() as session:
            result = session.execute(
                text("SELECT 1 as test, current_timestamp as ts")
            ).fetchone()

            return {
                "status": "healthy",
                "test_result": result[0] if result else None,
                "timestamp": str(result[1]) if result and len(result) > 1 else None,
                "engine_info": {
                    "pool_size": _direct_engine.pool.size()
                    if hasattr(_direct_engine, "pool")
                    else None,
                    "checked_out": _direct_engine.pool.checkedout()
                    if hasattr(_direct_engine, "pool")
                    else None,
                },
            }

    except Exception as e:
        logger.error(f"Direct connection test failed: {e}")
        return {"status": "unhealthy", "error": str(e), "error_type": type(e).__name__}


def get_direct_engine_status() -> dict:
    """
    Get status information about the direct database engine.

    Returns:
        dict: Engine status information
    """
    if _direct_engine is None:
        return {"initialized": False, "error": "Direct engine not initialized"}

    try:
        return {
            "initialized": True,
            "url_masked": str(_direct_engine.url).replace(
                _direct_engine.url.password or "", "***"
            )
            if _direct_engine.url.password
            else str(_direct_engine.url),
            "driver": getattr(_direct_engine, "driver", "unknown"),
            "pool_info": {
                "size": _direct_engine.pool.size()
                if hasattr(_direct_engine, "pool")
                else None,
                "checked_out": _direct_engine.pool.checkedout()
                if hasattr(_direct_engine, "pool")
                else None,
                "checked_in": _direct_engine.pool.checkedin()
                if hasattr(_direct_engine, "pool")
                else None,
            }
            if hasattr(_direct_engine, "pool")
            else None,
        }

    except Exception as e:
        return {"initialized": True, "error": f"Failed to get engine status: {e}"}


async def execute_sql(query: str, params: Optional[dict] = None) -> list:
    """
    Execute raw SQL query and return results.

    This is a helper function for executing raw SQL queries directly,
    primarily used by jobs and admin operations that need to call
    stored procedures or run custom queries.

    Args:
        query: SQL query string
        params: Optional query parameters

    Returns:
        List of result rows as dictionaries

    Raises:
        SQLAlchemyError: If query execution fails
    """
    try:
        with get_direct_session() as session:
            if params:
                result = session.execute(text(query), params)
            else:
                result = session.execute(text(query))

            # Try to fetch results if it's a SELECT or RETURNING query
            try:
                rows = result.fetchall()
                # Convert rows to list of dicts
                if rows and hasattr(result, "keys"):
                    keys = result.keys()
                    return [dict(zip(keys, row)) for row in rows]
                elif rows:
                    # If no column names, return as list of tuples
                    return [tuple(row) for row in rows]
                else:
                    return []
            except Exception:
                # Not a SELECT query, just return empty list
                return []

    except SQLAlchemyError as e:
        logger.error(f"SQL execution failed: {e}")
        logger.error(f"Query: {query}")
        raise


def cleanup_direct_database():
    """
    Cleanup direct database connections.

    Should be called during application shutdown.
    """
    global _direct_engine, _direct_session_factory

    try:
        if _direct_engine:
            _direct_engine.dispose()
            logger.info("Direct database engine disposed")

        _direct_engine = None
        _direct_session_factory = None

    except Exception as e:
        logger.error(f"Error cleaning up direct database: {e}")
