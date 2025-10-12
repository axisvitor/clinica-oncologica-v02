"""
Tests for enhanced WebSocket connection management.

This module tests:
- Enhanced WebSocket connection manager functionality
- Connection pooling and lifecycle management
- Heartbeat system and health monitoring
- Resource cleanup and memory management
- Connection state tracking and metrics
"""
import asyncio
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.services.enhanced_websocket_manager import (
    EnhancedWebSocketConnectionManager,
    EnhancedWebSocketManager,
    ConnectionState,
    ConnectionInfo
)
from app.services.websocket_heartbeat import (
    WebSocketHeartbeatManager,
    HeartbeatStatus,
    HeartbeatMetrics
)
from app.models.user import User, UserRole


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self):
        self.closed = False
        self.messages_sent = []
        self.close_code = None
        self.close_reason = None
    
    async def accept(self):
        """Mock accept method."""
        pass
    
    async def send_text(self, data: str):
        """Mock send_text method."""
        if self.closed:
            raise RuntimeError("WebSocket connection is closed")
        self.messages_sent.append(data)
    
    async def close(self, code: int = 1000, reason: str = ""):
        """Mock close method."""
        self.closed = True
        self.close_code = code
        self.close_reason = reason


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket."""
    return MockWebSocket()


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = Mock(spec=User)
    user.id = "test-user-id"
    user.email = "test@example.com"
    user.role = UserRole.PATIENT
    user.is_active = True
    return user


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return Mock(spec=Session)


@pytest.fixture
async def connection_manager():
    """Create an enhanced WebSocket connection manager."""
    manager = EnhancedWebSocketConnectionManager(
        heartbeat_interval=1,  # 1 second for faster testing
        heartbeat_timeout=0.5,  # 0.5 seconds
        max_missed_pings=2,
        cleanup_interval=2,  # 2 seconds
        max_connections_per_user=3
    )
    await manager.start()
    yield manager
    await manager.stop()


@pytest.fixture
def heartbeat_manager():
    """Create a WebSocket heartbeat manager."""
    return WebSocketHeartbeatManager(
        heartbeat_interval=1,
        heartbeat_timeout=0.5,
        max_missed_pings=2,
        cleanup_interval=2
    )


class TestEnhancedWebSocketConnectionManager:
    """Test enhanced WebSocket connection manager."""
    
    @pytest.mark.asyncio
    async def test_connection_lifecycle(self, connection_manager, mock_websocket):
        """Test basic connection lifecycle."""
        # Connect
        connection_id = await connection_manager.connect(mock_websocket)
        
        assert connection_id in connection_manager.connections
        assert len(connection_manager.connections) == 1
        
        connection_info = connection_manager.connections[connection_id]
        assert connection_info.state == ConnectionState.CONNECTED
        assert connection_info.websocket == mock_websocket
        
        # Disconnect
        await connection_manager.disconnect(connection_id)
        
        assert connection_id not in connection_manager.connections
        assert len(connection_manager.connections) == 0
        assert mock_websocket.closed
    
    @pytest.mark.asyncio
    async def test_connection_authentication(self, connection_manager, mock_websocket, mock_user, mock_db):
        """Test connection authentication."""
        connection_id = await connection_manager.connect(mock_websocket)
        
        # Mock the base ConnectionManager authentication
        with patch('app.services.enhanced_websocket_manager.ConnectionManager') as mock_base:
            mock_base_instance = mock_base.return_value
            mock_base_instance.authenticate_connection = AsyncMock(return_value=mock_user)
            
            # Authenticate
            user = await connection_manager.authenticate_connection(connection_id, "test-token", mock_db)
            
            assert user == mock_user
            
            connection_info = connection_manager.connections[connection_id]
            assert connection_info.authenticated
            assert connection_info.user_id == str(mock_user.id)
            assert connection_info.state == ConnectionState.AUTHENTICATED
            
            # Check user connections mapping
            assert str(mock_user.id) in connection_manager.user_connections
            assert connection_id in connection_manager.user_connections[str(mock_user.id)]
    
    @pytest.mark.asyncio
    async def test_connection_limit_per_user(self, connection_manager, mock_user, mock_db):
        """Test connection limit enforcement per user."""
        connection_ids = []
        
        # Mock authentication
        with patch('app.services.enhanced_websocket_manager.ConnectionManager') as mock_base:
            mock_base_instance = mock_base.return_value
            mock_base_instance.authenticate_connection = AsyncMock(return_value=mock_user)
            
            # Create connections up to the limit
            for i in range(4):  # Limit is 3, so 4th should disconnect oldest
                websocket = MockWebSocket()
                connection_id = await connection_manager.connect(websocket)
                await connection_manager.authenticate_connection(connection_id, "test-token", mock_db)
                connection_ids.append(connection_id)
            
            # First connection should be disconnected
            assert connection_ids[0] not in connection_manager.connections
            assert len(connection_manager.user_connections[str(mock_user.id)]) == 3
    
    @pytest.mark.asyncio
    async def test_patient_room_management(self, connection_manager, mock_websocket, mock_user, mock_db):
        """Test patient room join/leave functionality."""
        connection_id = await connection_manager.connect(mock_websocket)
        
        # Mock authentication
        with patch('app.services.enhanced_websocket_manager.ConnectionManager') as mock_base:
            mock_base_instance = mock_base.return_value
            mock_base_instance.authenticate_connection = AsyncMock(return_value=mock_user)
            
            await connection_manager.authenticate_connection(connection_id, "test-token", mock_db)
            
            # Join patient room
            patient_id = "patient-123"
            success = await connection_manager.join_patient_room(connection_id, patient_id)
            
            assert success
            assert patient_id in connection_manager.patient_rooms
            assert connection_id in connection_manager.patient_rooms[patient_id]
            
            connection_info = connection_manager.connections[connection_id]
            assert connection_info.patient_id == patient_id
            
            # Leave patient room
            await connection_manager.leave_patient_room(connection_id, patient_id)
            
            assert patient_id not in connection_manager.patient_rooms
            assert connection_info.patient_id is None
    
    @pytest.mark.asyncio
    async def test_message_sending(self, connection_manager, mock_websocket):
        """Test message sending functionality."""
        connection_id = await connection_manager.connect(mock_websocket)
        
        # Send message
        message = {"type": "test", "data": {"content": "hello"}}
        success = await connection_manager.send_message(connection_id, message)
        
        assert success
        assert len(mock_websocket.messages_sent) == 2  # Welcome message + test message
        
        # Parse the test message (second message)
        sent_message = json.loads(mock_websocket.messages_sent[1])
        assert sent_message["type"] == "test"
        assert sent_message["data"]["content"] == "hello"
        
        # Update connection stats
        connection_info = connection_manager.connections[connection_id]
        assert connection_info.messages_sent == 2
        assert connection_info.bytes_sent > 0
    
    @pytest.mark.asyncio
    async def test_broadcasting(self, connection_manager, mock_user, mock_db):
        """Test message broadcasting functionality."""
        # Create multiple connections for the same user
        connection_ids = []
        websockets = []
        
        with patch('app.services.enhanced_websocket_manager.ConnectionManager') as mock_base:
            mock_base_instance = mock_base.return_value
            mock_base_instance.authenticate_connection = AsyncMock(return_value=mock_user)
            
            for i in range(3):
                websocket = MockWebSocket()
                connection_id = await connection_manager.connect(websocket)
                await connection_manager.authenticate_connection(connection_id, "test-token", mock_db)
                connection_ids.append(connection_id)
                websockets.append(websocket)
            
            # Broadcast to user
            message = {"type": "broadcast", "data": {"content": "broadcast message"}}
            sent_count = await connection_manager.broadcast_to_user(str(mock_user.id), message)
            
            assert sent_count == 3
            
            # Check all websockets received the message
            for websocket in websockets:
                assert len(websocket.messages_sent) == 2  # Welcome + broadcast
                broadcast_msg = json.loads(websocket.messages_sent[1])
                assert broadcast_msg["type"] == "broadcast"
    
    @pytest.mark.asyncio
    async def test_connection_stats(self, connection_manager, mock_websocket, mock_user, mock_db):
        """Test connection statistics."""
        # Initial stats
        stats = connection_manager.get_connection_stats()
        assert stats["total_connections"] == 0
        assert stats["authenticated_connections"] == 0
        
        # Add connection
        connection_id = await connection_manager.connect(mock_websocket)
        
        stats = connection_manager.get_connection_stats()
        assert stats["total_connections"] == 1
        assert stats["authenticated_connections"] == 0
        
        # Authenticate connection
        with patch('app.services.enhanced_websocket_manager.ConnectionManager') as mock_base:
            mock_base_instance = mock_base.return_value
            mock_base_instance.authenticate_connection = AsyncMock(return_value=mock_user)
            
            await connection_manager.authenticate_connection(connection_id, "test-token", mock_db)
            
            stats = connection_manager.get_connection_stats()
            assert stats["authenticated_connections"] == 1
            assert stats["user_connections"] == 1
    
    @pytest.mark.asyncio
    async def test_heartbeat_integration(self, connection_manager, mock_websocket):
        """Test heartbeat system integration."""
        connection_id = await connection_manager.connect(mock_websocket)
        
        # Check heartbeat registration
        assert connection_id in connection_manager.heartbeat_manager.connection_metrics
        
        # Send ping
        success = await connection_manager.ping_connection(connection_id)
        assert success
        
        # Check heartbeat metrics
        metrics = connection_manager.heartbeat_manager.get_connection_health(connection_id)
        assert metrics is not None
        assert metrics.ping_count > 0
        
        # Simulate pong
        await connection_manager.handle_pong(connection_id, "test-ping-id")
        
        metrics = connection_manager.heartbeat_manager.get_connection_health(connection_id)
        assert metrics.pong_count > 0
        assert metrics.missed_pings == 0


class TestWebSocketHeartbeatManager:
    """Test WebSocket heartbeat manager."""
    
    @pytest.mark.asyncio
    async def test_heartbeat_lifecycle(self, heartbeat_manager):
        """Test heartbeat manager lifecycle."""
        await heartbeat_manager.start()
        assert heartbeat_manager._running
        
        await heartbeat_manager.stop()
        assert not heartbeat_manager._running
    
    def test_connection_registration(self, heartbeat_manager):
        """Test connection registration and unregistration."""
        connection_id = "test-connection"
        
        # Register connection
        heartbeat_manager.register_connection(connection_id)
        assert connection_id in heartbeat_manager.connection_metrics
        
        metrics = heartbeat_manager.connection_metrics[connection_id]
        assert metrics.connection_id == connection_id
        assert metrics.status == HeartbeatStatus.HEALTHY
        
        # Unregister connection
        heartbeat_manager.unregister_connection(connection_id)
        assert connection_id not in heartbeat_manager.connection_metrics
    
    @pytest.mark.asyncio
    async def test_ping_pong_cycle(self, heartbeat_manager):
        """Test ping/pong cycle."""
        connection_id = "test-connection"
        heartbeat_manager.register_connection(connection_id)
        
        # Mock send callback
        send_callback = AsyncMock(return_value=True)
        
        # Send ping
        success = await heartbeat_manager.send_ping(connection_id, send_callback)
        assert success
        
        # Check metrics
        metrics = heartbeat_manager.connection_metrics[connection_id]
        assert metrics.ping_count == 1
        assert metrics.last_ping_sent is not None
        
        # Get ping ID from the call
        call_args = send_callback.call_args
        ping_message = call_args[0][1]
        ping_id = ping_message["data"]["ping_id"]
        
        # Handle pong
        success = heartbeat_manager.handle_pong(connection_id, ping_id)
        assert success
        
        # Check updated metrics
        assert metrics.pong_count == 1
        assert metrics.missed_pings == 0
        assert metrics.last_pong_received is not None
        assert len(metrics.latency_samples) > 0
    
    @pytest.mark.asyncio
    async def test_missed_ping_handling(self, heartbeat_manager):
        """Test handling of missed pings."""
        connection_id = "test-connection"
        heartbeat_manager.register_connection(connection_id)
        
        # Mock send callback that fails
        send_callback = AsyncMock(return_value=False)
        
        # Send multiple failed pings
        for i in range(3):
            await heartbeat_manager.send_ping(connection_id, send_callback)
        
        metrics = heartbeat_manager.connection_metrics[connection_id]
        assert metrics.missed_pings == 3
        assert metrics.status == HeartbeatStatus.DEAD
    
    def test_health_summary(self, heartbeat_manager):
        """Test health summary generation."""
        # Register multiple connections with different states
        connections = ["conn1", "conn2", "conn3", "conn4"]
        for conn_id in connections:
            heartbeat_manager.register_connection(conn_id)
        
        # Set different states
        heartbeat_manager.connection_metrics["conn1"].status = HeartbeatStatus.HEALTHY
        heartbeat_manager.connection_metrics["conn2"].status = HeartbeatStatus.WARNING
        heartbeat_manager.connection_metrics["conn3"].status = HeartbeatStatus.CRITICAL
        heartbeat_manager.connection_metrics["conn4"].status = HeartbeatStatus.DEAD
        
        summary = heartbeat_manager.get_health_summary()
        
        assert summary["total_connections"] == 4
        assert summary["healthy_connections"] == 1
        assert summary["warning_connections"] == 1
        assert summary["critical_connections"] == 1
        assert summary["dead_connections"] == 1
    
    @pytest.mark.asyncio
    async def test_ping_timeout_handling(self, heartbeat_manager):
        """Test ping timeout detection."""
        connection_id = "test-connection"
        heartbeat_manager.register_connection(connection_id)
        
        # Mock send callback
        send_callback = AsyncMock(return_value=True)
        
        # Send ping
        await heartbeat_manager.send_ping(connection_id, send_callback)
        
        # Wait for timeout (longer than heartbeat_timeout)
        await asyncio.sleep(0.6)
        
        # Perform cleanup to trigger timeout handling
        await heartbeat_manager._perform_cleanup()
        
        # Check that timeout was recorded
        assert heartbeat_manager.total_timeouts > 0


class TestEnhancedWebSocketManager:
    """Test enhanced WebSocket manager singleton."""
    
    def test_singleton_pattern(self):
        """Test singleton pattern implementation."""
        manager1 = EnhancedWebSocketManager.get_instance()
        manager2 = EnhancedWebSocketManager.get_instance()
        
        assert manager1 is manager2
    
    @pytest.mark.asyncio
    async def test_manager_lifecycle(self):
        """Test manager start/stop lifecycle."""
        manager = EnhancedWebSocketManager.get_instance()
        
        await manager.start()
        assert manager.is_running
        
        await manager.stop()
        assert not manager.is_running
    
    @pytest.mark.asyncio
    async def test_delegation_methods(self):
        """Test that manager properly delegates to connection manager."""
        manager = EnhancedWebSocketManager.get_instance()
        
        # Mock the connection manager
        mock_connection_manager = Mock()
        mock_connection_manager.connect = AsyncMock(return_value="test-id")
        mock_connection_manager.disconnect = AsyncMock()
        mock_connection_manager.get_connection_stats = Mock(return_value={})
        
        manager.connection_manager = mock_connection_manager
        
        # Test delegation
        mock_websocket = MockWebSocket()
        connection_id = await manager.connect(mock_websocket)
        assert connection_id == "test-id"
        mock_connection_manager.connect.assert_called_once_with(mock_websocket, None)
        
        await manager.disconnect(connection_id)
        mock_connection_manager.disconnect.assert_called_once_with(connection_id, "Client disconnect")
        
        stats = manager.get_connection_stats()
        mock_connection_manager.get_connection_stats.assert_called_once()


class TestConnectionInfo:
    """Test ConnectionInfo dataclass."""
    
    def test_connection_info_creation(self):
        """Test ConnectionInfo creation and defaults."""
        mock_websocket = MockWebSocket()
        
        info = ConnectionInfo(
            connection_id="test-id",
            websocket=mock_websocket
        )
        
        assert info.connection_id == "test-id"
        assert info.websocket == mock_websocket
        assert info.state == ConnectionState.CONNECTING
        assert not info.authenticated
        assert info.ping_count == 0
        assert info.pong_count == 0
        assert info.missed_pings == 0
        assert isinstance(info.connected_at, datetime)
        assert isinstance(info.last_ping, datetime)
        assert isinstance(info.last_pong, datetime)


class TestConnectionState:
    """Test ConnectionState enum."""
    
    def test_connection_states(self):
        """Test all connection states are defined."""
        expected_states = [
            "connecting", "connected", "authenticated", 
            "disconnecting", "disconnected", "error"
        ]
        
        for state in expected_states:
            assert hasattr(ConnectionState, state.upper())
            assert getattr(ConnectionState, state.upper()).value == state


@pytest.mark.asyncio
async def test_integration_websocket_with_heartbeat():
    """Integration test for WebSocket manager with heartbeat system."""
    manager = EnhancedWebSocketConnectionManager(
        heartbeat_interval=0.1,  # Very fast for testing
        heartbeat_timeout=0.05,
        max_missed_pings=2
    )
    
    await manager.start()
    
    try:
        # Create connection
        mock_websocket = MockWebSocket()
        connection_id = await manager.connect(mock_websocket)
        
        # Wait for heartbeat cycle
        await asyncio.sleep(0.2)
        
        # Check that pings were sent
        assert len(mock_websocket.messages_sent) > 1  # Welcome + ping messages
        
        # Check heartbeat metrics
        heartbeat_stats = manager.get_heartbeat_stats()
        assert heartbeat_stats["total_pings_sent"] > 0
        
        # Get connection heartbeat info
        heartbeat_info = manager.get_connection_heartbeat_info(connection_id)
        assert heartbeat_info is not None
        assert heartbeat_info["ping_count"] > 0
        
    finally:
        await manager.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])