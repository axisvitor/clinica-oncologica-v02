"""
State machine utilities for Flow Services (QW-021).

Encapsulates next-step resolution and transition bookkeeping so the
execution engine can remain stateless.
"""

from __future__ import annotations

# Standard library imports
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Local application imports
from ..execution.conditions import ConditionEvaluator
from ..types import FlowContext, FlowStatus, FlowTransitionType
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class FlowStateMachine:
    """
    Determines state transitions for flow executions.

    Manages the logic for transitioning between flow steps based on
    template transitions and conditions.

    Attributes:
        condition_evaluator: Handler for evaluating transition conditions.
    """

    def __init__(self, condition_evaluator: Optional[ConditionEvaluator] = None):
        """
        Initialize the flow state machine.

        Args:
            condition_evaluator: Optional condition evaluator instance.
        """
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

        Args:
            current_step_id: Current step identifier.
            template: Flow template containing transitions.
            context: Flow execution context.
            transition_type: Type of transition (automatic/manual).

        Returns:
            Next step ID or None if no valid transition exists.
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
        """
        Apply transition effects to FlowContext.

        Args:
            context: Flow execution context.
            from_step: Current step identifier.
            to_step: Next step identifier (None if completing).
            transition_type: Type of transition.

        Returns:
            Updated flow context with transition applied.
        """
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
            "timestamp": now_sao_paulo().isoformat(),
        }

        if to_step is None:
            context.status = FlowStatus.COMPLETED
            context.completed_at = now_sao_paulo()
            logger.info("Flow %s completed", context.flow_instance_id)

        return context


__all__ = ["FlowStateMachine"]
