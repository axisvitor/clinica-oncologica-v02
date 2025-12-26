"""
Dashboard helpers for Flow Monitoring.

This module provides utility functions for building dashboard snapshots
from flow analytics data.
"""

from __future__ import annotations

# Standard library imports
from typing import Any, Dict

# Local application imports
from ..analytics.analytics import FlowAnalytics


def build_dashboard_snapshot(analytics: FlowAnalytics) -> Dict[str, Any]:
    """
    Build basic dashboard snapshot from analytics.

    Aggregates key metrics for operational dashboards including
    active flows, completion counts, and failure counts.

    Args:
        analytics: FlowAnalytics instance to query.

    Returns:
        Dictionary with dashboard metrics.

    Example:
        >>> analytics = get_flow_analytics()
        >>> snapshot = build_dashboard_snapshot(analytics)
        >>> print(f"Active flows: {snapshot['active_flows']}")
    """
    aggregate_metrics = analytics.get_aggregate_metrics()
    system_health = analytics.get_system_health()

    return {
        "active_flows": system_health.get("active_flows", 0),
        "completed_today": aggregate_metrics.get("total_flows_completed", 0),
        "failed_today": aggregate_metrics.get("total_flows_failed", 0),
        "success_rate_percentage": aggregate_metrics.get("success_rate_percentage", 0.0),
        "total_errors": aggregate_metrics.get("total_errors", 0),
        "healthy_flows": system_health.get("healthy_flows", 0),
        "unhealthy_flows": system_health.get("unhealthy_flows", 0),
    }


__all__ = ["build_dashboard_snapshot"]
