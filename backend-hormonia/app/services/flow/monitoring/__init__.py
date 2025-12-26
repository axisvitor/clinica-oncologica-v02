"""
Flow Monitoring - Monitoring facade for Flow Services.

This module provides a simplified monitoring interface that re-exports
analytics components from the consolidated flow analytics module.

Exports:
    - FlowMetricsCollector: Metrics collection (from analytics.metrics)
    - FlowMonitor: Health monitoring (from analytics.health)
    - FlowAnalytics: Main analytics service (from analytics.analytics)
    - FlowEventBroadcaster: Event broadcasting (from analytics)
    - FlowHealthMetrics: Health metrics dataclass (from analytics.monitor)
    - HealthStatus: Health status enum (from analytics.monitor)
    - get_flow_analytics: Singleton getter for FlowAnalytics
    - build_dashboard_snapshot: Dashboard helper (from dashboard)
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
