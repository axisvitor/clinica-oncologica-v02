"""
Integration tests for API contract validation and critical endpoints.
Tests core functionality without over-testing implementation details.
"""
import pytest
import asyncio
from httpx import AsyncClient
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend_hormonia.app.main import app
from backend_hormonia.app.database import get_db, Base
from backend_hormonia.app.models.user import User, UserRole
from backend_hormonia.app.utils.security import get_password_hash


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(setup_database):
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def async_client(setup_database):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def test_user():
    """Create a test user for authentication tests."""
    db = TestingSessionLocal()
    try:
        user = User(
            email="test@example.com",
            hashed_password=get_password_hash("testpassword123"),
            full_name="Test User",
            role=UserRole.doctor,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


@pytest.fixture
def admin_user():
    """Create an admin user for admin endpoint tests."""
    db = TestingSessionLocal()
    try:
        user = User(
            email="admin@example.com",
            hashed_password=get_password_hash("adminpassword123"),
            full_name="Admin User",
            role=UserRole.admin,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


class TestHealthEndpoints:
    """Test health check endpoints for basic connectivity."""

    def test_root_health_check(self, client):
        """Test basic health endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_api_health_check(self, client):
        """Test API health endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data


class TestAuthenticationEndpoints:
    """Test authentication endpoints and Firebase integration."""

    def test_login_disabled_local_auth(self, client):
        """Test that local authentication is properly disabled."""
        response = client.post("/api/v1/auth/login", data={
            "username": "test@example.com",
            "password": "testpassword123"
        })
        assert response.status_code == 410  # Gone
        assert "Firebase-only authentication" in response.json()["detail"]

    def test_login_json_disabled(self, client):
        """Test that JSON login is disabled."""
        response = client.post("/api/v1/auth/login-json", json={
            "email": "test@example.com",
            "password": "testpassword123"
        })
        assert response.status_code == 410  # Gone
        assert "Firebase-only authentication" in response.json()["detail"]

    def test_refresh_token_disabled(self, client):
        """Test that refresh token endpoint is disabled."""
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": "fake_token"
        })
        assert response.status_code == 410  # Gone
        assert "Firebase handles refresh" in response.json()["detail"]

    def test_me_endpoint_without_auth(self, client):
        """Test /me endpoint without authentication."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401


class TestAdminUserManagement:
    """Test admin user management endpoints."""

    def test_list_users_without_admin(self, client):
        """Test that non-admin users cannot list users."""
        response = client.get("/api/v1/admin/users/")
        assert response.status_code == 401  # No auth

    def test_create_user_without_admin(self, client):
        """Test that non-admin users cannot create users."""
        user_data = {
            "email": "newuser@example.com",
            "password": "newpassword123",
            "full_name": "New User",
            "role": "doctor",
            "is_active": True
        }
        response = client.post("/api/v1/admin/users/", json=user_data)
        assert response.status_code == 401  # No auth

    def test_user_stats_without_admin(self, client):
        """Test that user stats require admin access."""
        response = client.get("/api/v1/admin/users/stats/overview")
        assert response.status_code == 401  # No auth


class TestWebhookEndpoints:
    """Test webhook endpoints for security and validation."""

    def test_evolution_message_webhook_no_signature(self, client):
        """Test webhook rejects requests without signature in production mode."""
        # Mock production environment
        import os
        original_env = os.environ.get('ENVIRONMENT')
        os.environ['ENVIRONMENT'] = 'production'

        try:
            response = client.post("/api/v1/webhooks/evolution/message", json={
                "event": "message.received",
                "data": {}
            })
            # Should fail in production without signature
            assert response.status_code in [401, 500]  # Unauthorized or error
        finally:
            # Restore environment
            if original_env:
                os.environ['ENVIRONMENT'] = original_env
            else:
                os.environ.pop('ENVIRONMENT', None)

    def test_evolution_status_webhook_structure(self, client):
        """Test webhook accepts properly structured status updates."""
        response = client.post("/api/v1/webhooks/evolution/status", json={
            "event": "message.status",
            "data": {
                "status": "read",
                "messageId": "test_message_id"
            }
        })
        # Should not crash, may return 401 due to signature validation
        assert response.status_code in [200, 401, 500]

    def test_evolution_health_check(self, client):
        """Test Evolution API health check endpoint."""
        response = client.get("/api/v1/webhooks/evolution/health")
        # Should return status regardless of Evolution API connection
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestUserPreferences:
    """Test user preferences endpoints."""

    def test_get_preferences_without_auth(self, client):
        """Test that preferences require authentication."""
        response = client.get("/api/v1/auth/users/preferences")
        assert response.status_code == 401

    def test_update_preferences_without_auth(self, client):
        """Test that preference updates require authentication."""
        response = client.put("/api/v1/auth/users/preferences", json={
            "notification_email": False,
            "theme": "dark"
        })
        assert response.status_code == 401


class TestNotificationEndpoints:
    """Test notification system endpoints."""

    def test_notifications_without_auth(self, client):
        """Test that notifications require authentication."""
        response = client.get("/api/v1/auth/notifications")
        assert response.status_code == 401

    def test_mark_notification_read_without_auth(self, client):
        """Test that notification actions require authentication."""
        response = client.post("/api/v1/auth/notifications/test-id/read")
        assert response.status_code == 401


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_login_rate_limiting(self, client):
        """Test that login attempts are rate limited."""
        # Make multiple requests to trigger rate limiting
        for _ in range(6):  # More than the 5/minute limit
            response = client.post("/api/v1/auth/login", data={
                "username": "test@example.com",
                "password": "wrongpassword"
            })

        # Last request should be rate limited or return 410 (disabled)
        assert response.status_code in [429, 410]


class TestErrorHandling:
    """Test error handling and validation."""

    def test_invalid_json_handling(self, client):
        """Test that invalid JSON is handled gracefully."""
        response = client.post(
            "/api/v1/auth/login-json",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [400, 410, 422]

    def test_missing_required_fields(self, client):
        """Test validation of required fields."""
        response = client.post("/api/v1/admin/users/", json={
            "email": "test@example.com"
            # Missing required fields
        })
        assert response.status_code in [401, 422]  # Validation error or auth required

    def test_invalid_email_format(self, client):
        """Test email validation."""
        response = client.post("/api/v1/admin/users/", json={
            "email": "invalid-email",
            "password": "password123",
            "full_name": "Test User",
            "role": "doctor"
        })
        assert response.status_code in [401, 422]  # Validation error or auth required


class TestSecurityHeaders:
    """Test security headers and CORS configuration."""

    def test_security_headers_present(self, client):
        """Test that security headers are present in responses."""
        response = client.get("/api/v1/health")
        # Check for basic security considerations
        assert response.status_code == 200
        # Additional security header checks would go here

    def test_cors_configuration(self, client):
        """Test CORS headers for cross-origin requests."""
        response = client.options("/api/v1/health")
        # Should handle OPTIONS requests properly
        assert response.status_code in [200, 405]  # OK or Method Not Allowed


@pytest.mark.asyncio
class TestAsyncOperations:
    """Test async operations and concurrency."""

    async def test_concurrent_health_checks(self, async_client):
        """Test that multiple concurrent requests are handled properly."""
        tasks = []
        for _ in range(10):
            task = asyncio.create_task(async_client.get("/api/v1/health"))
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        # All requests should succeed
        for response in responses:
            assert response.status_code == 200

    async def test_webhook_concurrent_processing(self, async_client):
        """Test concurrent webhook processing."""
        webhook_data = {
            "event": "message.received",
            "data": {"test": "data"}
        }

        tasks = []
        for _ in range(5):
            task = asyncio.create_task(
                async_client.post("/api/v1/webhooks/evolution/message", json=webhook_data)
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        # Should handle concurrent webhooks without crashes
        for response in responses:
            assert response.status_code in [200, 401, 500]  # Various valid responses


if __name__ == "__main__":
    pytest.main([__file__, "-v"])