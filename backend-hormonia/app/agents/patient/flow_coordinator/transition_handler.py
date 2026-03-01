"""Transition Handler - Manages phase transitions and timing optimizations."""

from __future__ import annotations

# DDD service agent - no LLM calls, not a pydantic-ai migration target.

# Standard library
import logging
from typing import Any, Dict, List

# Third-party
from sqlalchemy.orm import Session

# Local
from app.services.enhanced_flow_engine import FlowType

from .models import FlowContext
from app.utils.timezone import now_sao_paulo


class TransitionHandler:
    """
    Handles flow phase transitions and timing optimizations.

    Manages transitions between flow phases, optimizes message
    timing based on patient engagement, and personalizes content
    based on patient patterns and risk factors.

    Attributes:
        db_session: Database session.
        agent_id: Unique agent identifier.
        logger: Logger instance.
    """

    def __init__(self, db_session: Session, agent_id: str, logger: logging.Logger):
        self.db_session = db_session
        self.agent_id = agent_id
        self.logger = logger

    async def transition_flow_phase(self, context: FlowContext):
        """Transition patient to different flow phase."""
        if context.flow_state:
            previous_flow_type = context.flow_state.flow_type

            # Update flow state to monthly recurring
            context.flow_state.state_data = context.flow_state.state_data or {}
            context.flow_state.state_data.update(
                {
                    "phase_transition": {
                        "from": "daily_intensive",
                        "to": "quiz_mensal",
                        "transitioned_at": now_sao_paulo().isoformat(),
                        "transitioned_by": self.agent_id,
                    }
                }
            )

            # Change flow type
            context.flow_state.flow_type = FlowType.QUIZ_MENSAL.value

            self.db_session.commit()

            self.logger.info(
                "flow_transition_executed",
                extra={
                    "audit": True,
                    "transition_type": "phase_change",
                    "patient_id": str(context.patient_id) if context.patient_id else None,
                    "from_phase": previous_flow_type,
                    "to_phase": FlowType.QUIZ_MENSAL.value,
                    "trigger": "automated",
                    "agent_id": self.agent_id,
                },
            )

    async def optimize_timing(self, context: FlowContext) -> Dict[str, Any]:
        """Optimize message timing for better engagement."""
        # Analyze response patterns to find optimal times
        # For now, return adjusted timing
        optimized_timing = {
            "morning": 9,  # 9 AM instead of 8 AM
            "afternoon": 15,  # 3 PM instead of 2 PM
            "evening": 19,  # 7 PM instead of 8 PM
        }

        # Update flow state with new timing
        if context.flow_state:
            context.flow_state.state_data = context.flow_state.state_data or {}
            context.flow_state.state_data.update(
                {
                    "optimized_timing": optimized_timing,
                    "timing_optimized_by": self.agent_id,
                    "timing_optimized_at": now_sao_paulo().isoformat(),
                }
            )

            self.db_session.commit()

        return optimized_timing

    async def personalize_content(self, context: FlowContext):
        """Personalize content based on patient patterns."""
        if context.flow_state:
            personalization_settings = {
                "tone": "supportive"
                if any("mood" in rf for rf in context.risk_factors)
                else "encouraging",
                "frequency": "reduced"
                if context.adherence_metrics.get("message_response_rate", 1.0) < 0.5
                else "normal",
                "content_focus": await self._determine_content_focus(context),
                "personalized_by": self.agent_id,
                "personalized_at": now_sao_paulo().isoformat(),
            }

            context.flow_state.state_data = context.flow_state.state_data or {}
            context.flow_state.state_data.update(
                {"personalization": personalization_settings}
            )

            self.db_session.commit()

    async def _determine_content_focus(self, context: FlowContext) -> List[str]:
        """Determine content focus areas based on patient needs."""
        focus_areas = []

        # Base on risk factors
        for risk_factor in context.risk_factors:
            if "mood" in risk_factor:
                focus_areas.append("emotional_support")
            elif "symptom" in risk_factor:
                focus_areas.append("symptom_management")
            elif "engagement" in risk_factor:
                focus_areas.append("motivation_enhancement")

        # Default focus if no specific risks
        if not focus_areas:
            focus_areas = ["general_wellness", "treatment_adherence"]

        return focus_areas

    async def pause_flow(self, context: FlowContext):
        """Pause flow temporarily."""
        if context.flow_state:
            context.flow_state.state_data = context.flow_state.state_data or {}
            context.flow_state.state_data.update(
                {
                    "flow_paused": True,
                    "paused_at": now_sao_paulo().isoformat(),
                    "paused_by": self.agent_id,
                    "pause_reason": "patient_request_or_medical_indication",
                }
            )

            self.db_session.commit()

            self.logger.info(
                "flow_transition_executed",
                extra={
                    "audit": True,
                    "transition_type": "pause",
                    "patient_id": str(context.patient_id) if context.patient_id else None,
                    "flow_type": context.flow_state.flow_type,
                    "trigger": "automated",
                    "agent_id": self.agent_id,
                },
            )

    async def resume_flow(self, context: FlowContext):
        """Resume paused flow."""
        if context.flow_state:
            context.flow_state.state_data = context.flow_state.state_data or {}
            context.flow_state.state_data.update(
                {
                    "flow_paused": False,
                    "resumed_at": now_sao_paulo().isoformat(),
                    "resumed_by": self.agent_id,
                }
            )

            self.db_session.commit()

            self.logger.info(
                "flow_transition_executed",
                extra={
                    "audit": True,
                    "transition_type": "resume",
                    "patient_id": str(context.patient_id) if context.patient_id else None,
                    "flow_type": context.flow_state.flow_type,
                    "trigger": "automated",
                    "agent_id": self.agent_id,
                },
            )
