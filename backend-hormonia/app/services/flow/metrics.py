"""Prometheus counters for flow observability signals."""

from __future__ import annotations

import logging

from prometheus_client import Counter

logger = logging.getLogger(__name__)

AI_PERSONALIZATION_FALLBACK_TOTAL = Counter(
    "ai_personalization_fallback_total",
    "AI personalization fallback count by reason",
    ["reason"],
)


def record_ai_fallback(*, reason: str) -> None:
    AI_PERSONALIZATION_FALLBACK_TOTAL.labels(reason=reason).inc()
    logger.info(
        "ai_personalization_fallback",
        extra={
            "reason": reason,
            "metric_type": "ai_fallback",
        },
    )
