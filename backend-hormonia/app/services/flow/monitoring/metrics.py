"""
Flow Metrics - Re-export metrics collector.

This module provides backwards compatibility by re-exporting
the FlowMetricsCollector from the analytics module.
"""

from __future__ import annotations

# Local application imports
from ..analytics.metrics_collector import FlowMetricsCollector


__all__ = ["FlowMetricsCollector"]
