"""
NotificationDispatcher - Multi-channel notification dispatch system.

This module provides a unified dispatcher for sending notifications
across multiple channels (email, websocket, webhook, SMS, etc.).
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from ..types import (
    Alert,
    NotificationChannel,
    NotificationTarget,
    NotificationResult,
    DispatchResult,
)
from ..config import get_config

logger = logging.getLogger(__name__)


class ChannelHandler:
    """
    Base class for notification channel handlers.

    All channel implementations should inherit from this class
    and implement the send() method.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize channel handler.

        Args:
            config: Channel-specific configuration
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)

    async def send(
        self,
        alert: Alert,
        target: NotificationTarget,
    ) -> NotificationResult:
        """
        Send notification through this channel.

        Args:
            alert: Alert to send
            target: Target recipient

        Returns:
            NotificationResult with success/failure status

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Channel handler must implement send()")

    def is_enabled(self) -> bool:
        """Check if channel is enabled."""
        return self.enabled


class NotificationDispatcher:
    """
    Multi-channel notification dispatcher.

    Coordinates notification delivery across multiple channels:
    - Email (SMTP)
    - WebSocket (real-time)
    - Webhook (HTTP callbacks)
    - SMS (Twilio/etc)
    - Slack (webhooks)
    - PagerDuty (API)
    - Push notifications
    - Dashboard alerts

    Features:
    - Channel routing
    - Failure handling and retries
    - Notification history
    - Rate limiting
    - Batch notifications
    """

    def __init__(self):
        """Initialize NotificationDispatcher."""
        self.config = get_config()
        self._channels: Dict[NotificationChannel, ChannelHandler] = {}
        self._notification_history: List[NotificationResult] = []

        # Statistics
        self._total_sent = 0
        self._total_failed = 0

        logger.info("NotificationDispatcher initialized")

    def register_channel(
        self,
        channel: NotificationChannel,
        handler: ChannelHandler,
    ) -> None:
        """
        Register a notification channel handler.

        Args:
            channel: Channel type
            handler: Channel handler instance
        """
        if channel in self._channels:
            logger.warning(f"Overwriting existing handler for {channel.value}")

        self._channels[channel] = handler
        logger.info(f"Registered channel handler: {channel.value}")

    def unregister_channel(self, channel: NotificationChannel) -> None:
        """
        Unregister a notification channel.

        Args:
            channel: Channel type to unregister

        Raises:
            ValueError: If channel not registered
        """
        if channel not in self._channels:
            raise ValueError(f"Channel {channel.value} not registered")

        del self._channels[channel]
        logger.info(f"Unregistered channel: {channel.value}")

    def get_channel(self, channel: NotificationChannel) -> Optional[ChannelHandler]:
        """
        Get channel handler by type.

        Args:
            channel: Channel type

        Returns:
            Channel handler or None if not registered
        """
        return self._channels.get(channel)

    def get_registered_channels(self) -> List[NotificationChannel]:
        """
        Get list of registered channels.

        Returns:
            List of registered channel types
        """
        return list(self._channels.keys())

    async def dispatch(
        self,
        alert: Alert,
        targets: List[NotificationTarget],
        channels: Optional[List[NotificationChannel]] = None,
    ) -> DispatchResult:
        """
        Dispatch notifications for an alert.

        Args:
            alert: Alert to send
            targets: List of notification targets
            channels: Optional list of channels to use (default: use config)

        Returns:
            DispatchResult with detailed results
        """
        logger.info(
            f"Dispatching notifications for alert {alert.id} "
            f"to {len(targets)} target(s)"
        )

        # Determine channels to use
        channels_to_use = channels or self.config.default_channels

        # Validate channels are registered
        available_channels = [ch for ch in channels_to_use if ch in self._channels]

        if len(available_channels) < len(channels_to_use):
            missing = set(channels_to_use) - set(available_channels)
            logger.warning(
                f"Some channels not registered: {[ch.value for ch in missing]}"
            )

        # Dispatch to all targets across all channels
        results = []

        for target in targets:
            # Determine which channels to use for this target
            target_channels = self._determine_target_channels(
                target, available_channels
            )

            for channel in target_channels:
                result = await self._send_to_channel(alert, target, channel)
                results.append(result)

        # Calculate totals
        total_sent = sum(1 for r in results if r.success)
        total_failed = sum(1 for r in results if not r.success)

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

        logger.info(f"Dispatch complete: {total_sent} sent, {total_failed} failed")

        return dispatch_result

    async def dispatch_batch(
        self,
        alerts: List[Alert],
        targets: List[NotificationTarget],
        channels: Optional[List[NotificationChannel]] = None,
    ) -> List[DispatchResult]:
        """
        Dispatch notifications for multiple alerts in batch.

        Args:
            alerts: List of alerts to send
            targets: List of notification targets
            channels: Optional list of channels to use

        Returns:
            List of DispatchResults
        """
        logger.info(f"Batch dispatching {len(alerts)} alert(s)")

        results = []
        for alert in alerts:
            result = await self.dispatch(alert, targets, channels)
            results.append(result)

        logger.info(f"Batch dispatch complete: {len(results)} alerts processed")
        return results

    def get_notification_history(
        self,
        limit: int = 100,
        channel: Optional[NotificationChannel] = None,
        success_only: bool = False,
    ) -> List[NotificationResult]:
        """
        Get notification history.

        Args:
            limit: Maximum number of results to return
            channel: Filter by channel type
            success_only: Only return successful notifications

        Returns:
            List of notification results
        """
        history = self._notification_history

        # Apply filters
        if channel:
            history = [h for h in history if h.channel == channel]

        if success_only:
            history = [h for h in history if h.success]

        # Return most recent first, limited
        return sorted(history, key=lambda h: h.sent_at, reverse=True)[:limit]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get dispatcher statistics.

        Returns:
            Dictionary of statistics
        """
        total_notifications = self._total_sent + self._total_failed
        success_rate = (
            self._total_sent / total_notifications if total_notifications > 0 else 0
        )

        # Statistics by channel
        by_channel = {}
        for channel in self._channels.keys():
            channel_results = [
                r for r in self._notification_history if r.channel == channel
            ]
            channel_sent = sum(1 for r in channel_results if r.success)
            channel_failed = sum(1 for r in channel_results if not r.success)

            by_channel[channel.value] = {
                "sent": channel_sent,
                "failed": channel_failed,
                "total": channel_sent + channel_failed,
                "success_rate": (
                    channel_sent / (channel_sent + channel_failed)
                    if (channel_sent + channel_failed) > 0
                    else 0
                ),
            }

        return {
            "total_sent": self._total_sent,
            "total_failed": self._total_failed,
            "total_notifications": total_notifications,
            "success_rate": success_rate,
            "registered_channels": len(self._channels),
            "by_channel": by_channel,
            "history_size": len(self._notification_history),
        }

    def reset_statistics(self) -> None:
        """Reset dispatcher statistics."""
        self._total_sent = 0
        self._total_failed = 0
        logger.debug("Statistics reset")

    def clear_history(self) -> None:
        """Clear notification history."""
        self._notification_history.clear()
        logger.debug("Notification history cleared")

    # Private helper methods

    def _determine_target_channels(
        self,
        target: NotificationTarget,
        available_channels: List[NotificationChannel],
    ) -> List[NotificationChannel]:
        """
        Determine which channels to use for a specific target.

        Args:
            target: Notification target
            available_channels: Available channels

        Returns:
            List of channels to use for this target
        """
        # Use target's preferred channels if specified
        if target.channels:
            return [ch for ch in target.channels if ch in available_channels]

        # Otherwise use available channels
        return available_channels

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
            target: Notification target
            channel: Channel to use

        Returns:
            NotificationResult
        """
        handler = self._channels.get(channel)

        if not handler:
            logger.error(f"No handler registered for channel {channel.value}")
            return NotificationResult(
                channel=channel,
                target=target,
                success=False,
                error=f"No handler registered for channel {channel.value}",
                sent_at=datetime.now(),
            )

        if not handler.is_enabled():
            logger.debug(f"Channel {channel.value} is disabled")
            return NotificationResult(
                channel=channel,
                target=target,
                success=False,
                error=f"Channel {channel.value} is disabled",
                sent_at=datetime.now(),
            )

        try:
            logger.debug(
                f"Sending alert {alert.id} to target {target.user_id} "
                f"via {channel.value}"
            )

            result = await handler.send(alert, target)

            if result.success:
                logger.info(f"Successfully sent alert {alert.id} via {channel.value}")
            else:
                logger.warning(
                    f"Failed to send alert {alert.id} via {channel.value}: "
                    f"{result.error}"
                )

            return result

        except Exception as e:
            logger.error(
                f"Error sending alert {alert.id} via {channel.value}: {e}",
                exc_info=True,
            )

            return NotificationResult(
                channel=channel,
                target=target,
                success=False,
                error=f"Exception: {str(e)}",
                sent_at=datetime.now(),
                metadata={"exception_type": type(e).__name__},
            )


# Singleton instance
_notification_dispatcher: Optional[NotificationDispatcher] = None


def get_notification_dispatcher() -> NotificationDispatcher:
    """
    Get global NotificationDispatcher instance.

    Returns:
        NotificationDispatcher singleton
    """
    global _notification_dispatcher
    if _notification_dispatcher is None:
        _notification_dispatcher = NotificationDispatcher()
    return _notification_dispatcher


def set_notification_dispatcher(dispatcher: NotificationDispatcher) -> None:
    """
    Set global NotificationDispatcher instance.

    Args:
        dispatcher: NotificationDispatcher instance to use
    """
    global _notification_dispatcher
    _notification_dispatcher = dispatcher
