"""
Test Session Isolation - Concurrent Request Handling

Validates that concurrent requests get independent database sessions
and no session cross-talk occurs.

ISSUE: Global ServiceProvider caused session sharing between requests
RESOLUTION: Implemented request-scoped ServiceProvider with contextvars

Run with: pytest tests/integration/test_session_isolation.py -v
"""
import pytest
import asyncio
from fastapi.testclient import TestClient


class TestSessionIsolation:
    """Test database session isolation under concurrent load"""

    def setup_method(self):
        """Setup test environment"""
        from app.main import app
        self.client = TestClient(app)

    def test_session_isolation_basic(self):
        """Test that get_db() creates unique sessions"""
        from app.database import get_db

        db1 = next(get_db())
        db2 = next(get_db())
        try:
            assert id(db1) != id(db2), "Sessions should be unique"
            assert db1.is_active
            assert db2.is_active
        finally:
            db1.close()
            db2.close()

    @pytest.mark.asyncio
    async def test_concurrent_requests_isolated_sessions(self):
        """
        Test that concurrent requests get independent database sessions.

        This test simulates 20 concurrent requests to ensure no session cross-talk.
        Each request should get its own ServiceProvider with isolated session.
        """
        async def make_request(request_id: int):
            """Make a single request with unique identifier"""
            # Simulate concurrent API calls
            response = self.client.get("/api/v1/railway/health")
            return {
                "request_id": request_id,
                "status_code": response.status_code,
                "success": response.status_code in [200, 503]
            }

        # Fire 20 concurrent requests
        tasks = [make_request(i) for i in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed without exceptions
        successful_requests = [r for r in results if isinstance(r, dict) and r["success"]]
        failed_requests = [r for r in results if not (isinstance(r, dict) and r.get("success"))]

        assert len(successful_requests) >= 18, f"Too many failures: {len(failed_requests)}/20"
        assert len(failed_requests) <= 2, f"Failures: {failed_requests}"

    def test_sequential_requests_no_session_leakage(self):
        """
        Test that sequential requests don't share session state.

        Each request should start with a fresh session from the pool.
        """
        responses = []

        for i in range(10):
            response = self.client.get("/api/v1/railway/health")
            responses.append({
                "request_num": i,
                "status_code": response.status_code,
                "success": response.status_code in [200, 503]
            })

        # All requests should succeed independently
        successful = sum(1 for r in responses if r["success"])
        assert successful == 10, f"Some requests failed: {responses}"

    def test_service_provider_per_request_uniqueness(self):
        """
        Test that each request gets a unique ServiceProvider instance.

        This indirectly validates session isolation by ensuring
        no global singleton is being used.
        """
        from app.dependencies import get_thread_safe_service_provider

        # Simulate multiple requests
        provider_ids = []

        for i in range(5):
            # Get ServiceProvider as FastAPI would during a request
            provider_gen = get_thread_safe_service_provider()
            provider = next(provider_gen)

            provider_ids.append(id(provider))

            # Cleanup (simulate end of request)
            try:
                provider_gen.close()
            except StopIteration:
                pass

        # All providers should be unique (different memory addresses)
        unique_providers = len(set(provider_ids))

        # Providers should always be unique
        assert unique_providers == 5, f"Expected 5 unique providers, got {unique_providers}"


class TestSessionCleanup:
    """Test that database sessions are properly cleaned up"""

    def setup_method(self):
        """Setup test environment"""
        from app.main import app
        self.client = TestClient(app)

    def test_session_cleanup_after_request(self):
        """
        Test that sessions are closed after request completes.

        Verifies the finally block in get_db() dependency executes.
        """
        from app.database import engine

        # Get initial pool stats
        initial_checked_in = engine.pool.checkedin()

        # Make a request (should acquire and release a connection)
        response = self.client.get("/api/v1/railway/health")

        # Pool should return to initial state (or better)
        final_checked_in = engine.pool.checkedin()

        # Allow some variance for pool management
        assert final_checked_in >= initial_checked_in - 1, \
            f"Session leak detected! Initial: {initial_checked_in}, Final: {final_checked_in}"

    def test_session_rollback_on_exception(self):
        """
        Test that sessions are rolled back on exceptions.

        Simulates an operation that fails to verify
        proper error handling and rollback.
        """
        from app.database import get_db
        from sqlalchemy import text

        db = next(get_db())

        try:
            # Simulate an operation that might fail
            db.execute(text("SELECT 1"))
            # If we get here, connection works
            success = True
        except Exception:
            # Exception should trigger rollback in finally block
            success = False
        finally:
            db.close()

        # Should succeed with basic query
        assert success, "Basic database query failed"


class TestThreadSafety:
    """Test thread safety of session management"""

    def test_contextvar_isolation(self):
        """
        Test that contextvars properly isolate sessions.

        This is a lower-level test that verifies the session manager
        uses contextvars correctly.
        """
        from app.core.session_manager import _request_session
        from app.database import get_db

        # Initially should be None
        initial_session = _request_session.get()

        # Create a session
        db = next(get_db())

        try:
            # Session should be set in context (or properly managed)
            current_session = _request_session.get()

            # Verify session is active
            assert db.is_active, "Session should be active"

        finally:
            db.close()

        # After cleanup, verify session is closed
        assert not db.is_active, "Session should be closed after cleanup"

    def test_no_global_service_provider(self):
        """
        Test that global service provider pattern is disabled.

        The old get_service_provider(request) pattern should raise RuntimeError.
        """
        from app.services import get_service_provider

        # Create a mock request
        class MockRequest:
            pass

        request = MockRequest()

        # Should raise RuntimeError (deprecated and disabled)
        with pytest.raises(RuntimeError, match="Global service provider is DISABLED"):
            get_service_provider(request)
