"""
Prometheus metrics for monitoring and observability.

Provides comprehensive metrics for security, performance, and business logic.
"""

import time
from contextlib import contextmanager
from typing import Generator, Optional
from prometheus_client import Counter, Histogram, Gauge

# ============================================================================
# SECURITY METRICS
# ============================================================================

failed_auth_total = Counter(
    "auth_failed_total", "Total failed authentication attempts", ["method", "reason"]
)

unauthorized_access_total = Counter(
    "unauthorized_access_total",
    "Total unauthorized access attempts",
    ["endpoint", "role", "required_role"],
)

rate_limit_hits_total = Counter(
    "rate_limit_hits_total", "Total rate limit hits", ["endpoint", "tier"]
)

webhook_signature_failures_total = Counter(
    "webhook_signature_failures_total",
    "Total webhook signature validation failures",
    ["source"],
)

sql_injection_attempts_total = Counter(
    "sql_injection_attempts_total",
    "Total SQL injection attempts detected",
    ["endpoint", "parameter"],
)

csrf_failures_total = Counter(
    "csrf_failures_total", "Total CSRF validation failures", ["endpoint"]
)

# ============================================================================
# PERFORMANCE METRICS
# ============================================================================

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint", "status_code"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.0, 5.0, 10.0],
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation", "table"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

cache_hit_rate = Gauge("cache_hit_rate", "Cache hit rate percentage", ["cache_type"])

cache_miss_rate = Gauge("cache_miss_rate", "Cache miss rate percentage", ["cache_type"])

n1_query_detected_total = Counter(
    "n1_query_detected_total",
    "Total N+1 query patterns detected",
    ["endpoint", "model"],
)

# ============================================================================
# BUSINESS METRICS
# ============================================================================

saga_total = Counter("saga_total", "Total saga executions", ["saga_type", "status"])

saga_duration_seconds = Histogram(
    "saga_duration_seconds",
    "Saga execution duration in seconds",
    ["saga_type", "status"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

saga_compensation_total = Counter(
    "saga_compensation_total",
    "Total saga compensations executed",
    ["saga_type", "reason"],
)

patient_created_total = Counter(
    "patient_created_total", "Total patients created", ["source"]
)

patient_updated_total = Counter(
    "patient_updated_total", "Total patients updated", ["field"]
)

webhook_processed_total = Counter(
    "webhook_processed_total",
    "Total webhooks processed",
    ["source", "event_type", "status"],
)

quiz_session_total = Counter("quiz_session_total", "Total quiz sessions", ["status"])

quiz_response_total = Counter(
    "quiz_response_total", "Total quiz responses", ["question_type"]
)

# ============================================================================
# MEDIUM-009: WEBHOOK RETRY METRICS
# ============================================================================

webhook_retry_attempts = Counter(
    "webhook_retry_attempts_total", "Total webhook retry attempts", ["attempt_number"]
)

webhook_retry_success = Counter(
    "webhook_retry_success_total", "Successful webhook retries", ["attempt_number"]
)

webhook_retry_failures = Counter(
    "webhook_retry_failures_total",
    "Failed webhook retry attempts",
    ["attempt_number", "error_type"],
)

webhook_dlq_enqueued = Counter(
    "webhook_dlq_enqueued_total", "Webhooks sent to Dead Letter Queue", ["error_type"]
)

webhook_processing_duration = Histogram(
    "webhook_processing_duration_seconds",
    "Webhook processing duration including retries",
    ["event_type", "final_status"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

webhook_retry_delay_seconds = Histogram(
    "webhook_retry_delay_seconds",
    "Delay between webhook retry attempts",
    ["attempt_number"],
    buckets=[1, 2, 4, 8, 16, 32, 64],
)

# ============================================================================
# MEDIUM-008: CACHE TTL METRICS
# ============================================================================

cache_hits_total = Counter("cache_hits_total", "Total cache hits", ["cache_type"])

cache_misses_total = Counter("cache_misses_total", "Total cache misses", ["cache_type"])

cache_ttl_seconds = Gauge(
    "cache_ttl_seconds", "Configured TTL for cache type", ["cache_type"]
)

# ============================================================================
# MEDIUM-015: PAGINATION METRICS
# ============================================================================

pagination_requests_total = Counter(
    "pagination_requests_total",
    "Total pagination requests",
    ["model", "pagination_type"],
)

pagination_query_duration_seconds = Histogram(
    "pagination_query_duration_seconds",
    "Pagination query duration",
    ["model", "pagination_type"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

pagination_page_size = Histogram(
    "pagination_page_size",
    "Pagination page sizes requested",
    ["model"],
    buckets=[10, 20, 50, 100, 200],
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


@contextmanager
def track_request_duration(
    method: str, endpoint: str, status_code: Optional[int] = None
) -> Generator[None, None, None]:
    """
    Context manager to track HTTP request duration.

    Usage:
        with track_request_duration("GET", "/api/v2/patients", 200):
            # Your request handler code
            pass
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        status = str(status_code) if status_code else "unknown"
        http_request_duration_seconds.labels(
            method=method, endpoint=endpoint, status_code=status
        ).observe(duration)


@contextmanager
def track_db_query(operation: str, table: str) -> Generator[None, None, None]:
    """
    Context manager to track database query duration.

    Usage:
        with track_db_query("SELECT", "patients"):
            # Your database query code
            result = session.query(Patient).all()
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        db_query_duration_seconds.labels(operation=operation, table=table).observe(
            duration
        )


@contextmanager
def track_saga_execution(
    saga_type: str, status: str = "success"
) -> Generator[None, None, None]:
    """
    Context manager to track saga execution.

    Usage:
        with track_saga_execution("patient_onboarding", "success"):
            # Your saga code
            await saga.execute()
    """
    start_time = time.time()
    final_status = status

    try:
        yield
    except Exception:
        final_status = "failed"
        raise
    finally:
        duration = time.time() - start_time
        saga_total.labels(saga_type=saga_type, status=final_status).inc()
        saga_duration_seconds.labels(saga_type=saga_type, status=final_status).observe(
            duration
        )


def track_cache_access(cache_type: str, hits: int, misses: int) -> None:
    """
    Track cache hit/miss rates.

    Usage:
        track_cache_access("redis", hits=95, misses=5)
    """
    total = hits + misses
    if total > 0:
        hit_rate = (hits / total) * 100
        miss_rate = (misses / total) * 100

        cache_hit_rate.labels(cache_type=cache_type).set(hit_rate)
        cache_miss_rate.labels(cache_type=cache_type).set(miss_rate)
