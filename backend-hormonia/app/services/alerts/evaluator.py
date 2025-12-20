"""
Alert Evaluator - Rule evaluation logic.

This module handles the evaluation of alert rules against patient and
infrastructure context data.
"""

import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4
from datetime import datetime, timezone

if TYPE_CHECKING:
    from .rule_engine import RuleEngine

from .types import (
    Alert,
    AlertRuleType,
    AlertStatus,
)

logger = logging.getLogger(__name__)


class AlertEvaluator:
    """
    Handles alert rule evaluation.

    Responsible for:
    - Evaluating patient alert rules
    - Evaluating infrastructure alert rules
    - Creating alerts from evaluation results
    """

    def __init__(self, rule_engine: Optional["RuleEngine"] = None):
        """
        Initialize AlertEvaluator.

        Args:
            rule_engine: Rule evaluation engine (injected)
        """
        self.rule_engine = rule_engine
        self._alert_cache: Dict[UUID, Alert] = {}

    async def evaluate_patient_alerts(
        self, patient_id: UUID, context: Dict[str, Any]
    ) -> List[Alert]:
        """
        Evaluate all alert rules for a patient.

        Args:
            patient_id: Patient UUID
            context: Evaluation context (messages, quiz responses, etc.)

        Returns:
            List of triggered alerts

        Raises:
            ValueError: If patient_id is invalid
            RuntimeError: If rule engine not configured
        """
        if not self.rule_engine:
            raise RuntimeError("RuleEngine not configured")

        logger.info(f"Evaluating patient alerts for patient {patient_id}")

        # Add patient_id to context
        context["patient_id"] = str(patient_id)

        # Evaluate all patient-related rules
        evaluations = await self.rule_engine.evaluate_rules(
            context=context,
            rule_types=[
                AlertRuleType.NO_RESPONSE,
                AlertRuleType.MISSED_QUIZ,
                AlertRuleType.NEGATIVE_SENTIMENT,
                AlertRuleType.TREATMENT_ADHERENCE,
                AlertRuleType.EMERGENCY_KEYWORDS,
            ],
        )

        # Create alerts for triggered rules
        triggered_alerts = []
        for evaluation in evaluations:
            if evaluation.triggered:
                alert = await self._create_alert_from_evaluation(evaluation, context)
                triggered_alerts.append(alert)

        logger.info(
            f"Patient {patient_id}: {len(triggered_alerts)} alerts triggered "
            f"out of {len(evaluations)} rules evaluated"
        )

        return triggered_alerts

    async def evaluate_infrastructure_alerts(
        self, context: Dict[str, Any]
    ) -> List[Alert]:
        """
        Evaluate infrastructure monitoring alerts.

        Args:
            context: Infrastructure context (pool status, metrics, etc.)

        Returns:
            List of triggered alerts

        Raises:
            RuntimeError: If rule engine not configured
        """
        if not self.rule_engine:
            raise RuntimeError("RuleEngine not configured")

        logger.info("Evaluating infrastructure alerts")

        # Evaluate infrastructure rules
        evaluations = await self.rule_engine.evaluate_rules(
            context=context,
            rule_types=[
                AlertRuleType.POOL_EXHAUSTION,
                AlertRuleType.SLOW_QUERY,
                AlertRuleType.CONNECTION_ERROR,
                AlertRuleType.QUERY_TIMEOUT,
                AlertRuleType.HIGH_UTILIZATION,
                AlertRuleType.UNHEALTHY_CONNECTION,
            ],
        )

        # Create alerts for triggered rules
        triggered_alerts = []
        for evaluation in evaluations:
            if evaluation.triggered:
                alert = await self._create_alert_from_evaluation(evaluation, context)
                triggered_alerts.append(alert)

        logger.info(
            f"Infrastructure: {len(triggered_alerts)} alerts triggered "
            f"out of {len(evaluations)} rules evaluated"
        )

        return triggered_alerts

    async def _create_alert_from_evaluation(
        self, evaluation, context: Dict[str, Any]
    ) -> Alert:
        """Create alert from rule evaluation result."""
        alert = Alert(
            id=uuid4(),
            rule_id=evaluation.rule.id,
            rule_type=evaluation.rule.rule_type,
            severity=evaluation.rule.severity,
            status=AlertStatus.PENDING,
            title=evaluation.rule.name,
            message=evaluation.reason or "Alert triggered",
            context=evaluation.context,
            metadata=evaluation.metadata,
            created_at=datetime.now(),
        )

        self._alert_cache[alert.id] = alert
        return alert

    def get_alert_cache(self) -> Dict[UUID, Alert]:
        """Get the internal alert cache."""
        return self._alert_cache

    def set_alert_cache(self, cache: Dict[UUID, Alert]) -> None:
        """Set the internal alert cache."""
        self._alert_cache = cache
