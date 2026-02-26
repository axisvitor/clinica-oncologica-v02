"""Prometheus instrumentation helpers for saga orchestrator."""

import logging
import re

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Histogram, Gauge

    SAGA_STARTS_TOTAL = Counter(
        "saga_onboarding_starts_total",
        "Total number of saga starts",
        ["doctor_id"],
    )
    SAGA_COMPLETIONS_TOTAL = Counter(
        "saga_onboarding_completions_total",
        "Total number of saga completions",
        ["doctor_id"],
    )
    SAGA_FAILURES_TOTAL = Counter(
        "saga_onboarding_failures_total",
        "Total number of saga failures",
        ["doctor_id", "step", "error_type"],
    )
    SAGA_DURATION_SECONDS = Histogram(
        "saga_onboarding_duration_seconds",
        "Duration of saga execution in seconds",
        ["status"],
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
    )
    SAGA_LOCK_ACQUISITION_SECONDS = Histogram(
        "saga_lock_acquisition_seconds",
        "Time to acquire distributed lock",
        ["lock_type"],
        buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
    )
    SAGA_COMPENSATIONS_TOTAL = Counter(
        "saga_compensations_total",
        "Total number of compensation attempts",
        ["step", "result"],
    )
    SAGA_TRANSACTION_DURATION_SECONDS = Histogram(
        "saga_transaction_duration_seconds",
        "Duration of saga transaction (excluding async tasks)",
        ["step"],
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
    )
    SAGA_PHONE_NORMALIZATION_TOTAL = Counter(
        "saga_phone_normalization_total",
        "Total phone normalizations in saga",
        ["format_detected"],
    )
    SAGA_STEP_DURATION_SECONDS = Histogram(
        "saga_step_duration_seconds",
        "Duration of individual saga steps",
        ["step_name"],
        buckets=[0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    SAGA_STARTS_TOTAL = None
    SAGA_COMPLETIONS_TOTAL = None
    SAGA_FAILURES_TOTAL = None
    SAGA_DURATION_SECONDS = None
    SAGA_LOCK_ACQUISITION_SECONDS = None
    SAGA_COMPENSATIONS_TOTAL = None
    SAGA_TRANSACTION_DURATION_SECONDS = None
    SAGA_PHONE_NORMALIZATION_TOTAL = None
    SAGA_STEP_DURATION_SECONDS = None
    logger.warning("prometheus_client not available, saga metrics disabled")


def _detect_phone_format(phone: str) -> str:
    if not phone:
        return "other"
    if phone.startswith("+"):
        return "e164"
    digits = re.sub(r"\D", "", phone)
    if len(digits) in (10, 11, 12, 13):
        return "brazilian"
    return "other"


__all__ = [
    "SAGA_STARTS_TOTAL",
    "SAGA_COMPLETIONS_TOTAL",
    "SAGA_FAILURES_TOTAL",
    "SAGA_DURATION_SECONDS",
    "SAGA_LOCK_ACQUISITION_SECONDS",
    "SAGA_COMPENSATIONS_TOTAL",
    "SAGA_TRANSACTION_DURATION_SECONDS",
    "SAGA_PHONE_NORMALIZATION_TOTAL",
    "SAGA_STEP_DURATION_SECONDS",
    "METRICS_AVAILABLE",
    "_detect_phone_format",
]
