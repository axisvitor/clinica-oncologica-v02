import logging
from typing import Any, Optional

from fastapi import Depends

from app.database import get_db
from app.services.analytics import FlowAnalyticsService

from .alerts import FlowDashboardAlertsMixin
from .analytics import FlowDashboardAnalyticsMixin
from .optimization import FlowDashboardOptimizationMixin
from .risk import FlowDashboardRiskMixin
from .trends import FlowDashboardTrendsMixin

logger = logging.getLogger(__name__)


class FlowDashboardService(
    FlowDashboardOptimizationMixin,
    FlowDashboardAlertsMixin,
    FlowDashboardRiskMixin,
    FlowDashboardTrendsMixin,
    FlowDashboardAnalyticsMixin,
):
    """
    Service for generating flow analytics dashboards and reports.
    Provides real-time metrics, trend analysis, and actionable insights.
    """

    def __init__(
        self, db: Any, analytics_service: Optional[FlowAnalyticsService] = None
    ):
        """
        Initialize flow dashboard service.

        Args:
            db: Database session
            analytics_service: Flow analytics service instance
        """
        self.db = db
        self.analytics_service = analytics_service or FlowAnalyticsService(db)

        logger.info("Flow Dashboard Service initialized")


_flow_dashboard_service: Optional[FlowDashboardService] = None


def get_flow_dashboard_service(db: Any = Depends(get_db)) -> FlowDashboardService:
    """
    Get flow dashboard service instance.

    Args:
        db: Database session

    Returns:
        FlowDashboardService instance
    """
    return FlowDashboardService(db)


__all__ = ["FlowDashboardService", "get_flow_dashboard_service"]
