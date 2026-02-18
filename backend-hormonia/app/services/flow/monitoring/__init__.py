"""
Flow monitoring surface for consolidated analytics services.

Exports:
    - FlowMetricsCollector
    - FlowMonitor
    - FlowAnalytics
    - FlowEventBroadcaster
    - FlowHealthMetrics
    - HealthStatus
    - get_flow_analytics
    - build_dashboard_snapshot
"""

from __future__ import annotations

# Re-export from analytics module
from ..analytics import (
    FlowAnalytics,
    FlowEventBroadcaster,
    FlowMetricsCollector,
    FlowMonitor,
    get_flow_analytics,
    reset_flow_analytics,
)
from ..analytics.monitor import FlowHealthMetrics, HealthStatus
from .dashboard import build_dashboard_snapshot


__all__ = [
    # Main analytics service
    "FlowAnalytics",
    "get_flow_analytics",
    "reset_flow_analytics",
    # Components
    "FlowMetricsCollector",
    "FlowMonitor",
    "FlowEventBroadcaster",
    # Health monitoring
    "FlowHealthMetrics",
    "HealthStatus",
    # Dashboard helpers
    "build_dashboard_snapshot",
]
