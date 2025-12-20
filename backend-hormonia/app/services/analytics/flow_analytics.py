"""
Flow Analytics Service for tracking and analyzing conversation flow performance.
Implements comprehensive event tracking, engagement metrics, and patient risk identification.
"""

import logging
from typing import List, Optional, Any, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, and_, desc
from uuid import UUID
from enum import Enum

from app.models.flow import PatientFlowState
from app.models.flow_analytics import FlowAnalytics, FlowMessage
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Flow analytics event types."""

    MESSAGE_SENT = "message_sent"
    MESSAGE_DELIVERED = "message_delivered"
    MESSAGE_READ = "message_read"
    RESPONSE_RECEIVED = "response_received"
    FLOW_STARTED = "flow_started"
    FLOW_COMPLETED = "flow_completed"
    FLOW_PAUSED = "flow_paused"
    FLOW_RESUMED = "flow_resumed"
    FLOW_ADVANCED = "flow_advanced"
    PATIENT_ENGAGED = "patient_engaged"
    PATIENT_DISENGAGED = "patient_disengaged"
    CONCERN_DETECTED = "concern_detected"
    FOLLOW_UP_TRIGGERED = "follow_up_triggered"


class RiskLevel(str, Enum):
    """Patient risk levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PatientRisk:
    """Patient risk assessment result."""

    def __init__(
        self,
        patient_id: UUID,
        risk_level: RiskLevel,
        risk_factors: List[str],
        last_response: Optional[datetime] = None,
        recommended_actions: List[str] = None,
    ):
        self.patient_id = patient_id
        self.risk_level = risk_level
        self.risk_factors = risk_factors
        self.last_response = last_response
        self.recommended_actions = recommended_actions or []


class EngagementMetrics:
    """Engagement metrics container."""

    def __init__(self):
        self.total_messages_sent = 0
        self.total_responses_received = 0
        self.response_rate = 0.0
        self.average_response_time = None
        self.sentiment_distribution = {}
        self.completion_rates = {}
        self.engagement_score = 0.0


