"""
Prometheus Exporters
Export metrics in Prometheus format for monitoring.
"""

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from fastapi import APIRouter, Response
from typing import Dict, Any
import logging
import time

logger = logging.getLogger(__name__)

# Create custom registry
registry = CollectorRegistry()

# System metrics
cpu_usage = Gauge("system_cpu_usage_percent", "CPU usage percentage", registry=registry)

memory_usage = Gauge(
    "system_memory_usage_bytes", "Memory usage in bytes", registry=registry
)

memory_percent = Gauge(
    "system_memory_usage_percent", "Memory usage percentage", registry=registry
)

disk_usage = Gauge("system_disk_usage_bytes", "Disk usage in bytes", registry=registry)

disk_percent = Gauge(
    "system_disk_usage_percent", "Disk usage percentage", registry=registry
)

# Network metrics
network_bytes_sent = Counter(
    "system_network_bytes_sent_total", "Total bytes sent", registry=registry
)

network_bytes_recv = Counter(
    "system_network_bytes_recv_total", "Total bytes received", registry=registry
)

# API metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=registry,
)

http_request_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
    registry=registry,
)

http_response_size = Summary(
    "http_response_size_bytes",
    "HTTP response size",
    ["method", "endpoint"],
    registry=registry,
)

# Database metrics
db_connections_active = Gauge(
    "database_connections_active", "Active database connections", registry=registry
)

db_query_duration = Histogram(
    "database_query_duration_seconds",
    "Database query duration",
    ["operation"],
    registry=registry,
)

db_errors_total = Counter(
    "database_errors_total", "Total database errors", ["error_type"], registry=registry
)

# Cache metrics
cache_hits_total = Counter(
    "cache_hits_total", "Total cache hits", ["cache_type"], registry=registry
)

cache_misses_total = Counter(
    "cache_misses_total", "Total cache misses", ["cache_type"], registry=registry
)

cache_size = Gauge(
    "cache_size_bytes", "Cache size in bytes", ["cache_type"], registry=registry
)

# Application metrics
active_users = Gauge("app_active_users", "Number of active users", registry=registry)

total_patients = Gauge(
    "app_total_patients", "Total number of patients", registry=registry
)

quiz_sessions_active = Gauge(
    "app_quiz_sessions_active", "Active quiz sessions", registry=registry
)

whatsapp_messages_sent = Counter(
    "whatsapp_messages_sent_total",
    "Total WhatsApp messages sent",
    ["message_type"],
    registry=registry,
)

whatsapp_messages_received = Counter(
    "whatsapp_messages_received_total",
    "Total WhatsApp messages received",
    ["message_type"],
    registry=registry,
)

# Health check metrics
health_check_status = Gauge(
    "health_check_status",
    "Health check status (1=healthy, 0=unhealthy)",
    ["service"],
    registry=registry,
)

health_check_duration = Histogram(
    "health_check_duration_seconds",
    "Health check duration",
    ["service"],
    registry=registry,
)

# Alert metrics
alerts_active = Gauge(
    "alerts_active_total", "Total active alerts", ["severity"], registry=registry
)

alerts_triggered = Counter(
    "alerts_triggered_total",
    "Total alerts triggered",
    ["severity", "source"],
    registry=registry,
)

# Quiz metrics
quiz_link_generated = Counter(
    "quiz_link_generated_total",
    "Total quiz links generated",
    ["delivery_method", "quiz_type"],
    registry=registry,
)

quiz_access_success = Counter(
    "quiz_access_success_total",
    "Total successful quiz accesses",
    ["quiz_type"],
    registry=registry,
)

quiz_access_failure = Counter(
    "quiz_access_failure_total",
    "Total failed quiz access attempts",
    ["reason"],
    registry=registry,
)

quiz_submit_success = Counter(
    "quiz_submit_success_total",
    "Total successful quiz submissions",
    ["quiz_type", "is_encrypted"],
    registry=registry,
)

quiz_submit_failure = Counter(
    "quiz_submit_failure_total",
    "Total failed quiz submissions",
    ["reason"],
    registry=registry,
)

token_rotated = Counter(
    "token_rotated_total", "Total token rotations", ["quiz_type"], registry=registry
)

fallback_activated = Counter(
    "fallback_activated_total",
    "Total fallback activations",
    ["reason", "fallback_type"],
    registry=registry,
)

quiz_completion_rate = Gauge(
    "quiz_completion_rate_percent",
    "Quiz completion rate percentage",
    ["quiz_type", "month"],
    registry=registry,
)

token_expiry_rate = Gauge(
    "token_expiry_rate_percent",
    "Token expiry rate percentage",
    ["quiz_type", "month"],
    registry=registry,
)

