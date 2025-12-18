"""
Flow Dashboard Service for real-time analytics and reporting.
Provides dashboard data, trend analysis, and optimization recommendations.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy import and_, desc
from enum import Enum

from app.services.analytics import (
    FlowAnalyticsService,
    EventType,
    RiskLevel,
    PatientRisk,
)
from app.models.flow_analytics import FlowAnalytics

logger = logging.getLogger(__name__)


class DashboardTimeframe(str, Enum):
    """Dashboard timeframe options."""

    LAST_24_HOURS = "24h"
    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"
    LAST_90_DAYS = "90d"
    CUSTOM = "custom"


class TrendDirection(str, Enum):
    """Trend direction indicators."""

    UP = "up"
    DOWN = "down"
    STABLE = "stable"
    UNKNOWN = "unknown"


class FlowDashboardService:
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
            # Calculate date range
            date_range = self._get_date_range(timeframe, custom_range)

            # Get basic metrics
            engagement_metrics = (
                await self.analytics_service.calculate_engagement_metrics(
                    date_range=date_range
                )
            )

            # Get at-risk patients
            at_risk_patients = await self.analytics_service.identify_at_risk_patients(
                lookback_days=(date_range[1] - date_range[0]).days
            )

            # Get flow type breakdown
            flow_type_metrics = await self._get_flow_type_breakdown(date_range)

            # Get trend analysis
            trends = await self._calculate_trends(date_range)

            # Get recent alerts
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
                        [
                            p
                            for p in at_risk_patients
                            if p.risk_level == RiskLevel.MEDIUM
                        ]
                    ),
                },
                "flow_type_breakdown": flow_type_metrics,
                "trends": trends,
                "recent_alerts": recent_alerts,
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get dashboard overview: {e}")
            raise

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

            # Get daily engagement metrics
            daily_metrics = await self._get_daily_engagement_metrics(
                date_range, flow_type
            )

            # Calculate trend direction
            trend_direction = self._calculate_trend_direction(
                daily_metrics, "response_rate"
            )

            # Get engagement distribution
            engagement_distribution = await self._get_engagement_distribution(
                date_range, flow_type
            )

            # Get top performing days/times
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

    async def get_at_risk_patient_dashboard(
        self,
        risk_levels: Optional[List[RiskLevel]] = None,
        flow_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive at-risk patient dashboard.

        Args:
            risk_levels: Optional risk level filters
            flow_type: Optional flow type filter

        Returns:
            At-risk patient dashboard data
        """
        try:
            # Get all at-risk patients
            all_at_risk = await self.analytics_service.identify_at_risk_patients(
                flow_type=flow_type, lookback_days=14
            )

            # Filter by risk levels if specified
            if risk_levels:
                at_risk_patients = [
                    p for p in all_at_risk if p.risk_level in risk_levels
                ]
            else:
                at_risk_patients = all_at_risk

            # Group by risk level
            risk_groups = {
                RiskLevel.CRITICAL: [],
                RiskLevel.HIGH: [],
                RiskLevel.MEDIUM: [],
                RiskLevel.LOW: [],
            }

            for patient in at_risk_patients:
                risk_groups[patient.risk_level].append(patient)

            # Get risk factor analysis
            risk_factor_analysis = self._analyze_risk_factors(at_risk_patients)

            # Get intervention recommendations
            interventions = await self._generate_intervention_recommendations(
                at_risk_patients
            )

            # Get historical risk trends
            risk_trends = await self._get_risk_trends()

            return {
                "summary": {
                    "total_at_risk": len(at_risk_patients),
                    "by_risk_level": {
                        level.value: len(patients)
                        for level, patients in risk_groups.items()
                    },
                    "flow_type_filter": flow_type,
                },
                "risk_groups": {
                    level.value: [
                        {
                            "patient_id": str(p.patient_id),
                            "risk_factors": p.risk_factors,
                            "last_response": p.last_response.isoformat()
                            if p.last_response
                            else None,
                            "recommended_actions": p.recommended_actions,
                        }
                        for p in patients
                    ]
                    for level, patients in risk_groups.items()
                },
                "risk_factor_analysis": risk_factor_analysis,
                "intervention_recommendations": interventions,
                "risk_trends": risk_trends,
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get at-risk patient dashboard: {e}")
            raise

    async def get_flow_optimization_recommendations(
        self, flow_type: str, analysis_days: int = 30
    ) -> Dict[str, Any]:
        """
        Generate flow optimization recommendations based on analytics.

        Args:
            flow_type: Flow type to analyze
            analysis_days: Days of data to analyze

        Returns:
            Flow optimization recommendations
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=analysis_days)

            # Get flow performance metrics
            performance_metrics = (
                await self.analytics_service.get_flow_performance_metrics(
                    flow_type=flow_type, date_range=(start_date, end_date)
                )
            )

            # Analyze message timing effectiveness
            timing_analysis = await self._analyze_message_timing(
                flow_type, (start_date, end_date)
            )

            # Analyze content effectiveness
            content_analysis = await self._analyze_content_effectiveness(
                flow_type, (start_date, end_date)
            )

            # Analyze drop-off points
            dropoff_analysis = await self._analyze_flow_dropoffs(
                flow_type, (start_date, end_date)
            )

            # Generate specific recommendations
            recommendations = self._generate_optimization_recommendations(
                performance_metrics, timing_analysis, content_analysis, dropoff_analysis
            )

            return {
                "flow_type": flow_type,
                "analysis_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": analysis_days,
                },
                "current_performance": performance_metrics,
                "timing_analysis": timing_analysis,
                "content_analysis": content_analysis,
                "dropoff_analysis": dropoff_analysis,
                "recommendations": recommendations,
                "priority_actions": self._prioritize_recommendations(recommendations),
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get flow optimization recommendations: {e}")
            raise

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
            current_time = datetime.utcnow()

            alerts = []

            # Check for patients with no recent responses
            no_response_alerts = await self._check_no_response_alerts()
            alerts.extend(no_response_alerts)

            # Check for concerning sentiment patterns
            sentiment_alerts = await self._check_sentiment_alerts()
            alerts.extend(sentiment_alerts)

            # Check for system performance issues
            performance_alerts = await self._check_performance_alerts()
            alerts.extend(performance_alerts)

            # Check for unusual engagement drops
            engagement_alerts = await self._check_engagement_alerts()
            alerts.extend(engagement_alerts)

            # Filter by severity if specified
            if severity_levels:
                alerts = [a for a in alerts if a["severity"] in severity_levels]

            # Sort by severity and timestamp
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

    def _get_date_range(
        self,
        timeframe: DashboardTimeframe,
        custom_range: Optional[Tuple[datetime, datetime]] = None,
    ) -> Tuple[datetime, datetime]:
        """Get date range based on timeframe."""
        if timeframe == DashboardTimeframe.CUSTOM and custom_range:
            return custom_range

        end_date = datetime.utcnow()

        if timeframe == DashboardTimeframe.LAST_24_HOURS:
            start_date = end_date - timedelta(hours=24)
        elif timeframe == DashboardTimeframe.LAST_7_DAYS:
            start_date = end_date - timedelta(days=7)
        elif timeframe == DashboardTimeframe.LAST_30_DAYS:
            start_date = end_date - timedelta(days=30)
        elif timeframe == DashboardTimeframe.LAST_90_DAYS:
            start_date = end_date - timedelta(days=90)
        else:
            start_date = end_date - timedelta(days=7)  # Default

        return (start_date, end_date)

    async def _get_flow_type_breakdown(
        self, date_range: Tuple[datetime, datetime]
    ) -> Dict[str, Any]:
        """Get breakdown of metrics by flow type."""
        flow_types = self.db.query(FlowAnalytics.flow_type).distinct().all()
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
        # Compare current period with previous period of same length
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
        if abs(current - previous) < 0.01:  # Less than 1% change
            return TrendDirection.STABLE
        elif current > previous:
            return TrendDirection.UP
        else:
            return TrendDirection.DOWN

    async def _get_recent_alerts(
        self, date_range: Tuple[datetime, datetime]
    ) -> List[Dict[str, Any]]:
        """Get recent alerts within date range."""
        # This would typically query an alerts table, but for now we'll generate based on analytics
        alerts = []

        # Check for concerning events
        concerning_events = (
            self.db.query(FlowAnalytics)
            .filter(
                and_(
                    FlowAnalytics.event_type == EventType.CONCERN_DETECTED,
                    FlowAnalytics.timestamp.between(date_range[0], date_range[1]),
                )
            )
            .order_by(desc(FlowAnalytics.timestamp))
            .limit(10)
            .all()
        )

        for event in concerning_events:
            alerts.append(
                {
                    "id": str(event.id),
                    "type": "patient_concern",
                    "severity": "high",
                    "patient_id": str(event.patient_id),
                    "message": f"Concerning response detected in {event.flow_type} flow",
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.event_data,
                }
            )

        return alerts

    async def _get_daily_engagement_metrics(
        self, date_range: Tuple[datetime, datetime], flow_type: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Get daily engagement metrics."""
        # This would involve complex queries to get daily breakdowns
        # For now, return a simplified structure
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

        # Simple linear trend calculation
        first_half = values[: len(values) // 2]
        second_half = values[len(values) // 2 :]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        if abs(second_avg - first_avg) < 0.01:
            return TrendDirection.STABLE
        elif second_avg > first_avg:
            return TrendDirection.UP
        else:
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
        # This would involve complex time-based analysis
        # For now, return a simplified structure
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

        # Add more insights based on data patterns
        if daily_metrics:
            avg_response_rate = sum(d["response_rate"] for d in daily_metrics) / len(
                daily_metrics
            )
            if avg_response_rate > 80:
                insights.append(
                    "Excellent response rates - current strategy is effective"
                )
            elif avg_response_rate < 50:
                insights.append(
                    "Low response rates - consider message timing or content adjustments"
                )

        return insights

    def _analyze_risk_factors(
        self, at_risk_patients: List[PatientRisk]
    ) -> Dict[str, Any]:
        """Analyze common risk factors."""
        all_factors = []
        for patient in at_risk_patients:
            all_factors.extend(patient.risk_factors)

        # Count factor frequency
        factor_counts = {}
        for factor in all_factors:
            # Normalize factor text for grouping
            normalized = factor.lower()
            if "no response" in normalized:
                key = "no_response"
            elif "low engagement" in normalized:
                key = "low_engagement"
            elif "negative sentiment" in normalized:
                key = "negative_sentiment"
            elif "concerning events" in normalized:
                key = "concerning_events"
            else:
                key = "other"

            factor_counts[key] = factor_counts.get(key, 0) + 1

        return {
            "most_common_factors": factor_counts,
            "total_risk_factors": len(all_factors),
            "patients_analyzed": len(at_risk_patients),
        }

    async def _generate_intervention_recommendations(
        self, at_risk_patients: List[PatientRisk]
    ) -> List[Dict[str, Any]]:
        """Generate intervention recommendations for at-risk patients."""
        recommendations = []

        # Group by risk level
        critical_patients = [
            p for p in at_risk_patients if p.risk_level == RiskLevel.CRITICAL
        ]
        high_risk_patients = [
            p for p in at_risk_patients if p.risk_level == RiskLevel.HIGH
        ]

        if critical_patients:
            recommendations.append(
                {
                    "priority": "immediate",
                    "action": "Healthcare provider outreach",
                    "description": f"Contact {len(critical_patients)} critical risk patients immediately",
                    "patient_count": len(critical_patients),
                    "estimated_time": "2-4 hours",
                }
            )

        if high_risk_patients:
            recommendations.append(
                {
                    "priority": "high",
                    "action": "Personalized re-engagement",
                    "description": f"Send personalized messages to {len(high_risk_patients)} high-risk patients",
                    "patient_count": len(high_risk_patients),
                    "estimated_time": "1-2 hours",
                }
            )

        return recommendations

    async def _get_risk_trends(self) -> Dict[str, Any]:
        """Get historical risk trends."""
        # This would involve complex historical analysis
        # For now, return a simplified structure
        return {
            "trend_direction": "stable",
            "weekly_risk_counts": [],
            "risk_level_changes": {},
        }

    async def _analyze_message_timing(
        self, flow_type: str, date_range: Tuple[datetime, datetime]
    ) -> Dict[str, Any]:
        """Analyze message timing effectiveness."""
        # This would involve complex timing analysis
        return {
            "optimal_send_times": ["10:00", "14:00", "16:00"],
            "response_rates_by_hour": {},
            "recommendations": [
                "Send messages between 10 AM and 4 PM for best response rates"
            ],
        }

    async def _analyze_content_effectiveness(
        self, flow_type: str, date_range: Tuple[datetime, datetime]
    ) -> Dict[str, Any]:
        """Analyze content effectiveness."""
        return {
            "high_performing_templates": [],
            "low_performing_templates": [],
            "sentiment_by_template": {},
            "recommendations": ["Consider A/B testing different message approaches"],
        }

    async def _analyze_flow_dropoffs(
        self, flow_type: str, date_range: Tuple[datetime, datetime]
    ) -> Dict[str, Any]:
        """Analyze flow drop-off points."""
        return {
            "common_dropoff_days": [7, 14, 21],
            "dropoff_rates_by_day": {},
            "recommendations": ["Add engagement boosters at days 7 and 14"],
        }

    def _generate_optimization_recommendations(
        self,
        performance_metrics: Dict[str, Any],
        timing_analysis: Dict[str, Any],
        content_analysis: Dict[str, Any],
        dropoff_analysis: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Generate optimization recommendations."""
        recommendations = []

        # Response rate recommendations
        response_rate = performance_metrics.get("overview", {}).get("response_rate", 0)
        if response_rate < 70:
            recommendations.append(
                {
                    "category": "engagement",
                    "priority": "high",
                    "title": "Improve Response Rates",
                    "description": f"Current response rate is {response_rate:.1f}%. Consider message timing and content optimization.",
                    "actions": [
                        "Review message timing",
                        "A/B test message content",
                        "Personalize messages more",
                    ],
                }
            )

        # Timing recommendations
        recommendations.extend(
            [
                {
                    "category": "timing",
                    "priority": "medium",
                    "title": "Optimize Message Timing",
                    "description": "Send messages during peak engagement hours",
                    "actions": timing_analysis.get("recommendations", []),
                }
            ]
        )

        return recommendations

    def _prioritize_recommendations(
        self, recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Prioritize recommendations by impact and effort."""
        priority_order = {"high": 0, "medium": 1, "low": 2}
        return sorted(
            recommendations,
            key=lambda x: priority_order.get(x.get("priority", "low"), 3),
        )

    async def _check_no_response_alerts(self) -> List[Dict[str, Any]]:
        """Check for patients with no recent responses."""
        alerts = []

        # Get patients with no responses in last 48 hours
        datetime.utcnow() - timedelta(hours=48)

        # This would involve complex queries
        # For now, return empty list
        return alerts

    async def _check_sentiment_alerts(self) -> List[Dict[str, Any]]:
        """Check for concerning sentiment patterns."""
        alerts = []

        # Get recent negative sentiment patterns
        recent_negative = (
            self.db.query(FlowAnalytics)
            .filter(
                and_(
                    FlowAnalytics.sentiment_score < -0.5,
                    FlowAnalytics.timestamp >= datetime.utcnow() - timedelta(hours=24),
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
        # This would check system metrics
        return []

    async def _check_engagement_alerts(self) -> List[Dict[str, Any]]:
        """Check for unusual engagement drops."""
        # This would check for sudden engagement drops
        return []


# Global service instance
_flow_dashboard_service: Optional[FlowDashboardService] = None


def get_flow_dashboard_service(db: Any) -> FlowDashboardService:
    """
    Get flow dashboard service instance.

    Args:
        db: Database session

    Returns:
        FlowDashboardService instance
    """
    return FlowDashboardService(db)
