from typing import Any
"""
Flow Analytics - Analytics and monitoring for Flow Services (QW-021).

This module provides analytics, metrics collection, and monitoring capabilities
for the consolidated flow system.

Exports:
    - FlowAnalytics: Main analytics service
    - FlowMetricsCollector: Metrics collection
    - FlowEventBroadcaster: Event broadcasting
    - FlowMonitor: Flow health monitoring
    - get_flow_analytics: Singleton getter for FlowAnalytics
"""

from .analytics import FlowAnalytics
from .metrics_collector import FlowMetricsCollector
from .event_broadcaster import FlowEventBroadcaster
from .monitor import FlowMonitor

# Singleton instance
_flow_analytics_instance = None


def get_flow_analytics() -> FlowAnalytics:
    """
    Get or create the global FlowAnalytics singleton instance.

    Returns:
        FlowAnalytics: The singleton instance
    """
    global _flow_analytics_instance
    if _flow_analytics_instance is None:
        _flow_analytics_instance = FlowAnalytics()
    return _flow_analytics_instance


def reset_flow_analytics():
    """Reset the global FlowAnalytics instance (for testing)."""
    global _flow_analytics_instance
    _flow_analytics_instance = None


__all__ = [
    "FlowAnalytics",
    "FlowMetricsCollector",
    "FlowEventBroadcaster",
    "FlowMonitor",
    "get_flow_analytics",
    "reset_flow_analytics",
]
