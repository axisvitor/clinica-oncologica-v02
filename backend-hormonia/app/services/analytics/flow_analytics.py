"""
Flow Analytics Service for tracking and analyzing conversation flow performance.
Implements real-time aggregation metrics using Message and PatientFlowState tables.
"""

import logging
import inspect
from typing import List, Optional, Any, Tuple, Dict
from datetime import datetime, timedelta
from uuid import UUID
from enum import Enum

from sqlalchemy import func, case, select, and_, desc
from sqlalchemy.orm import Session

from app.models.message import Message, MessageDirection, MessageStatus
from app.models.flow import PatientFlowState, FlowTemplateVersion, FlowKind
# Keeping FlowAnalytics model import for backward compat if needed, though we rely on aggregation now.
from app.models.flow_analytics import FlowAnalytics 

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Flow analytics event types (Deprecated - kept for compatibility)."""
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
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_messages_sent": self.total_messages_sent,
            "total_responses_received": self.total_responses_received,
            "response_rate": self.response_rate,
            "average_response_time": self.average_response_time,
            "engagement_score": self.engagement_score
        }


class FlowAnalyticsService:
    """
    Service for tracking and analyzing conversation flow performance.
    Uses real-time aggregation from 'messages' and 'patient_flow_states' tables.
    """

    def __init__(self, db: Session):
        """
        Initialize flow analytics service.

        Args:
            db: Database session
        """
        self.db = db

    async def _resolve(self, maybe_awaitable: Any) -> Any:
        if inspect.isawaitable(maybe_awaitable):
            return await maybe_awaitable
        return maybe_awaitable

    async def calculate_engagement_metrics(
        self,
        flow_type: Optional[str] = None,
        date_range: Optional[Tuple[datetime, datetime]] = None,
        patient_id: Optional[UUID] = None
    ) -> EngagementMetrics:
        """
        Calculate comprehensive engagement metrics based on message history.
        """
        metrics = EngagementMetrics()
        
        # Base query for messages
        query = select(
            func.count(Message.id).filter(Message.direction == MessageDirection.OUTBOUND).label("sent"),
            func.count(Message.id).filter(Message.direction == MessageDirection.INBOUND).label("received")
        )
        
        conditions = []
        if patient_id:
            conditions.append(Message.patient_id == patient_id)
        
        if date_range:
            start_date, end_date = date_range
            conditions.append(Message.created_at >= start_date)
            conditions.append(Message.created_at <= end_date)
            
        if conditions:
            query = query.where(and_(*conditions))
            
        query_result = await self._resolve(self.db.execute(query))
        result = query_result.first()
        
        if result:
            metrics.total_messages_sent = result.sent or 0
            metrics.total_responses_received = result.received or 0
            
            if metrics.total_messages_sent > 0:
                metrics.response_rate = round(metrics.total_responses_received / metrics.total_messages_sent, 2)
                # Simple engagement score: capped multiplier of response rate
                metrics.engagement_score = min(metrics.response_rate * 10.0, 10.0)
        
        return metrics

    async def get_flow_performance_metrics(
        self, flow_type: str, date_range: Optional[Tuple[datetime, datetime]] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive performance metrics for a specific flow type (kind).
        Aggregates data from PatientFlowState.
        """
        # 1. Find the FlowKind ID for the given string key
        kind_stmt = select(FlowKind).where(FlowKind.kind_key == flow_type).limit(1)
        kind_result = await self._resolve(self.db.execute(kind_stmt))
        kind = kind_result.scalars().first()
        if not kind:
            return {
                "flow_type": flow_type,
                "error": "Flow type not found",
                "overview": {"total_started": 0, "active": 0, "completed": 0, "drop_off_rate": 0.0}
            }

        # 2. Query PatientFlowState joined with FlowTemplateVersion
        # to filter by this specific FlowKind
        query = (
            select(
                func.count(PatientFlowState.id).label("total"),
                func.count(PatientFlowState.id).filter(PatientFlowState.status == 'active').label("active"),
                func.count(PatientFlowState.id).filter(PatientFlowState.status == 'completed').label("completed"),
                func.count(PatientFlowState.id).filter(
                    PatientFlowState.status.in_(['paused', 'cancelled', 'inactive'])
                ).label("dropped")
            )
            .join(FlowTemplateVersion, PatientFlowState.flow_template_version_id == FlowTemplateVersion.id)
            .where(FlowTemplateVersion.flow_kind_id == kind.id)
        )

        if date_range:
            start_date, end_date = date_range
            query = query.where(PatientFlowState.started_at >= start_date)
            query = query.where(PatientFlowState.started_at <= end_date)

        query_result = await self._resolve(self.db.execute(query))
        result = query_result.first()
        
        total = result.total if result else 0
        completed = result.completed if result else 0
        active = result.active if result else 0
        dropped = result.dropped if result else 0
        
        completion_rate = round(completed / total, 2) if total > 0 else 0.0
        drop_off_rate = round(dropped / total, 2) if total > 0 else 0.0

        return {
            "flow_type": flow_type,
            "overview": {
                "total_started": total,
                "active": active,
                "completed": completed,
                "completion_rate": completion_rate,
                "dropped": dropped,
                "drop_off_rate": drop_off_rate
            }
        }

    async def get_patient_analytics_summary(
        self, patient_id: UUID, lookback_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive analytics summary for a specific patient.
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        
        # Engagement
        engagement = await self.calculate_engagement_metrics(
            patient_id=patient_id,
            date_range=(start_date, end_date)
        )
        
        # Recent Flows
        recent_flows_stmt = (
            select(PatientFlowState)
            .where(PatientFlowState.patient_id == patient_id)
            .order_by(desc(PatientFlowState.last_interaction_at))
            .limit(5)
        )
        recent_flows_result = await self._resolve(self.db.execute(recent_flows_stmt))
        recent_flows = recent_flows_result.scalars().all()
        
        flows_summary = []
        for flow in recent_flows:
            flows_summary.append({
                "flow_type": flow.flow_type, # Using the @property we saw in flow.py
                "status": flow.status,
                "current_step": flow.current_step,
                "last_interaction": flow.last_interaction_at.isoformat() if flow.last_interaction_at else None
            })

        return {
            "patient_id": str(patient_id),
            "period": f"{lookback_days} days",
            "engagement": engagement.to_dict(),
            "recent_flows": flows_summary
        }

    # Deprecated/Stubbed methods - kept for interface compatibility if needed, 
    # but functionally they don't do anything as there is no event table.
    
    async def track_message_sent(self, *args, **kwargs):
        """Deprecated: Use Message table directly."""
        pass

    async def track_response_received(self, *args, **kwargs):
        """Deprecated: Use Message table directly."""
        pass

    async def track_flow_event(self, *args, **kwargs):
        """Deprecated: Flow events are inferred from state changes."""
        pass
    
    async def identify_at_risk_patients(
        self, flow_type: Optional[str] = None, lookback_days: int = 7
    ) -> List[PatientRisk]:
        """
        Identify patients at risk based on simple heuristics (e.g. low response rate).
        """
        # Implementation could be complex, for now returning empty list or simple logic
        # This can be expanded to query patients with low engagement scores
        return []
