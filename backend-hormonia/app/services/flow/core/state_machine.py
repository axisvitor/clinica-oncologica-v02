"""
State machine utilities for Flow Services (QW-021).

Encapsulates next-step resolution and transition bookkeeping so the
execution engine can remain stateless.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging

from ..types import FlowContext, FlowStatus, FlowTransitionType
from ..execution.conditions import ConditionEvaluator

logger = logging.getLogger(__name__)


class FlowStateMachine:
    """Determines state transitions for flow executions."""

    def __init__(self, condition_evaluator: Optional[ConditionEvaluator] = None):
        self.condition_evaluator = condition_evaluator or ConditionEvaluator()

    def get_next_step(
        self,
        current_step_id: str,
        template: Dict[str, Any],
        context: FlowContext,
        transition_type: FlowTransitionType = FlowTransitionType.AUTOMATIC,
    ) -> Optional[str]:
        """
        Determine the next step that should run based on template transitions.
        """
        transitions = template.get("transitions", [])
        for transition in transitions:
            if transition.get("from") != current_step_id:
                continue

            conditions = transition.get("conditions", [])
            if not conditions or all(
                self.condition_evaluator.evaluate(condition, context)
                for condition in conditions
            ):
                next_step = transition.get("to")
                logger.debug(
                    "Transition %s -> %s (type=%s)",
                    current_step_id,
                    next_step,
                    transition_type,
                )
                return next_step

        # Fallback to sequential order
        steps = template.get("steps", [])
        step_ids = [step.get("step_id") for step in steps]

        try:
            index = step_ids.index(current_step_id)
        except ValueError:
            logger.warning(
                "Current step %s not found in template; terminating flow %s",
                current_step_id,
                context.flow_instance_id,
            )
            return None

        if index < len(step_ids) - 1:
            return step_ids[index + 1]
        return None

    async def transition_state(
        self,
        context: FlowContext,
        from_step: str,
        to_step: Optional[str],
        transition_type: FlowTransitionType = FlowTransitionType.AUTOMATIC,
    ) -> FlowContext:
        """Apply transition effects to FlowContext."""
        logger.info(
            "State transition %s -> %s (type=%s)",
            from_step,
            to_step,
            transition_type,
        )

        context.current_step_id = to_step
        context.flow_data["last_transition"] = {
            "from": from_step,
            "to": to_step,
            "type": transition_type.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if to_step is None:
            context.status = FlowStatus.COMPLETED
            context.completed_at = datetime.now(timezone.utc)
            logger.info("Flow %s completed", context.flow_instance_id)

        return context


__all__ = ["FlowStateMachine"]
