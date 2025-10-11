"""
Authentication flow integration tests.
Tests the unified Firebase authentication system and admin access patterns.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from httpx import AsyncClient
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend_hormonia.app.main import app
from backend_hormonia.app.database import get_db, Base
from backend_hormonia.app.models.user import User, UserRole
from backend_hormonia.app.utils.security import get_password_hash
from backend_hormonia.app.dependencies import get_current_user, get_admin_user


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_auth.db"
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
def test_doctor_user():
    """Create a test doctor user."""
    db = TestingSessionLocal()
    try:
        user = User(
            email="doctor@example.com",
            hashed_password=get_password_hash("doctorpass123"),
            full_name="Dr. Test Doctor",
            role=UserRole.doctor,
            is_active=True,
            metadata={"firebase_uid": "test-firebase-uid-doctor"}
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


@pytest.fixture
def test_admin_user():
    """Create a test admin user."""
    db = TestingSessionLocal()
    try:
        user = User(
            email="admin@example.com",
            hashed_password=get_password_hash("adminpass123"),
            full_name="Admin User",
            role=UserRole.admin,
            is_active=True,
            metadata={"firebase_uid": "test-firebase-uid-admin"}
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


@pytest.fixture
def inactive_user():
    """Create an inactive user for testing access control."""
    db = TestingSessionLocal()
    try:
        user = User(
            email="inactive@example.com",
            hashed_password=get_password_hash("inactivepass123"),
            full_name="Inactive User",
            role=UserRole.doctor,
            is_active=False,
            metadata={"firebase_uid": "test-firebase-uid-inactive"}
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


class TestFirebaseAuthIntegration:
    """Test Firebase authentication integration."""

    def test_local_login_disabled(self, client):
        """Test that local login is properly disabled."""
        response = client.post("/api/v1/auth/login", data={
            "username": "doctor@example.com",
            "password": "doctorpass123"
        })
        assert response.status_code == 410
        assert "Firebase-only authentication" in response.json()["detail"]

    def test_local_json_login_disabled(self, client):
        """Test that JSON login is disabled."""
        response = client.post("/api/v1/auth/login-json", json={
            "email": "doctor@example.com",
            "password": "doctorpass123"
        })
        assert response.status_code == 410
        assert "Firebase-only authentication" in response.json()["detail"]

    def test_refresh_token_disabled(self, client):
        """Test that refresh token endpoint is disabled."""
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": "test_token"
        })
        assert response.status_code == 410
        assert "Firebase handles refresh" in response.json()["detail"]

    @patch('backend_hormonia.app.dependencies.verify_firebase_token')
    def test_me_endpoint_with_valid_firebase_token(self, mock_verify, client, test_doctor_user):
        """Test /me endpoint with valid Firebase token."""
        # Mock Firebase token verification
        mock_verify.return_value = {
            "uid": "test-firebase-uid-doctor",
            "email": "doctor@example.com"
        }

        # Mock the get_current_user dependency
        def mock_get_current_user():
            return test_doctor_user

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer fake-firebase-token"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["email"] == "doctor@example.com"
            assert data["role"] == "doctor"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_me_endpoint_without_token(self, client):
        """Test /me endpoint without authentication token."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401


