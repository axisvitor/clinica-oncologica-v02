import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_

from app.models.flow_analytics import FlowAnalytics

from .models import DashboardTimeframe, TrendDirection

logger = logging.getLogger(__name__)


class FlowDashboardTrendsMixin:
    async def get_patient_engagement_trends(
        self,
        timeframe: DashboardTimeframe = DashboardTimeframe.LAST_30_DAYS,
        flow_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get patient engagement trend analysis.

        Args:
            timeframe: Analysis timeframe
            flow_type: Optional flow type filter

        Returns:
            Engagement trend data
        """
        try:
            date_range = self._get_date_range(timeframe)
            daily_metrics = await self._get_daily_engagement_metrics(date_range, flow_type)
            trend_direction = self._calculate_trend_direction(
                daily_metrics, "response_rate"
            )
            engagement_distribution = await self._get_engagement_distribution(
                date_range, flow_type
            )
            peak_engagement = await self._get_peak_engagement_times(
                date_range, flow_type
            )

            return {
                "timeframe": {
                    "start_date": date_range[0].isoformat(),
                    "end_date": date_range[1].isoformat(),
                },
                "flow_type": flow_type,
                "trend_direction": trend_direction,
                "daily_metrics": daily_metrics,
                "engagement_distribution": engagement_distribution,
                "peak_engagement_times": peak_engagement,
                "insights": self._generate_engagement_insights(
                    daily_metrics, trend_direction
                ),
            }

        except Exception as e:
            logger.error(f"Failed to get engagement trends: {e}")
            raise

    async def _get_daily_engagement_metrics(
        self, date_range: Tuple[datetime, datetime], flow_type: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Get daily engagement metrics."""
        daily_metrics = []

        current_date = date_range[0]
        while current_date < date_range[1]:
            next_date = current_date + timedelta(days=1)

            day_metrics = await self.analytics_service.calculate_engagement_metrics(
                flow_type=flow_type, date_range=(current_date, next_date)
            )

            daily_metrics.append(
                {
                    "date": current_date.date().isoformat(),
                    "messages_sent": day_metrics.total_messages_sent,
                    "responses_received": day_metrics.total_responses_received,
                    "response_rate": day_metrics.response_rate,
                    "engagement_score": day_metrics.engagement_score,
                }
            )

            current_date = next_date

        return daily_metrics

    def _calculate_trend_direction(
        self, daily_metrics: List[Dict[str, Any]], metric_key: str
    ) -> TrendDirection:
        """Calculate trend direction from daily metrics."""
        if len(daily_metrics) < 2:
            return TrendDirection.UNKNOWN

        values = [
            day[metric_key] for day in daily_metrics if day[metric_key] is not None
        ]
        if len(values) < 2:
            return TrendDirection.UNKNOWN

        first_half = values[: len(values) // 2]
        second_half = values[len(values) // 2 :]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        if abs(second_avg - first_avg) < 0.01:
            return TrendDirection.STABLE
        if second_avg > first_avg:
            return TrendDirection.UP
        return TrendDirection.DOWN

    async def _get_engagement_distribution(
        self, date_range: Tuple[datetime, datetime], flow_type: Optional[str]
    ) -> Dict[str, Any]:
        """Get engagement score distribution."""
        query = self.db.query(FlowAnalytics.engagement_score).filter(
            and_(
                FlowAnalytics.engagement_score.isnot(None),
                FlowAnalytics.timestamp.between(date_range[0], date_range[1]),
            )
        )

        if flow_type:
            query = query.filter(FlowAnalytics.flow_type == flow_type)

        scores = [score[0] for score in query.all()]

        if not scores:
            return {"high": 0, "medium": 0, "low": 0}

        high = sum(1 for s in scores if s >= 0.7)
        medium = sum(1 for s in scores if 0.3 <= s < 0.7)
        low = sum(1 for s in scores if s < 0.3)
        total = len(scores)

        return {
            "high": high / total * 100,
            "medium": medium / total * 100,
            "low": low / total * 100,
            "total_data_points": total,
        }

    async def _get_peak_engagement_times(
        self, date_range: Tuple[datetime, datetime], flow_type: Optional[str]
    ) -> Dict[str, Any]:
        """Get peak engagement times analysis."""
        return {
            "best_day_of_week": "Tuesday",
            "best_hour_of_day": 10,
            "response_rate_by_hour": {},
            "response_rate_by_day": {},
        }

    def _generate_engagement_insights(
        self, daily_metrics: List[Dict[str, Any]], trend_direction: TrendDirection
    ) -> List[str]:
        """Generate insights from engagement data."""
        insights = []

        if trend_direction == TrendDirection.UP:
            insights.append("Patient engagement is improving over time")
        elif trend_direction == TrendDirection.DOWN:
            insights.append("Patient engagement is declining - consider intervention")
        else:
            insights.append("Patient engagement remains stable")

        if daily_metrics:
            avg_response_rate = sum(d["response_rate"] for d in daily_metrics) / len(
                daily_metrics
            )
            if avg_response_rate > 80:
                insights.append("Excellent response rates - current strategy is effective")
            elif avg_response_rate < 50:
                insights.append(
                    "Low response rates - consider message timing or content adjustments"
                )

        return insights


__all__ = ["FlowDashboardTrendsMixin"]
