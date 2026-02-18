"""
AlertManager - Refactored orchestrator for the unified alert system.

This is the refactored version following SOLID principles with
clear separation of concerns through dependency injection.
"""

import logging
import inspect
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime

from .types import (
    Alert,
    AlertRuleType,
    AlertSeverity,
    AlertStatus,
    AlertStatistics,
    DashboardData,
    NotificationChannel,
    NotificationTarget,
    DispatchResult,
)
from .config import get_config, AlertSystemConfig
from .notification.dispatcher import (
    NotificationDispatcher,
    get_notification_dispatcher,
)
from .escalation_handler import EscalationHandler, get_escalation_handler
from .persistence_handler import PersistenceHandler, get_persistence_handler
from .threshold_manager import ThresholdManager, get_threshold_manager
from .metrics import MetricsCollector, get_metrics_collector
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Refactored AlertManager - Core orchestrator using dependency injection.

    This class orchestrates alert operations by composing specialized handlers.
    Each handler has a single responsibility:
    - NotificationDispatcher: Dispatch notifications
    - EscalationHandler: Manage escalations
    - PersistenceHandler: Store/retrieve alerts
    - ThresholdManager: Debouncing and thresholds
    - MetricsCollector: Track metrics

    The AlertManager coordinates these handlers without implementing
    their logic directly (Single Responsibility Principle).
    """

    def __init__(
        self,
        notification_handler: Optional[NotificationDispatcher] = None,
        escalation_handler: Optional[EscalationHandler] = None,
        persistence_handler: Optional[PersistenceHandler] = None,
        threshold_manager: Optional[ThresholdManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        rule_engine: Optional[Any] = None,
        processor: Optional[Any] = None,
        config: Optional[AlertSystemConfig] = None,
        dispatcher: Optional[NotificationDispatcher] = None,
        escalation_manager: Optional[EscalationHandler] = None,
        **legacy_kwargs: Any,
    ):
        """
        Initialize AlertManager with dependency injection.

        Args:
            notification_handler: Handles notification dispatch
            escalation_handler: Handles escalation logic
            persistence_handler: Handles alert storage
            threshold_manager: Handles debouncing and thresholds
            metrics_collector: Tracks metrics
            rule_engine: Rule evaluation engine (legacy support)
            processor: Alert processor (legacy support)
            config: Alert system configuration
            dispatcher: Legacy alias for notification_handler
            escalation_manager: Legacy alias for escalation_handler
            legacy_kwargs: Backward-compatible kwargs accepted and ignored
        """
        if legacy_kwargs:
            logger.debug(
                "Ignoring unsupported legacy AlertManager kwargs: %s",
                ", ".join(sorted(legacy_kwargs.keys())),
            )

        # Use provided handlers or get singletons
        self.notification_handler = (
            notification_handler or dispatcher or get_notification_dispatcher()
        )
        self.escalation_handler = (
            escalation_handler or escalation_manager or get_escalation_handler()
        )
        self.persistence_handler = persistence_handler or get_persistence_handler()
        self.threshold_manager = threshold_manager or get_threshold_manager()
        self.metrics_collector = metrics_collector or get_metrics_collector()

        # Compatibility aliases preserved for legacy callsites/tests
        self.dispatcher = self.notification_handler
        self.escalation_manager = self.escalation_handler

        # Legacy support
        self.rule_engine = rule_engine
        self.processor = processor

        # Config
        self.config = config or get_config()

        logger.info("AlertManager initialized (refactored)")

    async def evaluate_patient_alerts(
        self, patient_id: UUID, context: Dict[str, Any]
    ) -> List[Alert]:
        """
        Evaluate all alert rules for a patient.

        Args:
            patient_id: Patient UUID
            context: Evaluation context

        Returns:
            List of triggered alerts

        Raises:
            RuntimeError: If rule engine not configured
        """
        if not self.rule_engine:
            raise RuntimeError("RuleEngine not configured")

        logger.info(f"Evaluating patient alerts for patient {patient_id}")

        context["patient_id"] = str(patient_id)

        evaluations = await self._run_rule_evaluations(
            context=context,
            rule_types=[
                AlertRuleType.NO_RESPONSE,
                AlertRuleType.MISSED_QUIZ,
                AlertRuleType.NEGATIVE_SENTIMENT,
                AlertRuleType.TREATMENT_ADHERENCE,
                AlertRuleType.EMERGENCY_KEYWORDS,
            ],
            patient_id=patient_id,
        )

        triggered_alerts = []
        for evaluation in evaluations:
            if evaluation.triggered:
                alert = await self._create_alert_from_evaluation(evaluation, context)
                triggered_alerts.append(alert)

        logger.info(f"Patient {patient_id}: {len(triggered_alerts)} alerts triggered")

        return triggered_alerts

    async def evaluate_infrastructure_alerts(
        self, context: Dict[str, Any]
    ) -> List[Alert]:
        """
        Evaluate infrastructure monitoring alerts.

        Args:
            context: Infrastructure context

        Returns:
            List of triggered alerts

        Raises:
            RuntimeError: If rule engine not configured
        """
        if not self.rule_engine:
            raise RuntimeError("RuleEngine not configured")

        logger.info("Evaluating infrastructure alerts")

        evaluations = await self._run_rule_evaluations(
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

        triggered_alerts = []
        for evaluation in evaluations:
            if evaluation.triggered:
                alert = await self._create_alert_from_evaluation(evaluation, context)
                triggered_alerts.append(alert)

        logger.info(f"Infrastructure: {len(triggered_alerts)} alerts triggered")

        return triggered_alerts

    async def process_alert(self, alert: Alert) -> DispatchResult:
        """
        Process an alert through the complete pipeline.

        Orchestrates:
        1. Debounce check (ThresholdManager)
        2. Alert processing (Processor)
        3. Persistence (PersistenceHandler)
        4. Target resolution
        5. Notification dispatch (NotificationDispatcher)
        6. Escalation scheduling (EscalationHandler)
        7. Metrics tracking (MetricsCollector)

        Args:
            alert: Alert to process

        Returns:
            Notification dispatch result
        """
        logger.info(f"Processing alert {alert.id}: {alert.title}")

        # 1. Check debouncing
        if await self.threshold_manager.should_debounce(alert):
            logger.info(f"Alert {alert.id} debounced")
            return DispatchResult(
                alert_id=alert.id,
                total_sent=0,
                total_failed=0,
                results=[],
                dispatched_at=datetime.now(),
            )

        # 2. Process alert if processor available
        if self.processor:
            alert = await self.processor.process(alert)

        # 3. Persist alert
        alert = await self.persistence_handler.store_alert(alert)

        # 4. Track metrics
        self.metrics_collector.record_alert_created(alert)

        # 5. Get notification targets
        targets = await self._get_notification_targets(alert)

        # 6. Dispatch notifications
        dispatch_result = await self.notification_handler.dispatch(
            alert=alert,
            targets=targets,
            channels=alert.notification_channels,
        )

        # 7. Track dispatch metrics
        self.metrics_collector.record_alert_dispatched(alert, dispatch_result)

        # 8. Update alert
        alert.notification_sent = True
        alert = await self.persistence_handler.update_alert(alert)

        # 9. Schedule escalation if needed
        if self.escalation_handler.should_escalate(alert):
            await self.escalation_handler.schedule_escalation(
                alert, self.notification_handler
            )

        logger.info(
            f"Alert {alert.id} processed: "
            f"{dispatch_result.total_sent} sent, {dispatch_result.total_failed} failed"
        )

        return dispatch_result

    async def acknowledge_alert(
        self, alert_id: UUID, user_id: UUID, notes: Optional[str] = None
    ) -> Alert:
        """
        Acknowledge an alert.

        Args:
            alert_id: Alert UUID
            user_id: User acknowledging
            notes: Optional notes

        Returns:
            Updated alert

        Raises:
            ValueError: If alert not found or invalid state
        """
        logger.info(f"Acknowledging alert {alert_id} by user {user_id}")

        alert = await self.persistence_handler.get_alert(alert_id)

        if alert.status == AlertStatus.ACKNOWLEDGED:
            raise ValueError(f"Alert {alert_id} already acknowledged")

        if alert.status == AlertStatus.RESOLVED:
            raise ValueError(f"Alert {alert_id} already resolved")

        # Update alert
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = now_sao_paulo()
        alert.acknowledged_by = user_id

        if notes:
            alert.metadata["acknowledgment_notes"] = notes

        # Persist changes
        alert = await self.persistence_handler.update_alert(alert)

        # Cancel escalation
        self.escalation_handler.cancel_escalation(alert_id)

        # Track metrics
        self.metrics_collector.record_alert_acknowledged(alert)

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
            user_id: User resolving (optional)

        Returns:
            Updated alert

        Raises:
            ValueError: If alert not found or already resolved
        """
        logger.info(f"Resolving alert {alert_id}")

        alert = await self.persistence_handler.get_alert(alert_id)

        if alert.status == AlertStatus.RESOLVED:
            raise ValueError(f"Alert {alert_id} already resolved")

        # Update alert
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = now_sao_paulo()
        alert.resolved_by = user_id
        alert.metadata["resolution"] = resolution

        # Persist changes
        alert = await self.persistence_handler.update_alert(alert)

        # Cancel escalation
        self.escalation_handler.cancel_escalation(alert_id)

        # Track metrics
        self.metrics_collector.record_alert_resolved(alert)

        logger.info(f"Alert {alert_id} resolved successfully")

        return alert

    def get_alert_statistics(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> AlertStatistics:
        """
        Get alert statistics.

        Args:
            filters: Optional filters

        Returns:
            Alert statistics
        """
        logger.info("Generating alert statistics")

        # Get alerts from persistence
        alerts = []  # In real impl: await self.persistence_handler.list_alerts(filters)

        # Use metrics collector to calculate statistics
        statistics = self.metrics_collector.get_statistics(alerts, filters)

        logger.info(f"Statistics generated: {statistics.total_alerts} total alerts")

        return statistics

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
        logger.info("Generating dashboard data")

        # Get statistics
        statistics = self.get_alert_statistics(filters)

        # Get recent alerts (would come from persistence in real impl)
        recent_alerts = []

        # Top alert types from statistics
        rule_type_counts = statistics.by_rule_type
        top_alert_types = [
            {"rule_type": rule_type.value, "count": count}
            for rule_type, count in sorted(
                rule_type_counts.items(), key=lambda x: x[1], reverse=True
            )[:10]
        ]

        # Alert timeline
        alert_timeline = self.metrics_collector.generate_timeline(
            recent_alerts, hours=24
        )

        dashboard = DashboardData(
            statistics=statistics,
            recent_alerts=recent_alerts,
            top_alert_types=top_alert_types,
            alert_timeline=alert_timeline,
        )

        logger.info("Dashboard data generated successfully")

        return dashboard

    async def _run_rule_evaluations(
        self,
        context: Dict[str, Any],
        rule_types: List[AlertRuleType],
        patient_id: Optional[UUID] = None,
    ) -> List[Any]:
        """
        Execute rule engine evaluations with backward-compatible interfaces.

        Supports both:
        - rule_engine.evaluate_rules(context=..., rule_types=...)
        - legacy rule_engine.evaluate(patient_id=..., context=...)
        """
        evaluate_rules = getattr(self.rule_engine, "evaluate_rules", None)
        if callable(evaluate_rules):
            maybe_result = evaluate_rules(
                context=context,
                rule_types=rule_types,
            )
            if inspect.isawaitable(maybe_result):
                return await maybe_result

        evaluate = getattr(self.rule_engine, "evaluate", None)
        if callable(evaluate):
            kwargs: Dict[str, Any] = {"context": context}
            if patient_id is not None:
                kwargs["patient_id"] = patient_id
            maybe_result = evaluate(**kwargs)
            if inspect.isawaitable(maybe_result):
                return await maybe_result

        raise RuntimeError("RuleEngine does not provide evaluate interface")

    @staticmethod
    def _coerce_rule_type(value: Any) -> AlertRuleType:
        if isinstance(value, AlertRuleType):
            return value
        try:
            return AlertRuleType(value)
        except Exception:
            return AlertRuleType.CUSTOM

    @staticmethod
    def _coerce_severity(value: Any) -> AlertSeverity:
        if isinstance(value, AlertSeverity):
            return value
        try:
            return AlertSeverity(value)
        except Exception:
            return AlertSeverity.WARNING

    async def _create_alert_from_evaluation(
        self, evaluation: Any, context: Dict[str, Any]
    ) -> Alert:
        """Create alert from rule evaluation result (legacy-compatible)."""
        from uuid import uuid4

        # Current shape: evaluation.rule.<...>; legacy shape: evaluation.<...>
        rule = getattr(evaluation, "rule", None)

        if rule is not None:
            rule_id = getattr(rule, "id", uuid4())
            rule_type = self._coerce_rule_type(
                getattr(rule, "rule_type", AlertRuleType.CUSTOM)
            )
            severity = self._coerce_severity(
                getattr(rule, "severity", AlertSeverity.WARNING)
            )
            title = getattr(rule, "name", "Alert triggered")
        else:
            rule_id = getattr(evaluation, "rule_id", uuid4())
            rule_type = self._coerce_rule_type(
                getattr(evaluation, "rule_type", AlertRuleType.CUSTOM)
            )
            severity = self._coerce_severity(
                getattr(evaluation, "severity", AlertSeverity.WARNING)
            )
            title = getattr(evaluation, "title", "Alert triggered")

        message = (
            getattr(evaluation, "message", None)
            or getattr(evaluation, "reason", None)
            or "Alert triggered"
        )
        eval_context = getattr(evaluation, "context", context) or context
        metadata = getattr(evaluation, "metadata", {}) or {}

        return Alert(
            id=uuid4(),
            rule_id=rule_id,
            rule_type=rule_type,
            severity=severity,
            status=AlertStatus.PENDING,
            title=title,
            message=message,
            context=eval_context,
            metadata=metadata,
            created_at=datetime.now(),
        )

    async def _get_notification_targets(self, alert: Alert) -> List[NotificationTarget]:
        """
        Determine notification targets for an alert.

        Args:
            alert: Alert to get targets for

        Returns:
            List of NotificationTarget
        """

        targets: List[NotificationTarget] = []

        # Determine channels based on severity
        if alert.severity == AlertSeverity.INFO:
            return targets
        elif alert.severity == AlertSeverity.WARNING:
            channels = [NotificationChannel.EMAIL, NotificationChannel.DASHBOARD]
        elif alert.severity == AlertSeverity.CRITICAL:
            channels = [
                NotificationChannel.EMAIL,
                NotificationChannel.DASHBOARD,
                NotificationChannel.WEBSOCKET,
            ]
        else:  # FATAL
            channels = [
                NotificationChannel.EMAIL,
                NotificationChannel.WHATSAPP,
                NotificationChannel.DASHBOARD,
                NotificationChannel.WEBSOCKET,
            ]

        # Get target user IDs
        target_user_ids = await self._resolve_target_users(alert)

        for user_id in target_user_ids:
            targets.append(
                NotificationTarget(
                    user_id=user_id,
                    channels=channels,
                    metadata={
                        "alert_id": str(alert.id),
                        "severity": alert.severity.value,
                        "rule_type": alert.rule_type.value,
                    },
                )
            )

        return targets

    async def _resolve_target_users(self, alert: Alert) -> List[UUID]:
        """
        Resolve target user IDs for notification.

        Args:
            alert: Alert to resolve targets for

        Returns:
            List of user UUIDs
        """

        target_user_ids: List[UUID] = []

        # Check context for specific targets
        if "notify_user_ids" in alert.context:
            for uid in alert.context["notify_user_ids"]:
                try:
                    target_user_ids.append(UUID(uid) if isinstance(uid, str) else uid)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid user ID: {uid}")

        # Default to admin users for infrastructure alerts
        if not target_user_ids or alert.rule_type in [
            AlertRuleType.POOL_EXHAUSTION,
            AlertRuleType.SLOW_QUERY,
            AlertRuleType.CONNECTION_ERROR,
            AlertRuleType.QUERY_TIMEOUT,
            AlertRuleType.HIGH_UTILIZATION,
            AlertRuleType.UNHEALTHY_CONNECTION,
        ]:
            admin_ids = self.config.metadata.get("admin_user_ids", [])
            for admin_id in admin_ids:
                try:
                    uid = UUID(admin_id) if isinstance(admin_id, str) else admin_id
                    if uid not in target_user_ids:
                        target_user_ids.append(uid)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid admin user ID: {admin_id}")

        return list(set(target_user_ids))


# Singleton instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get global AlertManager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def set_alert_manager(manager: AlertManager) -> None:
    """Set global AlertManager instance."""
    global _alert_manager
    _alert_manager = manager
