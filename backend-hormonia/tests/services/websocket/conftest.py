"""
Pytest configuration and shared fixtures for WebSocket tests.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.services.websocket import UnifiedWebSocketConnectionManager


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection with common methods."""
    ws = AsyncMock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.close = AsyncMock()
    ws.client_state = "CONNECTED"
    return ws


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = Mock(spec=Session)
    session.query = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.close = Mock()
    return session


@pytest.fixture
async def websocket_manager():
    """
    Create a fresh WebSocket manager for testing.

    Note: This creates a new instance, not the singleton,
    to ensure test isolation.
    """
    manager = UnifiedWebSocketConnectionManager()
    yield manager

    # Cleanup after test
    if manager._started:
        await manager.stop()

    # Disconnect all connections
    for conn_id in list(manager.connections.keys()):
        await manager.disconnect(conn_id)


@pytest.fixture
def mock_user():
    """Create a mock user object."""
    user = Mock()
    user.id = "test-user-id"
    user.email = "test@example.com"
    user.role = "doctor"
    user.is_active = True
    user.firebase_uid = "firebase-test-uid"
    return user


@pytest.fixture
def mock_patient():
    """Create a mock patient object."""
    patient = Mock()
    patient.id = "test-patient-id"
    patient.cpf = "12345678900"
    patient.full_name = "Test Patient"
    patient.is_active = True
    return patient
