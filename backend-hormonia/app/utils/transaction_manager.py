"""
Database transaction management utilities.

Provides async and sync context managers for database transactions
with automatic commit/rollback and error handling.

Author: Code Implementation Agent
Date: 2025-01-22
"""

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator, Callable, Any, Union
from collections.abc import Awaitable
import logging
import functools

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@asynccontextmanager
async def async_transaction(
    session: AsyncSession,
    auto_commit: bool = True,
    rollback_on_error: bool = True,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database transactions.

    Provides automatic commit on success and rollback on failure.

    Args:
        session: AsyncSession for database operations
        auto_commit: Automatically commit on success (default: True)
        rollback_on_error: Automatically rollback on error (default: True)

    Yields:
        AsyncSession: The database session

    Example:
        >>> async with async_transaction(db) as session:
        ...     session.add(new_record)
        ...     # Auto-commits on success, auto-rolls back on exception

    Raises:
        Exception: Re-raises any exception after rollback
    """
    try:
        yield session

        if auto_commit:
            await session.commit()
            logger.debug("Transaction committed successfully")

    except Exception as e:
        if rollback_on_error:
            await session.rollback()
            logger.error(f"Transaction rolled back due to error: {e}")
        raise


@contextmanager
def sync_transaction(
    session: Session,
    auto_commit: bool = True,
    rollback_on_error: bool = True,
) -> Generator[Session, None, None]:
    """
    Sync context manager for database transactions.

    Provides automatic commit on success and rollback on failure.

    Args:
        session: Session for database operations
        auto_commit: Automatically commit on success (default: True)
        rollback_on_error: Automatically rollback on error (default: True)

    Yields:
        Session: The database session

    Example:
        >>> with sync_transaction(db) as session:
        ...     session.add(new_record)
        ...     # Auto-commits on success, auto-rolls back on exception

    Raises:
        Exception: Re-raises any exception after rollback
    """
    try:
        yield session

        if auto_commit:
            session.commit()
            logger.debug("Transaction committed successfully")

    except Exception as e:
        if rollback_on_error:
            session.rollback()
            logger.error(f"Transaction rolled back due to error: {e}")
        raise


def with_transaction(
    auto_commit: bool = True,
    rollback_on_error: bool = True
) -> Callable[[Callable], Callable]:
    """Decorator for automatic transaction management on async/sync functions.

    Wraps the function with async_transaction or sync_transaction context manager.
    Expects 'db' or 'session' parameter in function signature.

    Args:
        auto_commit: Automatically commit on success. Defaults to True.
        rollback_on_error: Automatically rollback on error. Defaults to True.

    Returns:
        Decorator function that wraps target function with transaction management

    Example:
        >>> @with_transaction()
        ... async def create_record(db: AsyncSession, data: dict):
        ...     record = Model(**data)
        ...     db.add(record)
        ...     return record
        >>>
        >>> @with_transaction(auto_commit=False)
        ... def update_record(session: Session, record_id: int, data: dict):
        ...     record = session.query(Model).get(record_id)
        ...     record.update(**data)
        ...     return record

    Raises:
        ValueError: If no database session found in function arguments
        TypeError: If session type doesn't match expected AsyncSession/Session
        Exception: Re-raises any exception after rollback
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Extract session from kwargs
            session = kwargs.get("db") or kwargs.get("session")

            # Extract from args if not in kwargs
            if not session and args:
                # Check if first arg is a session
                if isinstance(args[0], (AsyncSession, Session)):
                    session = args[0]
                # Check if first arg has a db/session attribute (service pattern)
                elif hasattr(args[0], "db"):
                    session = args[0].db
                elif hasattr(args[0], "session"):
                    session = args[0].session

            if not session:
                raise ValueError(
                    f"No database session found in {func.__name__} arguments. "
                    "Expected 'db' or 'session' parameter."
                )

            # Use appropriate transaction context
            if isinstance(session, AsyncSession):
                async with async_transaction(session, auto_commit, rollback_on_error):
                    return await func(*args, **kwargs)
            else:
                raise TypeError(
                    f"with_transaction decorator expects AsyncSession, got {type(session)}"
                )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Extract session from kwargs
            session = kwargs.get("db") or kwargs.get("session")

            # Extract from args if not in kwargs
            if not session and args:
                if isinstance(args[0], Session):
                    session = args[0]
                elif hasattr(args[0], "db"):
                    session = args[0].db
                elif hasattr(args[0], "session"):
                    session = args[0].session

            if not session:
                raise ValueError(
                    f"No database session found in {func.__name__} arguments. "
                    "Expected 'db' or 'session' parameter."
                )

            # Use sync transaction context
            if isinstance(session, Session):
                with sync_transaction(session, auto_commit, rollback_on_error):
                    return func(*args, **kwargs)
            else:
                raise TypeError(
                    f"with_transaction decorator expects Session, got {type(session)}"
                )

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Export public API
__all__ = [
    "async_transaction",
    "sync_transaction",
    "with_transaction",
]
