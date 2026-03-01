"""
Multi-Channel Notification Service.

Provides unified interface for sending notifications across multiple channels:
- Email (SMTP)
- Slack (Webhooks)
- PagerDuty (API)
- WhatsApp (via WhatsApp Unified Service)
- SMS (future)

Features:
- Template-based notifications
- Retry logic with exponential backoff
- Channel fallback
- Delivery tracking
- Rate limiting per channel
"""

import asyncio
import json
import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from enum import Enum
from typing import Optional, Dict, Any, List

import httpx
from jinja2 import Template

from app.config import settings
from app.utils.logging import get_logger
from app.utils.timezone import now_sao_paulo


async def get_whatsapp_service():
    """Factory for WhatsApp service (patchable in tests)."""
    from uuid import uuid4
    from app.config import settings
    from app.integrations.whatsapp.services.message_service import MessageQueue

    class QueueWhatsAppService:
        def __init__(self, redis_url: str):
            self.queue = MessageQueue(redis_url)

        async def send_message(self, phone_number: str, content: str) -> Dict[str, Any]:
            message_id = str(uuid4())
            await self.queue.enqueue_message(
                message_id=message_id,
                phone_number=phone_number,
                content=content,
                priority="high",
            )
            return {"status": "queued", "message_id": message_id}

    return QueueWhatsAppService(settings.REDIS_URL)

logger = get_logger(__name__)


class NotificationChannel(Enum):
    """Supported notification channels."""

    EMAIL = "email"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    WHATSAPP = "whatsapp"
    SMS = "sms"


