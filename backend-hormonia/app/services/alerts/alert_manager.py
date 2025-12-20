"""
AlertManager - Core alert orchestration for the unified alert system.

This module provides the main orchestrator for the alert system,
coordinating alert evaluation, processing, notification, and lifecycle management.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Set, TYPE_CHECKING
from uuid import UUID
from datetime import datetime, timedelta, timezone

if TYPE_CHECKING:
    from .rule_engine import RuleEngine
    from .notification_dispatcher import NotificationDispatcher
    from .processor import AlertProcessor

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
        self._escalation_tasks: Set[asyncio.Task] = set()

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
                dispatched_at=datetime.now(timezone.utc),
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
        alert.acknowledged_at = datetime.now(timezone.utc)
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
        alert.resolved_at = datetime.now(timezone.utc)
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
            created_at=datetime.now(timezone.utc),
        )

        self._alert_cache[alert.id] = alert
        return alert

    async def _should_debounce(self, alert: Alert) -> bool:
        """Check if alert should be debounced."""
        debounce_window = timedelta(minutes=self.config.debounce_minutes)
        cutoff_time = datetime.now(timezone.utc) - debounce_window

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
        """
        Determine notification targets for an alert based on severity and type.

        Target resolution logic:
        - INFO/WARNING: Dashboard only (no notification targets)
        - CRITICAL: Admin users via Email + Dashboard
        - FATAL: All admin users via Email + WhatsApp + Dashboard

        For patient alerts, also notify the assigned doctor if available.

        Args:
            alert: Alert to get targets for

        Returns:
            List of NotificationTarget with user_id and channels
        """

        targets: List[NotificationTarget] = []

        # Determine channels based on severity
        if alert.severity == AlertSeverity.INFO:
            # INFO alerts only go to dashboard (no direct notification)
            return targets

        elif alert.severity == AlertSeverity.WARNING:
            # WARNING alerts: Dashboard + Email to system admin
            channels = [NotificationChannel.EMAIL, NotificationChannel.DASHBOARD]

        elif alert.severity == AlertSeverity.CRITICAL:
            # CRITICAL alerts: Email + Dashboard + WebSocket
            channels = [
                NotificationChannel.EMAIL,
                NotificationChannel.DASHBOARD,
                NotificationChannel.WEBSOCKET,
            ]

        else:  # FATAL
            # FATAL alerts: All channels including WhatsApp
            channels = [
                NotificationChannel.EMAIL,
                NotificationChannel.WHATSAPP,
                NotificationChannel.DASHBOARD,
                NotificationChannel.WEBSOCKET,
            ]

        # Get notification targets from alert context or config
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

        logger.info(
            f"Resolved {len(targets)} notification targets for alert {alert.id}",
            extra={
                "severity": alert.severity.value,
                "channels": [c.value for c in channels],
            },
        )

        return targets

    async def _resolve_target_users(self, alert: Alert) -> List[UUID]:
        """
        Resolve target user IDs for notification based on alert type.

        For patient alerts: Notify assigned doctor + admin
        For infrastructure alerts: Notify system admins

        Args:
            alert: Alert to resolve targets for

        Returns:
            List of user UUIDs to notify
        """

        target_user_ids: List[UUID] = []

        # Check if alert context contains specific target users
        if "notify_user_ids" in alert.context:
            for uid in alert.context["notify_user_ids"]:
                try:
                    target_user_ids.append(UUID(uid) if isinstance(uid, str) else uid)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid user ID in alert context: {uid}")

        # Check if there's a patient_id and get assigned doctor
        if "patient_id" in alert.context:
            patient_id = alert.context["patient_id"]
            try:
                # Try to get patient's assigned doctor from repository
                from app.repositories.patient_repository import PatientRepository
                from app.dependencies.database import get_db_session

                async for db in get_db_session():
                    patient_repo = PatientRepository(db)
                    patient = await patient_repo.get_by_id(
                        UUID(patient_id) if isinstance(patient_id, str) else patient_id
                    )
                    if (
                        patient
                        and hasattr(patient, "assigned_doctor_id")
                        and patient.assigned_doctor_id
                    ):
                        target_user_ids.append(patient.assigned_doctor_id)
                    break
            except Exception as e:
                logger.warning(f"Could not resolve patient's doctor: {e}")

        # For infrastructure alerts or if no specific targets, notify system admins
        if not target_user_ids or alert.rule_type in [
            AlertRuleType.POOL_EXHAUSTION,
            AlertRuleType.SLOW_QUERY,
            AlertRuleType.CONNECTION_ERROR,
            AlertRuleType.QUERY_TIMEOUT,
            AlertRuleType.HIGH_UTILIZATION,
            AlertRuleType.UNHEALTHY_CONNECTION,
        ]:
            # Get admin user IDs from config or default list
            admin_ids = self.config.metadata.get("admin_user_ids", [])
            for admin_id in admin_ids:
                try:
                    uid = UUID(admin_id) if isinstance(admin_id, str) else admin_id
                    if uid not in target_user_ids:
                        target_user_ids.append(uid)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid admin user ID in config: {admin_id}")

        # Deduplicate
        target_user_ids = list(set(target_user_ids))

        return target_user_ids

    def _should_escalate(self, alert: Alert) -> bool:
        """Check if alert should be escalated."""
        # Escalate critical and fatal alerts
        return alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.FATAL]

    async def _schedule_escalation(self, alert: Alert) -> None:
        """
        Schedule alert escalation if not acknowledged within threshold.

        Escalation logic:
        1. Wait for configured escalation delay (default: 1 hour)
        2. If alert still not acknowledged, escalate
        3. Increase escalation level
        4. Send notifications to escalation targets
        5. Repeat until max_escalation_level reached

        Args:
            alert: Alert to schedule escalation for
        """
        logger.info(
            f"Scheduling escalation for alert {alert.id}",
            extra={
                "severity": alert.severity.value,
                "current_level": alert.escalation_level,
                "max_level": self.config.max_escalation_level,
            },
        )

        # Check if max escalation level reached
        if alert.escalation_level >= self.config.max_escalation_level:
            logger.warning(
                f"Alert {alert.id} reached max escalation level ({self.config.max_escalation_level})"
            )
            return

        # Get escalation delay from config or rule config
        escalation_delay_seconds = self.config.metadata.get(
            "escalation_delay_seconds",
            3600,  # Default: 1 hour
        )

        # For critical/fatal alerts, use shorter escalation time
        if alert.severity == AlertSeverity.FATAL:
            escalation_delay_seconds = min(
                escalation_delay_seconds, 900
            )  # 15 minutes max
        elif alert.severity == AlertSeverity.CRITICAL:
            escalation_delay_seconds = min(
                escalation_delay_seconds, 1800
            )  # 30 minutes max

        # Schedule the escalation as a background task
        task = asyncio.create_task(
            self._execute_escalation(alert.id, escalation_delay_seconds),
            name=f"escalation_{alert.id}",
        )

        # Track the task to prevent garbage collection and enable cleanup
        self._escalation_tasks.add(task)
        task.add_done_callback(self._escalation_tasks.discard)

        logger.info(
            f"Escalation scheduled for alert {alert.id} in {escalation_delay_seconds} seconds"
        )

    async def _execute_escalation(self, alert_id: UUID, delay_seconds: int) -> None:
        """
        Execute escalation after delay.

        Args:
            alert_id: ID of alert to escalate
            delay_seconds: Seconds to wait before escalating
        """
        try:
            # Wait for escalation delay
            await asyncio.sleep(delay_seconds)

            # Get current alert state
            try:
                alert = await self._get_alert(alert_id)
            except ValueError:
                logger.info(f"Alert {alert_id} no longer exists, skipping escalation")
                return

            # Check if alert was acknowledged or resolved
            if alert.status in [
                AlertStatus.ACKNOWLEDGED,
                AlertStatus.RESOLVED,
                AlertStatus.EXPIRED,
            ]:
                logger.info(
                    f"Alert {alert_id} already {alert.status.value}, skipping escalation"
                )
                return

            # Increment escalation level
            alert.escalation_level += 1
            alert.escalated = True
            alert.metadata["last_escalation_at"] = datetime.now(timezone.utc).isoformat()

            logger.warning(
                f"Escalating alert {alert_id} to level {alert.escalation_level}",
                extra={
                    "alert_id": str(alert_id),
                    "severity": alert.severity.value,
                    "level": alert.escalation_level,
                },
            )

            # Get escalation targets (higher level gets more targets)
            escalation_targets = await self._get_escalation_targets(alert)

            # Dispatch escalation notifications if dispatcher available
            if self.dispatcher and escalation_targets:
                # Add escalation flag to alert for notification template
                alert.metadata["is_escalation"] = True
                alert.metadata["escalation_level"] = alert.escalation_level

                escalation_result = await self.dispatcher.dispatch(
                    alert=alert,
                    targets=escalation_targets,
                    channels=[NotificationChannel.EMAIL, NotificationChannel.WHATSAPP],
                )

                logger.info(
                    f"Escalation notifications sent for alert {alert_id}: "
                    f"{escalation_result.total_sent} sent, {escalation_result.total_failed} failed"
                )

            # Update cache
            self._alert_cache[alert_id] = alert

            # Schedule next escalation if not at max level
            if alert.escalation_level < self.config.max_escalation_level:
                await self._schedule_escalation(alert)

        except Exception as e:
            logger.error(
                f"Error executing escalation for alert {alert_id}: {e}", exc_info=True
            )

    async def _get_escalation_targets(self, alert: Alert) -> List[NotificationTarget]:
        """
        Get notification targets for escalated alert.

        Higher escalation levels include more senior targets.

        Args:
            alert: Alert being escalated

        Returns:
            List of escalation targets
        """
        targets: List[NotificationTarget] = []

        # Escalation channels always include Email and WhatsApp for urgency
        escalation_channels = [
            NotificationChannel.EMAIL,
            NotificationChannel.WHATSAPP,
            NotificationChannel.DASHBOARD,
        ]

        # Get escalation target user IDs based on level
        escalation_targets = self.config.metadata.get("escalation_targets", {})

        # Level 1: Team leads
        # Level 2: Department heads
        # Level 3: Executive / On-call

        level_key = f"level_{alert.escalation_level}"
        target_ids = escalation_targets.get(level_key, [])

        # If no specific targets configured, use admin list
        if not target_ids:
            target_ids = self.config.metadata.get("admin_user_ids", [])

        for user_id in target_ids:
            try:
                uid = UUID(user_id) if isinstance(user_id, str) else user_id
                targets.append(
                    NotificationTarget(
                        user_id=uid,
                        channels=escalation_channels,
                        metadata={
                            "alert_id": str(alert.id),
                            "escalation_level": alert.escalation_level,
                            "is_escalation": True,
                        },
                    )
                )
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid escalation target ID: {user_id} - {e}")

        logger.info(
            f"Resolved {len(targets)} escalation targets for alert {alert.id} level {alert.escalation_level}"
        )

        return targets

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
        now = datetime.now(timezone.utc)
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

    async def cleanup(self) -> None:
        """
        Cleanup AlertManager resources on shutdown.

        Cancels all pending escalation tasks to ensure graceful shutdown.
        This should be called when the application is shutting down.
        """
        logger.info(
            f"Cleaning up AlertManager: cancelling {len(self._escalation_tasks)} pending escalation tasks"
        )

        # Cancel all pending escalation tasks
        for task in self._escalation_tasks:
            if not task.done():
                task.cancel()

        # Wait for all tasks to complete cancellation
        if self._escalation_tasks:
            await asyncio.gather(*self._escalation_tasks, return_exceptions=True)

        # Clear the task set
        self._escalation_tasks.clear()

        logger.info("AlertManager cleanup complete")


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
