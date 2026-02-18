"""
Unit Tests for FlowEventBroadcaster - QW-021 Flow Services Consolidation.

Tests event broadcasting, subscription management, and event handling for the
consolidated flow analytics system.
"""

import pytest
import asyncio
from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock, AsyncMock

from app.services.flow.analytics.event_broadcaster import FlowEventBroadcaster
from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
from app.services.flow.types import (
    FlowEvent,
    FlowEventType,
    FlowContext,
    FlowStepData,
    FlowType,
    FlowStatus,
    FlowStepType,
    FlowStepStatus,
)


@pytest.fixture
def broadcaster():
    """Create FlowEventBroadcaster instance."""
    return FlowEventBroadcaster(max_workers=2)


@pytest.fixture
def flow_instance_id():
    """Create test flow instance ID."""
    return uuid4()


@pytest.fixture
def sample_event(flow_instance_id):
    """Create sample flow event for testing."""
    return FlowEvent(
        event_id=str(uuid4()),
        event_type=FlowEventType.FLOW_STARTED,
        flow_instance_id=flow_instance_id,
        data={"test": "data"},
        source="test",
    )


@pytest.fixture
def sample_context(flow_instance_id):
    """Create sample flow context for testing."""
    return FlowContext(
        flow_instance_id=flow_instance_id,
        flow_type=FlowType.DAILY_FOLLOW_UP,
        patient_id=uuid4(),
        status=FlowStatus.ACTIVE,
    )


@pytest.fixture
def sample_step_data():
    """Create sample step data for testing."""
    return FlowStepData(
        step_id="step_001",
        step_type=FlowStepType.MESSAGE,
        step_name="Test Step",
        status=FlowStepStatus.COMPLETED,
    )


class TestFlowEventBroadcasterInitialization:
    """Test FlowEventBroadcaster initialization."""

    def test_initialization(self, broadcaster):
        """Test broadcaster initializes correctly."""
        assert broadcaster is not None
        assert broadcaster.config is not None
        assert len(broadcaster._subscribers) == 0
        assert len(broadcaster._wildcard_subscribers) == 0
        assert len(broadcaster._event_queue) == 0

    def test_initialization_with_max_workers(self):
        """Test initialization with custom max_workers."""
        broadcaster = FlowEventBroadcaster(max_workers=5)
        assert broadcaster._executor is not None


class TestSubscriptionManagement:
    """Test event subscription management."""

    def test_subscribe_to_event_type(self, broadcaster):
        """Test subscribing to specific event type."""
        handler = Mock()

        subscription_id = broadcaster.subscribe(FlowEventType.FLOW_STARTED, handler)

        assert subscription_id is not None
        assert len(broadcaster._subscribers[FlowEventType.FLOW_STARTED]) == 1

    def test_subscribe_multiple_handlers(self, broadcaster):
        """Test subscribing multiple handlers to same event."""
        handler1 = Mock()
        handler2 = Mock()

        id1 = broadcaster.subscribe(FlowEventType.FLOW_STARTED, handler1)
        id2 = broadcaster.subscribe(FlowEventType.FLOW_STARTED, handler2)

        assert id1 != id2
        assert len(broadcaster._subscribers[FlowEventType.FLOW_STARTED]) == 2

    def test_subscribe_different_event_types(self, broadcaster):
        """Test subscribing to different event types."""
        handler1 = Mock()
        handler2 = Mock()

        broadcaster.subscribe(FlowEventType.FLOW_STARTED, handler1)
        broadcaster.subscribe(FlowEventType.FLOW_COMPLETED, handler2)

        assert len(broadcaster._subscribers[FlowEventType.FLOW_STARTED]) == 1
        assert len(broadcaster._subscribers[FlowEventType.FLOW_COMPLETED]) == 1

    def test_subscribe_all_events(self, broadcaster):
        """Test wildcard subscription to all events."""
        handler = Mock()

        subscription_id = broadcaster.subscribe_all(handler)

        assert subscription_id is not None
        assert len(broadcaster._wildcard_subscribers) == 1

    def test_unsubscribe(self, broadcaster):
        """Test unsubscribing from events."""
        handler = Mock()
        subscription_id = broadcaster.subscribe(FlowEventType.FLOW_STARTED, handler)

        result = broadcaster.unsubscribe(subscription_id)

        assert result is True
        assert len(broadcaster._subscribers[FlowEventType.FLOW_STARTED]) == 0

    def test_unsubscribe_wildcard(self, broadcaster):
        """Test unsubscribing from wildcard subscription."""
        handler = Mock()
        subscription_id = broadcaster.subscribe_all(handler)

        result = broadcaster.unsubscribe(subscription_id)

        assert result is True
        assert len(broadcaster._wildcard_subscribers) == 0

    def test_unsubscribe_invalid_id(self, broadcaster):
        """Test unsubscribing with invalid ID."""
        result = broadcaster.unsubscribe("invalid_id")
        assert result is False

    def test_unsubscribe_all(self, broadcaster):
        """Test unsubscribing all handlers."""
        handler1 = Mock()
        handler2 = Mock()
        handler3 = Mock()

        broadcaster.subscribe(FlowEventType.FLOW_STARTED, handler1)
        broadcaster.subscribe(FlowEventType.FLOW_COMPLETED, handler2)
        broadcaster.subscribe_all(handler3)

        broadcaster.unsubscribe_all()

        assert len(broadcaster._subscribers) == 0
        assert len(broadcaster._wildcard_subscribers) == 0


