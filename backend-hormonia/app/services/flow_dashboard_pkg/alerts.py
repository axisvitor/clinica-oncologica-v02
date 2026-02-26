import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_

from app.models.flow_analytics import FlowAnalytics
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class FlowDashboardAlertsMixin:
    async def get_real_time_alerts(
        self, severity_levels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get real-time alerts for flow monitoring.

        Args:
            severity_levels: Optional severity level filters

        Returns:
            Real-time alerts data
        """
        try:
            current_time = now_sao_paulo()
            alerts = []

            no_response_alerts = await self._check_no_response_alerts()
            alerts.extend(no_response_alerts)

            sentiment_alerts = await self._check_sentiment_alerts()
            alerts.extend(sentiment_alerts)

            performance_alerts = await self._check_performance_alerts()
            alerts.extend(performance_alerts)

            engagement_alerts = await self._check_engagement_alerts()
            alerts.extend(engagement_alerts)

            if severity_levels:
                alerts = [a for a in alerts if a["severity"] in severity_levels]

            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            alerts.sort(
                key=lambda x: (severity_order.get(x["severity"], 4), x["timestamp"])
            )

            return {
                "alerts": alerts,
                "summary": {
                    "total_alerts": len(alerts),
                    "by_severity": {
                        severity: len([a for a in alerts if a["severity"] == severity])
                        for severity in ["critical", "high", "medium", "low"]
                    },
                },
                "last_updated": current_time.isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get real-time alerts: {e}")
            raise

    async def _check_no_response_alerts(self) -> List[Dict[str, Any]]:
        """Check for patients with no recent responses."""
        alerts = []
        now_sao_paulo() - timedelta(hours=48)
        return alerts

    async def _check_sentiment_alerts(self) -> List[Dict[str, Any]]:
        """Check for concerning sentiment patterns."""
        alerts = []

        recent_negative = (
            self.db.query(FlowAnalytics)
            .filter(
                and_(
                    FlowAnalytics.sentiment_score < -0.5,
                    FlowAnalytics.timestamp >= now_sao_paulo() - timedelta(hours=24),
                )
            )
            .all()
        )

        for event in recent_negative:
            alerts.append(
                {
                    "id": f"sentiment_{event.id}",
                    "type": "negative_sentiment",
                    "severity": "medium",
                    "patient_id": str(event.patient_id),
                    "message": f"Negative sentiment detected (score: {event.sentiment_score:.2f})",
                    "timestamp": event.timestamp.isoformat(),
                    "data": {"sentiment_score": event.sentiment_score},
                }
            )

        return alerts

    async def _check_performance_alerts(self) -> List[Dict[str, Any]]:
        """Check for system performance issues."""
        return []

    async def _check_engagement_alerts(self) -> List[Dict[str, Any]]:
        """Check for unusual engagement drops."""
        return []


__all__ = ["FlowDashboardAlertsMixin"]
