"""
Alert Escalation - Escalation logic and management.

This module handles alert escalation including scheduling, execution,
and target resolution.
"""

import asyncio
import logging
from typing import Dict, List, Optional, TYPE_CHECKING
from uuid import UUID
from datetime import datetime, timezone

if TYPE_CHECKING:
    from .notification_dispatcher import NotificationDispatcher

from .types import (
    Alert,
    AlertSeverity,
    AlertStatus,
    NotificationChannel,
    NotificationTarget,
)
from .config import AlertSystemConfig, get_config

logger = logging.getLogger(__name__)


class AlertEscalation:
    """
    Handles alert escalation logic.

    Responsible for:
    - Determining if alerts should be escalated
    - Scheduling escalation tasks
    - Executing escalation notifications
    - Resolving escalation targets
    """

    def __init__(
        self,
        dispatcher: Optional["NotificationDispatcher"] = None,
        config: Optional[AlertSystemConfig] = None,
    ):
        """
        Initialize AlertEscalation.

        Args:
            dispatcher: Notification dispatcher (injected)
            config: Alert system configuration
        """
        self.dispatcher = dispatcher
        self.config = config or get_config()

    def should_escalate(self, alert: Alert) -> bool:
        """Check if alert should be escalated."""
        # Escalate critical and fatal alerts
        return alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.FATAL]

    async def schedule_escalation(
        self, alert: Alert, alert_cache: Dict[UUID, Alert]
    ) -> None:
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
            alert_cache: Shared alert cache
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
        asyncio.create_task(
            self._execute_escalation(alert.id, escalation_delay_seconds, alert_cache),
            name=f"escalation_{alert.id}",
        )

        logger.info(
            f"Escalation scheduled for alert {alert.id} in {escalation_delay_seconds} seconds"
        )

    async def _execute_escalation(
        self, alert_id: UUID, delay_seconds: int, alert_cache: Dict[UUID, Alert]
    ) -> None:
        """
        Execute escalation after delay.

        Args:
            alert_id: ID of alert to escalate
            delay_seconds: Seconds to wait before escalating
            alert_cache: Shared alert cache
        """
        try:
            # Wait for escalation delay
            await asyncio.sleep(delay_seconds)

            # Get current alert state
            if alert_id not in alert_cache:
                logger.info(f"Alert {alert_id} no longer exists, skipping escalation")
                return

            alert = alert_cache[alert_id]

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
            alert.metadata["last_escalation_at"] = datetime.now().isoformat()

            logger.warning(
                f"Escalating alert {alert_id} to level {alert.escalation_level}",
                extra={
                    "alert_id": str(alert_id),
                    "severity": alert.severity.value,
                    "level": alert.escalation_level,
                },
            )

            # Get escalation targets (higher level gets more targets)
            escalation_targets = await self.get_escalation_targets(alert)

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
            alert_cache[alert_id] = alert

            # Schedule next escalation if not at max level
            if alert.escalation_level < self.config.max_escalation_level:
                await self.schedule_escalation(alert, alert_cache)

        except Exception as e:
            logger.error(
                f"Error executing escalation for alert {alert_id}: {e}", exc_info=True
            )

    async def get_escalation_targets(self, alert: Alert) -> List[NotificationTarget]:
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