class TestEventBroadcasting:
    """Test event broadcasting functionality."""

    def test_broadcast_event(self, broadcaster, sample_event):
        """Test broadcasting event to subscribers."""
        handler = Mock()
        broadcaster.subscribe(FlowEventType.FLOW_STARTED, handler)

        broadcaster.broadcast(sample_event)

        handler.assert_called_once()
        call_args = handler.call_args[0][0]
        assert call_args.event_type == FlowEventType.FLOW_STARTED

    def test_broadcast_to_multiple_handlers(self, broadcaster, sample_event):
        """Test broadcasting to multiple handlers."""
        handler1 = Mock()
        handler2 = Mock()

        broadcaster.subscribe(FlowEventType.FLOW_STARTED, handler1)
        broadcaster.subscribe(FlowEventType.FLOW_STARTED, handler2)

        broadcaster.broadcast(sample_event)

        handler1.assert_called_once()
        handler2.assert_called_once()

    def test_broadcast_to_wildcard_subscribers(self, broadcaster, sample_event):
        """Test broadcasting to wildcard subscribers."""
        wildcard_handler = Mock()
        specific_handler = Mock()

        broadcaster.subscribe_all(wildcard_handler)
        broadcaster.subscribe(FlowEventType.FLOW_STARTED, specific_handler)

        broadcaster.broadcast(sample_event)

        wildcard_handler.assert_called_once()
        specific_handler.assert_called_once()

    def test_broadcast_no_subscribers(self, broadcaster, sample_event):
        """Test broadcasting with no subscribers (should not crash)."""
        # Should not raise exception
        broadcaster.broadcast(sample_event)

    def test_broadcast_adds_to_queue(self, broadcaster, sample_event):
        """Test that broadcast adds event to queue."""
        broadcaster.broadcast(sample_event)

        assert len(broadcaster._event_queue) == 1
        assert broadcaster._event_queue[0].event_id == sample_event.event_id

    def test_broadcast_disabled(self, broadcaster, sample_event):
        """Test broadcast when event broadcasting is disabled."""
        broadcaster.config.enable_event_broadcasting = False
        handler = Mock()
        broadcaster.subscribe(FlowEventType.FLOW_STARTED, handler)

        broadcaster.broadcast(sample_event)

        handler.assert_not_called()


