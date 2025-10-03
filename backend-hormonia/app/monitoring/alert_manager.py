"""
Alert Management System
Centralized alert handling, notification, and escalation.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict, field
from enum import Enum
import logging
import json
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertStatus(str, Enum):
    """Alert lifecycle status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class NotificationChannel(str, Enum):
    """Notification delivery channels"""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SMS = "sms"
    PAGERDUTY = "pagerduty"


@dataclass
class Alert:
    """Alert definition"""
    alert_id: str
    severity: AlertSeverity
    title: str
    description: str
    source: str
    metric_name: str
    current_value: float
    threshold_value: float
    created_at: datetime
    status: AlertStatus = AlertStatus.ACTIVE
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    notification_sent: bool = False
    escalation_level: int = 0


@dataclass
class AlertRule:
    """Alert rule configuration"""
    rule_id: str
    name: str
    metric_name: str
    condition: str  # e.g., "gt", "lt", "eq"
    threshold: float
    severity: AlertSeverity
    duration_seconds: int = 0  # Alert only if condition persists
    cooldown_seconds: int = 300  # Don't re-alert within this period
    enabled: bool = True
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class NotificationConfig:
    """Notification configuration"""
    channel: NotificationChannel
    enabled: bool = True
    recipients: List[str] = field(default_factory=list)
    severity_filter: List[AlertSeverity] = field(default_factory=list)
    rate_limit_per_hour: int = 10
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EscalationPolicy:
    """Alert escalation policy"""
    policy_id: str
    name: str
    levels: List[Dict[str, Any]]  # [{delay_minutes: 15, notify: [...]}]
    severity_filter: List[AlertSeverity] = field(default_factory=list)


class AlertAggregator:
    """Aggregate and deduplicate alerts"""

    def __init__(self, window_seconds: int = 300):
        self.window_seconds = window_seconds
        self.alert_cache: Dict[str, Alert] = {}
        self.alert_counts: Dict[str, int] = defaultdict(int)

    def fingerprint(self, alert: Alert) -> str:
        """Generate alert fingerprint for deduplication"""
        key = f"{alert.source}:{alert.metric_name}:{alert.threshold_value}"
        return hashlib.md5(key.encode()).hexdigest()

    def should_alert(self, alert: Alert) -> bool:
        """Check if alert should be sent (deduplication)"""
        fp = self.fingerprint(alert)

        if fp in self.alert_cache:
            cached_alert = self.alert_cache[fp]

            # Check if within cooldown window
            time_diff = (alert.created_at - cached_alert.created_at).total_seconds()
            if time_diff < self.window_seconds:
                self.alert_counts[fp] += 1
                return False

        # New alert or outside cooldown window
        self.alert_cache[fp] = alert
        self.alert_counts[fp] = 1
        return True

    def get_alert_count(self, alert: Alert) -> int:
        """Get aggregated alert count"""
        fp = self.fingerprint(alert)
        return self.alert_counts.get(fp, 0)


