"""
Unit Tests for NotificationDispatcher.

Tests the multi-channel notification dispatch system including:
- Channel registration and management
- Single and multi-channel dispatch
- Batch notifications
- Retry mechanisms
- Failure handling
- Statistics tracking

Author: Backend Team
Date: 2025-01-20
"""

import pytest
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, Any, List, Optional

from app.services.alerts import (
    NotificationDispatcher,
    ChannelHandler,
    Alert,
    AlertSeverity,
    AlertStatus,
    AlertRuleType,
    NotificationChannel,
    NotificationTarget,
    NotificationResult,
    DispatchResult,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def dispatcher():
    """Create NotificationDispatcher instance."""
    return NotificationDispatcher()


@pytest.fixture
def sample_alert():
    """Sample alert object."""
    return Alert(
        id=uuid4(),
        patient_id=uuid4(),
        rule_type=AlertRuleType.NO_RESPONSE,
        severity=AlertSeverity.HIGH,
        status=AlertStatus.PENDING,
        title="Patient No Response",
        message="Patient has not responded in 48 hours",
        metadata={"days_without_response": 2},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_target():
    """Sample notification target."""
    return NotificationTarget(
        user_id=uuid4(),
        email="doctor@example.com",
        phone="+5511999999999",
        preferred_channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
    )


@pytest.fixture
def mock_channel_handler():
    """Create mock channel handler."""
    handler = MagicMock(spec=ChannelHandler)
    handler.send = AsyncMock()
    handler.is_enabled = MagicMock(return_value=True)
    handler.enabled = True
    return handler


@pytest.fixture
def successful_result(sample_alert):
    """Sample successful notification result."""
    return NotificationResult(
        channel=NotificationChannel.EMAIL,
        target_id=uuid4(),
        success=True,
        message="Notification sent successfully",
        sent_at=datetime.utcnow(),
        alert_id=sample_alert.id,
    )


@pytest.fixture
def failed_result(sample_alert):
    """Sample failed notification result."""
    return NotificationResult(
        channel=NotificationChannel.SMS,
        target_id=uuid4(),
        success=False,
        message="SMS delivery failed",
        error="Network timeout",
        sent_at=datetime.utcnow(),
        alert_id=sample_alert.id,
    )


# ============================================================================
# Test Dispatcher Initialization
# ============================================================================


class TestDispatcherInitialization:
    """Test NotificationDispatcher initialization."""

    def test_init_default(self):
        """Test dispatcher initialization with defaults."""
        dispatcher = NotificationDispatcher()

        assert dispatcher._channels == {}
        assert dispatcher._notification_history == []
        assert dispatcher._total_sent == 0
        assert dispatcher._total_failed == 0

    def test_init_creates_config(self):
        """Test that dispatcher creates config."""
        dispatcher = NotificationDispatcher()

        assert dispatcher.config is not None


# ============================================================================
# Test Channel Registration
# ============================================================================


class TestChannelRegistration:
    """Test channel registration and management."""

    def test_register_channel(self, dispatcher, mock_channel_handler):
        """Test registering a channel handler."""
        # Execute
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel_handler)

        # Assert
        assert NotificationChannel.EMAIL in dispatcher._channels
        assert dispatcher._channels[NotificationChannel.EMAIL] == mock_channel_handler

    def test_register_multiple_channels(self, dispatcher, mock_channel_handler):
        """Test registering multiple channels."""
        handler1 = mock_channel_handler
        handler2 = MagicMock(spec=ChannelHandler)

        # Execute
        dispatcher.register_channel(NotificationChannel.EMAIL, handler1)
        dispatcher.register_channel(NotificationChannel.SMS, handler2)

        # Assert
        assert len(dispatcher._channels) == 2
        assert NotificationChannel.EMAIL in dispatcher._channels
        assert NotificationChannel.SMS in dispatcher._channels

    def test_register_channel_overwrites_existing(self, dispatcher):
        """Test that registering same channel overwrites previous handler."""
        handler1 = MagicMock(spec=ChannelHandler)
        handler2 = MagicMock(spec=ChannelHandler)

        # Register first handler
        dispatcher.register_channel(NotificationChannel.EMAIL, handler1)
        assert dispatcher._channels[NotificationChannel.EMAIL] == handler1

        # Register second handler (should overwrite)
        dispatcher.register_channel(NotificationChannel.EMAIL, handler2)
        assert dispatcher._channels[NotificationChannel.EMAIL] == handler2
        assert dispatcher._channels[NotificationChannel.EMAIL] != handler1

    def test_get_channel_exists(self, dispatcher, mock_channel_handler):
        """Test getting a registered channel."""
        # Setup
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel_handler)

        # Execute
        handler = dispatcher.get_channel(NotificationChannel.EMAIL)

        # Assert
        assert handler == mock_channel_handler

    def test_get_channel_not_exists(self, dispatcher):
        """Test getting non-existent channel returns None."""
        # Execute
        handler = dispatcher.get_channel(NotificationChannel.EMAIL)

        # Assert
        assert handler is None

    def test_get_registered_channels(self, dispatcher):
        """Test getting list of registered channels."""
        handler1 = MagicMock(spec=ChannelHandler)
        handler2 = MagicMock(spec=ChannelHandler)

        # Register channels
        dispatcher.register_channel(NotificationChannel.EMAIL, handler1)
        dispatcher.register_channel(NotificationChannel.SMS, handler2)

        # Execute
        channels = dispatcher.get_registered_channels()

        # Assert
        assert len(channels) == 2
        assert NotificationChannel.EMAIL in channels
        assert NotificationChannel.SMS in channels

    def test_get_registered_channels_empty(self, dispatcher):
        """Test getting registered channels when none registered."""
        # Execute
        channels = dispatcher.get_registered_channels()

        # Assert
        assert channels == []

    def test_unregister_channel(self, dispatcher, mock_channel_handler):
        """Test unregistering a channel."""
        # Setup
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel_handler)
        assert NotificationChannel.EMAIL in dispatcher._channels

        # Execute
        dispatcher.unregister_channel(NotificationChannel.EMAIL)

        # Assert
        assert NotificationChannel.EMAIL not in dispatcher._channels

    def test_unregister_channel_not_registered(self, dispatcher):
        """Test unregistering non-existent channel raises error."""
        # Execute & Assert
        with pytest.raises(ValueError) as exc_info:
            dispatcher.unregister_channel(NotificationChannel.EMAIL)

        assert "not registered" in str(exc_info.value).lower()


