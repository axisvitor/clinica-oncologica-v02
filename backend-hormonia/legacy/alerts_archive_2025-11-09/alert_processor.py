"""
Alert processing service for handling alert workflows and notifications.

⚠️  DEPRECATED: This is the legacy alert processor (pre-QW-020).
    Use app.services.alerts.alert_manager.AlertManager instead.
    This service will be removed in a future version.
"""

import logging
import warnings
import asyncio
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta
from dataclasses import dataclass

import requests
from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.user import User, UserRole
from app.repositories.alert import AlertRepository
from app.repositories.user import UserRepository
from app.services.alert import AlertService
from app.services.websocket_events import websocket_events
from app.schemas.websocket import WebSocketEventType

logger = logging.getLogger(__name__)


def _emit_deprecation_warning(method_name: str) -> None:
    """Emit deprecation warning for legacy alert processor methods."""
    try:
        from app.config.settings import Settings

        settings = Settings()

        if settings.ALERTS_LEGACY_DEPRECATION_WARNING:
            warnings.warn(
                f"AlertProcessor.{method_name} is deprecated and will be removed in a future version. "
                f"Please migrate to app.services.alerts.alert_manager.AlertManager. "
                f"See QW-020 migration guide for details.",
                DeprecationWarning,
                stacklevel=3,
            )
            logger.warning(
                f"DEPRECATED: AlertProcessor.{method_name} called. "
                f"Migrate to AlertManager (QW-020). "
                f"Set USE_CONSOLIDATED_ALERTS=True in settings to use new system."
            )
    except Exception as e:
        # Fail silently if settings not available
        logger.debug(f"Could not emit deprecation warning: {e}")


@dataclass
class NotificationChannel:
    """Configuration for notification channels."""

    channel_type: str  # 'email', 'sms', 'webhook', 'websocket'
    enabled: bool
    config: Dict[str, Any]


@dataclass
class EscalationRule:
    """Configuration for alert escalation."""

    severity: AlertSeverity
    escalation_delay_minutes: int
    escalation_roles: List[UserRole]
    max_escalations: int


