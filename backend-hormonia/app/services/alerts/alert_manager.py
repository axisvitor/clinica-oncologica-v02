"""
AlertManager - Core alert orchestration for the unified alert system.

This module provides the main orchestrator for the alert system,
coordinating alert evaluation, processing, notification, and lifecycle management.
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from .types import (
    Alert,
    AlertRule,
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

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Unified alert management system.

    Coordinates:
    - Alert evaluation (rule engine)
    - Alert processing (lifecycle)
    - Notification dispatch (multi-channel)
    - Statistics and dashboard data

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
        self.rule_engine = rule_engine
        self.processor = processor
        self.dispatcher = dispatcher
        self.config = config or get_config()

        self._alert_cache: Dict[UUID, Alert] = {}
        self._alert_history: List[Dict[str, Any]] = []

        logger.info("AlertManager initialized")

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

    async def process_alert(self, alert: Alert) -> DispatchResult:
        """
        Process an alert through the complete pipeline.

        Steps:
        1. Check debouncing
        2. Store alert
        3. Determine notification targets
        4. Dispatch notifications
        5. Schedule escalation (if needed)

        Args:
            alert: Alert to process

        Returns:
            Notification dispatch result

        Raises:
            RuntimeError: If required components not configured
        """
        if not self.processor:
            raise RuntimeError("AlertProcessor not configured")
        if not self.dispatcher:
            raise RuntimeError("NotificationDispatcher not configured")

        logger.info(f"Processing alert {alert.id}: {alert.title}")

        # Check debouncing
        if await self._should_debounce(alert):
            logger.info(f"Alert {alert.id} debounced (duplicate within threshold)")
            return DispatchResult(
                alert_id=alert.id,
                total_sent=0,
                total_failed=0,
                results=[],
                dispatched_at=datetime.now(),
            )

        # Process through processor
        processed_alert = await self.processor.process(alert)

        # Get notification targets
        targets = await self._get_notification_targets(processed_alert)

        # Dispatch notifications
        dispatch_result = await self.dispatcher.dispatch(
            alert=processed_alert,
            targets=targets,
            channels=processed_alert.notification_channels,
        )

        # Update alert
        processed_alert.notification_sent = True
        self._alert_cache[processed_alert.id] = processed_alert

        # Schedule escalation if needed
        if self._should_escalate(processed_alert):
            await self._schedule_escalation(processed_alert)

        logger.info(
            f"Alert {alert.id} processed: "
            f"{dispatch_result.total_sent} sent, "
            f"{dispatch_result.total_failed} failed"
        )

        return dispatch_result

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

        Raises:
            ValueError: If alert not found or already acknowledged
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

        Raises:
            ValueError: If alert not found or already resolved
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
        logger.info("Generating alert statistics")

        # Get all alerts (from cache for now, should query repository)
        alerts = list(self._alert_cache.values())

        # Apply filters
        if filters:
            alerts = self._apply_filters(alerts, filters)

        # Calculate statistics
        total_alerts = len(alerts)
        active_alerts = sum(1 for a in alerts if a.status == AlertStatus.ACTIVE)
        acknowledged_alerts = sum(
            1 for a in alerts if a.status == AlertStatus.ACKNOWLEDGED
        )
        resolved_alerts = sum(1 for a in alerts if a.status == AlertStatus.RESOLVED)
        expired_alerts = sum(1 for a in alerts if a.status == AlertStatus.EXPIRED)

        # By severity
        by_severity = {}
        for severity in AlertSeverity:
            by_severity[severity] = sum(1 for a in alerts if a.severity == severity)

        # By rule type
        by_rule_type = {}
        for rule_type in AlertRuleType:
            by_rule_type[rule_type] = sum(1 for a in alerts if a.rule_type == rule_type)

        # By status
        by_status = {}
        for status in AlertStatus:
            by_status[status] = sum(1 for a in alerts if a.status == status)

        # Calculate average times
        avg_resolution_time = self._calculate_average_resolution_time(alerts)
        avg_acknowledgment_time = self._calculate_average_acknowledgment_time(alerts)

        statistics = AlertStatistics(
            total_alerts=total_alerts,
            active_alerts=active_alerts,
            acknowledged_alerts=acknowledged_alerts,
            resolved_alerts=resolved_alerts,
            expired_alerts=expired_alerts,
            by_severity=by_severity,
            by_rule_type=by_rule_type,
            by_status=by_status,
            average_resolution_time=avg_resolution_time,
            average_acknowledgment_time=avg_acknowledgment_time,
        )

        logger.info(f"Statistics generated: {total_alerts} total alerts")

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

        # Get recent alerts
        alerts = list(self._alert_cache.values())
        if filters:
            alerts = self._apply_filters(alerts, filters)

        # Sort by created_at descending
        alerts.sort(key=lambda a: a.created_at, reverse=True)
        recent_alerts = alerts[:20]

        # Top alert types
        rule_type_counts = statistics.by_rule_type
        top_alert_types = [
            {"rule_type": rule_type.value, "count": count}
            for rule_type, count in sorted(
                rule_type_counts.items(), key=lambda x: x[1], reverse=True
            )[:10]
        ]

        # Alert timeline (last 24 hours by hour)
        alert_timeline = self._generate_alert_timeline(alerts)

        dashboard = DashboardData(
            statistics=statistics,
            recent_alerts=recent_alerts,
            top_alert_types=top_alert_types,
            alert_timeline=alert_timeline,
        )

        logger.info("Dashboard data generated successfully")

        return dashboard

    # Private helper methods

    async def _create_alert_from_evaluation(
        self, evaluation, context: Dict[str, Any]
    ) -> Alert:
        """Create alert from rule evaluation result."""
        from uuid import uuid4

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

    async def _should_debounce(self, alert: Alert) -> bool:
        """Check if alert should be debounced."""
        debounce_window = timedelta(minutes=self.config.debounce_minutes)
        cutoff_time = datetime.now() - debounce_window

        # Check for similar alerts within debounce window
        for existing_alert in self._alert_cache.values():
            if (
                existing_alert.rule_type == alert.rule_type
                and existing_alert.severity == alert.severity
                and existing_alert.created_at > cutoff_time
                and existing_alert.id != alert.id
            ):
                return True

        return False

    async def _get_notification_targets(self, alert: Alert) -> List[NotificationTarget]:
        """Determine notification targets for an alert."""
        # TODO: Implement actual target resolution logic
        # For now, return empty list
        return []

    def _should_escalate(self, alert: Alert) -> bool:
        """Check if alert should be escalated."""
        # Escalate critical and fatal alerts
        return alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.FATAL]

    async def _schedule_escalation(self, alert: Alert) -> None:
        """Schedule alert escalation."""
        logger.info(f"Scheduling escalation for alert {alert.id}")
        # TODO: Implement escalation scheduling
        pass

    async def _get_alert(self, alert_id: UUID) -> Alert:
        """Get alert by ID."""
        if alert_id not in self._alert_cache:
            raise ValueError(f"Alert {alert_id} not found")
        return self._alert_cache[alert_id]

    def _apply_filters(
        self, alerts: List[Alert], filters: Dict[str, Any]
    ) -> List[Alert]:
        """Apply filters to alert list."""
        filtered = alerts

        if "severity" in filters:
            filtered = [a for a in filtered if a.severity == filters["severity"]]

        if "rule_type" in filters:
            filtered = [a for a in filtered if a.rule_type == filters["rule_type"]]

        if "status" in filters:
            filtered = [a for a in filtered if a.status == filters["status"]]

        if "start_date" in filters:
            start_date = filters["start_date"]
            filtered = [a for a in filtered if a.created_at >= start_date]

        if "end_date" in filters:
            end_date = filters["end_date"]
            filtered = [a for a in filtered if a.created_at <= end_date]

        return filtered

    def _calculate_average_resolution_time(
        self, alerts: List[Alert]
    ) -> Optional[float]:
        """Calculate average time to resolve alerts."""
        resolved = [a for a in alerts if a.resolved_at and a.created_at]
        if not resolved:
            return None

        total_seconds = sum(
            (a.resolved_at - a.created_at).total_seconds() for a in resolved
        )
        return total_seconds / len(resolved)

    def _calculate_average_acknowledgment_time(
        self, alerts: List[Alert]
    ) -> Optional[float]:
        """Calculate average time to acknowledge alerts."""
        acknowledged = [a for a in alerts if a.acknowledged_at and a.created_at]
        if not acknowledged:
            return None

        total_seconds = sum(
            (a.acknowledged_at - a.created_at).total_seconds() for a in acknowledged
        )
        return total_seconds / len(acknowledged)

    def _generate_alert_timeline(self, alerts: List[Alert]) -> List[Dict[str, Any]]:
        """Generate hourly alert timeline for last 24 hours."""
        now = datetime.now()
        timeline = []

        for hour_offset in range(24):
            hour_start = now - timedelta(hours=hour_offset + 1)
            hour_end = now - timedelta(hours=hour_offset)

            hour_alerts = [a for a in alerts if hour_start <= a.created_at < hour_end]

            timeline.append(
                {
                    "hour": hour_start.strftime("%Y-%m-%d %H:00"),
                    "count": len(hour_alerts),
                    "by_severity": {
                        severity.value: sum(
                            1 for a in hour_alerts if a.severity == severity
                        )
                        for severity in AlertSeverity
                    },
                }
            )

        timeline.reverse()
        return timeline


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
