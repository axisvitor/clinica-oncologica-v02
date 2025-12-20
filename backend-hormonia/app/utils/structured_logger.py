"""
Structured logging utility with correlation IDs and JSON formatting.

Provides comprehensive logging with request correlation, performance metrics,
and context propagation for distributed tracing.
"""

import logging
import json
import uuid
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from functools import wraps
import time

# Context variables for request tracking
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
request_id: ContextVar[str] = ContextVar("request_id", default="")
user_id: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
request_path: ContextVar[str] = ContextVar("request_path", default="")


class StructuredLogger:
    """
    Structured logger that outputs JSON-formatted logs with correlation IDs
    and request context for easy parsing and filtering.
    """

    def __init__(self, name: str):
        """
        Initialize structured logger.

        Args:
            name: Logger name (typically module name)
        """
        self.logger = logging.getLogger(name)
        self.name = name

    def _format_message(
        self, level: str, message: str, exc_info: Optional[Exception] = None, **kwargs
    ) -> str:
        """
        Format log message as JSON with context.

        Args:
            level: Log level (INFO, WARNING, ERROR, etc.)
            message: Log message
            exc_info: Exception information if available
            **kwargs: Additional context fields

        Returns:
            JSON-formatted log string
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "level": level,
            "logger": self.name,
            "message": message,
            "correlation_id": correlation_id.get() or str(uuid.uuid4()),
            "request_id": request_id.get() or "",
            "request_path": request_path.get() or "",
        }

        # Add user ID if available
        if user_id.get():
            log_data["user_id"] = user_id.get()

        # Add exception information
        if exc_info:
            log_data["exception"] = {
                "type": type(exc_info).__name__,
                "message": str(exc_info),
                "traceback": traceback.format_exc(),
            }

        # Add additional context
        log_data.update(kwargs)

        return json.dumps(log_data)

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(self._format_message("DEBUG", message, **kwargs))

    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(self._format_message("INFO", message, **kwargs))

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(self._format_message("WARNING", message, **kwargs))

    def error(self, message: str, exc_info: Optional[Exception] = None, **kwargs):
        """Log error message with optional exception info."""
        self.logger.error(
            self._format_message("ERROR", message, exc_info=exc_info, **kwargs)
        )

    def critical(self, message: str, exc_info: Optional[Exception] = None, **kwargs):
        """Log critical message with optional exception info."""
        self.logger.critical(
            self._format_message("CRITICAL", message, exc_info=exc_info, **kwargs)
        )

    def log_performance(self, operation: str, duration_ms: float, **kwargs):
        """
        Log performance metrics.

        Args:
            operation: Operation name
            duration_ms: Duration in milliseconds
            **kwargs: Additional metrics
        """
        self.info(
            f"Performance metric: {operation}",
            operation=operation,
            duration_ms=round(duration_ms, 2),
            metric_type="performance",
            **kwargs,
        )

    def log_query(self, query_type: str, table: str, duration_ms: float, **kwargs):
        """
        Log database query metrics.

        Args:
            query_type: Type of query (SELECT, INSERT, UPDATE, DELETE)
            table: Table name
            duration_ms: Query duration in milliseconds
            **kwargs: Additional query context
        """
        self.info(
            f"Database query: {query_type} on {table}",
            query_type=query_type,
            table=table,
            duration_ms=round(duration_ms, 2),
            metric_type="database_query",
            **kwargs,
        )

    def log_cache_operation(self, operation: str, hit: bool, key: str, **kwargs):
        """
        Log cache operation.

        Args:
            operation: Cache operation (GET, SET, DELETE)
            hit: Whether cache hit occurred
            key: Cache key
            **kwargs: Additional context
        """
        self.info(
            f"Cache {operation}: {'HIT' if hit else 'MISS'}",
            operation=operation,
            cache_hit=hit,
            cache_key=key,
            metric_type="cache_operation",
            **kwargs,
        )

    def log_api_call(
        self, endpoint: str, method: str, status_code: int, duration_ms: float, **kwargs
    ):
        """
        Log API call metrics.

        Args:
            endpoint: API endpoint
            method: HTTP method
            status_code: Response status code
            duration_ms: Request duration in milliseconds
            **kwargs: Additional context
        """
        self.info(
            f"API call: {method} {endpoint}",
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration_ms=round(duration_ms, 2),
            metric_type="api_call",
            **kwargs,
        )


def set_correlation_id(corr_id: str):
    """Set correlation ID for current context."""
    correlation_id.set(corr_id)


def get_correlation_id() -> str:
    """Get correlation ID from current context."""
    return correlation_id.get() or str(uuid.uuid4())


def set_request_id(req_id: str):
    """Set request ID for current context."""
    request_id.set(req_id)


def set_user_id(uid: Optional[str]):
    """Set user ID for current context."""
    user_id.set(uid)


def set_request_path(path: str):
    """Set request path for current context."""
    request_path.set(path)


def clear_context():
    """Clear all context variables."""
    correlation_id.set("")
    request_id.set("")
    user_id.set(None)
    request_path.set("")


def log_execution_time(logger: StructuredLogger, operation: str):
    """
    Decorator to log execution time of a function.

    Args:
        logger: Structured logger instance
        operation: Operation name for logging
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.log_performance(operation, duration_ms, status="success")
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.log_performance(
                    operation, duration_ms, status="error", error=str(e)
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.log_performance(operation, duration_ms, status="success")
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                logger.log_performance(
                    operation, duration_ms, status="error", error=str(e)
                )
                raise

        # Return appropriate wrapper based on function type
        if hasattr(func, "__await__"):
            return async_wrapper
        return sync_wrapper

    return decorator


def configure_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path for file output
    """
    # Set log level
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger.addHandler(file_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)


# Create default logger
logger = StructuredLogger(__name__)
