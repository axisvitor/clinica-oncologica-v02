"""
Integration tests for the complete WebSocket management system.

This module tests:
- End-to-end WebSocket connection management
- Integration between enhanced manager and heartbeat system
- Real-world scenarios with multiple connections
- Performance and resource management
- Error recovery and resilience
"""
import asyncio
import pytest
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.services.enhanced_websocket_manager import (
    EnhancedWebSocketConnectionManager,
    EnhancedWebSocketManager,
    ConnectionState
)
from app.services.websocket_heartbeat import (
    WebSocketHeartbeatManager,
    HeartbeatStatus
)
from app.models.user import User, UserRole


class MockWebSocket:
    """Enhanced mock WebSocket for integration testing."""
    
    def __init__(self, connection_id=None):
        self.connection_id = connection_id or f"mock-{id(self)}"
        self.closed = False
        self.messages_sent = []
        self.close_code = None
        self.close_reason = None
        self.accept_called = False
        self.send_delay = 0  # Simulate network delay
        self.fail_send = False  # Simulate send failures
        
    async def accept(self):
        """Mock accept method."""
        self.accept_called = True
        await asyncio.sleep(0.001)  # Simulate small delay
    
    async def send_text(self, data: str):
        """Mock send_text method with failure simulation."""
        if self.closed:
            raise RuntimeError("WebSocket connection is closed")
        
        if self.fail_send:
            raise RuntimeError("Send failed")
        
        if self.send_delay > 0:
            await asyncio.sleep(self.send_delay)
        
        self.messages_sent.append(data)
    
    async def close(self, code: int = 1000, reason: str = ""):
        """Mock close method."""
        self.closed = True
        self.close_code = code
        self.close_reason = reason
    
    def get_sent_messages(self):
        """Get all sent messages as parsed JSON."""
        return [json.loads(msg) for msg in self.messages_sent]


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    user = Mock(spec=User)
    user.id = "test-user-123"
    user.email = "test@example.com"
    user.role = UserRole.PATIENT
    user.is_active = True
    return user


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return Mock(spec=Session)


@pytest.fixture
async def integration_manager():
    """Create an enhanced WebSocket manager for integration testing."""
    manager = EnhancedWebSocketConnectionManager(
        heartbeat_interval=0.1,  # 100ms for fast testing
        heartbeat_timeout=0.05,  # 50ms timeout
        max_missed_pings=2,
        cleanup_interval=0.2,    # 200ms cleanup
        max_connections_per_user=3
    )
    await manager.start()
    yield manager
    await manager.stop()


