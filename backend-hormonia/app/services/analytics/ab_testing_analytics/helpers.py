"""
Helper Utilities Module

This module contains utility functions for real-time metrics calculation,
trend analysis, and data extraction.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class MetricsHelper:
    """Helper for calculating various metrics."""

    @staticmethod
    def calculate_response_rate(metrics: List[Any]) -> float:
        """Calculate response rate from metrics."""
        if not metrics:
            return 0.0

        responded = len([m for m in metrics if m.event_type == "responded"])
        return responded / len(metrics)

    @staticmethod
    def calculate_avg_response_time(metrics: List[Any]) -> float:
        """Calculate average response time."""
        response_times = [
            m.response_time_seconds
            for m in metrics
            if m.response_time_seconds is not None
        ]

        if not response_times:
            return 0.0

        return sum(response_times) / len(response_times)

    @staticmethod
    def calculate_error_rate(metrics: List[Any]) -> float:
        """Calculate error rate from metrics."""
        if not metrics:
            return 0.0

        errors = len([m for m in metrics if m.event_type == "error"])
        return errors / len(metrics)

    @staticmethod
    def calculate_avg_engagement(metrics: List[Any]) -> float:
        """Calculate average engagement score."""
        engagement_scores = [
            m.engagement_score for m in metrics if m.engagement_score is not None
        ]

        if not engagement_scores:
            return 0.0

        return sum(engagement_scores) / len(engagement_scores)


class TrendAnalyzer:
    """Analyzer for trend calculations."""

    def __init__(self, db: Any):
        """Initialize trend analyzer."""
        self.db = db

    def calculate_trend_indicators(self, experiment_id: str) -> Dict[str, Any]:
        """Calculate trend indicators over time."""
        try:
            from app.models.ab_experiment import ABExperimentMetric

            # Get last 7 days of data
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)

            metrics = (
                self.db.query(ABExperimentMetric)
                .filter(
                    ABExperimentMetric.experiment_id == experiment_id,
                    ABExperimentMetric.event_timestamp >= cutoff_time,
                )
                .order_by(ABExperimentMetric.event_timestamp)
                .all()
            )

            if not metrics:
                return {"message": "Insufficient data for trend analysis"}

            # Group by day
            daily_metrics = {}
            for metric in metrics:
                day = metric.event_timestamp.date()
                if day not in daily_metrics:
                    daily_metrics[day] = {"control": [], "treatment": []}

                variant = (
                    "control" if metric.variant.value == "control" else "treatment"
                )
                daily_metrics[day][variant].append(metric)

            # Calculate daily rates
            trend_data = []
            for day in sorted(daily_metrics.keys()):
                control_metrics = daily_metrics[day]["control"]
                treatment_metrics = daily_metrics[day]["treatment"]

                trend_data.append(
                    {
                        "date": day.isoformat(),
                        "control_response_rate": MetricsHelper.calculate_response_rate(
                            control_metrics
                        ),
                        "treatment_response_rate": MetricsHelper.calculate_response_rate(
                            treatment_metrics
                        ),
                        "control_avg_engagement": MetricsHelper.calculate_avg_engagement(
                            control_metrics
                        ),
                        "treatment_avg_engagement": MetricsHelper.calculate_avg_engagement(
                            treatment_metrics
                        ),
                    }
                )

            # Calculate trend direction
            if len(trend_data) >= 2:
                first_day = trend_data[0]
                last_day = trend_data[-1]

                response_trend = (
                    "increasing"
                    if last_day["treatment_response_rate"]
                    > first_day["treatment_response_rate"]
                    else "decreasing"
                )
                engagement_trend = (
                    "increasing"
                    if last_day["treatment_avg_engagement"]
                    > first_day["treatment_avg_engagement"]
                    else "decreasing"
                )
            else:
                response_trend = "stable"
                engagement_trend = "stable"

            return {
                "trend_data": trend_data,
                "response_rate_trend": response_trend,
                "engagement_trend": engagement_trend,
                "data_points": len(trend_data),
            }

        except Exception as e:
            logger.error(f"Error calculating trends: {str(e)}")
            return {"error": str(e)}


class AlertChecker:
    """Checker for performance alerts."""

    @staticmethod
    def check_performance_alerts(
        real_time_kpis: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Check for performance alerts based on KPIs."""
        alerts = []

        # Check error rates
        control_error_rate = real_time_kpis.get("error_rates", {}).get("control", 0)
        treatment_error_rate = real_time_kpis.get("error_rates", {}).get("treatment", 0)

        if control_error_rate > 0.1:
            alerts.append(
                {
                    "severity": "warning",
                    "type": "error_rate",
                    "message": f"Control group error rate elevated: {control_error_rate * 100:.1f}%",
                }
            )

        if treatment_error_rate > 0.1:
            alerts.append(
                {
                    "severity": "warning",
                    "type": "error_rate",
                    "message": f"Treatment group error rate elevated: {treatment_error_rate * 100:.1f}%",
                }
            )

        # Check response rates
        control_response_rate = real_time_kpis.get("response_rates", {}).get(
            "control", 0
        )
        treatment_response_rate = real_time_kpis.get("response_rates", {}).get(
            "treatment", 0
        )

        if control_response_rate < 0.3:
            alerts.append(
                {
                    "severity": "info",
                    "type": "response_rate",
                    "message": f"Control group response rate low: {control_response_rate * 100:.1f}%",
                }
            )

        if treatment_response_rate < 0.3:
            alerts.append(
                {
                    "severity": "info",
                    "type": "response_rate",
                    "message": f"Treatment group response rate low: {treatment_response_rate * 100:.1f}%",
                }
            )

        # Check response time
        control_response_time = real_time_kpis.get("average_response_time", {}).get(
            "control", 0
        )
        treatment_response_time = real_time_kpis.get("average_response_time", {}).get(
            "treatment", 0
        )

        if control_response_time > 3600:  # 1 hour
            alerts.append(
                {
                    "severity": "warning",
                    "type": "response_time",
                    "message": f"Control group response time elevated: {control_response_time / 60:.1f} minutes",
                }
            )

        if treatment_response_time > 3600:
            alerts.append(
                {
                    "severity": "warning",
                    "type": "response_time",
                    "message": f"Treatment group response time elevated: {treatment_response_time / 60:.1f} minutes",
                }
            )

        if not alerts:
            alerts.append(
                {
                    "severity": "success",
                    "type": "all_clear",
                    "message": "All metrics within normal ranges",
                }
            )

        return alerts


