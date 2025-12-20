"""
Unit tests for UnifiedWebSocketConnectionManager.

Tests cover:
- Connection lifecycle (connect, disconnect)
- Authentication (Firebase, JWT, auto-fallback)
- Room management
- Message broadcasting
- Heartbeat monitoring
- Cleanup operations
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.services.websocket import (
    UnifiedWebSocketConnectionManager,
    ConnectionState,
    ConnectionInfo,
    get_websocket_manager
)


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    ws = AsyncMock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def manager():
    """Create a fresh WebSocket manager instance for each test."""
    # Create new instance (not singleton)
    return UnifiedWebSocketConnectionManager()


@pytest.mark.asyncio
class TestConnectionLifecycle:
    """Test connection establishment and cleanup."""

    async def test_connect_accepts_websocket(self, manager, mock_websocket):
        """Test that connect() accepts the WebSocket connection."""
        connection_id = "test-connection-1"

        result = await manager.connect(mock_websocket, connection_id)

        assert result == connection_id
        mock_websocket.accept.assert_called_once()
        assert connection_id in manager.connections
        assert connection_id in manager.connection_info

    async def test_connect_creates_connection_info(self, manager, mock_websocket):
        """Test that connection info is created with correct initial state."""
        connection_id = "test-connection-2"

        await manager.connect(mock_websocket, connection_id)

        conn_info = manager.connection_info[connection_id]
        assert isinstance(conn_info, ConnectionInfo)
        assert conn_info.connection_id == connection_id
        assert conn_info.state == ConnectionState.CONNECTED
        assert conn_info.user_id is None
        assert conn_info.role is None
        assert isinstance(conn_info.connected_at, datetime)

    async def test_disconnect_removes_connection(self, manager, mock_websocket):
        """Test that disconnect() properly cleans up connection."""
        connection_id = "test-connection-3"

        await manager.connect(mock_websocket, connection_id)
        await manager.disconnect(connection_id)

        assert connection_id not in manager.connections
        assert connection_id not in manager.connection_info

    async def test_disconnect_with_reason(self, manager, mock_websocket):
        """Test disconnect with a specific reason."""
        connection_id = "test-connection-4"

        await manager.connect(mock_websocket, connection_id)
        await manager.disconnect(connection_id, reason="Test shutdown")

        assert connection_id not in manager.connections


@pytest.mark.asyncio
class TestAuthentication:
    """Test authentication methods."""

    async def test_authenticate_connection_firebase(self, manager, mock_websocket, mock_db):
        """Test Firebase authentication."""
        connection_id = "test-auth-1"
        token = "valid-firebase-token"

        with patch('app.services.websocket.connection_manager.verify_firebase_token') as mock_verify:
            mock_user = Mock()
            mock_user.id = "user-123"
            mock_user.email = "test@example.com"
            mock_user.role = "doctor"
            mock_verify.return_value = {"uid": "firebase-uid-123"}

            # Mock database query
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user

            await manager.connect(mock_websocket, connection_id)
            user = await manager.authenticate_connection(connection_id, token, mock_db, auth_type="firebase")

            assert user is not None
            conn_info = manager.connection_info[connection_id]
            assert conn_info.state == ConnectionState.AUTHENTICATED
            assert conn_info.user_id == "user-123"

    async def test_authenticate_connection_jwt(self, manager, mock_websocket, mock_db):
        """Test JWT authentication."""
        connection_id = "test-auth-2"
        token = "valid-jwt-token"

        with patch('app.services.websocket.connection_manager.decode_jwt') as mock_decode:
            mock_user = Mock()
            mock_user.id = "user-456"
            mock_user.email = "jwt@example.com"
            mock_user.role = "admin"
            mock_decode.return_value = {"user_id": "user-456"}

            mock_db.query.return_value.filter.return_value.first.return_value = mock_user

            await manager.connect(mock_websocket, connection_id)
            user = await manager.authenticate_connection(connection_id, token, mock_db, auth_type="jwt")

            assert user is not None
            conn_info = manager.connection_info[connection_id]
            assert conn_info.state == ConnectionState.AUTHENTICATED

    async def test_authenticate_auto_fallback(self, manager, mock_websocket, mock_db):
        """Test auto fallback from Firebase to JWT."""
        connection_id = "test-auth-3"
        token = "jwt-token"

        with patch('app.services.websocket.connection_manager.verify_firebase_token') as mock_firebase:
            with patch('app.services.websocket.connection_manager.decode_jwt') as mock_jwt:
                # Firebase fails
                mock_firebase.side_effect = Exception("Invalid Firebase token")

                # JWT succeeds
                mock_user = Mock()
                mock_user.id = "user-789"
                mock_jwt.return_value = {"user_id": "user-789"}
                mock_db.query.return_value.filter.return_value.first.return_value = mock_user

                await manager.connect(mock_websocket, connection_id)
                user = await manager.authenticate_connection(connection_id, token, mock_db, auth_type="auto")

                # Should fall back to JWT
                assert user is not None
                mock_firebase.assert_called_once()
                mock_jwt.assert_called_once()


@pytest.mark.asyncio
class TestRoomManagement:
    """Test room management functionality."""

    async def test_join_patient_room(self, manager, mock_websocket):
        """Test joining a patient room."""
        connection_id = "test-room-1"
        patient_id = "patient-123"

        await manager.connect(mock_websocket, connection_id)
        # Simulate authentication
        manager.connection_info[connection_id].state = ConnectionState.AUTHENTICATED
        manager.connection_info[connection_id].user_id = "user-1"

        result = await manager.join_patient_room(connection_id, patient_id)

        assert result is True
        assert patient_id in manager.patient_rooms
        assert connection_id in manager.patient_rooms[patient_id]

    async def test_join_room_requires_authentication(self, manager, mock_websocket):
        """Test that joining room requires authentication."""
        connection_id = "test-room-2"
        patient_id = "patient-456"

        await manager.connect(mock_websocket, connection_id)
        # Don't authenticate

        result = await manager.join_patient_room(connection_id, patient_id)

        assert result is False

    async def test_leave_patient_room(self, manager, mock_websocket):
        """Test leaving a patient room."""
        connection_id = "test-room-3"
        patient_id = "patient-789"

        await manager.connect(mock_websocket, connection_id)
        manager.connection_info[connection_id].state = ConnectionState.AUTHENTICATED
        manager.connection_info[connection_id].user_id = "user-2"

        await manager.join_patient_room(connection_id, patient_id)
        await manager.leave_patient_room(connection_id, patient_id)

        assert connection_id not in manager.patient_rooms.get(patient_id, set())


@pytest.mark.asyncio
class TestMessaging:
    """Test message sending functionality."""

    async def test_send_message(self, manager, mock_websocket):
        """Test sending a message to a connection."""
        connection_id = "test-msg-1"
        message = {"type": "test", "data": "hello"}

        await manager.connect(mock_websocket, connection_id)
        result = await manager.send_message(connection_id, message)

        assert result is True
        mock_websocket.send_json.assert_called_once_with(message)

    async def test_broadcast_to_patient_room(self, manager, mock_websocket):
        """Test broadcasting to a patient room."""
        patient_id = "patient-broadcast-1"
        message = {"type": "update", "data": "patient updated"}

        # Create multiple connections in same room
        conn1 = await manager.connect(AsyncMock(spec=WebSocket), "conn-1")
        conn2 = await manager.connect(AsyncMock(spec=WebSocket), "conn-2")

        manager.connection_info[conn1].state = ConnectionState.AUTHENTICATED
        manager.connection_info[conn2].state = ConnectionState.AUTHENTICATED

        await manager.join_patient_room(conn1, patient_id)
        await manager.join_patient_room(conn2, patient_id)

        count = await manager.broadcast_to_patient_room(patient_id, message)

        assert count == 2

    async def test_broadcast_to_user(self, manager, mock_websocket):
        """Test broadcasting to all user connections."""
        user_id = "user-multi-device"
        message = {"type": "notification", "data": "new message"}

        # Create multiple connections for same user
        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)

        conn1 = await manager.connect(ws1, "device-1")
        conn2 = await manager.connect(ws2, "device-2")

        manager.connection_info[conn1].user_id = user_id
        manager.connection_info[conn1].state = ConnectionState.AUTHENTICATED
        manager.connection_info[conn2].user_id = user_id
        manager.connection_info[conn2].state = ConnectionState.AUTHENTICATED

        count = await manager.broadcast_to_user(user_id, message)

        assert count == 2
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()


@pytest.mark.asyncio
class TestHeartbeat:
    """Test heartbeat monitoring."""

    async def test_ping_connection(self, manager, mock_websocket):
        """Test sending ping to connection."""
        connection_id = "test-ping-1"

        await manager.connect(mock_websocket, connection_id)
        ping_id = await manager.ping_connection(connection_id)

        assert ping_id is not None
        mock_websocket.send_json.assert_called_once()

    async def test_handle_pong_updates_heartbeat(self, manager, mock_websocket):
        """Test that pong updates last heartbeat time."""
        connection_id = "test-pong-1"

        await manager.connect(mock_websocket, connection_id)
        initial_heartbeat = manager.connection_info[connection_id].last_heartbeat

        # Wait a bit
        await asyncio.sleep(0.1)

        ping_id = await manager.ping_connection(connection_id)
        await manager.handle_pong(connection_id, ping_id, datetime.utcnow().timestamp())

        updated_heartbeat = manager.connection_info[connection_id].last_heartbeat
        assert updated_heartbeat > initial_heartbeat


@pytest.mark.asyncio
class TestCleanup:
    """Test cleanup operations."""

    async def test_cleanup_stale_connections(self, manager, mock_websocket):
        """Test that stale connections are cleaned up."""
        connection_id = "test-cleanup-1"

        await manager.connect(mock_websocket, connection_id)

        # Make connection stale by setting old heartbeat
        manager.connection_info[connection_id].last_heartbeat = (
            datetime.utcnow() - timedelta(seconds=manager.heartbeat_interval * 3)
        )

        # Run cleanup
        await manager._cleanup_stale_connections()

        assert connection_id not in manager.connections


@pytest.mark.asyncio
class TestLifecycle:
    """Test lifecycle management."""

    async def test_start_initializes_background_tasks(self, manager):
        """Test that start() creates background tasks."""
        await manager.start()

        assert manager._started is True
        assert len(manager._background_tasks) > 0

    async def test_stop_cancels_background_tasks(self, manager):
        """Test that stop() cancels all background tasks."""
        await manager.start()
        initial_task_count = len(manager._background_tasks)

        await manager.stop()

        assert manager._started is False
        # Tasks should be cancelled
        for task in manager._background_tasks:
            assert task.cancelled() or task.done()


def test_get_websocket_manager_returns_singleton():
    """Test that get_websocket_manager returns the same instance."""
    manager1 = get_websocket_manager()
    manager2 = get_websocket_manager()

    assert manager1 is manager2


@pytest.mark.asyncio
class TestConnectionStats:
    """Test connection statistics."""

    async def test_get_connection_stats(self, manager, mock_websocket):
        """Test getting connection statistics."""
        # Create multiple connections
        await manager.connect(AsyncMock(spec=WebSocket), "conn-1")
        await manager.connect(AsyncMock(spec=WebSocket), "conn-2")

        stats = manager.get_connection_stats()

        assert stats["total_connections"] == 2
        assert "connections_by_state" in stats
        assert "uptime" in stats
