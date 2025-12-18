"""
Alert Processor - Alert processing pipeline.

This module handles the complete alert processing workflow including
debouncing, notification, and lifecycle management.
"""

import logging
from typing import Dict, Optional, TYPE_CHECKING
from uuid import UUID
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from .notification_dispatcher import NotificationDispatcher

from .types import (
    Alert,
    AlertStatus,
    DispatchResult,
)
from .config import AlertSystemConfig, get_config

logger = logging.getLogger(__name__)


class AlertProcessor:
    """
    Handles alert processing pipeline.

    Responsible for:
    - Debouncing duplicate alerts
    - Processing alerts through the pipeline
    - Managing alert lifecycle
    - Coordinating notification dispatch
    """

    def __init__(
        self,
        processor: Optional["AlertProcessor"] = None,
        dispatcher: Optional["NotificationDispatcher"] = None,
        config: Optional[AlertSystemConfig] = None,
    ):
        """
        Initialize AlertProcessor.

        Args:
            processor: Alert processor (injected for compatibility)
            dispatcher: Notification dispatcher (injected)
            config: Alert system configuration
        """
        self.processor = processor
        self.dispatcher = dispatcher
        self.config = config or get_config()
        self._alert_cache: Dict[UUID, Alert] = {}

    async def process_alert(
        self,
        alert: Alert,
        alert_cache: Dict[UUID, Alert],
        should_escalate_callback,
        schedule_escalation_callback,
        get_notification_targets_callback,
    ) -> DispatchResult:
        """
        Process an alert through the complete pipeline.

        Steps:
        1. Check debouncing
        2. Store alert
        3. Determine notification targets
        4. Dispatch notifications
        5. Schedule escalation (if needed)

        Args:
            alert: Alert to process
            alert_cache: Shared alert cache
            should_escalate_callback: Callback to check if escalation needed
            schedule_escalation_callback: Callback to schedule escalation
            get_notification_targets_callback: Callback to get targets

        Returns:
            Notification dispatch result

        Raises:
            RuntimeError: If required components not configured
        """
        if not self.processor:
            # Use self if no external processor configured
            self.processor = self

        if not self.dispatcher:
            raise RuntimeError("NotificationDispatcher not configured")

        logger.info(f"Processing alert {alert.id}: {alert.title}")

        # Check debouncing
        if await self._should_debounce(alert, alert_cache):
            logger.info(f"Alert {alert.id} debounced (duplicate within threshold)")
            return DispatchResult(
                alert_id=alert.id,
                total_sent=0,
                total_failed=0,
                results=[],
                dispatched_at=datetime.now(),
            )

        # Process through processor
        if self.processor != self:
            processed_alert = await self.processor.process(alert)
        else:
            # Simple processing: just mark as active
            alert.status = AlertStatus.ACTIVE
            processed_alert = alert

        # Get notification targets
        targets = await get_notification_targets_callback(processed_alert)

        # Dispatch notifications
        dispatch_result = await self.dispatcher.dispatch(
            alert=processed_alert,
            targets=targets,
            channels=processed_alert.notification_channels,
        )

        # Update alert
        processed_alert.notification_sent = True
        alert_cache[processed_alert.id] = processed_alert

        # Schedule escalation if needed
        if should_escalate_callback(processed_alert):
            await schedule_escalation_callback(processed_alert)

        logger.info(
            f"Alert {alert.id} processed: "
            f"{dispatch_result.total_sent} sent, "
            f"{dispatch_result.total_failed} failed"
        )

        return dispatch_result

    async def _should_debounce(
        self, alert: Alert, alert_cache: Dict[UUID, Alert]
    ) -> bool:
        """Check if alert should be debounced."""
        debounce_window = timedelta(minutes=self.config.debounce_minutes)
        cutoff_time = datetime.now() - debounce_window

        # Check for similar alerts within debounce window
        for existing_alert in alert_cache.values():
            if (
                existing_alert.rule_type == alert.rule_type
                and existing_alert.severity == alert.severity
                and existing_alert.created_at > cutoff_time
                and existing_alert.id != alert.id
            ):
                return True

        return False

    async def process(self, alert: Alert) -> Alert:
        """
        Simple alert processing.

        Args:
            alert: Alert to process

        Returns:
            Processed alert
        """
        alert.status = AlertStatus.ACTIVE
        return alert

    def get_alert_cache(self) -> Dict[UUID, Alert]:
        """Get the internal alert cache."""
        return self._alert_cache

    def set_alert_cache(self, cache: Dict[UUID, Alert]) -> None:
        """Set the internal alert cache."""
        self._alert_cache = cache
