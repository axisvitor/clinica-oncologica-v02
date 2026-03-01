import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, select

from app.models.flow_analytics import FlowAnalytics
from app.services.analytics import EventType, RiskLevel
from app.utils.timezone import now_sao_paulo

from .models import DashboardTimeframe, TrendDirection

logger = logging.getLogger(__name__)


class FlowDashboardAnalyticsMixin:
    @staticmethod
    def _flow_type_column():
        return getattr(FlowAnalytics, "flow_type", FlowAnalytics.flow_template_version_id)

    @staticmethod
    def _timestamp_column():
        return getattr(FlowAnalytics, "timestamp", FlowAnalytics.calculated_at)

    @staticmethod
    def _event_type_column():
        return getattr(FlowAnalytics, "event_type", None)

    async def get_dashboard_overview(
        self,
        timeframe: DashboardTimeframe = DashboardTimeframe.LAST_7_DAYS,
        custom_range: Optional[Tuple[datetime, datetime]] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive dashboard overview with key metrics.

        Args:
            timeframe: Dashboard timeframe
            custom_range: Custom date range if timeframe is CUSTOM

        Returns:
            Dashboard overview data
        """
        try:
            date_range = self._get_date_range(timeframe, custom_range)
            engagement_metrics = await self.analytics_service.calculate_engagement_metrics(
                date_range=date_range
            )
            at_risk_patients = await self.analytics_service.identify_at_risk_patients(
                lookback_days=(date_range[1] - date_range[0]).days
            )
            flow_type_metrics = await self._get_flow_type_breakdown(date_range)
            trends = await self._calculate_trends(date_range)
            recent_alerts = await self._get_recent_alerts(date_range)

            return {
                "timeframe": {
                    "type": timeframe.value,
                    "start_date": date_range[0].isoformat(),
                    "end_date": date_range[1].isoformat(),
                    "days": (date_range[1] - date_range[0]).days,
                },
                "overview_metrics": {
                    "total_messages_sent": engagement_metrics.total_messages_sent,
                    "total_responses_received": engagement_metrics.total_responses_received,
                    "response_rate": engagement_metrics.response_rate,
                    "average_response_time": engagement_metrics.average_response_time.total_seconds()
                    if engagement_metrics.average_response_time
                    else None,
                    "engagement_score": engagement_metrics.engagement_score,
                    "sentiment_distribution": engagement_metrics.sentiment_distribution,
                    "completion_rates": engagement_metrics.completion_rates,
                },
                "at_risk_summary": {
                    "total_at_risk": len(at_risk_patients),
                    "critical_risk": len(
                        [
                            p
                            for p in at_risk_patients
                            if p.risk_level == RiskLevel.CRITICAL
                        ]
                    ),
                    "high_risk": len(
                        [p for p in at_risk_patients if p.risk_level == RiskLevel.HIGH]
                    ),
                    "medium_risk": len(
                        [p for p in at_risk_patients if p.risk_level == RiskLevel.MEDIUM]
                    ),
                },
                "flow_type_breakdown": flow_type_metrics,
                "trends": trends,
                "recent_alerts": recent_alerts,
                "generated_at": now_sao_paulo().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get dashboard overview: {e}")
            raise

    def _get_date_range(
        self,
        timeframe: DashboardTimeframe,
        custom_range: Optional[Tuple[datetime, datetime]] = None,
    ) -> Tuple[datetime, datetime]:
        """Get date range based on timeframe."""
        if timeframe == DashboardTimeframe.CUSTOM and custom_range:
            return custom_range

        end_date = now_sao_paulo()

        if timeframe == DashboardTimeframe.LAST_24_HOURS:
            start_date = end_date - timedelta(hours=24)
        elif timeframe == DashboardTimeframe.LAST_7_DAYS:
            start_date = end_date - timedelta(days=7)
        elif timeframe == DashboardTimeframe.LAST_30_DAYS:
            start_date = end_date - timedelta(days=30)
        elif timeframe == DashboardTimeframe.LAST_90_DAYS:
            start_date = end_date - timedelta(days=90)
        else:
            start_date = end_date - timedelta(days=7)

        return (start_date, end_date)

    async def _get_flow_type_breakdown(
        self, date_range: Tuple[datetime, datetime]
    ) -> Dict[str, Any]:
        """Get breakdown of metrics by flow type."""
        flow_type_column = self._flow_type_column()
        flow_types_stmt = select(flow_type_column).distinct()
        flow_types = (await self.db.execute(flow_types_stmt)).all()
        breakdown = {}

        for flow_type_tuple in flow_types:
            flow_type = flow_type_tuple[0]
            metrics = await self.analytics_service.calculate_engagement_metrics(
                flow_type=flow_type, date_range=date_range
            )

            breakdown[flow_type] = {
                "messages_sent": metrics.total_messages_sent,
                "responses_received": metrics.total_responses_received,
                "response_rate": metrics.response_rate,
                "engagement_score": metrics.engagement_score,
                "completion_rate": metrics.completion_rates.get(flow_type, 0.0),
            }

        return breakdown

    async def _calculate_trends(
        self, date_range: Tuple[datetime, datetime]
    ) -> Dict[str, Any]:
        """Calculate trend analysis for key metrics."""
        period_length = date_range[1] - date_range[0]
        previous_start = date_range[0] - period_length
        previous_end = date_range[0]

        current_metrics = await self.analytics_service.calculate_engagement_metrics(
            date_range=date_range
        )
        previous_metrics = await self.analytics_service.calculate_engagement_metrics(
            date_range=(previous_start, previous_end)
        )

        def calculate_change(current, previous):
            if previous == 0:
                return 0.0 if current == 0 else 100.0
            return ((current - previous) / previous) * 100

        return {
            "response_rate": {
                "current": current_metrics.response_rate,
                "previous": previous_metrics.response_rate,
                "change_percent": calculate_change(
                    current_metrics.response_rate, previous_metrics.response_rate
                ),
                "direction": self._get_trend_direction(
                    current_metrics.response_rate, previous_metrics.response_rate
                ),
            },
            "engagement_score": {
                "current": current_metrics.engagement_score,
                "previous": previous_metrics.engagement_score,
                "change_percent": calculate_change(
                    current_metrics.engagement_score, previous_metrics.engagement_score
                ),
                "direction": self._get_trend_direction(
                    current_metrics.engagement_score, previous_metrics.engagement_score
                ),
            },
            "messages_sent": {
                "current": current_metrics.total_messages_sent,
                "previous": previous_metrics.total_messages_sent,
                "change_percent": calculate_change(
                    current_metrics.total_messages_sent,
                    previous_metrics.total_messages_sent,
                ),
                "direction": self._get_trend_direction(
                    current_metrics.total_messages_sent,
                    previous_metrics.total_messages_sent,
                ),
            },
        }

    def _get_trend_direction(self, current: float, previous: float) -> TrendDirection:
        """Determine trend direction."""
        if abs(current - previous) < 0.01:
            return TrendDirection.STABLE
        if current > previous:
            return TrendDirection.UP
        return TrendDirection.DOWN

    async def _get_recent_alerts(
        self, date_range: Tuple[datetime, datetime]
    ) -> List[Dict[str, Any]]:
        """Get recent alerts within date range."""
        alerts = []

        timestamp_column = self._timestamp_column()
        conditions = [timestamp_column.between(date_range[0], date_range[1])]
        event_type_column = self._event_type_column()
        if event_type_column is not None:
            conditions.append(event_type_column == EventType.CONCERN_DETECTED)

        concerning_events_stmt = (
            select(FlowAnalytics)
            .where(and_(*conditions))
            .order_by(desc(timestamp_column))
            .limit(10)
        )
        concerning_events = (
            await self.db.execute(concerning_events_stmt)
        ).scalars().all()

        for event in concerning_events:
            alerts.append(
                {
                    "id": str(event.id),
                    "type": "patient_concern",
                    "severity": "high",
                    "patient_id": str(event.patient_id),
                    "message": "Concerning response detected in "
                    f"{getattr(event, 'flow_type', getattr(event, 'flow_template_version_id', 'unknown'))} flow",
                    "timestamp": getattr(
                        event,
                        "timestamp",
                        getattr(event, "calculated_at", now_sao_paulo()),
                    ).isoformat(),
                    "data": getattr(event, "event_data", getattr(event, "step_analytics", {})),
                }
            )

        return alerts


__all__ = ["FlowDashboardAnalyticsMixin"]