fallback_activation_frequency = Gauge(
    "fallback_activation_frequency_percent",
    "Fallback activation frequency percentage",
    ["reason", "month"],
    registry=registry,
)


class MetricsExporter:
    """Prometheus metrics exporter"""

    @staticmethod
    async def update_system_metrics(metrics: Dict[str, Any]):
        """Update system metrics"""
        try:
            cpu_usage.set(metrics.get("cpu_percent", 0))
            memory_usage.set(metrics.get("memory_used", 0))
            memory_percent.set(metrics.get("memory_percent", 0))
            disk_usage.set(metrics.get("disk_used", 0))
            disk_percent.set(metrics.get("disk_percent", 0))

            # Network metrics are counters, so we set the total
            network_bytes_sent._value.set(metrics.get("network_bytes_sent", 0))
            network_bytes_recv._value.set(metrics.get("network_bytes_recv", 0))

        except Exception as e:
            logger.error(f"Error updating system metrics: {e}")

    @staticmethod
    def record_http_request(method: str, endpoint: str, status: int, duration: float):
        """Record HTTP request metrics"""
        try:
            http_requests_total.labels(
                method=method, endpoint=endpoint, status=status
            ).inc()
            http_request_duration.labels(method=method, endpoint=endpoint).observe(
                duration
            )
        except Exception as e:
            logger.error(f"Error recording HTTP metrics: {e}")

    @staticmethod
    def record_response_size(method: str, endpoint: str, size: int):
        """Record HTTP response size"""
        try:
            http_response_size.labels(method=method, endpoint=endpoint).observe(size)
        except Exception as e:
            logger.error(f"Error recording response size: {e}")

    @staticmethod
    def update_database_metrics(active_connections: int):
        """Update database metrics"""
        try:
            db_connections_active.set(active_connections)
        except Exception as e:
            logger.error(f"Error updating database metrics: {e}")

    @staticmethod
    def record_db_query(operation: str, duration: float):
        """Record database query metrics"""
        try:
            db_query_duration.labels(operation=operation).observe(duration)
        except Exception as e:
            logger.error(f"Error recording DB query: {e}")

    @staticmethod
    def record_db_error(error_type: str):
        """Record database error"""
        try:
            db_errors_total.labels(error_type=error_type).inc()
        except Exception as e:
            logger.error(f"Error recording DB error: {e}")

    @staticmethod
    def record_cache_hit(cache_type: str):
        """Record cache hit"""
        try:
            cache_hits_total.labels(cache_type=cache_type).inc()
        except Exception as e:
            logger.error(f"Error recording cache hit: {e}")

    @staticmethod
    def record_cache_miss(cache_type: str):
        """Record cache miss"""
        try:
            cache_misses_total.labels(cache_type=cache_type).inc()
        except Exception as e:
            logger.error(f"Error recording cache miss: {e}")

    @staticmethod
    def update_cache_size(cache_type: str, size: int):
        """Update cache size"""
        try:
            cache_size.labels(cache_type=cache_type).set(size)
        except Exception as e:
            logger.error(f"Error updating cache size: {e}")

    @staticmethod
    def update_app_metrics(
        active_users_count: int = 0,
        total_patients_count: int = 0,
        quiz_sessions_count: int = 0,
    ):
        """Update application metrics"""
        try:
            active_users.set(active_users_count)
            total_patients.set(total_patients_count)
            quiz_sessions_active.set(quiz_sessions_count)
        except Exception as e:
            logger.error(f"Error updating app metrics: {e}")

    @staticmethod
    def record_whatsapp_message(direction: str, message_type: str):
        """Record WhatsApp message"""
        try:
            if direction == "sent":
                whatsapp_messages_sent.labels(message_type=message_type).inc()
            elif direction == "received":
                whatsapp_messages_received.labels(message_type=message_type).inc()
        except Exception as e:
            logger.error(f"Error recording WhatsApp message: {e}")

    @staticmethod
    def update_health_status(service: str, is_healthy: bool):
        """Update health check status"""
        try:
            health_check_status.labels(service=service).set(1 if is_healthy else 0)
        except Exception as e:
            logger.error(f"Error updating health status: {e}")

    @staticmethod
    def record_health_check(service: str, duration: float):
        """Record health check duration"""
        try:
            health_check_duration.labels(service=service).observe(duration)
        except Exception as e:
            logger.error(f"Error recording health check: {e}")

    @staticmethod
    def update_alerts(severity: str, count: int):
        """Update alert metrics"""
        try:
            alerts_active.labels(severity=severity).set(count)
        except Exception as e:
            logger.error(f"Error updating alerts: {e}")

    @staticmethod
    def record_alert_triggered(severity: str, source: str):
        """Record alert triggered"""
        try:
            alerts_triggered.labels(severity=severity, source=source).inc()
        except Exception as e:
            logger.error(f"Error recording alert: {e}")

    # Quiz metrics methods
    @staticmethod
    def record_quiz_link_generated(delivery_method: str, quiz_type: str = "monthly"):
        """Record quiz link generation"""
        try:
            quiz_link_generated.labels(
                delivery_method=delivery_method, quiz_type=quiz_type
            ).inc()
        except Exception as e:
            logger.error(f"Error recording quiz link generation: {e}")

    @staticmethod
    def record_quiz_access_success(quiz_type: str = "monthly"):
        """Record successful quiz access"""
        try:
            quiz_access_success.labels(quiz_type=quiz_type).inc()
        except Exception as e:
            logger.error(f"Error recording quiz access success: {e}")

    @staticmethod
    def record_quiz_access_failure(reason: str):
        """Record failed quiz access"""
        try:
            quiz_access_failure.labels(reason=reason).inc()
        except Exception as e:
            logger.error(f"Error recording quiz access failure: {e}")

    @staticmethod
    def record_quiz_submit_success(
        quiz_type: str = "monthly", is_encrypted: bool = False
    ):
        """Record successful quiz submission"""
        try:
            quiz_submit_success.labels(
                quiz_type=quiz_type, is_encrypted=str(is_encrypted)
            ).inc()
        except Exception as e:
            logger.error(f"Error recording quiz submit success: {e}")

    @staticmethod
    def record_quiz_submit_failure(reason: str):
        """Record failed quiz submission"""
        try:
            quiz_submit_failure.labels(reason=reason).inc()
        except Exception as e:
            logger.error(f"Error recording quiz submit failure: {e}")

    @staticmethod
    def record_token_rotated(quiz_type: str = "monthly"):
        """Record token rotation"""
        try:
            token_rotated.labels(quiz_type=quiz_type).inc()
        except Exception as e:
            logger.error(f"Error recording token rotation: {e}")

    @staticmethod
    def record_fallback_activated(reason: str, fallback_type: str = "whatsapp"):
        """Record fallback activation"""
        try:
            fallback_activated.labels(reason=reason, fallback_type=fallback_type).inc()
        except Exception as e:
            logger.error(f"Error recording fallback activation: {e}")

    @staticmethod
    def update_quiz_completion_rate(
        rate: float, quiz_type: str = "monthly", month: str = None
    ):
        """Update quiz completion rate"""
        try:
            if month is None:
                from datetime import datetime

                month = datetime.now().strftime("%Y-%m")
            quiz_completion_rate.labels(quiz_type=quiz_type, month=month).set(rate)
        except Exception as e:
            logger.error(f"Error updating quiz completion rate: {e}")

    @staticmethod
    def update_token_expiry_rate(
        rate: float, quiz_type: str = "monthly", month: str = None
    ):
        """Update token expiry rate"""
        try:
            if month is None:
                from datetime import datetime

                month = datetime.now().strftime("%Y-%m")
            token_expiry_rate.labels(quiz_type=quiz_type, month=month).set(rate)
        except Exception as e:
            logger.error(f"Error updating token expiry rate: {e}")

    @staticmethod
    def update_fallback_activation_frequency(
        frequency: float, reason: str, month: str = None
    ):
        """Update fallback activation frequency"""
        try:
            if month is None:
                from datetime import datetime

                month = datetime.now().strftime("%Y-%m")
            fallback_activation_frequency.labels(reason=reason, month=month).set(
                frequency
            )
        except Exception as e:
            logger.error(f"Error updating fallback activation frequency: {e}")


# FastAPI router for metrics endpoint
router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
async def metrics():
    """
    Prometheus metrics endpoint
    Returns metrics in Prometheus exposition format
    """
    try:
        metrics_output = generate_latest(registry)
        return Response(content=metrics_output, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        return Response(
            content=f"# Error generating metrics: {e}\n",
            media_type=CONTENT_TYPE_LATEST,
            status_code=500,
        )


# Middleware for automatic HTTP metrics collection
class PrometheusMiddleware:
    """Middleware to automatically collect HTTP metrics"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        method = scope["method"]
        path = scope["path"]

        # Skip metrics endpoint itself
        if path == "/metrics":
            await self.app(scope, receive, send)
            return

        status_code = 200

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.time() - start_time
            MetricsExporter.record_http_request(method, path, status_code, duration)


# Global exporter instance
metrics_exporter = MetricsExporter()
