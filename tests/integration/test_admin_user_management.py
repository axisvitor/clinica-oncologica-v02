"""
Admin user management integration tests.
Tests admin CRUD operations, role validation, and security controls.
"""
import pytest
from uuid import uuid4
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
from backend_hormonia.app.dependencies import get_admin_user, get_current_user, RequestContext


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_admin.db"
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
def admin_user():
    """Create an admin user for testing."""
    db = TestingSessionLocal()
    try:
        user = User(
            email="admin@example.com",
            hashed_password=get_password_hash("admin123"),
            full_name="Admin User",
            role=UserRole.admin,
            is_active=True,
            metadata={"firebase_uid": "admin-firebase-uid"}
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


@pytest.fixture
def doctor_user():
    """Create a doctor user for testing."""
    db = TestingSessionLocal()
    try:
        user = User(
            email="doctor@example.com",
            hashed_password=get_password_hash("doctor123"),
            full_name="Dr. Test Doctor",
            role=UserRole.doctor,
            is_active=True,
            metadata={"firebase_uid": "doctor-firebase-uid"}
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


@pytest.fixture
def inactive_user():
    """Create an inactive user for testing."""
    db = TestingSessionLocal()
    try:
        user = User(
            email="inactive@example.com",
            hashed_password=get_password_hash("inactive123"),
            full_name="Inactive User",
            role=UserRole.doctor,
            is_active=False,
            metadata={"firebase_uid": "inactive-firebase-uid"}
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def mock_request_context():
    """Create a mock request context."""
    return RequestContext(
        ip_address="127.0.0.1",
        user_agent="test-agent",
        request_id="test-request-id"
    )


class TestAdminAccessControl:
    """Test admin access control and permissions."""

    def test_admin_endpoints_require_admin_role(self, client):
        """Test that admin endpoints require admin role."""
        endpoints = [
            "/api/v1/admin/users/",
            "/api/v1/admin/users/stats/overview"
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401  # Unauthorized without auth

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_admin_user_list_with_admin_auth(self, mock_context, client, admin_user):
        """Test user list endpoint with admin authentication."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        try:
            response = client.get("/api/v1/admin/users/")
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert "page" in data
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_doctor_cannot_access_admin_endpoints(self, mock_context, client, doctor_user):
        """Test that doctor users cannot access admin endpoints."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Admin access required")

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        try:
            response = client.get("/api/v1/admin/users/")
            assert response.status_code == 403
        finally:
            app.dependency_overrides.pop(get_admin_user, None)


class TestUserCRUDOperations:
    """Test user CRUD operations."""

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_create_user_success(self, mock_context, client, admin_user):
        """Test successful user creation."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        user_data = {
            "email": "newuser@example.com",
            "password": "newuser123",
            "full_name": "New User",
            "role": "doctor",
            "is_active": True
        }

        try:
            response = client.post("/api/v1/admin/users/", json=user_data)
            assert response.status_code == 201
            data = response.json()
            assert data["email"] == "newuser@example.com"
            assert data["role"] == "doctor"
            assert data["is_active"] is True
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_create_user_duplicate_email(self, mock_context, client, admin_user, doctor_user):
        """Test user creation with duplicate email."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        user_data = {
            "email": doctor_user.email,  # Duplicate email
            "password": "duplicate123",
            "full_name": "Duplicate User",
            "role": "doctor",
            "is_active": True
        }

        try:
            response = client.post("/api/v1/admin/users/", json=user_data)
            assert response.status_code == 400
            assert "already exists" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_get_user_details(self, mock_context, client, admin_user, doctor_user):
        """Test getting user details."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        try:
            response = client.get(f"/api/v1/admin/users/{doctor_user.id}")
            assert response.status_code == 200
            data = response.json()
            assert data["email"] == doctor_user.email
            assert data["full_name"] == doctor_user.full_name
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_get_user_not_found(self, mock_context, client, admin_user):
        """Test getting non-existent user."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        fake_uuid = str(uuid4())

        try:
            response = client.get(f"/api/v1/admin/users/{fake_uuid}")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_update_user_success(self, mock_context, client, admin_user, doctor_user):
        """Test successful user update."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        update_data = {
            "full_name": "Updated Doctor Name",
            "email": "updated.doctor@example.com"
        }

        try:
            response = client.put(f"/api/v1/admin/users/{doctor_user.id}", json=update_data)
            assert response.status_code == 200
            data = response.json()
            assert data["full_name"] == "Updated Doctor Name"
            assert data["email"] == "updated.doctor@example.com"
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_delete_user_success(self, mock_context, client, admin_user, doctor_user):
        """Test successful user deletion (soft delete)."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        try:
            response = client.delete(f"/api/v1/admin/users/{doctor_user.id}")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "deleted successfully" in data["message"]
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_cannot_delete_self(self, mock_context, client, admin_user):
        """Test that admin cannot delete their own account."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        try:
            response = client.delete(f"/api/v1/admin/users/{admin_user.id}")
            assert response.status_code == 400
            assert "Cannot delete your own account" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_admin_user, None)


class TestUserRoleManagement:
    """Test user role management operations."""

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_update_user_role_success(self, mock_context, client, admin_user, doctor_user):
        """Test successful role update."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        role_data = {"role": "admin"}

        try:
            response = client.put(f"/api/v1/admin/users/{doctor_user.id}/role", json=role_data)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "admin" in data["message"]
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_invalid_role_update(self, mock_context, client, admin_user, doctor_user):
        """Test role update with invalid role."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        role_data = {"role": "invalid_role"}

        try:
            response = client.put(f"/api/v1/admin/users/{doctor_user.id}/role", json=role_data)
            assert response.status_code == 400
            assert "Invalid role" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_cannot_change_own_role(self, mock_context, client, admin_user):
        """Test that admin cannot change their own role."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        role_data = {"role": "doctor"}

        try:
            response = client.put(f"/api/v1/admin/users/{admin_user.id}/role", json=role_data)
            assert response.status_code == 400
            assert "Cannot change your own role" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_admin_user, None)


class TestUserActivationControls:
    """Test user activation and deactivation controls."""

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_activate_inactive_user(self, mock_context, client, admin_user, inactive_user):
        """Test activating an inactive user."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        try:
            response = client.post(f"/api/v1/admin/users/{inactive_user.id}/activate")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "activated successfully" in data["message"]
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_activate_already_active_user(self, mock_context, client, admin_user, doctor_user):
        """Test activating an already active user."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        try:
            response = client.post(f"/api/v1/admin/users/{doctor_user.id}/activate")
            assert response.status_code == 400
            assert "already active" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_deactivate_active_user(self, mock_context, client, admin_user, doctor_user):
        """Test deactivating an active user."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        try:
            response = client.post(f"/api/v1/admin/users/{doctor_user.id}/deactivate")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "deactivated successfully" in data["message"]
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_cannot_deactivate_self(self, mock_context, client, admin_user):
        """Test that admin cannot deactivate their own account."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        try:
            response = client.post(f"/api/v1/admin/users/{admin_user.id}/deactivate")
            assert response.status_code == 400
            assert "Cannot deactivate your own account" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_admin_user, None)