class NotificationManager:
    """Manage alert notifications"""

    def __init__(self):
        self.configs: Dict[NotificationChannel, NotificationConfig] = {}
        self.notification_history: List[Dict] = []
        self.rate_limiters: Dict[str, List[datetime]] = defaultdict(list)

    def add_config(self, config: NotificationConfig):
        """Add notification configuration"""
        self.configs[config.channel] = config

    async def send_notification(
        self,
        alert: Alert,
        channels: Optional[List[NotificationChannel]] = None
    ) -> Dict[str, bool]:
        """Send alert notification through configured channels"""
        results = {}

        target_channels = channels or list(self.configs.keys())

        for channel in target_channels:
            if channel not in self.configs:
                continue

            config = self.configs[channel]

            # Check if enabled
            if not config.enabled:
                results[channel.value] = False
                continue

            # Check severity filter
            if config.severity_filter and alert.severity not in config.severity_filter:
                results[channel.value] = False
                continue

            # Check rate limit
            if not self._check_rate_limit(channel, config.rate_limit_per_hour):
                logger.warning(f"Rate limit exceeded for {channel.value}")
                results[channel.value] = False
                continue

            # Send notification
            success = await self._send_to_channel(channel, alert, config)
            results[channel.value] = success

            if success:
                self.notification_history.append({
                    'alert_id': alert.alert_id,
                    'channel': channel.value,
                    'timestamp': datetime.utcnow(),
                    'recipients': config.recipients
                })

        return results

    def _check_rate_limit(
        self,
        channel: NotificationChannel,
        limit_per_hour: int
    ) -> bool:
        """Check notification rate limit"""
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)

        # Clean old entries
        key = channel.value
        self.rate_limiters[key] = [
            ts for ts in self.rate_limiters[key] if ts > hour_ago
        ]

        # Check limit
        if len(self.rate_limiters[key]) >= limit_per_hour:
            return False

        self.rate_limiters[key].append(now)
        return True

    async def _send_to_channel(
        self,
        channel: NotificationChannel,
        alert: Alert,
        config: NotificationConfig
    ) -> bool:
        """Send notification to specific channel"""
        try:
            if channel == NotificationChannel.EMAIL:
                return await self._send_email(alert, config)
            elif channel == NotificationChannel.SLACK:
                return await self._send_slack(alert, config)
            elif channel == NotificationChannel.WEBHOOK:
                return await self._send_webhook(alert, config)
            elif channel == NotificationChannel.SMS:
                return await self._send_sms(alert, config)
            elif channel == NotificationChannel.PAGERDUTY:
                return await self._send_pagerduty(alert, config)

            return False

        except Exception as e:
            logger.error(f"Error sending notification via {channel.value}: {e}")
            return False

    async def _send_email(
        self,
        alert: Alert,
        config: NotificationConfig
    ) -> bool:
        """Send email notification"""
        # TODO: Implement email sending
        logger.info(f"Would send email for alert {alert.alert_id}")
        return True

    async def _send_slack(
        self,
        alert: Alert,
        config: NotificationConfig
    ) -> bool:
        """Send Slack notification"""
        # TODO: Implement Slack webhook
        logger.info(f"Would send Slack notification for alert {alert.alert_id}")
        return True

    async def _send_webhook(
        self,
        alert: Alert,
        config: NotificationConfig
    ) -> bool:
        """Send webhook notification"""
        # TODO: Implement webhook
        logger.info(f"Would send webhook for alert {alert.alert_id}")
        return True

    async def _send_sms(
        self,
        alert: Alert,
        config: NotificationConfig
    ) -> bool:
        """Send SMS notification"""
        # TODO: Implement SMS
        logger.info(f"Would send SMS for alert {alert.alert_id}")
        return True

    async def _send_pagerduty(
        self,
        alert: Alert,
        config: NotificationConfig
    ) -> bool:
        """Send PagerDuty notification"""
        # TODO: Implement PagerDuty integration
        logger.info(f"Would send PagerDuty alert {alert.alert_id}")
        return True


