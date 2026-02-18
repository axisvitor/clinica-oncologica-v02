"""
Threshold manager - Manages alert thresholds and debouncing.

This module handles threshold checking, debouncing logic,
and rate limiting for alerts.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from .types import Alert, AlertRuleType, AlertSeverity
from .config import get_config, AlertSystemConfig
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class ThresholdManager:
    """
    Manages alert thresholds and debouncing.

    Responsibilities:
    - Debounce duplicate alerts
    - Track alert frequencies
    - Threshold checking
    - Rate limiting
    - Alert suppression rules
    """

    def __init__(self, config: Optional[AlertSystemConfig] = None):
        """
        Initialize threshold manager.

        Args:
            config: Alert system configuration
        """
        self.config = config or get_config()

        # Track recent alerts for debouncing
        self._recent_alerts: Dict[str, datetime] = {}

        # Track alert frequencies
        self._alert_counts: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        logger.info("ThresholdManager initialized")

    async def should_debounce(self, alert: Alert) -> bool:
        """
        Check if alert should be debounced.

        Debouncing prevents duplicate alerts within a time window.

        Args:
            alert: Alert to check

        Returns:
            True if alert should be debounced (suppressed)
        """
        debounce_window = timedelta(minutes=self.config.debounce_minutes)
        cutoff_time = now_sao_paulo() - debounce_window

        # Create unique key for this alert type
        debounce_key = self._get_debounce_key(alert)

        # Check if we've seen this alert recently
        if debounce_key in self._recent_alerts:
            last_seen = self._recent_alerts[debounce_key]

            if last_seen > cutoff_time:
                logger.debug(
                    f"Alert debounced (key: {debounce_key}, "
                    f"last seen: {last_seen}, window: {self.config.debounce_minutes}m)"
                )
                return True

        # Update last seen time
        self._recent_alerts[debounce_key] = now_sao_paulo()

        # Clean up old entries
        self._cleanup_recent_alerts(cutoff_time)

        return False

    async def check_threshold(
        self, alert: Alert, threshold_type: str, value: Any
    ) -> bool:
        """
        Check if a threshold is exceeded.

        Args:
            alert: Alert context
            threshold_type: Type of threshold to check
            value: Value to check against threshold

        Returns:
            True if threshold is exceeded
        """
        thresholds = self.config.monitoring_thresholds

        # Map threshold types to configured values
        threshold_map = {
            "pool_utilization_warning": thresholds.pool_utilization_warning,
            "pool_utilization_critical": thresholds.pool_utilization_critical,
            "slow_query_duration": thresholds.slow_query_duration,
            "connection_errors_per_minute": thresholds.connection_errors_per_minute,
            "query_timeout_rate": thresholds.query_timeout_rate,
            "connection_test_failure_count": thresholds.connection_test_failure_count,
        }

        threshold_value = threshold_map.get(threshold_type)

        if threshold_value is None:
            logger.warning(f"Unknown threshold type: {threshold_type}")
            return False

        # Check if value exceeds threshold
        exceeded = value >= threshold_value

        if exceeded:
            logger.debug(
                f"Threshold exceeded: {threshold_type} "
                f"(value: {value}, threshold: {threshold_value})"
            )

        return exceeded

    def increment_alert_count(
        self,
        rule_type: AlertRuleType,
        severity: AlertSeverity,
        window: str = "hour",
    ) -> int:
        """
        Increment alert count for tracking.

        Args:
            rule_type: Type of alert rule
            severity: Alert severity
            window: Time window ('hour', 'day', 'week')

        Returns:
            Current count for this alert type
        """
        count_key = f"{rule_type.value}:{severity.value}:{window}"
        self._alert_counts[window][count_key] += 1

        return self._alert_counts[window][count_key]

    def get_alert_frequency(
        self,
        rule_type: AlertRuleType,
        severity: AlertSeverity,
        window: str = "hour",
    ) -> int:
        """
        Get alert frequency for a specific type.

        Args:
            rule_type: Type of alert rule
            severity: Alert severity
            window: Time window ('hour', 'day', 'week')

        Returns:
            Number of alerts in the time window
        """
        count_key = f"{rule_type.value}:{severity.value}:{window}"
        return self._alert_counts[window].get(count_key, 0)

    def reset_counts(self, window: Optional[str] = None) -> None:
        """
        Reset alert counts.

        Args:
            window: Optional specific window to reset (resets all if None)
        """
        if window:
            if window in self._alert_counts:
                self._alert_counts[window].clear()
                logger.info(f"Reset alert counts for window: {window}")
        else:
            self._alert_counts.clear()
            logger.info("Reset all alert counts")

    def _get_debounce_key(self, alert: Alert) -> str:
        """
        Generate unique debounce key for an alert.

        Args:
            alert: Alert to generate key for

        Returns:
            Debounce key string
        """
        # Create key from rule type, severity, and relevant context
        key_parts = [
            alert.rule_type.value,
            alert.severity.value,
        ]

        # Add patient ID if present
        if "patient_id" in alert.context:
            key_parts.append(str(alert.context["patient_id"]))

        # Add resource ID for infrastructure alerts
        if "resource_id" in alert.context:
            key_parts.append(str(alert.context["resource_id"]))

        return ":".join(key_parts)

    def _cleanup_recent_alerts(self, cutoff_time: datetime) -> None:
        """
        Remove old entries from recent alerts tracking.

        Args:
            cutoff_time: Remove entries older than this time
        """
        keys_to_remove = [
            key
            for key, timestamp in self._recent_alerts.items()
            if timestamp < cutoff_time
        ]

        for key in keys_to_remove:
            del self._recent_alerts[key]

        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} old debounce entries")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get threshold manager statistics.

        Returns:
            Dictionary with threshold metrics
        """
        return {
            "recent_alerts_tracked": len(self._recent_alerts),
            "debounce_window_minutes": self.config.debounce_minutes,
            "alert_counts": dict(self._alert_counts),
        }


# Singleton instance
_threshold_manager: Optional[ThresholdManager] = None


def get_threshold_manager() -> ThresholdManager:
    """
    Get global ThresholdManager instance.

    Returns:
        ThresholdManager singleton
    """
    global _threshold_manager
    if _threshold_manager is None:
        _threshold_manager = ThresholdManager()
    return _threshold_manager


def set_threshold_manager(manager: ThresholdManager) -> None:
    """
    Set global ThresholdManager instance.

    Args:
        manager: ThresholdManager instance to use
    """
    global _threshold_manager
    _threshold_manager = manager