class TestConvenienceBroadcastMethods:
    """Test convenience methods for common events."""

    def test_broadcast_flow_started(
        self, broadcaster, flow_instance_id, sample_context
    ):
        """Test broadcasting flow started event."""
        handler = Mock()
        broadcaster.subscribe(FlowEventType.FLOW_STARTED, handler)

        broadcaster.broadcast_flow_started(flow_instance_id, sample_context)

        handler.assert_called_once()
        call_args = handler.call_args[0][0]
        assert call_args.event_type == FlowEventType.FLOW_STARTED
        assert call_args.flow_instance_id == flow_instance_id

    def test_broadcast_flow_completed(
        self, broadcaster, flow_instance_id, sample_context
    ):
        """Test broadcasting flow completed event."""
        handler = Mock()
        broadcaster.subscribe(FlowEventType.FLOW_COMPLETED, handler)

        sample_context.started_at = now_sao_paulo_naive()
        sample_context.completed_at = now_sao_paulo_naive()

        broadcaster.broadcast_flow_completed(flow_instance_id, sample_context)

        handler.assert_called_once()
        call_args = handler.call_args[0][0]
        assert call_args.event_type == FlowEventType.FLOW_COMPLETED

    def test_broadcast_flow_failed(self, broadcaster, flow_instance_id, sample_context):
        """Test broadcasting flow failed event."""
        handler = Mock()
        broadcaster.subscribe(FlowEventType.FLOW_FAILED, handler)

        error = Exception("Test error")
        broadcaster.broadcast_flow_failed(flow_instance_id, sample_context, error)

        handler.assert_called_once()
        call_args = handler.call_args[0][0]
        assert call_args.event_type == FlowEventType.FLOW_FAILED
        assert "error_type" in call_args.data

    def test_broadcast_step_started(
        self, broadcaster, flow_instance_id, sample_step_data
    ):
        """Test broadcasting step started event."""
        handler = Mock()
        broadcaster.subscribe(FlowEventType.STEP_STARTED, handler)

        broadcaster.broadcast_step_started(flow_instance_id, sample_step_data)

        handler.assert_called_once()
        call_args = handler.call_args[0][0]
        assert call_args.event_type == FlowEventType.STEP_STARTED
        assert call_args.step_id == sample_step_data.step_id

    def test_broadcast_step_completed(
        self, broadcaster, flow_instance_id, sample_step_data
    ):
        """Test broadcasting step completed event."""
        handler = Mock()
        broadcaster.subscribe(FlowEventType.STEP_COMPLETED, handler)

        sample_step_data.started_at = now_sao_paulo_naive()
        sample_step_data.completed_at = now_sao_paulo_naive()

        broadcaster.broadcast_step_completed(flow_instance_id, sample_step_data)

        handler.assert_called_once()

    def test_broadcast_step_failed(
        self, broadcaster, flow_instance_id, sample_step_data
    ):
        """Test broadcasting step failed event."""
        handler = Mock()
        broadcaster.subscribe(FlowEventType.STEP_FAILED, handler)

        error = Exception("Step error")
        broadcaster.broadcast_step_failed(flow_instance_id, sample_step_data, error)

        handler.assert_called_once()
        call_args = handler.call_args[0][0]
        assert call_args.event_type == FlowEventType.STEP_FAILED


