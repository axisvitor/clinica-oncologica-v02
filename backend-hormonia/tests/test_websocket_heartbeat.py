"""
Tests for WebSocket heartbeat system.

This module tests:
- Heartbeat manager functionality
- Connection health monitoring
- Ping/pong cycle management
- Dead connection detection
- Health metrics and statistics
"""
import asyncio
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from app.services.websocket_heartbeat import (
    WebSocketHeartbeatManager,
    HeartbeatStatus,
    HeartbeatMetrics
)


@pytest.fixture
def heartbeat_manager():
    """Create a WebSocket heartbeat manager for testing."""
    return WebSocketHeartbeatManager(
        heartbeat_interval=0.1,  # 100ms for fast testing
        heartbeat_timeout=0.05,  # 50ms timeout
        max_missed_pings=3,
        warning_threshold=2,
        cleanup_interval=0.2,  # 200ms cleanup
        latency_history_size=5
    )


@pytest.fixture
async def running_heartbeat_manager():
    """Create and start a heartbeat manager."""
    manager = WebSocketHeartbeatManager(
        heartbeat_interval=0.1,
        heartbeat_timeout=0.05,
        max_missed_pings=3,
        warning_threshold=2,
        cleanup_interval=0.2
    )
    await manager.start()
    yield manager
    await manager.stop()


class TestHeartbeatMetrics:
    """Test HeartbeatMetrics dataclass."""
    
    def test_metrics_creation(self):
        """Test HeartbeatMetrics creation and defaults."""
        metrics = HeartbeatMetrics(connection_id="test-conn")
        
        assert metrics.connection_id == "test-conn"
        assert metrics.status == HeartbeatStatus.HEALTHY
        assert metrics.ping_count == 0
        assert metrics.pong_count == 0
        assert metrics.missed_pings == 0
        assert metrics.average_latency == 0.0
        assert metrics.min_latency == float('inf')
        assert metrics.max_latency == 0.0
        assert len(metrics.latency_samples) == 0
        assert isinstance(metrics.created_at, datetime)
    
    def test_latency_sample_addition(self):
        """Test adding latency samples and statistics calculation."""
        metrics = HeartbeatMetrics(connection_id="test-conn")
        
        # Add latency samples
        latencies = [10.0, 20.0, 30.0, 15.0, 25.0]
        for latency in latencies:
            metrics.add_latency_sample(latency)
        
        assert len(metrics.latency_samples) == 5
        assert metrics.average_latency == 20.0  # (10+20+30+15+25)/5
        assert metrics.min_latency == 10.0
        assert metrics.max_latency == 30.0
        
        # Add more samples to test rolling window
        for i in range(10):
            metrics.add_latency_sample(100.0)
        
        # Should keep only last 10 samples
        assert len(metrics.latency_samples) == 10
        assert all(sample == 100.0 for sample in metrics.latency_samples[-5:])
    
    def test_status_update(self):
        """Test status update based on missed pings."""
        metrics = HeartbeatMetrics(connection_id="test-conn")
        
        # Healthy state
        metrics.missed_pings = 0
        metrics.update_status(max_missed_pings=3, warning_threshold=2)
        assert metrics.status == HeartbeatStatus.HEALTHY
        
        # Warning state
        metrics.missed_pings = 2
        metrics.update_status(max_missed_pings=3, warning_threshold=2)
        assert metrics.status == HeartbeatStatus.WARNING
        
        # Critical state
        metrics.missed_pings = 2
        metrics.update_status(max_missed_pings=3, warning_threshold=1)
        assert metrics.status == HeartbeatStatus.CRITICAL
        
        # Dead state
        metrics.missed_pings = 3
        metrics.update_status(max_missed_pings=3, warning_threshold=2)
        assert metrics.status == HeartbeatStatus.DEAD