class TestPasswordManagement:
    """Test admin password management operations."""

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_reset_user_password(self, mock_context, client, admin_user, doctor_user):
        """Test admin password reset for user."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        password_data = {
            "new_password": "newpassword123",
            "force_change": True
        }

        try:
            response = client.post(f"/api/v1/admin/users/{doctor_user.id}/reset-password", json=password_data)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "reset successfully" in data["message"]
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_reset_password_weak_password(self, mock_context, client, admin_user, doctor_user):
        """Test password reset with weak password."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        password_data = {
            "new_password": "123",  # Too weak
            "force_change": False
        }

        try:
            response = client.post(f"/api/v1/admin/users/{doctor_user.id}/reset-password", json=password_data)
            assert response.status_code in [400, 422]  # Validation error
        finally:
            app.dependency_overrides.pop(get_admin_user, None)


class TestUserStatistics:
    """Test user statistics and reporting."""

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_get_user_stats(self, mock_context, client, admin_user):
        """Test getting user statistics."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        try:
            response = client.get("/api/v1/admin/users/stats/overview")
            assert response.status_code == 200
            data = response.json()
            assert "total_users" in data
            assert "active_users" in data
            assert "inactive_users" in data
            assert "by_role" in data
            assert "recent_registrations" in data
        finally:
            app.dependency_overrides.pop(get_admin_user, None)


class TestUserActivityTracking:
    """Test user activity tracking and audit logs."""

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_get_user_activity(self, mock_context, client, admin_user, doctor_user):
        """Test getting user activity history."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        try:
            response = client.get(f"/api/v1/admin/users/{doctor_user.id}/activity")
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert "page" in data
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_user_activity_pagination(self, mock_context, client, admin_user, doctor_user):
        """Test user activity pagination."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        try:
            response = client.get(f"/api/v1/admin/users/{doctor_user.id}/activity?page=1&size=5")
            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 1
            assert data["size"] == 5
        finally:
            app.dependency_overrides.pop(get_admin_user, None)


class TestUserListPagination:
    """Test user list pagination and filtering."""

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_user_list_pagination(self, mock_context, client, admin_user):
        """Test user list with pagination."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        try:
            response = client.get("/api/v1/admin/users/?page=1&size=10")
            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 1
            assert data["size"] == 10
            assert "total_pages" in data
            assert "has_next" in data
            assert "has_previous" in data
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_user_list_filtering(self, mock_context, client, admin_user):
        """Test user list with role filtering."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        try:
            response = client.get("/api/v1/admin/users/?role=doctor&is_active=true")
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            # All returned users should be doctors and active
            for user in data["items"]:
                assert user["role"] == "doctor"
                assert user["is_active"] is True
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_user_list_search(self, mock_context, client, admin_user):
        """Test user list with search functionality."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        try:
            response = client.get("/api/v1/admin/users/?search=admin")
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
        finally:
            app.dependency_overrides.pop(get_admin_user, None)


class TestDataValidation:
    """Test input validation and sanitization."""

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_create_user_invalid_email(self, mock_context, client, admin_user):
        """Test user creation with invalid email."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        user_data = {
            "email": "invalid-email",
            "password": "validpass123",
            "full_name": "Test User",
            "role": "doctor",
            "is_active": True
        }

        try:
            response = client.post("/api/v1/admin/users/", json=user_data)
            assert response.status_code == 422  # Validation error
        finally:
            app.dependency_overrides.pop(get_admin_user, None)

    @patch('backend_hormonia.app.dependencies.get_request_context')
    def test_create_user_missing_required_fields(self, mock_context, client, admin_user):
        """Test user creation with missing required fields."""
        mock_context.return_value = mock_request_context()

        def mock_get_admin_user():
            return admin_user

        app.dependency_overrides[get_admin_user] = mock_get_admin_user

        user_data = {
            "email": "test@example.com"
            # Missing password, full_name, role
        }

        try:
            response = client.post("/api/v1/admin/users/", json=user_data)
            assert response.status_code == 422  # Validation error
        finally:
            app.dependency_overrides.pop(get_admin_user, None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])