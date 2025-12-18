"""
Target Resolver - User and target resolution.

This module handles the resolution of notification targets based on
alert severity, type, and context.
"""

import logging
from typing import List, Optional
from uuid import UUID

from .types import (
    Alert,
    AlertSeverity,
    AlertRuleType,
    NotificationChannel,
    NotificationTarget,
)
from .config import AlertSystemConfig, get_config

logger = logging.getLogger(__name__)


class TargetResolver:
    """
    Handles notification target resolution.

    Responsible for:
    - Determining notification channels based on severity
    - Resolving target users for alerts
    - Handling patient-doctor assignments
    - Managing admin and infrastructure targets
    """

    def __init__(self, config: Optional[AlertSystemConfig] = None):
        """
        Initialize TargetResolver.

        Args:
            config: Alert system configuration
        """
        self.config = config or get_config()

    async def get_notification_targets(self, alert: Alert) -> List[NotificationTarget]:
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
