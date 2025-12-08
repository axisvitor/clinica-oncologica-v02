"""
Provider notification system for the Follow-up Action System.
Handles sending notifications through various channels.
"""
import logging
from typing import Dict, Any, Union
from uuid import UUID

from .enums import NotificationChannel
from .models import EscalationAlert
from app.models.patient import Patient

logger = logging.getLogger(__name__)


class NotificationService:
    """Handles provider notifications through multiple channels."""

    async def send_provider_notification(self,
                                        patient_id: UUID,
                                        patient_repo,
                                        notification_data: Union[Dict[str, Any], EscalationAlert],
                                        channel: NotificationChannel) -> bool:
        """
        Send notification to healthcare provider.

        Args:
            patient_id: Patient UUID
            patient_repo: Patient repository instance
            notification_data: Alert or notification data
            channel: Notification channel to use

        Returns:
            True if notification sent successfully
        """
        try:
            # Get patient information
            patient = patient_repo.get(patient_id)
            if not patient:
                return False

            # Format notification based on channel
            if isinstance(notification_data, EscalationAlert):
                alert = notification_data
                notification_content = self._format_alert_notification(alert, patient)
            else:
                notification_content = self._format_generic_notification(notification_data, patient)

            # Send through appropriate channel
            if channel == NotificationChannel.EMAIL:
                success = await self._send_email_notification(notification_content)
            elif channel == NotificationChannel.SMS:
                success = await self._send_sms_notification(notification_content)
            elif channel == NotificationChannel.DASHBOARD_ALERT:
                success = await self._send_dashboard_alert(notification_content)
            elif channel == NotificationChannel.PUSH_NOTIFICATION:
                success = await self._send_push_notification(notification_content)
            else:
                success = False

            logger.info(f"Sent {channel.value} notification for patient {patient_id}: {success}")
            return success

        except Exception as e:
            logger.error(f"Failed to send provider notification: {e}")
            return False

    def _format_alert_notification(self, alert: EscalationAlert, patient: Patient) -> Dict[str, Any]:
        """
        Format escalation alert for notification.

        Args:
            alert: EscalationAlert instance
            patient: Patient model instance

        Returns:
            Formatted notification content
        """
        return {
            "type": "escalation_alert",
            "patient_name": patient.name,
            "patient_id": str(alert.patient_id),
            "escalation_level": alert.escalation_level.value,
            "concern_type": alert.concern_type.value,
            "description": alert.description,
            "original_message": alert.original_message,
            "recommended_actions": alert.recommended_actions,
            "requires_immediate_response": alert.requires_immediate_response,
            "created_at": alert.created_at.isoformat()
        }

    def _format_generic_notification(self, notification_data: Dict[str, Any], patient: Patient) -> Dict[str, Any]:
        """
        Format generic notification.

        Args:
            notification_data: Notification data dictionary
            patient: Patient model instance

        Returns:
            Formatted notification content
        """
        return {
            "type": "provider_notification",
            "patient_name": patient.name,
            **notification_data
        }

    async def _send_email_notification(self, notification_content: Dict[str, Any]) -> bool:
        """
        Send email notification (placeholder implementation).

        Args:
            notification_content: Formatted notification content

        Returns:
            True if sent successfully
        """
        # In production, integrate with email service
        logger.info(f"Email notification: {notification_content['type']} for {notification_content.get('patient_name')}")
        return True

    async def _send_sms_notification(self, notification_content: Dict[str, Any]) -> bool:
        """
        Send SMS notification (placeholder implementation).

        Args:
            notification_content: Formatted notification content

        Returns:
            True if sent successfully
        """
        # In production, integrate with SMS service
        logger.info(f"SMS notification: {notification_content['type']} for {notification_content.get('patient_name')}")
        return True

    async def _send_dashboard_alert(self, notification_content: Dict[str, Any]) -> bool:
        """
        Send dashboard alert (placeholder implementation).

        Args:
            notification_content: Formatted notification content

        Returns:
            True if sent successfully
        """
        # In production, integrate with dashboard system
        logger.info(f"Dashboard alert: {notification_content['type']} for {notification_content.get('patient_name')}")
        return True

    async def _send_push_notification(self, notification_content: Dict[str, Any]) -> bool:
        """
        Send push notification (placeholder implementation).

        Args:
            notification_content: Formatted notification content

        Returns:
            True if sent successfully
        """
        # In production, integrate with push notification service
        logger.info(f"Push notification: {notification_content['type']} for {notification_content.get('patient_name')}")
        return True
