"""Database retry logic with exponential backoff and circuit breaker

This module provides a robust decorator for database operations that implements:
- Exponential backoff with jitter for retries
- Circuit breaker pattern to prevent cascade failures
- Automatic session rollback on failures
- Comprehensive logging for debugging

Usage:
    from app.utils.db_retry import with_db_retry

    class MyService:
        @with_db_retry(max_retries=3)
        def get_data(self, db: Session, id: UUID):
            return db.query(Model).filter(Model.id == id).first()
"""
import asyncio
import functools
import logging
import time
from typing import Callable, Optional, Any
import random
from sqlalchemy.exc import (
    OperationalError,
    TimeoutError as SQLTimeoutError,
    DBAPIError,
    IntegrityError,
    ProgrammingError,
    DataError
)
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _attempt_rollback(args, kwargs):
    """Attempt to rollback database session from various sources
    
    Checks for session in kwargs['db'], args[0].db, or args[0].repository.db
    """
    # Check kwargs first
    if 'db' in kwargs and isinstance(kwargs['db'], Session):
        try:
            kwargs['db'].rollback()
            logger.debug("Rolled back session from kwargs['db']")
            return True
        except Exception as e:
            logger.warning(f"Failed to rollback session from kwargs: {str(e)}")
    
    # Check self.db pattern (common in services)
    if args and hasattr(args[0], 'db') and isinstance(args[0].db, Session):
        try:
            args[0].db.rollback()
            logger.debug("Rolled back session from self.db")
            return True
        except Exception as e:
            logger.warning(f"Failed to rollback session from self.db: {str(e)}")
    
    # Check self.repository.db pattern
    if (args and hasattr(args[0], 'repository') and 
        hasattr(args[0].repository, 'db') and 
        isinstance(args[0].repository.db, Session)):
        try:
            args[0].repository.db.rollback()
            logger.debug("Rolled back session from self.repository.db")
            return True
        except Exception as e:
            logger.warning(f"Failed to rollback session from self.repository.db: {str(e)}")
    
    return False


class DatabaseCircuitBreaker:
    """Circuit breaker for database operations

    Implements the circuit breaker pattern to prevent cascade failures:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests are rejected immediately
    - HALF_OPEN: Testing if service has recovered

    Attributes:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery
        failure_count: Current count of consecutive failures
        last_failure_time: Timestamp of last failure
        state: Current circuit state (closed/open/half_open)
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        """Initialize circuit breaker

        Args:
            failure_threshold: Number of failures before circuit opens
            recovery_timeout: Seconds before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half_open

    def _check_circuit_state(self):
        """Check and update circuit state before operation

        Raises:
            Exception: If circuit is open and not ready for recovery
        """
        if self.state == "open":
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.recovery_timeout:
                logger.info("Circuit breaker transitioning to HALF_OPEN state")
                self.state = "half_open"
            else:
                logger.error("Circuit breaker is OPEN - rejecting database operation")
                raise Exception("Circuit breaker is OPEN - database operations temporarily disabled")

    def _record_success(self):
        """Record successful operation and update circuit state"""
        if self.state == "half_open":
            logger.info("Circuit breaker closing after successful operation")
            self.state = "closed"
            self.failure_count = 0

    def _record_failure(self):
        """Record failed operation and update circuit state"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        # Open circuit if threshold exceeded
        if self.failure_count >= self.failure_threshold:
            logger.error(
                f"Circuit breaker OPENING after {self.failure_count} failures. "
                f"Will attempt recovery in {self.recovery_timeout}s"
            )
            self.state = "open"

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute synchronous function through circuit breaker

        Args:
            func: Synchronous function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result from function execution

        Raises:
            Exception: If circuit is open or function fails
        """
        self._check_circuit_state()

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result

        except (ProgrammingError, DataError):
            # Don't count non-transitory errors for circuit breaker
            raise
        except Exception as e:
            self._record_failure()
            raise

    async def acall(self, func: Callable, *args, **kwargs) -> Any:
        """Execute asynchronous function through circuit breaker

        Args:
            func: Async function to execute (coroutine function)
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result from function execution

        Raises:
            Exception: If circuit is open or function fails
        """
        self._check_circuit_state()

        try:
            # Properly await the coroutine
            result = await func(*args, **kwargs)
            self._record_success()
            return result

        except (ProgrammingError, DataError):
            # Don't count non-transitory errors for circuit breaker
            raise
        except Exception as e:
            self._record_failure()
            raise


