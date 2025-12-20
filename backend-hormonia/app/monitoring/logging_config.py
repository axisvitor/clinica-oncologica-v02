"""
Structured logging configuration for monitoring and observability.

Provides JSON-formatted logging with context-aware fields.
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional context fields."""

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any],
    ) -> None:
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)

        # Add timestamp
        log_record["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Add log level
        log_record["level"] = record.levelname

        # Add logger name
        log_record["logger"] = record.name

        # Add module and function
        log_record["module"] = record.module
        log_record["function"] = record.funcName

        # Add line number
        log_record["line"] = record.lineno

        # Add process and thread info
        log_record["process_id"] = record.process
        log_record["thread_id"] = record.thread


def configure_structured_logging(
    log_level: str = "INFO", log_file: Optional[str] = None
) -> None:
    """
    Configure structured JSON logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path for file handler
    """
    # Create formatter
    formatter = CustomJsonFormatter("%(timestamp)s %(level)s %(name)s %(message)s")

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers = []

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_structured_logger(name: str) -> logging.Logger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_security_event(
    logger: logging.Logger,
    event_type: str,
    severity: str,
    details: Dict[str, Any],
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
) -> None:
    """
    Log a security event with structured context.

    Args:
        logger: Logger instance
        event_type: Type of security event (e.g., "failed_auth", "unauthorized_access")
        severity: Event severity (low, medium, high, critical)
        details: Additional event details
        user_id: Optional user ID
        ip_address: Optional IP address
    """
    log_data = {
        "event_category": "security",
        "event_type": event_type,
        "severity": severity,
        "details": details,
    }

    if user_id:
        log_data["user_id"] = user_id

    if ip_address:
        log_data["ip_address"] = ip_address

    # Choose log level based on severity
    level_map = {
        "low": logging.INFO,
        "medium": logging.WARNING,
        "high": logging.ERROR,
        "critical": logging.CRITICAL,
    }

    log_level = level_map.get(severity, logging.WARNING)
    logger.log(log_level, f"Security event: {event_type}", extra=log_data)


def log_performance_event(
    logger: logging.Logger,
    event_type: str,
    duration_ms: float,
    details: Dict[str, Any],
    threshold_exceeded: bool = False,
) -> None:
    """
    Log a performance event with structured context.

    Args:
        logger: Logger instance
        event_type: Type of performance event (e.g., "slow_query", "high_latency")
        duration_ms: Event duration in milliseconds
        details: Additional event details
        threshold_exceeded: Whether performance threshold was exceeded
    """
    log_data = {
        "event_category": "performance",
        "event_type": event_type,
        "duration_ms": duration_ms,
        "threshold_exceeded": threshold_exceeded,
        "details": details,
    }

    log_level = logging.WARNING if threshold_exceeded else logging.INFO
    logger.log(log_level, f"Performance event: {event_type}", extra=log_data)


def log_business_event(
    logger: logging.Logger,
    event_type: str,
    entity_type: str,
    entity_id: Optional[int],
    details: Dict[str, Any],
    user_id: Optional[int] = None,
) -> None:
    """
    Log a business event with structured context.

    Args:
        logger: Logger instance
        event_type: Type of business event (e.g., "patient_created", "saga_completed")
        entity_type: Type of entity (e.g., "patient", "saga")
        entity_id: Entity ID
        details: Additional event details
        user_id: Optional user ID who triggered the event
    """
    log_data = {
        "event_category": "business",
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": details,
    }

    if user_id:
        log_data["user_id"] = user_id

    logger.info(f"Business event: {event_type}", extra=log_data)
