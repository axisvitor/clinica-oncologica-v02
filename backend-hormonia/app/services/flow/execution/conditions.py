"""
Condition evaluation utilities for Flow Services.

These helpers centralize conditional logic used by transitions and
branching steps so they can be reused by both the engine and validators.
"""

from __future__ import annotations

from typing import Any, Dict
import logging

from ..types import FlowContext

logger = logging.getLogger(__name__)


class ConditionEvaluator:
    """Evaluates simple boolean expressions against a FlowContext."""

    def evaluate(self, condition: Dict[str, Any], context: FlowContext) -> bool:
        condition_type = condition.get("type", "simple")

        if condition_type == "simple":
            return self._evaluate_simple(condition, context)
        if condition_type == "and":
            return all(
                self.evaluate(child, context)
                for child in condition.get("conditions", [])
            )
        if condition_type == "or":
            return any(
                self.evaluate(child, context)
                for child in condition.get("conditions", [])
            )
        if condition_type == "not":
            return not self.evaluate(condition.get("condition", {}), context)

        logger.warning("Unknown condition type '%s'", condition_type)
        return False

    def _evaluate_simple(self, condition: Dict[str, Any], context: FlowContext) -> bool:
        variable_name = condition.get("variable")
        operator = condition.get("operator")
        expected_value = condition.get("value")
        actual_value = context.variables.get(variable_name)

        if operator == "equals":
            return actual_value == expected_value
        if operator == "not_equals":
            return actual_value != expected_value
        if operator == "greater_than":
            return actual_value > expected_value
        if operator == "less_than":
            return actual_value < expected_value
        if operator == "greater_or_equal":
            return actual_value >= expected_value
        if operator == "less_or_equal":
            return actual_value <= expected_value
        if operator == "in":
            return actual_value in (expected_value or [])
        if operator == "not_in":
            return actual_value not in (expected_value or [])

        logger.warning("Unsupported operator '%s'", operator)
        return False


__all__ = ["ConditionEvaluator"]
