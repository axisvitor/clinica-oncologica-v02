"""
Centralized error handling for critical system errors.

This module provides comprehensive error handling with fallback mechanisms,
structured logging, and error tracking for critical system issues.
"""

import logging
import traceback
import time
from typing import Dict, Any, Optional
from datetime import datetime
from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.models.error_tracking import ErrorLog
from app.core.database import get_scoped_session


logger = logging.getLogger(__name__)


class CriticalErrorHandler:
    """
    Centralized handler for critical system errors with fallback mechanisms.

    Provides secure error handling with:
    - Rate limiting to prevent log spam
    - Error deduplication and tracking
    - Secure fallbacks that deny access when uncertain
    - Structured logging with context information
    """

    def __init__(self, max_errors_per_hour: int = 50, enable_tracking: bool = True):
        """
        Initialize the error handler.

        Args:
            max_errors_per_hour: Maximum errors to log per hour per error type
            enable_tracking: Whether to track errors in database
        """
        self.max_errors_per_hour = max_errors_per_hour
        self.enable_tracking = enable_tracking
        self.error_counts: Dict[str, list] = defaultdict(list)
        self.logger = logging.getLogger(__name__)

    def _should_log_error(self, error_key: str) -> bool:
        """
        Check if we should log this error based on rate limiting.

        Args:
            error_key: Unique key for the error type

        Returns:
            True if error should be logged, False if rate limited
        """
        now = time.time()
        one_hour_ago = now - 3600

        # Clean old entries
        self.error_counts[error_key] = [
            timestamp
            for timestamp in self.error_counts[error_key]
            if timestamp > one_hour_ago
        ]

        # Check if we're under the limit
        if len(self.error_counts[error_key]) < self.max_errors_per_hour:
            self.error_counts[error_key].append(now)
            return True

        return False

    def _create_error_key(self, error_type: str, error_message: str) -> str:
        """Create a unique key for error deduplication."""
        return f"{error_type}:{hash(error_message)}"

    async def _track_error_in_db(
        self,
        error_type: str,
        error_message: str,
        context: Dict[str, Any],
        stack_trace: Optional[str] = None,
        severity: str = "ERROR",
    ) -> Optional[ErrorLog]:
        """
        Track error in database with deduplication.

        Args:
            error_type: Type of error (e.g., 'DI_GENERATOR', 'ROLE_ENUM')
            error_message: The error message
            context: Additional context information
            stack_trace: Full stack trace (optional)
            severity: Error severity level

        Returns:
            ErrorLog instance if successfully tracked, None otherwise
        """
        if not self.enable_tracking:
            return None

        try:
            with get_scoped_session() as session:
                # Check for existing error (deduplication)
                existing_error = (
                    session.query(ErrorLog)
                    .filter(
                        ErrorLog.error_type == error_type,
                        ErrorLog.error_message == error_message,
                    )
                    .first()
                )

                if existing_error:
                    # Update existing error
                    existing_error.increment_count()
                    existing_error.context = context  # Update context with latest info
                    if stack_trace:
                        existing_error.stack_trace = stack_trace
                    session.commit()
                    return existing_error
                else:
                    # Create new error log
                    error_log = ErrorLog(
                        error_type=error_type,
                        error_message=error_message,
                        stack_trace=stack_trace,
                        context=context,
                        severity=severity,
                    )
                    session.add(error_log)
                    session.commit()
                    return error_log

        except Exception as e:
            # Don't let error tracking failures break the application
            self.logger.error(f"Failed to track error in database: {e}")
            return None

    async def handle_dependency_injection_error(
        self, error: Exception, context: Dict[str, Any]
    ) -> None:
        """
        Handle dependency injection errors with fallback.

        Args:
            error: The dependency injection error
            context: Additional context (endpoint, request info, etc.)

        Raises:
            HTTPException: Service unavailable error with secure message
        """
        error_type = "DI_GENERATOR_ERROR"
        error_message = str(error)
        error_key = self._create_error_key(error_type, error_message)

        # Log with rate limiting
        if self._should_log_error(error_key):
            self.logger.error(
                f"Dependency injection error: {error_message}",
                extra={
                    "error_type": error_type,
                    "context": context,
                    "stack_trace": traceback.format_exc(),
                },
            )

            # Track in database
            await self._track_error_in_db(
                error_type=error_type,
                error_message=error_message,
                context=context,
                stack_trace=traceback.format_exc(),
                severity="CRITICAL",
            )

        # Secure fallback: provide generic error message
        raise HTTPException(
            status_code=500, detail="Service temporarily unavailable. Please try again."
        )

    async def handle_role_enum_error(
        self,
        error: Exception,
        user_role: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> None:
        """
        Handle role enum errors with secure fallback.

        Args:
            error: The role enum error (AttributeError, etc.)
            user_role: The problematic user role
            endpoint: The endpoint where error occurred

        Raises:
            HTTPException: Access denied with secure message
        """
        error_type = "ROLE_ENUM_ERROR"
        error_message = str(error)
        error_key = self._create_error_key(error_type, error_message)

        context = {
            "user_role": user_role,
            "endpoint": endpoint,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Log with rate limiting
        if self._should_log_error(error_key):
            self.logger.error(
                f"Role enum error: {error_message}",
                extra={
                    "error_type": error_type,
                    "context": context,
                    "stack_trace": traceback.format_exc(),
                },
            )

            # Track in database
            await self._track_error_in_db(
                error_type=error_type,
                error_message=error_message,
                context=context,
                stack_trace=traceback.format_exc(),
                severity="ERROR",
            )

        # Secure fallback: deny access
        raise HTTPException(
            status_code=403, detail="Access denied. Invalid role configuration."
        )

    async def handle_schema_mismatch_error(
        self,
        error: Exception,
        table_name: Optional[str] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Handle database schema mismatch errors.

        Args:
            error: The schema mismatch error
            table_name: Name of the affected table
            operation: The database operation that failed
            context: Additional context information

        Raises:
            HTTPException: Service unavailable with guidance
        """
        error_type = "SCHEMA_MISMATCH_ERROR"
        error_message = str(error)
        error_key = self._create_error_key(error_type, error_message)

        error_context = {
            "table_name": table_name,
            "operation": operation,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if context:
            error_context.update(context)

        # Log with rate limiting
        if self._should_log_error(error_key):
            self.logger.error(
                f"Schema mismatch error: {error_message}",
                extra={
                    "error_type": error_type,
                    "context": error_context,
                    "stack_trace": traceback.format_exc(),
                },
            )

            # Track in database
            await self._track_error_in_db(
                error_type=error_type,
                error_message=error_message,
                context=error_context,
                stack_trace=traceback.format_exc(),
                severity="ERROR",
            )

        # Provide helpful error message
        raise HTTPException(
            status_code=500,
            detail="Database schema mismatch detected. Please contact support.",
        )

    async def handle_validation_error(
        self,
        error: Exception,
        field_name: Optional[str] = None,
        input_value: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Handle validation errors with user-friendly messages.

        Args:
            error: The validation error
            field_name: Name of the field that failed validation
            input_value: The invalid input value (sanitized)
            context: Additional context information

        Raises:
            HTTPException: Bad request with helpful error message
        """
        error_type = "VALIDATION_ERROR"
        error_message = str(error)
        error_key = self._create_error_key(error_type, error_message)

        error_context = {
            "field_name": field_name,
            "input_type": type(input_value).__name__
            if input_value is not None
            else None,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if context:
            error_context.update(context)

        # Log with rate limiting (lower severity for validation errors)
        if self._should_log_error(error_key):
            self.logger.warning(
                f"Validation error: {error_message}",
                extra={"error_type": error_type, "context": error_context},
            )

            # Track in database with lower severity
            await self._track_error_in_db(
                error_type=error_type,
                error_message=error_message,
                context=error_context,
                severity="WARNING",
            )

        # Provide user-friendly error message
        if field_name:
            detail = f"Invalid value for field '{field_name}': {error_message}"
        else:
            detail = f"Validation error: {error_message}"

        raise HTTPException(status_code=400, detail=detail)

    async def handle_generic_error(
        self,
        error: Exception,
        error_type: str = "GENERIC_ERROR",
        context: Optional[Dict[str, Any]] = None,
        severity: str = "ERROR",
        status_code: int = 500,
        user_message: str = "An unexpected error occurred. Please try again.",
    ) -> None:
        """
        Handle generic errors with customizable response.

        Args:
            error: The error that occurred
            error_type: Type classification for the error
            context: Additional context information
            severity: Error severity level
            status_code: HTTP status code to return
            user_message: User-friendly error message

        Raises:
            HTTPException: Error response with specified status code
        """
        error_message = str(error)
        error_key = self._create_error_key(error_type, error_message)

        error_context = {"timestamp": datetime.utcnow().isoformat()}
        if context:
            error_context.update(context)

        # Log with rate limiting
        if self._should_log_error(error_key):
            log_level = getattr(logging, severity, logging.ERROR)
            self.logger.log(
                log_level,
                f"{error_type}: {error_message}",
                extra={
                    "error_type": error_type,
                    "context": error_context,
                    "stack_trace": traceback.format_exc(),
                },
            )

            # Track in database
            await self._track_error_in_db(
                error_type=error_type,
                error_message=error_message,
                context=error_context,
                stack_trace=traceback.format_exc(),
                severity=severity,
            )

        raise HTTPException(status_code=status_code, detail=user_message)

    def error_context(self, operation: str, **context_data):
        """
        Context manager for automatic error handling.

        Args:
            operation: Description of the operation being performed
            **context_data: Additional context data

        Usage:
            with error_handler.error_context("user_authentication", user_id="123"):
                # Code that might raise errors
                pass
        """

        class ErrorContextManager:
            def __init__(self, handler, operation, context_data):
                self.handler = handler
                self.operation = operation
                self.context_data = context_data

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    return False

                if issubclass(exc_type, HTTPException):
                    # Re-raise HTTP exceptions as-is
                    return False

                # Handle unexpected errors

                # Determine error type and raise appropriate HTTPException
                if issubclass(exc_type, AttributeError) and "UserRole" in str(exc_val):
                    # Convert to HTTPException for role errors
                    raise HTTPException(
                        status_code=403,
                        detail="Access denied. Invalid role configuration.",
                    ) from exc_val
                elif issubclass(exc_type, SQLAlchemyError):
                    # Convert to HTTPException for schema errors
                    raise HTTPException(
                        status_code=500,
                        detail="Database schema mismatch detected. Please contact support.",
                    ) from exc_val
                else:
                    # Convert to HTTPException for generic errors
                    raise HTTPException(
                        status_code=500,
                        detail="An unexpected error occurred. Please try again.",
                    ) from exc_val

        return ErrorContextManager(self, operation, context_data)

    def get_error_stats(self) -> Dict[str, Any]:
        """
        Get current error statistics.

        Returns:
            Dictionary with error statistics
        """
        now = time.time()
        one_hour_ago = now - 3600

        stats = {}
        for error_key, timestamps in self.error_counts.items():
            recent_errors = [t for t in timestamps if t > one_hour_ago]
            stats[error_key] = {
                "count_last_hour": len(recent_errors),
                "rate_limited": len(recent_errors) >= self.max_errors_per_hour,
            }

        return {
            "error_types": stats,
            "total_error_types": len(stats),
            "rate_limit_threshold": self.max_errors_per_hour,
        }


# Global error handler instance
error_handler = CriticalErrorHandler()


# Convenience functions for common error types
async def handle_di_error(error: Exception, context: Dict[str, Any]) -> None:
    """Convenience function for dependency injection errors."""
    await error_handler.handle_dependency_injection_error(error, context)


async def handle_role_error(
    error: Exception, user_role: str = None, endpoint: str = None
) -> None:
    """Convenience function for role enum errors."""
    await error_handler.handle_role_enum_error(error, user_role, endpoint)


async def handle_schema_error(
    error: Exception, table_name: str = None, operation: str = None
) -> None:
    """Convenience function for schema mismatch errors."""
    await error_handler.handle_schema_mismatch_error(error, table_name, operation)


async def handle_validation_error(
    error: Exception, field_name: str = None, input_value: Any = None
) -> None:
    """Convenience function for validation errors."""
    await error_handler.handle_validation_error(error, field_name, input_value)
