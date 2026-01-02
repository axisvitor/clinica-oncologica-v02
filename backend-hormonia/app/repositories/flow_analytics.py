"""
Flow Analytics Repository for database operations.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, asc
from uuid import UUID

from app.models.flow import FlowAnalytics, FlowMessage
from app.repositories.base import BaseRepository


class FlowAnalyticsRepository(BaseRepository[FlowAnalytics]):
    """Repository for flow analytics operations."""

    def __init__(self, db: Session):
        super().__init__(FlowAnalytics, db)

    def get_by_patient_and_date_range(
        self, patient_id: UUID, start_date: datetime, end_date: datetime
    ) -> List[FlowAnalytics]:
        """Get analytics records for patient within date range."""
        return (
            self.db.query(FlowAnalytics)
            .filter(
                and_(
                    FlowAnalytics.patient_id == patient_id,
                    FlowAnalytics.timestamp.between(start_date, end_date),
                )
            )
            .order_by(desc(FlowAnalytics.timestamp))
            .all()
        )

    def get_by_flow_type_and_date_range(
        self, flow_type: str, start_date: datetime, end_date: datetime
    ) -> List[FlowAnalytics]:
        """Get analytics records for flow type within date range."""
        return (
            self.db.query(FlowAnalytics)
            .filter(
                and_(
                    FlowAnalytics.flow_type == flow_type,
                    FlowAnalytics.timestamp.between(start_date, end_date),
                )
            )
            .order_by(desc(FlowAnalytics.timestamp))
            .all()
        )

    def get_event_counts_by_type(
        self,
        flow_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Get event counts grouped by event type."""
        query = self.db.query(
            FlowAnalytics.event_type, func.count(FlowAnalytics.id).label("count")
        )

        if flow_type:
            query = query.filter(FlowAnalytics.flow_type == flow_type)

        if start_date and end_date:
            query = query.filter(FlowAnalytics.timestamp.between(start_date, end_date))

        results = query.group_by(FlowAnalytics.event_type).all()
        return {event_type: count for event_type, count in results}

    def get_daily_metrics(
        self, flow_type: str, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get daily metrics for a flow type."""
        query = (
            self.db.query(
                func.date(FlowAnalytics.timestamp).label("date"),
                FlowAnalytics.event_type,
                func.count(FlowAnalytics.id).label("count"),
            )
            .filter(
                and_(
                    FlowAnalytics.flow_type == flow_type,
                    FlowAnalytics.timestamp.between(start_date, end_date),
                )
            )
            .group_by(func.date(FlowAnalytics.timestamp), FlowAnalytics.event_type)
            .order_by(func.date(FlowAnalytics.timestamp))
        )

        results = query.all()

        # Organize by date
        daily_metrics = {}
        for date, event_type, count in results:
            date_str = date.isoformat()
            if date_str not in daily_metrics:
                daily_metrics[date_str] = {}
            daily_metrics[date_str][event_type] = count

        return [{"date": date, **metrics} for date, metrics in daily_metrics.items()]

    def get_patient_engagement_scores(
        self, patient_ids: List[UUID], start_date: datetime, end_date: datetime
    ) -> Dict[UUID, float]:
        """Get average engagement scores for patients."""
        query = (
            self.db.query(
                FlowAnalytics.patient_id,
                func.avg(FlowAnalytics.engagement_score).label("avg_engagement"),
            )
            .filter(
                and_(
                    FlowAnalytics.patient_id.in_(patient_ids),
                    FlowAnalytics.engagement_score.isnot(None),
                    FlowAnalytics.timestamp.between(start_date, end_date),
                )
            )
            .group_by(FlowAnalytics.patient_id)
        )

        results = query.all()
        return {
            patient_id: float(avg_engagement) for patient_id, avg_engagement in results
        }

    def get_sentiment_distribution(
        self,
        flow_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Get sentiment score distribution."""
        query = self.db.query(FlowAnalytics.sentiment_score).filter(
            FlowAnalytics.sentiment_score.isnot(None)
        )

        if flow_type:
            query = query.filter(FlowAnalytics.flow_type == flow_type)

        if start_date and end_date:
            query = query.filter(FlowAnalytics.timestamp.between(start_date, end_date))

        scores = [score[0] for score in query.all()]

        if not scores:
            return {"positive": 0, "neutral": 0, "negative": 0}

        positive = sum(1 for s in scores if s > 0.1)
        neutral = sum(1 for s in scores if -0.1 <= s <= 0.1)
        negative = sum(1 for s in scores if s < -0.1)

        return {"positive": positive, "neutral": neutral, "negative": negative}

    def get_response_time_stats(
        self,
        flow_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """Get response time statistics."""
        query = self.db.query(FlowAnalytics.response_time_seconds).filter(
            FlowAnalytics.response_time_seconds.isnot(None)
        )

        if flow_type:
            query = query.filter(FlowAnalytics.flow_type == flow_type)

        if start_date and end_date:
            query = query.filter(FlowAnalytics.timestamp.between(start_date, end_date))

        times = [time[0] for time in query.all()]

        if not times:
            return {"avg": 0.0, "min": 0.0, "max": 0.0, "median": 0.0}

        times.sort()
        n = len(times)

        return {
            "avg": sum(times) / n,
            "min": min(times),
            "max": max(times),
            "median": times[n // 2]
            if n % 2 == 1
            else (times[n // 2 - 1] + times[n // 2]) / 2,
        }

    def delete_old_records(self, cutoff_date: datetime) -> int:
        """Delete analytics records older than cutoff date."""
        deleted_count = (
            self.db.query(FlowAnalytics)
            .filter(FlowAnalytics.timestamp < cutoff_date)
            .delete()
        )

        return deleted_count


class FlowMessageRepository(BaseRepository[FlowMessage]):
    """Repository for flow message operations."""

    def __init__(self, db: Session):
        super().__init__(FlowMessage, db)

    def get_by_flow_state(self, flow_state_id: UUID) -> List[FlowMessage]:
        """Get all messages for a flow state."""
        return (
            self.db.query(FlowMessage)
            .filter(FlowMessage.flow_state_id == flow_state_id)
            .order_by(asc(FlowMessage.flow_day))
            .all()
        )

    def get_delivery_metrics(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Get message delivery metrics."""
        query = self.db.query(FlowMessage).filter(
            FlowMessage.scheduled_for.between(start_date, end_date)
        )

        total_scheduled = query.count()
        sent = query.filter(FlowMessage.sent_at.isnot(None)).count()
        delivered = query.filter(FlowMessage.delivered_at.isnot(None)).count()
        read = query.filter(FlowMessage.read_at.isnot(None)).count()

        # Calculate average delivery times
        delivery_times = (
            query.filter(
                and_(
                    FlowMessage.sent_at.isnot(None),
                    FlowMessage.delivered_at.isnot(None),
                )
            )
            .with_entities(
                (
                    func.extract("epoch", FlowMessage.delivered_at)
                    - func.extract("epoch", FlowMessage.sent_at)
                ).label("delivery_time")
            )
            .all()
        )

        avg_delivery_time = None
        if delivery_times:
            avg_delivery_time = sum(dt[0] for dt in delivery_times) / len(
                delivery_times
            )

        return {
            "total_scheduled": total_scheduled,
            "sent": sent,
            "delivered": delivered,
            "read": read,
            "send_rate": (sent / total_scheduled * 100) if total_scheduled > 0 else 0.0,
            "delivery_rate": (delivered / sent * 100) if sent > 0 else 0.0,
            "read_rate": (read / delivered * 100) if delivered > 0 else 0.0,
            "avg_delivery_time_seconds": avg_delivery_time,
        }

    def get_response_correlation(
        self, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get correlation between messages sent and responses received."""
        query = self.db.query(FlowMessage).filter(
            and_(
                FlowMessage.sent_at.between(start_date, end_date),
                FlowMessage.sent_at.isnot(None),
            )
        )

        messages_with_responses = query.filter(
            FlowMessage.response_received_at.isnot(None)
        ).all()

        correlation_data = []
        for message in messages_with_responses:
            response_time = None
            if message.response_received_at and message.sent_at:
                response_time = (
                    message.response_received_at - message.sent_at
                ).total_seconds()

            correlation_data.append(
                {
                    "flow_day": message.flow_day,
                    "template_id": message.template_id,
                    "sent_at": message.sent_at.isoformat(),
                    "response_received_at": message.response_received_at.isoformat(),
                    "response_time_seconds": response_time,
                    "response_data": message.response_data,
                }
            )

        return correlation_data
