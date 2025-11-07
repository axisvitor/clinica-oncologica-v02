"""
Main analytics service orchestrator.
Coordinates metrics collection, dashboard generation, and report building.
"""
import logging
from datetime import date
from typing import Dict, Optional, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.utils.db_retry import with_db_retry
from app.schemas.report import AnalyticsRequest, AnalyticsResponse, DashboardResponse

from .metrics_collector import MetricsCollector
from .dashboard_generator import DashboardGenerator
from .report_builder import ReportBuilder


logger = logging.getLogger(__name__)


class AnalyticsError(Exception):
    """Analytics specific error."""
    pass


class AnalyticsService:
    """
    Main analytics service orchestrator.

    Provides comprehensive analytics including:
    - Patient engagement metrics
    - System performance statistics
    - Trend analysis and pattern detection
    - Dashboard data aggregation

    Coordinates between:
    - MetricsCollector: Raw data collection and aggregation
    - DashboardGenerator: Real-time dashboard data
    - ReportBuilder: Comprehensive reports and pattern analysis
    """

    def __init__(self, db: Session):
        """
        Initialize analytics service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

        # Initialize domain components
        self.metrics_collector = MetricsCollector(db)
        self.dashboard_generator = DashboardGenerator(db, self.metrics_collector)
        self.report_builder = ReportBuilder(db, self.metrics_collector)

        logger.info("AnalyticsService initialized with domain components")

    @with_db_retry(max_retries=3)
    def get_analytics(self, request: AnalyticsRequest) -> AnalyticsResponse:
        """
        Get comprehensive analytics data.

        Args:
            request: Analytics request parameters

        Returns:
            Analytics response with patient and system metrics

        Raises:
            AnalyticsError: If analytics generation fails
        """
        try:
            logger.info("Getting analytics data via ReportBuilder")
            return self.report_builder.build_analytics_report(request)
        except Exception as e:
            logger.error(f"Analytics generation failed: {e}")
            raise AnalyticsError(f"Analytics generation failed: {str(e)}")

    @with_db_retry(max_retries=3)
    def get_dashboard_data(self, doctor_id: Optional[UUID] = None) -> DashboardResponse:
        """
        Get dashboard data with real-time updates.

        Args:
            doctor_id: Optional doctor ID to filter data

        Returns:
            Dashboard response with quick stats and charts

        Raises:
            AnalyticsError: If dashboard generation fails
        """
        try:
            logger.info("Getting dashboard data via DashboardGenerator")
            return self.dashboard_generator.generate_dashboard(doctor_id)
        except Exception as e:
            logger.error(f"Dashboard data generation failed: {e}")
            raise AnalyticsError(f"Dashboard generation failed: {str(e)}")

    @with_db_retry(max_retries=3)
    def get_treatment_distribution(
        self,
        period: str = "30d",
        doctor_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Get treatment type distribution for specified period.

        Args:
            period: Time period ("7d", "30d", "90d", or "all")
            doctor_id: Optional doctor ID to filter patients

        Returns:
            Distribution data with counts, percentages, and colors

        Raises:
            AnalyticsError: If distribution generation fails
        """
        try:
            logger.info(f"Getting treatment distribution via ReportBuilder for period: {period}")
            return self.report_builder.build_treatment_distribution(period, doctor_id)
        except Exception as e:
            logger.error(f"Treatment distribution generation failed: {e}")
            raise AnalyticsError(f"Treatment distribution failed: {str(e)}")

    @with_db_retry(max_retries=3)
    def detect_patterns(
        self,
        patient_id: Optional[UUID] = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Detect patterns in patient data using trend analysis.

        Args:
            patient_id: Optional patient ID to analyze specific patient
            days_back: Number of days to analyze

        Returns:
            Dictionary containing detected patterns

        Raises:
            AnalyticsError: If pattern detection fails
        """
        try:
            logger.info(f"Detecting patterns via ReportBuilder")
            return self.report_builder.detect_patterns(patient_id, days_back)
        except Exception as e:
            logger.error(f"Pattern detection failed: {e}")
            raise AnalyticsError(f"Pattern detection failed: {str(e)}")
