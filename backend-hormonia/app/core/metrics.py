"""
Prometheus Metrics Integration for Clínica Hormonia
Provides application-level metrics for monitoring
"""

from prometheus_client import Counter, Histogram, Gauge, Info
from functools import wraps
import time
from typing import Callable

# Application Metrics
app_requests_total = Counter(
    "app_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status"],
)

app_request_duration_seconds = Histogram(
    "app_request_duration_seconds",
    "HTTP request latency in seconds",
    ["endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)

app_active_users_total = Gauge(
    "app_active_users_total", "Number of currently active users"
)

app_patient_onboarding_total = Counter(
    "app_patient_onboarding_total", "Total patient onboarding attempts", ["status"]
)

app_quiz_completion_rate = Gauge(
    "app_quiz_completion_rate", "Quiz completion rate (0-1)"
)

app_upload_bytes_total = Counter(
    "app_upload_bytes_total", "Total bytes uploaded", ["user_tier"]
)

# Security Metrics
app_security_scan_total = Counter(
    "app_security_scan_total", "Total security scans performed", ["scanner", "result"]
)

app_virus_detected_total = Counter(
    "app_virus_detected_total", "Total viruses detected in uploads"
)

app_mime_validation_failures_total = Counter(
    "app_mime_validation_failures_total", "Total MIME type validation failures"
)

app_blocked_extensions_total = Counter(
    "app_blocked_extensions_total", "Files blocked by extension", ["extension"]
)

# Performance Metrics
app_db_query_duration_seconds = Histogram(
    "app_db_query_duration_seconds",
    "Database query duration in seconds",
    ["query"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
)

app_redis_operations_total = Counter(
    "app_redis_operations_total", "Total Redis operations", ["operation"]
)

app_celery_task_duration_seconds = Histogram(
    "app_celery_task_duration_seconds",
    "Celery task duration in seconds",
    ["task"],
    buckets=[1, 5, 10, 30, 60, 300, 600],
)

app_celery_queue_size = Gauge(
    "app_celery_queue_size", "Number of tasks in Celery queue", ["queue"]
)

# Business Metrics
app_revenue_total = Counter("app_revenue_total", "Total revenue in USD", ["tier"])

app_quota_usage_bytes = Gauge(
    "app_quota_usage_bytes", "Current quota usage in bytes", ["user", "tier"]
)

app_quota_limit_bytes = Gauge("app_quota_limit_bytes", "Quota limit in bytes", ["tier"])

app_notifications_sent_total = Counter(
    "app_notifications_sent_total", "Total notifications sent", ["channel"]
)

app_sla_compliance_ratio = Gauge(
    "app_sla_compliance_ratio", "SLA compliance ratio (0-1)"
)

app_quiz_completion_total = Counter(
    "app_quiz_completion_total", "Total quiz completions", ["status"]
)

app_whatsapp_messages_total = Counter(
    "app_whatsapp_messages_total", "Total WhatsApp messages sent", ["status"]
)

app_patient_risk_alerts_total = Counter(
    "app_patient_risk_alerts_total", "Patient risk alerts triggered", ["risk_level"]
)

app_api_rate_limit_hits_total = Counter(
    "app_api_rate_limit_hits_total",
    "API rate limit violations",
    ["endpoint", "user_tier"],
)

# Circuit Breaker Metrics (HIGH-006)
circuit_breaker_state_gauge = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["service"],
)

circuit_breaker_failures_total = Counter(
    "circuit_breaker_failures_total", "Total circuit breaker failures", ["service"]
)

circuit_breaker_successes_total = Counter(
    "circuit_breaker_successes_total", "Total circuit breaker successes", ["service"]
)

circuit_breaker_fallback_total = Counter(
    "circuit_breaker_fallback_total",
    "Total circuit breaker fallback activations",
    ["service"],
)

circuit_breaker_call_duration_seconds = Histogram(
    "circuit_breaker_call_duration_seconds",
    "Circuit breaker protected call duration in seconds",
    ["service", "status"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

circuit_breaker_open_count = Counter(
    "circuit_breaker_open_count", "Number of times circuit breaker opened", ["service"]
)

circuit_breaker_half_open_count = Counter(
    "circuit_breaker_half_open_count",
    "Number of times circuit breaker entered half-open state",
    ["service"],
)

# Application Info
app_info = Info("app_info", "Application information")
app_info.info(
    {"version": "2.0.0", "environment": "production", "application": "clinica-hormonia"}
)


# Decorators for automatic instrumentation
def track_request_metrics(endpoint: str):
    """Decorator to track HTTP request metrics"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "200"
            method = "GET"

            try:
                result = await func(*args, **kwargs)

                # Try to extract status from result
                if hasattr(result, "status_code"):
                    status = str(result.status_code)

                return result
            except Exception:
                status = "500"
                raise
            finally:
                duration = time.time() - start_time

                # Record metrics
                app_requests_total.labels(
                    method=method, endpoint=endpoint, status=status
                ).inc()

                app_request_duration_seconds.labels(endpoint=endpoint).observe(duration)

        return wrapper

    return decorator


def track_db_query_metrics(query_name: str):
    """Decorator to track database query metrics"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.time() - start_time
                app_db_query_duration_seconds.labels(query=query_name).observe(duration)

        return wrapper

    return decorator


def track_celery_task_metrics(task_name: str):
    """Decorator to track Celery task metrics"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                return func(*args, **kwargs)
            finally:
                duration = time.time() - start_time
                app_celery_task_duration_seconds.labels(task=task_name).observe(
                    duration
                )

        return wrapper

    return decorator


# Helper functions for common operations
def record_patient_onboarding(status: str):
    """Record patient onboarding attempt"""
    app_patient_onboarding_total.labels(status=status).inc()


def record_quiz_completion(status: str):
    """Record quiz completion"""
    app_quiz_completion_total.labels(status=status).inc()


def record_file_upload(bytes_uploaded: int, user_tier: str):
    """Record file upload"""
    app_upload_bytes_total.labels(user_tier=user_tier).inc(bytes_uploaded)


def record_security_scan(scanner: str, result: str):
    """Record security scan"""
    app_security_scan_total.labels(scanner=scanner, result=result).inc()


def record_virus_detection():
    """Record virus detection"""
    app_virus_detected_total.inc()


def record_mime_validation_failure():
    """Record MIME validation failure"""
    app_mime_validation_failures_total.inc()


def record_blocked_extension(extension: str):
    """Record blocked file extension"""
    app_blocked_extensions_total.labels(extension=extension).inc()


def record_redis_operation(operation: str):
    """Record Redis operation"""
    app_redis_operations_total.labels(operation=operation).inc()


def record_notification_sent(channel: str):
    """Record notification sent"""
    app_notifications_sent_total.labels(channel=channel).inc()


def record_whatsapp_message(status: str):
    """Record WhatsApp message"""
    app_whatsapp_messages_total.labels(status=status).inc()


def record_patient_risk_alert(risk_level: str):
    """Record patient risk alert"""
    app_patient_risk_alerts_total.labels(risk_level=risk_level).inc()


def record_rate_limit_hit(endpoint: str, user_tier: str):
    """Record API rate limit violation"""
    app_api_rate_limit_hits_total.labels(endpoint=endpoint, user_tier=user_tier).inc()


def update_quota_usage(user: str, tier: str, usage_bytes: int):
    """Update user quota usage"""
    app_quota_usage_bytes.labels(user=user, tier=tier).set(usage_bytes)


def update_active_users(count: int):
    """Update active users count"""
    app_active_users_total.set(count)


def update_quiz_completion_rate(rate: float):
    """Update quiz completion rate"""
    app_quiz_completion_rate.set(rate)


def update_sla_compliance(ratio: float):
    """Update SLA compliance ratio"""
    app_sla_compliance_ratio.set(ratio)


def update_celery_queue_size(queue: str, size: int):
    """Update Celery queue size"""
    app_celery_queue_size.labels(queue=queue).set(size)
