"""
Rules Evaluator Module - Condition Evaluation

Evaluates conditions for business rules.
"""

import logging
from typing import Dict, Any
from datetime import datetime, timezone


logger = logging.getLogger(__name__)


class RuleConditionEvaluator:
    """
    Evaluates conditions for business rules.

    Responsibilities:
    - Evaluate rule conditions
    - Check time-based conditions
    - Validate state conditions
    - Handle complex condition logic
    """

    def __init__(self):
        """Initialize RuleConditionEvaluator."""
        logger.info("RuleConditionEvaluator initialized")

    def evaluate_time_condition(
        self, current_time: datetime, condition: Dict[str, Any]
    ) -> bool:
        """
        Evaluate time-based condition.

        Args:
            current_time: Current datetime
            condition: Condition specification

        Returns:
            True if condition is met
        """
        condition_type = condition.get("type")

        if condition_type == "hour_range":
            start_hour = condition.get("start_hour", 0)
            end_hour = condition.get("end_hour", 24)
            current_hour = current_time.hour
            return start_hour <= current_hour < end_hour

        elif condition_type == "day_of_week":
            allowed_days = condition.get("days", [])
            current_day = current_time.weekday()
            return current_day in allowed_days

        elif condition_type == "business_hours":
            return 8 <= current_time.hour < 18 and current_time.weekday() < 5

        return True

    def evaluate_state_condition(
        self, current_state: str, allowed_states: list[str]
    ) -> bool:
        """
        Evaluate state-based condition.

        Args:
            current_state: Current state
            allowed_states: List of allowed states

        Returns:
            True if state is allowed
        """
        is_allowed = current_state in allowed_states

        logger.debug(
            f"State condition evaluation: {current_state} in {allowed_states} = {is_allowed}"
        )

        return is_allowed

    def evaluate_day_condition(
        self, current_day: int, condition: Dict[str, Any]
    ) -> bool:
        """
        Evaluate treatment day condition.

        Args:
            current_day: Current treatment day
            condition: Condition specification

        Returns:
            True if condition is met
        """
        condition_type = condition.get("type")

        if condition_type == "min_day":
            min_day = condition.get("min_day", 0)
            return current_day >= min_day

        elif condition_type == "max_day":
            max_day = condition.get("max_day", 999)
            return current_day <= max_day

        elif condition_type == "day_range":
            min_day = condition.get("min_day", 0)
            max_day = condition.get("max_day", 999)
            return min_day <= current_day <= max_day

        elif condition_type == "specific_days":
            allowed_days = condition.get("days", [])
            return current_day in allowed_days

        return True

    def evaluate_composite_condition(
        self, conditions: list[Dict[str, Any]], operator: str = "AND"
    ) -> bool:
        """
        Evaluate composite condition with multiple sub-conditions.

        Args:
            conditions: List of condition evaluations
            operator: Logical operator ('AND' or 'OR')

        Returns:
            True if composite condition is met
        """
        if not conditions:
            return True

        results = [c.get("result", False) for c in conditions]

        if operator == "AND":
            return all(results)
        elif operator == "OR":
            return any(results)
        else:
            logger.warning(f"Unknown operator: {operator}, defaulting to AND")
            return all(results)
