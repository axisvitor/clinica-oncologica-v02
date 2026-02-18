"""
Thread-Safe Session Management for Hormonia Backend System.

This module provides request-scoped database session management using
contextvars to ensure thread safety in multi-worker environments.

Key Features:
- Request-scoped sessions using contextvars
- Automatic session lifecycle management
- Factory pattern for ServiceProvider instantiation
- Proper error handling and cleanup
- Thread-safe context isolation
"""

import logging
from contextlib import contextmanager, asynccontextmanager
from contextvars import ContextVar
from typing import Optional, Generator, AsyncGenerator
from sqlalchemy.orm import Session
import redis.asyncio as redis

from app.database import SessionLocal

# Import ServiceProvider from dedicated module (avoids package/module shadowing)
from app.service_provider import ServiceProvider

logger = logging.getLogger(__name__)

# Context variable for request-scoped database session
_request_session: ContextVar[Optional[Session]] = ContextVar(
    "request_session", default=None
)

# Context variable for request-scoped Redis client
_request_redis: ContextVar[Optional[redis.Redis]] = ContextVar(
    "request_redis", default=None
)

# Context variable for request-scoped ServiceProvider
_request_service_provider: ContextVar[Optional[ServiceProvider]] = ContextVar(
    "request_service_provider", default=None
)


