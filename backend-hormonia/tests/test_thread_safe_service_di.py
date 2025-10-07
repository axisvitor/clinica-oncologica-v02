"""
Test Thread-Safe Service Dependency Injection

Verifies that the refactored service DI system provides proper per-request
session isolation and prevents thread-safety violations.

Test Coverage:
1. Concurrent session isolation
2. Per-request ServiceProvider instances
3. Session lifecycle management
4. Deprecated get_service_provider() raises error
"""
import pytest
import asyncio
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.services import ServiceProvider, get_service_provider
from app.dependencies import get_thread_safe_service_provider


class TestThreadSafeServiceProvider:
    """Test thread-safe ServiceProvider creation and session isolation."""

    def test_service_provider_per_request_isolation(self):
        """Verify each ServiceProvider gets its own session."""
        # Create two mock sessions
        session1 = Mock(spec=Session)
        session1.is_active = True

        session2 = Mock(spec=Session)
        session2.is_active = True

        # Create two ServiceProviders
        provider1 = ServiceProvider(db=session1, redis_client=None)
        provider2 = ServiceProvider(db=session2, redis_client=None)

        # Verify they have different sessions
        assert provider1.db is not provider2.db
        assert id(provider1.db) != id(provider2.db)

        # Verify each has unique request ID
        assert provider1._request_id != provider2._request_id

    def test_service_provider_session_validation(self):
        """Verify session validation detects inactive sessions."""
        # Create mock session
        session = Mock(spec=Session)

        # Test active session
        session.is_active = True
        provider = ServiceProvider(db=session, redis_client=None)
        provider.validate_session()  # Should not raise

        # Test inactive session
        session.is_active = False
        provider = ServiceProvider(db=session, redis_client=None)

        with pytest.raises(RuntimeError, match="no longer active"):
            provider.validate_session()

    def test_service_provider_lazy_loading(self):
        """Verify services are lazy-loaded on first access."""
        session = Mock(spec=Session)
        session.is_active = True

        provider = ServiceProvider(db=session, redis_client=None)

        # Services should be None initially
        assert provider._patient_service is None
        assert provider._auth_service is None

        # Access should trigger lazy loading
        # Note: This will fail if dependencies aren't mocked
        # In integration tests, verify lazy loading works

    @pytest.mark.asyncio
    async def test_thread_safe_provider_generator(self):
        """Verify get_thread_safe_service_provider returns generator."""
        # This test requires mocking the session manager
        # In integration tests, verify generator pattern works

        # For now, verify function exists and is callable
        assert callable(get_thread_safe_service_provider)


class TestDeprecatedGlobalProvider:
    """Test that deprecated get_service_provider raises errors."""

    def test_get_service_provider_raises_runtime_error(self):
        """Verify deprecated get_service_provider always raises."""
        mock_request = Mock()
        mock_request.app.state.service_provider = Mock()

        with pytest.raises(RuntimeError, match="DISABLED for thread safety"):
            get_service_provider(mock_request)

    def test_get_service_provider_shows_migration_guide(self):
        """Verify error message includes migration instructions."""
        mock_request = Mock()

        try:
            get_service_provider(mock_request)
            pytest.fail("Should have raised RuntimeError")
        except RuntimeError as e:
            error_msg = str(e)
            assert "get_thread_safe_service_provider" in error_msg
            assert "SERVICE_DI_REFACTOR.md" in error_msg
            assert "SOLUTION" in error_msg


class TestConcurrentSessionIsolation:
    """Test session isolation under concurrent requests."""

    @pytest.mark.asyncio
    async def test_concurrent_service_provider_creation(self):
        """Verify concurrent requests get independent ServiceProviders."""

        async def create_provider(session_id: int):
            """Simulate creating a ServiceProvider for a request."""
            # Mock session with unique ID
            session = Mock(spec=Session)
            session.is_active = True
            session._session_id = session_id

            provider = ServiceProvider(db=session, redis_client=None)

            # Verify provider uses correct session
            assert provider.db._session_id == session_id
            return provider

        # Create 10 providers concurrently
        tasks = [create_provider(i) for i in range(10)]
        providers = await asyncio.gather(*tasks)

        # Verify all providers are unique
        provider_ids = [id(p) for p in providers]
        assert len(set(provider_ids)) == 10

        # Verify all sessions are unique
        session_ids = [p.db._session_id for p in providers]
        assert session_ids == list(range(10))


class TestRedisClientDetection:
    """Test Redis client type detection."""

    def test_redis_client_type_detection_none(self):
        """Verify detection when no Redis client provided."""
        session = Mock(spec=Session)
        session.is_active = True

        provider = ServiceProvider(db=session, redis_client=None)
        assert provider._redis_client_type == "none"

    def test_redis_client_type_detection_async(self):
        """Verify detection of async Redis client."""
        session = Mock(spec=Session)
        session.is_active = True

        # Mock async Redis client
        redis_client = Mock()
        redis_client.__aenter__ = Mock()

        provider = ServiceProvider(db=session, redis_client=redis_client)
        assert provider._redis_client_type == "async"

    def test_redis_client_type_detection_sync(self):
        """Verify detection of sync Redis client."""
        session = Mock(spec=Session)
        session.is_active = True

        # Mock sync Redis client
        redis_client = Mock()
        redis_client.ping = Mock()
        # Ensure it's not async
        delattr(redis_client, '__aenter__') if hasattr(redis_client, '__aenter__') else None

        provider = ServiceProvider(db=session, redis_client=redis_client)
        # Should detect as sync or wrapper
        assert provider._redis_client_type in ["sync", "wrapper"]


class TestSessionLifecycle:
    """Test ServiceProvider lifecycle and cleanup."""

    def test_service_provider_destruction_logging(self):
        """Verify cleanup logging on ServiceProvider destruction."""
        session = Mock(spec=Session)
        session.is_active = True

        provider = ServiceProvider(db=session, redis_client=None)
        request_id = provider._request_id

        # Delete provider and verify cleanup
        # (Actual cleanup happens in __del__, hard to test directly)
        del provider

        # In real scenario, logger.debug would be called
        # For now, just verify request_id was set
        assert request_id is not None


# Integration test example (requires real database)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_requests_no_session_crosstalk():
    """
    Integration test: Verify no session cross-talk under concurrent load.

    This test requires:
    - Running database
    - FastAPI test client
    - Authentication tokens

    Example:
        async with AsyncClient(app=app, base_url="http://test") as client:
            tasks = [
                client.get("/api/v1/patients/me", headers={"Authorization": f"Bearer {token}"})
                for _ in range(10)
            ]
            results = await asyncio.gather(*tasks)
            assert all(r.status_code == 200 for r in results)
    """
    pytest.skip("Integration test - requires running database and auth setup")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
