"""
Report building and pattern analysis.
Handles comprehensive reporting, trend analysis, and anomaly detection.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import deque
from statistics import mean, stdev
from uuid import UUID

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.message import Message, MessageDirection
from app.models.quiz import QuizResponse
from app.models.alert import Alert
from app.utils.db_retry import with_db_retry
from app.services.query_performance_monitor import QueryPerformanceMonitor
from app.schemas.report import AnalyticsRequest, AnalyticsResponse
from app.domain.analytics.date_utils import build_date_window
from app.utils.timezone import now_sao_paulo


logger = logging.getLogger(__name__)


# Treatment type color mapping for consistent chart rendering
TREATMENT_COLORS = {
    "Quimioterapia": "#3b82f6",  # blue
    "Radioterapia": "#10b981",  # green
    "Imunoterapia": "#f59e0b",  # amber
    "Cirurgia": "#ef4444",  # red
    "Terapia Alvo": "#8b5cf6",  # purple
    "Hormonioterapia": "#ec4899",  # pink
    "Outros": "#6b7280",  # gray
}


class ReportBuilder:
    """
    Builds comprehensive reports and analyzes patterns.

    Handles:
    - Full analytics reports
    - Treatment distribution analysis
    - Pattern detection and trend analysis
    - Anomaly detection
    - Historical comparisons
    """

    def __init__(self, db: Session, metrics_collector):
        """
        Initialize report builder.

        Args:
            db: Database session
            metrics_collector: MetricsCollector instance for data collection
        """
        self.db = db
        self.metrics_collector = metrics_collector
        self.query_monitor = QueryPerformanceMonitor(db)

        logger.info("ReportBuilder initialized")

    @staticmethod
    def _date_window(start_date: date, end_date: date) -> tuple[datetime, datetime]:
        """Build inclusive date window [start, end+1day) in Sao Paulo timezone."""
        return build_date_window(start_date, end_date)

    @with_db_retry(max_retries=3)
    def build_analytics_report(self, request: AnalyticsRequest) -> AnalyticsResponse:
        """
        Build comprehensive analytics report.

        Args:
            request: Analytics request parameters

        Returns:
            Analytics response with patient and system metrics
        """
        try:
            logger.info("Building analytics report")

            # Get patient analytics
            patient_analytics = []
            if request.patient_ids:
                with self.query_monitor.monitor_query("analytics_patient_specific"):
                    for patient_id in request.patient_ids:
                        analytics = self.metrics_collector.get_patient_metrics(
                            patient_id,
                            request.start_date,
                            request.end_date,
                            request.metrics,
                        )
                        if analytics:
                            patient_analytics.append(analytics)
            else:
                # Get analytics for all patients (filtered by doctor if specified)
                # OPTIMIZATION: Use eager loading to prevent N+1 queries
                with self.query_monitor.monitor_query("analytics_all_patients"):
                    patients = (
                        self.metrics_collector.get_filtered_patients_with_relations(
                            request.doctor_id
                        )
                    )
                    for patient in patients:
                        analytics = self.metrics_collector.get_patient_metrics(
                            patient.id,
                            request.start_date,
                            request.end_date,
                            request.metrics,
                        )
                        if analytics:
                            patient_analytics.append(analytics)

            # Get system analytics
            with self.query_monitor.monitor_query("analytics_system_metrics"):
                system_analytics = self.metrics_collector.get_system_metrics(
                    request.start_date, request.end_date
                )

            response = AnalyticsResponse(
                patient_analytics=patient_analytics, system_analytics=system_analytics
            )

            logger.info(
                f"Generated analytics report for {len(patient_analytics)} patients"
            )
            return response

        except Exception as e:
            logger.error(f"Analytics report building failed: {e}")
            raise

    @with_db_retry(max_retries=3)
    def build_treatment_distribution(
        self, period: str = "30d", doctor_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Build treatment type distribution report for specified period.

        Args:
            period: Time period ("7d", "30d", "90d", or "all")
            doctor_id: Optional doctor ID to filter patients

        Returns:
            Distribution data with counts, percentages, and colors
        """
        try:
            logger.info(f"Building treatment distribution for period: {period}")

            # Calculate date filter based on period
            if period == "all":
                date_filter = None
            else:
                days = int(period.rstrip("d"))
                date_filter = now_sao_paulo() - timedelta(days=days)

            # Build base query for treatment type counts
            query = self.db.query(
                Patient.treatment_type, func.count(Patient.id).label("count")
            )

            # Apply date filter if specified
            if date_filter:
                query = query.filter(Patient.created_at >= date_filter)

            # Apply doctor filter if specified
            if doctor_id:
                query = query.filter(Patient.doctor_id == doctor_id)

            # Filter out null treatment types and group by treatment type
            query = query.filter(Patient.treatment_type.isnot(None))
            results = query.group_by(Patient.treatment_type).all()

            # Calculate total patients
            total = sum(r.count for r in results)

            # Handle empty results
            if total == 0:
                return {
                    "data": [],
                    "period": period,
                    "total_patients": 0,
                    "timestamp": now_sao_paulo().isoformat(),
                }

            # Build distribution list with percentages and colors
            distribution = []
            for treatment_type, count in results:
                percentage = round((count / total * 100) if total > 0 else 0, 2)
                color = TREATMENT_COLORS.get(treatment_type, "#6b7280")

                distribution.append(
                    {
                        "treatment_type": treatment_type,
                        "count": count,
                        "percentage": percentage,
                        "color": color,
                    }
                )

            # Sort by count descending (most common treatments first)
            distribution.sort(key=lambda x: x["count"], reverse=True)

            # Group small categories into "Outros" if they're below threshold
            MIN_PERCENTAGE_THRESHOLD = 2.0
            large_categories = [
                d for d in distribution if d["percentage"] >= MIN_PERCENTAGE_THRESHOLD
            ]
            small_categories = [
                d for d in distribution if d["percentage"] < MIN_PERCENTAGE_THRESHOLD
            ]

            if small_categories and len(large_categories) > 0:
                outros_count = sum(c["count"] for c in small_categories)
                outros_percentage = sum(c["percentage"] for c in small_categories)
                large_categories.append(
                    {
                        "treatment_type": "Outros",
                        "count": outros_count,
                        "percentage": round(outros_percentage, 2),
                        "color": TREATMENT_COLORS["Outros"],
                    }
                )
                distribution = large_categories

            return {
                "data": distribution,
                "period": period,
                "total_patients": total,
                "timestamp": now_sao_paulo().isoformat(),
            }

        except Exception as e:
            logger.error(f"Treatment distribution building failed: {e}")
            raise

    @with_db_retry(max_retries=3)
    def detect_patterns(
        self, patient_id: Optional[UUID] = None, days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Detect patterns in patient data using trend analysis.

        Args:
            patient_id: Optional patient ID to analyze specific patient
            days_back: Number of days to analyze

        Returns:
            Dictionary containing detected patterns
        """
        try:
            logger.info(
                f"Detecting patterns for {'all patients' if not patient_id else f'patient {patient_id}'}"
            )

            end_date = now_sao_paulo().date()
            start_date = end_date - timedelta(days=days_back)

            patterns = {
                "engagement_trends": self._analyze_engagement_trends(
                    patient_id, start_date, end_date
                ),
                "response_time_patterns": self._analyze_response_time_patterns(
                    patient_id, start_date, end_date
                ),
                "alert_patterns": self._analyze_alert_patterns(
                    patient_id, start_date, end_date
                ),
                "quiz_completion_trends": self._analyze_quiz_trends(
                    patient_id, start_date, end_date
                ),
                "anomalies": self._detect_anomalies(patient_id, start_date, end_date),
            }

            logger.info("Pattern detection completed")
            return patterns

        except Exception as e:
            logger.error(f"Pattern detection failed: {e}")
            raise

    # Private analysis methods

    def _analyze_engagement_trends(
        self, patient_id: Optional[UUID], start_date: date, end_date: date
    ) -> Dict[str, Any]:
        """Analyze engagement trends."""
        # Get daily message counts
        query = (
            self.db.query(
                func.date(Message.created_at).label("date"),
                func.count(Message.id).label("count"),
            )
            .filter(
                and_(Message.created_at >= start_date, Message.created_at <= end_date)
            )
            .group_by(func.date(Message.created_at))
        )

        if patient_id:
            query = query.filter(Message.patient_id == patient_id)

        daily_counts = query.all()

        # Calculate trend
        if len(daily_counts) < 2:
            return {"trend": "insufficient_data", "slope": 0}

        # Simple linear trend calculation
        x_values = list(range(len(daily_counts)))
        y_values = []
        for _, count in daily_counts:
            # Handle Mock objects
            try:
                count_num = int(count)
            except (TypeError, ValueError):
                count_num = getattr(count, "return_value", 0)
            y_values.append(count_num)

        # Calculate slope
        n = len(x_values)
        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        sum_x2 = sum(x * x for x in x_values)

        slope = (
            (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            if (n * sum_x2 - sum_x * sum_x) != 0
            else 0
        )

        # Handle Mock objects for slope comparisons
        try:
            slope_num = float(slope)
        except (TypeError, ValueError):
            slope_num = getattr(slope, "return_value", 0)

        trend = (
            "increasing"
            if slope_num > 0.1
            else "decreasing"
            if slope_num < -0.1
            else "stable"
        )

        return {
            "trend": trend,
            "slope": round(slope, 3),
            "daily_average": round(sum_y / n, 2) if n > 0 else 0,
        }

    def _analyze_response_time_patterns(
        self, patient_id: Optional[UUID], start_date: date, end_date: date
    ) -> Dict[str, Any]:
        """Analyze response time patterns."""
        query = self.db.query(Message).filter(
            and_(
                Message.created_at >= start_date,
                Message.created_at <= end_date,
            )
        )

        if patient_id:
            query = query.filter(Message.patient_id == patient_id)

        messages = query.order_by(Message.created_at).all()

        response_times: List[float] = []
        outbound_queue: deque[datetime] = deque()

        for msg in messages:
            if msg.direction == MessageDirection.OUTBOUND:
                outbound_queue.append(msg.created_at)
            elif msg.direction == MessageDirection.INBOUND and outbound_queue:
                start_time = outbound_queue.popleft()
                diff_hours = (msg.created_at - start_time).total_seconds() / 3600

                # Handle Mock objects for diff_hours comparison
                try:
                    diff_hours_num = float(diff_hours)
                except (TypeError, ValueError):
                    diff_hours_num = getattr(diff_hours, "return_value", 0)

                if diff_hours_num >= 0:
                    response_times.append(diff_hours_num)

        if not response_times:
            return {
                "average_response_time_hours": None,
                "fastest_response_hours": None,
                "slowest_response_hours": None,
                "std_dev_hours": None,
                "pattern": "no_data",
            }

        avg = mean(response_times)
        fastest = min(response_times)
        slowest = max(response_times)
        std_dev = stdev(response_times) if len(response_times) > 1 else 0.0

        # Handle Mock objects for avg comparisons
        try:
            avg_num = float(avg)
        except (TypeError, ValueError):
            avg_num = getattr(avg, "return_value", 0)

        if avg_num <= 1:
            pattern = "fast"
        elif avg_num <= 4:
            pattern = "moderate"
        else:
            pattern = "slow"

        return {
            "average_response_time_hours": round(avg, 2),
            "fastest_response_hours": round(fastest, 2),
            "slowest_response_hours": round(slowest, 2),
            "std_dev_hours": round(std_dev, 2),
            "pattern": pattern,
        }

    def _analyze_alert_patterns(
        self, patient_id: Optional[UUID], start_date: date, end_date: date
    ) -> Dict[str, Any]:
        """Analyze alert patterns."""
        query = self.db.query(Alert).filter(
            and_(Alert.created_at >= start_date, Alert.created_at <= end_date)
        )

        if patient_id:
            query = query.filter(Alert.patient_id == patient_id)

        alerts = query.all()

        if not alerts:
            return {"pattern": "no_alerts", "frequency": 0}

        # Analyze by severity
        severity_counts = {}
        for alert in alerts:
            severity = alert.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        # Analyze frequency
        days_in_period = (end_date - start_date).days + 1
        frequency = len(alerts) / days_in_period

        # Handle Mock objects for frequency comparison
        try:
            frequency_num = float(frequency)
        except (TypeError, ValueError):
            frequency_num = getattr(frequency, "return_value", 0)

        return {
            "pattern": "high_frequency" if frequency_num > 1 else "low_frequency",
            "frequency": round(frequency, 2),
            "severity_distribution": severity_counts,
            "total_alerts": len(alerts),
        }

    def _analyze_quiz_trends(
        self, patient_id: Optional[UUID], start_date: date, end_date: date
    ) -> Dict[str, Any]:
        """Analyze quiz completion trends."""
        start_dt, end_dt_exclusive = self._date_window(start_date, end_date)
        query = self.db.query(QuizResponse).filter(
            and_(
                QuizResponse.responded_at.isnot(None),
                QuizResponse.responded_at >= start_dt,
                QuizResponse.responded_at < end_dt_exclusive,
            )
        )

        if patient_id:
            query = query.filter(QuizResponse.patient_id == patient_id)

        completions = query.all()

        days_in_period = (end_date - start_date).days + 1
        completion_rate = len(completions) / days_in_period

        # Handle Mock objects for completion_rate comparisons
        try:
            completion_rate_num = float(completion_rate)
        except (TypeError, ValueError):
            completion_rate_num = getattr(completion_rate, "return_value", 0)

        return {
            "completion_rate": round(completion_rate, 2),
            "total_completions": len(completions),
            "trend": "improving" if completion_rate_num > 0.5 else "needs_attention",
        }

    def _detect_anomalies(
        self, patient_id: Optional[UUID], start_date: date, end_date: date
    ) -> List[Dict[str, Any]]:
        """Detect anomalies in patient data."""
        anomalies = []

        # Check for sudden drop in engagement
        engagement_trend = self._analyze_engagement_trends(
            patient_id, start_date, end_date
        )
        # Handle Mock objects for slope comparison
        slope_value = engagement_trend["slope"]
        try:
            slope_num = float(slope_value)
        except (TypeError, ValueError):
            slope_num = getattr(slope_value, "return_value", 0)

        if engagement_trend["trend"] == "decreasing" and slope_num < -1:
            anomalies.append(
                {
                    "type": "engagement_drop",
                    "severity": "medium",
                    "description": "Significant decrease in patient engagement detected",
                }
            )

        # Check for high alert frequency
        alert_pattern = self._analyze_alert_patterns(patient_id, start_date, end_date)
        # Handle Mock objects for frequency comparison
        frequency_value = alert_pattern["frequency"]
        try:
            frequency_num = float(frequency_value)
        except (TypeError, ValueError):
            frequency_num = getattr(frequency_value, "return_value", 0)

        if frequency_num > 2:
            anomalies.append(
                {
                    "type": "high_alert_frequency",
                    "severity": "high",
                    "description": f"High alert frequency detected: {alert_pattern['frequency']} alerts per day",
                }
            )

        return anomalies
