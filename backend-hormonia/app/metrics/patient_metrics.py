"""Prometheus metrics for patient create idempotency and performance."""

from prometheus_client import Counter, Histogram

patient_create_idempotency_hits = Counter(
    "patient_create_idempotency_hits",
    "Idempotent requests detected",
    ["source"],
)

patient_create_idempotency_misses = Counter(
    "patient_create_idempotency_misses",
    "New patient creations",
)

patient_create_duration = Histogram(
    "patient_create_duration_seconds",
    "Patient creation duration",
    ["idempotent"],
)
