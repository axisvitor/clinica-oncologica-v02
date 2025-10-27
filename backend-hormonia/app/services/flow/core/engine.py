"""
Flow Engine - Core execution logic for Flow Services (QW-021).

The refactored engine is intentionally slim: it orchestrates dedicated
components (executor, scheduler, state machine) instead of embedding
business logic directly. This keeps the module testable and aligns with
the layered architecture described in QW-021.
"""

from __future__ import annotations

from typing import Dict, Any, Optional, Tuple
import logging

from ..types import FlowContext, FlowStepData, FlowTransitionType
from ..config import get_flow_config
from ..execution.executor import FlowStepExecutor, ExecutionResult
from ..execution.scheduler import FlowScheduler
from ..execution.conditions import ConditionEvaluator
from ..execution.transitions import TransitionPlanner
from .state_machine import FlowStateMachine

logger = logging.getLogger(__name__)


class FlowEngine:
    """
    Stateless flow executor.

    FlowManager passes FlowContext plus template fragments and the engine
    returns updated contexts along with the executed step metadata.
    """

    def __init__(
        self,
        executor: Optional[FlowStepExecutor] = None,
        scheduler: Optional[FlowScheduler] = None,
        condition_evaluator: Optional[ConditionEvaluator] = None,
        state_machine: Optional[FlowStateMachine] = None,
        transition_planner: Optional[TransitionPlanner] = None,
    ):
        self.config = get_flow_config()

        self.condition_evaluator = condition_evaluator or ConditionEvaluator()
        self.scheduler = scheduler or FlowScheduler()
        self.state_machine = state_machine or FlowStateMachine(
            condition_evaluator=self.condition_evaluator
        )
        self.transition_planner = transition_planner or TransitionPlanner(
            state_machine=self.state_machine
        )
        self.executor = executor or FlowStepExecutor(
            scheduler=self.scheduler,
            condition_evaluator=self.condition_evaluator,
        )

        logger.info("FlowEngine initialized (QW-021 executor stack ready)")

    async def execute_step(
        self,
        context: FlowContext,
        step_definition: Dict[str, Any],
    ) -> Tuple[FlowContext, FlowStepData]:
        """Delegate execution to FlowStepExecutor."""
        result: ExecutionResult = await self.executor.execute(context, step_definition)
        return result.context, result.step_data

    def get_next_step(
        self,
        current_step_id: str,
        template: Dict[str, Any],
        context: FlowContext,
        transition_type: FlowTransitionType = FlowTransitionType.AUTOMATIC,
    ) -> Optional[str]:
        """Return the next step using the transition planner."""
        return self.transition_planner.next_step(
            current_step_id=current_step_id,
            template=template,
            context=context,
            transition_type=transition_type,
        )

    async def transition_state(
        self,
        context: FlowContext,
        from_step: str,
        to_step: Optional[str],
        transition_type: FlowTransitionType = FlowTransitionType.AUTOMATIC,
    ) -> FlowContext:
        """Apply state transition bookkeeping."""
        return await self.transition_planner.apply(
            context=context,
            from_step=from_step,
            to_step=to_step,
            transition_type=transition_type,
        )

    def __repr__(self) -> str:
        return "<FlowEngine(modular=True)>"


__all__ = ["FlowEngine"]