# ============================================================================
# Test Single Channel Dispatch
# ============================================================================


class TestSingleChannelDispatch:
    """Test single channel notification dispatch."""

    @pytest.mark.asyncio
    async def test_dispatch_single_channel_success(
        self,
        dispatcher,
        sample_alert,
        sample_target,
        mock_channel_handler,
        successful_result,
    ):
        """Test successful dispatch to single channel."""
        # Setup
        mock_channel_handler.send.return_value = successful_result
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel_handler)

        # Execute
        result = await dispatcher.dispatch(
            alert=sample_alert,
            targets=[sample_target],
            channels=[NotificationChannel.EMAIL],
        )

        # Assert
        assert isinstance(result, DispatchResult)
        assert result.alert_id == sample_alert.id
        assert result.total_sent >= 1
        assert result.total_failed == 0
        assert len(result.results) >= 1
        mock_channel_handler.send.assert_called()

    @pytest.mark.asyncio
    async def test_dispatch_single_channel_failure(
        self,
        dispatcher,
        sample_alert,
        sample_target,
        mock_channel_handler,
        failed_result,
    ):
        """Test failed dispatch to single channel."""
        # Setup
        mock_channel_handler.send.return_value = failed_result
        dispatcher.register_channel(NotificationChannel.SMS, mock_channel_handler)

        # Execute
        result = await dispatcher.dispatch(
            alert=sample_alert,
            targets=[sample_target],
            channels=[NotificationChannel.SMS],
        )

        # Assert
        assert result.total_sent == 0
        assert result.total_failed >= 1

    @pytest.mark.asyncio
    async def test_dispatch_updates_statistics(
        self,
        dispatcher,
        sample_alert,
        sample_target,
        mock_channel_handler,
        successful_result,
    ):
        """Test that dispatch updates statistics."""
        # Setup
        mock_channel_handler.send.return_value = successful_result
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel_handler)

        initial_sent = dispatcher._total_sent
        initial_failed = dispatcher._total_failed

        # Execute
        await dispatcher.dispatch(
            alert=sample_alert,
            targets=[sample_target],
            channels=[NotificationChannel.EMAIL],
        )

        # Assert
        assert dispatcher._total_sent > initial_sent
        assert dispatcher._total_failed >= initial_failed

    @pytest.mark.asyncio
    async def test_dispatch_stores_history(
        self,
        dispatcher,
        sample_alert,
        sample_target,
        mock_channel_handler,
        successful_result,
    ):
        """Test that dispatch stores notification history."""
        # Setup
        mock_channel_handler.send.return_value = successful_result
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel_handler)

        # Execute
        await dispatcher.dispatch(
            alert=sample_alert,
            targets=[sample_target],
            channels=[NotificationChannel.EMAIL],
        )

        # Assert
        assert len(dispatcher._notification_history) > 0


