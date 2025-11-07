"""
DEPRECATED: This module is deprecated and maintained for backward compatibility only.

Please use app.domain.analytics instead:
    from app.domain.analytics import AnalyticsService

This wrapper will be removed in a future version.
"""
import warnings
from datetime import date
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.report import AnalyticsRequest, AnalyticsResponse, DashboardResponse

# Import from new location
from app.domain.analytics import (
    AnalyticsService as NewAnalyticsService,
    AnalyticsError as NewAnalyticsError,
    MetricsCollector,
    DashboardGenerator,
    ReportBuilder
)

# Re-export error for backward compatibility
AnalyticsError = NewAnalyticsError


class AnalyticsService:
    """
    DEPRECATED: Analytics service backward compatibility wrapper.

    This class maintains backward compatibility with existing code.
    New code should use app.domain.analytics.AnalyticsService instead.

    Deprecated since: v2.0.0
    Will be removed in: v3.0.0
    """

    def __init__(self, db: Session):
        """
        Initialize analytics service with database session.

        Issues a deprecation warning on first use.
        """
        warnings.warn(
            "app.services.analytics.AnalyticsService is deprecated. "
            "Use app.domain.analytics.AnalyticsService instead. "
            "This compatibility wrapper will be removed in v3.0.0.",
            DeprecationWarning,
            stacklevel=2
        )
        self._impl = NewAnalyticsService(db)
        self.db = db

        # Expose internal components for advanced use cases
        self.metrics_collector = self._impl.metrics_collector
        self.dashboard_generator = self._impl.dashboard_generator
        self.report_builder = self._impl.report_builder

    def get_analytics(self, request: AnalyticsRequest) -> AnalyticsResponse:
        """
        Get comprehensive analytics data.

        DEPRECATED: Use app.domain.analytics.AnalyticsService.get_analytics() instead.
        """
        return self._impl.get_analytics(request)

    def get_dashboard_data(self, doctor_id: Optional[UUID] = None) -> DashboardResponse:
        """
        Get dashboard data with real-time updates.

        DEPRECATED: Use app.domain.analytics.AnalyticsService.get_dashboard_data() instead.
        """
        return self._impl.get_dashboard_data(doctor_id)

    def get_treatment_distribution(
        self,
        period: str = "30d",
        doctor_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Get treatment type distribution for specified period.

        DEPRECATED: Use app.domain.analytics.AnalyticsService.get_treatment_distribution() instead.
        """
        return self._impl.get_treatment_distribution(period, doctor_id)

    def detect_patterns(
        self,
        patient_id: Optional[UUID] = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Detect patterns in patient data using trend analysis.

        DEPRECATED: Use app.domain.analytics.AnalyticsService.detect_patterns() instead.
        """
        return self._impl.detect_patterns(patient_id, days_back)

    def __getattr__(self, name):
        """
        Proxy any other attribute access to the new implementation.

        This ensures complete backward compatibility for any private methods
        or attributes that might be used by existing code.
        """
        return getattr(self._impl, name)


# Treatment colors constant for backward compatibility
TREATMENT_COLORS = {
    "Quimioterapia": "#3b82f6",  # blue
    "Radioterapia": "#10b981",   # green
    "Imunoterapia": "#f59e0b",   # amber
    "Cirurgia": "#ef4444",       # red
    "Terapia Alvo": "#8b5cf6",   # purple
    "Hormonioterapia": "#ec4899", # pink
    "Outros": "#6b7280"          # gray
}
