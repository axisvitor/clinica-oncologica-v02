"""
RuleEngine - Generic alert rule evaluation engine.

This module provides a flexible, extensible rule evaluation system
that supports custom rule types and evaluators.
"""

import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from uuid import UUID
from datetime import datetime

from ..types import (
    AlertRule,
    AlertRuleType,
    AlertEvaluation,
)

logger = logging.getLogger(__name__)


# Type alias for rule evaluator functions
RuleEvaluator = Callable[[AlertRule, Dict[str, Any]], Awaitable[AlertEvaluation]]


class RuleEngine:
    """
    Generic alert rule evaluation engine.

    Features:
    - Register custom rule types
    - Register evaluator functions for each rule type
    - Evaluate rules against context
    - Support async evaluators
    - Cache evaluation results (optional)
    - Track evaluation metrics

    Example:
        >>> engine = RuleEngine()
        >>>
        >>> # Register a rule
        >>> rule = AlertRule(
        ...     id=uuid4(),
        ...     name="High Temperature",
        ...     rule_type=AlertRuleType.CUSTOM,
        ...     severity=AlertSeverity.WARNING,
        ...     condition={"threshold": 38.5},
        ...     enabled=True
        ... )
        >>> engine.register_rule(rule)
        >>>
        >>> # Register evaluator
        >>> async def evaluate_temperature(rule, context):
        ...     temp = context.get("temperature", 0)
        ...     threshold = rule.condition.get("threshold", 37.5)
        ...     triggered = temp > threshold
        ...     return AlertEvaluation(
        ...         rule=rule,
        ...         triggered=triggered,
        ...         context=context,
        ...         reason=f"Temperature {temp}°C exceeds {threshold}°C" if triggered else None
        ...     )
        >>>
        >>> engine.register_evaluator(AlertRuleType.CUSTOM, evaluate_temperature)
        >>>
        >>> # Evaluate
        >>> results = await engine.evaluate_rules({"temperature": 39.2})
    """

    def __init__(self):
        """Initialize RuleEngine."""
        self._rules: Dict[UUID, AlertRule] = {}
        self._rules_by_type: Dict[AlertRuleType, List[AlertRule]] = {}
        self._evaluators: Dict[AlertRuleType, RuleEvaluator] = {}

        self._evaluation_count = 0
        self._triggered_count = 0
        self._cache_enabled = False
        self._evaluation_cache: Dict[str, AlertEvaluation] = {}

        logger.info("RuleEngine initialized")

    def register_rule(self, rule: AlertRule) -> None:
        """
        Register an alert rule.

        Args:
            rule: Alert rule to register

        Raises:
            ValueError: If rule with same ID already exists
        """
        if rule.id in self._rules:
            raise ValueError(f"Rule {rule.id} already registered")

        self._rules[rule.id] = rule

        # Add to type index
        if rule.rule_type not in self._rules_by_type:
            self._rules_by_type[rule.rule_type] = []
        self._rules_by_type[rule.rule_type].append(rule)

        logger.info(
            f"Registered rule {rule.id}: {rule.name} "
            f"(type={rule.rule_type.value}, severity={rule.severity.value})"
        )

    def unregister_rule(self, rule_id: UUID) -> None:
        """
        Unregister an alert rule.

        Args:
            rule_id: Rule UUID to unregister

        Raises:
            ValueError: If rule not found
        """
        if rule_id not in self._rules:
            raise ValueError(f"Rule {rule_id} not found")

        rule = self._rules[rule_id]
        del self._rules[rule_id]

        # Remove from type index
        if rule.rule_type in self._rules_by_type:
            self._rules_by_type[rule.rule_type] = [
                r for r in self._rules_by_type[rule.rule_type] if r.id != rule_id
            ]

        logger.info(f"Unregistered rule {rule_id}")

    def register_evaluator(
        self, rule_type: AlertRuleType, evaluator: RuleEvaluator
    ) -> None:
        """
        Register a rule evaluator function.

        The evaluator function must have signature:
            async def evaluator(rule: AlertRule, context: Dict[str, Any]) -> AlertEvaluation

        Args:
            rule_type: Rule type this evaluator handles
            evaluator: Async evaluator function

        Raises:
            ValueError: If evaluator already registered for this type
        """
        if rule_type in self._evaluators:
            logger.warning(f"Overwriting existing evaluator for {rule_type.value}")

        self._evaluators[rule_type] = evaluator
        logger.info(f"Registered evaluator for rule type {rule_type.value}")

    def unregister_evaluator(self, rule_type: AlertRuleType) -> None:
        """
        Unregister a rule evaluator.

        Args:
            rule_type: Rule type to unregister evaluator for

        Raises:
            ValueError: If no evaluator registered for this type
        """
        if rule_type not in self._evaluators:
            raise ValueError(f"No evaluator registered for {rule_type.value}")

        del self._evaluators[rule_type]
        logger.info(f"Unregistered evaluator for rule type {rule_type.value}")

    async def evaluate_rules(
        self,
        context: Dict[str, Any],
        rule_types: Optional[List[AlertRuleType]] = None,
        rule_ids: Optional[List[UUID]] = None,
    ) -> List[AlertEvaluation]:
        """
        Evaluate alert rules against context.

        Args:
            context: Evaluation context (patient data, metrics, etc.)
            rule_types: Optional list of rule types to evaluate (default: all)
            rule_ids: Optional list of specific rule IDs to evaluate

        Returns:
            List of evaluation results (both triggered and not triggered)

        Raises:
            RuntimeError: If no evaluator registered for a rule type
        """
        logger.debug(f"Evaluating rules with context keys: {list(context.keys())}")

        # Determine which rules to evaluate
        rules_to_evaluate = self._get_rules_to_evaluate(rule_types, rule_ids)

        if not rules_to_evaluate:
            logger.warning("No rules to evaluate")
            return []

        # Evaluate each rule
        evaluations = []
        for rule in rules_to_evaluate:
            if not rule.enabled:
                logger.debug(f"Skipping disabled rule {rule.id}")
                continue

            evaluation = await self._evaluate_rule(rule, context)
            evaluations.append(evaluation)

            # Update metrics
            self._evaluation_count += 1
            if evaluation.triggered:
                self._triggered_count += 1

        logger.info(
            f"Evaluated {len(evaluations)} rules: "
            f"{sum(1 for e in evaluations if e.triggered)} triggered"
        )

        return evaluations

    async def evaluate_rule(
        self, rule_id: UUID, context: Dict[str, Any]
    ) -> AlertEvaluation:
        """
        Evaluate a single rule by ID.

        Args:
            rule_id: Rule UUID to evaluate
            context: Evaluation context

        Returns:
            Evaluation result

        Raises:
            ValueError: If rule not found
            RuntimeError: If no evaluator registered for rule type
        """
        if rule_id not in self._rules:
            raise ValueError(f"Rule {rule_id} not found")

        rule = self._rules[rule_id]
        return await self._evaluate_rule(rule, context)

    def get_rule(self, rule_id: UUID) -> Optional[AlertRule]:
        """
        Get rule by ID.

        Args:
            rule_id: Rule UUID

        Returns:
            Alert rule or None if not found
        """
        return self._rules.get(rule_id)

    def get_rules_by_type(self, rule_type: AlertRuleType) -> List[AlertRule]:
        """
        Get all rules of a specific type.

        Args:
            rule_type: Rule type

        Returns:
            List of rules (empty if none found)
        """
        return self._rules_by_type.get(rule_type, [])

    def get_all_rules(self) -> List[AlertRule]:
        """
        Get all registered rules.

        Returns:
            List of all rules
        """
        return list(self._rules.values())

    def get_enabled_rules(self) -> List[AlertRule]:
        """
        Get all enabled rules.

        Returns:
            List of enabled rules
        """
        return [rule for rule in self._rules.values() if rule.enabled]

    def update_rule(self, rule_id: UUID, updates: Dict[str, Any]) -> AlertRule:
        """
        Update a rule's properties.

        Args:
            rule_id: Rule UUID to update
            updates: Dictionary of fields to update

        Returns:
            Updated rule

        Raises:
            ValueError: If rule not found or invalid field
        """
        if rule_id not in self._rules:
            raise ValueError(f"Rule {rule_id} not found")

        rule = self._rules[rule_id]

        # Update allowed fields
        allowed_fields = {"name", "severity", "condition", "enabled", "metadata"}
        for field, value in updates.items():
            if field not in allowed_fields:
                raise ValueError(f"Cannot update field: {field}")
            setattr(rule, field, value)

        rule.updated_at = datetime.now()

        logger.info(f"Updated rule {rule_id}: {list(updates.keys())}")

        return rule

    def enable_cache(self) -> None:
        """Enable evaluation result caching."""
        self._cache_enabled = True
        logger.info("Rule evaluation caching enabled")

    def disable_cache(self) -> None:
        """Disable evaluation result caching."""
        self._cache_enabled = False
        self._evaluation_cache.clear()
        logger.info("Rule evaluation caching disabled")

    def clear_cache(self) -> None:
        """Clear evaluation cache."""
        self._evaluation_cache.clear()
        logger.debug("Evaluation cache cleared")

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get rule engine metrics.

        Returns:
            Dictionary of metrics
        """
        return {
            "total_rules": len(self._rules),
            "enabled_rules": len(self.get_enabled_rules()),
            "rules_by_type": {
                rule_type.value: len(rules)
                for rule_type, rules in self._rules_by_type.items()
            },
            "registered_evaluators": len(self._evaluators),
            "evaluation_count": self._evaluation_count,
            "triggered_count": self._triggered_count,
            "trigger_rate": (
                self._triggered_count / self._evaluation_count
                if self._evaluation_count > 0
                else 0
            ),
            "cache_enabled": self._cache_enabled,
            "cache_size": len(self._evaluation_cache),
        }

    def reset_metrics(self) -> None:
        """Reset evaluation metrics."""
        self._evaluation_count = 0
        self._triggered_count = 0
        logger.debug("Metrics reset")

    # Private methods

    def _get_rules_to_evaluate(
        self,
        rule_types: Optional[List[AlertRuleType]],
        rule_ids: Optional[List[UUID]],
    ) -> List[AlertRule]:
        """Determine which rules to evaluate based on filters."""
        if rule_ids:
            # Specific rules requested
            return [self._rules[rid] for rid in rule_ids if rid in self._rules]

        if rule_types:
            # Specific types requested
            rules = []
            for rule_type in rule_types:
                rules.extend(self._rules_by_type.get(rule_type, []))
            return rules

        # All rules
        return list(self._rules.values())

    async def _evaluate_rule(
        self, rule: AlertRule, context: Dict[str, Any]
    ) -> AlertEvaluation:
        """
        Evaluate a single rule.

        Args:
            rule: Rule to evaluate
            context: Evaluation context

        Returns:
            Evaluation result

        Raises:
            RuntimeError: If no evaluator registered for rule type
        """
        # Check cache
        if self._cache_enabled:
            cache_key = self._get_cache_key(rule, context)
            if cache_key in self._evaluation_cache:
                logger.debug(f"Cache hit for rule {rule.id}")
                return self._evaluation_cache[cache_key]

        # Get evaluator
        if rule.rule_type not in self._evaluators:
            raise RuntimeError(
                f"No evaluator registered for rule type {rule.rule_type.value}"
            )

        evaluator = self._evaluators[rule.rule_type]

        # Evaluate
        try:
            logger.debug(f"Evaluating rule {rule.id}: {rule.name}")
            evaluation = await evaluator(rule, context)

            # Cache result
            if self._cache_enabled:
                cache_key = self._get_cache_key(rule, context)
                self._evaluation_cache[cache_key] = evaluation

            return evaluation

        except Exception as e:
            logger.error(f"Error evaluating rule {rule.id}: {e}", exc_info=True)
            # Return non-triggered evaluation on error
            return AlertEvaluation(
                rule=rule,
                triggered=False,
                context=context,
                reason=f"Evaluation error: {str(e)}",
                metadata={"error": str(e), "error_type": type(e).__name__},
            )

    def _get_cache_key(self, rule: AlertRule, context: Dict[str, Any]) -> str:
        """Generate cache key for rule and context."""
        # Simple cache key: rule_id + sorted context keys
        context_keys = sorted(context.keys())
        return f"{rule.id}:{':'.join(context_keys)}"


# Singleton instance
_rule_engine: Optional[RuleEngine] = None


def get_rule_engine() -> RuleEngine:
    """
    Get global RuleEngine instance.

    Returns:
        RuleEngine singleton
    """
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = RuleEngine()
    return _rule_engine


def set_rule_engine(engine: RuleEngine) -> None:
    """
    Set global RuleEngine instance.

    Args:
        engine: RuleEngine instance to use
    """
    global _rule_engine
    _rule_engine = engine
