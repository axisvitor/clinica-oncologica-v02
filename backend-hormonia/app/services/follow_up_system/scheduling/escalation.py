"""
Escalation action scheduler.
Handles scheduling of escalation notifications to healthcare providers.
"""
import logging
from uuid import UUID
from datetime import datetime

from ..models import FollowUpAction
from ..enums import NotificationChannel

logger = logging.getLogger(__name__)


class EscalationScheduler:
    """Schedules escalation notification actions."""

    def __init__(self, notification_service, patient_repo, active_alerts: dict):
        """
        Initialize escalation scheduler.

        Args:
            notification_service: Notification service instance
            patient_repo: Patient repository
            active_alerts: Active alerts storage
        """
        self.notification_service = notification_service
        self.patient_repo = patient_repo
        self.active_alerts = active_alerts

    async def schedule_escalation_action(self, action: FollowUpAction) -> None:
        """
        Schedule an escalation notification action.

        Args:
            action: FollowUpAction for escalation
        """
        try:
            alert_id = action.parameters.get("alert_id")
            if not alert_id:
                logger.warning(f"No alert_id for escalation action {action.action_id}")
                return

            alert = self.active_alerts.get(UUID(alert_id))
            if not alert:
                logger.warning(f"Alert {alert_id} not found for action {action.action_id}")
                return

            # Send notifications through configured channels
            for channel in alert.notification_channels:
                await self.notification_service.send_provider_notification(
                    patient_id=action.patient_id,
                    patient_repo=self.patient_repo,
                    notification_data=alert,
                    channel=channel
                )

            # Mark action as executed
            action.executed_at = datetime.utcnow()
            action.status = "executed"
            action.execution_result = {
                "notifications_sent": len(alert.notification_channels),
                "channels": [ch.value for ch in alert.notification_channels]
            }

            logger.info(f"Scheduled escalation notifications for action {action.action_id}")

        except Exception as e:
            logger.error(f"Failed to schedule escalation action: {e}")

    async def schedule_provider_notification(self, action: FollowUpAction) -> None:
        """
        Schedule a provider notification action.

        Args:
            action: FollowUpAction for provider notification
        """
        try:
            # Create provider notification
            notification_data = {
                "patient_id": str(action.patient_id),
                "concern": action.parameters.get("concern"),
                "concern_type": action.parameters.get("concern_type"),
                "original_message": action.parameters.get("original_message"),
                "priority": action.priority,
                "created_at": action.created_at.isoformat()
            }

            # Send notification
            await self.notification_service.send_provider_notification(
                patient_id=action.patient_id,
                patient_repo=self.patient_repo,
                notification_data=notification_data,
                channel=NotificationChannel.DASHBOARD_ALERT
            )

            # Mark as executed
            action.executed_at = datetime.utcnow()
            action.status = "executed"

            logger.info(f"Scheduled provider notification for action {action.action_id}")

        except Exception as e:
            logger.error(f"Failed to schedule provider notification: {e}")
