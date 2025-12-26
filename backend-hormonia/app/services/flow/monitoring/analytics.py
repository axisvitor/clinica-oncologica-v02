"""
Flow Analytics - Re-export analytics service.

This module provides backwards compatibility by re-exporting
the FlowAnalytics service from the analytics module.
"""

from __future__ import annotations

# Local application imports
from ..analytics import get_flow_analytics, reset_flow_analytics
from ..analytics.analytics import FlowAnalytics


__all__ = ["FlowAnalytics", "get_flow_analytics", "reset_flow_analytics"]
