"""
Thread-safe database management for multi-worker FastAPI deployment.

Features:
- Connection pooling with proper isolation
- Thread-safe session management
- Connection health monitoring
- Automatic reconnection handling
- Resource cleanup and monitoring
"""

import threading
import logging
from contextlib import contextmanager
from typing import Generator, Optional
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
from app.config import settings

logger = logging.getLogger(__name__)


class ThreadSafeDatabaseManager:
    """
    Thread-safe database manager with connection pooling.

    Ensures each thread gets isolated database connections while
    maintaining efficient resource utilization through pooling.
    """

    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        """Ensure singleton pattern with thread safety."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self, database_url: str = None):
        """Initialize thread-safe database manager."""
        if hasattr(self, "_initialized"):
            return

        self.database_url = database_url or settings.database_url
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._local_data = threading.local()
        self._lock = threading.RLock()
        self._initialized = True

        logger.info("ThreadSafeDatabaseManager initialized")

    def _create_engine(self) -> Engine:
        """Create database engine with thread-safe configuration."""
        engine_config = {
            # Connection pool configuration
            "poolclass": QueuePool,
            "pool_size": 10,  # Number of connections to maintain in pool
            "max_overflow": 20,  # Additional connections beyond pool_size
            "pool_pre_ping": True,  # Verify connections before use
            "pool_recycle": 3600,  # Recycle connections after 1 hour
            "pool_timeout": 30,  # Timeout for getting connection from pool
            # Engine configuration for thread safety
            "echo": settings.debug,  # Log SQL statements in debug mode
            "isolation_level": "READ_COMMITTED",  # Safe for concurrent access
            "connect_args": {
                "connect_timeout": 10,
                "application_name": "hormonia_backend",
            },
        }

        # PostgreSQL specific optimizations
        if "postgresql" in self.database_url:
            engine_config["connect_args"].update(
                {
                    "options": "-c default_transaction_isolation=read_committed",
                    "server_side_cursors": True,
                }
            )

        engine = create_engine(self.database_url, **engine_config)

        # Add event listeners for monitoring
        self._setup_engine_events(engine)

        return engine

    def _setup_engine_events(self, engine: Engine):
        """Setup engine event listeners for monitoring and debugging."""

        @event.listens_for(engine, "connect")
        def receive_connect(dbapi_connection, connection_record):
            """Log new database connections."""
            thread_id = threading.get_ident()
            logger.debug(f"New database connection established for thread {thread_id}")

        @event.listens_for(engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Log connection checkouts from pool."""
            thread_id = threading.get_ident()
            logger.debug(f"Connection checked out from pool for thread {thread_id}")

        @event.listens_for(engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """Log connection checkins to pool."""
            thread_id = threading.get_ident()
            logger.debug(f"Connection checked in to pool for thread {thread_id}")

        @event.listens_for(engine, "invalidate")
        def receive_invalidate(dbapi_connection, connection_record, exception):
            """Log connection invalidations."""
            thread_id = threading.get_ident()
            logger.warning(
                f"Connection invalidated for thread {thread_id}: {exception}"
            )

    def get_engine(self) -> Engine:
        """Get or create database engine."""
        with self._lock:
            if self._engine is None:
                self._engine = self._create_engine()
                logger.info("Database engine created successfully")
            return self._engine

    def get_session_factory(self) -> sessionmaker:
        """Get or create session factory."""
        with self._lock:
            if self._session_factory is None:
                engine = self.get_engine()
                self._session_factory = sessionmaker(
                    bind=engine,
                    autocommit=False,
                    autoflush=False,
                    expire_on_commit=False,  # Prevent lazy loading issues
                )
                logger.info("Session factory created successfully")
            return self._session_factory

    def create_session(self) -> Session:
        """
        Create a new database session.

        Each call returns a new session instance isolated from other threads.
        """
        session_factory = self.get_session_factory()
        session = session_factory()

        # Track session for debugging
        thread_id = threading.get_ident()
        logger.debug(f"New session created for thread {thread_id}")

        return session

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions with automatic cleanup.

        Ensures sessions are properly closed and rolled back on errors.
        """
        session = None
        thread_id = threading.get_ident()

        try:
            session = self.create_session()
            logger.debug(f"Session context started for thread {thread_id}")
            yield session
            session.commit()
            logger.debug(f"Session committed for thread {thread_id}")

        except Exception as e:
            if session:
                session.rollback()
                logger.error(f"Session rolled back for thread {thread_id}: {e}")
            raise

        finally:
            if session:
                session.close()
                logger.debug(f"Session closed for thread {thread_id}")

    def health_check(self) -> bool:
        """
        Perform health check on database connection.

        Returns True if database is accessible, False otherwise.
        """
        try:
            with self.get_session() as session:
                # Simple query to test connection
                session.execute("SELECT 1").fetchone()
                return True

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    def get_pool_status(self) -> dict:
        """Get connection pool status for monitoring."""
        engine = self.get_engine()
        pool = engine.pool

        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }

    def cleanup(self):
        """Clean up database connections and resources."""
        with self._lock:
            if self._engine:
                try:
                    self._engine.dispose()
                    logger.info("Database engine disposed successfully")
                except Exception as e:
                    logger.error(f"Error disposing database engine: {e}")
                finally:
                    self._engine = None
                    self._session_factory = None

    @classmethod
    def reset_instance(cls):
        """Reset singleton instance (useful for testing)."""
        with cls._lock:
            if cls._instance:
                cls._instance.cleanup()
                cls._instance = None


# Global database manager instance
_db_manager: Optional[ThreadSafeDatabaseManager] = None
_db_manager_lock = threading.RLock()


def get_database_manager(database_url: str = None) -> ThreadSafeDatabaseManager:
    """Get or create global database manager instance."""
    global _db_manager

    with _db_manager_lock:
        if _db_manager is None:
            _db_manager = ThreadSafeDatabaseManager(database_url)
        return _db_manager


def get_db_session_factory():
    """Get database session factory for dependency injection."""
    db_manager = get_database_manager()
    return db_manager.create_session


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.

    Provides thread-safe database sessions with automatic cleanup.
    """
    db_manager = get_database_manager()
    with db_manager.get_session() as session:
        yield session


def health_check_database() -> bool:
    """Health check endpoint for database connectivity."""
    try:
        db_manager = get_database_manager()
        return db_manager.health_check()
    except Exception as e:
        logger.error(f"Database health check error: {e}")
        return False


def get_database_metrics() -> dict:
    """Get database metrics for monitoring."""
    try:
        db_manager = get_database_manager()
        pool_status = db_manager.get_pool_status()

        return {
            "status": "healthy" if db_manager.health_check() else "unhealthy",
            "pool": pool_status,
            "thread_id": threading.get_ident(),
        }

    except Exception as e:
        logger.error(f"Error getting database metrics: {e}")
        return {
            "status": "error",
            "error": str(e),
            "thread_id": threading.get_ident(),
        }


# Cleanup function for graceful shutdown
def cleanup_database():
    """Cleanup database connections on shutdown."""
    global _db_manager

    with _db_manager_lock:
        if _db_manager:
            _db_manager.cleanup()
            _db_manager = None
            logger.info("Database manager cleaned up")


# Export public interface
__all__ = [
    "ThreadSafeDatabaseManager",
    "get_database_manager",
    "get_db_session_factory",
    "get_db",
    "health_check_database",
    "get_database_metrics",
    "cleanup_database",
]