class FlowAnalyticsService:
    """
    Service for tracking and analyzing conversation flow performance.
    Provides comprehensive analytics, engagement metrics, and risk identification.
    """

    def __init__(self, db: Any):
        """
        Initialize flow analytics service.

        Args:
            db: Database session
        """
        self.db = db
        self.analytics_repo = BaseRepository(FlowAnalytics, db)
        self.flow_message_repo = BaseRepository(FlowMessage, db)

        logger.info("Flow Analytics Service initialized")

    async def track_message_sent(
        self,
        patient_id: UUID,
        message_id: UUID,
        flow_type: str,
        flow_day: int,
        template_id: str,
        additional_data: Optional[dict[str, Any]] = None,
    ) -> FlowAnalytics:
        """
        Track message sent event.

        Args:
            patient_id: Patient UUID
            message_id: Message UUID
            flow_type: Flow type
            flow_day: Current flow day
            template_id: Template identifier
            additional_data: Additional event data

        Returns:
            Created analytics record
        """
        try:
            event_data = {
                "message_id": str(message_id),
                "template_id": template_id,
                **(additional_data or {}),
            }

            analytics = FlowAnalytics(
                patient_id=patient_id,
                flow_type=flow_type,
                flow_day=flow_day,
                event_type=EventType.MESSAGE_SENT,
                event_data=event_data,
                timestamp=datetime.now(timezone.utc),
            )

            self.db.add(analytics)
            self.db.commit()
            self.db.refresh(analytics)

            logger.info(
                f"Tracked message sent for patient {patient_id} on day {flow_day}"
            )
            return analytics

        except Exception as e:
            logger.error(f"Failed to track message sent: {e}")
            self.db.rollback()
            raise

    async def track_response_received(
        self,
        patient_id: UUID,
        message_id: Optional[UUID],
        flow_type: str,
        flow_day: int,
        response_text: str,
        sentiment_score: Optional[float] = None,
        engagement_score: Optional[float] = None,
        response_time_seconds: Optional[int] = None,
        additional_data: Optional[dict[str, Any]] = None,
    ) -> FlowAnalytics:
        """
        Track patient response received event.

        Args:
            patient_id: Patient UUID
            message_id: Original message UUID (optional)
            flow_type: Flow type
            flow_day: Current flow day
            response_text: Patient response text
            sentiment_score: Sentiment analysis score (-1 to 1)
            engagement_score: Engagement score (0 to 1)
            response_time_seconds: Time to respond in seconds
            additional_data: Additional event data

        Returns:
            Created analytics record
        """
        try:
            event_data = {
                "original_message_id": str(message_id) if message_id else None,
                "response_length": len(response_text),
                "response_word_count": len(response_text.split()),
                **(additional_data or {}),
            }

            analytics = FlowAnalytics(
                patient_id=patient_id,
                flow_type=flow_type,
                flow_day=flow_day,
                event_type=EventType.RESPONSE_RECEIVED,
                event_data=event_data,
                sentiment_score=sentiment_score,
                engagement_score=engagement_score,
                response_time_seconds=response_time_seconds,
                timestamp=datetime.now(timezone.utc),
            )

            self.db.add(analytics)
            self.db.commit()
            self.db.refresh(analytics)

            logger.info(
                f"Tracked response received for patient {patient_id} on day {flow_day}"
            )
            return analytics

        except Exception as e:
            logger.error(f"Failed to track response received: {e}")
            self.db.rollback()
            raise

    async def track_flow_event(
        self,
        patient_id: UUID,
        flow_type: str,
        flow_day: int,
        event_type: EventType,
        event_data: Optional[dict[str, Any]] = None,
    ) -> FlowAnalytics:
        """
        Track general flow event.

        Args:
            patient_id: Patient UUID
            flow_type: Flow type
            flow_day: Current flow day
            event_type: Type of event
            event_data: Event-specific data

        Returns:
            Created analytics record
        """
        try:
            analytics = FlowAnalytics(
                patient_id=patient_id,
                flow_type=flow_type,
                flow_day=flow_day,
                event_type=event_type,
                event_data=event_data or {},
                timestamp=datetime.now(timezone.utc),
            )

            self.db.add(analytics)
            self.db.commit()
            self.db.refresh(analytics)

            logger.info(f"Tracked flow event {event_type} for patient {patient_id}")
            return analytics

        except Exception as e:
            logger.error(f"Failed to track flow event: {e}")
            self.db.rollback()
            raise

    async def calculate_engagement_metrics(
        self,
        flow_type: Optional[str] = None,
        date_range: Optional[Tuple[datetime, datetime]] = None,
    ) -> EngagementMetrics:
        """
        Calculate comprehensive engagement metrics.

        Args:
            flow_type: Optional flow type filter
            date_range: Optional date range (start, end)

        Returns:
            Engagement metrics
        """
        try:
            # Default to last 30 days if no range provided
            if not date_range:
                end_date = datetime.now(timezone.utc)
                start_date = end_date - timedelta(days=30)
                date_range = (start_date, end_date)

            metrics = EngagementMetrics()

            # Build base query
            query = self.db.query(FlowAnalytics).filter(
                FlowAnalytics.timestamp.between(date_range[0], date_range[1])
            )

            if flow_type:
                query = query.filter(FlowAnalytics.flow_type == flow_type)

            # Calculate message metrics
            messages_sent = query.filter(
                FlowAnalytics.event_type == EventType.MESSAGE_SENT
            ).count()

            responses_received = query.filter(
                FlowAnalytics.event_type == EventType.RESPONSE_RECEIVED
            ).count()

            metrics.total_messages_sent = messages_sent
            metrics.total_responses_received = responses_received
            metrics.response_rate = (
                (responses_received / messages_sent * 100) if messages_sent > 0 else 0.0
            )

            # Calculate average response time
            response_times = (
                query.filter(
                    and_(
                        FlowAnalytics.event_type == EventType.RESPONSE_RECEIVED,
                        FlowAnalytics.response_time_seconds.isnot(None),
                    )
                )
                .with_entities(FlowAnalytics.response_time_seconds)
                .all()
            )

            if response_times:
                avg_response_time = sum(rt[0] for rt in response_times) / len(
                    response_times
                )
                metrics.average_response_time = timedelta(seconds=avg_response_time)

            # Calculate sentiment distribution
            sentiment_data = (
                query.filter(
                    and_(
                        FlowAnalytics.event_type == EventType.RESPONSE_RECEIVED,
                        FlowAnalytics.sentiment_score.isnot(None),
                    )
                )
                .with_entities(FlowAnalytics.sentiment_score)
                .all()
            )

            if sentiment_data:
                positive = sum(1 for s in sentiment_data if s[0] > 0.1)
                neutral = sum(1 for s in sentiment_data if -0.1 <= s[0] <= 0.1)
                negative = sum(1 for s in sentiment_data if s[0] < -0.1)
                total = len(sentiment_data)

                metrics.sentiment_distribution = {
                    "positive": positive / total * 100,
                    "neutral": neutral / total * 100,
                    "negative": negative / total * 100,
                }

            # Calculate completion rates by flow type
            flow_types = self.db.query(FlowAnalytics.flow_type).distinct().all()

            for ft in flow_types:
                flow_type_name = ft[0]

                started = query.filter(
                    and_(
                        FlowAnalytics.flow_type == flow_type_name,
                        FlowAnalytics.event_type == EventType.FLOW_STARTED,
                    )
                ).count()

                completed = query.filter(
                    and_(
                        FlowAnalytics.flow_type == flow_type_name,
                        FlowAnalytics.event_type == EventType.FLOW_COMPLETED,
                    )
                ).count()

                completion_rate = (completed / started * 100) if started > 0 else 0.0
                metrics.completion_rates[flow_type_name] = completion_rate

            # Calculate overall engagement score
            engagement_scores = (
                query.filter(FlowAnalytics.engagement_score.isnot(None))
                .with_entities(FlowAnalytics.engagement_score)
                .all()
            )

            if engagement_scores:
                metrics.engagement_score = sum(es[0] for es in engagement_scores) / len(
                    engagement_scores
                )

            logger.info(
                f"Calculated engagement metrics: {metrics.response_rate:.1f}% response rate"
            )
            return metrics

        except Exception as e:
            logger.error(f"Failed to calculate engagement metrics: {e}")
            raise

    async def identify_at_risk_patients(
        self, flow_type: Optional[str] = None, lookback_days: int = 7
    ) -> List[PatientRisk]:
        """
        Identify patients at risk based on interaction patterns.

        Args:
            flow_type: Optional flow type filter
            lookback_days: Days to look back for analysis

        Returns:
            List of at-risk patients
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)
            at_risk_patients = []

            # Get all active patients
            active_patients_query = self.db.query(PatientFlowState).filter(
                PatientFlowState.completed_at.is_(None)
            )

            if flow_type:
                active_patients_query = active_patients_query.filter(
                    PatientFlowState.flow_type == flow_type
                )

            active_patients = active_patients_query.all()

            for flow_state in active_patients:
                patient_id = flow_state.patient_id
                risk_factors = []
                risk_level = RiskLevel.LOW

                # Check for lack of recent responses
                last_response = (
                    self.db.query(FlowAnalytics)
                    .filter(
                        and_(
                            FlowAnalytics.patient_id == patient_id,
                            FlowAnalytics.event_type == EventType.RESPONSE_RECEIVED,
                        )
                    )
                    .order_by(desc(FlowAnalytics.timestamp))
                    .first()
                )

                if not last_response:
                    risk_factors.append("No responses recorded")
                    risk_level = RiskLevel.HIGH
                elif last_response.timestamp < cutoff_date:
                    days_since_response = (
                        datetime.now(timezone.utc) - last_response.timestamp
                    ).days
                    risk_factors.append(f"No response for {days_since_response} days")
                    if days_since_response > 14:
                        risk_level = RiskLevel.HIGH
                    elif days_since_response > 7:
                        risk_level = RiskLevel.MEDIUM

                # Check for declining engagement
                recent_engagement = (
                    self.db.query(FlowAnalytics)
                    .filter(
                        and_(
                            FlowAnalytics.patient_id == patient_id,
                            FlowAnalytics.timestamp >= cutoff_date,
                            FlowAnalytics.engagement_score.isnot(None),
                        )
                    )
                    .with_entities(FlowAnalytics.engagement_score)
                    .all()
                )

                if recent_engagement:
                    avg_engagement = sum(e[0] for e in recent_engagement) / len(
                        recent_engagement
                    )
                    if avg_engagement < 0.3:
                        risk_factors.append(
                            f"Low engagement score: {avg_engagement:.2f}"
                        )
                        if risk_level == RiskLevel.LOW:
                            risk_level = RiskLevel.MEDIUM

                # Check for negative sentiment patterns
                recent_sentiment = (
                    self.db.query(FlowAnalytics)
                    .filter(
                        and_(
                            FlowAnalytics.patient_id == patient_id,
                            FlowAnalytics.timestamp >= cutoff_date,
                            FlowAnalytics.sentiment_score.isnot(None),
                        )
                    )
                    .with_entities(FlowAnalytics.sentiment_score)
                    .all()
                )

                if recent_sentiment:
                    negative_responses = sum(1 for s in recent_sentiment if s[0] < -0.3)
                    if negative_responses > len(recent_sentiment) * 0.5:
                        risk_factors.append("Predominantly negative sentiment")
                        if risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]:
                            risk_level = RiskLevel.HIGH

                # Check for concerning events
                concerning_events = (
                    self.db.query(FlowAnalytics)
                    .filter(
                        and_(
                            FlowAnalytics.patient_id == patient_id,
                            FlowAnalytics.timestamp >= cutoff_date,
                            FlowAnalytics.event_type == EventType.CONCERN_DETECTED,
                        )
                    )
                    .count()
                )

                if concerning_events > 0:
                    risk_factors.append(
                        f"{concerning_events} concerning events detected"
                    )
                    risk_level = RiskLevel.CRITICAL

                # Generate recommended actions
                recommended_actions = self._generate_risk_recommendations(
                    risk_level, risk_factors
                )

                # Only include patients with identified risks
                if risk_factors:
                    patient_risk = PatientRisk(
                        patient_id=patient_id,
                        risk_level=risk_level,
                        risk_factors=risk_factors,
                        last_response=last_response.timestamp
                        if last_response
                        else None,
                        recommended_actions=recommended_actions,
                    )
                    at_risk_patients.append(patient_risk)

            # Sort by risk level (critical first)
            risk_order = {
                RiskLevel.CRITICAL: 0,
                RiskLevel.HIGH: 1,
                RiskLevel.MEDIUM: 2,
                RiskLevel.LOW: 3,
            }
            at_risk_patients.sort(key=lambda x: risk_order[x.risk_level])

            logger.info(f"Identified {len(at_risk_patients)} at-risk patients")
            return at_risk_patients

        except Exception as e:
            logger.error(f"Failed to identify at-risk patients: {e}")
            raise

    def _generate_risk_recommendations(
        self, risk_level: RiskLevel, risk_factors: List[str]
    ) -> List[str]:
        """Generate recommended actions based on risk level and factors."""
        recommendations = []

        if risk_level == RiskLevel.CRITICAL:
            recommendations.extend(
                [
                    "Immediate healthcare provider notification required",
                    "Schedule urgent follow-up call",
                    "Review patient's medical status",
                ]
            )
        elif risk_level == RiskLevel.HIGH:
            recommendations.extend(
                [
                    "Healthcare provider should review patient status",
                    "Consider personalized outreach",
                    "Adjust message frequency or content",
                ]
            )
        elif risk_level == RiskLevel.MEDIUM:
            recommendations.extend(
                [
                    "Monitor patient engagement closely",
                    "Consider sending engagement-boosting message",
                    "Review message timing preferences",
                ]
            )

        # Factor-specific recommendations
        if "No response" in str(risk_factors):
            recommendations.append("Send re-engagement message with different approach")

        if "Low engagement" in str(risk_factors):
            recommendations.append("Personalize messages based on patient preferences")

        if "negative sentiment" in str(risk_factors):
            recommendations.append("Focus on supportive and empathetic messaging")

        return recommendations

    async def get_flow_performance_metrics(
        self, flow_type: str, date_range: Optional[Tuple[datetime, datetime]] = None
    ) -> dict[str, Any]:
        """
        Get comprehensive performance metrics for a specific flow type.

        Args:
            flow_type: Flow type to analyze
            date_range: Optional date range

        Returns:
            Flow performance metrics
        """
        try:
            if not date_range:
                end_date = datetime.now(timezone.utc)
                start_date = end_date - timedelta(days=30)
                date_range = (start_date, end_date)

            # Base query for this flow type
            query = self.db.query(FlowAnalytics).filter(
                and_(
                    FlowAnalytics.flow_type == flow_type,
                    FlowAnalytics.timestamp.between(date_range[0], date_range[1]),
                )
            )

            # Basic metrics
            total_events = query.count()
            unique_patients = (
                query.with_entities(FlowAnalytics.patient_id).distinct().count()
            )

            # Message metrics
            messages_sent = query.filter(
                FlowAnalytics.event_type == EventType.MESSAGE_SENT
            ).count()
            responses_received = query.filter(
                FlowAnalytics.event_type == EventType.RESPONSE_RECEIVED
            ).count()

            # Flow completion metrics
            flows_started = query.filter(
                FlowAnalytics.event_type == EventType.FLOW_STARTED
            ).count()
            flows_completed = query.filter(
                FlowAnalytics.event_type == EventType.FLOW_COMPLETED
            ).count()

            # Day-by-day breakdown
            day_metrics = {}
            max_day = (
                query.with_entities(func.max(FlowAnalytics.flow_day)).scalar() or 0
            )

            for day in range(1, max_day + 1):
                day_query = query.filter(FlowAnalytics.flow_day == day)
                day_messages = day_query.filter(
                    FlowAnalytics.event_type == EventType.MESSAGE_SENT
                ).count()
                day_responses = day_query.filter(
                    FlowAnalytics.event_type == EventType.RESPONSE_RECEIVED
                ).count()

                day_metrics[f"day_{day}"] = {
                    "messages_sent": day_messages,
                    "responses_received": day_responses,
                    "response_rate": (day_responses / day_messages * 100)
                    if day_messages > 0
                    else 0.0,
                }

            # Sentiment analysis
            sentiment_data = (
                query.filter(FlowAnalytics.sentiment_score.isnot(None))
                .with_entities(FlowAnalytics.sentiment_score)
                .all()
            )

            sentiment_metrics = {}
            if sentiment_data:
                scores = [s[0] for s in sentiment_data]
                sentiment_metrics = {
                    "average_sentiment": sum(scores) / len(scores),
                    "positive_responses": sum(1 for s in scores if s > 0.1),
                    "neutral_responses": sum(1 for s in scores if -0.1 <= s <= 0.1),
                    "negative_responses": sum(1 for s in scores if s < -0.1),
                }

            return {
                "flow_type": flow_type,
                "date_range": {
                    "start": date_range[0].isoformat(),
                    "end": date_range[1].isoformat(),
                },
                "overview": {
                    "total_events": total_events,
                    "unique_patients": unique_patients,
                    "messages_sent": messages_sent,
                    "responses_received": responses_received,
                    "response_rate": (responses_received / messages_sent * 100)
                    if messages_sent > 0
                    else 0.0,
                    "flows_started": flows_started,
                    "flows_completed": flows_completed,
                    "completion_rate": (flows_completed / flows_started * 100)
                    if flows_started > 0
                    else 0.0,
                },
                "daily_breakdown": day_metrics,
                "sentiment_analysis": sentiment_metrics,
            }

        except Exception as e:
            logger.error(f"Failed to get flow performance metrics: {e}")
            raise

    async def get_patient_analytics_summary(
        self, patient_id: UUID, lookback_days: int = 30
    ) -> dict[str, Any]:
        """
        Get comprehensive analytics summary for a specific patient.

        Args:
            patient_id: Patient UUID
            lookback_days: Days to look back

        Returns:
            Patient analytics summary
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)

            # Get patient's analytics data
            analytics_data = (
                self.db.query(FlowAnalytics)
                .filter(
                    and_(
                        FlowAnalytics.patient_id == patient_id,
                        FlowAnalytics.timestamp >= cutoff_date,
                    )
                )
                .order_by(desc(FlowAnalytics.timestamp))
                .all()
            )

            if not analytics_data:
                return {
                    "patient_id": str(patient_id),
                    "message": "No analytics data found for this patient",
                    "summary": {},
                }

            # Calculate metrics
            messages_received = sum(
                1 for a in analytics_data if a.event_type == EventType.MESSAGE_SENT
            )
            responses_sent = sum(
                1 for a in analytics_data if a.event_type == EventType.RESPONSE_RECEIVED
            )

            # Sentiment analysis
            sentiment_scores = [
                a.sentiment_score
                for a in analytics_data
                if a.sentiment_score is not None
            ]
            avg_sentiment = (
                sum(sentiment_scores) / len(sentiment_scores)
                if sentiment_scores
                else None
            )

            # Engagement analysis
            engagement_scores = [
                a.engagement_score
                for a in analytics_data
                if a.engagement_score is not None
            ]
            avg_engagement = (
                sum(engagement_scores) / len(engagement_scores)
                if engagement_scores
                else None
            )

            # Response time analysis
            response_times = [
                a.response_time_seconds
                for a in analytics_data
                if a.response_time_seconds is not None
            ]
            avg_response_time = (
                sum(response_times) / len(response_times) if response_times else None
            )

            # Recent activity
            last_message = next(
                (a for a in analytics_data if a.event_type == EventType.MESSAGE_SENT),
                None,
            )
            last_response = next(
                (
                    a
                    for a in analytics_data
                    if a.event_type == EventType.RESPONSE_RECEIVED
                ),
                None,
            )

            return {
                "patient_id": str(patient_id),
                "analysis_period": {
                    "start_date": cutoff_date.isoformat(),
                    "end_date": datetime.now(timezone.utc).isoformat(),
                    "days": lookback_days,
                },
                "engagement_summary": {
                    "messages_received": messages_received,
                    "responses_sent": responses_sent,
                    "response_rate": (responses_sent / messages_received * 100)
                    if messages_received > 0
                    else 0.0,
                    "average_engagement_score": avg_engagement,
                    "average_response_time_seconds": avg_response_time,
                },
                "sentiment_analysis": {
                    "average_sentiment_score": avg_sentiment,
                    "sentiment_trend": self._calculate_sentiment_trend(
                        sentiment_scores
                    ),
                    "total_sentiment_data_points": len(sentiment_scores),
                },
                "recent_activity": {
                    "last_message_sent": last_message.timestamp.isoformat()
                    if last_message
                    else None,
                    "last_response_received": last_response.timestamp.isoformat()
                    if last_response
                    else None,
                    "days_since_last_response": (
                        datetime.now(timezone.utc) - last_response.timestamp
                    ).days
                    if last_response
                    else None,
                },
                "flow_progress": {
                    "current_flow_type": analytics_data[0].flow_type
                    if analytics_data
                    else None,
                    "current_flow_day": analytics_data[0].flow_day
                    if analytics_data
                    else None,
                },
            }

        except Exception as e:
            logger.error(f"Failed to get patient analytics summary: {e}")
            raise

    def _calculate_sentiment_trend(self, sentiment_scores: List[float]) -> str:
        """Calculate sentiment trend from scores."""
        if len(sentiment_scores) < 2:
            return "insufficient_data"

        # Compare first half with second half
        mid_point = len(sentiment_scores) // 2
        first_half_avg = sum(sentiment_scores[:mid_point]) / mid_point
        second_half_avg = sum(sentiment_scores[mid_point:]) / (
            len(sentiment_scores) - mid_point
        )

        difference = second_half_avg - first_half_avg

        if difference > 0.1:
            return "improving"
        elif difference < -0.1:
            return "declining"
        else:
            return "stable"

    async def cleanup_old_analytics(self, days_to_keep: int = 90) -> int:
        """
        Clean up old analytics data.

        Args:
            days_to_keep: Number of days of data to keep

        Returns:
            Number of records deleted
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

            deleted_count = (
                self.db.query(FlowAnalytics)
                .filter(FlowAnalytics.timestamp < cutoff_date)
                .delete()
            )

            self.db.commit()

            logger.info(f"Cleaned up {deleted_count} old analytics records")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old analytics: {e}")
            self.db.rollback()
            raise
