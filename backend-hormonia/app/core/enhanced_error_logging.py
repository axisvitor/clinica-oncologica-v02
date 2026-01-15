"""
Enhanced Error Logging System with structured logging, correlation IDs, and error aggregation.

This module provides comprehensive error logging capabilities with:
- Structured logging with error context and stack traces
- Correlation IDs for tracking errors across requests
- Error aggregation and alerting mechanisms
- Performance-optimized logging with rate limiting
"""

import asyncio
import logging
import traceback
import uuid
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading

from app.core.logging_config import RateLimitedLogger
from app.models.error_tracking import ErrorLog
from app.database import get_scoped_session


logger = logging.getLogger(__name__)


class LogLevel(str, Enum):
    """Log levels for structured logging."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class ErrorContext:
    """Structured error context information."""

    correlation_id: str
    timestamp: datetime
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    additional_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class ErrorAggregation:
    """Error aggregation data for monitoring."""

    error_type: str
    error_pattern: str
    count: int
    first_occurrence: datetime
    last_occurrence: datetime
    affected_users: Set[str] = field(default_factory=set)
    affected_endpoints: Set[str] = field(default_factory=set)
    correlation_ids: List[str] = field(default_factory=list)
    severity: AlertSeverity = AlertSeverity.LOW

    def should_alert(self, threshold_config: Dict[str, Any]) -> bool:
        """Check if this aggregation should trigger an alert."""
        time_window = threshold_config.get("time_window_minutes", 60)
        count_threshold = threshold_config.get("count_threshold", 10)
        user_threshold = threshold_config.get("affected_users_threshold", 5)

        # Check if within time window
        time_diff = datetime.now(timezone.utc) - self.first_occurrence
        if time_diff > timedelta(minutes=time_window):
            return False

        # Check count threshold
        if self.count >= count_threshold:
            return True

        # Check affected users threshold
        if len(self.affected_users) >= user_threshold:
            return True

        return False


class CorrelationIdManager:
    """Manager for correlation IDs across requests."""

    _local = threading.local()

    @classmethod
    def generate_id(cls) -> str:
        """Generate a new correlation ID."""
        return str(uuid.uuid4())

    @classmethod
    def set_correlation_id(cls, correlation_id: str) -> None:
        """Set correlation ID for current context."""
        cls._local.correlation_id = correlation_id

    @classmethod
    def get_correlation_id(cls) -> Optional[str]:
        """Get correlation ID for current context."""
        return getattr(cls._local, "correlation_id", None)

    @classmethod
    def ensure_correlation_id(cls) -> str:
        """Ensure correlation ID exists, create if not."""
        correlation_id = cls.get_correlation_id()
        if not correlation_id:
            correlation_id = cls.generate_id()
            cls.set_correlation_id(correlation_id)
        return correlation_id

    @classmethod
    @contextmanager
    def correlation_context(cls, correlation_id: Optional[str] = None):
        """Context manager for correlation ID."""
        if correlation_id is None:
            correlation_id = cls.generate_id()

        old_id = cls.get_correlation_id()
        cls.set_correlation_id(correlation_id)
        try:
            yield correlation_id
        finally:
            if old_id:
                cls.set_correlation_id(old_id)
            else:
                cls._local.correlation_id = None


class StructuredErrorLogger:
    """
    Enhanced error logger with structured logging and correlation tracking.
    """

    def __init__(
        self,
        rate_limiter: Optional[RateLimitedLogger] = None,
        enable_aggregation: bool = True,
        enable_alerting: bool = True,
        aggregation_window_minutes: int = 60,
    ):
        """
        Initialize structured error logger.

        Args:
            rate_limiter: Rate limiter for log messages
            enable_aggregation: Whether to enable error aggregation
            enable_alerting: Whether to enable alerting
            aggregation_window_minutes: Time window for error aggregation
        """
        self.rate_limiter = rate_limiter or RateLimitedLogger()
        self.enable_aggregation = enable_aggregation
        self.enable_alerting = enable_alerting
        self.aggregation_window_minutes = aggregation_window_minutes

        # Error aggregation storage
        self.error_aggregations: Dict[str, ErrorAggregation] = {}
        self.aggregation_lock = threading.Lock()

        # Alert configuration
        self.alert_thresholds = {
            "database_errors": {
                "time_window_minutes": 30,
                "count_threshold": 5,
                "affected_users_threshold": 3,
            },
            "api_errors": {
                "time_window_minutes": 60,
                "count_threshold": 10,
                "affected_users_threshold": 5,
            },
            "websocket_errors": {
                "time_window_minutes": 15,
                "count_threshold": 20,
                "affected_users_threshold": 10,
            },
            "authentication_errors": {
                "time_window_minutes": 10,
                "count_threshold": 15,
                "affected_users_threshold": 5,
            },
        }

        # Alert callbacks
        self.alert_callbacks: List[callable] = []

        self.logger = logging.getLogger(__name__)

    def log_error(
        self,
        error: Exception,
        level: LogLevel = LogLevel.ERROR,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        """
        Log error with structured context.

        Args:
            error: The exception to log
            level: Log level
            user_id: User ID associated with the error
            session_id: Session ID
            request_id: Request ID
            endpoint: API endpoint where error occurred
            method: HTTP method
            user_agent: User agent string
            ip_address: Client IP address
            additional_context: Additional context data
            correlation_id: Correlation ID (generated if not provided)

        Returns:
            Correlation ID for the logged error
        """
        # Ensure correlation ID
        if not correlation_id:
            correlation_id = CorrelationIdManager.ensure_correlation_id()

        # Create error context
        error_context = ErrorContext(
            correlation_id=correlation_id,
            timestamp=datetime.now(timezone.utc),
            error_type=type(error).__name__,
            error_message=str(error),
            stack_trace=traceback.format_exc(),
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            endpoint=endpoint,
            method=method,
            user_agent=user_agent,
            ip_address=ip_address,
            additional_context=additional_context or {},
        )

        # Create log message
        log_message = self._format_error_message(error_context)
        log_key = f"error_{error_context.error_type}_{endpoint or 'unknown'}"

        # Check rate limiting
        if self.rate_limiter.should_log(
            log_key, log_message, getattr(logging, level.value)
        ):
            # Log with structured data
            log_level = getattr(logging, level.value)
            self.logger.log(
                log_level,
                log_message,
                extra={
                    "structured_error": error_context.to_dict(),
                    "correlation_id": correlation_id,
                    "error_type": error_context.error_type,
                    "endpoint": endpoint,
                    "user_id": user_id,
                },
            )

            # Store in database asynchronously
            asyncio.create_task(self._store_error_in_db(error_context))

        # Handle aggregation
        if self.enable_aggregation:
            self._aggregate_error(error_context)

        return correlation_id

    def log_structured(
        self,
        message: str,
        level: LogLevel = LogLevel.INFO,
        event_type: str = "general",
        correlation_id: Optional[str] = None,
        **context_data,
    ) -> str:
        """
        Log structured message with correlation ID.

        Args:
            message: Log message
            level: Log level
            event_type: Type of event being logged
            correlation_id: Correlation ID (generated if not provided)
            **context_data: Additional context data

        Returns:
            Correlation ID for the logged message
        """
        if not correlation_id:
            correlation_id = CorrelationIdManager.ensure_correlation_id()

        log_key = f"structured_{event_type}"

        if self.rate_limiter.should_log(
            log_key, message, getattr(logging, level.value)
        ):
            log_level = getattr(logging, level.value)
            self.logger.log(
                log_level,
                message,
                extra={
                    "event_type": event_type,
                    "correlation_id": correlation_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "context": context_data,
                },
            )

        return correlation_id

    def _format_error_message(self, error_context: ErrorContext) -> str:
        """Format error message for logging."""
        parts = [f"[{error_context.correlation_id}]"]

        if error_context.endpoint:
            parts.append(
                f"{error_context.method or 'UNKNOWN'} {error_context.endpoint}"
            )

        parts.append(f"{error_context.error_type}: {error_context.error_message}")

        if error_context.user_id:
            parts.append(f"(User: {error_context.user_id})")

        return " ".join(parts)

    def _aggregate_error(self, error_context: ErrorContext) -> None:
        """Aggregate error for monitoring and alerting."""
        with self.aggregation_lock:
            # Create aggregation key
            error_pattern = (
                f"{error_context.error_type}_{error_context.endpoint or 'unknown'}"
            )

            if error_pattern not in self.error_aggregations:
                self.error_aggregations[error_pattern] = ErrorAggregation(
                    error_type=error_context.error_type,
                    error_pattern=error_pattern,
                    count=0,
                    first_occurrence=error_context.timestamp,
                    last_occurrence=error_context.timestamp,
                )

            aggregation = self.error_aggregations[error_pattern]
            aggregation.count += 1
            aggregation.last_occurrence = error_context.timestamp
            aggregation.correlation_ids.append(error_context.correlation_id)

            if error_context.user_id:
                aggregation.affected_users.add(error_context.user_id)

            if error_context.endpoint:
                aggregation.affected_endpoints.add(error_context.endpoint)

            # Determine severity
            aggregation.severity = self._calculate_severity(aggregation)

            # Check if should alert
            if self.enable_alerting:
                self._check_and_send_alerts(aggregation)

    def _calculate_severity(self, aggregation: ErrorAggregation) -> AlertSeverity:
        """Calculate alert severity based on aggregation data."""
        if aggregation.count >= 50 or len(aggregation.affected_users) >= 20:
            return AlertSeverity.CRITICAL
        elif aggregation.count >= 20 or len(aggregation.affected_users) >= 10:
            return AlertSeverity.HIGH
        elif aggregation.count >= 10 or len(aggregation.affected_users) >= 5:
            return AlertSeverity.MEDIUM
        else:
            return AlertSeverity.LOW

    def _check_and_send_alerts(self, aggregation: ErrorAggregation) -> None:
        """Check if aggregation should trigger alerts and send them."""
        # Get threshold config for error type
        error_category = self._categorize_error(aggregation.error_type)
        threshold_config = self.alert_thresholds.get(
            error_category,
            self.alert_thresholds["api_errors"],  # Default
        )

        if aggregation.should_alert(threshold_config):
            alert_data = {
                "error_pattern": aggregation.error_pattern,
                "error_type": aggregation.error_type,
                "count": aggregation.count,
                "affected_users": len(aggregation.affected_users),
                "affected_endpoints": list(aggregation.affected_endpoints),
                "severity": aggregation.severity.value,
                "first_occurrence": aggregation.first_occurrence.isoformat(),
                "last_occurrence": aggregation.last_occurrence.isoformat(),
                "correlation_ids": aggregation.correlation_ids[-10:],  # Last 10 IDs
            }

            # Send alerts through registered callbacks
            for callback in self.alert_callbacks:
                try:
                    callback(alert_data)
                except Exception as e:
                    self.logger.error(f"Alert callback failed: {e}")

    def _categorize_error(self, error_type: str) -> str:
        """Categorize error type for threshold configuration."""
        error_type_lower = error_type.lower()

        if any(
            db_term in error_type_lower
            for db_term in ["sql", "database", "connection", "integrity"]
        ):
            return "database_errors"
        elif any(
            ws_term in error_type_lower for ws_term in ["websocket", "connection"]
        ):
            return "websocket_errors"
        elif any(
            auth_term in error_type_lower
            for auth_term in ["auth", "permission", "token"]
        ):
            return "authentication_errors"
        else:
            return "api_errors"

    async def _store_error_in_db(self, error_context: ErrorContext) -> None:
        """Store error context in database."""
        try:
            with get_scoped_session() as session:
                error_log = ErrorLog(
                    error_type=error_context.error_type,
                    error_message=error_context.error_message,
                    stack_trace=error_context.stack_trace,
                    context=error_context.to_dict(),
                    severity="ERROR",
                )
                session.add(error_log)
                session.commit()
        except Exception as e:
            # Don't let error storage failures break the application
            self.logger.error(f"Failed to store error in database: {e}")

    def add_alert_callback(self, callback: callable) -> None:
        """Add alert callback function."""
        self.alert_callbacks.append(callback)

    def get_aggregation_stats(self) -> Dict[str, Any]:
        """Get error aggregation statistics."""
        with self.aggregation_lock:
            stats = {"total_patterns": len(self.error_aggregations), "patterns": {}}

            for pattern, aggregation in self.error_aggregations.items():
                stats["patterns"][pattern] = {
                    "count": aggregation.count,
                    "affected_users": len(aggregation.affected_users),
                    "affected_endpoints": len(aggregation.affected_endpoints),
                    "severity": aggregation.severity.value,
                    "first_occurrence": aggregation.first_occurrence.isoformat(),
                    "last_occurrence": aggregation.last_occurrence.isoformat(),
                }

            return stats

    def cleanup_old_aggregations(self) -> None:
        """Clean up old error aggregations."""
        with self.aggregation_lock:
            cutoff_time = datetime.now(timezone.utc) - timedelta(
                minutes=self.aggregation_window_minutes * 2
            )

            patterns_to_remove = []
            for pattern, aggregation in self.error_aggregations.items():
                if aggregation.last_occurrence < cutoff_time:
                    patterns_to_remove.append(pattern)

            for pattern in patterns_to_remove:
                del self.error_aggregations[pattern]

    @contextmanager
    def error_context(
        self,
        operation: str,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        **context_data,
    ):
        """
        Context manager for automatic error logging.

        Args:
            operation: Description of the operation
            user_id: User ID
            correlation_id: Correlation ID
            **context_data: Additional context data
        """
        if not correlation_id:
            correlation_id = CorrelationIdManager.ensure_correlation_id()

        with CorrelationIdManager.correlation_context(correlation_id):
            try:
                yield correlation_id
            except Exception as e:
                self.log_error(
                    error=e,
                    user_id=user_id,
                    correlation_id=correlation_id,
                    additional_context={"operation": operation, **context_data},
                )
                raise


# Global enhanced error logger instance
_enhanced_error_logger: Optional[StructuredErrorLogger] = None


def get_enhanced_error_logger() -> StructuredErrorLogger:
    """
    Get or create enhanced error logger instance.

    Returns:
        StructuredErrorLogger instance
    """
    global _enhanced_error_logger

    if _enhanced_error_logger is None:
        _enhanced_error_logger = StructuredErrorLogger()

    return _enhanced_error_logger


# Convenience functions
def log_error_with_context(
    error: Exception,
    operation: str = "unknown",
    user_id: Optional[str] = None,
    **context_data,
) -> str:
    """Log error with context using global logger."""
    logger_instance = get_enhanced_error_logger()
    return logger_instance.log_error(
        error=error,
        user_id=user_id,
        additional_context={"operation": operation, **context_data},
    )


def log_structured_event(
    message: str,
    event_type: str = "general",
    level: LogLevel = LogLevel.INFO,
    **context_data,
) -> str:
    """Log structured event using global logger."""
    logger_instance = get_enhanced_error_logger()
    return logger_instance.log_structured(
        message=message, level=level, event_type=event_type, **context_data
    )


def error_tracking_context(
    operation: str, user_id: Optional[str] = None, **context_data
):
    """Context manager for error tracking."""
    logger_instance = get_enhanced_error_logger()
    return logger_instance.error_context(
        operation=operation, user_id=user_id, **context_data
    )


# Alert callback example
def console_alert_callback(alert_data: Dict[str, Any]) -> None:
    """Example alert callback that logs to console."""
    severity = alert_data["severity"]
    pattern = alert_data["error_pattern"]
    count = alert_data["count"]

    alert_message = f"ALERT [{severity}]: {pattern} occurred {count} times"

    if severity in ["HIGH", "CRITICAL"]:
        logger.error(alert_message, extra={"alert_data": alert_data})
    else:
        logger.warning(alert_message, extra={"alert_data": alert_data})


# Register default alert callback
get_enhanced_error_logger().add_alert_callback(console_alert_callback)
