"""
Transition planning utilities for Flow Services.

The planner wraps FlowStateMachine helpers to add additional metadata
and logging around computed transitions.
"""

from __future__ import annotations

from typing import Dict, Any, Optional
import logging

from ..types import FlowContext, FlowTransitionType
from ..core.state_machine import FlowStateMachine

logger = logging.getLogger(__name__)


class TransitionPlanner:
    """High-level helper that determines upcoming steps."""

    def __init__(self, state_machine: Optional[FlowStateMachine] = None):
        self.state_machine = state_machine or FlowStateMachine()

    def next_step(
        self,
        current_step_id: str,
        template: Dict[str, Any],
        context: FlowContext,
        transition_type: FlowTransitionType = FlowTransitionType.AUTOMATIC,
    ) -> Optional[str]:
        return self.state_machine.get_next_step(
            current_step_id=current_step_id,
            template=template,
            context=context,
            transition_type=transition_type,
        )

    async def apply(
        self,
        context: FlowContext,
        from_step: str,
        to_step: Optional[str],
        transition_type: FlowTransitionType = FlowTransitionType.AUTOMATIC,
    ) -> FlowContext:
        return await self.state_machine.transition_state(
            context=context,
            from_step=from_step,
            to_step=to_step,
            transition_type=transition_type,
        )


__all__ = ["TransitionPlanner"]
