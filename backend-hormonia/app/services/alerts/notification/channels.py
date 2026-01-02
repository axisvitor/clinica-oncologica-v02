"""
Notification channel implementations.

This module provides concrete implementations of notification channels
for the alert system (Email, WebSocket, Webhook, Dashboard, etc.).
"""

import logging
import smtplib
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from uuid import UUID

import aiohttp

from ..types import (
    Alert,
    NotificationTarget,
    NotificationResult,
    NotificationChannel,
)
from ..config import (
    EmailChannelConfig,
    WebSocketChannelConfig,
    WebhookChannelConfig,
)
from .dispatcher import ChannelHandler

logger = logging.getLogger(__name__)


class EmailChannelHandler(ChannelHandler):
    """
    Email notification channel using SMTP.

    Sends alert notifications via email to specified recipients.
    """

    def __init__(self, config: Optional[EmailChannelConfig] = None):
        """
        Initialize email channel handler.

        Args:
            config: Email channel configuration
        """
        super().__init__(config.metadata if config else {})
        self.email_config = config

        if not self.email_config:
            logger.warning("EmailChannelHandler initialized without configuration")

    async def send(
        self,
        alert: Alert,
        target: NotificationTarget,
    ) -> NotificationResult:
        """
        Send alert notification via email.

        Args:
            alert: Alert to send
            target: Target recipient

        Returns:
            NotificationResult with success/failure status
        """
        if not self.email_config:
            return NotificationResult(
                channel=NotificationChannel.EMAIL,
                target=target,
                success=False,
                error="Email configuration not set",
                sent_at=datetime.now(),
            )

        try:
            # Get recipient email from target metadata
            recipient_email = target.metadata.get("email")
            if not recipient_email:
                return NotificationResult(
                    channel=NotificationChannel.EMAIL,
                    target=target,
                    success=False,
                    error="No email address in target metadata",
                    sent_at=datetime.now(),
                )

            # Create email message
            message = self._create_email_message(alert, recipient_email)

            # Send via SMTP
            await self._send_smtp(message, recipient_email)

            logger.info(f"Email sent successfully to {recipient_email}")

            return NotificationResult(
                channel=NotificationChannel.EMAIL,
                target=target,
                success=True,
                sent_at=datetime.now(),
                metadata={
                    "recipient": recipient_email,
                    "subject": message["Subject"],
                },
            )

        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
            return NotificationResult(
                channel=NotificationChannel.EMAIL,
                target=target,
                success=False,
                error=str(e),
                sent_at=datetime.now(),
                metadata={"exception_type": type(e).__name__},
            )

    def _create_email_message(self, alert: Alert, recipient: str) -> MIMEMultipart:
        """Create email message from alert."""
        message = MIMEMultipart("alternative")
        message["Subject"] = f"[{alert.severity.value.upper()}] {alert.title}"
        message["From"] = (
            f"{self.email_config.from_name} <{self.email_config.from_address}>"
        )
        message["To"] = recipient

        # Create plain text version
        text = f"""
Alert Notification
==================

Severity: {alert.severity.value.upper()}
Type: {alert.rule_type.value}
Time: {alert.created_at.strftime("%Y-%m-%d %H:%M:%S")}

{alert.title}

{alert.message}

Alert ID: {alert.id}
"""

        # Create HTML version
        html = f"""
<html>
  <body>
    <h2 style="color: {self._get_severity_color(alert.severity)};">
      Alert Notification
    </h2>
    <p><strong>Severity:</strong> {alert.severity.value.upper()}</p>
    <p><strong>Type:</strong> {alert.rule_type.value}</p>
    <p><strong>Time:</strong> {alert.created_at.strftime("%Y-%m-%d %H:%M:%S")}</p>
    <hr>
    <h3>{alert.title}</h3>
    <p>{alert.message}</p>
    <hr>
    <p style="font-size: 0.9em; color: #666;">
      Alert ID: {alert.id}
    </p>
  </body>
</html>
"""

        # Attach parts
        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        message.attach(part1)
        message.attach(part2)

        return message

    def _get_severity_color(self, severity) -> str:
        """Get HTML color for severity level."""
        colors = {
            "info": "#0066cc",
            "warning": "#ff9900",
            "critical": "#cc0000",
            "fatal": "#990000",
        }
        return colors.get(severity.value, "#333333")

    async def _send_smtp(self, message: MIMEMultipart, recipient: str) -> None:
        """Send email via SMTP."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._send_smtp_sync,
            message,
            recipient,
        )

    def _send_smtp_sync(self, message: MIMEMultipart, recipient: str) -> None:
        """Synchronous SMTP send."""
        if self.email_config.use_tls:
            server = smtplib.SMTP(
                self.email_config.smtp_host,
                self.email_config.smtp_port,
            )
            server.starttls()
        else:
            server = smtplib.SMTP(
                self.email_config.smtp_host,
                self.email_config.smtp_port,
            )

        if self.email_config.smtp_user and self.email_config.smtp_password:
            server.login(
                self.email_config.smtp_user,
                self.email_config.smtp_password,
            )

        server.send_message(message)
        server.quit()


class WebSocketChannelHandler(ChannelHandler):
    """
    WebSocket notification channel.

    Sends real-time notifications to connected WebSocket clients.
    """

    def __init__(self, config: Optional[WebSocketChannelConfig] = None):
        """
        Initialize WebSocket channel handler.

        Args:
            config: WebSocket channel configuration
        """
        super().__init__(config.metadata if config else {})
        self.ws_config = config
        self._socket_manager = None  # Will be injected

    def set_socket_manager(self, manager: Any) -> None:
        """
        Set the Socket.IO manager instance.

        Args:
            manager: Socket.IO server manager
        """
        self._socket_manager = manager

    async def send(
        self,
        alert: Alert,
        target: NotificationTarget,
    ) -> NotificationResult:
        """
        Send alert notification via WebSocket.

        Args:
            alert: Alert to send
            target: Target recipient

        Returns:
            NotificationResult with success/failure status
        """
        if not self._socket_manager:
            return NotificationResult(
                channel=NotificationChannel.WEBSOCKET,
                target=target,
                success=False,
                error="Socket manager not configured",
                sent_at=datetime.now(),
            )

        try:
            # Prepare notification payload
            payload = {
                "type": "alert",
                "alert_id": str(alert.id),
                "severity": alert.severity.value,
                "rule_type": alert.rule_type.value,
                "title": alert.title,
                "message": alert.message,
                "status": alert.status.value,
                "created_at": alert.created_at.isoformat(),
                "metadata": alert.metadata,
            }

            # Determine room (user-specific)
            room = f"user_{target.user_id}"

            # Emit to specific room
            await self._socket_manager.emit(
                "alert_notification",
                payload,
                room=room,
            )

            logger.info(f"WebSocket notification sent to room {room}")

            return NotificationResult(
                channel=NotificationChannel.WEBSOCKET,
                target=target,
                success=True,
                sent_at=datetime.now(),
                metadata={
                    "room": room,
                    "event": "alert_notification",
                },
            )

        except Exception as e:
            logger.error(f"Failed to send WebSocket notification: {e}", exc_info=True)
            return NotificationResult(
                channel=NotificationChannel.WEBSOCKET,
                target=target,
                success=False,
                error=str(e),
                sent_at=datetime.now(),
                metadata={"exception_type": type(e).__name__},
            )


class WebhookChannelHandler(ChannelHandler):
    """
    Webhook notification channel.

    Sends HTTP POST notifications to configured webhook URLs.
    """

    def __init__(self, config: Optional[WebhookChannelConfig] = None):
        """
        Initialize webhook channel handler.

        Args:
            config: Webhook channel configuration
        """
        super().__init__(config.metadata if config else {})
        self.webhook_config = config

    async def send(
        self,
        alert: Alert,
        target: NotificationTarget,
    ) -> NotificationResult:
        """
        Send alert notification via webhook.

        Args:
            alert: Alert to send
            target: Target recipient

        Returns:
            NotificationResult with success/failure status
        """
        if not self.webhook_config:
            return NotificationResult(
                channel=NotificationChannel.WEBHOOK,
                target=target,
                success=False,
                error="Webhook configuration not set",
                sent_at=datetime.now(),
            )

        # Get webhook URL from target or config
        webhook_url = (
            target.metadata.get("webhook_url") or self.webhook_config.default_url
        )

        if not webhook_url:
            return NotificationResult(
                channel=NotificationChannel.WEBHOOK,
                target=target,
                success=False,
                error="No webhook URL configured",
                sent_at=datetime.now(),
            )

        try:
            # Prepare webhook payload
            payload = {
                "alert_id": str(alert.id),
                "rule_id": str(alert.rule_id),
                "rule_type": alert.rule_type.value,
                "severity": alert.severity.value,
                "status": alert.status.value,
                "title": alert.title,
                "message": alert.message,
                "context": alert.context,
                "metadata": alert.metadata,
                "created_at": alert.created_at.isoformat(),
                "target_user_id": str(target.user_id),
            }

            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Clinica-Oncologica-Alert-System/1.0",
            }

            # Add authentication if configured
            if (
                self.webhook_config.auth_type == "bearer"
                and self.webhook_config.auth_token
            ):
                headers["Authorization"] = f"Bearer {self.webhook_config.auth_token}"

            # Add custom headers
            headers.update(self.webhook_config.custom_headers)

            # Send HTTP POST
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.webhook_config.timeout),
                ) as response:
                    response_text = await response.text()

                    if response.status >= 200 and response.status < 300:
                        logger.info(
                            f"Webhook notification sent successfully to {webhook_url}"
                        )
                        return NotificationResult(
                            channel=NotificationChannel.WEBHOOK,
                            target=target,
                            success=True,
                            sent_at=datetime.now(),
                            metadata={
                                "webhook_url": webhook_url,
                                "status_code": response.status,
                                "response": response_text[:500],  # Limit response size
                            },
                        )
                    else:
                        logger.warning(
                            f"Webhook returned non-success status: {response.status}"
                        )
                        return NotificationResult(
                            channel=NotificationChannel.WEBHOOK,
                            target=target,
                            success=False,
                            error=f"HTTP {response.status}: {response_text[:200]}",
                            sent_at=datetime.now(),
                            metadata={
                                "webhook_url": webhook_url,
                                "status_code": response.status,
                            },
                        )

        except asyncio.TimeoutError:
            logger.error(f"Webhook request timed out: {webhook_url}")
            return NotificationResult(
                channel=NotificationChannel.WEBHOOK,
                target=target,
                success=False,
                error="Request timed out",
                sent_at=datetime.now(),
                metadata={"webhook_url": webhook_url},
            )

        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}", exc_info=True)
            return NotificationResult(
                channel=NotificationChannel.WEBHOOK,
                target=target,
                success=False,
                error=str(e),
                sent_at=datetime.now(),
                metadata={
                    "webhook_url": webhook_url,
                    "exception_type": type(e).__name__,
                },
            )


class DashboardChannelHandler(ChannelHandler):
    """
    Dashboard notification channel.

    Stores notifications for display in the dashboard UI.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize dashboard channel handler.

        Args:
            config: Dashboard channel configuration
        """
        super().__init__(config)
        self._dashboard_notifications: Dict[UUID, Dict[str, Any]] = {}

    async def send(
        self,
        alert: Alert,
        target: NotificationTarget,
    ) -> NotificationResult:
        """
        Store alert notification for dashboard display.

        Args:
            alert: Alert to send
            target: Target recipient

        Returns:
            NotificationResult with success/failure status
        """
        try:
            # Store notification in memory (in production, store in database)
            notification = {
                "alert_id": alert.id,
                "user_id": target.user_id,
                "severity": alert.severity.value,
                "title": alert.title,
                "message": alert.message,
                "created_at": alert.created_at,
                "read": False,
            }

            self._dashboard_notifications[alert.id] = notification

            logger.info(f"Dashboard notification stored for user {target.user_id}")

            return NotificationResult(
                channel=NotificationChannel.DASHBOARD,
                target=target,
                success=True,
                sent_at=datetime.now(),
                metadata={
                    "user_id": str(target.user_id),
                    "notification_id": str(alert.id),
                },
            )

        except Exception as e:
            logger.error(f"Failed to store dashboard notification: {e}", exc_info=True)
            return NotificationResult(
                channel=NotificationChannel.DASHBOARD,
                target=target,
                success=False,
                error=str(e),
                sent_at=datetime.now(),
                metadata={"exception_type": type(e).__name__},
            )

    def get_notifications(
        self, user_id: UUID, unread_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get dashboard notifications for a user.

        Args:
            user_id: User UUID
            unread_only: Only return unread notifications

        Returns:
            List of notifications
        """
        notifications = [
            n for n in self._dashboard_notifications.values() if n["user_id"] == user_id
        ]

        if unread_only:
            notifications = [n for n in notifications if not n["read"]]

        return sorted(notifications, key=lambda n: n["created_at"], reverse=True)

    def mark_as_read(self, alert_id: UUID) -> bool:
        """
        Mark notification as read.

        Args:
            alert_id: Alert UUID

        Returns:
            True if marked successfully
        """
        if alert_id in self._dashboard_notifications:
            self._dashboard_notifications[alert_id]["read"] = True
            return True
        return False


