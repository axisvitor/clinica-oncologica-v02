"""
Flow Analytics Repository for database operations.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, asc
from uuid import UUID

from app.models.flow_analytics import FlowAnalytics, FlowMessage
from app.models.flow import FlowTemplateVersion, FlowKind
from app.models.message import Message  # Import Message for delivery metrics
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
                    FlowAnalytics.calculated_at.between(start_date, end_date),
                )
            )
            .order_by(desc(FlowAnalytics.calculated_at))
            .all()
        )

    def get_by_flow_type_and_date_range(
        self, flow_type: str, start_date: datetime, end_date: datetime
    ) -> List[FlowAnalytics]:
        """Get analytics records for flow type within date range."""
        return (
            self.db.query(FlowAnalytics)
            .join(FlowTemplateVersion, FlowAnalytics.flow_template_version_id == FlowTemplateVersion.id)
            .join(FlowKind, FlowTemplateVersion.flow_kind_id == FlowKind.id)
            .filter(
                and_(
                    FlowKind.kind_key == flow_type,
                    FlowAnalytics.calculated_at.between(start_date, end_date),
                )
            )
            .order_by(desc(FlowAnalytics.calculated_at))
            .all()
        )

    # NOTE: The following methods were removed because the flow_analytics table
    # does not contain the necessary granular event data (event_type, sentiment_score, etc.)
    # in the current schema. These metrics should be derived from interaction_patterns JSONB
    # or a separate event log table if created in the future.

    def get_event_counts_by_type(
        self,
        flow_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """
        Get event counts grouped by event type.
        NOT IMPLEMENTED: Requires event-level logging not present in flow_analytics table.
        """
        return {}

    def get_daily_metrics(
        self, flow_type: str, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get daily metrics for a flow type.
        NOT IMPLEMENTED: Requires event-level logging not present in flow_analytics table.
        """
        return []

    def get_patient_engagement_scores(
        self, patient_ids: List[UUID], start_date: datetime, end_date: datetime
    ) -> Dict[UUID, float]:
        """
        Get average success rates for patients (proxy for engagement).
        """
        query = (
            self.db.query(
                FlowAnalytics.patient_id,
                func.avg(FlowAnalytics.success_rate).label("avg_success"),
            )
            .filter(
                and_(
                    FlowAnalytics.patient_id.in_(patient_ids),
                    FlowAnalytics.success_rate.isnot(None),
                    FlowAnalytics.calculated_at.between(start_date, end_date),
                )
            )
            .group_by(FlowAnalytics.patient_id)
        )

        results = query.all()
        return {
            patient_id: float(avg_success) for patient_id, avg_success in results
        }

    def get_sentiment_distribution(
        self,
        flow_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """
        Get sentiment score distribution.
        NOT IMPLEMENTED: sentiment_score column does not exist.
        """
        return {"positive": 0, "neutral": 0, "negative": 0}

    def get_response_time_stats(
        self,
        flow_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """Get response time statistics using avg_response_time_seconds."""
        query = self.db.query(FlowAnalytics.avg_response_time_seconds).filter(
            FlowAnalytics.avg_response_time_seconds.isnot(None)
        )

        if flow_type:
             query = query.join(FlowTemplateVersion).join(FlowKind).filter(FlowKind.kind_key == flow_type)

        if start_date and end_date:
            query = query.filter(FlowAnalytics.calculated_at.between(start_date, end_date))

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
            .filter(FlowAnalytics.calculated_at < cutoff_date)
            .delete()
        )

        return deleted_count


class FlowMessageRepository(BaseRepository[FlowMessage]):
    """Repository for flow message operations."""

    def __init__(self, db: Session):
        super().__init__(FlowMessage, db)

    def get_by_flow_state(self, flow_state_id: UUID) -> List[FlowMessage]:
        """
        Get all messages definitions for a flow state.
        NOTE: This logic assumes we want the template messages for the state's current version.
        But FlowMessage does not have 'flow_state_id'. It maps to 'flow_template_version_id'.
        """
        # We can't implement this directly without a join to PatientFlowState
        # Assuming flow_state_id is PatientFlowState.id
        from app.models.flow import PatientFlowState
        
        state = self.db.query(PatientFlowState).filter(PatientFlowState.id == flow_state_id).first()
        if not state:
            return []
            
        return (
            self.db.query(FlowMessage)
            .filter(FlowMessage.flow_template_version_id == state.flow_template_version_id)
            .order_by(asc(FlowMessage.step_number))
            .all()
        )

    def get_delivery_metrics(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get message delivery metrics.
        Uses the Message model (actual sent messages) instead of FlowMessage (templates).
        """
        query = self.db.query(Message).filter(
            Message.scheduled_for.between(start_date, end_date)
        )

        total_scheduled = query.count()
        sent = query.filter(Message.sent_at.isnot(None)).count()
        delivered = query.filter(Message.delivered_at.isnot(None)).count()
        read = query.filter(Message.read_at.isnot(None)).count()

        # Calculate average delivery times
        delivery_times = (
            query.filter(
                and_(
                    Message.sent_at.isnot(None),
                    Message.delivered_at.isnot(None),
                )
            )
            .with_entities(
                (
                    func.extract("epoch", Message.delivered_at)
                    - func.extract("epoch", Message.sent_at)
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
        """
        Get correlation between messages sent and responses received.
        Uses Message model.
        """
        # Assuming we want to track outbound messages that got a response?
        # Constructing a simple query on Message table
        query = self.db.query(Message).filter(
            and_(
                Message.sent_at.between(start_date, end_date),
                Message.sent_at.isnot(None),
            )
        )
        
        # Note: logic for 'response_received_at' depends on how responses are linked.
        # The Message model might not have 'response_received_at'.
        # Assuming we can't easily implement this with just the Message model unless 
        # there is a direct link or we check the 'status' or related events.
        
        # For now returning empty list as implementation would be speculative
        return []
