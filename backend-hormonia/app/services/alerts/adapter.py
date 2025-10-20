"""
AlertManagerAdapter - Compatibility layer for AlertManager integration.

This adapter bridges the consolidated AlertManager with the existing router/API layer
that expects repository access and legacy method signatures.

This is a transitional component for Phase 5 migration (QW-020).
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.alert import AlertRepository
from app.repositories.patient import PatientRepository
from app.repositories.message import MessageRepository
from app.repositories.quiz_response import QuizResponseRepository
from app.models.alert import Alert, AlertSeverity, AlertStatus

from .alert_manager import AlertManager
from .types import AlertStatistics, DashboardData

logger = logging.getLogger(__name__)


class AlertManagerAdapter:
    """
    Adapter that combines AlertManager with repository access.

    Provides a unified interface that:
    - Exposes AlertManager methods for new consolidated logic
    - Provides repository access for existing router/API code
    - Implements missing methods needed by routers
    - Maintains backward compatibility during migration

    This is a temporary bridge during Phase 5 migration.
    """

    def __init__(
        self,
        db: Session,
        alert_manager: Optional[AlertManager] = None,
    ):
        """
        Initialize AlertManagerAdapter.

        Args:
            db: Database session
            alert_manager: AlertManager instance (optional, will create if not provided)
        """
        self.db = db
        self.alert_manager = alert_manager or self._create_alert_manager()

        # Repository access (for compatibility with existing routers)
        self.alert_repo = AlertRepository(db)
        self.patient_repo = PatientRepository(db)
        self.message_repo = MessageRepository(db)
        self.quiz_repo = QuizResponseRepository(db)

        logger.info("AlertManagerAdapter initialized with repository access")

    def _create_alert_manager(self) -> AlertManager:
        """Create AlertManager with default dependencies."""
        from .evaluation.rule_engine import RuleEngine
        from .processing.alert_processor import AlertProcessor
        from .notification.notification_dispatcher import NotificationDispatcher

        rule_engine = RuleEngine()
        processor = AlertProcessor()
        dispatcher = NotificationDispatcher()

        return AlertManager(
            rule_engine=rule_engine,
            processor=processor,
            dispatcher=dispatcher,
        )

    # ============================================================================
    # AlertManager Methods (Delegation)
    # ============================================================================

    async def evaluate_patient_alerts(
        self, patient_id: UUID, context: Dict[str, Any]
    ) -> List[Alert]:
        """
        Evaluate all alert rules for a patient.

        Delegates to AlertManager.evaluate_patient_alerts().
        """
        return await self.alert_manager.evaluate_patient_alerts(patient_id, context)

    async def evaluate_infrastructure_alerts(
        self, context: Dict[str, Any]
    ) -> List[Alert]:
        """
        Evaluate infrastructure monitoring alerts.

        Delegates to AlertManager.evaluate_infrastructure_alerts().
        """
        return await self.alert_manager.evaluate_infrastructure_alerts(context)

    async def process_alert(self, alert: Alert) -> Any:
        """
        Process an alert through the complete pipeline.

        Delegates to AlertManager.process_alert().
        """
        return await self.alert_manager.process_alert(alert)

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
            Updated alert from database
        """
        # Get alert from database
        db_alert = self.alert_repo.get(alert_id)
        if not db_alert:
            raise ValueError(f"Alert {alert_id} not found")

        if db_alert.status == AlertStatus.ACKNOWLEDGED:
            raise ValueError(f"Alert {alert_id} already acknowledged")

        if db_alert.status == AlertStatus.RESOLVED:
            raise ValueError(f"Alert {alert_id} already resolved")

        # Update in database
        db_alert.status = AlertStatus.ACKNOWLEDGED
        db_alert.acknowledged_at = datetime.utcnow()
        db_alert.acknowledged_by = user_id

        if notes:
            if not db_alert.metadata:
                db_alert.metadata = {}
            db_alert.metadata["acknowledgment_notes"] = notes

        self.db.commit()
        self.db.refresh(db_alert)

        logger.info(f"Alert {alert_id} acknowledged by user {user_id}")

        return db_alert

    async def resolve_alert(
        self, alert_id: UUID, user_id: UUID, resolution_notes: Optional[str] = None
    ) -> Alert:
        """
        Resolve an alert.

        Args:
            alert_id: Alert UUID
            user_id: User resolving the alert
            resolution_notes: Resolution notes

        Returns:
            Updated alert from database
        """
        # Get alert from database
        db_alert = self.alert_repo.get(alert_id)
        if not db_alert:
            raise ValueError(f"Alert {alert_id} not found")

        if db_alert.status == AlertStatus.RESOLVED:
            raise ValueError(f"Alert {alert_id} already resolved")

        # Update in database
        db_alert.status = AlertStatus.RESOLVED
        db_alert.resolved_at = datetime.utcnow()
        db_alert.resolved_by = user_id

        if resolution_notes:
            if not db_alert.metadata:
                db_alert.metadata = {}
            db_alert.metadata["resolution"] = resolution_notes

        self.db.commit()
        self.db.refresh(db_alert)

        logger.info(f"Alert {alert_id} resolved by user {user_id}")

        return db_alert

    def get_alert_statistics(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get alert statistics from database.

        Args:
            filters: Optional filters

        Returns:
            Statistics dictionary
        """
        # Query database for statistics
        all_alerts = self.alert_repo.get_paginated(skip=0, limit=10000)[0]

        # Apply filters if provided
        if filters:
            all_alerts = self._apply_filters(all_alerts, filters)

        # Calculate statistics
        total_alerts = len(all_alerts)
        active_alerts = sum(1 for a in all_alerts if a.status == AlertStatus.ACTIVE)
        acknowledged_alerts = sum(
            1 for a in all_alerts if a.status == AlertStatus.ACKNOWLEDGED
        )
        resolved_alerts = sum(1 for a in all_alerts if a.status == AlertStatus.RESOLVED)
        expired_alerts = sum(1 for a in all_alerts if a.status == AlertStatus.EXPIRED)

        # By severity
        by_severity = {}
        for severity in AlertSeverity:
            by_severity[severity.value] = sum(
                1 for a in all_alerts if a.severity == severity
            )

        # By status
        by_status = {}
        for status in AlertStatus:
            by_status[status.value] = sum(1 for a in all_alerts if a.status == status)

        statistics = {
            "total_alerts": total_alerts,
            "active_alerts": active_alerts,
            "acknowledged_alerts": acknowledged_alerts,
            "resolved_alerts": resolved_alerts,
            "expired_alerts": expired_alerts,
            "by_severity": by_severity,
            "by_status": by_status,
        }

        logger.info(f"Statistics generated: {total_alerts} total alerts")

        return statistics

    def get_alert_dashboard_data(self) -> Dict[str, Any]:
        """
        Get dashboard data for alert monitoring.

        Returns:
            Dashboard data dictionary with metrics and recent alerts
        """
        # Get statistics
        statistics = self.get_alert_statistics()

        # Get recent alerts (last 50)
        recent_alerts, _ = self.alert_repo.get_paginated(skip=0, limit=50)

        # Sort by created_at descending
        recent_alerts = sorted(recent_alerts, key=lambda a: a.created_at, reverse=True)

        # Get unacknowledged count
        unacknowledged_count = self.alert_repo.count_unacknowledged()

        # Get critical alerts count
        critical_count = self.alert_repo.count_by_severity(AlertSeverity.CRITICAL)

        dashboard_data = {
            "statistics": statistics,
            "recent_alerts": [self._alert_to_dict(a) for a in recent_alerts[:20]],
            "unacknowledged_count": unacknowledged_count,
            "critical_count": critical_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info("Dashboard data generated successfully")

        return dashboard_data

    def process_escalation(self, alert_id: UUID) -> Dict[str, Any]:
        """
        Manually escalate an alert.

        Args:
            alert_id: Alert UUID to escalate

        Returns:
            Escalation result dictionary
        """
        # Get alert
        alert = self.alert_repo.get(alert_id)
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        # Escalate severity
        current_severity = alert.severity
        escalated = False

        if current_severity == AlertSeverity.LOW:
            alert.severity = AlertSeverity.MEDIUM
            escalated = True
        elif current_severity == AlertSeverity.MEDIUM:
            alert.severity = AlertSeverity.HIGH
            escalated = True
        elif current_severity == AlertSeverity.HIGH:
            alert.severity = AlertSeverity.CRITICAL
            escalated = True

        if escalated:
            # Update metadata
            if not alert.metadata:
                alert.metadata = {}
            alert.metadata["manually_escalated"] = True
            alert.metadata["escalated_at"] = datetime.utcnow().isoformat()
            alert.metadata["previous_severity"] = current_severity.value

            self.db.commit()
            self.db.refresh(alert)

            logger.info(
                f"Alert {alert_id} escalated from {current_severity} to {alert.severity}"
            )

            return {
                "success": True,
                "alert_id": str(alert_id),
                "previous_severity": current_severity.value,
                "new_severity": alert.severity.value,
                "message": "Alert escalated successfully",
            }
        else:
            logger.warning(
                f"Alert {alert_id} is already at maximum severity (CRITICAL)"
            )
            return {
                "success": False,
                "alert_id": str(alert_id),
                "severity": current_severity.value,
                "message": "Alert is already at maximum severity",
            }

    def update_alert_rule(
        self,
        rule_type: str,
        severity: Optional[AlertSeverity] = None,
        threshold: Optional[float] = None,
        time_window_hours: Optional[int] = None,
        description_template: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> bool:
        """
        Update alert rule configuration.

        Note: This is a stub implementation for compatibility.
        Full implementation requires rule configuration storage.

        Args:
            rule_type: Rule type identifier
            severity: New severity level
            threshold: New threshold value
            time_window_hours: New time window
            description_template: New description template
            enabled: Enable/disable rule

        Returns:
            True if successful, False otherwise
        """
        logger.warning(
            f"update_alert_rule called for {rule_type} - "
            "stub implementation, configuration not persisted"
        )

        # TODO: Implement rule configuration persistence
        # For now, just log and return success
        return True

    def update_notification_channel(self, channel_name: str, enabled: bool) -> bool:
        """
        Update notification channel configuration.

        Note: This is a stub implementation for compatibility.
        Full implementation requires channel configuration storage.

        Args:
            channel_name: Channel name (email, sms, whatsapp, etc.)
            enabled: Enable/disable channel

        Returns:
            True if successful, False otherwise
        """
        logger.warning(
            f"update_notification_channel called for {channel_name} - "
            "stub implementation, configuration not persisted"
        )

        # TODO: Implement channel configuration persistence
        # For now, just log and return success
        return True

    # ============================================================================
    # Helper Methods
    # ============================================================================

    def _apply_filters(
        self, alerts: List[Alert], filters: Dict[str, Any]
    ) -> List[Alert]:
        """Apply filters to alert list."""
        filtered = alerts

        if "severity" in filters:
            severity = filters["severity"]
            filtered = [a for a in filtered if a.severity == severity]

        if "status" in filters:
            status = filters["status"]
            filtered = [a for a in filtered if a.status == status]

        if "patient_id" in filters:
            patient_id = filters["patient_id"]
            filtered = [a for a in filtered if a.patient_id == patient_id]

        if "date_from" in filters:
            date_from = filters["date_from"]
            filtered = [a for a in filtered if a.created_at >= date_from]

        if "date_to" in filters:
            date_to = filters["date_to"]
            filtered = [a for a in filtered if a.created_at <= date_to]

        return filtered

    def _alert_to_dict(self, alert: Alert) -> Dict[str, Any]:
        """Convert alert to dictionary for serialization."""
        return {
            "id": str(alert.id),
            "rule_type": alert.rule_type,
            "severity": alert.severity.value,
            "status": alert.status.value,
            "title": alert.title,
            "message": alert.message,
            "patient_id": str(alert.patient_id) if alert.patient_id else None,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
            "acknowledged_at": (
                alert.acknowledged_at.isoformat() if alert.acknowledged_at else None
            ),
            "resolved_at": (
                alert.resolved_at.isoformat() if alert.resolved_at else None
            ),
            "metadata": alert.metadata,
        }

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<AlertManagerAdapter(alert_manager={self.alert_manager}, repositories=4)>"
        )
