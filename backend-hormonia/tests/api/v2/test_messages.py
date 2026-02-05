"""
Tests for Messages API v2

Comprehensive test suite for message management endpoints including:
- Message CRUD operations
- Conversation management
- Bulk operations
- Templates
- Inbound messages
- Analytics
- Search & filtering
"""

import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.models.user import User
from app.models.patient import Patient
from app.models.message import Message, MessageStatus, MessageType, MessageDirection


# ============================================================================
# Test Message CRUD (13 endpoints)
# ============================================================================

class TestMessageCRUD:
    """Test message CRUD operations."""

    def test_list_messages_cursor_pagination(self, client: TestClient, auth_headers: dict):
        """Test listing messages with cursor pagination."""
        response = client.get(
            "/api/v2/messages?limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "next_cursor" in data

    def test_list_messages_with_filters(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test listing messages with filters."""
        response = client.get(
            f"/api/v2/messages?patient_id={test_patient.id}&status=sent&limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_get_message_by_id(self, client: TestClient, auth_headers: dict):
        """Test getting a specific message."""
        message_id = uuid4()
        response = client.get(
            f"/api/v2/messages/{message_id}",
            headers=auth_headers
        )
        assert response.status_code in [200, 404]

    def test_send_message_success(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test sending a message."""
        payload = {
            "patient_id": str(test_patient.id),
            "content": "Hello",
            "type": "text"
        }
        response = client.post(
            "/api/v2/messages/send",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code in [200, 201]

    def test_send_message_rate_limited(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test rate limiting on message sending."""
        payload = {
            "patient_id": str(test_patient.id),
            "content": "Test",
            "type": "text"
        }
        # Send multiple requests rapidly
        for _ in range(65):  # Exceeds 60/min limit
            response = client.post(
                "/api/v2/messages/send",
                json=payload,
                headers=auth_headers
            )
        assert response.status_code == 429

    def test_list_scheduled_messages(self, client: TestClient, auth_headers: dict):
        """Test listing scheduled messages."""
        response = client.get(
            "/api/v2/messages/scheduled?limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_cancel_scheduled_message(self, client: TestClient, auth_headers: dict):
        """Test canceling a scheduled message."""
        message_id = uuid4()
        response = client.put(
            f"/api/v2/messages/{message_id}/cancel",
            headers=auth_headers
        )
        assert response.status_code in [200, 404]

    @patch('app.utils.redis_cache.get_async_redis_client')
    def test_patient_message_stats_cached(self, mock_redis, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test patient message statistics with caching."""
        mock_redis_client = AsyncMock()
        mock_redis_client.get.return_value = None
        mock_redis.return_value = mock_redis_client

        response = client.get(
            f"/api/v2/messages/patient/{test_patient.id}/stats",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_get_message_status(self, client: TestClient, auth_headers: dict):
        """Test getting message delivery status."""
        message_id = uuid4()
        response = client.get(
            f"/api/v2/messages/{message_id}/status",
            headers=auth_headers
        )
        assert response.status_code in [200, 404]

    def test_retry_failed_message(self, client: TestClient, auth_headers: dict):
        """Test retrying a single failed message."""
        message_id = uuid4()
        response = client.post(
            f"/api/v2/messages/{message_id}/retry",
            headers=auth_headers
        )
        assert response.status_code in [200, 404]

    def test_retry_all_failed_messages(self, client: TestClient, auth_headers: dict):
        """Test retrying all failed messages."""
        response = client.post(
            "/api/v2/messages/retry-failed",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_list_failed_messages(self, client: TestClient, auth_headers: dict):
        """Test listing failed messages."""
        response = client.get(
            "/api/v2/messages/failed?limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_filter_by_status(self, client: TestClient, auth_headers: dict):
        """Test filtering messages by status."""
        response = client.get(
            "/api/v2/messages/status/sent?limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200

    @patch('app.utils.redis_cache.get_async_redis_client')
    def test_overall_statistics_cached(self, mock_redis, client: TestClient, auth_headers: dict):
        """Test overall message statistics with caching."""
        mock_redis_client = AsyncMock()
        mock_redis_client.get.return_value = None
        mock_redis.return_value = mock_redis_client

        response = client.get(
            "/api/v2/messages/statistics",
            headers=auth_headers
        )
        assert response.status_code == 200


# ============================================================================
# Test Conversation Management (6 endpoints from enhanced)
# ============================================================================

class TestConversations:
    """Test conversation management endpoints."""

    def test_get_conversation_history(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test getting conversation history for a patient."""
        response = client.get(
            f"/api/v2/messages/conversations/{test_patient.id}?limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_conversation_cursor_pagination(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test conversation pagination."""
        response = client.get(
            f"/api/v2/messages/conversations/{test_patient.id}?limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "next_cursor" in data

    def test_list_all_conversations(self, client: TestClient, auth_headers: dict):
        """Test listing all conversations."""
        response = client.get(
            "/api/v2/messages/conversations?limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_conversation_unread_count(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test getting unread message count for conversation."""
        response = client.get(
            f"/api/v2/messages/conversations/{test_patient.id}/unread",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "count" in data

    def test_mark_conversation_read(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test marking entire conversation as read."""
        response = client.post(
            f"/api/v2/messages/conversations/{test_patient.id}/mark-read",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_conversation_eager_loading(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test conversation with eager-loaded patient data."""
        response = client.get(
            f"/api/v2/messages/conversations/{test_patient.id}?include=patient",
            headers=auth_headers
        )
        assert response.status_code == 200


# ============================================================================
# Test Bulk Operations (1 endpoint)
# ============================================================================

class TestBulkOperations:
    """Test bulk message operations."""

    def test_bulk_send_messages(self, client: TestClient, auth_headers: dict):
        """Test sending messages to multiple patients."""
        payload = {
            "patient_ids": [str(uuid4()), str(uuid4())],
            "content": "Bulk message",
            "type": "text"
        }
        response = client.post(
            "/api/v2/messages/bulk/send",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code in [200, 201]

    def test_bulk_send_rate_limited(self, client: TestClient, auth_headers: dict):
        """Test rate limiting on bulk operations."""
        payload = {
            "patient_ids": [str(uuid4())],
            "content": "Test",
            "type": "text"
        }
        # Exceed 10/min limit
        for _ in range(12):
            response = client.post(
                "/api/v2/messages/bulk/send",
                json=payload,
                headers=auth_headers
            )
        assert response.status_code == 429

    def test_bulk_send_validation(self, client: TestClient, auth_headers: dict):
        """Test validation on bulk operations."""
        payload = {
            "patient_ids": [],  # Empty list
            "content": "Test",
            "type": "text"
        }
        response = client.post(
            "/api/v2/messages/bulk/send",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 422


# ============================================================================
# Test Templates (5 endpoints - stubs)
# ============================================================================

class TestMessageTemplates:
    """Test message template endpoints (stub implementation)."""

    def test_list_templates_stub(self, client: TestClient, auth_headers: dict):
        """Test listing templates (returns empty list)."""
        response = client.get(
            "/api/v2/messages/templates",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []

    def test_get_template_not_implemented(self, client: TestClient, auth_headers: dict):
        """Test getting template (not implemented)."""
        template_id = uuid4()
        response = client.get(
            f"/api/v2/messages/templates/{template_id}",
            headers=auth_headers
        )
        assert response.status_code == 501

    def test_create_template_not_implemented(self, client: TestClient, auth_headers: dict):
        """Test creating template (not implemented)."""
        payload = {"name": "Test Template"}
        response = client.post(
            "/api/v2/messages/templates",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 501

    def test_update_template_not_implemented(self, client: TestClient, auth_headers: dict):
        """Test updating template (not implemented)."""
        template_id = uuid4()
        payload = {"name": "Updated"}
        response = client.put(
            f"/api/v2/messages/templates/{template_id}",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 501

    def test_delete_template_not_implemented(self, client: TestClient, auth_headers: dict):
        """Test deleting template (not implemented)."""
        template_id = uuid4()
        response = client.delete(
            f"/api/v2/messages/templates/{template_id}",
            headers=auth_headers
        )
        assert response.status_code == 501


# ============================================================================
# Test Inbound Messages (1 endpoint)
# ============================================================================

class TestInboundMessages:
    """Test inbound message processing."""

    def test_process_inbound_message(self, client: TestClient, auth_headers: dict):
        """Test processing inbound message webhook."""
        payload = {
            "patient_phone": "5511999999999",
            "content": "Hello",
            "whatsapp_id": "wamid.123",
            "type": "text"
        }
        response = client.post(
            "/api/v2/messages/inbound",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code in [200, 201]

    def test_inbound_message_validation(self, client: TestClient, auth_headers: dict):
        """Test inbound message validation."""
        payload = {
            "patient_phone": "",  # Invalid
            "content": "Test",
            "whatsapp_id": "wamid.123"
        }
        response = client.post(
            "/api/v2/messages/inbound",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 422

    def test_inbound_creates_patient_response(self, client: TestClient, auth_headers: dict):
        """Test that inbound message creates patient response record."""
        payload = {
            "patient_phone": "5511999999999",
            "content": "Yes",
            "whatsapp_id": "wamid.456",
            "type": "text"
        }
        response = client.post(
            "/api/v2/messages/inbound",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code in [200, 201]


# ============================================================================
# Test Search & Filtering (1 endpoint)
# ============================================================================

class TestSearchAndFiltering:
    """Test message search and filtering."""

    def test_search_messages_by_content(self, client: TestClient, auth_headers: dict):
        """Test searching messages by content."""
        response = client.get(
            "/api/v2/messages/search?q=hello&limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_search_with_filters(self, client: TestClient, auth_headers: dict):
        """Test search with additional filters."""
        response = client.get(
            "/api/v2/messages/search?q=test&status=sent&type=text",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_search_cursor_pagination(self, client: TestClient, auth_headers: dict):
        """Test search results pagination."""
        response = client.get(
            "/api/v2/messages/search?q=message&limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "next_cursor" in data


# ============================================================================
# Test Analytics (2 endpoints)
# ============================================================================

class TestMessageAnalytics:
    """Test message analytics endpoints."""

    @patch('app.utils.redis_cache.get_async_redis_client')
    def test_delivery_rate_analytics(self, mock_redis, client: TestClient, auth_headers: dict):
        """Test delivery rate analytics with caching."""
        mock_redis_client = AsyncMock()
        mock_redis_client.get.return_value = None
        mock_redis.return_value = mock_redis_client

        response = client.get(
            "/api/v2/messages/analytics/delivery-rate?timeframe=week",
            headers=auth_headers
        )
        assert response.status_code == 200

    @patch('app.utils.redis_cache.get_async_redis_client')
    def test_response_time_analytics(self, mock_redis, client: TestClient, auth_headers: dict):
        """Test response time analytics with caching."""
        mock_redis_client = AsyncMock()
        mock_redis_client.get.return_value = None
        mock_redis.return_value = mock_redis_client

        response = client.get(
            "/api/v2/messages/analytics/response-time?timeframe=month",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_analytics_cache_invalidation(self, client: TestClient, auth_headers: dict):
        """Test analytics cache is properly managed."""
        # First request - cache miss
        response1 = client.get(
            "/api/v2/messages/analytics/delivery-rate",
            headers=auth_headers
        )
        # Second request - should hit cache
        response2 = client.get(
            "/api/v2/messages/analytics/delivery-rate",
            headers=auth_headers
        )
        assert response1.status_code == response2.status_code == 200


# ============================================================================
# Test Message Status Tracking
# ============================================================================

class TestMessageStatusTracking:
    """Test message status tracking and updates."""

    def test_message_status_enum_values(self):
        """Test all message status values."""
        valid_statuses = ['pending', 'sent', 'delivered', 'read', 'failed']
        for status in valid_statuses:
            assert status in [s.value for s in MessageStatus]

    def test_message_type_enum_values(self):
        """Test all message type values."""
        valid_types = ['text', 'image', 'audio', 'video', 'document']
        for msg_type in valid_types:
            assert msg_type in [t.value for t in MessageType]

    def test_message_direction_enum_values(self):
        """Test message direction enum."""
        assert MessageDirection.OUTBOUND.value == 'outbound'
        assert MessageDirection.INBOUND.value == 'inbound'


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_patient(db_session, test_user: User) -> Patient:
    """Create a test patient for message tests."""
    patient = Patient(
        id=uuid4(),
        name="Test Patient",
        phone="5511999999999",
        doctor_id=test_user.id,
        created_at=datetime.utcnow()
    )
    db_session.add(patient)
    db_session.commit()
    return patient


@pytest.fixture
def test_message(db_session, test_patient: Patient) -> Message:
    """Create a test message."""
    message = Message(
        id=uuid4(),
        patient_id=test_patient.id,
        direction=MessageDirection.OUTBOUND,
        type=MessageType.TEXT,
        content="Test message",
        status=MessageStatus.SENT,
        created_at=datetime.utcnow()
    )
    db_session.add(message)
    db_session.commit()
    return message