class AlertManager:
    """Main alert management system"""

    def __init__(self):
        self.alerts: Dict[str, Alert] = {}
        self.rules: Dict[str, AlertRule] = {}
        self.aggregator = AlertAggregator()
        self.notification_manager = NotificationManager()
        self.escalation_policies: Dict[str, EscalationPolicy] = {}
        self.metric_states: Dict[str, List[Dict]] = defaultdict(list)

    def add_rule(self, rule: AlertRule):
        """Add alert rule"""
        self.rules[rule.rule_id] = rule
        logger.info(f"Added alert rule: {rule.name}")

    def add_escalation_policy(self, policy: EscalationPolicy):
        """Add escalation policy"""
        self.escalation_policies[policy.policy_id] = policy
        logger.info(f"Added escalation policy: {policy.name}")

    async def evaluate_rules(
        self,
        metric_name: str,
        value: float,
        source: str
    ) -> List[Alert]:
        """Evaluate alert rules for a metric"""
        triggered_alerts = []

        # Track metric state for duration-based rules
        self.metric_states[metric_name].append({
            'value': value,
            'timestamp': datetime.utcnow()
        })

        # Limit state history
        if len(self.metric_states[metric_name]) > 100:
            self.metric_states[metric_name] = self.metric_states[metric_name][-100:]

        for rule in self.rules.values():
            if not rule.enabled or rule.metric_name != metric_name:
                continue

            # Evaluate condition
            triggered = False
            if rule.condition == "gt" and value > rule.threshold:
                triggered = True
            elif rule.condition == "lt" and value < rule.threshold:
                triggered = True
            elif rule.condition == "eq" and value == rule.threshold:
                triggered = True
            elif rule.condition == "gte" and value >= rule.threshold:
                triggered = True
            elif rule.condition == "lte" and value <= rule.threshold:
                triggered = True

            if not triggered:
                continue

            # Check duration requirement
            if rule.duration_seconds > 0:
                if not self._check_duration(metric_name, rule):
                    continue

            # Create alert
            alert = Alert(
                alert_id=f"{rule.rule_id}_{int(datetime.utcnow().timestamp())}",
                severity=rule.severity,
                title=f"Alert: {rule.name}",
                description=f"{metric_name} {rule.condition} {rule.threshold} (current: {value})",
                source=source,
                metric_name=metric_name,
                current_value=value,
                threshold_value=rule.threshold,
                created_at=datetime.utcnow(),
                tags=rule.tags
            )

            # Check if should alert (deduplication)
            if self.aggregator.should_alert(alert):
                self.alerts[alert.alert_id] = alert
                triggered_alerts.append(alert)

                # Send notifications
                await self.notification_manager.send_notification(alert)

                # Start escalation if configured
                await self._start_escalation(alert)

                logger.warning(
                    f"Alert triggered: {alert.title} - {alert.description}"
                )

        return triggered_alerts

    def _check_duration(self, metric_name: str, rule: AlertRule) -> bool:
        """Check if condition persists for required duration"""
        states = self.metric_states[metric_name]
        if not states:
            return False

        cutoff_time = datetime.utcnow() - timedelta(seconds=rule.duration_seconds)

        # Check if all recent values within duration meet condition
        recent_states = [
            s for s in states if s['timestamp'] >= cutoff_time
        ]

        if not recent_states:
            return False

        for state in recent_states:
            value = state['value']
            meets_condition = False

            if rule.condition == "gt" and value > rule.threshold:
                meets_condition = True
            elif rule.condition == "lt" and value < rule.threshold:
                meets_condition = True
            elif rule.condition == "eq" and value == rule.threshold:
                meets_condition = True

            if not meets_condition:
                return False

        return True

    async def _start_escalation(self, alert: Alert):
        """Start alert escalation process"""
        # Find applicable escalation policies
        for policy in self.escalation_policies.values():
            if policy.severity_filter and alert.severity not in policy.severity_filter:
                continue

            # Schedule escalation levels
            asyncio.create_task(self._escalate(alert, policy))

    async def _escalate(self, alert: Alert, policy: EscalationPolicy):
        """Execute escalation policy"""
        for level_idx, level in enumerate(policy.levels):
            # Wait for delay
            delay_seconds = level.get('delay_minutes', 0) * 60
            await asyncio.sleep(delay_seconds)

            # Check if alert still active
            if alert.alert_id not in self.alerts:
                break

            current_alert = self.alerts[alert.alert_id]
            if current_alert.status != AlertStatus.ACTIVE:
                break

            # Escalate
            current_alert.escalation_level = level_idx + 1
            notify_channels = level.get('notify', [])

            logger.warning(
                f"Escalating alert {alert.alert_id} to level {level_idx + 1}"
            )

            # Send escalation notifications
            await self.notification_manager.send_notification(
                current_alert,
                [NotificationChannel(ch) for ch in notify_channels]
            )

    async def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str
    ) -> bool:
        """Acknowledge an alert"""
        if alert_id not in self.alerts:
            return False

        alert = self.alerts[alert_id]
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = acknowledged_by

        logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
        return True

    async def resolve_alert(
        self,
        alert_id: str,
        resolved_by: str,
        resolution_note: Optional[str] = None
    ) -> bool:
        """Resolve an alert"""
        if alert_id not in self.alerts:
            return False

        alert = self.alerts[alert_id]
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        alert.resolved_by = resolved_by

        if resolution_note:
            alert.metadata['resolution_note'] = resolution_note

        logger.info(f"Alert {alert_id} resolved by {resolved_by}")
        return True

    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None
    ) -> List[Alert]:
        """Get all active alerts"""
        active = [
            a for a in self.alerts.values()
            if a.status == AlertStatus.ACTIVE
        ]

        if severity:
            active = [a for a in active if a.severity == severity]

        return sorted(active, key=lambda x: x.created_at, reverse=True)

    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert summary statistics"""
        all_alerts = list(self.alerts.values())
        active_alerts = self.get_active_alerts()

        return {
            'total_alerts': len(all_alerts),
            'active_alerts': len(active_alerts),
            'by_severity': {
                'critical': len([a for a in active_alerts if a.severity == AlertSeverity.CRITICAL]),
                'error': len([a for a in active_alerts if a.severity == AlertSeverity.ERROR]),
                'warning': len([a for a in active_alerts if a.severity == AlertSeverity.WARNING]),
                'info': len([a for a in active_alerts if a.severity == AlertSeverity.INFO])
            },
            'by_status': {
                'active': len([a for a in all_alerts if a.status == AlertStatus.ACTIVE]),
                'acknowledged': len([a for a in all_alerts if a.status == AlertStatus.ACKNOWLEDGED]),
                'resolved': len([a for a in all_alerts if a.status == AlertStatus.RESOLVED])
            },
            'escalated_alerts': len([a for a in active_alerts if a.escalation_level > 0])
        }


# Global alert manager instance
alert_manager = AlertManager()