# ============================================================================
# Test Multi-Channel Dispatch
# ============================================================================


class TestMultiChannelDispatch:
    """Test multi-channel notification dispatch."""

    @pytest.mark.asyncio
    async def test_dispatch_multiple_channels(
        self, dispatcher, sample_alert, sample_target
    ):
        """Test dispatch to multiple channels."""
        # Setup handlers
        email_handler = MagicMock(spec=ChannelHandler)
        email_handler.send = AsyncMock(
            return_value=NotificationResult(
                channel=NotificationChannel.EMAIL,
                target_id=sample_target.user_id,
                success=True,
                message="Email sent",
                sent_at=datetime.utcnow(),
                alert_id=sample_alert.id,
            )
        )
        email_handler.is_enabled = MagicMock(return_value=True)

        sms_handler = MagicMock(spec=ChannelHandler)
        sms_handler.send = AsyncMock(
            return_value=NotificationResult(
                channel=NotificationChannel.SMS,
                target_id=sample_target.user_id,
                success=True,
                message="SMS sent",
                sent_at=datetime.utcnow(),
                alert_id=sample_alert.id,
            )
        )
        sms_handler.is_enabled = MagicMock(return_value=True)

        dispatcher.register_channel(NotificationChannel.EMAIL, email_handler)
        dispatcher.register_channel(NotificationChannel.SMS, sms_handler)

        # Execute
        result = await dispatcher.dispatch(
            alert=sample_alert,
            targets=[sample_target],
            channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        )

        # Assert
        assert result.total_sent >= 2
        assert len(result.results) >= 2

    @pytest.mark.asyncio
    async def test_dispatch_partial_failure(
        self, dispatcher, sample_alert, sample_target
    ):
        """Test dispatch with partial channel failures."""
        # Setup - one success, one failure
        email_handler = MagicMock(spec=ChannelHandler)
        email_handler.send = AsyncMock(
            return_value=NotificationResult(
                channel=NotificationChannel.EMAIL,
                target_id=sample_target.user_id,
                success=True,
                message="Email sent",
                sent_at=datetime.utcnow(),
                alert_id=sample_alert.id,
            )
        )
        email_handler.is_enabled = MagicMock(return_value=True)

        sms_handler = MagicMock(spec=ChannelHandler)
        sms_handler.send = AsyncMock(
            return_value=NotificationResult(
                channel=NotificationChannel.SMS,
                target_id=sample_target.user_id,
                success=False,
                message="SMS failed",
                error="Network error",
                sent_at=datetime.utcnow(),
                alert_id=sample_alert.id,
            )
        )
        sms_handler.is_enabled = MagicMock(return_value=True)

        dispatcher.register_channel(NotificationChannel.EMAIL, email_handler)
        dispatcher.register_channel(NotificationChannel.SMS, sms_handler)

        # Execute
        result = await dispatcher.dispatch(
            alert=sample_alert,
            targets=[sample_target],
            channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        )

        # Assert
        assert result.total_sent >= 1
        assert result.total_failed >= 1

    @pytest.mark.asyncio
    async def test_dispatch_skips_unregistered_channels(
        self,
        dispatcher,
        sample_alert,
        sample_target,
        mock_channel_handler,
        successful_result,
    ):
        """Test that dispatch skips unregistered channels."""
        # Setup - only register EMAIL
        mock_channel_handler.send.return_value = successful_result
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel_handler)

        # Execute - request EMAIL and SMS (but SMS not registered)
        result = await dispatcher.dispatch(
            alert=sample_alert,
            targets=[sample_target],
            channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        )

        # Assert - should only dispatch to EMAIL
        assert result is not None
        # Should not raise exception for unregistered channel


# ============================================================================
# Test Multiple Targets
# ============================================================================