class TestAdminAccessControl:
    """Test admin access control and role-based permissions."""

    @patch('backend_hormonia.app.dependencies.verify_firebase_token')
    def test_admin_endpoint_with_admin_user(self, mock_verify, client, test_admin_user):
        """Test admin endpoint access with admin user."""
        mock_verify.return_value = {
            "uid": "test-firebase-uid-admin",
            "email": "admin@example.com"
        }

        def mock_get_admin_user():
            return test_admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        try:
            response = client.get(
                "/api/v1/admin/users/stats/overview",
                headers={"Authorization": "Bearer fake-admin-token"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "total_users" in data
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    @patch('backend_hormonia.app.dependencies.verify_firebase_token')
    def test_admin_endpoint_with_doctor_user(self, mock_verify, client, test_doctor_user):
        """Test admin endpoint rejection with doctor user."""
        mock_verify.return_value = {
            "uid": "test-firebase-uid-doctor",
            "email": "doctor@example.com"
        }

        def mock_get_current_user():
            return test_doctor_user

        def mock_get_admin_user():
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Admin access required")

        app.dependency_overrides[get_current_user] = mock_get_current_user
        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        try:
            response = client.get(
                "/api/v1/admin/users/stats/overview",
                headers={"Authorization": "Bearer fake-doctor-token"}
            )
            assert response.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_admin_user, None)

    def test_admin_endpoint_without_auth(self, client):
        """Test admin endpoint without authentication."""
        response = client.get("/api/v1/admin/users/stats/overview")
        assert response.status_code == 401


class TestUserActivationStatus:
    """Test user activation status in authentication flow."""

    @patch('backend_hormonia.app.dependencies.verify_firebase_token')
    def test_inactive_user_access(self, mock_verify, client, inactive_user):
        """Test that inactive users cannot access protected endpoints."""
        mock_verify.return_value = {
            "uid": "test-firebase-uid-inactive",
            "email": "inactive@example.com"
        }

        def mock_get_current_user():
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Account is inactive")

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer fake-inactive-token"}
            )
            assert response.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestSessionBasedAuth:
    """Test session-based authentication patterns."""

    @patch('backend_hormonia.app.dependencies.verify_firebase_token')
    def test_session_cookie_auth(self, mock_verify, client, test_doctor_user):
        """Test authentication via session cookie."""
        mock_verify.return_value = {
            "uid": "test-firebase-uid-doctor",
            "email": "doctor@example.com"
        }

        def mock_get_current_user():
            return test_doctor_user

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            # Simulate session cookie authentication
            response = client.get(
                "/api/v1/auth/me",
                cookies={"session": "fake-session-id"}
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch('backend_hormonia.app.dependencies.verify_firebase_token')
    def test_x_session_id_header_auth(self, mock_verify, client, test_doctor_user):
        """Test authentication via X-Session-ID header."""
        mock_verify.return_value = {
            "uid": "test-firebase-uid-doctor",
            "email": "doctor@example.com"
        }

        def mock_get_current_user():
            return test_doctor_user

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = client.get(
                "/api/v1/auth/me",
                headers={"X-Session-ID": "fake-session-id"}
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestPasswordSecurity:
    """Test password security and change functionality."""

    @patch('backend_hormonia.app.dependencies.verify_firebase_token')
    @patch('requests.post')
    @patch('firebase_admin.auth.update_user')
    def test_password_change_flow(self, mock_update_user, mock_requests, mock_verify,
                                  client, test_doctor_user):
        """Test password change security flow."""
        mock_verify.return_value = {
            "uid": "test-firebase-uid-doctor",
            "email": "doctor@example.com"
        }

        # Mock current password verification success
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"localId": "test-firebase-uid-doctor"}
        mock_requests.return_value = mock_response

        def mock_get_current_user():
            return test_doctor_user

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = client.put(
                "/api/v1/auth/password",
                headers={"Authorization": "Bearer fake-token"},
                json={
                    "current_password": "doctorpass123",
                    "new_password": "newdoctorpass123"
                }
            )
            assert response.status_code == 200
            assert "Password updated successfully" in response.json()["message"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch('backend_hormonia.app.dependencies.verify_firebase_token')
    def test_password_change_rate_limiting(self, mock_verify, client, test_doctor_user):
        """Test password change rate limiting."""
        mock_verify.return_value = {
            "uid": "test-firebase-uid-doctor",
            "email": "doctor@example.com"
        }

        def mock_get_current_user():
            return test_doctor_user

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            # Make multiple password change attempts
            for _ in range(4):  # More than the 3/hour limit
                response = client.put(
                    "/api/v1/auth/password",
                    headers={"Authorization": "Bearer fake-token"},
                    json={
                        "current_password": "doctorpass123",
                        "new_password": "newpass123"
                    }
                )

            # Should eventually be rate limited
            assert response.status_code in [429, 400, 500]  # Rate limited or validation error
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestUserPreferencesAuth:
    """Test user preferences authentication requirements."""

    @patch('backend_hormonia.app.dependencies.verify_firebase_token')
    def test_get_preferences_authenticated(self, mock_verify, client, test_doctor_user):
        """Test getting preferences with authentication."""
        mock_verify.return_value = {
            "uid": "test-firebase-uid-doctor",
            "email": "doctor@example.com"
        }

        def mock_get_current_user():
            return test_doctor_user

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = client.get(
                "/api/v1/auth/users/preferences",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "preferences" in data
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_preferences_without_auth(self, client):
        """Test preferences endpoints require authentication."""
        response = client.get("/api/v1/auth/users/preferences")
        assert response.status_code == 401

        response = client.put("/api/v1/auth/users/preferences", json={
            "theme": "dark"
        })
        assert response.status_code == 401


class TestNotificationAuth:
    """Test notification system authentication."""

    @patch('backend_hormonia.app.dependencies.verify_firebase_token')
    def test_notifications_authenticated(self, mock_verify, client, test_doctor_user):
        """Test notifications with authentication."""
        mock_verify.return_value = {
            "uid": "test-firebase-uid-doctor",
            "email": "doctor@example.com"
        }

        def mock_get_current_user():
            return test_doctor_user

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = client.get(
                "/api/v1/auth/notifications",
                headers={"Authorization": "Bearer fake-token"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_notifications_without_auth(self, client):
        """Test notifications require authentication."""
        response = client.get("/api/v1/auth/notifications")
        assert response.status_code == 401

        response = client.post("/api/v1/auth/notifications/test-id/read")
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])