from typing import Any
"""
Alert evaluation submodule.

Provides rule evaluation engine and evaluator functions for alert rules.
"""

from .rule_engine import (
    RuleEngine,
    RuleEvaluator,
    get_rule_engine,
    set_rule_engine,
)

from .patient_rules import (
    evaluate_no_response,
    evaluate_missed_quiz,
    evaluate_negative_sentiment,
    evaluate_treatment_adherence,
    evaluate_emergency_keywords,
    PATIENT_EVALUATORS,
    register_patient_evaluators,
)

__all__ = [
    # Rule engine
    "RuleEngine",
    "RuleEvaluator",
    "get_rule_engine",
    "set_rule_engine",
    # Patient evaluators
    "evaluate_no_response",
    "evaluate_missed_quiz",
    "evaluate_negative_sentiment",
    "evaluate_treatment_adherence",
    "evaluate_emergency_keywords",
    "PATIENT_EVALUATORS",
    "register_patient_evaluators",
]