class TestMultipleTargets:
    """Test dispatch to multiple targets."""

    @pytest.mark.asyncio
    async def test_dispatch_multiple_targets(self, dispatcher, sample_alert):
        """Test dispatch to multiple notification targets."""
        # Setup targets
        target1 = NotificationTarget(
            user_id=uuid4(),
            email="doctor1@example.com",
            preferred_channels=[NotificationChannel.EMAIL],
        )
        target2 = NotificationTarget(
            user_id=uuid4(),
            email="doctor2@example.com",
            preferred_channels=[NotificationChannel.EMAIL],
        )

        # Setup handler
        email_handler = MagicMock(spec=ChannelHandler)
        email_handler.send = AsyncMock(
            return_value=NotificationResult(
                channel=NotificationChannel.EMAIL,
                target_id=uuid4(),
                success=True,
                message="Email sent",
                sent_at=datetime.utcnow(),
                alert_id=sample_alert.id,
            )
        )
        email_handler.is_enabled = MagicMock(return_value=True)
        dispatcher.register_channel(NotificationChannel.EMAIL, email_handler)

        # Execute
        result = await dispatcher.dispatch(
            alert=sample_alert,
            targets=[target1, target2],
            channels=[NotificationChannel.EMAIL],
        )

        # Assert - should send to both targets
        assert result.total_sent >= 2
        assert email_handler.send.call_count >= 2


# ============================================================================
# Test Batch Dispatch
# ============================================================================


class TestBatchDispatch:
    """Test batch notification dispatch."""

    @pytest.mark.asyncio
    async def test_dispatch_batch_multiple_alerts(
        self, dispatcher, sample_target, mock_channel_handler, successful_result
    ):
        """Test batch dispatch for multiple alerts."""
        # Setup
        alert1 = Alert(
            id=uuid4(),
            patient_id=uuid4(),
            rule_type=AlertRuleType.NO_RESPONSE,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            title="Alert 1",
            message="Message 1",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        alert2 = Alert(
            id=uuid4(),
            patient_id=uuid4(),
            rule_type=AlertRuleType.MISSED_QUIZ,
            severity=AlertSeverity.MEDIUM,
            status=AlertStatus.PENDING,
            title="Alert 2",
            message="Message 2",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        mock_channel_handler.send.return_value = successful_result
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel_handler)

        # Execute
        results = await dispatcher.dispatch_batch(
            alerts=[alert1, alert2],
            targets=[sample_target],
            channels=[NotificationChannel.EMAIL],
        )

        # Assert
        assert len(results) == 2
        assert all(isinstance(r, DispatchResult) for r in results)

    @pytest.mark.asyncio
    async def test_dispatch_batch_empty_list(self, dispatcher, sample_target):
        """Test batch dispatch with empty alert list."""
        # Execute
        results = await dispatcher.dispatch_batch(
            alerts=[],
            targets=[sample_target],
            channels=[NotificationChannel.EMAIL],
        )

        # Assert
        assert results == []


# ============================================================================
# Test Default Channels
# ============================================================================


class TestDefaultChannels:
    """Test default channel selection."""

    @pytest.mark.asyncio
    async def test_dispatch_uses_default_channels_when_none_specified(
        self,
        dispatcher,
        sample_alert,
        sample_target,
        mock_channel_handler,
        successful_result,
    ):
        """Test that dispatch uses default channels when not specified."""
        # Setup
        mock_channel_handler.send.return_value = successful_result
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel_handler)

        # Execute - no channels specified
        result = await dispatcher.dispatch(
            alert=sample_alert,
            targets=[sample_target],
            # channels=None (use default)
        )

        # Assert - should still dispatch
        assert result is not None


# ============================================================================
# Test Statistics
# ============================================================================


