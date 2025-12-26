"""
Flow Analytics - Analytics and monitoring for Flow Services (QW-021).

This module provides analytics, metrics collection, and monitoring capabilities
for the consolidated flow system.

Exports:
    - FlowAnalytics: Main analytics service
    - FlowMetricsCollector: Metrics collection
    - FlowEventBroadcaster: Event broadcasting
    - FlowMonitor: Flow health monitoring
    - FlowHealthMetrics: Health metrics data class
    - HealthStatus: Health status enumeration
    - get_flow_analytics: Singleton getter for FlowAnalytics
    - reset_flow_analytics: Singleton reset for testing
"""

from __future__ import annotations

# Standard library imports
from typing import Optional

# Local application imports
from .analytics import FlowAnalytics
from .event_broadcaster import FlowEventBroadcaster
from .metrics_collector import FlowMetricsCollector
from .monitor import FlowHealthMetrics, FlowMonitor, HealthStatus

# Singleton instance
_flow_analytics_instance: Optional[FlowAnalytics] = None


def get_flow_analytics() -> FlowAnalytics:
    """
    Get or create the global FlowAnalytics singleton instance.

    Returns:
        Global FlowAnalytics instance.
    """
    global _flow_analytics_instance
    if _flow_analytics_instance is None:
        _flow_analytics_instance = FlowAnalytics()
    return _flow_analytics_instance


def reset_flow_analytics() -> None:
    """
    Reset the global FlowAnalytics instance.

    Useful for testing and cleanup scenarios.
    """
    global _flow_analytics_instance
    if _flow_analytics_instance is not None:
        _flow_analytics_instance.shutdown()
    _flow_analytics_instance = None


__all__ = [
    "FlowAnalytics",
    "FlowEventBroadcaster",
    "FlowHealthMetrics",
    "FlowMetricsCollector",
    "FlowMonitor",
    "HealthStatus",
    "get_flow_analytics",
    "reset_flow_analytics",
]