class TestEventQueue:
    """Test event queue management."""

    def test_event_added_to_queue(self, broadcaster, sample_event):
        """Test that events are added to queue."""
        broadcaster.broadcast(sample_event)

        assert len(broadcaster._event_queue) == 1

    def test_queue_size_limit(self, broadcaster):
        """Test that queue respects size limit."""
        max_size = broadcaster._max_queue_size

        # Add more events than max size
        for i in range(max_size + 10):
            event = FlowEvent(
                event_id=str(uuid4()),
                event_type=FlowEventType.FLOW_STARTED,
                flow_instance_id=uuid4(),
                data={"index": i},
            )
            broadcaster.broadcast(event)

        # Queue should not exceed max size
        assert len(broadcaster._event_queue) == max_size

    def test_get_recent_events(self, broadcaster, flow_instance_id):
        """Test getting recent events."""
        # Add some events
        for i in range(5):
            event = FlowEvent(
                event_id=str(uuid4()),
                event_type=FlowEventType.FLOW_STARTED,
                flow_instance_id=flow_instance_id,
                data={"index": i},
            )
            broadcaster.broadcast(event)

        recent = broadcaster.get_recent_events(limit=3)

        assert len(recent) == 3

    def test_get_recent_events_filtered_by_flow(self, broadcaster):
        """Test filtering recent events by flow ID."""
        flow_id_1 = uuid4()
        flow_id_2 = uuid4()

        # Add events for different flows
        for i in range(3):
            broadcaster.broadcast(
                FlowEvent(
                    event_id=str(uuid4()),
                    event_type=FlowEventType.FLOW_STARTED,
                    flow_instance_id=flow_id_1,
                    data={},
                )
            )
            broadcaster.broadcast(
                FlowEvent(
                    event_id=str(uuid4()),
                    event_type=FlowEventType.FLOW_STARTED,
                    flow_instance_id=flow_id_2,
                    data={},
                )
            )

        recent = broadcaster.get_recent_events(flow_instance_id=flow_id_1)

        assert len(recent) == 3
        assert all(e.flow_instance_id == flow_id_1 for e in recent)

    def test_get_recent_events_filtered_by_type(self, broadcaster, flow_instance_id):
        """Test filtering recent events by event type."""
        # Add different event types
        broadcaster.broadcast(
            FlowEvent(
                event_id=str(uuid4()),
                event_type=FlowEventType.FLOW_STARTED,
                flow_instance_id=flow_instance_id,
                data={},
            )
        )
        broadcaster.broadcast(
            FlowEvent(
                event_id=str(uuid4()),
                event_type=FlowEventType.FLOW_COMPLETED,
                flow_instance_id=flow_instance_id,
                data={},
            )
        )
        broadcaster.broadcast(
            FlowEvent(
                event_id=str(uuid4()),
                event_type=FlowEventType.FLOW_STARTED,
                flow_instance_id=flow_instance_id,
                data={},
            )
        )

        recent = broadcaster.get_recent_events(event_type=FlowEventType.FLOW_STARTED)

        assert len(recent) == 2
        assert all(e.event_type == FlowEventType.FLOW_STARTED for e in recent)

    def test_clear_event_queue(self, broadcaster, sample_event):
        """Test clearing event queue."""
        broadcaster.broadcast(sample_event)
        assert len(broadcaster._event_queue) > 0

        broadcaster.clear_event_queue()

        assert len(broadcaster._event_queue) == 0


class TestErrorHandling:
    """Test error handling in event handlers."""

    def test_handler_error_caught(self, broadcaster, sample_event):
        """Test that handler errors are caught and don't crash."""

        def failing_handler(event):
            raise Exception("Handler error")

        broadcaster.subscribe(FlowEventType.FLOW_STARTED, failing_handler)

        # Should not raise exception
        broadcaster.broadcast(sample_event)

    def test_one_handler_error_doesnt_affect_others(self, broadcaster, sample_event):
        """Test that one handler error doesn't prevent others from running."""

        def failing_handler(event):
            raise Exception("Handler error")

        working_handler = Mock()

        broadcaster.subscribe(FlowEventType.FLOW_STARTED, failing_handler)
        broadcaster.subscribe(FlowEventType.FLOW_STARTED, working_handler)

        broadcaster.broadcast(sample_event)

        # Working handler should still be called
        working_handler.assert_called_once()


class TestAsyncHandlers:
    """Test async event handler support."""

    @pytest.mark.asyncio
    async def test_async_handler_support(self, broadcaster, sample_event):
        """Test that async handlers are supported."""
        async_handler = AsyncMock()

        broadcaster.subscribe(FlowEventType.FLOW_STARTED, async_handler)
        broadcaster.broadcast(sample_event)

        # Give async handler time to execute
        await asyncio.sleep(0.1)

        # Note: In real implementation, async handlers run in executor
        # This test verifies the system doesn't crash with async handlers


