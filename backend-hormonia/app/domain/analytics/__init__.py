"""
Analytics domain package.

Provides comprehensive analytics functionality split into focused modules:
- MetricsCollector: Raw data collection and aggregation
- DashboardGenerator: Real-time dashboard data and visualizations
- ReportBuilder: Comprehensive reporting and pattern analysis
- AnalyticsService: Main orchestrator coordinating all analytics operations

Public API:
    AnalyticsService: Main entry point for all analytics operations
    MetricsCollector: Direct access to metrics collection
    DashboardGenerator: Direct access to dashboard generation
    ReportBuilder: Direct access to report building
"""

from .analytics_service import AnalyticsService, AnalyticsError
from .metrics_collector import MetricsCollector
from .dashboard_generator import DashboardGenerator
from .report_builder import ReportBuilder

__all__ = [
    "AnalyticsService",
    "AnalyticsError",
    "MetricsCollector",
    "DashboardGenerator",
    "ReportBuilder",
]

__version__ = "2.0.0"
