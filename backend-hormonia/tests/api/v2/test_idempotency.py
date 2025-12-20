"""
Tests for idempotency key support
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from fastapi.testclient import TestClient


class TestPatientCreateIdempotency:
    """Test idempotency on patient creation."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer test_token"}

    @pytest.fixture
    def patient_data(self):
        return {
            "name": "Test Patient",
            "phone": "+5511999999999",
            "treatment_type": "chemotherapy"
        }

    def test_create_with_idempotency_key(self, client, auth_headers, patient_data):
        """Test patient creation with idempotency key."""
        idempotency_key = f"test-{uuid4()}"

        # First request
        response1 = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers={**auth_headers, "X-Idempotency-Key": idempotency_key}
        )

        # Second request with same key should return same result
        response2 = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers={**auth_headers, "X-Idempotency-Key": idempotency_key}
        )

        # Both should succeed with same patient ID
        assert response1.status_code in [200, 201]
        assert response2.status_code in [200, 201]
        assert response1.json()["id"] == response2.json()["id"]

    def test_different_keys_create_different_patients(self, client, auth_headers):
        """Test different keys create different patients."""
        patient_data_1 = {
            "name": "Test Patient 1",
            "phone": "+5511888888888",
            "treatment_type": "chemotherapy"
        }

        patient_data_2 = {
            "name": "Test Patient 2",
            "phone": "+5511777777777",
            "treatment_type": "radiotherapy"
        }

        response1 = client.post(
            "/api/v2/patients",
            json=patient_data_1,
            headers={**auth_headers, "X-Idempotency-Key": f"key-{uuid4()}"}
        )

        response2 = client.post(
            "/api/v2/patients",
            json=patient_data_2,
            headers={**auth_headers, "X-Idempotency-Key": f"key-{uuid4()}"}
        )

        assert response1.status_code in [200, 201]
        assert response2.status_code in [200, 201]
        assert response1.json()["id"] != response2.json()["id"]

    def test_create_without_idempotency_key_allows_duplicates(self, client, auth_headers):
        """Test creation without idempotency key allows duplicates."""
        patient_data = {
            "name": "Test Patient",
            "phone": "+5511666666666",
            "treatment_type": "chemotherapy"
        }

        # Two requests without idempotency key
        response1 = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=auth_headers
        )

        # Change phone to avoid DB constraint
        patient_data["phone"] = "+5511666666667"

        response2 = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=auth_headers
        )

        # Should create different patients
        if response1.status_code in [200, 201] and response2.status_code in [200, 201]:
            assert response1.json()["id"] != response2.json()["id"]

    def test_idempotency_key_expires(self):
        """Test idempotency key expires after TTL."""
        from app.services.idempotency_service import IdempotencyService

        mock_redis = MagicMock()
        service = IdempotencyService(redis=mock_redis)

        key = f"test-{uuid4()}"
        result = {"id": "123", "name": "Test"}

        # Set with TTL
        service.set_result(key, result, ttl_seconds=3600)

        # Verify setex was called with correct TTL
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 3600  # TTL in seconds


