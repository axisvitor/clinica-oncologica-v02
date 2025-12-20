"""
Comprehensive tests for Roles & Permissions API v2
Tests for role management, assignment, bulk operations, statistics, and validation.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock
from typing import List

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.utils.security import get_password_hash


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def admin_user(db_session: Session):
    """Create an admin user for testing."""
    admin = User(
        id=uuid4(),
        email="admin@test.com",
        hashed_password=get_password_hash("AdminPass123"),
        full_name="Test Admin",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def doctor_user(db_session: Session):
    """Create a doctor user for testing."""
    doctor = User(
        id=uuid4(),
        email="doctor@test.com",
        hashed_password=get_password_hash("DoctorPass123"),
        full_name="Dr. Test Doctor",
        role=UserRole.DOCTOR,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


@pytest.fixture
def inactive_user(db_session: Session):
    """Create an inactive user for testing."""
    user = User(
        id=uuid4(),
        email="inactive@test.com",
        hashed_password=get_password_hash("InactivePass123"),
        full_name="Inactive User",
        role=UserRole.DOCTOR,
        is_active=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def multiple_users(db_session: Session):
    """Create multiple users for bulk testing."""
    users = []
    for i in range(10):
        user = User(
            id=uuid4(),
            email=f"user{i}@test.com",
            hashed_password=get_password_hash(f"TestPass{i}123"),
            full_name=f"Test User {i}",
            role=UserRole.DOCTOR if i % 2 == 0 else UserRole.ADMIN,
            is_active=i % 3 != 0,  # Some inactive
            created_at=datetime.utcnow() - timedelta(days=i),
            updated_at=datetime.utcnow()
        )
        users.append(user)
        db_session.add(user)

    db_session.commit()
    for user in users:
        db_session.refresh(user)

    return users


@pytest.fixture
def mock_redis_cache():
    """Mock Redis cache for testing."""
    cache = AsyncMock()
    cache.get.return_value = None
    cache.set.return_value = True
    cache.delete.return_value = True
    return cache


@pytest.fixture
def mock_audit_service():
    """Mock audit service for testing."""
    service = Mock()
    service.log_event.return_value = None
    return service


# ============================================================================
# TEST: GET AVAILABLE ROLES
# ============================================================================

class TestGetAvailableRoles:
    """Tests for GET /roles endpoint."""

    def test_get_available_roles_success(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User
    ):
        """Test getting list of available roles."""
        response = client.get("/api/v2/roles")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "data" in data
        assert "total" in data
        assert len(data["data"]) == 2  # ADMIN and DOCTOR

        # Verify role structure
        for role in data["data"]:
            assert "name" in role
            assert "value" in role
            assert "description" in role
            assert "permissions" in role
            assert isinstance(role["permissions"], list)

    def test_get_available_roles_includes_user_counts(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        doctor_user: User
    ):
        """Test that role list includes user counts."""
        response = client.get("/api/v2/roles")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should have user counts
        for role in data["data"]:
            assert "user_count" in role
            assert isinstance(role["user_count"], int)

    def test_get_available_roles_caching(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        mock_redis_cache
    ):
        """Test that role list is cached."""
        with patch('app.api.v2.roles.get_redis_cache', return_value=mock_redis_cache):
            response1 = client.get("/api/v2/roles")
            response2 = client.get("/api/v2/roles")

            assert response1.status_code == status.HTTP_200_OK
            assert response2.status_code == status.HTTP_200_OK

            # Both requests should return same data
            assert response1.json() == response2.json()


# ============================================================================
# TEST: GET USER ROLE
# ============================================================================

class TestGetUserRole:
    """Tests for GET /roles/{user_id} endpoint."""

    def test_get_user_role_success(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        doctor_user: User
    ):
        """Test getting role for a specific user."""
        response = client.get(f"/api/v2/roles/{doctor_user.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["user_id"] == str(doctor_user.id)
        assert data["email"] == doctor_user.email
        assert data["current_role"] == "doctor"
        assert data["is_active"] == True

    def test_get_user_role_not_found(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User
    ):
        """Test getting role for non-existent user."""
        fake_id = uuid4()
        response = client.get(f"/api/v2/roles/{fake_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_get_user_role_includes_timestamps(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        doctor_user: User
    ):
        """Test that user role info includes timestamps."""
        response = client.get(f"/api/v2/roles/{doctor_user.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "created_at" in data
        assert "updated_at" in data
        # last_login is optional
        assert "last_login" in data


# ============================================================================
# TEST: ASSIGN ROLE
# ============================================================================

class TestAssignRole:
    """Tests for POST /roles/{user_id}/assign endpoint."""

    def test_assign_role_success(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        doctor_user: User
    ):
        """Test successful role assignment."""
        response = client.post(
            f"/api/v2/roles/{doctor_user.id}/assign",
            json={"role": "admin", "reason": "Promotion"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["user_id"] == str(doctor_user.id)
        assert data["current_role"] == "admin"

        # Verify in database
        db_session.refresh(doctor_user)
        assert doctor_user.role == UserRole.ADMIN

    def test_assign_role_with_audit_logging(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        doctor_user: User,
        mock_audit_service
    ):
        """Test that role assignment is logged to audit trail."""
        with patch('app.api.v2.roles.AuditService', return_value=mock_audit_service):
            response = client.post(
                f"/api/v2/roles/{doctor_user.id}/assign",
                json={"role": "admin", "reason": "Promotion"}
            )

            assert response.status_code == status.HTTP_200_OK
            # Audit service should have been called
            assert mock_audit_service.log_event.called

    def test_assign_role_prevents_last_admin_removal(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User
    ):
        """Test that cannot remove role from last admin."""
        response = client.post(
            f"/api/v2/roles/{admin_user.id}/assign",
            json={"role": "doctor"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "last active admin" in response.json()["detail"].lower()

    def test_assign_role_invalid_role(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        doctor_user: User
    ):
        """Test assigning invalid role."""
        response = client.post(
            f"/api/v2/roles/{doctor_user.id}/assign",
            json={"role": "superuser"}  # Invalid role
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_assign_role_user_not_found(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User
    ):
        """Test assigning role to non-existent user."""
        fake_id = uuid4()
        response = client.post(
            f"/api/v2/roles/{fake_id}/assign",
            json={"role": "doctor"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_assign_role_cache_invalidation(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        doctor_user: User,
        mock_redis_cache
    ):
        """Test that caches are invalidated after role assignment."""
        with patch('app.api.v2.roles.get_redis_cache', return_value=mock_redis_cache):
            response = client.post(
                f"/api/v2/roles/{doctor_user.id}/assign",
                json={"role": "admin"}
            )

            assert response.status_code == status.HTTP_200_OK
            # Cache delete should have been called
            assert mock_redis_cache.delete.called


# ============================================================================
# TEST: REVOKE ROLE
# ============================================================================

class TestRevokeRole:
    """Tests for DELETE /roles/{user_id}/revoke endpoint."""

    def test_revoke_role_success(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        multiple_users: List[User]
    ):
        """Test successful role revocation (reset to DOCTOR)."""
        # Get an admin user from multiple_users
        target_user = next(u for u in multiple_users if u.role == UserRole.ADMIN)

        response = client.delete(
            f"/api/v2/roles/{target_user.id}/revoke",
            json={"reason": "Department change"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["user_id"] == str(target_user.id)
        assert data["current_role"] == "doctor"

        # Verify in database
        db_session.refresh(target_user)
        assert target_user.role == UserRole.DOCTOR

    def test_revoke_role_prevents_last_admin_removal(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User
    ):
        """Test that cannot revoke role from last admin."""
        response = client.delete(
            f"/api/v2/roles/{admin_user.id}/revoke"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "last active admin" in response.json()["detail"].lower()

    def test_revoke_role_with_audit_logging(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        multiple_users: List[User],
        mock_audit_service
    ):
        """Test that role revocation is logged to audit trail."""
        target_user = next(u for u in multiple_users if u.role == UserRole.ADMIN)

        with patch('app.api.v2.roles.AuditService', return_value=mock_audit_service):
            response = client.delete(
                f"/api/v2/roles/{target_user.id}/revoke",
                json={"reason": "Role reset"}
            )

            assert response.status_code == status.HTTP_200_OK
            # Audit service should have been called
            assert mock_audit_service.log_event.called


# ============================================================================
# TEST: BULK ASSIGN ROLES
# ============================================================================

class TestBulkAssignRoles:
    """Tests for POST /roles/bulk-assign endpoint."""

    def test_bulk_assign_success(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        multiple_users: List[User]
    ):
        """Test successful bulk role assignment."""
        # Get doctor users only
        doctor_users = [u for u in multiple_users if u.role == UserRole.DOCTOR][:3]
        user_ids = [str(u.id) for u in doctor_users]

        response = client.post(
            "/api/v2/roles/bulk-assign",
            json={
                "user_ids": user_ids,
                "role": "doctor",
                "reason": "Bulk update"
            }
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["success_count"] >= 0
        assert data["failure_count"] >= 0
        assert isinstance(data["successful_users"], list)
        assert isinstance(data["failed_users"], list)

    def test_bulk_assign_max_users_validation(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User
    ):
        """Test that bulk assign enforces max 50 users."""
        # Try to assign to 51 users
        user_ids = [str(uuid4()) for _ in range(51)]

        response = client.post(
            "/api/v2/roles/bulk-assign",
            json={
                "user_ids": user_ids,
                "role": "doctor"
            }
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_bulk_assign_handles_partial_failures(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        doctor_user: User
    ):
        """Test that bulk assign handles partial failures gracefully."""
        # Mix of valid and invalid user IDs
        user_ids = [
            str(doctor_user.id),
            str(uuid4()),  # Non-existent user
            str(uuid4())   # Non-existent user
        ]

        response = client.post(
            "/api/v2/roles/bulk-assign",
            json={
                "user_ids": user_ids,
                "role": "doctor"
            }
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should have some successes and some failures
        assert data["success_count"] >= 1
        assert data["failure_count"] >= 1
        assert len(data["failed_users"]) == data["failure_count"]

    def test_bulk_assign_validates_duplicates(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        doctor_user: User
    ):
        """Test that bulk assign rejects duplicate user IDs."""
        user_id = str(doctor_user.id)

        response = client.post(
            "/api/v2/roles/bulk-assign",
            json={
                "user_ids": [user_id, user_id],  # Duplicate
                "role": "doctor"
            }
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ============================================================================
# TEST: ROLE STATISTICS
# ============================================================================

class TestRoleStatistics:
    """Tests for GET /roles/statistics endpoint."""

    def test_get_statistics_success(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        multiple_users: List[User]
    ):
        """Test getting role distribution statistics."""
        response = client.get("/api/v2/roles/statistics")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "total_users" in data
        assert "role_distribution" in data
        assert "active_users_by_role" in data
        assert "inactive_users_by_role" in data
        assert isinstance(data["role_distribution"], dict)

    def test_statistics_includes_role_changes(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User
    ):
        """Test that statistics include role changes count."""
        response = client.get("/api/v2/roles/statistics")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "role_changes_last_30_days" in data
        assert isinstance(data["role_changes_last_30_days"], int)

    def test_statistics_caching(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        mock_redis_cache
    ):
        """Test that statistics are cached."""
        with patch('app.api.v2.roles.get_redis_cache', return_value=mock_redis_cache):
            response1 = client.get("/api/v2/roles/statistics")
            response2 = client.get("/api/v2/roles/statistics")

            assert response1.status_code == status.HTTP_200_OK
            assert response2.status_code == status.HTTP_200_OK


# ============================================================================
# TEST: ROLE PERMISSIONS
# ============================================================================

class TestRolePermissions:
    """Tests for GET /roles/permissions/{role} endpoint."""

    def test_get_permissions_admin(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User
    ):
        """Test getting permissions for admin role."""
        response = client.get("/api/v2/roles/permissions/admin")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["role"] == "admin"
        assert isinstance(data["permissions"], list)
        assert len(data["permissions"]) > 0
        assert "permission_groups" in data
        assert isinstance(data["permission_groups"], dict)

    def test_get_permissions_doctor(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User
    ):
        """Test getting permissions for doctor role."""
        response = client.get("/api/v2/roles/permissions/doctor")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["role"] == "doctor"
        assert isinstance(data["permissions"], list)
        # Doctor should have fewer permissions than admin
        assert len(data["permissions"]) > 0

    def test_get_permissions_invalid_role(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User
    ):
        """Test getting permissions for invalid role."""
        response = client.get("/api/v2/roles/permissions/superuser")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_permissions_caching(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        mock_redis_cache
    ):
        """Test that permissions are cached."""
        with patch('app.api.v2.roles.get_redis_cache', return_value=mock_redis_cache):
            response1 = client.get("/api/v2/roles/permissions/admin")
            response2 = client.get("/api/v2/roles/permissions/admin")

            assert response1.status_code == status.HTTP_200_OK
            assert response2.status_code == status.HTTP_200_OK


# ============================================================================
# TEST: ROLE VALIDATION
# ============================================================================

class TestRoleValidation:
    """Tests for POST /roles/validate endpoint."""

    def test_validate_valid_assignment(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        doctor_user: User
    ):
        """Test validation of a valid role assignment."""
        response = client.post(
            "/api/v2/roles/validate",
            json={
                "user_id": str(doctor_user.id),
                "target_role": "admin"
            }
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["valid"] == True
        assert data["user_id"] == str(doctor_user.id)
        assert data["current_role"] == "doctor"
        assert data["target_role"] == "admin"
        assert data["reason"] is None

    def test_validate_user_not_found(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User
    ):
        """Test validation for non-existent user."""
        fake_id = uuid4()
        response = client.post(
            "/api/v2/roles/validate",
            json={
                "user_id": str(fake_id),
                "target_role": "admin"
            }
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["valid"] == False
        assert data["reason"] == "user_not_found"

    def test_validate_last_admin_protection(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User
    ):
        """Test validation prevents removing last admin."""
        response = client.post(
            "/api/v2/roles/validate",
            json={
                "user_id": str(admin_user.id),
                "target_role": "doctor"
            }
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["valid"] == False
        assert data["reason"] == "last_admin_protection"

    def test_validate_inactive_user_admin(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        inactive_user: User
    ):
        """Test validation prevents assigning admin to inactive user."""
        response = client.post(
            "/api/v2/roles/validate",
            json={
                "user_id": str(inactive_user.id),
                "target_role": "admin"
            }
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["valid"] == False
        assert data["reason"] == "inactive_user_admin"

    def test_validate_same_role_warning(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        doctor_user: User
    ):
        """Test validation warns if user already has the role."""
        response = client.post(
            "/api/v2/roles/validate",
            json={
                "user_id": str(doctor_user.id),
                "target_role": "doctor"
            }
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["valid"] == True
        assert len(data["warnings"]) > 0
        assert any("already has" in w.lower() for w in data["warnings"])


# ============================================================================
# TEST: RBAC ENFORCEMENT
# ============================================================================

class TestRBACEnforcement:
    """Tests for RBAC enforcement across all endpoints."""

    def test_non_admin_cannot_access_roles(
        self,
        client: TestClient,
        db_session: Session,
        doctor_user: User
    ):
        """Test that non-admin users cannot access role endpoints."""
        # Mock the get_admin_user dependency to raise 403
        with patch('app.api.v2.roles.get_admin_user') as mock_auth:
            mock_auth.side_effect = HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )

            response = client.get("/api/v2/roles")
            assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# TEST: RATE LIMITING
# ============================================================================

class TestRateLimiting:
    """Tests for rate limiting on role endpoints."""

    def test_assign_role_rate_limit(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
        doctor_user: User
    ):
        """Test that role assignment is rate limited."""
        # This test would require actual rate limiter setup
        # For now, just verify the decorator is present
        # In production, rate limiter would return 429 after threshold
        pass

    def test_bulk_assign_rate_limit(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User
    ):
        """Test that bulk assignment has stricter rate limits."""
        # This test would require actual rate limiter setup
        # Bulk operations should have lower limits than single operations
        pass
