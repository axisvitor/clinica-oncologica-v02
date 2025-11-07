"""
Rules Engine Module - Business Rules Execution

Executes business rules for flow operations.
"""

import logging
from typing import Dict, Any, Optional, Callable, List
from uuid import UUID

from app.utils.date_helpers import calculate_flow_type_from_day


logger = logging.getLogger(__name__)


class FlowRulesEngine:
    """
    Executes business rules for flow operations.

    Responsibilities:
    - Apply business rules to flow operations
    - Determine flow type from treatment day
    - Evaluate flow conditions
    - Manage rule precedence
    """

    def __init__(self):
        """Initialize FlowRulesEngine."""
        self.rules: Dict[str, List[Callable]] = {
            'flow_start': [],
            'flow_advance': [],
            'flow_pause': [],
            'flow_resume': [],
            'flow_stop': []
        }

        logger.info("FlowRulesEngine initialized")

    def register_rule(
        self,
        rule_type: str,
        rule_function: Callable
    ):
        """
        Register a business rule.

        Args:
            rule_type: Type of rule (flow_start, flow_advance, etc.)
            rule_function: Rule function to execute
        """
        if rule_type in self.rules:
            self.rules[rule_type].append(rule_function)
            logger.info(f"Rule registered for {rule_type}")
        else:
            logger.warning(f"Unknown rule type: {rule_type}")

    async def execute_rules(
        self,
        rule_type: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Execute all rules for a given type.

        Args:
            rule_type: Type of rules to execute
            context: Execution context

        Returns:
            List of rule execution results
        """
        results = []
        rules = self.rules.get(rule_type, [])

        for rule in rules:
            try:
                result = await rule(context) if callable(rule) else None
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Error executing rule: {e}")
                results.append({'success': False, 'error': str(e)})

        return results

    def determine_flow_type(
        self,
        treatment_day: int,
        patient_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Determine flow type based on treatment day and patient metadata.

        Args:
            treatment_day: Current treatment day
            patient_metadata: Additional patient metadata

        Returns:
            Flow type identifier
        """
        flow_type = calculate_flow_type_from_day(treatment_day)

        logger.debug(f"Flow type determined: {flow_type} for day {treatment_day}")
        return flow_type

    def should_transition_flow_type(
        self,
        current_flow_type: str,
        target_day: int
    ) -> tuple[bool, Optional[str]]:
        """
        Determine if flow type should transition.

        Args:
            current_flow_type: Current flow type
            target_day: Target treatment day

        Returns:
            Tuple of (should_transition, new_flow_type)
        """
        new_flow_type = calculate_flow_type_from_day(target_day)

        if new_flow_type != current_flow_type:
            logger.info(f"Flow type transition needed: {current_flow_type} -> {new_flow_type}")
            return True, new_flow_type

        return False, None
