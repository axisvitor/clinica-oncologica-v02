"""
AlertManager - Core alert orchestration (Refactored).

This module provides the main orchestrator for the alert system,
coordinating alert evaluation, processing, notification, and lifecycle management.

This is the refactored version with modular composition.
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime

from .types import (
    Alert,
    AlertStatus,
    AlertStatistics,
    DashboardData,
    DispatchResult,
)
from .config import get_config, AlertSystemConfig
from .evaluator import AlertEvaluator
from .processor import AlertProcessor
from .escalation import AlertEscalation
from .statistics import AlertStatisticsCollector
from .target_resolver import TargetResolver

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Unified alert management system (Refactored).

    Coordinates:
    - Alert evaluation (via AlertEvaluator)
    - Alert processing (via AlertProcessor)
    - Notification dispatch (via dispatcher)
    - Escalation (via AlertEscalation)
    - Statistics (via AlertStatisticsCollector)
    - Target resolution (via TargetResolver)

    This is the main entry point for all alert operations.
    """

    def __init__(
        self,
        rule_engine: Optional["RuleEngine"] = None,
        processor: Optional["AlertProcessor"] = None,
        dispatcher: Optional["NotificationDispatcher"] = None,
        config: Optional[AlertSystemConfig] = None,
    ):
        """
        Initialize AlertManager.

        Args:
            rule_engine: Rule evaluation engine (injected)
            processor: Alert processor (injected)
            dispatcher: Notification dispatcher (injected)
            config: Alert system configuration
        """
        self.config = config or get_config()

        # Initialize modular components
        self.evaluator = AlertEvaluator(rule_engine=rule_engine)
        self.processor = AlertProcessor(
            processor=processor,
            dispatcher=dispatcher,
            config=self.config,
        )
        self.escalation = AlertEscalation(dispatcher=dispatcher, config=self.config)
        self.statistics = AlertStatisticsCollector()
        self.target_resolver = TargetResolver(config=self.config)

        # Keep references for compatibility
        self.rule_engine = rule_engine
        self.dispatcher = dispatcher

        # Shared state
        self._alert_cache: Dict[UUID, Alert] = {}
        self._alert_history: List[Dict[str, Any]] = []

        # Sync caches
        self.evaluator.set_alert_cache(self._alert_cache)
        self.processor.set_alert_cache(self._alert_cache)

        logger.info("AlertManager initialized (Refactored)")

    # ===== EVALUATION METHODS (delegated to AlertEvaluator) =====

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
        """
        alerts = await self.evaluator.evaluate_patient_alerts(patient_id, context)
        # Sync cache
        self._alert_cache = self.evaluator.get_alert_cache()
        return alerts

    async def evaluate_infrastructure_alerts(
        self, context: Dict[str, Any]
    ) -> List[Alert]:
        """
        Evaluate infrastructure monitoring alerts.

        Args:
            context: Infrastructure context (pool status, metrics, etc.)

        Returns:
            List of triggered alerts
        """
        alerts = await self.evaluator.evaluate_infrastructure_alerts(context)
        # Sync cache
        self._alert_cache = self.evaluator.get_alert_cache()
        return alerts

    # ===== PROCESSING METHODS (delegated to AlertProcessor) =====

    async def process_alert(self, alert: Alert) -> DispatchResult:
        """
        Process an alert through the complete pipeline.

        Args:
            alert: Alert to process

        Returns:
            Notification dispatch result
        """
        result = await self.processor.process_alert(
            alert=alert,
            alert_cache=self._alert_cache,
            should_escalate_callback=self.escalation.should_escalate,
            schedule_escalation_callback=lambda a: self.escalation.schedule_escalation(
                a, self._alert_cache
            ),
            get_notification_targets_callback=self.target_resolver.get_notification_targets,
        )
        # Sync cache
        self._alert_cache = self.processor.get_alert_cache()
        return result

    # ===== LIFECYCLE METHODS =====

    async def acknowledge_alert(
        self, alert_id: UUID, user_id: UUID, notes: Optional[str] = None
    ) -> Alert:
        """
        Acknowledge an alert.

        Args:
            alert_id: Alert UUID
            user_id: User acknowledging the alert
            notes: Optional acknowledgment notes

        Returns:
            Updated alert
        """
        logger.info(f"Acknowledging alert {alert_id} by user {user_id}")

        # Get alert
        alert = await self._get_alert(alert_id)

        if alert.status == AlertStatus.ACKNOWLEDGED:
            raise ValueError(f"Alert {alert_id} already acknowledged")

        if alert.status == AlertStatus.RESOLVED:
            raise ValueError(f"Alert {alert_id} already resolved")

        # Update alert
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.now()
        alert.acknowledged_by = user_id

        if notes:
            alert.metadata["acknowledgment_notes"] = notes

        # Store updated alert
        self._alert_cache[alert_id] = alert

        logger.info(f"Alert {alert_id} acknowledged successfully")

        return alert

    async def resolve_alert(
        self, alert_id: UUID, resolution: str, user_id: Optional[UUID] = None
    ) -> Alert:
        """
        Resolve an alert.

        Args:
            alert_id: Alert UUID
            resolution: Resolution description
            user_id: User resolving the alert (optional)

        Returns:
            Updated alert
        """
        logger.info(f"Resolving alert {alert_id}")

        # Get alert
        alert = await self._get_alert(alert_id)

        if alert.status == AlertStatus.RESOLVED:
            raise ValueError(f"Alert {alert_id} already resolved")

        # Update alert
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now()
        alert.resolved_by = user_id
        alert.metadata["resolution"] = resolution

        # Store updated alert
        self._alert_cache[alert_id] = alert

        # Add to history
        self._alert_history.append(
            {
                "alert_id": str(alert_id),
                "resolved_at": alert.resolved_at.isoformat(),
                "resolution": resolution,
            }
        )

        logger.info(f"Alert {alert_id} resolved successfully")

        return alert

    # ===== STATISTICS METHODS (delegated to AlertStatisticsCollector) =====

    def get_alert_statistics(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> AlertStatistics:
        """
        Get alert statistics.

        Args:
            filters: Optional filters (date range, severity, rule type, etc.)

        Returns:
            Alert statistics
        """
        return self.statistics.get_alert_statistics(self._alert_cache, filters)

    def get_dashboard_data(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> DashboardData:
        """
        Get dashboard aggregated data.

        Args:
            filters: Optional filters

        Returns:
            Dashboard data
        """
        return self.statistics.get_dashboard_data(self._alert_cache, filters)

    # ===== PRIVATE HELPER METHODS =====

    async def _get_alert(self, alert_id: UUID) -> Alert:
        """Get alert by ID."""
        if alert_id not in self._alert_cache:
            raise ValueError(f"Alert {alert_id} not found")
        return self._alert_cache[alert_id]


# Singleton instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """
    Get global AlertManager instance.

    Returns:
        AlertManager singleton
    """
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def set_alert_manager(manager: AlertManager) -> None:
    """
    Set global AlertManager instance.

    Args:
        manager: AlertManager instance to use
    """
    global _alert_manager
    _alert_manager = manager