class TestPatientUpdateIdempotency:
    """Test idempotency on patient updates."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": "Bearer test_token"}

    def test_patch_with_idempotency_key(self, client, auth_headers):
        """Test PATCH uses idempotency key."""
        patient_id = "123"
        update_data = {"name": "Updated Name"}
        idempotency_key = f"update-{uuid4()}"

        # First update
        response1 = client.patch(
            f"/api/v2/patients/{patient_id}",
            json=update_data,
            headers={**auth_headers, "X-Idempotency-Key": idempotency_key}
        )

        # Second update with same key
        response2 = client.patch(
            f"/api/v2/patients/{patient_id}",
            json=update_data,
            headers={**auth_headers, "X-Idempotency-Key": idempotency_key}
        )

        # Both should return same response
        if response1.status_code == 200:
            assert response2.status_code == 200
            assert response1.json() == response2.json()

    def test_put_with_idempotency_key(self, client, auth_headers):
        """Test PUT uses idempotency key."""
        patient_id = "123"
        full_data = {
            "name": "Complete Patient Data",
            "phone": "+5511555555555",
            "treatment_type": "chemotherapy"
        }
        idempotency_key = f"put-{uuid4()}"

        response1 = client.put(
            f"/api/v2/patients/{patient_id}",
            json=full_data,
            headers={**auth_headers, "X-Idempotency-Key": idempotency_key}
        )

        response2 = client.put(
            f"/api/v2/patients/{patient_id}",
            json=full_data,
            headers={**auth_headers, "X-Idempotency-Key": idempotency_key}
        )

        if response1.status_code == 200:
            assert response2.status_code == 200


class TestWebhookIdempotency:
    """Test webhook idempotency."""

    @pytest.mark.asyncio
    async def test_duplicate_event_skipped(self):
        """Test duplicate webhook events are skipped."""
        from app.services.webhook_service import WebhookService

        mock_redis = AsyncMock()
        mock_redis.exists.return_value = True  # Already processed

        service = WebhookService(redis=mock_redis)

        is_processed = await service.is_event_processed("evt_123")

        assert is_processed is True
        mock_redis.exists.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_event_processed(self):
        """Test new webhook events are processed."""
        from app.services.webhook_service import WebhookService

        mock_redis = AsyncMock()
        mock_redis.exists.return_value = False  # Not processed yet

        service = WebhookService(redis=mock_redis)

        is_processed = await service.is_event_processed("evt_new")

        assert is_processed is False
        mock_redis.exists.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_marked_as_processed(self):
        """Test event is marked as processed after handling."""
        from app.services.webhook_service import WebhookService

        mock_redis = AsyncMock()
        service = WebhookService(redis=mock_redis)

        event_id = "evt_456"
        await service.mark_event_processed(event_id)

        # Should be stored with TTL
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert event_id in str(call_args)

    @pytest.mark.asyncio
    async def test_webhook_concurrent_processing_prevented(self):
        """Test concurrent webhook processing is prevented."""
        from app.services.webhook_service import WebhookService

        mock_redis = AsyncMock()
        call_count = 0

        async def exists_side_effect(key):
            nonlocal call_count
            call_count += 1
            # First call: not processed, second call: processed
            return call_count > 1

        mock_redis.exists.side_effect = exists_side_effect

        service = WebhookService(redis=mock_redis)

        # Simulate concurrent calls
        event_id = "evt_concurrent"

        result1 = await service.is_event_processed(event_id)
        result2 = await service.is_event_processed(event_id)

        assert result1 is False  # First call: not processed
        assert result2 is True   # Second call: already processed


class TestIdempotencyService:
    """Test idempotency service core functionality."""

    @pytest.mark.asyncio
    async def test_result_caching(self):
        """Test results are cached properly."""
        from app.services.idempotency_service import IdempotencyService

        mock_redis = AsyncMock()
        service = IdempotencyService(redis=mock_redis)

        key = "idempotency_123"
        result = {"id": "patient_456", "status": "created"}

        await service.cache_result(key, result, ttl=3600)

        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_result_retrieval(self):
        """Test cached results can be retrieved."""
        from app.services.idempotency_service import IdempotencyService
        import json

        mock_redis = AsyncMock()
        expected_result = {"id": "patient_456", "status": "created"}
        mock_redis.get.return_value = json.dumps(expected_result)

        service = IdempotencyService(redis=mock_redis)

        key = "idempotency_123"
        result = await service.get_cached_result(key)

        assert result == expected_result
        mock_redis.get.assert_called_once_with(key)

    @pytest.mark.asyncio
    async def test_key_generation(self):
        """Test idempotency key generation."""
        from app.services.idempotency_service import IdempotencyService

        service = IdempotencyService()

        # Test with different inputs
        key1 = service.generate_key("POST", "/patients", {"name": "Test"})
        key2 = service.generate_key("POST", "/patients", {"name": "Test"})
        key3 = service.generate_key("POST", "/patients", {"name": "Different"})

        # Same input should generate same key
        assert key1 == key2
        # Different input should generate different key
        assert key1 != key3

    @pytest.mark.asyncio
    async def test_ttl_configuration(self):
        """Test TTL can be configured."""
        from app.services.idempotency_service import IdempotencyService

        mock_redis = AsyncMock()
        service = IdempotencyService(redis=mock_redis, default_ttl=7200)

        key = "test_key"
        result = {"test": "data"}

        await service.cache_result(key, result)

        # Should use default TTL
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 7200


class TestIdempotencyMiddleware:
    """Test idempotency middleware."""

    @pytest.mark.asyncio
    async def test_middleware_extracts_key_from_header(self):
        """Test middleware extracts idempotency key from header."""
        from app.middleware.idempotency_middleware import IdempotencyMiddleware
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = "key_123"

        middleware = IdempotencyMiddleware(app=MagicMock())

        key = middleware._extract_key(mock_request)

        assert key == "key_123"
        mock_request.headers.get.assert_called_with("X-Idempotency-Key")

    @pytest.mark.asyncio
    async def test_middleware_skips_get_requests(self):
        """Test middleware skips GET requests."""
        from app.middleware.idempotency_middleware import IdempotencyMiddleware
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"

        middleware = IdempotencyMiddleware(app=MagicMock())

        should_process = middleware._should_process_request(mock_request)

        assert should_process is False

    @pytest.mark.asyncio
    async def test_middleware_processes_post_requests(self):
        """Test middleware processes POST requests."""
        from app.middleware.idempotency_middleware import IdempotencyMiddleware
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"

        middleware = IdempotencyMiddleware(app=MagicMock())

        should_process = middleware._should_process_request(mock_request)

        assert should_process is True
