"""
Alert escalation management system.

This module provides escalation logic for alerts that require
progressive notification and handling.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from dataclasses import dataclass

from ..types import (
    Alert,
    EscalationRule,
    EscalationStrategy,
    NotificationTarget,
)
from ..config import get_config
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


@dataclass
class Escalation:
    """Escalation instance."""

    id: UUID
    alert_id: UUID
    rule_id: UUID
    level: int
    scheduled_at: datetime
    executed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    status: str = "scheduled"  # scheduled, executed, cancelled
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        """Initialize metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}


class EscalationManager:
    """
    Alert escalation manager.

    Handles progressive escalation of alerts based on:
    - Time without acknowledgment
    - Severity level
    - Custom escalation rules
    - Escalation strategies (immediate, delayed, progressive)

    Features:
    - Schedule escalations
    - Execute escalation actions
    - Cancel escalations
    - Track escalation history
    - Multi-level escalation paths
    """

    def __init__(self):
        """Initialize EscalationManager."""
        self.config = get_config()

        # Storage (in-memory, should use database in production)
        self._escalations: Dict[UUID, Escalation] = {}
        self._escalation_rules: Dict[UUID, EscalationRule] = {}
        self._alert_escalations: Dict[
            UUID, List[UUID]
        ] = {}  # alert_id -> escalation_ids

        # Statistics
        self._total_scheduled = 0
        self._total_executed = 0
        self._total_cancelled = 0

        logger.info("EscalationManager initialized")

    def register_escalation_rule(self, rule: EscalationRule) -> None:
        """
        Register an escalation rule.

        Args:
            rule: Escalation rule to register
        """
        self._escalation_rules[rule.id] = rule
        logger.info(
            f"Registered escalation rule {rule.id} for alert type {rule.alert_type.value}"
        )

    def unregister_escalation_rule(self, rule_id: UUID) -> None:
        """
        Unregister an escalation rule.

        Args:
            rule_id: Rule UUID to unregister

        Raises:
            ValueError: If rule not found
        """
        if rule_id not in self._escalation_rules:
            raise ValueError(f"Escalation rule {rule_id} not found")

        del self._escalation_rules[rule_id]
        logger.info(f"Unregistered escalation rule {rule_id}")

    def get_escalation_rule(self, alert: Alert) -> Optional[EscalationRule]:
        """
        Get escalation rule for an alert.

        Args:
            alert: Alert to get rule for

        Returns:
            EscalationRule or None if no matching rule
        """
        for rule in self._escalation_rules.values():
            if rule.alert_type == alert.rule_type and rule.enabled:
                return rule
        return None

    async def schedule_escalation(
        self,
        alert: Alert,
        rule: Optional[EscalationRule] = None,
    ) -> Escalation:
        """
        Schedule an escalation for an alert.

        Args:
            alert: Alert to escalate
            rule: Optional escalation rule (auto-detected if not provided)

        Returns:
            Scheduled escalation

        Raises:
            ValueError: If no escalation rule found
        """
        # Get escalation rule
        if not rule:
            rule = self.get_escalation_rule(alert)

        if not rule:
            raise ValueError(
                f"No escalation rule found for alert type {alert.rule_type.value}"
            )

        # Check if already at max escalation level
        if alert.escalation_level >= self.config.max_escalation_level:
            logger.warning(
                f"Alert {alert.id} already at max escalation level "
                f"({alert.escalation_level})"
            )
            raise ValueError("Alert already at max escalation level")

        # Calculate scheduled time based on strategy
        scheduled_at = self._calculate_escalation_time(alert, rule)

        # Create escalation
        escalation = Escalation(
            id=uuid4(),
            alert_id=alert.id,
            rule_id=rule.id,
            level=alert.escalation_level + 1,
            scheduled_at=scheduled_at,
            status="scheduled",
            metadata={
                "alert_severity": alert.severity.value,
                "strategy": rule.escalation_strategy.value,
                "target": rule.escalation_target,
            },
        )

        # Store escalation
        self._escalations[escalation.id] = escalation

        # Track by alert
        if alert.id not in self._alert_escalations:
            self._alert_escalations[alert.id] = []
        self._alert_escalations[alert.id].append(escalation.id)

        # Update statistics
        self._total_scheduled += 1

        logger.info(
            f"Scheduled escalation {escalation.id} for alert {alert.id} "
            f"at level {escalation.level}, scheduled for {scheduled_at}"
        )

        return escalation

    async def execute_escalation(
        self,
        escalation_id: UUID,
        dispatcher: Optional[Any] = None,
    ) -> bool:
        """
        Execute a scheduled escalation.

        Args:
            escalation_id: Escalation UUID to execute
            dispatcher: NotificationDispatcher instance (optional)

        Returns:
            True if executed successfully

        Raises:
            ValueError: If escalation not found or already executed
        """
        if escalation_id not in self._escalations:
            raise ValueError(f"Escalation {escalation_id} not found")

        escalation = self._escalations[escalation_id]

        if escalation.status == "executed":
            raise ValueError(f"Escalation {escalation_id} already executed")

        if escalation.status == "cancelled":
            raise ValueError(f"Escalation {escalation_id} was cancelled")

        logger.info(f"Executing escalation {escalation_id} at level {escalation.level}")

        try:
            # Get escalation rule
            rule = self._escalation_rules.get(escalation.rule_id)
            if not rule:
                logger.error(f"Escalation rule {escalation.rule_id} not found")
                return False

            # Execute escalation actions
            await self._execute_escalation_actions(escalation, rule, dispatcher)

            # Mark as executed
            escalation.status = "executed"
            escalation.executed_at = now_sao_paulo()

            # Update statistics
            self._total_executed += 1

            logger.info(f"Escalation {escalation_id} executed successfully")
            return True

        except Exception as e:
            logger.error(
                f"Failed to execute escalation {escalation_id}: {e}",
                exc_info=True,
            )
            return False

    async def cancel_escalation(
        self,
        alert_id: UUID,
        reason: str = "Alert acknowledged or resolved",
    ) -> int:
        """
        Cancel all pending escalations for an alert.

        Args:
            alert_id: Alert UUID
            reason: Cancellation reason

        Returns:
            Number of escalations cancelled
        """
        if alert_id not in self._alert_escalations:
            logger.debug(f"No escalations found for alert {alert_id}")
            return 0

        escalation_ids = self._alert_escalations[alert_id]
        cancelled_count = 0

        for escalation_id in escalation_ids:
            escalation = self._escalations.get(escalation_id)
            if escalation and escalation.status == "scheduled":
                escalation.status = "cancelled"
                escalation.cancelled_at = now_sao_paulo()
                escalation.metadata["cancellation_reason"] = reason

                cancelled_count += 1
                self._total_cancelled += 1

                logger.info(
                    f"Cancelled escalation {escalation_id} for alert {alert_id}: {reason}"
                )

        logger.info(f"Cancelled {cancelled_count} escalation(s) for alert {alert_id}")
        return cancelled_count

    def get_pending_escalations(
        self,
        before: Optional[datetime] = None,
    ) -> List[Escalation]:
        """
        Get pending escalations.

        Args:
            before: Optional datetime to filter escalations scheduled before this time

        Returns:
            List of pending escalations
        """
        now = now_sao_paulo()
        cutoff = before or now

        pending = [
            e
            for e in self._escalations.values()
            if e.status == "scheduled" and e.scheduled_at <= cutoff
        ]

        return sorted(pending, key=lambda e: e.scheduled_at)

    def get_alert_escalations(self, alert_id: UUID) -> List[Escalation]:
        """
        Get all escalations for an alert.

        Args:
            alert_id: Alert UUID

        Returns:
            List of escalations
        """
        if alert_id not in self._alert_escalations:
            return []

        escalation_ids = self._alert_escalations[alert_id]
        return [
            self._escalations[eid] for eid in escalation_ids if eid in self._escalations
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get escalation statistics.

        Returns:
            Dictionary of statistics
        """
        total_escalations = len(self._escalations)
        scheduled = sum(
            1 for e in self._escalations.values() if e.status == "scheduled"
        )
        executed = sum(1 for e in self._escalations.values() if e.status == "executed")
        cancelled = sum(
            1 for e in self._escalations.values() if e.status == "cancelled"
        )

        return {
            "total_escalations": total_escalations,
            "scheduled": scheduled,
            "executed": executed,
            "cancelled": cancelled,
            "total_scheduled_lifetime": self._total_scheduled,
            "total_executed_lifetime": self._total_executed,
            "total_cancelled_lifetime": self._total_cancelled,
            "registered_rules": len(self._escalation_rules),
            "alerts_with_escalations": len(self._alert_escalations),
        }

    # Private helper methods

    def _calculate_escalation_time(
        self,
        alert: Alert,
        rule: EscalationRule,
    ) -> datetime:
        """
        Calculate when escalation should occur.

        Args:
            alert: Alert to escalate
            rule: Escalation rule

        Returns:
            Datetime when escalation should occur
        """
        now = now_sao_paulo()

        if rule.escalation_strategy == EscalationStrategy.IMMEDIATE:
            # Escalate immediately
            return now

        elif rule.escalation_strategy == EscalationStrategy.DELAYED:
            # Escalate after fixed delay
            return now + timedelta(seconds=rule.escalation_delay)

        elif rule.escalation_strategy == EscalationStrategy.PROGRESSIVE:
            # Escalate with increasing delays per level
            # Level 1: 1x delay, Level 2: 2x delay, Level 3: 4x delay
            multiplier = 2**alert.escalation_level
            delay_seconds = rule.escalation_delay * multiplier
            return now + timedelta(seconds=delay_seconds)

        else:
            # Default to delayed
            return now + timedelta(seconds=rule.escalation_delay)

    async def _execute_escalation_actions(
        self,
        escalation: Escalation,
        rule: EscalationRule,
        dispatcher: Optional[Any],
    ) -> None:
        """
        Execute actions for an escalation.

        Args:
            escalation: Escalation to execute
            rule: Escalation rule
            dispatcher: NotificationDispatcher instance
        """
        logger.info(
            f"Executing escalation actions for level {escalation.level}: "
            f"target={rule.escalation_target}"
        )

        # Get alert (should be retrieved from repository in production)

        # Determine escalation targets based on rule
        targets = self._get_escalation_targets(rule, escalation.level)

        if not targets:
            logger.warning(f"No escalation targets found for rule {rule.id}")
            return

        # Send escalation notifications
        if dispatcher:
            try:
                # TODO: Import Alert model and retrieve actual alert
                # For now, log the action
                logger.info(
                    f"Would dispatch escalation notification to {len(targets)} target(s)"
                )

                # In production:
                # alert = await get_alert(alert_id)
                # await dispatcher.dispatch(alert, targets)

            except Exception as e:
                logger.error(f"Failed to dispatch escalation notification: {e}")
        else:
            logger.warning("No dispatcher provided for escalation notification")

    def _get_escalation_targets(
        self,
        rule: EscalationRule,
        level: int,
    ) -> List[NotificationTarget]:
        """
        Get notification targets for escalation.

        Args:
            rule: Escalation rule
            level: Escalation level

        Returns:
            List of notification targets
        """
        # TODO: Implement target resolution based on rule.escalation_target
        # For now, return empty list
        #
        # In production, this would:
        # - Parse escalation_target (e.g., "supervisor", "on-call", "admin")
        # - Look up users with those roles
        # - Return NotificationTarget instances
        logger.debug(
            f"Resolving escalation targets for level {level}: {rule.escalation_target}"
        )
        return []


# Singleton instance
_escalation_manager: Optional[EscalationManager] = None


def get_escalation_manager() -> EscalationManager:
    """
    Get global EscalationManager instance.

    Returns:
        EscalationManager singleton
    """
    global _escalation_manager
    if _escalation_manager is None:
        _escalation_manager = EscalationManager()
    return _escalation_manager


def set_escalation_manager(manager: EscalationManager) -> None:
    """
    Set global EscalationManager instance.

    Args:
        manager: EscalationManager instance to use
    """
    global _escalation_manager
    _escalation_manager = manager
