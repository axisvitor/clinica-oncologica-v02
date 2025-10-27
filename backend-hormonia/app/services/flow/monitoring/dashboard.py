"""Dashboard helpers built on top of FlowAnalytics."""

from typing import Dict, Any

from ..analytics.analytics import FlowAnalytics


def build_dashboard_snapshot(analytics: FlowAnalytics) -> Dict[str, Any]:
    """Return basic counters for ops dashboards."""
    metrics = analytics.get_latest_metrics()
    return {
        "active_flows": metrics.active_flows if metrics else 0,
        "completed_today": metrics.completed_flows if metrics else 0,
        "failed_today": metrics.failed_flows if metrics else 0,
    }


__all__ = ["build_dashboard_snapshot"]