class SlackChannelHandler(ChannelHandler):
    """
    Slack notification channel (stub implementation).

    TODO: Implement full Slack integration.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Slack channel handler."""
        super().__init__(config)
        logger.warning("SlackChannelHandler is a stub implementation")

    async def send(
        self,
        alert: Alert,
        target: NotificationTarget,
    ) -> NotificationResult:
        """Send alert notification via Slack (stub)."""
        logger.info("Slack notification (stub) - not implemented")
        return NotificationResult(
            channel=NotificationChannel.SLACK,
            target=target,
            success=False,
            error="Slack integration not yet implemented",
            sent_at=datetime.now(),
        )


class PagerDutyChannelHandler(ChannelHandler):
    """
    PagerDuty notification channel (stub implementation).

    TODO: Implement full PagerDuty integration.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize PagerDuty channel handler."""
        super().__init__(config)
        logger.warning("PagerDutyChannelHandler is a stub implementation")

    async def send(
        self,
        alert: Alert,
        target: NotificationTarget,
    ) -> NotificationResult:
        """Send alert notification via PagerDuty (stub)."""
        logger.info("PagerDuty notification (stub) - not implemented")
        return NotificationResult(
            channel=NotificationChannel.PAGERDUTY,
            target=target,
            success=False,
            error="PagerDuty integration not yet implemented",
            sent_at=datetime.now(),
        )


class SMSChannelHandler(ChannelHandler):
    """
    SMS notification channel (stub implementation).

    TODO: Implement SMS integration (Twilio/etc).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize SMS channel handler."""
        super().__init__(config)
        logger.warning("SMSChannelHandler is a stub implementation")

    async def send(
        self,
        alert: Alert,
        target: NotificationTarget,
    ) -> NotificationResult:
        """Send alert notification via SMS (stub)."""
        logger.info("SMS notification (stub) - not implemented")
        return NotificationResult(
            channel=NotificationChannel.SMS,
            target=target,
            success=False,
            error="SMS integration not yet implemented",
            sent_at=datetime.now(),
        )
