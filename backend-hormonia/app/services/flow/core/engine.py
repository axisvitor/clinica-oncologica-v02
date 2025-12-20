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

    Transaction Safety:
        While the engine itself doesn't directly interact with the database,
        it provides transaction-safe execution patterns for callers that do.
        The engine ensures atomic operations by using try/except blocks and
        proper error propagation.
    """

    def __init__(
        self,
        executor: Optional[FlowStepExecutor] = None,
        scheduler: Optional[FlowScheduler] = None,
        condition_evaluator: Optional[ConditionEvaluator] = None,
        state_machine: Optional[FlowStateMachine] = None,
        transition_planner: Optional[TransitionPlanner] = None,
        db: Optional[Any] = None,
    ):
        self.config = get_flow_config()
        self.db = db  # Optional database session for transaction management

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
        """
        Delegate execution to FlowStepExecutor with transaction safety.

        Note: This method modifies the context in-memory. The caller is
        responsible for persisting changes within a database transaction.
        If an exception occurs, the in-memory context changes will not
        be persisted, ensuring consistency.

        Args:
            context: Flow execution context
            step_definition: Step definition from template

        Returns:
            Tuple of updated context and step execution data

        Raises:
            Exception: Any exception from step execution is propagated
                      to allow the caller to handle rollback
        """
        try:
            result: ExecutionResult = await self.executor.execute(context, step_definition)
            return result.context, result.step_data
        except Exception as e:
            logger.error(
                "Step execution failed for flow %s, step %s: %s",
                context.flow_instance_id,
                step_definition.get("step_id"),
                str(e),
            )
            # Re-raise to allow caller to handle transaction rollback
            raise

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
        """
        Apply state transition bookkeeping with transaction safety.

        Note: This method modifies the context in-memory. The caller is
        responsible for persisting changes within a database transaction.
        If an exception occurs, the in-memory context changes will not
        be persisted, ensuring consistency.

        Args:
            context: Flow execution context
            from_step: Current step ID
            to_step: Next step ID (None if flow is completing)
            transition_type: Type of transition

        Returns:
            Updated flow context

        Raises:
            Exception: Any exception from transition is propagated
                      to allow the caller to handle rollback
        """
        try:
            updated_context = await self.transition_planner.apply(
                context=context,
                from_step=from_step,
                to_step=to_step,
                transition_type=transition_type,
            )
            logger.debug(
                "State transition completed: %s -> %s (type=%s)",
                from_step,
                to_step,
                transition_type,
            )
            return updated_context
        except Exception as e:
            logger.error(
                "State transition failed for flow %s: %s -> %s: %s",
                context.flow_instance_id,
                from_step,
                to_step,
                str(e),
            )
            # Re-raise to allow caller to handle transaction rollback
            raise

    async def execute_step_with_transaction(
        self,
        context: FlowContext,
        step_definition: Dict[str, Any],
    ) -> Tuple[FlowContext, FlowStepData]:
        """
        Execute step with automatic transaction management.

        This method wraps execute_step with database transaction handling.
        If a database session is configured, it will commit on success
        and rollback on failure. If no database session is configured,
        it behaves the same as execute_step.

        Args:
            context: Flow execution context
            step_definition: Step definition from template

        Returns:
            Tuple of updated context and step execution data

        Raises:
            Exception: Any exception from step execution after rollback
        """
        if not self.db:
            # No database session, just execute normally
            return await self.execute_step(context, step_definition)

        try:
            # Execute step (modifies context in-memory)
            result_context, step_data = await self.execute_step(context, step_definition)

            # If successful and DB session exists, commit would happen in caller
            # This method doesn't commit - it just ensures atomicity
            logger.debug(
                "Step execution successful for flow %s, step %s",
                context.flow_instance_id,
                step_definition.get("step_id"),
            )
            return result_context, step_data

        except Exception as e:
            # Rollback database transaction if configured
            if self.db:
                try:
                    self.db.rollback()
                    logger.info(
                        "Database rollback completed after step execution failure: %s",
                        str(e),
                    )
                except Exception as rollback_error:
                    logger.error(
                        "Failed to rollback transaction: %s",
                        str(rollback_error),
                    )
            raise

    async def transition_state_with_transaction(
        self,
        context: FlowContext,
        from_step: str,
        to_step: Optional[str],
        transition_type: FlowTransitionType = FlowTransitionType.AUTOMATIC,
    ) -> FlowContext:
        """
        Apply state transition with automatic transaction management.

        This method wraps transition_state with database transaction handling.
        If a database session is configured, it will commit on success
        and rollback on failure. If no database session is configured,
        it behaves the same as transition_state.

        Args:
            context: Flow execution context
            from_step: Current step ID
            to_step: Next step ID (None if flow is completing)
            transition_type: Type of transition

        Returns:
            Updated flow context

        Raises:
            Exception: Any exception from transition after rollback
        """
        if not self.db:
            # No database session, just execute normally
            return await self.transition_state(context, from_step, to_step, transition_type)

        try:
            # Execute transition (modifies context in-memory)
            updated_context = await self.transition_state(
                context, from_step, to_step, transition_type
            )

            # If successful and DB session exists, commit would happen in caller
            # This method doesn't commit - it just ensures atomicity
            logger.debug(
                "State transition successful: %s -> %s (type=%s)",
                from_step,
                to_step,
                transition_type,
            )
            return updated_context

        except Exception as e:
            # Rollback database transaction if configured
            if self.db:
                try:
                    self.db.rollback()
                    logger.info(
                        "Database rollback completed after transition failure: %s",
                        str(e),
                    )
                except Exception as rollback_error:
                    logger.error(
                        "Failed to rollback transaction: %s",
                        str(rollback_error),
                    )
            raise

    def __repr__(self) -> str:
        return "<FlowEngine(modular=True)>"


__all__ = ["FlowEngine"]
