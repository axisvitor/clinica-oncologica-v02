"""
Flow step executor for the consolidated flow engine.

The executor encapsulates step-specific behavior, leaving FlowEngine as a
thin orchestrator that wires the scheduler, condition evaluator and
state machine together.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Callable, Awaitable, Optional
import logging

from ..types import (
    FlowContext,
    FlowStepData,
    FlowStepStatus,
    FlowStepType,
)
from ..config import get_flow_config
from .scheduler import FlowScheduler
from .conditions import ConditionEvaluator
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of executing a single step."""

    context: FlowContext
    step_data: FlowStepData


class FlowStepExecutor:
    """Executes individual steps using dependency-injected helpers."""

    def __init__(
        self,
        scheduler: Optional[FlowScheduler] = None,
        condition_evaluator: Optional[ConditionEvaluator] = None,
    ):
        self.scheduler = scheduler or FlowScheduler()
        self.condition_evaluator = condition_evaluator or ConditionEvaluator()
        self.config = get_flow_config().execution

        self._handlers: Dict[
            FlowStepType,
            Callable[[FlowContext, Dict[str, Any]], Awaitable[Dict[str, Any]]],
        ] = {  # type: ignore
            FlowStepType.MESSAGE: self._execute_message_step,
            FlowStepType.QUESTION: self._execute_question_step,
            FlowStepType.DECISION: self._execute_decision_step,
            FlowStepType.ACTION: self._execute_action_step,
            FlowStepType.WAIT: self._execute_wait_step,
            FlowStepType.BRANCH: self._execute_branch_step,
            FlowStepType.LOOP: self._execute_loop_step,
            FlowStepType.END: self._execute_end_step,
        }

    async def execute(
        self,
        context: FlowContext,
        step_definition: Dict[str, Any],
    ) -> ExecutionResult:
        """
        Execute a step and return the updated context plus step data.
        """
        step_id = step_definition.get("step_id")
        step_type = FlowStepType(step_definition.get("type"))

        logger.info(
            "Executing step %s (type=%s) for flow %s",
            step_id,
            step_type,
            context.flow_instance_id,
        )

        step_data = FlowStepData(
            step_id=step_id,
            step_type=step_type,
            step_name=step_definition.get("name", step_id),
            status=FlowStepStatus.IN_PROGRESS,
            input_data=step_definition.get("input_data", {}),
            started_at=now_sao_paulo(),
            metadata=step_definition.get("metadata", {}),
        )

        handler = self._handlers.get(step_type, self._execute_default_step)

        try:
            output = await handler(context, step_definition)
            step_data.status = FlowStepStatus.COMPLETED
            step_data.output_data = output
            step_data.completed_at = now_sao_paulo()

            context.steps_completed.append(step_id)
            context.steps_history.append(step_data)
            context.flow_data.update(output.get("flow_data_updates", {}))
            context.variables.update(output.get("variables_updates", {}))

            return ExecutionResult(context=context, step_data=step_data)

        except Exception as exc:
            step_data.status = FlowStepStatus.FAILED
            step_data.error = str(exc)
            step_data.completed_at = now_sao_paulo()
            context.steps_history.append(step_data)
            logger.exception("Step %s failed: %s", step_id, exc)
            raise

    # --------------------------------------------------------------------- #
    # Step handlers
    # --------------------------------------------------------------------- #

    async def _execute_message_step(
        self, context: FlowContext, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        message_content = step_def.get("content", "")
        message_content = self._substitute_variables(message_content, context.variables)

        return {
            "message_sent": True,
            "message_content": message_content,
            "timestamp": now_sao_paulo().isoformat(),
            "flow_data_updates": {},
            "variables_updates": {"last_message_sent": message_content},
        }

    async def _execute_question_step(
        self, context: FlowContext, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        question = self._substitute_variables(
            step_def.get("question", ""), context.variables
        )
        response = context.flow_data.get("pending_response")

        return {
            "question_asked": question,
            "response_received": response is not None,
            "response": response,
            "flow_data_updates": {},
            "variables_updates": {
                "last_question": question,
                "last_response": response,
            },
        }

    async def _execute_decision_step(
        self, context: FlowContext, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        conditions = step_def.get("conditions", [])
        default_path = step_def.get("default_path")

        chosen_path = None
        for condition in conditions:
            if self.condition_evaluator.evaluate(condition, context):
                chosen_path = condition.get("path")
                break
        if chosen_path is None:
            chosen_path = default_path

        return {
            "decision_made": True,
            "chosen_path": chosen_path,
            "conditions_evaluated": len(conditions),
            "flow_data_updates": {"last_decision": chosen_path},
            "variables_updates": {"last_path": chosen_path},
        }

    async def _execute_action_step(
        self, context: FlowContext, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        action_type = step_def.get("action_type")
        action_params = step_def.get("params", {})

        # TODO: plug into actual action dispatchers
        return {
            "action_executed": True,
            "action_type": action_type,
            "params": action_params,
            "result": {"status": "success"},
            "flow_data_updates": {f"action_{action_type}_executed": True},
            "variables_updates": {},
        }

    async def _execute_wait_step(
        self, context: FlowContext, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        wait_until = self.scheduler.compute_wait_until(context, step_def)
        if not wait_until:
            duration_seconds = step_def.get("duration_seconds", 0)
            wait_until = now_sao_paulo() + timedelta(seconds=duration_seconds)

        return {
            "wait_started": True,
            "resume_at": wait_until.isoformat(),
            "flow_data_updates": {"paused_until": wait_until.isoformat()},
            "variables_updates": {},
        }

    async def _execute_branch_step(
        self, context: FlowContext, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        branches = step_def.get("branches", [])
        condition = step_def.get("condition")

        if condition:
            condition_met = self.condition_evaluator.evaluate(condition, context)
            branch_taken = branches[0] if condition_met else branches[1]
        else:
            branch_taken = branches[0] if branches else None

        return {
            "branch_executed": True,
            "branch_taken": branch_taken,
            "total_branches": len(branches),
            "flow_data_updates": {"current_branch": branch_taken},
            "variables_updates": {},
        }

    async def _execute_loop_step(
        self, context: FlowContext, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        loop_to_step = step_def.get("loop_to_step")
        max_iterations = step_def.get("max_iterations", 10)
        loop_condition = step_def.get("condition")

        iteration = context.flow_data.get("loop_iteration", 0) + 1
        should_continue = iteration < max_iterations
        if loop_condition:
            should_continue = should_continue and self.condition_evaluator.evaluate(
                loop_condition, context
            )

        return {
            "loop_executed": True,
            "loop_to_step": loop_to_step if should_continue else None,
            "current_iteration": iteration,
            "should_continue": should_continue,
            "flow_data_updates": {"loop_iteration": iteration},
            "variables_updates": {},
        }

    async def _execute_end_step(
        self, context: FlowContext, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        end_reason = step_def.get("reason", "completed")
        final_message = step_def.get("final_message")

        return {
            "flow_ended": True,
            "end_reason": end_reason,
            "final_message": final_message,
            "flow_data_updates": {"ended_at": now_sao_paulo().isoformat()},
            "variables_updates": {},
        }

    async def _execute_default_step(
        self, context: FlowContext, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fallback handler for unsupported step types."""
        return {
            "step_processed": True,
            "flow_data_updates": {},
            "variables_updates": {},
        }

    def _substitute_variables(self, text: str, variables: Dict[str, Any]) -> str:
        if not text or not variables:
            return text

        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            text = text.replace(placeholder, str(value))
        return text


__all__ = ["FlowStepExecutor", "ExecutionResult"]
