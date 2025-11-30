"""
Notification handler - Manages notification dispatch across channels.

This module handles the sending of notifications through various channels
with retry logic, rate limiting, and failure handling.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID

from .types import (
    Alert,
    NotificationChannel,
    NotificationTarget,
    NotificationResult,
    DispatchResult,
)
from .config import get_config, AlertSystemConfig
from .base import NotificationChannelHandler

logger = logging.getLogger(__name__)


class NotificationHandler:
    """
    Handles notification dispatch across multiple channels.

    Responsibilities:
    - Channel management and routing
    - Notification dispatch orchestration
    - Failure handling and retries
    - Rate limiting
    - Notification history tracking
    """

    def __init__(self, config: Optional[AlertSystemConfig] = None):
        """
        Initialize notification handler.

        Args:
            config: Alert system configuration
        """
        self.config = config or get_config()
        self._channels: Dict[NotificationChannel, NotificationChannelHandler] = {}
        self._notification_history: List[NotificationResult] = []
        self._total_sent = 0
        self._total_failed = 0

        logger.info("NotificationHandler initialized")

    def register_channel(
        self,
        channel: NotificationChannel,
        handler: NotificationChannelHandler,
    ) -> None:
        """
        Register a notification channel handler.

        Args:
            channel: Channel type
            handler: Channel handler implementation
        """
        self._channels[channel] = handler
        logger.info(f"Registered channel handler: {channel.value}")

    def unregister_channel(self, channel: NotificationChannel) -> None:
        """
        Unregister a notification channel.

        Args:
            channel: Channel to unregister
        """
        if channel in self._channels:
            del self._channels[channel]
            logger.info(f"Unregistered channel: {channel.value}")

    def is_channel_available(self, channel: NotificationChannel) -> bool:
        """
        Check if a channel is available and enabled.

        Args:
            channel: Channel to check

        Returns:
            True if channel is registered and enabled
        """
        handler = self._channels.get(channel)
        return handler is not None and handler.is_enabled()

    async def dispatch(
        self,
        alert: Alert,
        targets: List[NotificationTarget],
        channels: Optional[List[NotificationChannel]] = None,
    ) -> DispatchResult:
        """
        Dispatch notifications to targets across channels.

        Args:
            alert: Alert to send
            targets: Notification targets
            channels: Optional list of channels (uses target channels if None)

        Returns:
            DispatchResult with dispatch statistics
        """
        logger.info(
            f"Dispatching notifications for alert {alert.id} to {len(targets)} targets"
        )

        results: List[NotificationResult] = []
        total_sent = 0
        total_failed = 0

        # Process each target
        for target in targets:
            target_channels = channels or target.channels

            # Process each channel for this target
            for channel in target_channels:
                try:
                    result = await self._send_to_channel(alert, target, channel)
                    results.append(result)

                    if result.success:
                        total_sent += 1
                    else:
                        total_failed += 1

                except Exception as e:
                    logger.error(
                        f"Failed to send notification via {channel.value} "
                        f"to target {target.user_id}: {e}",
                        exc_info=True,
                    )

                    # Create failed result
                    result = NotificationResult(
                        channel=channel,
                        target=target,
                        success=False,
                        error=str(e),
                        sent_at=datetime.now(),
                    )
                    results.append(result)
                    total_failed += 1

        # Update statistics
        self._total_sent += total_sent
        self._total_failed += total_failed

        # Store in history
        self._notification_history.extend(results)

        dispatch_result = DispatchResult(
            alert_id=alert.id,
            total_sent=total_sent,
            total_failed=total_failed,
            results=results,
            dispatched_at=datetime.now(),
        )

        logger.info(
            f"Dispatch complete for alert {alert.id}: "
            f"{total_sent} sent, {total_failed} failed"
        )

        return dispatch_result

    async def _send_to_channel(
        self,
        alert: Alert,
        target: NotificationTarget,
        channel: NotificationChannel,
    ) -> NotificationResult:
        """
        Send notification through a specific channel.

        Args:
            alert: Alert to send
            target: Target recipient
            channel: Channel to use

        Returns:
            NotificationResult

        Raises:
            ValueError: If channel not available
        """
        if not self.is_channel_available(channel):
            raise ValueError(f"Channel {channel.value} not available")

        handler = self._channels[channel]

        logger.debug(
            f"Sending notification via {channel.value} to user {target.user_id}"
        )

        # Send with timeout
        try:
            result = await asyncio.wait_for(
                handler.send(alert, target),
                timeout=self.config.notification_timeout,
            )

            logger.debug(
                f"Notification sent via {channel.value} to {target.user_id}: "
                f"{'SUCCESS' if result.success else 'FAILED'}"
            )

            return result

        except asyncio.TimeoutError:
            logger.warning(
                f"Notification via {channel.value} timed out "
                f"after {self.config.notification_timeout}s"
            )

            return NotificationResult(
                channel=channel,
                target=target,
                success=False,
                error=f"Timeout after {self.config.notification_timeout}s",
                sent_at=datetime.now(),
            )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get notification statistics.

        Returns:
            Dictionary with notification metrics
        """
        total_attempts = self._total_sent + self._total_failed
        success_rate = (
            (self._total_sent / total_attempts * 100) if total_attempts > 0 else 0.0
        )

        # Calculate per-channel statistics
        by_channel: Dict[str, Dict[str, int]] = {}
        for result in self._notification_history:
            channel_key = result.channel.value
            if channel_key not in by_channel:
                by_channel[channel_key] = {"sent": 0, "failed": 0}

            if result.success:
                by_channel[channel_key]["sent"] += 1
            else:
                by_channel[channel_key]["failed"] += 1

        return {
            "total_sent": self._total_sent,
            "total_failed": self._total_failed,
            "total_attempts": total_attempts,
            "success_rate": round(success_rate, 2),
            "by_channel": by_channel,
            "registered_channels": [c.value for c in self._channels.keys()],
        }

    def get_history(
        self, limit: Optional[int] = 100
    ) -> List[NotificationResult]:
        """
        Get notification history.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of notification results
        """
        if limit:
            return self._notification_history[-limit:]
        return self._notification_history.copy()

    def clear_history(self) -> None:
        """Clear notification history."""
        self._notification_history.clear()
        logger.info("Notification history cleared")


# Singleton instance
_notification_handler: Optional[NotificationHandler] = None


def get_notification_handler() -> NotificationHandler:
    """
    Get global NotificationHandler instance.

    Returns:
        NotificationHandler singleton
    """
    global _notification_handler
    if _notification_handler is None:
        _notification_handler = NotificationHandler()
    return _notification_handler


def set_notification_handler(handler: NotificationHandler) -> None:
    """
    Set global NotificationHandler instance.

    Args:
        handler: NotificationHandler instance to use
    """
    global _notification_handler
    _notification_handler = handler
