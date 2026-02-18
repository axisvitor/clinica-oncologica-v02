"""
Structured logging configuration for monitoring system integration.

This module provides structured logging specifically designed for monitoring
systems, with proper formatting, context injection, and alert correlation.
"""

import json
import logging
import time
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
from functools import wraps

from app.core.logging_config import RateLimitedLogger
from app.utils.timezone import now_sao_paulo


class MonitoringLogger:
    """
    Structured logger for monitoring system integration.

    Provides:
    - Structured JSON logging for monitoring systems
    - Context injection for correlation
    - Alert-level classification
    - Performance metrics logging
    - Error pattern detection
    """

    def __init__(self, logger_name: str = "monitoring"):
        """
        Initialize monitoring logger.

        Args:
            logger_name: Name for the logger instance
        """
        self.logger = logging.getLogger(logger_name)
        self.rate_limiter = RateLimitedLogger(max_logs_per_second=20)
        self.context_stack: List[Dict[str, Any]] = []

    def _format_log_entry(
        self,
        level: str,
        message: str,
        event_type: str,
        context: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        alert_level: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Format log entry for monitoring systems.

        Args:
            level: Log level (INFO, WARNING, ERROR, CRITICAL)
            message: Human-readable message
            event_type: Type of event for monitoring classification
            context: Additional context data
            metrics: Performance or business metrics
            alert_level: Alert classification (LOW, MEDIUM, HIGH, CRITICAL)

        Returns:
            Structured log entry dictionary
        """
        log_entry = {
            "timestamp": now_sao_paulo().isoformat(),
            "level": level,
            "message": message,
            "event_type": event_type,
            "service": "hormonia-backend",
            "version": "1.0.0",  # TODO: Get from config
        }

        # Add context from stack
        if self.context_stack:
            merged_context = {}
            for ctx in self.context_stack:
                merged_context.update(ctx)
            log_entry["context"] = merged_context

        # Add additional context
        if context:
            if "context" in log_entry:
                log_entry["context"].update(context)
            else:
                log_entry["context"] = context

        # Add metrics
        if metrics:
            log_entry["metrics"] = metrics

        # Add alert level for monitoring systems
        if alert_level:
            log_entry["alert_level"] = alert_level
            log_entry["requires_alert"] = True

        return log_entry

    def _should_log(self, event_type: str, level: str) -> bool:
        """
        Check if we should log based on rate limiting and level.

        Args:
            event_type: Type of event
            level: Log level

        Returns:
            True if should log, False if rate limited
        """
        # Always log CRITICAL events
        if level == "CRITICAL":
            return True

        # Rate limit other events
        log_key = f"{event_type}_{level}"
        return self.rate_limiter.should_log(log_key)

    def log_system_event(
        self,
        event_type: str,
        message: str,
        level: str = "INFO",
        context: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        alert_level: Optional[str] = None,
    ) -> None:
        """
        Log a system event with structured format.

        Args:
            event_type: Type of event (e.g., 'dependency_injection_error', 'role_enum_error')
            message: Human-readable message
            level: Log level
            context: Additional context data
            metrics: Performance or business metrics
            alert_level: Alert classification for monitoring
        """
        if not self._should_log(event_type, level):
            return

        log_entry = self._format_log_entry(
            level=level,
            message=message,
            event_type=event_type,
            context=context,
            metrics=metrics,
            alert_level=alert_level,
        )

        # Log as JSON for monitoring systems
        log_level = getattr(logging, level, logging.INFO)
        self.logger.log(log_level, json.dumps(log_entry))

    def log_error_pattern(
        self,
        error_type: str,
        error_message: str,
        count: int,
        context: Optional[Dict[str, Any]] = None,
        alert_level: str = "MEDIUM",
    ) -> None:
        """
        Log error pattern detection for monitoring.

        Args:
            error_type: Type of error pattern
            error_message: Error message
            count: Number of occurrences
            context: Additional context
            alert_level: Alert level for monitoring
        """
        self.log_system_event(
            event_type="error_pattern_detected",
            message=f"Error pattern detected: {error_type} ({count} occurrences)",
            level="WARNING" if count < 10 else "ERROR",
            context={
                "error_type": error_type,
                "error_message": error_message,
                "occurrence_count": count,
                **(context or {}),
            },
            metrics={
                "error_count": count,
                "error_rate": count / 3600,  # Assuming 1-hour window
            },
            alert_level=alert_level,
        )

    def log_performance_metric(
        self,
        metric_name: str,
        value: float,
        unit: str,
        context: Optional[Dict[str, Any]] = None,
        threshold_warning: Optional[float] = None,
        threshold_critical: Optional[float] = None,
    ) -> None:
        """
        Log performance metric with threshold checking.

        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Unit of measurement
            context: Additional context
            threshold_warning: Warning threshold
            threshold_critical: Critical threshold
        """
        # Determine alert level based on thresholds
        alert_level = None
        level = "INFO"

        if threshold_critical and value >= threshold_critical:
            alert_level = "CRITICAL"
            level = "CRITICAL"
        elif threshold_warning and value >= threshold_warning:
            alert_level = "HIGH"
            level = "WARNING"

        self.log_system_event(
            event_type="performance_metric",
            message=f"Performance metric: {metric_name} = {value} {unit}",
            level=level,
            context={"metric_name": metric_name, "unit": unit, **(context or {})},
            metrics={
                metric_name: value,
                "threshold_warning": threshold_warning,
                "threshold_critical": threshold_critical,
            },
            alert_level=alert_level,
        )

    def log_health_check(
        self,
        check_name: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
    ) -> None:
        """
        Log health check result.

        Args:
            check_name: Name of the health check
            status: Status (healthy, unhealthy, warning)
            details: Additional details
            duration_ms: Check duration in milliseconds
        """
        level = "INFO"
        alert_level = None

        if status == "unhealthy":
            level = "ERROR"
            alert_level = "HIGH"
        elif status == "warning":
            level = "WARNING"
            alert_level = "MEDIUM"

        metrics = {}
        if duration_ms is not None:
            metrics["duration_ms"] = duration_ms

        self.log_system_event(
            event_type="health_check",
            message=f"Health check '{check_name}': {status}",
            level=level,
            context={"check_name": check_name, "status": status, **(details or {})},
            metrics=metrics,
            alert_level=alert_level,
        )

    def log_critical_fix_status(
        self, fix_name: str, status: str, details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log critical fix status for monitoring.

        Args:
            fix_name: Name of the critical fix
            status: Status (working, broken, degraded)
            details: Additional details
        """
        level = "INFO"
        alert_level = None

        if status == "broken":
            level = "CRITICAL"
            alert_level = "CRITICAL"
        elif status == "degraded":
            level = "WARNING"
            alert_level = "HIGH"

        self.log_system_event(
            event_type="critical_fix_status",
            message=f"Critical fix '{fix_name}': {status}",
            level=level,
            context={"fix_name": fix_name, "status": status, **(details or {})},
            alert_level=alert_level,
        )

    @contextmanager
    def context(self, **context_data):
        """
        Context manager for adding context to all logs within the block.

        Args:
            **context_data: Context data to add

        Usage:
            with monitoring_logger.context(user_id="123", operation="login"):
                monitoring_logger.log_system_event("user_login", "User logged in")
        """
        self.context_stack.append(context_data)
        try:
            yield
        finally:
            self.context_stack.pop()

    def performance_timer(self, operation_name: str, **context_data):
        """
        Context manager for timing operations and logging performance.

        Args:
            operation_name: Name of the operation being timed
            **context_data: Additional context data

        Usage:
            with monitoring_logger.performance_timer("database_query", table="users"):
                # Database operation
                pass
        """

        class PerformanceTimer:
            def __init__(self, logger, operation_name, context_data):
                self.logger = logger
                self.operation_name = operation_name
                self.context_data = context_data
                self.start_time = None

            def __enter__(self):
                self.start_time = time.time()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                _ = exc_tb
                duration_ms = (time.time() - self.start_time) * 1000

                # Log performance metric
                self.logger.log_performance_metric(
                    metric_name=f"{self.operation_name}_duration_ms",
                    value=duration_ms,
                    unit="ms",
                    context={"operation": self.operation_name, **self.context_data},
                    threshold_warning=1000,  # 1 second
                    threshold_critical=5000,  # 5 seconds
                )

                # Log error if operation failed
                if exc_type is not None:
                    self.logger.log_system_event(
                        event_type="operation_failed",
                        message=f"Operation '{self.operation_name}' failed: {exc_val}",
                        level="ERROR",
                        context={
                            "operation": self.operation_name,
                            "duration_ms": duration_ms,
                            "error_type": exc_type.__name__,
                            **self.context_data,
                        },
                        alert_level="MEDIUM",
                    )

        return PerformanceTimer(self, operation_name, context_data)


def monitoring_decorator(
    event_type: str,
    log_args: bool = False,
    log_result: bool = False,
    alert_on_error: bool = True,
):
    """
    Decorator for automatic monitoring logging of function calls.

    Args:
        event_type: Type of event for monitoring
        log_args: Whether to log function arguments
        log_result: Whether to log function result
        alert_on_error: Whether to generate alerts on errors

    Usage:
        @monitoring_decorator("user_authentication", log_args=True)
        def authenticate_user(username, password):
            # Authentication logic
            pass
    """

    def _build_monitoring_context(func, args, kwargs):
        context = {"function": func.__name__, "module": func.__module__}
        if log_args:
            context["args"] = str(args)
            context["kwargs"] = {k: str(v) for k, v in kwargs.items()}
        return context

    def _log_success_event(monitoring_logger, func, context, result):
        if log_result:
            context["result"] = str(result)[:100]
        monitoring_logger.log_system_event(
            event_type=event_type,
            message=f"Function '{func.__name__}' completed successfully",
            level="DEBUG",
            context=context,
        )

    def _log_error_event(monitoring_logger, func, context, error):
        if not alert_on_error:
            return
        monitoring_logger.log_system_event(
            event_type=f"{event_type}_error",
            message=f"Function '{func.__name__}' failed: {str(error)}",
            level="ERROR",
            context={
                **context,
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
            alert_level="MEDIUM",
        )

    async def _run_async_call(func, monitoring_logger, context, *args, **kwargs):
        with monitoring_logger.performance_timer(func.__name__, **context):
            try:
                result = await func(*args, **kwargs)
                _log_success_event(monitoring_logger, func, context, result)
                return result
            except Exception as exc:
                _log_error_event(monitoring_logger, func, context, exc)
                raise

    def _run_sync_call(func, monitoring_logger, context, *args, **kwargs):
        with monitoring_logger.performance_timer(func.__name__, **context):
            try:
                result = func(*args, **kwargs)
                _log_success_event(monitoring_logger, func, context, result)
                return result
            except Exception as exc:
                _log_error_event(monitoring_logger, func, context, exc)
                raise

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            monitoring_logger = MonitoringLogger()
            context = _build_monitoring_context(func, args, kwargs)
            return await _run_async_call(
                func,
                monitoring_logger,
                context,
                *args,
                **kwargs,
            )

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            monitoring_logger = MonitoringLogger()
            context = _build_monitoring_context(func, args, kwargs)
            return _run_sync_call(
                func,
                monitoring_logger,
                context,
                *args,
                **kwargs,
            )

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Global monitoring logger instance
monitoring_logger = MonitoringLogger()


# Convenience functions
def log_critical_error(
    error_type: str, message: str, context: Optional[Dict[str, Any]] = None
):
    """Log critical error with immediate alert."""
    monitoring_logger.log_system_event(
        event_type=error_type,
        message=message,
        level="CRITICAL",
        context=context,
        alert_level="CRITICAL",
    )


def log_performance_warning(
    metric_name: str,
    value: float,
    threshold: float,
    context: Optional[Dict[str, Any]] = None,
):
    """Log performance warning."""
    monitoring_logger.log_performance_metric(
        metric_name=metric_name,
        value=value,
        unit="ms",
        context=context,
        threshold_warning=threshold,
    )


def log_health_status(
    check_name: str, is_healthy: bool, details: Optional[Dict[str, Any]] = None
):
    """Log health check status."""
    status = "healthy" if is_healthy else "unhealthy"
    monitoring_logger.log_health_check(check_name, status, details)