class DataExtractor:
    """Helper for extracting and organizing experiment data."""

    def __init__(self, db: Any):
        """Initialize data extractor."""
        self.db = db

    def get_experiment_data(self, experiment_id: str) -> tuple:
        """Get experiment data separated by variant."""
        from app.models.ab_experiment import ABExperimentMetric, VariantType

        metrics = (
            self.db.query(ABExperimentMetric)
            .filter(ABExperimentMetric.experiment_id == experiment_id)
            .all()
        )

        control_data = [
            {
                "event_type": m.event_type,
                "response_time": m.response_time_seconds,
                "engagement_score": m.engagement_score,
                "timestamp": m.event_timestamp,
                "event_data": m.event_data,
            }
            for m in metrics
            if m.variant == VariantType.CONTROL
        ]

        treatment_data = [
            {
                "event_type": m.event_type,
                "response_time": m.response_time_seconds,
                "engagement_score": m.engagement_score,
                "timestamp": m.event_timestamp,
                "event_data": m.event_data,
            }
            for m in metrics
            if m.variant == VariantType.TREATMENT
        ]

        return control_data, treatment_data


class ResultsStore:
    """Helper for storing experiment results."""

    def __init__(self, db: Any):
        """Initialize results store."""
        self.db = db

    def store_experiment_results(
        self, experiment_id: str, results: Dict[str, Any]
    ) -> None:
        """Store comprehensive results in database."""
        try:
            from app.models.ab_experiment import ABExperiment

            # Update experiment record with key results
            experiment = (
                self.db.query(ABExperiment)
                .filter(ABExperiment.id == experiment_id)
                .first()
            )

            if experiment:
                experiment.results = results
                experiment.is_statistically_significant = (
                    results.get("statistical_tests", {})
                    .get("overall", {})
                    .get("is_significant", False)
                )
                experiment.p_value = (
                    results.get("statistical_tests", {})
                    .get("overall", {})
                    .get("min_p_value")
                )
                experiment.effect_size = results.get("effect_sizes", {}).get("cohens_d")
                experiment.winner = self._determine_winner(results)

                self.db.commit()

        except Exception as e:
            logger.error(f"Error storing results: {str(e)}")
            self.db.rollback()

    def _determine_winner(self, results: Dict[str, Any]) -> Optional[str]:
        """Determine winning variant based on results."""
        if (
            not results.get("statistical_tests", {})
            .get("overall", {})
            .get("is_significant", False)
        ):
            return None

        treatment_response = (
            results.get("variant_statistics", {})
            .get("treatment", {})
            .get("response_rate", 0)
        )
        control_response = (
            results.get("variant_statistics", {})
            .get("control", {})
            .get("response_rate", 0)
        )

        if treatment_response > control_response:
            return "treatment"
        elif control_response > treatment_response:
            return "control"
        else:
            return "tie"