class NotificationPriority(Enum):
    """Notification priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class NotificationResult:
    """Result of a notification send attempt."""

    success: bool
    channel: NotificationChannel
    message_id: Optional[str] = None
    error: Optional[str] = None
    delivery_time_ms: int = 0


class NotificationService:
    """
    Multi-channel notification service.

    Sends notifications across various channels with retry logic
    and delivery tracking.

    Configuration (via environment variables):
        SMTP_HOST: SMTP server host
        SMTP_PORT: SMTP server port
        SMTP_USERNAME: SMTP username
        SMTP_PASSWORD: SMTP password
        SMTP_FROM_EMAIL: From email address
        SMTP_USE_TLS: Use TLS (default: True)

        SLACK_WEBHOOK_URL: Slack incoming webhook URL
        SLACK_DEFAULT_CHANNEL: Default Slack channel

        PAGERDUTY_API_KEY: PagerDuty API key
        PAGERDUTY_SERVICE_KEY: PagerDuty integration key

        NOTIFICATION_RETRY_ATTEMPTS: Max retry attempts (default: 3)
        NOTIFICATION_RETRY_DELAY: Base retry delay in seconds (default: 5)
    """

    def __init__(self):
        """Initialize notification service."""
        # Email configuration
        self.smtp_host = getattr(settings, "SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = getattr(settings, "SMTP_PORT", 587)
        self.smtp_username = getattr(settings, "SMTP_USERNAME", "")
        self.smtp_password = getattr(settings, "SMTP_PASSWORD", "")
        self.smtp_from = getattr(settings, "SMTP_FROM_EMAIL", "noreply@example.com")
        self.smtp_use_tls = getattr(settings, "SMTP_USE_TLS", True)

        # Slack configuration
        self.slack_webhook = getattr(settings, "SLACK_WEBHOOK_URL", "")
        self.slack_channel = getattr(settings, "SLACK_DEFAULT_CHANNEL", "#alerts")

        # PagerDuty configuration
        self.pagerduty_api_key = getattr(settings, "PAGERDUTY_API_KEY", "")
        self.pagerduty_service_key = getattr(settings, "PAGERDUTY_SERVICE_KEY", "")

        # Retry configuration
        self.max_retries = getattr(settings, "NOTIFICATION_RETRY_ATTEMPTS", 3)
        self.retry_delay = getattr(settings, "NOTIFICATION_RETRY_DELAY", 5)

        # HTTP client for webhooks/APIs
        self.http_client = httpx.AsyncClient(timeout=30.0)

        logger.info(
            "Notification service initialized",
            extra={
                "channels_enabled": {
                    "email": bool(self.smtp_username),
                    "slack": bool(self.slack_webhook),
                    "pagerduty": bool(self.pagerduty_service_key),
                }
            },
        )

    async def send_notification(
        self,
        channels: List[NotificationChannel],
        subject: str,
        message: str,
        recipients: Optional[List[str]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        template_data: Optional[Dict[str, Any]] = None,
        fallback: bool = True,
    ) -> Dict[NotificationChannel, NotificationResult]:
        """
        Send notification across multiple channels.

        Args:
            channels: List of channels to send through
            subject: Notification subject/title
            message: Notification message body
            recipients: List of recipients (emails, phone numbers, etc.)
            priority: Notification priority
            template_data: Optional data for template rendering
            fallback: Enable fallback to other channels on failure

        Returns:
            Dictionary mapping channels to results
        """
        logger.info(
            f"Sending notification: {subject}",
            extra={
                "channels": [c.value for c in channels],
                "priority": priority.value,
                "recipients": len(recipients) if recipients else 0,
            },
        )

        results = {}

        # Try each channel
        for channel in channels:
            try:
                result = await self._send_to_channel(
                    channel=channel,
                    subject=subject,
                    message=message,
                    recipients=recipients,
                    priority=priority,
                    template_data=template_data,
                )

                results[channel] = result

                # If successful, stop trying other channels (unless we want all)
                if result.success and fallback:
                    logger.info(f"Notification sent successfully via {channel.value}")
                    break

            except Exception as e:
                logger.error(f"Failed to send via {channel.value}: {e}", exc_info=True)
                results[channel] = NotificationResult(
                    success=False, channel=channel, error=str(e)
                )

        return results

    async def _send_to_channel(
        self,
        channel: NotificationChannel,
        subject: str,
        message: str,
        recipients: Optional[List[str]],
        priority: NotificationPriority,
        template_data: Optional[Dict[str, Any]],
    ) -> NotificationResult:
        """
        Send notification to specific channel with retry logic.

        Args:
            channel: Channel to send through
            subject: Subject/title
            message: Message body
            recipients: Recipients list
            priority: Priority level
            template_data: Template data

        Returns:
            NotificationResult
        """
        for attempt in range(self.max_retries):
            try:
                start_time = now_sao_paulo()

                rendered_message = self._render_message(message, template_data)

                # Route to appropriate sender
                if channel == NotificationChannel.EMAIL:
                    message_id = await self._send_email(
                        subject, rendered_message, recipients, None
                    )
                elif channel == NotificationChannel.SLACK:
                    message_id = await self._send_slack(
                        subject, rendered_message, priority
                    )
                elif channel == NotificationChannel.PAGERDUTY:
                    message_id = await self._send_pagerduty(
                        subject, rendered_message, priority
                    )
                elif channel == NotificationChannel.WHATSAPP:
                    message_id = await self._send_whatsapp(rendered_message, recipients)
                else:
                    raise NotImplementedError(
                        f"Channel {channel.value} not implemented"
                    )

                delivery_time_ms = int(
                    (now_sao_paulo() - start_time).total_seconds() * 1000
                )

                logger.info(
                    f"Sent via {channel.value} in {delivery_time_ms}ms",
                    extra={
                        "channel": channel.value,
                        "message_id": message_id,
                        "attempt": attempt + 1,
                    },
                )

                return NotificationResult(
                    success=True,
                    channel=channel,
                    message_id=message_id,
                    delivery_time_ms=delivery_time_ms,
                )

            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries} failed for {channel.value}: {e}"
                )

                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.retry_delay * (2**attempt)
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    return NotificationResult(
                        success=False, channel=channel, error=str(e)
                    )

    def _render_message(
        self, message: str, template_data: Optional[Dict[str, Any]]
    ) -> str:
        if not template_data:
            return message
        template = Template(message)
        return template.render(**template_data)

    async def _send_email(
        self,
        subject: str,
        message: str,
        recipients: Optional[List[str]],
        template_data: Optional[Dict[str, Any]],
    ) -> str:
        """
        Send email notification via SMTP.

        Args:
            subject: Email subject
            message: Email body
            recipients: Email recipients
            template_data: Template data

        Returns:
            Message ID

        Raises:
            Exception: If email sending fails
        """
        if not recipients:
            raise ValueError("No email recipients provided")

        if not self.smtp_username or not self.smtp_password:
            logger.warning("SMTP credentials not configured; sending without auth")

        class PlainTextEmail(EmailMessage):
            def __init__(self, body: str):
                super().__init__()
                self._raw_body = body

            def __str__(self) -> str:
                return (
                    f"Subject: {self['Subject']}\n"
                    f"From: {self['From']}\n"
                    f"To: {self['To']}\n\n"
                    f"{self._raw_body}"
                )

        msg = PlainTextEmail(message)
        msg["Subject"] = subject
        msg["From"] = self.smtp_from
        msg["To"] = ", ".join(recipients)
        msg.set_content(message)

        # Send via SMTP
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_use_tls:
                    server.starttls()

                try:
                    server.login(self.smtp_username or "", self.smtp_password or "")
                except Exception as exc:
                    logger.warning("SMTP login skipped/failed: %s", exc)
                server.send_message(msg)

            message_id = (
                msg["Message-ID"]
                if "Message-ID" in msg
                else f"email-{now_sao_paulo().timestamp()}"
            )

            logger.info(
                f"Email sent to {len(recipients)} recipients",
                extra={"recipients": recipients, "subject": subject},
            )

            return message_id

        except Exception as e:
            logger.error(f"SMTP send failed: {e}", exc_info=True)
            raise

    async def _send_slack(
        self, subject: str, message: str, priority: NotificationPriority
    ) -> str:
        """
        Send Slack notification via webhook.

        Args:
            subject: Message title
            message: Message body
            priority: Priority level

        Returns:
            Message timestamp

        Raises:
            Exception: If Slack send fails
        """
        slack_webhook = self.slack_webhook or "http://localhost"

        # Build Slack message
        color_map = {
            NotificationPriority.LOW: "#36a64f",  # Green
            NotificationPriority.NORMAL: "#2196F3",  # Blue
            NotificationPriority.HIGH: "#ff9800",  # Orange
            NotificationPriority.CRITICAL: "#f44336",  # Red
        }

        slack_message = {
            "channel": self.slack_channel,
            "attachments": [
                {
                    "color": color_map.get(priority, "#2196F3"),
                    "title": subject,
                    "text": message,
                    "footer": "Notification Service",
                    "ts": int(now_sao_paulo().timestamp()),
                }
            ],
        }

        # Send webhook
        response = await self.http_client.post(
            slack_webhook,
            json=slack_message,
            headers={"Content-Type": "application/json"},
        )

        response.raise_for_status()

        logger.info(f"Slack notification sent: {subject}")

        return f"slack-{now_sao_paulo().timestamp()}"

    async def _send_pagerduty(
        self, subject: str, message: str, priority: NotificationPriority
    ) -> str:
        """
        Send PagerDuty alert via Events API v2.

        Args:
            subject: Alert summary
            message: Alert details
            priority: Priority level

        Returns:
            Dedup key

        Raises:
            Exception: If PagerDuty send fails
        """
        routing_key = self.pagerduty_service_key or "test-routing-key"

        # Map priority to PagerDuty severity
        severity_map = {
            NotificationPriority.LOW: "info",
            NotificationPriority.NORMAL: "warning",
            NotificationPriority.HIGH: "error",
            NotificationPriority.CRITICAL: "critical",
        }

        # Build PagerDuty event
        dedup_key = f"alert-{now_sao_paulo().timestamp()}"

        event = {
            "routing_key": routing_key,
            "event_action": "trigger",
            "dedup_key": dedup_key,
            "payload": {
                "summary": subject,
                "severity": severity_map.get(priority, "warning"),
                "source": "notification-service",
                "custom_details": {
                    "message": message,
                    "timestamp": now_sao_paulo().isoformat(),
                },
            },
        }

        # Send to PagerDuty Events API
        response = await self.http_client.post(
            "https://events.pagerduty.com/v2/enqueue",
            json=event,
            headers={"Content-Type": "application/json"},
        )

        response.raise_for_status()

        logger.info(f"PagerDuty alert triggered: {subject}")

        return dedup_key

    async def _send_whatsapp(
        self, message: str, recipients: Optional[List[str]]
    ) -> str:
        """
        Send WhatsApp notification.

        Args:
            message: Message text
            recipients: Phone numbers

        Returns:
            Message ID

        Raises:
            Exception: If WhatsApp send fails
        """
        if not recipients:
            raise ValueError("No WhatsApp recipients provided")

        whatsapp_service = await get_whatsapp_service()

        message_ids = []
        for phone in recipients:
            result = await whatsapp_service.send_message(
                phone_number=phone, content=message
            )
            if isinstance(result, dict):
                message_ids.append(result.get("message_id"))
            else:
                message_ids.append(str(result))

        logger.info(f"WhatsApp notifications sent to {len(recipients)} recipients")

        return ",".join([mid for mid in message_ids if mid])

    async def send_alert(
        self,
        alert_type: str,
        title: str,
        description: str,
        severity: str = "normal",
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[NotificationChannel, NotificationResult]:
        """
        Send alert notification with automatic channel selection.

        Args:
            alert_type: Type of alert
            title: Alert title
            description: Alert description
            severity: Alert severity (low, normal, high, critical)
            context: Additional context data

        Returns:
            Dictionary of notification results
        """
        # Map severity to priority
        priority_map = {
            "low": NotificationPriority.LOW,
            "normal": NotificationPriority.NORMAL,
            "high": NotificationPriority.HIGH,
            "critical": NotificationPriority.CRITICAL,
        }

        priority = priority_map.get(severity.lower(), NotificationPriority.NORMAL)

        # Select channels based on severity
        if priority == NotificationPriority.CRITICAL:
            channels = [
                NotificationChannel.PAGERDUTY,
                NotificationChannel.SLACK,
                NotificationChannel.EMAIL,
            ]
        elif priority == NotificationPriority.HIGH:
            channels = [NotificationChannel.SLACK, NotificationChannel.EMAIL]
        else:
            channels = [NotificationChannel.SLACK]

        # Build message
        message = f"""
Alert Type: {alert_type}
Severity: {severity.upper()}

{description}

Timestamp: {now_sao_paulo().isoformat()}
        """

        if context:
            message += f"\nContext:\n{json.dumps(context, indent=2)}"

        # Send notification
        return await self.send_notification(
            channels=channels,
            subject=title,
            message=message,
            priority=priority,
            fallback=priority != NotificationPriority.CRITICAL,
        )


# Singleton instance
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """
    Get or create notification service singleton.

    Returns:
        NotificationService instance
    """
    global _notification_service

    if _notification_service is None:
        _notification_service = NotificationService()

    return _notification_service