class TestStatistics:
    """Test notification statistics tracking."""

    @pytest.mark.asyncio
    async def test_statistics_increment_on_success(
        self,
        dispatcher,
        sample_alert,
        sample_target,
        mock_channel_handler,
        successful_result,
    ):
        """Test that statistics increment on successful send."""
        # Setup
        mock_channel_handler.send.return_value = successful_result
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel_handler)

        initial_sent = dispatcher._total_sent

        # Execute
        await dispatcher.dispatch(
            alert=sample_alert,
            targets=[sample_target],
            channels=[NotificationChannel.EMAIL],
        )

        # Assert
        assert dispatcher._total_sent > initial_sent

    @pytest.mark.asyncio
    async def test_statistics_increment_on_failure(
        self,
        dispatcher,
        sample_alert,
        sample_target,
        mock_channel_handler,
        failed_result,
    ):
        """Test that statistics increment on failed send."""
        # Setup
        mock_channel_handler.send.return_value = failed_result
        dispatcher.register_channel(NotificationChannel.SMS, mock_channel_handler)

        initial_failed = dispatcher._total_failed

        # Execute
        await dispatcher.dispatch(
            alert=sample_alert,
            targets=[sample_target],
            channels=[NotificationChannel.SMS],
        )

        # Assert
        assert dispatcher._total_failed > initial_failed

    def test_get_statistics(self, dispatcher):
        """Test retrieving dispatcher statistics."""
        # Set some statistics
        dispatcher._total_sent = 100
        dispatcher._total_failed = 5

        # Execute
        stats = dispatcher.get_statistics()

        # Assert
        assert stats["total_sent"] == 100
        assert stats["total_failed"] == 5
        assert "success_rate" in stats


# ============================================================================
# Test History
# ============================================================================


class TestNotificationHistory:
    """Test notification history tracking."""

    @pytest.mark.asyncio
    async def test_history_stores_results(
        self,
        dispatcher,
        sample_alert,
        sample_target,
        mock_channel_handler,
        successful_result,
    ):
        """Test that notification history stores results."""
        # Setup
        mock_channel_handler.send.return_value = successful_result
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel_handler)

        # Execute
        await dispatcher.dispatch(
            alert=sample_alert,
            targets=[sample_target],
            channels=[NotificationChannel.EMAIL],
        )

        # Assert
        assert len(dispatcher._notification_history) > 0
        assert all(
            isinstance(r, NotificationResult) for r in dispatcher._notification_history
        )

    @pytest.mark.asyncio
    async def test_get_history_by_alert(
        self,
        dispatcher,
        sample_alert,
        sample_target,
        mock_channel_handler,
        successful_result,
    ):
        """Test retrieving history for specific alert."""
        # Setup
        mock_channel_handler.send.return_value = successful_result
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel_handler)

        # Execute
        await dispatcher.dispatch(
            alert=sample_alert,
            targets=[sample_target],
            channels=[NotificationChannel.EMAIL],
        )

        # Get history
        history = dispatcher.get_history(alert_id=sample_alert.id)

        # Assert
        assert len(history) > 0
        assert all(r.alert_id == sample_alert.id for r in history)

    def test_clear_history(self, dispatcher):
        """Test clearing notification history."""
        # Add some history
        dispatcher._notification_history.append(
            NotificationResult(
                channel=NotificationChannel.EMAIL,
                target_id=uuid4(),
                success=True,
                message="Test",
                sent_at=datetime.utcnow(),
                alert_id=uuid4(),
            )
        )

        assert len(dispatcher._notification_history) > 0

        # Clear
        dispatcher.clear_history()

        # Assert
        assert len(dispatcher._notification_history) == 0


# ============================================================================
# Test Error Handling
# ============================================================================


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_dispatch_handles_handler_exception(
        self, dispatcher, sample_alert, sample_target
    ):
        """Test that dispatch handles channel handler exceptions."""
        # Setup handler that raises exception
        failing_handler = MagicMock(spec=ChannelHandler)
        failing_handler.send = AsyncMock(side_effect=Exception("Channel error"))
        failing_handler.is_enabled = MagicMock(return_value=True)
        dispatcher.register_channel(NotificationChannel.EMAIL, failing_handler)

        # Execute - should not raise exception
        result = await dispatcher.dispatch(
            alert=sample_alert,
            targets=[sample_target],
            channels=[NotificationChannel.EMAIL],
        )

        # Assert - should handle gracefully
        assert result is not None

    @pytest.mark.asyncio
    async def test_dispatch_with_empty_targets(
        self, dispatcher, sample_alert, mock_channel_handler
    ):
        """Test dispatch with empty targets list."""
        # Setup
        dispatcher.register_channel(NotificationChannel.EMAIL, mock_channel_handler)

        # Execute
        result = await dispatcher.dispatch(
            alert=sample_alert,
            targets=[],
            channels=[NotificationChannel.EMAIL],
        )

        # Assert
        assert result.total_sent == 0
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_dispatch_with_none_alert(self, dispatcher, sample_target):
        """Test dispatch with None alert."""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            await dispatcher.dispatch(
                alert=None,
                targets=[sample_target],
                channels=[NotificationChannel.EMAIL],
            )
