"""
Flow Engine - Core execution logic for Flow Services (QW-021).

This module implements the FlowEngine class, which handles the execution
of individual flow steps, state transitions, and condition evaluation.

The engine is designed to be stateless - it receives context, executes logic,
and returns updated context. State persistence is handled by FlowManager.

Migration Note:
    This consolidates execution logic from:
    - flow_engine.py (legacy engine)
    - enhanced_flow_engine.py (enhanced version)
    - flow_core.py (core logic)
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import logging
from uuid import uuid4

from ..types import (
    FlowContext,
    FlowStepData,
    FlowStepType,
    FlowStepStatus,
    FlowStatus,
    FlowTransitionType,
)
from ..config import get_flow_config

logger = logging.getLogger(__name__)


class FlowEngine:
    """
    Flow execution engine.

    Handles the core logic for executing flow steps, evaluating conditions,
    and managing state transitions. Designed to be stateless and reusable.

    Example:
        >>> engine = FlowEngine()
        >>> context = FlowContext(...)
        >>> step_data = {...}
        >>> updated_context = await engine.execute_step(context, step_data)
    """

    def __init__(self):
        """Initialize the flow engine."""
        self.config = get_flow_config()
        logger.info("FlowEngine initialized")

    async def execute_step(
        self,
        context: FlowContext,
        step_definition: Dict[str, Any],
    ) -> Tuple[FlowContext, FlowStepData]:
        """
        Execute a single flow step.

        Args:
            context: Current flow execution context
            step_definition: Step definition from template

        Returns:
            Tuple of (updated_context, step_result)

        Raises:
            ValueError: If step definition is invalid
            RuntimeError: If step execution fails
        """
        step_id = step_definition.get("step_id")
        step_type = FlowStepType(step_definition.get("type"))

        logger.info(
            f"Executing step {step_id} (type: {step_type}) for flow {context.flow_instance_id}"
        )

        # Create step data
        step_data = FlowStepData(
            step_id=step_id,
            step_type=step_type,
            step_name=step_definition.get("name", step_id),
            status=FlowStepStatus.IN_PROGRESS,
            input_data=step_definition.get("input_data", {}),
            started_at=datetime.utcnow(),
            metadata=step_definition.get("metadata", {}),
        )

        try:
            # Execute based on step type
            if step_type == FlowStepType.MESSAGE:
                output = await self._execute_message_step(context, step_definition)
            elif step_type == FlowStepType.QUESTION:
                output = await self._execute_question_step(context, step_definition)
            elif step_type == FlowStepType.DECISION:
                output = await self._execute_decision_step(context, step_definition)
            elif step_type == FlowStepType.ACTION:
                output = await self._execute_action_step(context, step_definition)
            elif step_type == FlowStepType.WAIT:
                output = await self._execute_wait_step(context, step_definition)
            elif step_type == FlowStepType.BRANCH:
                output = await self._execute_branch_step(context, step_definition)
            elif step_type == FlowStepType.LOOP:
                output = await self._execute_loop_step(context, step_definition)
            elif step_type == FlowStepType.END:
                output = await self._execute_end_step(context, step_definition)
            else:
                raise ValueError(f"Unknown step type: {step_type}")

            # Mark step as completed
            step_data.status = FlowStepStatus.COMPLETED
            step_data.output_data = output
            step_data.completed_at = datetime.utcnow()

            # Update context
            context.steps_completed.append(step_id)
            context.steps_history.append(step_data)
            context.flow_data.update(output.get("flow_data_updates", {}))
            context.variables.update(output.get("variables_updates", {}))

            logger.info(f"Step {step_id} completed successfully")

            return context, step_data

        except Exception as e:
            # Mark step as failed
            step_data.status = FlowStepStatus.FAILED
            step_data.error = str(e)
            step_data.completed_at = datetime.utcnow()

            context.steps_history.append(step_data)

            logger.error(f"Step {step_id} failed: {e}", exc_info=True)
            raise RuntimeError(f"Step execution failed: {e}") from e

    async def _execute_message_step(
        self, context: FlowContext, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a message step (send message to patient).

        Args:
            context: Flow context
            step_def: Step definition

        Returns:
            Step output data
        """
        message_content = step_def.get("content", "")

        # Template variable substitution
        message_content = self._substitute_variables(message_content, context.variables)

        # In production, this would call message service
        # For now, just prepare the message data
        output = {
            "message_sent": True,
            "message_content": message_content,
            "timestamp": datetime.utcnow().isoformat(),
            "flow_data_updates": {},
            "variables_updates": {"last_message_sent": message_content},
        }

        logger.debug(f"Message step executed: {len(message_content)} chars")
        return output

    async def _execute_question_step(
        self, context: FlowContext, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a question step (ask question, wait for response).

        Args:
            context: Flow context
            step_def: Step definition

        Returns:
            Step output data
        """
        question = step_def.get("question", "")
        question = self._substitute_variables(question, context.variables)

        # Check if we already have a response (from previous execution)
        response = context.flow_data.get("pending_response")

        output = {
            "question_asked": question,
            "response_received": response is not None,
            "response": response,
            "flow_data_updates": {},
            "variables_updates": {
                "last_question": question,
                "last_response": response,
            },
        }

        logger.debug(f"Question step executed: response={'yes' if response else 'no'}")
        return output

    async def _execute_decision_step(
        self, context: FlowContext, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a decision step (evaluate conditions, choose path).

        Args:
            context: Flow context
            step_def: Step definition

        Returns:
            Step output data including chosen path
        """
        conditions = step_def.get("conditions", [])
        default_path = step_def.get("default_path")

        chosen_path = None
        for condition in conditions:
            if await self.evaluate_condition(condition, context):
                chosen_path = condition.get("path")
                break

        if chosen_path is None:
            chosen_path = default_path

        output = {
            "decision_made": True,
            "chosen_path": chosen_path,
            "conditions_evaluated": len(conditions),
            "flow_data_updates": {"last_decision": chosen_path},
            "variables_updates": {"last_path": chosen_path},
        }

        logger.debug(f"Decision step: chose path '{chosen_path}'")
        return output

    async def _execute_action_step(
        self, context: FlowContext, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute an action step (API call, task execution, etc.).

        Args:
            context: Flow context
            step_def: Step definition

        Returns:
            Step output data
        """
        action_type = step_def.get("action_type")
        action_params = step_def.get("params", {})

        # In production, this would dispatch to different action handlers
        # For now, just log the action
        output = {
            "action_executed": True,
            "action_type": action_type,
            "params": action_params,
            "result": {"status": "success"},
            "flow_data_updates": {f"action_{action_type}_executed": True},
            "variables_updates": {},
        }

        logger.debug(f"Action step executed: {action_type}")
        return output

    async def _execute_wait_step(
        self, context: FlowContext, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a wait step (pause execution for duration).

        Args:
            context: Flow context
            step_def: Step definition

        Returns:
            Step output data
        """
        wait_duration_seconds = step_def.get("duration_seconds", 0)
        wait_until = step_def.get("wait_until")  # Specific datetime

        if wait_until:
            # Wait until specific time
            resume_at = datetime.fromisoformat(wait_until)
        else:
            # Wait for duration
            resume_at = datetime.utcnow() + timedelta(seconds=wait_duration_seconds)

        output = {
            "wait_started": True,
            "resume_at": resume_at.isoformat(),
            "duration_seconds": wait_duration_seconds,
            "flow_data_updates": {"paused_until": resume_at.isoformat()},
            "variables_updates": {},
        }

        logger.debug(f"Wait step: resume at {resume_at}")
        return output

    async def _execute_branch_step(
        self, context: FlowContext, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a branch step (split flow into multiple paths).

        Args:
            context: Flow context
            step_def: Step definition

        Returns:
            Step output data
        """
        branches = step_def.get("branches", [])
        condition = step_def.get("condition")

        # Evaluate which branch to take
        if condition:
            condition_met = await self.evaluate_condition(condition, context)
            branch_taken = branches[0] if condition_met else branches[1]
        else:
            # Default to first branch
            branch_taken = branches[0] if branches else None

        output = {
            "branch_executed": True,
            "branch_taken": branch_taken,
            "total_branches": len(branches),
            "flow_data_updates": {"current_branch": branch_taken},
            "variables_updates": {},
        }

        logger.debug(f"Branch step: took branch '{branch_taken}'")
        return output

    async def _execute_loop_step(
        self, context: FlowContext, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a loop step (loop back to previous step).

        Args:
            context: Flow context
            step_def: Step definition

        Returns:
            Step output data
        """
        loop_to_step = step_def.get("loop_to_step")
        max_iterations = step_def.get("max_iterations", 10)
        loop_condition = step_def.get("condition")

        current_iteration = context.flow_data.get("loop_iteration", 0) + 1

        # Check if should continue loop
        should_continue = current_iteration < max_iterations
        if loop_condition:
            should_continue = should_continue and await self.evaluate_condition(
                loop_condition, context
            )

        output = {
            "loop_executed": True,
            "loop_to_step": loop_to_step if should_continue else None,
            "current_iteration": current_iteration,
            "should_continue": should_continue,
            "flow_data_updates": {"loop_iteration": current_iteration},
            "variables_updates": {},
        }

        logger.debug(
            f"Loop step: iteration {current_iteration}, continue={should_continue}"
        )
        return output

    async def _execute_end_step(
        self, context: FlowContext, step_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute an end step (terminate flow).

        Args:
            context: Flow context
            step_def: Step definition

        Returns:
            Step output data
        """
        end_reason = step_def.get("reason", "completed")
        final_message = step_def.get("final_message")

        output = {
            "flow_ended": True,
            "end_reason": end_reason,
            "final_message": final_message,
            "flow_data_updates": {"ended_at": datetime.utcnow().isoformat()},
            "variables_updates": {},
        }

        logger.info(f"End step: flow ending with reason '{end_reason}'")
        return output

    async def evaluate_condition(
        self, condition: Dict[str, Any], context: FlowContext
    ) -> bool:
        """
        Evaluate a condition against flow context.

        Supports various condition types:
        - Simple comparisons (equals, not_equals, greater_than, etc.)
        - Logical operators (and, or, not)
        - Variable checks (exists, is_empty, etc.)

        Args:
            condition: Condition definition
            context: Flow context with variables

        Returns:
            True if condition is met, False otherwise

        Example:
            >>> condition = {"variable": "age", "operator": "greater_than", "value": 18}
            >>> result = await engine.evaluate_condition(condition, context)
        """
        condition_type = condition.get("type", "simple")

        if condition_type == "simple":
            return self._evaluate_simple_condition(condition, context)
        elif condition_type == "and":
            return all(
                await self.evaluate_condition(c, context)
                for c in condition.get("conditions", [])
            )
        elif condition_type == "or":
            return any(
                await self.evaluate_condition(c, context)
                for c in condition.get("conditions", [])
            )
        elif condition_type == "not":
            return not await self.evaluate_condition(
                condition.get("condition"), context
            )
        else:
            logger.warning(f"Unknown condition type: {condition_type}")
            return False

    def _evaluate_simple_condition(
        self, condition: Dict[str, Any], context: FlowContext
    ) -> bool:
        """
        Evaluate a simple condition (single comparison).

        Args:
            condition: Condition definition
            context: Flow context

        Returns:
            True if condition is met
        """
        variable_name = condition.get("variable")
        operator = condition.get("operator")
        expected_value = condition.get("value")

        # Get actual value from context
        actual_value = context.variables.get(variable_name)

        # Evaluate based on operator
        if operator == "equals":
            return actual_value == expected_value
        elif operator == "not_equals":
            return actual_value != expected_value
        elif operator == "greater_than":
            return actual_value > expected_value
        elif operator == "less_than":
            return actual_value < expected_value
        elif operator == "greater_or_equal":
            return actual_value >= expected_value
        elif operator == "less_or_equal":
            return actual_value <= expected_value
        elif operator == "contains":
            return expected_value in actual_value
        elif operator == "exists":
            return variable_name in context.variables
        elif operator == "is_empty":
            return not actual_value
        else:
            logger.warning(f"Unknown operator: {operator}")
            return False

    def get_next_step(
        self,
        current_step_id: str,
        template: Dict[str, Any],
        context: FlowContext,
        transition_type: FlowTransitionType = FlowTransitionType.AUTOMATIC,
    ) -> Optional[str]:
        """
        Determine the next step to execute.

        Args:
            current_step_id: Current step ID
            template: Flow template definition
            context: Flow context
            transition_type: Type of transition

        Returns:
            Next step ID, or None if flow should end
        """
        # Get transitions from template
        transitions = template.get("transitions", [])

        # Find transition rules for current step
        for transition in transitions:
            if transition.get("from") == current_step_id:
                # Check if conditions are met
                conditions = transition.get("conditions", [])
                if not conditions or all(
                    self._evaluate_simple_condition(c, context) for c in conditions
                ):
                    next_step = transition.get("to")
                    logger.debug(f"Transition: {current_step_id} → {next_step}")
                    return next_step

        # Default: look for sequential next step
        steps = template.get("steps", [])
        step_ids = [s.get("step_id") for s in steps]

        try:
            current_index = step_ids.index(current_step_id)
            if current_index < len(step_ids) - 1:
                next_step = step_ids[current_index + 1]
                logger.debug(f"Sequential transition: {current_step_id} → {next_step}")
                return next_step
        except ValueError:
            logger.warning(f"Step {current_step_id} not found in template")

        # No next step found
        logger.debug(f"No next step for {current_step_id}, flow should end")
        return None

    async def transition_state(
        self,
        context: FlowContext,
        from_step: str,
        to_step: Optional[str],
        transition_type: FlowTransitionType = FlowTransitionType.AUTOMATIC,
    ) -> FlowContext:
        """
        Transition flow state from one step to another.

        Args:
            context: Current flow context
            from_step: Current step ID
            to_step: Next step ID (None if ending)
            transition_type: Type of transition

        Returns:
            Updated flow context
        """
        logger.info(
            f"State transition: {from_step} → {to_step} (type: {transition_type})"
        )

        # Update current step
        context.current_step_id = to_step

        # If no next step, mark flow as completed
        if to_step is None:
            context.status = FlowStatus.COMPLETED
            context.completed_at = datetime.utcnow()
            logger.info(f"Flow {context.flow_instance_id} completed")

        # Update flow data
        context.flow_data["last_transition"] = {
            "from": from_step,
            "to": to_step,
            "type": transition_type.value,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return context

    def _substitute_variables(self, template: str, variables: Dict[str, Any]) -> str:
        """
        Substitute variables in a template string.

        Supports {{variable_name}} syntax.

        Args:
            template: Template string
            variables: Variables to substitute

        Returns:
            String with variables substituted
        """
        result = template
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            result = result.replace(placeholder, str(value))
        return result

    def __repr__(self) -> str:
        """String representation."""
        return f"<FlowEngine(config_loaded={self.config is not None})>"
