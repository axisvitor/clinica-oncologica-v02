"""
Configuration for the unified alert system.

This module provides configuration management for alerts,
including default settings, channel configurations, and thresholds.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from .types import (
    AlertSeverity,
    NotificationChannel,
    EscalationStrategy,
    MonitoringThresholds,
    ChannelConfig,
)


@dataclass
class AlertSystemConfig:
    """
    Main configuration for the alert system.

    Attributes:
        enabled: Whether alert system is enabled
        debounce_minutes: Minutes to wait before sending duplicate alerts
        max_escalation_level: Maximum escalation level before stopping
        notification_timeout: Timeout for notification attempts (seconds)
        batch_notification_delay: Delay before batching notifications (seconds)
        monitoring_thresholds: Infrastructure monitoring thresholds
        channel_configs: Configuration for each notification channel
        default_channels: Default channels to use if not specified
        metadata: Additional configuration metadata
    """

    enabled: bool = True
    debounce_minutes: int = 5
    max_escalation_level: int = 3
    notification_timeout: int = 30
    batch_notification_delay: int = 60

    monitoring_thresholds: MonitoringThresholds = field(
        default_factory=MonitoringThresholds
    )

    channel_configs: Dict[NotificationChannel, ChannelConfig] = field(
        default_factory=dict
    )

    default_channels: List[NotificationChannel] = field(
        default_factory=lambda: [
            NotificationChannel.EMAIL,
            NotificationChannel.DASHBOARD,
        ]
    )

    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_channel_config(
        self, channel: NotificationChannel
    ) -> Optional[ChannelConfig]:
        """
        Get configuration for a specific channel.

        Args:
            channel: Notification channel

        Returns:
            Channel configuration or None if not configured
        """
        return self.channel_configs.get(channel)

    def is_channel_enabled(self, channel: NotificationChannel) -> bool:
        """
        Check if a notification channel is enabled.

        Args:
            channel: Notification channel

        Returns:
            True if channel is configured and enabled
        """
        config = self.get_channel_config(channel)
        return config is not None and config.enabled

    def add_channel_config(self, config: ChannelConfig) -> None:
        """
        Add or update channel configuration.

        Args:
            config: Channel configuration to add
        """
        self.channel_configs[config.channel] = config


@dataclass
class RuleConfig:
    """
    Configuration for alert rules.

    Attributes:
        auto_acknowledge_after: Seconds before auto-acknowledgment
        auto_resolve_after: Seconds before auto-resolution
        auto_escalate_after: Seconds before auto-escalation
        escalation_strategy: Default escalation strategy
        notification_channels: Channels to use for this rule
        metadata: Additional rule configuration
    """

    auto_acknowledge_after: Optional[int] = None
    auto_resolve_after: Optional[int] = None
    auto_escalate_after: Optional[int] = 3600  # 1 hour

    escalation_strategy: EscalationStrategy = EscalationStrategy.DELAYED

    notification_channels: List[NotificationChannel] = field(
        default_factory=lambda: [
            NotificationChannel.EMAIL,
            NotificationChannel.DASHBOARD,
        ]
    )

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmailChannelConfig:
    """Configuration for email notification channel."""

    smtp_host: str
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    use_tls: bool = True
    from_address: str = "noreply@clinica-oncologica.com"
    from_name: str = "Clínica Oncológica - Alertas"

    # Templates
    alert_template: str = "alert_email.html"
    escalation_template: str = "escalation_email.html"

    # Rate limiting
    max_emails_per_minute: int = 10
    max_emails_per_hour: int = 100

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebSocketChannelConfig:
    """Configuration for WebSocket notification channel."""

    enabled: bool = True
    namespace: str = "/alerts"
    room_prefix: str = "alert_"

    # Connection settings
    ping_timeout: int = 60
    ping_interval: int = 25

    # Rate limiting
    max_messages_per_second: int = 10

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookChannelConfig:
    """Configuration for webhook notification channel."""

    enabled: bool = True
    default_url: Optional[str] = None

    # HTTP settings
    timeout: int = 10
    max_retries: int = 3
    retry_delay: int = 5  # seconds

    # Authentication
    auth_type: str = "none"  # none, bearer, basic, hmac
    auth_token: Optional[str] = None
    hmac_secret: Optional[str] = None

    # Headers
    custom_headers: Dict[str, str] = field(default_factory=dict)

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SlackChannelConfig:
    """Configuration for Slack notification channel."""

    enabled: bool = False
    webhook_url: Optional[str] = None
    bot_token: Optional[str] = None

    # Channels
    default_channel: str = "#alerts"
    critical_channel: str = "#alerts-critical"

    # Formatting
    use_markdown: bool = True
    mention_on_critical: bool = True
    mention_users: List[str] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PagerDutyChannelConfig:
    """Configuration for PagerDuty notification channel."""

    enabled: bool = False
    integration_key: Optional[str] = None

    # Routing
    routing_key: Optional[str] = None
    service_id: Optional[str] = None

    # Severity mapping
    severity_mapping: Dict[AlertSeverity, str] = field(
        default_factory=lambda: {
            AlertSeverity.INFO: "info",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.CRITICAL: "error",
            AlertSeverity.FATAL: "critical",
        }
    )

    # Auto-resolve
    auto_resolve_on_resolution: bool = True

    metadata: Dict[str, Any] = field(default_factory=dict)


# Default configuration instance
DEFAULT_CONFIG = AlertSystemConfig(
    enabled=True,
    debounce_minutes=5,
    max_escalation_level=3,
    notification_timeout=30,
    batch_notification_delay=60,
    monitoring_thresholds=MonitoringThresholds(),
    default_channels=[
        NotificationChannel.EMAIL,
        NotificationChannel.DASHBOARD,
    ],
)


# Configuration singleton
_config: Optional[AlertSystemConfig] = None


def get_config() -> AlertSystemConfig:
    """
    Get the global alert system configuration.

    Returns:
        AlertSystemConfig singleton instance
    """
    global _config
    if _config is None:
        _config = DEFAULT_CONFIG
    return _config


def set_config(config: AlertSystemConfig) -> None:
    """
    Set the global alert system configuration.

    Args:
        config: New configuration to use
    """
    global _config
    _config = config


def reset_config() -> None:
    """Reset configuration to default."""
    global _config
    _config = DEFAULT_CONFIG
