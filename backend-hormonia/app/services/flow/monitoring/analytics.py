from typing import Any
"""Monitoring facade over the analytics module."""

from ..analytics.analytics import FlowAnalytics
from ..analytics import get_flow_analytics

__all__ = ["FlowAnalytics", "get_flow_analytics"]