# Global circuit breaker instance
db_circuit_breaker = DatabaseCircuitBreaker()


def with_db_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    jitter: bool = True
):
    """Decorator for database operations with retry logic and circuit breaker

    Provides automatic retry with exponential backoff for transient database errors.
    Works with both sync and async functions. Integrates with circuit breaker pattern.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds between retries (default: 1.0)
        max_delay: Maximum delay in seconds (default: 10.0)
        exponential_base: Base for exponential backoff calculation (default: 2.0)
        jitter: Add randomization to delays to prevent thundering herd (default: True)

    Returns:
        Decorated function with retry logic

    Example:
        @with_db_retry(max_retries=5, base_delay=0.5)
        async def create_patient(db: Session, data: dict):
            patient = Patient(**data)
            db.add(patient)
            db.commit()
            return patient
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    # Execute through circuit breaker (async variant)
                    result = await db_circuit_breaker.acall(func, *args, **kwargs)
                    return result

                except (ProgrammingError, DataError) as e:
                    # Non-transitory errors - rollback and fail immediately
                    logger.error(f"Non-transitory database error in {func.__name__}: {str(e)}")
                    _attempt_rollback(args, kwargs)
                    raise
                    
                except (OperationalError, SQLTimeoutError, DBAPIError) as e:
                    last_exception = e

                    # Don't retry on integrity errors (data constraint violations)
                    if isinstance(e, IntegrityError):
                        logger.error(f"Integrity error in {func.__name__}: {str(e)}")
                        _attempt_rollback(args, kwargs)
                        raise

                    # Attempt to rollback session
                    _attempt_rollback(args, kwargs)

                    # Retry logic
                    if attempt < max_retries:
                        # Calculate delay with exponential backoff
                        delay = min(base_delay * (exponential_base ** attempt), max_delay)

                        # Add jitter to prevent thundering herd
                        if jitter:
                            delay *= (0.5 + random.random())

                        logger.warning(
                            f"Database operation '{func.__name__}' failed "
                            f"(attempt {attempt + 1}/{max_retries + 1}). "
                            f"Retrying in {delay:.2f}s. Error: {str(e)}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Database operation '{func.__name__}' failed after "
                            f"{max_retries + 1} attempts. Last error: {str(e)}"
                        )
                        raise last_exception

            raise last_exception

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    # Execute through circuit breaker
                    result = db_circuit_breaker.call(func, *args, **kwargs)
                    return result

                except (ProgrammingError, DataError) as e:
                    # Non-transitory errors - rollback and fail immediately
                    logger.error(f"Non-transitory database error in {func.__name__}: {str(e)}")
                    _attempt_rollback(args, kwargs)
                    raise
                    
                except (OperationalError, SQLTimeoutError, DBAPIError) as e:
                    last_exception = e

                    # Don't retry on integrity errors
                    if isinstance(e, IntegrityError):
                        logger.error(f"Integrity error in {func.__name__}: {str(e)}")
                        _attempt_rollback(args, kwargs)
                        raise

                    # Attempt to rollback session
                    _attempt_rollback(args, kwargs)

                    # Retry logic
                    if attempt < max_retries:
                        # Calculate delay with exponential backoff
                        delay = min(base_delay * (exponential_base ** attempt), max_delay)

                        # Add jitter
                        if jitter:
                            delay *= (0.5 + random.random())

                        logger.warning(
                            f"Database operation '{func.__name__}' failed "
                            f"(attempt {attempt + 1}/{max_retries + 1}). "
                            f"Retrying in {delay:.2f}s. Error: {str(e)}"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"Database operation '{func.__name__}' failed after "
                            f"{max_retries + 1} attempts. Last error: {str(e)}"
                        )
                        raise last_exception

            raise last_exception

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def reset_circuit_breaker():
    """Reset the global circuit breaker to closed state

    Useful for testing or manual recovery operations.
    """
    global db_circuit_breaker
    db_circuit_breaker.state = "closed"
    db_circuit_breaker.failure_count = 0
    db_circuit_breaker.last_failure_time = None
    logger.info("Circuit breaker manually reset to CLOSED state")