class SessionManager:
    """
    Manages database sessions with proper lifecycle and thread safety.

    Uses contextvars to ensure each request gets its own database session,
    preventing thread-safety issues in multi-worker environments.
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize session manager.

        Args:
            redis_client: Optional Redis client instance
        """
        self.redis_client = redis_client
        self._session_count = 0

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Get a thread-safe database session with proper lifecycle management.

        This context manager ensures:
        - Each request gets its own database session
        - Sessions are properly closed after use
        - Transactions are rolled back on exceptions
        - Context variables are cleaned up

        Yields:
            Session: SQLAlchemy database session

        Raises:
            SQLAlchemyError: On database connection or transaction errors
        """
        # Check if we already have a session in this context
        existing_session = _request_session.get()
        if existing_session and existing_session.is_active:
            logger.debug(
                f"Reusing existing active session: {hex(id(existing_session))}"
            )
            yield existing_session
            return
        elif existing_session and not existing_session.is_active:
            logger.warning(
                f"Found inactive session in context: {hex(id(existing_session))}, creating new one"
            )
            # Clear the inactive session from context
            _request_session.set(None)

        # Create new session
        try:
            session = SessionLocal()
        except Exception as db_error:
            logger.error(f"Failed to create database session: {db_error}")
            raise RuntimeError(
                f"Database session creation failed: {db_error}"
            ) from db_error

        session_token = _request_session.set(session)
        self._session_count += 1

        session_id = f"session_{self._session_count}"
        session_info = {
            "session_id": session_id,
            "session_hash": hex(id(session)),
            "context_var_id": hex(id(session_token)),
            "redis_available": self.redis_client is not None,
        }
        logger.info(
            f"Created database session: {session_id} (hash: {session_info['session_hash']})"
        )
        logger.debug(f"Session details: {session_info}")

        try:
            yield session
            # Commit any pending transactions
            if session.dirty or session.new or session.deleted:
                dirty_count = len(session.dirty)
                new_count = len(session.new)
                deleted_count = len(session.deleted)
                session.commit()
                logger.info(
                    f"Committed transaction for session: {session_id} "
                    f"(dirty: {dirty_count}, new: {new_count}, deleted: {deleted_count})"
                )
            else:
                logger.debug(f"No changes to commit for session: {session_id}")

        except Exception as e:
            logger.error(f"Session {session_id} error: {e}")
            try:
                session.rollback()
                logger.debug(f"Rolled back transaction for session: {session_id}")
            except Exception as rollback_error:
                logger.error(
                    f"Rollback failed for session {session_id}: {rollback_error}"
                )
            raise

        finally:
            try:
                session.close()
                logger.info(
                    f"Closed database session: {session_id} (hash: {session_info['session_hash']})"
                )
            except Exception as close_error:
                logger.error(f"Error closing session {session_id}: {close_error}")
            finally:
                # Clean up context variable safely
                try:
                    current_session = _request_session.get()
                    if current_session and current_session == session:
                        _request_session.reset(session_token)
                        logger.debug(
                            f"Reset context variable for session: {session_id}"
                        )
                    else:
                        logger.debug(
                            f"Skipped context reset - session mismatch for session: {session_id}"
                        )
                except LookupError:
                    # Context variable already reset or not set
                    logger.debug(
                        f"Context variable already reset for session: {session_id}"
                    )
                except Exception as context_error:
                    logger.warning(
                        f"Error resetting context variable for session {session_id}: {context_error}"
                    )

    def get_service_provider(self, session: Session) -> ServiceProvider:
        """
        Create or get a ServiceProvider instance for the current request.

        Uses contextvars to ensure each request gets its own ServiceProvider
        instance with its own database session and Redis client.

        Args:
            session: Database session for this request

        Returns:
            ServiceProvider: Thread-safe service provider instance
        """
        # Check if we already have a service provider in this context
        existing_provider = _request_service_provider.get()
        if existing_provider and existing_provider.db is session:
            logger.debug(
                f"Reusing existing ServiceProvider (hash: {hex(id(existing_provider))})"
            )
            return existing_provider

        # Create new service provider for this request
        provider = ServiceProvider(session, self.redis_client)
        _request_service_provider.set(provider)

        provider_info = {
            "provider_hash": hex(id(provider)),
            "session_hash": hex(id(session)),
            "redis_available": self.redis_client is not None,
        }
        logger.info(
            f"Created new ServiceProvider for request context: {provider_info['provider_hash']}"
        )
        logger.debug(f"ServiceProvider details: {provider_info}")
        return provider

    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[Session, None]:
        """
        Async version of get_session for use in async contexts.

        Uses the synchronous context manager internally, ensuring proper
        session lifecycle management in async/await contexts.

        Yields:
            Session: SQLAlchemy database session
        """
        logger.debug("Starting async session context")
        try:
            with self.get_session() as session:
                logger.debug(f"Async session yielded: {hex(id(session))}")
                yield session
        except Exception as e:
            logger.error(f"Error in async session context: {e}")
            raise
        finally:
            logger.debug("Async session context ended")

    def get_current_session(self) -> Optional[Session]:
        """
        Get the current session from context if it exists.

        Returns:
            Optional[Session]: Current session or None
        """
        return _request_session.get()

    def get_current_service_provider(self) -> Optional[ServiceProvider]:
        """
        Get the current service provider from context if it exists.

        Returns:
            Optional[ServiceProvider]: Current service provider or None
        """
        return _request_service_provider.get()


class RequestScopeFactory:
    """
    Factory for creating request-scoped dependencies.

    This factory ensures that each FastAPI request gets its own
    database session and service provider instances.
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize request scope factory.

        Args:
            redis_client: Optional Redis client instance
        """
        self.session_manager = SessionManager(redis_client)

    def create_session_dependency(self):
        """
        Create a FastAPI dependency for database sessions.

        Returns:
            Callable: FastAPI dependency function
        """

        def get_db_session() -> Generator[Session, None, None]:
            """FastAPI dependency for getting database session."""
            with self.session_manager.get_session() as session:
                yield session

        return get_db_session

    def create_service_provider_dependency(self):
        """
        Create a FastAPI dependency for ServiceProvider instances.

        Returns:
            Callable: FastAPI dependency function
        """

        def get_service_provider_instance() -> Generator[ServiceProvider, None, None]:
            """FastAPI dependency for getting ServiceProvider."""
            with self.session_manager.get_session() as session:
                provider = self.session_manager.get_service_provider(session)
                yield provider

        return get_service_provider_instance


# Global session manager instance (will be initialized with Redis client)
_global_session_manager: Optional[SessionManager] = None
_global_request_factory: Optional[RequestScopeFactory] = None


def initialize_session_manager(
    redis_client: Optional[redis.Redis] = None,
) -> SessionManager:
    """
    Initialize the global session manager.

    Should be called during application startup.

    Args:
        redis_client: Optional Redis client instance

    Returns:
        SessionManager: Initialized session manager
    """
    global _global_session_manager, _global_request_factory

    _global_session_manager = SessionManager(redis_client)
    _global_request_factory = RequestScopeFactory(redis_client)

    logger.info("Session manager initialized with thread-safe context support")
    return _global_session_manager


def get_session_manager() -> SessionManager:
    """
    Get the global session manager instance.

    Returns:
        SessionManager: Global session manager

    Raises:
        RuntimeError: If session manager has not been initialized
    """
    if _global_session_manager is None:
        logger.error(
            "Session manager not initialized - this will cause service provider failures"
        )
        logger.error(
            "Ensure initialize_session_manager() is called during application startup"
        )
        raise RuntimeError(
            "Session manager not initialized. Call initialize_session_manager() first. "
            "This usually indicates the application lifespan management is not working correctly."
        )
    return _global_session_manager


def get_request_factory() -> RequestScopeFactory:
    """
    Get the global request scope factory.

    Returns:
        RequestScopeFactory: Global request factory

    Raises:
        RuntimeError: If request factory has not been initialized
    """
    if _global_request_factory is None:
        logger.error(
            "Request factory not initialized - this will cause dependency injection failures"
        )
        logger.error(
            "Ensure initialize_session_manager() is called during application startup"
        )
        # Try to provide more context about what might have gone wrong
        if _global_session_manager is None:
            logger.error(
                "Both session manager and request factory are None - startup may have failed"
            )
        else:
            logger.error(
                "Session manager exists but request factory is None - partial initialization"
            )

        raise RuntimeError(
            "Request factory not initialized. Call initialize_session_manager() first. "
            "This usually indicates the application lifespan management failed during startup."
        )
    return _global_request_factory


# Health check utilities
def get_session_health_info() -> dict:
    """
    Get session manager health information.

    Returns:
        dict: Health information including active sessions
    """
    current_session = _request_session.get()
    current_provider = _request_service_provider.get()

    return {
        "has_active_session": current_session is not None,
        "has_active_provider": current_provider is not None,
        "session_id": str(id(current_session)) if current_session else None,
        "provider_id": str(id(current_provider)) if current_provider else None,
    }


def cleanup_session_manager():
    """
    Cleanup global session manager resources.

    Should be called during application shutdown or worker cleanup.
    """
    global _global_session_manager, _global_request_factory
    try:
        if _global_session_manager:
            # Clean up any active sessions
            current_session = _request_session.get()
            if current_session and current_session.is_active:
                try:
                    current_session.close()
                    logger.debug("Closed active session during cleanup")
                except Exception as e:
                    logger.warning(f"Error closing session during cleanup: {e}")

            _global_session_manager = None
            logger.info("Global session manager cleaned up")

        if _global_request_factory:
            _global_request_factory = None
            logger.info("Global request factory cleaned up")

        # Clean up context variables
        cleanup_request_context()

    except Exception as e:
        logger.error(f"Error during session manager cleanup: {e}")


def cleanup_request_context():
    """
    Manually cleanup request context variables.

    Normally not needed as context managers handle cleanup,
    but provided for edge cases or testing.
    """
    try:
        _request_session.set(None)
        _request_service_provider.set(None)
        _request_redis.set(None)
        logger.debug("Request context variables cleaned up")
    except Exception as e:
        logger.error(f"Error cleaning up request context: {e}")
