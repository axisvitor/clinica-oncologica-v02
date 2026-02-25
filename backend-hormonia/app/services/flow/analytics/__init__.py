"""
TOMBSTONED -- Phase 16 (Dead Code Removal)

This package has been decommissioned. The flow analytics, metrics collection,
event broadcasting, and health monitoring classes had zero production callers.

Production flow analytics uses ``app.services.analytics.FlowAnalyticsService``
and ``app.services.flow_dashboard.FlowDashboardService`` instead.

Do not import from this package.
"""
raise ImportError(
    "app.services.flow.analytics has been tombstoned in Phase 16 (Dead Code Removal). "
    "This package had zero production callers. "
    "Use app.services.analytics.FlowAnalyticsService for production analytics."
)
