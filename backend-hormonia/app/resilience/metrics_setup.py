"""Shared metrics setup helpers for resilience integrations."""

from __future__ import annotations

from typing import Any

from .metrics import metrics_collector


def initialize_metrics_collection(config: Any, logger: Any) -> None:
    """Configure resilience metrics collector from integration config."""
    if not config or not getattr(config, "metrics_enabled", False):
        return

    metrics_collector.retention_period = config.metrics_retention_hours * 3600
    metrics_collector.collection_interval = config.metrics_collection_interval
    logger.info("Metrics collection initialized")
