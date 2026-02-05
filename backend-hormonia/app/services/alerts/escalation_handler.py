"""
Escalation handler - Manages alert escalation logic.

This module handles the escalation of unacknowledged alerts,
including scheduling, execution, and target resolution.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID

from .types import (
    Alert,
    AlertStatus,
    AlertSeverity,
    NotificationTarget,
    NotificationChannel,
)
from .config import get_config, AlertSystemConfig

logger = logging.getLogger(__name__)


class EscalationHandler:
    """
    Handles alert escalation logic.

    Responsibilities:
    - Determine if alerts should be escalated
    - Schedule escalations with appropriate delays
    - Resolve escalation targets
    - Execute escalation notifications
    - Track escalation history
    """

    def __init__(self, config: Optional[AlertSystemConfig] = None):
        """
        Initialize escalation handler.

        Args:
            config: Alert system configuration
        """
        self.config = config or get_config()
        self._escalation_tasks: Dict[UUID, asyncio.Task] = {}
        self._escalation_history: List[Dict[str, Any]] = []

        logger.info("EscalationHandler initialized")

    def should_escalate(self, alert: Alert) -> bool:
        """
        Determine if alert should be escalated.

        Args:
            alert: Alert to check

        Returns:
            True if alert should be escalated
        """
        # Only escalate critical and fatal alerts
        if alert.severity not in [AlertSeverity.CRITICAL, AlertSeverity.FATAL]:
            return False

        # Don't escalate if already at max level
        if alert.escalation_level >= self.config.max_escalation_level:
            logger.debug(
                f"Alert {alert.id} already at max escalation level "
                f"({self.config.max_escalation_level})"
            )
            return False

        # Don't escalate if already acknowledged or resolved
        if alert.status in [
            AlertStatus.ACKNOWLEDGED,
            AlertStatus.RESOLVED,
            AlertStatus.EXPIRED,
        ]:
            return False

        return True

    async def schedule_escalation(
        self,
        alert: Alert,
        notification_handler: Optional[Any] = None,
    ) -> None:
        """
        Schedule alert escalation.

        Args:
            alert: Alert to schedule escalation for
            notification_handler: Optional notification handler for dispatch
        """
        if not self.should_escalate(alert):
            logger.debug(f"Alert {alert.id} does not require escalation")
            return

        escalation_delay = self._get_escalation_delay(alert)

        logger.info(
            f"Scheduling escalation for alert {alert.id} in {escalation_delay}s "
            f"(severity: {alert.severity.value}, level: {alert.escalation_level})"
        )

        # Create escalation task
        task = asyncio.create_task(
            self._execute_escalation(alert.id, escalation_delay, notification_handler),
            name=f"escalation_{alert.id}",
        )

        # Store task reference
        self._escalation_tasks[alert.id] = task

    def cancel_escalation(self, alert_id: UUID) -> None:
        """
        Cancel scheduled escalation.

        Args:
            alert_id: ID of alert to cancel escalation for
        """
        task = self._escalation_tasks.get(alert_id)
        if task and not task.done():
            task.cancel()
            logger.info(f"Cancelled escalation for alert {alert_id}")
            del self._escalation_tasks[alert_id]

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
        escalation_config = self.config.metadata.get("escalation_targets", {})

        # Level 1: Team leads
        # Level 2: Department heads
        # Level 3: Executive / On-call

        level_key = f"level_{alert.escalation_level}"
        target_ids = escalation_config.get(level_key, [])

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
            f"Resolved {len(targets)} escalation targets for alert {alert.id} "
            f"level {alert.escalation_level}"
        )

        return targets

    def _get_escalation_delay(self, alert: Alert) -> int:
        """
        Get escalation delay in seconds based on severity.

        Args:
            alert: Alert to get delay for

        Returns:
            Delay in seconds
        """
        default_delay = self.config.metadata.get(
            "escalation_delay_seconds",
            3600,  # Default: 1 hour
        )

        # For critical/fatal alerts, use shorter escalation time
        if alert.severity == AlertSeverity.FATAL:
            return min(default_delay, 900)  # 15 minutes max
        elif alert.severity == AlertSeverity.CRITICAL:
            return min(default_delay, 1800)  # 30 minutes max

        return default_delay

    async def _execute_escalation(
        self,
        alert_id: UUID,
        delay_seconds: int,
        notification_handler: Optional[Any] = None,
    ) -> None:
        """
        Execute escalation after delay.

        Args:
            alert_id: ID of alert to escalate
            delay_seconds: Seconds to wait before escalating
            notification_handler: Optional notification handler for dispatch
        """
        try:
            # Wait for escalation delay
            await asyncio.sleep(delay_seconds)

            # Get current alert state (would need alert repository in real impl)
            # For now, we'll log the escalation
            logger.warning(
                f"Executing escalation for alert {alert_id} "
                f"(this would update alert and send notifications)"
            )

            # Track escalation
            self._escalation_history.append(
                {
                    "alert_id": str(alert_id),
                    "escalated_at": datetime.now().isoformat(),
                    "delay_seconds": delay_seconds,
                }
            )

            # Clean up task reference
            if alert_id in self._escalation_tasks:
                del self._escalation_tasks[alert_id]

            logger.info(f"Escalation executed for alert {alert_id}")

        except asyncio.CancelledError:
            logger.info(f"Escalation cancelled for alert {alert_id}")
            raise

        except Exception as e:
            logger.error(
                f"Error executing escalation for alert {alert_id}: {e}",
                exc_info=True,
            )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get escalation statistics.

        Returns:
            Dictionary with escalation metrics
        """
        active_escalations = sum(
            1 for task in self._escalation_tasks.values() if not task.done()
        )

        return {
            "total_escalations": len(self._escalation_history),
            "active_escalations": active_escalations,
            "completed_escalations": len(self._escalation_history),
            "max_escalation_level": self.config.max_escalation_level,
        }

    def get_history(self, limit: Optional[int] = 100) -> List[Dict[str, Any]]:
        """
        Get escalation history.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of escalation records
        """
        if limit:
            return self._escalation_history[-limit:]
        return self._escalation_history.copy()


# Singleton instance
_escalation_handler: Optional[EscalationHandler] = None


def get_escalation_handler() -> EscalationHandler:
    """
    Get global EscalationHandler instance.

    Returns:
        EscalationHandler singleton
    """
    global _escalation_handler
    if _escalation_handler is None:
        _escalation_handler = EscalationHandler()
    return _escalation_handler


def set_escalation_handler(handler: EscalationHandler) -> None:
    """
    Set global EscalationHandler instance.

    Args:
        handler: EscalationHandler instance to use
    """
    global _escalation_handler
    _escalation_handler = handler