class TestUtilityMethods:
    """Test utility methods."""

    def test_get_subscriber_count(self, broadcaster):
        """Test getting subscriber count."""
        handler1 = Mock()
        handler2 = Mock()
        handler3 = Mock()

        broadcaster.subscribe(FlowEventType.FLOW_STARTED, handler1)
        broadcaster.subscribe(FlowEventType.FLOW_COMPLETED, handler2)
        broadcaster.subscribe_all(handler3)

        total_count = broadcaster.get_subscriber_count()
        assert total_count == 3

        specific_count = broadcaster.get_subscriber_count(FlowEventType.FLOW_STARTED)
        assert specific_count == 1

    def test_get_queue_size(self, broadcaster, sample_event):
        """Test getting queue size."""
        assert broadcaster.get_queue_size() == 0

        broadcaster.broadcast(sample_event)
        assert broadcaster.get_queue_size() == 1

    def test_shutdown(self, broadcaster):
        """Test shutting down broadcaster."""
        # Should not crash
        broadcaster.shutdown()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_subscribe_same_handler_multiple_times(self, broadcaster):
        """Test subscribing same handler multiple times."""
        handler = Mock()

        id1 = broadcaster.subscribe(FlowEventType.FLOW_STARTED, handler)
        id2 = broadcaster.subscribe(FlowEventType.FLOW_STARTED, handler)

        # Should create separate subscriptions
        assert id1 != id2
        assert len(broadcaster._subscribers[FlowEventType.FLOW_STARTED]) == 2

    def test_broadcast_empty_event_data(self, broadcaster, flow_instance_id):
        """Test broadcasting event with no data."""
        event = FlowEvent(
            event_id=str(uuid4()),
            event_type=FlowEventType.FLOW_STARTED,
            flow_instance_id=flow_instance_id,
            data={},
        )

        # Should not crash
        broadcaster.broadcast(event)

    def test_unsubscribe_while_broadcasting(self, broadcaster, sample_event):
        """Test unsubscribing during broadcast (edge case)."""
        subscription_ids = []

        def unsubscribing_handler(event):
            # Unsubscribe itself during execution
            if subscription_ids:
                broadcaster.unsubscribe(subscription_ids[0])

        sub_id = broadcaster.subscribe(
            FlowEventType.FLOW_STARTED, unsubscribing_handler
        )
        subscription_ids.append(sub_id)

        # Should not crash
        broadcaster.broadcast(sample_event)


class TestMultipleEventTypes:
    """Test handling multiple event types."""

    def test_handler_called_only_for_subscribed_type(self, broadcaster):
        """Test handler only called for subscribed event type."""
        handler = Mock()
        broadcaster.subscribe(FlowEventType.FLOW_STARTED, handler)

        # Broadcast different event type
        event = FlowEvent(
            event_id=str(uuid4()),
            event_type=FlowEventType.FLOW_COMPLETED,
            flow_instance_id=uuid4(),
            data={},
        )
        broadcaster.broadcast(event)

        handler.assert_not_called()

    def test_wildcard_receives_all_types(self, broadcaster):
        """Test wildcard subscriber receives all event types."""
        wildcard_handler = Mock()
        broadcaster.subscribe_all(wildcard_handler)

        event_types = [
            FlowEventType.FLOW_STARTED,
            FlowEventType.FLOW_COMPLETED,
            FlowEventType.FLOW_FAILED,
            FlowEventType.STEP_STARTED,
        ]

        for event_type in event_types:
            event = FlowEvent(
                event_id=str(uuid4()),
                event_type=event_type,
                flow_instance_id=uuid4(),
                data={},
            )
            broadcaster.broadcast(event)

        assert wildcard_handler.call_count == len(event_types)