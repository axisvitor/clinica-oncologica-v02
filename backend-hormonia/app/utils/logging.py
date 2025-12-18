"""
Comprehensive logging utilities for structured JSON logging.
"""

import logging
import traceback
from datetime import datetime
from typing import Any, Optional, Union

from pythonjsonlogger import jsonlogger

from app.config import settings


class StructuredFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)

        # Add timestamp in ISO format
        log_record["timestamp"] = datetime.utcnow().isoformat() + "Z"

        # Add service information
        log_record["service"] = "hormonia-backend"
        log_record["environment"] = settings.APP_ENVIRONMENT

        # Add log level
        log_record["level"] = record.levelname

        # Add logger name
        log_record["logger"] = record.name

        # Add thread and process info
        log_record["thread_id"] = record.thread
        log_record["process_id"] = record.process

        # Add request ID if available
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id

        # Add user ID if available
        if hasattr(record, "user_id"):
            log_record["user_id"] = record.user_id

        # Add patient ID if available
        if hasattr(record, "patient_id"):
            log_record["patient_id"] = record.patient_id

        # Add correlation ID if available
        if hasattr(record, "correlation_id"):
            log_record["correlation_id"] = record.correlation_id

        # Add exception information if present
        if record.exc_info:
            log_record["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }


class HealthCheckFilter(logging.Filter):
    """Filter to exclude health check requests from logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out health check requests."""
        try:
            message = record.getMessage()
            return "/health" not in message and "health_check" not in message
        except (TypeError, ValueError):
            # If getMessage() fails due to formatting issues, allow the record through
            return True


class SensitiveDataFilter(logging.Filter):
    """Filter to remove sensitive data from logs."""

    SENSITIVE_FIELDS = {
        "password",
        "token",
        "secret",
        "key",
        "authorization",
        "cookie",
        "session",
        "api_key",
        "access_token",
        "refresh_token",
    }

    def filter(self, record: logging.LogRecord) -> bool:
        """Remove sensitive data from log records."""
        try:
            if hasattr(record, "args") and record.args:
                # Filter args if they contain sensitive data
                filtered_args = []
                for arg in record.args:
                    if isinstance(arg, dict):
                        filtered_args.append(self._filter_dict(arg))
                    elif isinstance(arg, str):
                        filtered_args.append(self._filter_string(arg))
                    else:
                        filtered_args.append(arg)
                record.args = tuple(filtered_args)

            # Filter the message itself
            if hasattr(record, "msg") and isinstance(record.msg, str):
                record.msg = self._filter_string(record.msg)
        except (TypeError, ValueError, AttributeError):
            # If filtering fails, allow the record through without modification
            pass

        return True

    def _filter_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Filter sensitive data from dictionary."""
        filtered = {}
        for key, value in data.items():
            if key.lower() in self.SENSITIVE_FIELDS:
                filtered[key] = "[REDACTED]"
            elif isinstance(value, dict):
                filtered[key] = self._filter_dict(value)
            elif isinstance(value, list):
                filtered[key] = [
                    self._filter_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                filtered[key] = value
        return filtered

    def _filter_string(self, text: str) -> str:
        """Filter sensitive data from strings."""
        # Simple pattern matching for common sensitive patterns
        import re

        # Filter JWT tokens
        text = re.sub(
            r"Bearer\s+[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+",
            "Bearer [REDACTED]",
            text,
        )

        # Filter API keys (common patterns)
        text = re.sub(
            r'["\']?api[_-]?key["\']?\s*[:=]\s*["\']?[A-Za-z0-9\-_]{20,}["\']?',
            "api_key: [REDACTED]",
            text,
            flags=re.IGNORECASE,
        )

        # Filter passwords
        text = re.sub(
            r'["\']?password["\']?\s*[:=]\s*["\']?[^"\'\s]+["\']?',
            "password: [REDACTED]",
            text,
            flags=re.IGNORECASE,
        )

        return text


def setup_logging():
    """Setup structured logging with JSON and console formatters."""
    # Configure root logger with simple format to avoid Celery conflicts
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Configure specific loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.WARNING)


class LoggerAdapter(logging.LoggerAdapter):
    """Custom logger adapter for adding context to log records."""

    def __init__(self, logger: logging.Logger, extra: Optional[dict[str, Any]] = None):
        super().__init__(logger, extra or {})

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple:
        """Process log record with additional context."""
        # Add extra context to the log record
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        kwargs["extra"].update(self.extra)

        return msg, kwargs

    def with_context(self, **context: Any) -> "LoggerAdapter":
        """Create a new adapter with additional context."""
        new_extra = {**self.extra, **context}
        return LoggerAdapter(self.logger, new_extra)


def get_logger(name: str, **context: Any) -> LoggerAdapter:
    """Get a logger with optional context."""
    logger = logging.getLogger(name)
    return LoggerAdapter(logger, context)


def log_function_call(
    func_name: str,
    args: tuple = None,
    kwargs: dict[str, Any] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Log function call with parameters."""
    if logger is None:
        logger = logging.getLogger(__name__)

    # Filter sensitive data from args and kwargs
    safe_args = args or ()
    safe_kwargs = kwargs or {}

    # Apply sensitive data filtering
    filter_instance = SensitiveDataFilter()
    if isinstance(safe_kwargs, dict):
        safe_kwargs = filter_instance._filter_dict(safe_kwargs)

    logger.debug(
        f"Function call: {func_name}",
        extra={
            "function": func_name,
            "args": safe_args,
            "kwargs": safe_kwargs,
            "event_type": "function_call",
        },
    )


def log_database_operation(
    operation: str,
    table: str,
    record_id: Optional[str] = None,
    duration: Optional[float] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Log database operations."""
    if logger is None:
        logger = logging.getLogger(__name__)

    logger.info(
        f"Database {operation}: {table}",
        extra={
            "operation": operation,
            "table": table,
            "record_id": record_id,
            "duration_ms": duration * 1000 if duration else None,
            "event_type": "database_operation",
        },
    )


def log_external_api_call(
    service: str,
    endpoint: str,
    method: str,
    status_code: Optional[int] = None,
    duration: Optional[float] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Log external API calls."""
    if logger is None:
        logger = logging.getLogger(__name__)

    logger.info(
        f"External API call: {service} {method} {endpoint}",
        extra={
            "service": service,
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "duration_ms": duration * 1000 if duration else None,
            "event_type": "external_api_call",
        },
    )


def log_business_event(
    event_type: str,
    description: str,
    entity_id: Optional[str] = None,
    user_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Log business events."""
    if logger is None:
        logger = logging.getLogger(__name__)

    logger.info(
        f"Business event: {event_type} - {description}",
        extra={
            "event_type": "business_event",
            "business_event_type": event_type,
            "description": description,
            "entity_id": entity_id,
            "user_id": user_id,
            "metadata": metadata or {},
        },
    )


def log_security_event(
    event_type: str,
    description: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    severity: str = "INFO",
    logger: Optional[logging.Logger] = None,
) -> None:
    """Log security events."""
    if logger is None:
        logger = logging.getLogger(__name__)

    log_level = getattr(logging, severity.upper(), logging.INFO)

    logger.log(
        log_level,
        f"Security event: {event_type} - {description}",
        extra={
            "event_type": "security_event",
            "security_event_type": event_type,
            "description": description,
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "severity": severity,
        },
    )


def log_performance_metric(
    metric_name: str,
    value: Union[int, float],
    unit: str = "ms",
    tags: Optional[dict[str, str]] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Log performance metrics."""
    if logger is None:
        logger = logging.getLogger(__name__)

    logger.info(
        f"Performance metric: {metric_name} = {value}{unit}",
        extra={
            "event_type": "performance_metric",
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            "tags": tags or {},
        },
    )


# Initialize logging on module import
setup_logging()
