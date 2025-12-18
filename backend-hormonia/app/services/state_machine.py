"""
State machine for flow progression management.
"""

from typing import List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime
from dataclasses import dataclass

from app.services.template_loader import FlowTemplateData, FlowStep, FlowStepCondition


class TransitionResult(Enum):
    """Result of a state transition attempt."""

    SUCCESS = "success"
    CONDITION_NOT_MET = "condition_not_met"
    INVALID_STEP = "invalid_step"
    FLOW_COMPLETED = "flow_completed"
    ERROR = "error"


@dataclass
class StateTransition:
    """Represents a state transition."""

    from_step: int
    to_step: Optional[int]
    result: TransitionResult
    message: str
    conditions_evaluated: List[dict[str, Any]]
    timestamp: datetime


class ConditionEvaluator:
    """Evaluates flow step conditions."""

    @staticmethod
    def evaluate_condition(
        condition: FlowStepCondition, context: dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Evaluate a single condition.

        Args:
            condition: The condition to evaluate
            context: Context data for evaluation

        Returns:
            Tuple of (result, message)
        """
        try:
            if condition.type == "quiz_response":
                return ConditionEvaluator._evaluate_quiz_response(condition, context)
            elif condition.type == "time_based":
                return ConditionEvaluator._evaluate_time_based(condition, context)
            elif condition.type == "patient_data":
                return ConditionEvaluator._evaluate_patient_data(condition, context)
            elif condition.type == "message_count":
                return ConditionEvaluator._evaluate_message_count(condition, context)
            else:
                return False, f"Unknown condition type: {condition.type}"

        except Exception as e:
            return False, f"Error evaluating condition: {str(e)}"

    @staticmethod
    def _evaluate_quiz_response(
        condition: FlowStepCondition, context: dict[str, Any]
    ) -> Tuple[bool, str]:
        """Evaluate quiz response condition."""
        quiz_responses = context.get("quiz_responses", {})

        if not condition.field:
            return False, "Quiz response condition requires field"

        if condition.field not in quiz_responses:
            return False, f"Quiz response field '{condition.field}' not found"

        actual_value = quiz_responses[condition.field]
        expected_value = condition.value

        if condition.operator == "equals":
            result = actual_value == expected_value
        elif condition.operator == "not_equals":
            result = actual_value != expected_value
        elif condition.operator == "greater_than":
            result = actual_value > expected_value
        elif condition.operator == "less_than":
            result = actual_value < expected_value
        elif condition.operator == "contains":
            result = expected_value in str(actual_value)
        else:
            return False, f"Unknown operator: {condition.operator}"

        message = f"Quiz response {condition.field} {condition.operator} {expected_value}: {result}"
        return result, message

    @staticmethod
    def _evaluate_time_based(
        condition: FlowStepCondition, context: dict[str, Any]
    ) -> Tuple[bool, str]:
        """Evaluate time-based condition."""
        current_time = context.get("current_time", datetime.utcnow())

        if condition.field == "hours_since_start":
            start_time = context.get("flow_start_time")
            if not start_time:
                return False, "Flow start time not available"

            hours_elapsed = (current_time - start_time).total_seconds() / 3600
            expected_hours = condition.value

            if condition.operator == "greater_than":
                result = hours_elapsed > expected_hours
            elif condition.operator == "greater_equal":
                result = hours_elapsed >= expected_hours
            else:
                return False, f"Unsupported time operator: {condition.operator}"

            message = f"Hours since start ({hours_elapsed:.1f}) {condition.operator} {expected_hours}: {result}"
            return result, message

        elif condition.field == "time_of_day":
            current_hour = current_time.hour
            target_hour = condition.value

            if condition.operator == "equals":
                result = current_hour == target_hour
            elif condition.operator == "greater_than":
                result = current_hour > target_hour
            elif condition.operator == "less_than":
                result = current_hour < target_hour
            else:
                return False, f"Unsupported time operator: {condition.operator}"

            message = f"Current hour ({current_hour}) {condition.operator} {target_hour}: {result}"
            return result, message

        return False, f"Unknown time field: {condition.field}"

    @staticmethod
    def _evaluate_patient_data(
        condition: FlowStepCondition, context: dict[str, Any]
    ) -> Tuple[bool, str]:
        """Evaluate patient data condition."""
        patient_data = context.get("patient_data", {})

        if not condition.field:
            return False, "Patient data condition requires field"

        if condition.field not in patient_data:
            return False, f"Patient data field '{condition.field}' not found"

        actual_value = patient_data[condition.field]
        expected_value = condition.value

        if condition.operator == "equals":
            result = actual_value == expected_value
        elif condition.operator == "not_equals":
            result = actual_value != expected_value
        elif condition.operator == "in":
            result = (
                actual_value in expected_value
                if isinstance(expected_value, list)
                else False
            )
        else:
            return False, f"Unknown operator: {condition.operator}"

        message = f"Patient data {condition.field} {condition.operator} {expected_value}: {result}"
        return result, message

    @staticmethod
    def _evaluate_message_count(
        condition: FlowStepCondition, context: dict[str, Any]
    ) -> Tuple[bool, str]:
        """Evaluate message count condition."""
        message_count = context.get("message_count", 0)
        expected_count = condition.value

        if condition.operator == "greater_than":
            result = message_count > expected_count
        elif condition.operator == "greater_equal":
            result = message_count >= expected_count
        elif condition.operator == "equals":
            result = message_count == expected_count
        else:
            return False, f"Unknown operator: {condition.operator}"

        message = f"Message count ({message_count}) {condition.operator} {expected_count}: {result}"
        return result, message


class StateMachine:
    """State machine for managing flow progression."""

    def __init__(self, template: FlowTemplateData):
        self.template = template
        self.steps_by_id = {step.id: step for step in template.steps}
        self.condition_evaluator = ConditionEvaluator()

    def get_current_step(self, step_id: int) -> Optional[FlowStep]:
        """Get the current step by ID."""
        return self.steps_by_id.get(step_id)

    def get_next_step_id(self, current_step_id: int) -> Optional[int]:
        """Get the next step ID from current step."""
        current_step = self.get_current_step(current_step_id)
        if current_step:
            return current_step.next_step
        return None

    def can_transition(
        self, from_step_id: int, context: dict[str, Any]
    ) -> Tuple[bool, List[dict[str, Any]]]:
        """
        Check if transition from current step is allowed.

        Args:
            from_step_id: Current step ID
            context: Context data for condition evaluation

        Returns:
            Tuple of (can_transition, conditions_evaluated)
        """
        current_step = self.get_current_step(from_step_id)
        if not current_step:
            return False, [{"error": f"Step {from_step_id} not found"}]

        conditions_evaluated = []

        # If no conditions, transition is allowed
        if not current_step.conditions:
            return True, conditions_evaluated

        # Evaluate all conditions
        all_conditions_met = True
        for condition in current_step.conditions:
            result, message = self.condition_evaluator.evaluate_condition(
                condition, context
            )

            condition_result = {
                "condition": {
                    "type": condition.type,
                    "field": condition.field,
                    "operator": condition.operator,
                    "value": condition.value,
                },
                "result": result,
                "message": message,
            }
            conditions_evaluated.append(condition_result)

            if not result:
                all_conditions_met = False

        return all_conditions_met, conditions_evaluated

    def transition(
        self, from_step_id: int, context: dict[str, Any], force: bool = False
    ) -> StateTransition:
        """
        Attempt to transition from current step to next step.

        Args:
            from_step_id: Current step ID
            context: Context data for condition evaluation
            force: Force transition ignoring conditions

        Returns:
            StateTransition: Result of the transition attempt
        """
        timestamp = datetime.utcnow()

        # Check if current step exists
        current_step = self.get_current_step(from_step_id)
        if not current_step:
            return StateTransition(
                from_step=from_step_id,
                to_step=None,
                result=TransitionResult.INVALID_STEP,
                message=f"Step {from_step_id} not found",
                conditions_evaluated=[],
                timestamp=timestamp,
            )

        # Get next step
        next_step_id = current_step.next_step

        # Check if flow is completed
        if next_step_id is None:
            return StateTransition(
                from_step=from_step_id,
                to_step=None,
                result=TransitionResult.FLOW_COMPLETED,
                message="Flow completed",
                conditions_evaluated=[],
                timestamp=timestamp,
            )

        # Check conditions unless forced
        if not force:
            can_transition, conditions_evaluated = self.can_transition(
                from_step_id, context
            )

            if not can_transition:
                return StateTransition(
                    from_step=from_step_id,
                    to_step=next_step_id,
                    result=TransitionResult.CONDITION_NOT_MET,
                    message="Conditions not met for transition",
                    conditions_evaluated=conditions_evaluated,
                    timestamp=timestamp,
                )
        else:
            conditions_evaluated = []

        # Validate next step exists
        if not self.get_current_step(next_step_id):
            return StateTransition(
                from_step=from_step_id,
                to_step=next_step_id,
                result=TransitionResult.INVALID_STEP,
                message=f"Next step {next_step_id} not found",
                conditions_evaluated=conditions_evaluated,
                timestamp=timestamp,
            )

        # Successful transition
        return StateTransition(
            from_step=from_step_id,
            to_step=next_step_id,
            result=TransitionResult.SUCCESS,
            message=f"Transitioned from step {from_step_id} to {next_step_id}",
            conditions_evaluated=conditions_evaluated,
            timestamp=timestamp,
        )

    def get_available_transitions(
        self, from_step_id: int, context: dict[str, Any]
    ) -> List[dict[str, Any]]:
        """
        Get all available transitions from current step.

        Args:
            from_step_id: Current step ID
            context: Context data for condition evaluation

        Returns:
            List of available transitions with their conditions
        """
        current_step = self.get_current_step(from_step_id)
        if not current_step:
            return []

        transitions = []

        # Main transition
        if current_step.next_step is not None:
            can_transition, conditions = self.can_transition(from_step_id, context)
            next_step = self.get_current_step(current_step.next_step)

            transitions.append(
                {
                    "to_step": current_step.next_step,
                    "to_step_name": next_step.name if next_step else "Unknown",
                    "can_transition": can_transition,
                    "conditions": conditions,
                    "is_completion": False,
                }
            )
        else:
            # Flow completion
            transitions.append(
                {
                    "to_step": None,
                    "to_step_name": "Flow Completion",
                    "can_transition": True,
                    "conditions": [],
                    "is_completion": True,
                }
            )

        return transitions

    def validate_flow(self) -> List[str]:
        """
        Validate the flow template for consistency.

        Returns:
            List of validation errors
        """
        errors = []

        # Check for orphaned steps
        referenced_steps = set()
        for step in self.template.steps:
            if step.next_step is not None:
                referenced_steps.add(step.next_step)

        step_ids = set(step.id for step in self.template.steps)

        # Check for references to non-existent steps
        for ref_step in referenced_steps:
            if ref_step not in step_ids:
                errors.append(f"Step references non-existent step {ref_step}")

        # Check for unreachable steps (start from the first step in sequence)
        reachable_steps = set()

        def mark_reachable(step_id: int):
            if step_id in step_ids and step_id not in reachable_steps:
                reachable_steps.add(step_id)
                step = self.get_current_step(step_id)
                if step and step.next_step is not None:
                    mark_reachable(step.next_step)

        # Start from the first step (lowest ID, which is the entry point)
        if step_ids:
            entry_step = min(step_ids)
            mark_reachable(entry_step)

        for step_id in step_ids:
            if step_id not in reachable_steps:
                errors.append(f"Step {step_id} is unreachable")

        # Check for circular references
        def has_cycle(step_id: int, visited: set, path: set) -> bool:
            if step_id in path:
                return True
            if step_id in visited:
                return False

            visited.add(step_id)
            path.add(step_id)

            step = self.get_current_step(step_id)
            if step and step.next_step is not None:
                if has_cycle(step.next_step, visited, path):
                    return True

            path.remove(step_id)
            return False

        visited = set()
        for step_id in step_ids:
            if step_id not in visited:
                if has_cycle(step_id, visited, set()):
                    errors.append(
                        f"Circular reference detected starting from step {step_id}"
                    )

        return errors
