"""OBS-02 Prometheus metrics and structured logging for ADK invocations."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Iterator

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

ADK_INVOCATION_DURATION_SECONDS = Histogram(
    "adk_invocation_duration_seconds",
    "ADK invocation latency in seconds",
    ["tool_name", "status"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

ADK_INVOCATIONS_TOTAL = Counter(
    "adk_invocations_total",
    "Total ADK invocations by tool and status",
    ["tool_name", "status"],
)

ADK_INVOCATIONS_IN_FLIGHT = Gauge(
    "adk_invocations_in_flight",
    "Current number of in-flight ADK invocations by tool",
    ["tool_name"],
)


def record_adk_invocation(
    *,
    tool_name: str,
    status: str,
    duration_seconds: float,
    invocation_id: str | None = None,
    session_id: str | None = None,
) -> None:
    ADK_INVOCATION_DURATION_SECONDS.labels(
        tool_name=tool_name,
        status=status,
    ).observe(duration_seconds)
    ADK_INVOCATIONS_TOTAL.labels(
        tool_name=tool_name,
        status=status,
    ).inc()

    logger.info(
        "ADK invocation completed",
        extra={
            "adk_tool_name": tool_name,
            "adk_status": status,
            "adk_duration_ms": round(duration_seconds * 1000, 2),
            "adk_invocation_id": invocation_id,
            "adk_session_id": session_id,
            "metric_type": "adk_invocation",
        },
    )


@contextmanager
def track_adk_invocation(tool_name: str) -> Iterator[dict[str, float]]:
    ADK_INVOCATIONS_IN_FLIGHT.labels(tool_name=tool_name).inc()
    started_at = time.monotonic()
    try:
        yield {"start": started_at}
    finally:
        ADK_INVOCATIONS_IN_FLIGHT.labels(tool_name=tool_name).dec()