class AlertProcessor:
    """
    Service for processing alerts and managing notifications.

    ⚠️  DEPRECATED: This is the legacy alert processor (pre-QW-020).
        Use app.services.alerts.alert_manager.AlertManager instead.

        Migration Path:
        1. Set USE_CONSOLIDATED_ALERTS=True in settings
        2. Update imports: from app.services.alerts.alert_manager import AlertManager
        3. Replace AlertProcessor(db) with AlertManager(db)
        4. Update method calls to new API (see QW-020 docs)
    """

    def __init__(self, db: Session):
        _emit_deprecation_warning("__init__")

        self.db = db
        self.alert_repo = AlertRepository(db)
        self.user_repo = UserRepository(db)
        self.alert_system = AlertService(db)

        # Default notification channels - can be made configurable
        self.notification_channels = {
            "email": NotificationChannel(
                channel_type="email",
                enabled=True,
                config={"smtp_server": "localhost", "port": 587},
            ),
            "websocket": NotificationChannel(
                channel_type="websocket",
                enabled=True,
                config={"broadcast_room": "alerts"},
            ),
            "webhook": NotificationChannel(
                channel_type="webhook", enabled=False, config={"url": "", "timeout": 30}
            ),
        }

        # Default escalation rules
        self.escalation_rules = {
            AlertSeverity.CRITICAL: EscalationRule(
                severity=AlertSeverity.CRITICAL,
                escalation_delay_minutes=15,
                escalation_roles=[UserRole.DOCTOR, UserRole.ADMIN],
                max_escalations=3,
            ),
            AlertSeverity.HIGH: EscalationRule(
                severity=AlertSeverity.HIGH,
                escalation_delay_minutes=60,
                escalation_roles=[UserRole.DOCTOR],
                max_escalations=2,
            ),
            AlertSeverity.MEDIUM: EscalationRule(
                severity=AlertSeverity.MEDIUM,
                escalation_delay_minutes=240,  # 4 hours
                escalation_roles=[UserRole.DOCTOR],
                max_escalations=1,
            ),
            AlertSeverity.LOW: EscalationRule(
                severity=AlertSeverity.LOW,
                escalation_delay_minutes=1440,  # 24 hours
                escalation_roles=[UserRole.DOCTOR],
                max_escalations=1,
            ),
        }

    def process_alert(self, alert: Alert) -> Dict[str, Any]:
        """Process a new alert through the complete workflow."""
        logger.info(f"Processing alert {alert.id} for patient {alert.patient_id}")

        try:
            # Store the alert
            stored_alert = self.alert_system.create_alert(alert)

            # Send immediate notifications
            notification_results = self._send_notifications(stored_alert)

            # Schedule escalation if needed
            escalation_scheduled = self._schedule_escalation(stored_alert)

            # Log processing results
            logger.info(f"Alert {stored_alert.id} processed successfully")

            return {
                "alert_id": stored_alert.id,
                "status": "processed",
                "notifications_sent": notification_results,
                "escalation_scheduled": escalation_scheduled,
                "processed_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error processing alert {alert.id}: {e}")
            raise

    def _send_notifications(self, alert: Alert) -> Dict[str, Any]:
        """Send notifications for an alert through configured channels."""
        results = {}

        # Get relevant users to notify
        target_users = self._get_notification_targets(alert)

        for channel_name, channel in self.notification_channels.items():
            if not channel.enabled:
                continue

            try:
                if channel.channel_type == "email":
                    results[channel_name] = self._send_email_notifications(
                        alert, target_users, channel
                    )
                elif channel.channel_type == "websocket":
                    results[channel_name] = self._send_websocket_notifications(
                        alert, channel
                    )
                elif channel.channel_type == "webhook":
                    results[channel_name] = self._send_webhook_notifications(
                        alert, channel
                    )
                else:
                    logger.warning(
                        f"Unknown notification channel type: {channel.channel_type}"
                    )

            except Exception as e:
                logger.error(
                    f"Error sending {channel_name} notification for alert {alert.id}: {e}"
                )
                results[channel_name] = {"status": "error", "error": str(e)}

        return results

    def _get_notification_targets(self, alert: Alert) -> List[User]:
        """Get users who should be notified about this alert."""
        # Get the patient's doctor
        patient = alert.patient
        target_users = [patient.doctor] if patient and patient.doctor else []

        # For critical alerts, also notify admins
        if alert.severity == AlertSeverity.CRITICAL:
            admins = (
                self.db.query(User)
                .filter(User.role == UserRole.ADMIN)
                .filter(User.is_active == True)
                .all()
            )
            target_users.extend(admins)

        # For high severity alerts, also notify other doctors
        elif alert.severity == AlertSeverity.HIGH:
            doctors = (
                self.db.query(User)
                .filter(User.role == UserRole.DOCTOR)
                .filter(User.is_active == True)
                .limit(3)  # Limit to avoid spam
                .all()
            )
            target_users.extend(doctors)

        # Remove duplicates
        return list(set(target_users))

    def _send_email_notifications(
        self, alert: Alert, users: List[User], channel: NotificationChannel
    ) -> Dict[str, Any]:
        """Send email notifications via external provider."""
        logger.info(
            f"Sending email notifications for alert {alert.id} to {len(users)} users"
        )

        email_addresses = [user.email for user in users if user.email]
        subject = f"Medical Alert: {alert.alert_type.title()} - {alert.severity.value.title()}"
        body = alert.description or ""
        provider = channel.config.get("provider", "sendgrid").lower()
        result: Dict[str, Any] = {
            "recipients": email_addresses,
            "subject": subject,
            "provider": provider,
        }

        if not email_addresses:
            result["status"] = "no_recipients"
            result["sent_at"] = datetime.utcnow().isoformat()
            return result

        try:
            if provider == "sendgrid":
                api_key = channel.config.get("api_key")
                from_email = channel.config.get("from_email", "alerts@example.com")
                if not api_key:
                    raise ValueError("Missing SendGrid API key")
                payload = {
                    "personalizations": [
                        {"to": [{"email": addr} for addr in email_addresses]}
                    ],
                    "from": {"email": from_email},
                    "subject": subject,
                    "content": [{"type": "text/plain", "value": body}],
                }
                response = requests.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    json=payload,
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=channel.config.get("timeout", 10),
                )
                if response.status_code >= 400:
                    raise requests.RequestException(
                        f"SendGrid error: {response.status_code}"
                    )
                result.update({"status": "sent", "response_code": response.status_code})
            elif provider == "ses":
                try:
                    import boto3
                except Exception as exc:  # pragma: no cover
                    raise RuntimeError("boto3 is required for SES support") from exc
                ses = boto3.client("ses", region_name=channel.config.get("region"))
                response = ses.send_email(
                    Source=channel.config.get("from_email", "alerts@example.com"),
                    Destination={"ToAddresses": email_addresses},
                    Message={
                        "Subject": {"Data": subject},
                        "Body": {"Text": {"Data": body}},
                    },
                )
                result.update(
                    {"status": "sent", "message_id": response.get("MessageId")}
                )
            else:
                raise ValueError(f"Unsupported email provider: {provider}")
        except Exception as e:  # pragma: no cover
            logger.error(f"Error sending email notification: {e}")
            result.update({"status": "error", "error": str(e)})

        result["sent_at"] = datetime.utcnow().isoformat()
        return result

    def _send_websocket_notifications(
        self, alert: Alert, channel: NotificationChannel
    ) -> Dict[str, Any]:
        """Broadcast alert notifications via WebSocket."""
        logger.info(f"Broadcasting alert {alert.id} via WebSocket")

        data = {
            "alert_id": str(alert.id),
            "patient_id": str(alert.patient_id),
            "severity": alert.severity.value,
            "type": alert.alert_type,
            "description": alert.description,
        }

        try:
            sent_count = asyncio.run(
                websocket_events.publish_alert_event(
                    WebSocketEventType.ALERT_CREATED,
                    alert_id=alert.id,
                    patient_id=alert.patient_id,
                    alert_type=alert.alert_type,
                    severity=alert.severity.value,
                    title=f"Medical Alert: {alert.alert_type.title()}",
                    description=alert.description,
                    metadata={"channel": "websocket"},
                )
            )
        except Exception as e:  # pragma: no cover
            logger.error(f"Error broadcasting websocket notification: {e}")
            return {"status": "error", "error": str(e)}

        return {
            "status": "broadcasted",
            "room": channel.config.get("broadcast_room", "alerts"),
            "event": WebSocketEventType.ALERT_CREATED.value,
            "data": data,
            "sent_count": sent_count,
            "sent_at": datetime.utcnow().isoformat(),
        }

    def _send_webhook_notifications(
        self, alert: Alert, channel: NotificationChannel
    ) -> Dict[str, Any]:
        """Send webhook notifications to configured endpoints."""
        logger.info(f"Sending webhook notification for alert {alert.id}")

        urls = channel.config.get("urls") or [channel.config.get("url")]
        urls = [u for u in urls if u]
        payload = {
            "alert_id": str(alert.id),
            "patient_id": str(alert.patient_id),
            "severity": alert.severity.value,
            "type": alert.alert_type,
            "description": alert.description,
            "created_at": alert.created_at.isoformat(),
        }
        timeout = channel.config.get("timeout", 30)

        results = []
        for url in urls:
            try:
                response = requests.post(url, json=payload, timeout=timeout)
                response.raise_for_status()
                results.append(
                    {"url": url, "status": "sent", "status_code": response.status_code}
                )
            except Exception as e:  # pragma: no cover
                logger.error(f"Webhook notification failed for {url}: {e}")
                results.append({"url": url, "status": "error", "error": str(e)})

        return {
            "status": "completed",
            "results": results,
            "payload": payload,
            "sent_at": datetime.utcnow().isoformat(),
        }

    def _schedule_escalation(self, alert: Alert) -> bool:
        """Schedule escalation for an alert if needed."""
        escalation_rule = self.escalation_rules.get(alert.severity)
        if not escalation_rule:
            return False

        # This would typically schedule a background task
        logger.info(
            f"Scheduling escalation for alert {alert.id} in {escalation_rule.escalation_delay_minutes} minutes"
        )

        # Store escalation metadata in alert data
        if not alert.data:
            alert.data = {}

        alert.data["escalation"] = {
            "scheduled": True,
            "delay_minutes": escalation_rule.escalation_delay_minutes,
            "max_escalations": escalation_rule.max_escalations,
            "current_escalation": 0,
            "next_escalation_at": (
                datetime.utcnow()
                + timedelta(minutes=escalation_rule.escalation_delay_minutes)
            ).isoformat(),
        }

        self.alert_repo.update(alert)
        return True

    def process_escalation(self, alert_id: UUID) -> Dict[str, Any]:
        """Process escalation for an alert."""
        alert = self.alert_repo.get(alert_id)
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        if alert.status != AlertStatus.PENDING:
            logger.info(
                f"Alert {alert_id} already acknowledged/resolved, skipping escalation"
            )
            return {"status": "skipped", "reason": "alert_already_handled"}

        escalation_data = alert.data.get("escalation", {}) if alert.data else {}
        current_escalation = escalation_data.get("current_escalation", 0)
        max_escalations = escalation_data.get("max_escalations", 1)

        if current_escalation >= max_escalations:
            logger.info(f"Alert {alert_id} reached maximum escalations")
            return {"status": "max_reached", "escalation_count": current_escalation}

        # Escalate to higher roles
        escalation_rule = self.escalation_rules.get(alert.severity)
        if escalation_rule:
            # Send notifications to escalation roles
            escalation_users = (
                self.db.query(User)
                .filter(User.role.in_(escalation_rule.escalation_roles))
                .filter(User.is_active == True)
                .all()
            )

            # Send escalation notifications
            notification_results = {}
            for channel_name, channel in self.notification_channels.items():
                if channel.enabled:
                    try:
                        if channel.channel_type == "email":
                            notification_results[channel_name] = (
                                self._send_email_notifications(
                                    alert, escalation_users, channel
                                )
                            )
                        elif channel.channel_type == "websocket":
                            notification_results[channel_name] = (
                                self._send_websocket_notifications(alert, channel)
                            )
                    except Exception as e:
                        logger.error(f"Error sending escalation notification: {e}")

            # Update escalation data
            escalation_data["current_escalation"] = current_escalation + 1
            escalation_data["last_escalation_at"] = datetime.utcnow().isoformat()

            if current_escalation + 1 < max_escalations:
                escalation_data["next_escalation_at"] = (
                    datetime.utcnow()
                    + timedelta(minutes=escalation_rule.escalation_delay_minutes)
                ).isoformat()

            alert.data["escalation"] = escalation_data
            self.alert_repo.update(alert)

            logger.info(f"Alert {alert_id} escalated (level {current_escalation + 1})")

            return {
                "status": "escalated",
                "escalation_level": current_escalation + 1,
                "notifications_sent": notification_results,
                "escalated_at": datetime.utcnow().isoformat(),
            }

        return {"status": "no_escalation_rule"}

    async def acknowledge_alert(
        self, alert_id: UUID, user_id: UUID, notes: Optional[str] = None
    ) -> Optional[Alert]:
        """Acknowledge an alert and stop escalation."""
        alert = await self.alert_system.acknowledge_alert(alert_id, user_id)
        if not alert:
            return None

        # Add acknowledgment notes if provided
        if notes:
            if not alert.data:
                alert.data = {}
            alert.data["acknowledgment_notes"] = notes
            alert.data["acknowledged_at"] = datetime.utcnow().isoformat()
            self.alert_repo.update(alert)

        # Cancel any scheduled escalations
        if alert.data and "escalation" in alert.data:
            alert.data["escalation"]["cancelled"] = True
            alert.data["escalation"]["cancelled_at"] = datetime.utcnow().isoformat()
            self.alert_repo.update(alert)

        logger.info(f"Alert {alert_id} acknowledged by user {user_id}")
        return alert

    async def resolve_alert(
        self, alert_id: UUID, user_id: UUID, resolution_notes: Optional[str] = None
    ) -> Optional[Alert]:
        """Resolve an alert."""
        alert = await self.alert_system.resolve_alert(alert_id, user_id)
        if not alert:
            return None

        # Add resolution notes if provided
        if resolution_notes:
            if not alert.data:
                alert.data = {}
            alert.data["resolution_notes"] = resolution_notes
            alert.data["resolved_at"] = datetime.utcnow().isoformat()
            self.alert_repo.update(alert)

        logger.info(f"Alert {alert_id} resolved by user {user_id}")
        return alert

    def get_alert_dashboard_data(self) -> Dict[str, Any]:
        """Get dashboard data for alert management."""
        stats = self.alert_system.get_alert_statistics()

        # Get recent alerts
        recent_alerts = self.alert_repo.get_active_alerts(limit=10)

        # Get escalation statistics
        escalated_alerts = [
            alert
            for alert in recent_alerts
            if alert.data
            and alert.data.get("escalation", {}).get("current_escalation", 0) > 0
        ]

        return {
            "statistics": stats,
            "recent_alerts": [
                {
                    "id": str(alert.id),
                    "patient_id": str(alert.patient_id),
                    "type": alert.alert_type,
                    "severity": alert.severity.value,
                    "status": alert.status.value,
                    "description": alert.description,
                    "created_at": alert.created_at.isoformat(),
                    "escalation_level": alert.data.get("escalation", {}).get(
                        "current_escalation", 0
                    )
                    if alert.data
                    else 0,
                }
                for alert in recent_alerts
            ],
            "escalation_summary": {
                "total_escalated": len(escalated_alerts),
                "avg_escalation_level": sum(
                    alert.data.get("escalation", {}).get("current_escalation", 0)
                    for alert in escalated_alerts
                )
                / len(escalated_alerts)
                if escalated_alerts
                else 0,
            },
            "notification_channels": {
                name: {"enabled": channel.enabled, "type": channel.channel_type}
                for name, channel in self.notification_channels.items()
            },
        }

    def update_notification_channel(
        self, channel_name: str, enabled: bool, config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update notification channel configuration."""
        if channel_name not in self.notification_channels:
            return False

        channel = self.notification_channels[channel_name]
        channel.enabled = enabled

        if config:
            channel.config.update(config)

        logger.info(f"Updated notification channel {channel_name}: enabled={enabled}")
        return True

    def update_escalation_rule(self, severity: AlertSeverity, **kwargs) -> bool:
        """Update escalation rule configuration."""
        if severity not in self.escalation_rules:
            return False

        rule = self.escalation_rules[severity]
        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)

        logger.info(f"Updated escalation rule for {severity.value}")
        return True
