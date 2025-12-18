"""
Analytics Event Collection Module - Flow Event Tracking

Collects and tracks flow events for analytics and monitoring.
"""

import logging
from typing import Dict, Any, Optional
from uuid import UUID

from app.services.analytics import FlowAnalyticsService


logger = logging.getLogger(__name__)


class AnalyticsCollector:
    """
    Collects and tracks flow analytics events.

    Responsibilities:
    - Track flow lifecycle events
    - Collect flow execution metrics
    - Handle analytics service integration
    - Graceful degradation on analytics failures
    """

    def __init__(self, analytics_service: FlowAnalyticsService):
        """
        Initialize AnalyticsCollector.

        Args:
            analytics_service: Flow analytics service
        """
        self.analytics_service = analytics_service

        logger.info("AnalyticsCollector initialized")

    async def track_flow_event(
        self,
        patient_id: UUID,
        event_type: str,
        flow_type: str,
        current_day: int,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Track flow event in analytics service.

        Args:
            patient_id: Patient UUID
            event_type: Type of event
            flow_type: Flow type identifier
            current_day: Current day in flow
            metadata: Additional event metadata
        """
        try:
            await self.analytics_service.track_flow_event(
                patient_id=patient_id,
                event_type=event_type,
                flow_type=flow_type,
                flow_day=current_day,
                additional_data=metadata or {},
            )

            logger.debug(f"Flow event tracked: {event_type} for patient {patient_id}")

        except Exception as e:
            logger.warning(f"Analytics tracking failed (non-critical): {e}")

    async def track_flow_start(
        self,
        patient_id: UUID,
        flow_type: str,
        current_day: int,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Track flow start event."""
        await self.track_flow_event(
            patient_id=patient_id,
            event_type="flow_started",
            flow_type=flow_type,
            current_day=current_day,
            metadata=metadata,
        )

    async def track_flow_advance(
        self, patient_id: UUID, flow_type: str, from_day: int, to_day: int
    ):
        """Track flow advancement event."""
        await self.track_flow_event(
            patient_id=patient_id,
            event_type="flow_advanced",
            flow_type=flow_type,
            current_day=to_day,
            metadata={"from_day": from_day, "to_day": to_day},
        )

    async def track_flow_pause(
        self,
        patient_id: UUID,
        flow_type: str,
        current_day: int,
        reason: Optional[str] = None,
    ):
        """Track flow pause event."""
        await self.track_flow_event(
            patient_id=patient_id,
            event_type="flow_paused",
            flow_type=flow_type,
            current_day=current_day,
            metadata={"reason": reason},
        )

    async def track_flow_resume(
        self, patient_id: UUID, flow_type: str, current_day: int
    ):
        """Track flow resume event."""
        await self.track_flow_event(
            patient_id=patient_id,
            event_type="flow_resumed",
            flow_type=flow_type,
            current_day=current_day,
            metadata={},
        )

    async def track_flow_stop(
        self,
        patient_id: UUID,
        flow_type: str,
        final_day: int,
        reason: Optional[str] = None,
    ):
        """Track flow stop event."""
        await self.track_flow_event(
            patient_id=patient_id,
            event_type="flow_stopped",
            flow_type=flow_type,
            current_day=final_day,
            metadata={"reason": reason},
        )

    async def track_flow_transition(
        self, patient_id: UUID, from_flow_type: str, to_flow_type: str, current_day: int
    ):
        """Track flow type transition event."""
        await self.track_flow_event(
            patient_id=patient_id,
            event_type="flow_type_transition",
            flow_type=to_flow_type,
            current_day=current_day,
            metadata={"from_flow_type": from_flow_type, "to_flow_type": to_flow_type},
        )

    async def track_quiz_trigger(
        self, patient_id: UUID, flow_type: str, quiz_type: str, monthly_cycle: int
    ):
        """Track quiz trigger event."""
        await self.track_flow_event(
            patient_id=patient_id,
            event_type="quiz_triggered",
            flow_type=flow_type,
            current_day=0,
            metadata={"quiz_type": quiz_type, "monthly_cycle": monthly_cycle},
        )
