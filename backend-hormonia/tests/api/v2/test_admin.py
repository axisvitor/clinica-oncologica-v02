"""
Comprehensive tests for Admin API v2
Tests for user management, roles, permissions, audit, bulk operations, and search.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.audit_log import AuditLog
from app.utils.security import get_password_hash


from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
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
        created_at=now_sao_paulo_naive(),
        updated_at=now_sao_paulo_naive()
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
        created_at=now_sao_paulo_naive(),
        updated_at=now_sao_paulo_naive()
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
        created_at=now_sao_paulo_naive(),
        updated_at=now_sao_paulo_naive()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def multiple_users(db_session: Session):
    """Create multiple users for pagination testing."""
    users = []
    for i in range(25):
        user = User(
            id=uuid4(),
            email=f"user{i}@test.com",
            hashed_password=get_password_hash(f"TestPass{i}123"),
            full_name=f"Test User {i}",
            role=UserRole.DOCTOR if i % 2 == 0 else UserRole.ADMIN,
            is_active=i % 3 != 0,  # Some inactive
            created_at=now_sao_paulo_naive() - timedelta(days=i),
            updated_at=now_sao_paulo_naive()
        )
        users.append(user)
        db_session.add(user)

    db_session.commit()
    return users


@pytest.fixture
def audit_logs(db_session: Session, admin_user: User):
    """Create audit logs for testing."""
    logs = []
    for i in range(15):
        log = AuditLog(
            id=uuid4(),
            event_type=f"admin_user_{'create' if i % 2 == 0 else 'update'}",
            event_category="admin",
            severity="info",
            user_id=admin_user.id,
            ip_address="127.0.0.1",
            user_agent="TestAgent/1.0",
            event_data={"action": f"test_action_{i}"},
            result="success",
            timestamp=now_sao_paulo_naive() - timedelta(hours=i)
        )
        logs.append(log)
        db_session.add(log)

    db_session.commit()
    return logs


@pytest.fixture
def mock_admin_dependency():
    """Mock the admin user dependency."""
    def _mock_admin():
        user = Mock(spec=User)
        user.id = uuid4()
        user.email = "admin@test.com"
        user.role = UserRole.ADMIN
        user.is_active = True
        return user
    return _mock_admin


@pytest.fixture
def mock_context():
    """Mock RequestContext."""
    context = Mock()
    context.ip_address = "127.0.0.1"
    context.user_agent = "TestClient/1.0"
    return context


# ============================================================================
# USER MANAGEMENT TESTS
# ============================================================================

class TestListUsers:
    """Tests for GET /api/v2/admin/users"""

    def test_list_users_basic(self, client: TestClient, admin_user: User, multiple_users):
        """Test basic user listing."""
        response = client.get("/api/v2/admin/users")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "data" in data
        assert "next_cursor" in data
        assert "has_more" in data
        assert isinstance(data["data"], list)

    def test_list_users_with_limit(self, client: TestClient, admin_user: User, multiple_users):
        """Test user listing with custom limit."""
        response = client.get("/api/v2/admin/users?limit=10")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["data"]) <= 10

    def test_list_users_with_cursor_pagination(self, client: TestClient, admin_user: User, multiple_users):
        """Test cursor-based pagination."""
        # First page
        response1 = client.get("/api/v2/admin/users?limit=5")
        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()

        # Second page with cursor
        if data1["next_cursor"]:
            response2 = client.get(f"/api/v2/admin/users?limit=5&cursor={data1['next_cursor']}")
            assert response2.status_code == status.HTTP_200_OK
            data2 = response2.json()

            # Ensure no duplicate IDs
            ids1 = [u["id"] for u in data1["data"]]
            ids2 = [u["id"] for u in data2["data"]]
            assert len(set(ids1) & set(ids2)) == 0

    def test_list_users_filter_by_role(self, client: TestClient, admin_user: User, multiple_users):
        """Test filtering by role."""
        response = client.get("/api/v2/admin/users?role=doctor")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for user in data["data"]:
            assert user["role"] == "doctor"

    def test_list_users_filter_by_active_status(self, client: TestClient, admin_user: User, multiple_users):
        """Test filtering by active status."""
        response = client.get("/api/v2/admin/users?is_active=true")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for user in data["data"]:
            assert user["is_active"] is True

    def test_list_users_search(self, client: TestClient, admin_user: User, doctor_user: User):
        """Test search functionality."""
        response = client.get("/api/v2/admin/users?search=doctor")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should find the doctor user
        emails = [u["email"] for u in data["data"]]
        assert any("doctor" in email for email in emails)

    def test_list_users_field_selection(self, client: TestClient, admin_user: User, doctor_user: User):
        """Test field selection."""
        response = client.get("/api/v2/admin/users?fields=id,email")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for user in data["data"]:
            assert "id" in user
            assert "email" in user
            # Other fields should not be present (field selection applied)

    def test_list_users_invalid_limit(self, client: TestClient, admin_user: User):
        """Test invalid limit parameter."""
        response = client.get("/api/v2/admin/users?limit=200")

        # Should use max limit or return error
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY]


class TestCreateUser:
    """Tests for POST /api/v2/admin/users"""

    def test_create_user_success(self, client: TestClient, admin_user: User, db_session: Session):
        """Test successful user creation."""
        user_data = {
            "email": "newuser@test.com",
            "password": "SecurePass123",
            "full_name": "New User",
            "role": "doctor",
            "is_active": True
        }

        response = client.post("/api/v2/admin/users", json=user_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["email"] == user_data["email"].lower()
        assert data["full_name"] == user_data["full_name"]
        assert data["role"] == "doctor"
        assert "id" in data

    def test_create_user_duplicate_email(self, client: TestClient, admin_user: User, doctor_user: User):
        """Test creating user with duplicate email."""
        user_data = {
            "email": doctor_user.email,
            "password": "SecurePass123",
            "full_name": "Duplicate User",
            "role": "doctor",
            "is_active": True
        }

        response = client.post("/api/v2/admin/users", json=user_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in response.json()["detail"].lower()

    def test_create_user_weak_password(self, client: TestClient, admin_user: User):
        """Test creating user with weak password."""
        user_data = {
            "email": "weakpass@test.com",
            "password": "weak",
            "full_name": "Weak Password User",
            "role": "doctor",
            "is_active": True
        }

        response = client.post("/api/v2/admin/users", json=user_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_user_invalid_role(self, client: TestClient, admin_user: User):
        """Test creating user with invalid role."""
        user_data = {
            "email": "invalidrole@test.com",
            "password": "SecurePass123",
            "full_name": "Invalid Role User",
            "role": "invalid_role",
            "is_active": True
        }

        response = client.post("/api/v2/admin/users", json=user_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_user_invalid_email(self, client: TestClient, admin_user: User):
        """Test creating user with invalid email."""
        user_data = {
            "email": "not-an-email",
            "password": "SecurePass123",
            "full_name": "Invalid Email User",
            "role": "doctor",
            "is_active": True
        }

        response = client.post("/api/v2/admin/users", json=user_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestGetUser:
    """Tests for GET /api/v2/admin/users/{user_id}"""

    def test_get_user_success(self, client: TestClient, admin_user: User, doctor_user: User):
        """Test successful user retrieval."""
        response = client.get(f"/api/v2/admin/users/{doctor_user.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == str(doctor_user.id)
        assert data["email"] == doctor_user.email
        assert data["role"] == doctor_user.role.value

    def test_get_user_not_found(self, client: TestClient, admin_user: User):
        """Test getting non-existent user."""
        fake_id = uuid4()
        response = client.get(f"/api/v2/admin/users/{fake_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_user_field_selection(self, client: TestClient, admin_user: User, doctor_user: User):
        """Test field selection on user retrieval."""
        response = client.get(f"/api/v2/admin/users/{doctor_user.id}?fields=id,email")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "id" in data
        assert "email" in data

    def test_get_user_invalid_uuid(self, client: TestClient, admin_user: User):
        """Test getting user with invalid UUID."""
        response = client.get("/api/v2/admin/users/not-a-uuid")

        assert response.status_code in {
            status.HTTP_404_NOT_FOUND,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        }


class TestUpdateUser:
    """Tests for PUT /api/v2/admin/users/{user_id}"""

    def test_update_user_success(self, client: TestClient, admin_user: User, doctor_user: User, db_session: Session):
        """Test successful user update."""
        update_data = {
            "full_name": "Updated Doctor Name",
            "is_active": False
        }

        response = client.put(f"/api/v2/admin/users/{doctor_user.id}", json=update_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["full_name"] == update_data["full_name"]
        assert data["is_active"] == update_data["is_active"]

    def test_update_user_email(self, client: TestClient, admin_user: User, doctor_user: User):
        """Test updating user email."""
        update_data = {
            "email": "newemail@test.com"
        }

        response = client.put(f"/api/v2/admin/users/{doctor_user.id}", json=update_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["email"] == update_data["email"].lower()

    def test_update_user_duplicate_email(self, client: TestClient, admin_user: User, doctor_user: User):
        """Test updating to duplicate email."""
        update_data = {
            "email": admin_user.email
        }

        response = client.put(f"/api/v2/admin/users/{doctor_user.id}", json=update_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_user_role(self, client: TestClient, admin_user: User, doctor_user: User):
        """Test updating user role."""
        update_data = {
            "role": "admin"
        }

        response = client.put(f"/api/v2/admin/users/{doctor_user.id}", json=update_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["role"] == "admin"

    def test_update_user_not_found(self, client: TestClient, admin_user: User):
        """Test updating non-existent user."""
        fake_id = uuid4()
        update_data = {"full_name": "New Name"}

        response = client.put(f"/api/v2/admin/users/{fake_id}", json=update_data)

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDeleteUser:
    """Tests for DELETE /api/v2/admin/users/{user_id}"""

    def test_delete_user_success(self, client: TestClient, admin_user: User, doctor_user: User, db_session: Session):
        """Test successful user deletion."""
        response = client.delete(f"/api/v2/admin/users/{doctor_user.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["success"] is True
        assert data["user_id"] == str(doctor_user.id)

        # Verify user is deactivated
        db_session.refresh(doctor_user)
        assert doctor_user.is_active is False

    def test_delete_user_self_deletion(self, client: TestClient, admin_user: User):
        """Test preventing self-deletion."""
        response = client.delete(f"/api/v2/admin/users/{admin_user.id}")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "own account" in response.json()["detail"].lower()

    def test_delete_user_not_found(self, client: TestClient, admin_user: User):
        """Test deleting non-existent user."""
        fake_id = uuid4()
        response = client.delete(f"/api/v2/admin/users/{fake_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestRestoreUser:
    """Tests for POST /api/v2/admin/users/{user_id}/restore"""

    def test_restore_user_success(self, client: TestClient, admin_user: User, inactive_user: User, db_session: Session):
        """Test successful user restoration."""
        response = client.post(f"/api/v2/admin/users/{inactive_user.id}/restore")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["success"] is True

        # Verify user is activated
        db_session.refresh(inactive_user)
        assert inactive_user.is_active is True

    def test_restore_active_user(self, client: TestClient, admin_user: User, doctor_user: User):
        """Test restoring already active user."""
        response = client.post(f"/api/v2/admin/users/{doctor_user.id}/restore")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already active" in response.json()["detail"].lower()

    def test_restore_user_not_found(self, client: TestClient, admin_user: User):
        """Test restoring non-existent user."""
        fake_id = uuid4()
        response = client.post(f"/api/v2/admin/users/{fake_id}/restore")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestResetPassword:
    """Tests for POST /api/v2/admin/users/{user_id}/reset-password"""

    def test_reset_password_success(self, client: TestClient, admin_user: User, doctor_user: User):
        """Test successful password reset."""
        password_data = {
            "new_password": "NewSecurePass123",
            "force_change": True
        }

        response = client.post(
            f"/api/v2/admin/users/{doctor_user.id}/reset-password",
            json=password_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["success"] is True

    def test_reset_password_weak(self, client: TestClient, admin_user: User, doctor_user: User):
        """Test password reset with weak password."""
        password_data = {
            "new_password": "weak",
            "force_change": True
        }

        response = client.post(
            f"/api/v2/admin/users/{doctor_user.id}/reset-password",
            json=password_data
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_reset_password_user_not_found(self, client: TestClient, admin_user: User):
        """Test password reset for non-existent user."""
        fake_id = uuid4()
        password_data = {
            "new_password": "NewSecurePass123",
            "force_change": True
        }

        response = client.post(
            f"/api/v2/admin/users/{fake_id}/reset-password",
            json=password_data
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# AUDIT & STATS TESTS
# ============================================================================

class TestAuditLogs:
    """Tests for GET /api/v2/admin/audit-logs"""

    def test_get_audit_logs(self, client: TestClient, admin_user: User, audit_logs):
        """Test getting audit logs."""
        response = client.get("/api/v2/admin/audit-logs")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "data" in data
        assert "next_cursor" in data
        assert isinstance(data["data"], list)

    def test_get_audit_logs_with_filters(self, client: TestClient, admin_user: User, audit_logs):
        """Test audit logs with filters."""
        response = client.get("/api/v2/admin/audit-logs?event_type=admin_user_create&severity=info")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for log in data["data"]:
            assert log["event_type"] == "admin_user_create"
            assert log["severity"] == "info"

    def test_get_audit_logs_pagination(self, client: TestClient, admin_user: User, audit_logs):
        """Test audit logs pagination."""
        response1 = client.get("/api/v2/admin/audit-logs?limit=5")
        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()

        assert len(data1["data"]) <= 5


class TestUserAuditTrail:
    """Tests for GET /api/v2/admin/users/{user_id}/audit"""

    def test_get_user_audit_trail(self, client: TestClient, admin_user: User, audit_logs):
        """Test getting user audit trail."""
        response = client.get(f"/api/v2/admin/users/{admin_user.id}/audit")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "data" in data

    def test_get_user_audit_trail_not_found(self, client: TestClient, admin_user: User):
        """Test audit trail for non-existent user."""
        fake_id = uuid4()
        response = client.get(f"/api/v2/admin/users/{fake_id}/audit")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUserStatistics:
    """Tests for GET /api/v2/admin/stats/users"""

    def test_get_user_statistics(self, client: TestClient, admin_user: User, multiple_users):
        """Test getting user statistics."""
        response = client.get("/api/v2/admin/stats/users")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "total_users" in data
        assert "active_users" in data
        assert "inactive_users" in data
        assert "by_role" in data
        assert "recent_registrations" in data

        assert data["total_users"] > 0
        assert isinstance(data["by_role"], dict)


class TestActivityStatistics:
    """Tests for GET /api/v2/admin/stats/activity"""

    def test_get_activity_statistics(self, client: TestClient, admin_user: User, audit_logs):
        """Test getting activity statistics."""
        response = client.get("/api/v2/admin/stats/activity")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "total_events" in data
        assert "events_today" in data
        assert "events_this_week" in data
        assert "events_this_month" in data
        assert "by_event_type" in data
        assert "by_severity" in data


# ============================================================================
# BULK OPERATIONS TESTS
# ============================================================================

class TestBulkUpdate:
    """Tests for POST /api/v2/admin/users/bulk-update"""

    def test_bulk_update_success(self, client: TestClient, admin_user: User, multiple_users, db_session: Session):
        """Test successful bulk update."""
        user_ids = [str(u.id) for u in multiple_users[:3]]

        bulk_data = {
            "user_ids": user_ids,
            "updates": {
                "is_active": False
            }
        }

        response = client.post("/api/v2/admin/users/bulk-update", json=bulk_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["success"] is True
        assert data["successful"] == 3
        assert data["failed"] == 0

    def test_bulk_update_exceeds_limit(self, client: TestClient, admin_user: User, multiple_users):
        """Test bulk update exceeding limit."""
        user_ids = [str(uuid4()) for _ in range(101)]

        bulk_data = {
            "user_ids": user_ids,
            "updates": {"is_active": False}
        }

        response = client.post("/api/v2/admin/users/bulk-update", json=bulk_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_update_with_errors(self, client: TestClient, admin_user: User, doctor_user: User):
        """Test bulk update with some failures."""
        user_ids = [str(doctor_user.id), str(uuid4())]  # One valid, one invalid

        bulk_data = {
            "user_ids": user_ids,
            "updates": {"is_active": False}
        }

        response = client.post("/api/v2/admin/users/bulk-update", json=bulk_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["successful"] == 1
        assert data["failed"] == 1
        assert len(data["errors"]) == 1


class TestBulkDelete:
    """Tests for POST /api/v2/admin/users/bulk-delete"""

    def test_bulk_delete_success(self, client: TestClient, admin_user: User, multiple_users, db_session: Session):
        """Test successful bulk delete."""
        user_ids = [str(u.id) for u in multiple_users[:3]]

        bulk_data = {
            "user_ids": user_ids,
            "reason": "Test cleanup"
        }

        response = client.post("/api/v2/admin/users/bulk-delete", json=bulk_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["success"] is True
        assert data["successful"] == 3

    def test_bulk_delete_exceeds_limit(self, client: TestClient, admin_user: User):
        """Test bulk delete exceeding limit."""
        user_ids = [str(uuid4()) for _ in range(51)]

        bulk_data = {
            "user_ids": user_ids,
            "reason": "Test"
        }

        response = client.post("/api/v2/admin/users/bulk-delete", json=bulk_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_delete_self_prevention(self, client: TestClient, admin_user: User):
        """Test preventing self-deletion in bulk."""
        bulk_data = {
            "user_ids": [str(admin_user.id)],
            "reason": "Test"
        }

        response = client.post("/api/v2/admin/users/bulk-delete", json=bulk_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestExportUsers:
    """Tests for POST /api/v2/admin/users/export"""

    def test_export_users_csv(self, client: TestClient, admin_user: User, multiple_users):
        """Test exporting users to CSV."""
        export_data = {
            "format": "csv",
            "fields": ["id", "email", "full_name", "role"]
        }

        response = client.post("/api/v2/admin/users/export", json=export_data)

        assert response.status_code == status.HTTP_200_OK
        assert "text/csv" in response.headers["content-type"]

    def test_export_users_json(self, client: TestClient, admin_user: User, multiple_users):
        """Test exporting users to JSON."""
        export_data = {
            "format": "json"
        }

        response = client.post("/api/v2/admin/users/export", json=export_data)

        assert response.status_code == status.HTTP_200_OK
        assert "application/json" in response.headers["content-type"]

    def test_export_users_with_filters(self, client: TestClient, admin_user: User, multiple_users):
        """Test exporting users with filters."""
        export_data = {
            "format": "json"
        }

        response = client.post("/api/v2/admin/users/export?role=doctor", json=export_data)

        assert response.status_code == status.HTTP_200_OK


# ============================================================================
# SEARCH & FILTER TESTS
# ============================================================================

class TestSearchUsers:
    """Tests for POST /api/v2/admin/users/search"""

    def test_search_users_by_query(self, client: TestClient, admin_user: User, doctor_user: User):
        """Test searching users by query."""
        search_data = {
            "query": "doctor"
        }

        response = client.post("/api/v2/admin/users/search", json=search_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "data" in data

    def test_search_users_multiple_filters(self, client: TestClient, admin_user: User, multiple_users):
        """Test searching with multiple filters."""
        search_data = {
            "role": "doctor",
            "is_active": True
        }

        response = client.post("/api/v2/admin/users/search", json=search_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for user in data["data"]:
            assert user["role"] == "doctor"
            assert user["is_active"] is True

    def test_search_users_date_range(self, client: TestClient, admin_user: User, multiple_users):
        """Test searching with date range."""
        search_data = {
            "created_after": (now_sao_paulo_naive() - timedelta(days=30)).isoformat(),
            "created_before": now_sao_paulo_naive().isoformat()
        }

        response = client.post("/api/v2/admin/users/search", json=search_data)

        assert response.status_code == status.HTTP_200_OK


class TestListActiveUsers:
    """Tests for GET /api/v2/admin/users/active"""

    def test_list_active_users(self, client: TestClient, admin_user: User, multiple_users):
        """Test listing active users."""
        response = client.get("/api/v2/admin/users/active")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for user in data["data"]:
            assert user["is_active"] is True


class TestListInactiveUsers:
    """Tests for GET /api/v2/admin/users/inactive"""

    def test_list_inactive_users(self, client: TestClient, admin_user: User, multiple_users):
        """Test listing inactive users."""
        response = client.get("/api/v2/admin/users/inactive")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for user in data["data"]:
            assert user["is_active"] is False


# ============================================================================
# ROLE MANAGEMENT TESTS (Placeholder)
# ============================================================================

class TestRoleManagement:
    """Tests for role management endpoints (placeholder)"""

    def test_list_roles(self, client: TestClient, admin_user: User):
        """Test listing roles."""
        response = client.get("/api/v2/admin/roles")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "data" in data

    def test_create_role_not_implemented(self, client: TestClient, admin_user: User):
        """Test role creation returns not implemented."""
        role_data = {
            "name": "nurse",
            "description": "Nurse role",
            "permissions": []
        }

        response = client.post("/api/v2/admin/roles", json=role_data)

        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED


# ============================================================================
# PERMISSION MANAGEMENT TESTS (Placeholder)
# ============================================================================

class TestPermissionManagement:
    """Tests for permission management endpoints (placeholder)"""

    def test_list_permissions(self, client: TestClient, admin_user: User):
        """Test listing permissions."""
        response = client.get("/api/v2/admin/permissions")

        assert response.status_code == status.HTTP_200_OK

    def test_assign_permissions_post_not_allowed(self, client: TestClient, admin_user: User, doctor_user: User):
        """Test POST permission assignment is not allowed (use PUT)."""
        perm_data = {
            "permissions": ["read_patients"]
        }

        response = client.post(f"/api/v2/admin/users/{doctor_user.id}/permissions", json=perm_data)

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