class TestWebSocketHeartbeatManager:
    """Test WebSocket heartbeat manager."""
    
    @pytest.mark.asyncio
    async def test_manager_lifecycle(self, heartbeat_manager):
        """Test heartbeat manager start/stop lifecycle."""
        assert not heartbeat_manager._running
        
        await heartbeat_manager.start()
        assert heartbeat_manager._running
        assert heartbeat_manager._heartbeat_task is not None
        assert heartbeat_manager._cleanup_task is not None
        
        await heartbeat_manager.stop()
        assert not heartbeat_manager._running
        assert heartbeat_manager._heartbeat_task.cancelled()
        assert heartbeat_manager._cleanup_task.cancelled()
    
    def test_connection_registration(self, heartbeat_manager):
        """Test connection registration and unregistration."""
        connection_id = "test-connection-1"
        
        # Register connection
        heartbeat_manager.register_connection(connection_id)
        
        assert connection_id in heartbeat_manager.connection_metrics
        assert connection_id in heartbeat_manager.pending_pings
        
        metrics = heartbeat_manager.connection_metrics[connection_id]
        assert metrics.connection_id == connection_id
        assert metrics.status == HeartbeatStatus.HEALTHY
        
        # Unregister connection
        heartbeat_manager.unregister_connection(connection_id)
        
        assert connection_id not in heartbeat_manager.connection_metrics
        assert connection_id not in heartbeat_manager.pending_pings
    
    @pytest.mark.asyncio
    async def test_ping_sending(self, heartbeat_manager):
        """Test ping sending functionality."""
        connection_id = "test-connection"
        heartbeat_manager.register_connection(connection_id)
        
        # Mock send callback
        send_callback = AsyncMock(return_value=True)
        
        # Send ping
        success = await heartbeat_manager.send_ping(connection_id, send_callback)
        
        assert success
        send_callback.assert_called_once()
        
        # Check call arguments
        call_args = send_callback.call_args
        assert call_args[0][0] == connection_id  # connection_id
        ping_message = call_args[0][1]  # ping_message
        
        assert ping_message["type"] == "ping"
        assert "ping_id" in ping_message["data"]
        assert "timestamp" in ping_message["data"]
        assert "server_time" in ping_message["data"]
        
        # Check metrics update
        metrics = heartbeat_manager.connection_metrics[connection_id]
        assert metrics.ping_count == 1
        assert metrics.last_ping_sent is not None
        
        # Check pending pings
        ping_id = ping_message["data"]["ping_id"]
        assert ping_id in heartbeat_manager.pending_pings[connection_id]
        
        # Check statistics
        assert heartbeat_manager.total_pings_sent == 1
    
    @pytest.mark.asyncio
    async def test_ping_failure(self, heartbeat_manager):
        """Test ping sending failure handling."""
        connection_id = "test-connection"
        heartbeat_manager.register_connection(connection_id)
        
        # Mock send callback that fails
        send_callback = AsyncMock(return_value=False)
        
        # Send ping
        success = await heartbeat_manager.send_ping(connection_id, send_callback)
        
        assert not success
        
        # Check metrics update
        metrics = heartbeat_manager.connection_metrics[connection_id]
        assert metrics.missed_pings == 1
        assert metrics.status == HeartbeatStatus.HEALTHY  # Still healthy with 1 miss
    
    def test_pong_handling(self, heartbeat_manager):
        """Test pong response handling."""
        connection_id = "test-connection"
        heartbeat_manager.register_connection(connection_id)
        
        # Simulate a pending ping
        ping_id = "test-ping-123"
        ping_timestamp = time.time() - 0.01  # 10ms ago
        heartbeat_manager.pending_pings[connection_id][ping_id] = ping_timestamp
        
        # Handle pong
        success = heartbeat_manager.handle_pong(connection_id, ping_id)
        
        assert success
        
        # Check metrics update
        metrics = heartbeat_manager.connection_metrics[connection_id]
        assert metrics.pong_count == 1
        assert metrics.last_pong_received is not None
        assert metrics.missed_pings == 0
        assert len(metrics.latency_samples) == 1
        
        # Check latency calculation
        latency = metrics.latency_samples[0]
        assert latency > 0  # Should be positive
        assert latency < 100  # Should be reasonable (< 100ms)
        
        # Check pending ping removal
        assert ping_id not in heartbeat_manager.pending_pings[connection_id]
        
        # Check statistics
        assert heartbeat_manager.total_pongs_received == 1
    
    def test_pong_invalid_ping_id(self, heartbeat_manager):
        """Test pong handling with invalid ping ID."""
        connection_id = "test-connection"
        heartbeat_manager.register_connection(connection_id)
        
        # Handle pong with non-existent ping ID
        success = heartbeat_manager.handle_pong(connection_id, "invalid-ping-id")
        
        assert not success
        
        # Metrics should not be updated
        metrics = heartbeat_manager.connection_metrics[connection_id]
        assert metrics.pong_count == 0
    
    def test_connection_health_retrieval(self, heartbeat_manager):
        """Test connection health retrieval."""
        connection_id = "test-connection"
        
        # Non-existent connection
        health = heartbeat_manager.get_connection_health(connection_id)
        assert health is None
        
        # Register connection
        heartbeat_manager.register_connection(connection_id)
        
        # Get health
        health = heartbeat_manager.get_connection_health(connection_id)
        assert health is not None
        assert health.connection_id == connection_id
        assert health.status == HeartbeatStatus.HEALTHY
    
    def test_health_summary(self, heartbeat_manager):
        """Test health summary generation."""
        # Register multiple connections
        connections = ["conn1", "conn2", "conn3", "conn4"]
        for conn_id in connections:
            heartbeat_manager.register_connection(conn_id)
        
        # Set different states and metrics
        heartbeat_manager.connection_metrics["conn1"].status = HeartbeatStatus.HEALTHY
        heartbeat_manager.connection_metrics["conn1"].add_latency_sample(10.0)
        
        heartbeat_manager.connection_metrics["conn2"].status = HeartbeatStatus.WARNING
        heartbeat_manager.connection_metrics["conn2"].add_latency_sample(50.0)
        
        heartbeat_manager.connection_metrics["conn3"].status = HeartbeatStatus.CRITICAL
        heartbeat_manager.connection_metrics["conn3"].add_latency_sample(100.0)
        
        heartbeat_manager.connection_metrics["conn4"].status = HeartbeatStatus.DEAD
        
        # Set some statistics
        heartbeat_manager.total_pings_sent = 10
        heartbeat_manager.total_pongs_received = 8
        heartbeat_manager.total_timeouts = 2
        
        summary = heartbeat_manager.get_health_summary()
        
        assert summary["total_connections"] == 4
        assert summary["healthy_connections"] == 1
        assert summary["warning_connections"] == 1
        assert summary["critical_connections"] == 1
        assert summary["dead_connections"] == 1
        assert summary["average_latency_ms"] == 53.33  # (10+50+100)/3
        assert summary["total_pings_sent"] == 10
        assert summary["total_pongs_received"] == 8
        assert summary["total_timeouts"] == 2
        assert summary["ping_success_rate"] == 80.0  # 8/10 * 100
    
    def test_callback_setting(self, heartbeat_manager):
        """Test callback function setting."""
        # Mock callbacks
        on_dead = Mock()
        on_warning = Mock()
        on_timeout = Mock()
        
        # Set callbacks
        heartbeat_manager.set_callbacks(
            on_connection_dead=on_dead,
            on_connection_warning=on_warning,
            on_ping_timeout=on_timeout
        )
        
        assert heartbeat_manager.on_connection_dead == on_dead
        assert heartbeat_manager.on_connection_warning == on_warning
        assert heartbeat_manager.on_ping_timeout == on_timeout
    
    @pytest.mark.asyncio
    async def test_ping_timeout_detection(self, heartbeat_manager):
        """Test ping timeout detection."""
        connection_id = "test-connection"
        heartbeat_manager.register_connection(connection_id)
        
        # Mock timeout callback
        timeout_callback = Mock()
        heartbeat_manager.set_callbacks(on_ping_timeout=timeout_callback)
        
        # Add a pending ping that should timeout
        ping_id = "timeout-ping"
        old_timestamp = time.time() - 10  # 10 seconds ago
        heartbeat_manager.pending_pings[connection_id][ping_id] = old_timestamp
        
        # Perform cleanup to trigger timeout detection
        await heartbeat_manager._perform_cleanup()
        
        # Check timeout was detected
        assert heartbeat_manager.total_timeouts > 0
        timeout_callback.assert_called_once_with(connection_id, ping_id)
        
        # Check ping was removed from pending
        assert ping_id not in heartbeat_manager.pending_pings[connection_id]
    
    @pytest.mark.asyncio
    async def test_heartbeat_loop_dead_connection_detection(self, running_heartbeat_manager):
        """Test heartbeat loop detecting dead connections."""
        connection_id = "test-connection"
        running_heartbeat_manager.register_connection(connection_id)
        
        # Mock callbacks
        dead_callback = Mock()
        warning_callback = Mock()
        running_heartbeat_manager.set_callbacks(
            on_connection_dead=dead_callback,
            on_connection_warning=warning_callback
        )
        
        # Simulate missed pings
        metrics = running_heartbeat_manager.connection_metrics[connection_id]
        metrics.missed_pings = 2  # Warning threshold
        
        # Wait for heartbeat cycle
        await asyncio.sleep(0.15)
        
        # Should trigger warning callback
        warning_callback.assert_called_once_with(connection_id, metrics)
        
        # Simulate more missed pings to trigger dead state
        metrics.missed_pings = 3  # Max missed pings
        
        # Wait for another heartbeat cycle
        await asyncio.sleep(0.15)
        
        # Should trigger dead callback
        dead_callback.assert_called_once_with(connection_id)
        assert running_heartbeat_manager.total_dead_connections > 0
    
    @pytest.mark.asyncio
    async def test_concurrent_ping_handling(self, heartbeat_manager):
        """Test handling multiple concurrent pings."""
        connection_id = "test-connection"
        heartbeat_manager.register_connection(connection_id)
        
        # Mock send callback
        send_callback = AsyncMock(return_value=True)
        
        # Send multiple pings concurrently
        tasks = []
        for i in range(5):
            task = asyncio.create_task(
                heartbeat_manager.send_ping(connection_id, send_callback)
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # All pings should succeed
        assert all(results)
        assert send_callback.call_count == 5
        
        # Check metrics
        metrics = heartbeat_manager.connection_metrics[connection_id]
        assert metrics.ping_count == 5
        
        # Check pending pings
        assert len(heartbeat_manager.pending_pings[connection_id]) == 5
    
    @pytest.mark.asyncio
    async def test_cleanup_old_pending_pings(self, heartbeat_manager):
        """Test cleanup of old pending pings."""
        connection_id = "test-connection"
        heartbeat_manager.register_connection(connection_id)
        
        # Add old and new pending pings
        old_timestamp = time.time() - 200  # Very old
        new_timestamp = time.time() - 1    # Recent
        
        heartbeat_manager.pending_pings[connection_id]["old-ping"] = old_timestamp
        heartbeat_manager.pending_pings[connection_id]["new-ping"] = new_timestamp
        
        # Perform cleanup
        await heartbeat_manager._perform_cleanup()
        
        # Old ping should be removed, new ping should remain
        pending = heartbeat_manager.pending_pings[connection_id]
        assert "old-ping" not in pending
        assert "new-ping" in pending
        
        # Timeout should be recorded
        assert heartbeat_manager.total_timeouts > 0


class TestHeartbeatIntegration:
    """Integration tests for heartbeat system."""
    
    @pytest.mark.asyncio
    async def test_full_ping_pong_cycle(self, running_heartbeat_manager):
        """Test complete ping-pong cycle with real timing."""
        connection_id = "integration-test"
        running_heartbeat_manager.register_connection(connection_id)
        
        # Mock send callback that captures ping messages
        sent_pings = []
        
        async def mock_send(conn_id, message):
            sent_pings.append(message)
            return True
        
        # Send ping
        success = await running_heartbeat_manager.send_ping(connection_id, mock_send)
        assert success
        assert len(sent_pings) == 1
        
        # Extract ping ID and simulate pong
        ping_message = sent_pings[0]
        ping_id = ping_message["data"]["ping_id"]
        
        # Wait a bit to simulate network latency
        await asyncio.sleep(0.01)
        
        # Handle pong
        pong_success = running_heartbeat_manager.handle_pong(connection_id, ping_id)
        assert pong_success
        
        # Check final metrics
        metrics = running_heartbeat_manager.get_connection_health(connection_id)
        assert metrics.ping_count == 1
        assert metrics.pong_count == 1
        assert metrics.missed_pings == 0
        assert metrics.status == HeartbeatStatus.HEALTHY
        assert len(metrics.latency_samples) == 1
        assert metrics.latency_samples[0] > 0
    
    @pytest.mark.asyncio
    async def test_connection_degradation_cycle(self, running_heartbeat_manager):
        """Test connection health degradation over time."""
        connection_id = "degradation-test"
        running_heartbeat_manager.register_connection(connection_id)
        
        # Mock callbacks to track state changes
        state_changes = []
        
        def on_warning(conn_id, metrics):
            state_changes.append(("warning", conn_id, metrics.status))
        
        def on_dead(conn_id):
            state_changes.append(("dead", conn_id))
        
        running_heartbeat_manager.set_callbacks(
            on_connection_warning=on_warning,
            on_connection_dead=on_dead
        )
        
        # Simulate gradual connection degradation
        metrics = running_heartbeat_manager.connection_metrics[connection_id]
        
        # Start healthy
        assert metrics.status == HeartbeatStatus.HEALTHY
        
        # Simulate missed pings
        metrics.missed_pings = 2  # Warning threshold
        metrics.update_status(
            running_heartbeat_manager.max_missed_pings,
            running_heartbeat_manager.warning_threshold
        )
        
        # Wait for heartbeat cycle to detect warning
        await asyncio.sleep(0.15)
        
        # Should have triggered warning
        assert len(state_changes) > 0
        assert state_changes[0][0] == "warning"
        
        # Simulate more missed pings to reach dead state
        metrics.missed_pings = 3  # Max missed pings
        
        # Wait for heartbeat cycle to detect dead connection
        await asyncio.sleep(0.15)
        
        # Should have triggered dead callback
        dead_events = [event for event in state_changes if event[0] == "dead"]
        assert len(dead_events) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])