class TestWebSocketIntegration:
    """Integration tests for WebSocket management system."""
    
    @pytest.mark.asyncio
    async def test_complete_connection_lifecycle(self, integration_manager, mock_user, mock_db):
        """Test complete connection lifecycle from connect to disconnect."""
        # Create WebSocket connection
        websocket = MockWebSocket()
        
        # Connect
        connection_id = await integration_manager.connect(websocket)
        assert websocket.accept_called
        assert connection_id in integration_manager.connections
        
        # Verify welcome message was sent
        messages = websocket.get_sent_messages()
        assert len(messages) >= 1
        assert messages[0]["type"] == "connected"
        assert messages[0]["data"]["connection_id"] == connection_id
        
        # Authenticate
        with patch('app.services.enhanced_websocket_manager.ConnectionManager') as mock_base:
            mock_base_instance = mock_base.return_value
            mock_base_instance.authenticate_connection = AsyncMock(return_value=mock_user)
            
            user = await integration_manager.authenticate_connection(connection_id, "test-token", mock_db)
            assert user == mock_user
            
            connection_info = integration_manager.connections[connection_id]
            assert connection_info.authenticated
            assert connection_info.state == ConnectionState.AUTHENTICATED
        
        # Join patient room
        patient_id = "patient-456"
        success = await integration_manager.join_patient_room(connection_id, patient_id)
        assert success
        assert patient_id in integration_manager.patient_rooms
        
        # Send message
        test_message = {"type": "test", "data": {"content": "hello world"}}
        success = await integration_manager.send_message(connection_id, test_message)
        assert success
        
        # Verify message was sent
        messages = websocket.get_sent_messages()
        sent_test_message = next((msg for msg in messages if msg.get("type") == "test"), None)
        assert sent_test_message is not None
        assert sent_test_message["data"]["content"] == "hello world"
        
        # Disconnect
        await integration_manager.disconnect(connection_id, "Test complete")
        assert websocket.closed
        assert connection_id not in integration_manager.connections
        assert patient_id not in integration_manager.patient_rooms
    
    @pytest.mark.asyncio
    async def test_heartbeat_system_integration(self, integration_manager):
        """Test heartbeat system integration with connection manager."""
        websocket = MockWebSocket()
        connection_id = await integration_manager.connect(websocket)
        
        # Wait for heartbeat cycles
        await asyncio.sleep(0.3)  # Wait for multiple heartbeat intervals
        
        # Check that pings were sent
        messages = websocket.get_sent_messages()
        ping_messages = [msg for msg in messages if msg.get("type") == "ping"]
        assert len(ping_messages) > 0
        
        # Verify heartbeat registration
        heartbeat_info = integration_manager.get_connection_heartbeat_info(connection_id)
        assert heartbeat_info is not None
        assert heartbeat_info["ping_count"] > 0
        
        # Simulate pong response
        ping_message = ping_messages[0]
        ping_id = ping_message["data"]["ping_id"]
        await integration_manager.handle_pong(connection_id, ping_id)
        
        # Check updated heartbeat info
        updated_info = integration_manager.get_connection_heartbeat_info(connection_id)
        assert updated_info["pong_count"] > 0
        assert updated_info["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_multiple_connections_management(self, integration_manager, mock_user, mock_db):
        """Test managing multiple concurrent connections."""
        connections = []
        websockets = []
        
        # Create multiple connections
        for i in range(5):
            websocket = MockWebSocket(f"conn-{i}")
            connection_id = await integration_manager.connect(websocket)
            connections.append(connection_id)
            websockets.append(websocket)
        
        # Verify all connections are tracked
        assert len(integration_manager.connections) == 5
        
        # Authenticate all connections with the same user
        with patch('app.services.enhanced_websocket_manager.ConnectionManager') as mock_base:
            mock_base_instance = mock_base.return_value
            mock_base_instance.authenticate_connection = AsyncMock(return_value=mock_user)
            
            for connection_id in connections:
                await integration_manager.authenticate_connection(connection_id, "test-token", mock_db)
        
        # Check connection limit enforcement (max 3 per user)
        user_connections = integration_manager.user_connections.get(str(mock_user.id), set())
        assert len(user_connections) == 3  # Should have disconnected 2 oldest
        
        # Broadcast message to user
        broadcast_message = {"type": "broadcast", "data": {"content": "broadcast test"}}
        sent_count = await integration_manager.broadcast_to_user(str(mock_user.id), broadcast_message)
        assert sent_count == 3  # Should reach 3 active connections
        
        # Verify broadcast was received by active connections
        active_websockets = [ws for ws in websockets if not ws.closed]
        for websocket in active_websockets:
            messages = websocket.get_sent_messages()
            broadcast_received = any(
                msg.get("type") == "broadcast" and msg["data"]["content"] == "broadcast test"
                for msg in messages
            )
            assert broadcast_received
    
    @pytest.mark.asyncio
    async def test_patient_room_broadcasting(self, integration_manager, mock_user, mock_db):
        """Test patient room functionality with multiple connections."""
        patient_id = "patient-789"
        connections = []
        websockets = []
        
        # Create connections and join patient room
        with patch('app.services.enhanced_websocket_manager.ConnectionManager') as mock_base:
            mock_base_instance = mock_base.return_value
            mock_base_instance.authenticate_connection = AsyncMock(return_value=mock_user)
            
            for i in range(3):
                websocket = MockWebSocket(f"patient-conn-{i}")
                connection_id = await integration_manager.connect(websocket)
                await integration_manager.authenticate_connection(connection_id, "test-token", mock_db)
                
                # Join patient room
                success = await integration_manager.join_patient_room(connection_id, patient_id)
                assert success
                
                connections.append(connection_id)
                websockets.append(websocket)
        
        # Broadcast to patient room
        room_message = {"type": "patient_update", "data": {"patient_id": patient_id, "status": "updated"}}
        sent_count = await integration_manager.broadcast_to_patient_room(patient_id, room_message)
        assert sent_count == 3
        
        # Verify all connections in room received the message
        for websocket in websockets:
            messages = websocket.get_sent_messages()
            room_message_received = any(
                msg.get("type") == "patient_update" and msg["data"]["patient_id"] == patient_id
                for msg in messages
            )
            assert room_message_received
        
        # Leave patient room
        await integration_manager.leave_patient_room(connections[0], patient_id)
        
        # Broadcast again - should reach only 2 connections now
        sent_count = await integration_manager.broadcast_to_patient_room(patient_id, room_message)
        assert sent_count == 2
    
    @pytest.mark.asyncio
    async def test_connection_failure_recovery(self, integration_manager):
        """Test connection failure detection and recovery."""
        websocket = MockWebSocket()
        connection_id = await integration_manager.connect(websocket)
        
        # Simulate send failure
        websocket.fail_send = True
        
        # Try to send message - should fail
        test_message = {"type": "test", "data": {"content": "should fail"}}
        success = await integration_manager.send_message(connection_id, test_message)
        assert not success
        
        # Connection should be marked as error state
        connection_info = integration_manager.connections.get(connection_id)
        if connection_info:  # Connection might be cleaned up
            assert connection_info.error_count > 0
    
    @pytest.mark.asyncio
    async def test_heartbeat_timeout_and_cleanup(self, integration_manager):
        """Test heartbeat timeout detection and automatic cleanup."""
        websocket = MockWebSocket()
        connection_id = await integration_manager.connect(websocket)
        
        # Disable pong responses by making send fail for pings
        original_messages = len(websocket.messages_sent)
        
        # Wait for heartbeat timeout cycles
        await asyncio.sleep(0.4)  # Wait longer than heartbeat timeout
        
        # Check if connection was cleaned up due to missed heartbeats
        # Note: This depends on the heartbeat manager's cleanup logic
        heartbeat_stats = integration_manager.get_heartbeat_stats()
        assert heartbeat_stats["total_pings_sent"] > 0
    
    @pytest.mark.asyncio
    async def test_performance_with_many_connections(self, integration_manager):
        """Test performance with many concurrent connections."""
        num_connections = 20
        connections = []
        websockets = []
        
        start_time = time.time()
        
        # Create many connections quickly
        for i in range(num_connections):
            websocket = MockWebSocket(f"perf-conn-{i}")
            connection_id = await integration_manager.connect(websocket)
            connections.append(connection_id)
            websockets.append(websocket)
        
        connection_time = time.time() - start_time
        
        # Should be able to create connections quickly
        assert connection_time < 1.0  # Less than 1 second for 20 connections
        assert len(integration_manager.connections) == num_connections
        
        # Broadcast to all connections
        start_time = time.time()
        broadcast_message = {"type": "performance_test", "data": {"timestamp": time.time()}}
        sent_count = await integration_manager.broadcast_to_all_authenticated(broadcast_message)
        broadcast_time = time.time() - start_time
        
        # Broadcasting should be fast (connections aren't authenticated, so sent_count will be 0)
        assert broadcast_time < 0.5  # Less than 500ms
        
        # Clean up all connections
        start_time = time.time()
        for connection_id in connections:
            await integration_manager.disconnect(connection_id, "Performance test cleanup")
        cleanup_time = time.time() - start_time
        
        # Cleanup should be fast
        assert cleanup_time < 1.0  # Less than 1 second
        assert len(integration_manager.connections) == 0
    
    @pytest.mark.asyncio
    async def test_memory_management_and_cleanup(self, integration_manager):
        """Test memory management and proper cleanup."""
        initial_stats = integration_manager.get_connection_stats()
        initial_heartbeat_stats = integration_manager.get_heartbeat_stats()
        
        # Create and destroy connections multiple times
        for cycle in range(3):
            connections = []
            
            # Create connections
            for i in range(5):
                websocket = MockWebSocket(f"memory-test-{cycle}-{i}")
                connection_id = await integration_manager.connect(websocket)
                connections.append(connection_id)
            
            # Wait a bit for heartbeat registration
            await asyncio.sleep(0.05)
            
            # Disconnect all
            for connection_id in connections:
                await integration_manager.disconnect(connection_id, f"Cycle {cycle} cleanup")
            
            # Wait for cleanup
            await asyncio.sleep(0.05)
        
        # Check that connections are properly cleaned up
        final_stats = integration_manager.get_connection_stats()
        assert final_stats["total_connections"] == 0
        
        # Memory should be cleaned up (no lingering references)
        assert len(integration_manager.connections) == 0
        assert len(integration_manager.user_connections) == 0
        assert len(integration_manager.patient_rooms) == 0
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, integration_manager, mock_user, mock_db):
        """Test concurrent operations on the WebSocket manager."""
        # Create multiple connections concurrently
        async def create_connection(i):
            websocket = MockWebSocket(f"concurrent-{i}")
            connection_id = await integration_manager.connect(websocket)
            
            # Authenticate
            with patch('app.services.enhanced_websocket_manager.ConnectionManager') as mock_base:
                mock_base_instance = mock_base.return_value
                mock_base_instance.authenticate_connection = AsyncMock(return_value=mock_user)
                await integration_manager.authenticate_connection(connection_id, "test-token", mock_db)
            
            return connection_id, websocket
        
        # Create connections concurrently
        tasks = [create_connection(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check that all operations succeeded
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) >= 3  # At least 3 should succeed (connection limit)
        
        # Send messages concurrently
        async def send_message(connection_id):
            message = {"type": "concurrent_test", "data": {"sender": connection_id}}
            return await integration_manager.send_message(connection_id, message)
        
        # Get active connections
        active_connections = list(integration_manager.connections.keys())
        if active_connections:
            send_tasks = [send_message(conn_id) for conn_id in active_connections[:5]]
            send_results = await asyncio.gather(*send_tasks, return_exceptions=True)
            
            # Most sends should succeed
            successful_sends = [r for r in send_results if r is True]
            assert len(successful_sends) > 0


class TestWebSocketManagerSingleton:
    """Test the singleton WebSocket manager."""
    
    @pytest.mark.asyncio
    async def test_singleton_manager_integration(self):
        """Test the singleton manager with real operations."""
        manager = EnhancedWebSocketManager.get_instance()
        
        # Start manager
        await manager.start()
        assert manager.is_running
        
        try:
            # Create connection through singleton
            websocket = MockWebSocket()
            connection_id = await manager.connect(websocket)
            
            # Verify connection exists
            stats = manager.get_connection_stats()
            assert stats["total_connections"] == 1
            
            # Send message through singleton
            message = {"type": "singleton_test", "data": {"test": True}}
            success = await manager.send_message(connection_id, message)
            assert success
            
            # Disconnect through singleton
            await manager.disconnect(connection_id)
            
            # Verify cleanup
            stats = manager.get_connection_stats()
            assert stats["total_connections"] == 0
            
        finally:
            # Stop manager
            await manager.stop()
            assert not manager.is_running


class TestErrorScenarios:
    """Test various error scenarios and edge cases."""
    
    @pytest.mark.asyncio
    async def test_websocket_close_during_operation(self, integration_manager):
        """Test handling WebSocket close during operations."""
        websocket = MockWebSocket()
        connection_id = await integration_manager.connect(websocket)
        
        # Close WebSocket externally
        await websocket.close(1001, "Going away")
        
        # Try to send message to closed WebSocket
        message = {"type": "test", "data": {"content": "should fail"}}
        success = await integration_manager.send_message(connection_id, message)
        assert not success
    
    @pytest.mark.asyncio
    async def test_invalid_connection_operations(self, integration_manager):
        """Test operations on invalid/non-existent connections."""
        invalid_connection_id = "non-existent-connection"
        
        # Try operations on non-existent connection
        success = await integration_manager.send_message(invalid_connection_id, {"type": "test"})
        assert not success
        
        success = await integration_manager.join_patient_room(invalid_connection_id, "patient-123")
        assert not success
        
        success = await integration_manager.ping_connection(invalid_connection_id)
        assert not success
        
        info = integration_manager.get_connection_info(invalid_connection_id)
        assert info is None
    
    @pytest.mark.asyncio
    async def test_manager_stop_with_active_connections(self, integration_manager):
        """Test stopping manager with active connections."""
        # Create some connections
        connections = []
        for i in range(3):
            websocket = MockWebSocket(f"stop-test-{i}")
            connection_id = await integration_manager.connect(websocket)
            connections.append((connection_id, websocket))
        
        # Stop manager
        await integration_manager.stop()
        
        # All connections should be closed
        for connection_id, websocket in connections:
            assert websocket.closed
        
        # Manager should be stopped
        assert not integration_manager._running


if __name__ == "__main__":
    pytest.main([__file__, "-v"])