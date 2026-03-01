"""Shim -- canonical code lives in flow_dashboard_pkg/. See Phase 18."""

from app.services.flow_dashboard_pkg import (
    DashboardTimeframe,
    FlowDashboardService,
    TrendDirection,
    get_flow_dashboard_service,
)

__all__ = [
    "FlowDashboardService",
    "DashboardTimeframe",
    "TrendDirection",
    "get_flow_dashboard_service",
]
