"""
Integration tests for API contract validation - Testing all 5 fixed endpoints.

This module validates that API endpoints return the correct schema structure
as expected by frontend consumers.

Test Coverage:
1. GET /api/v2/admin/users - Paginated response {items, total, page, size}
2. GET /api/v2/admin/users/{id}/activity - Activity data with logs
3. GET /api/v2/auth/notifications - {notifications: [...], unread_count}
4. GET /api/v2/admin/stats - System stats with trend deltas
5. GET /api/v2/admin/system-stats - System stats response

Related Files:
- backend-hormonia/app/api/v2/admin/users.py
- backend-hormonia/app/api/v2/auth.py
- backend-hormonia/app/api/v2/admin/system_stats.py
"""
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import Request
from sqlalchemy.orm import Session

from app.dependencies import RequestContext, get_request_context
from app.dependencies.auth_dependencies import (
    get_current_user,
    get_current_user_from_session,
    get_current_user_object_from_session,
    get_optional_user,
    get_permissions_for_role,
)
from app.main import app
from app.middleware.csrf import get_csrf_token
from app.models.user import User, UserRole
from app.models.audit_log import AuditLog, AuditEventType
from app.utils.security import get_password_hash


from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
@pytest.fixture
def admin_user(db_session: Session):
    """Create admin user for testing."""
    user = User(
        id=uuid4(),
        email="admin@test.com",
        hashed_password=get_password_hash("admin123"),
        full_name="Admin User",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=now_sao_paulo_naive()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def regular_users(db_session: Session):
    """Create multiple regular users for pagination testing."""
    users = []
    for i in range(25):
        user = User(
            id=uuid4(),
            email=f"user{i}@test.com",
            hashed_password=get_password_hash(f"pass{i}"),
            full_name=f"User {i}",
            role=UserRole.DOCTOR if i % 2 == 0 else UserRole.ADMIN,
            is_active=i % 3 != 0,  # Mix of active/inactive
            created_at=now_sao_paulo_naive() - timedelta(days=i)
        )
        users.append(user)
        db_session.add(user)

    db_session.commit()
    return users


@pytest.fixture
def user_activity(db_session: Session, regular_users):
    """Create audit logs for user activity testing."""
    logs = []
    user = regular_users[0]
    event_types = list(AuditEventType)

    for i in range(10):
        log = AuditLog(
            id=uuid4(),
            user_id=user.id,
            event_type=event_types[i % len(event_types)],
            event_category="SYSTEM",
            severity="info",
            ip_address="127.0.0.1",
            user_agent="TestAgent/1.0",
            event_data={"action": f"test_action_{i}"},
            result="success",
            created_at=now_sao_paulo_naive() - timedelta(hours=i)
        )
        logs.append(log)
        db_session.add(log)

    db_session.commit()
    return logs


@pytest.fixture
def auth_headers(admin_user, admin_token):
    """Get authentication headers for admin user."""
    role = admin_user.role.value if hasattr(admin_user.role, "value") else str(admin_user.role)
    session_user = {
        "id": str(admin_user.id),
        "email": admin_user.email,
        "full_name": admin_user.full_name,
        "role": role,
        "is_active": admin_user.is_active,
        "firebase_uid": getattr(admin_user, "firebase_uid", None),
        "permissions": get_permissions_for_role(role),
    }
    session_id = f"test-session-{admin_user.id}"

    async def _override_session(request: Request):
        request.state.user_id = session_user.get("id")
        request.state.user_role = session_user.get("role")
        request.state.session_id = session_id
        return session_user

    async def _override_current_user(request: Request):
        request.state.user = admin_user
        request.state.user_id = str(admin_user.id)
        request.state.user_role = role
        request.state.session_id = session_id
        return admin_user

    async def _override_optional_user(credentials=None, services=None):
        return admin_user

    async def _override_request_context(request: Request):
        return RequestContext(
            ip_address="127.0.0.1",
            user_agent="pytest",
            user_id=admin_user.id,
            session_id=session_id,
        )

    app.dependency_overrides[get_current_user_from_session] = _override_session
    app.dependency_overrides[get_current_user_object_from_session] = lambda: admin_user
    app.dependency_overrides[get_current_user] = _override_current_user
    app.dependency_overrides[get_optional_user] = _override_optional_user
    app.dependency_overrides[get_request_context] = _override_request_context

    csrf_token = get_csrf_token()
    headers = {
        "X-Session-ID": session_id,
        "Authorization": f"Bearer {admin_token}",
        "X-CSRF-Token": csrf_token,
        "Cookie": f"csrf_token={csrf_token}",
    }
    yield headers
    app.dependency_overrides.pop(get_current_user_from_session, None)
    app.dependency_overrides.pop(get_current_user_object_from_session, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_optional_user, None)
    app.dependency_overrides.pop(get_request_context, None)


class TestUserListAPIContract:
    """Test GET /api/v2/admin/users endpoint contract."""

    def test_user_list_returns_paginated_response(
        self, client, auth_headers, regular_users
    ):
        """
        CRITICAL: Verify user list returns correct pagination schema.

        Expected Response:
        {
            "users": [...],  # Array of UserResponse objects (NOT "items")
            "total": int,
            "page": int,
            "size": int,
            "total_pages": int,
            "has_next": bool,
            "has_previous": bool
        }
        """
        response = client.get(
            "/api/v2/admin/users",
            headers=auth_headers,
            params={"page": 1, "size": 10}
        )

        assert response.status_code == 200
        data = response.json()

        # Validate schema structure
        assert "users" in data, "Response must have 'users' field (NOT 'items')"
        assert "total" in data, "Response must have 'total' field"
        assert "page" in data, "Response must have 'page' field"
        assert "size" in data, "Response must have 'size' field"
        assert "total_pages" in data, "Response must have 'total_pages' field"
        assert "has_next" in data, "Response must have 'has_next' field"
        assert "has_previous" in data, "Response must have 'has_previous' field"

        # Validate data types
        assert isinstance(data["users"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["page"], int)
        assert isinstance(data["size"], int)
        assert isinstance(data["total_pages"], int)
        assert isinstance(data["has_next"], bool)
        assert isinstance(data["has_previous"], bool)

        # Validate pagination logic
        assert data["page"] == 1
        assert data["size"] == 10
        assert len(data["users"]) <= 10
        assert data["total"] == 26  # 25 regular + 1 admin
        assert data["total_pages"] == 3  # ceil(26/10)
        assert data["has_next"] is True
        assert data["has_previous"] is False

    def test_user_list_pagination_page_2(
        self, client, auth_headers, regular_users
    ):
        """Verify second page pagination works correctly."""
        response = client.get(
            "/api/v2/admin/users",
            headers=auth_headers,
            params={"page": 2, "size": 10}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["page"] == 2
        assert data["has_next"] is True
        assert data["has_previous"] is True
        assert len(data["users"]) <= 10

    def test_user_list_with_filters(
        self, client, auth_headers, regular_users
    ):
        """Verify filtering works with pagination."""
        response = client.get(
            "/api/v2/admin/users",
            headers=auth_headers,
            params={"role": "doctor", "is_active": True, "page": 1, "size": 20}
        )

        assert response.status_code == 200
        data = response.json()

        # Validate all users are doctors and active
        for user in data["users"]:
            assert user["role"] == "doctor"
            assert user["is_active"] is True


class TestUserActivityAPIContract:
    """Test GET /api/v2/admin/users/{id}/activity endpoint contract."""

    def test_user_activity_returns_activity_logs(
        self, client, auth_headers, regular_users, user_activity
    ):
        """
        CRITICAL: Verify user activity endpoint returns activity data.

        Expected Response:
        {
            "user_id": str,
            "activities": [...],  # Array of activity log objects
            "total": int,
            "period": {
                "start": str (ISO datetime),
                "end": str (ISO datetime)
            }
        }
        """
        user = regular_users[0]
        response = client.get(
            f"/api/v2/admin/users/{user.id}/activity",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Validate schema structure
        assert "data" in data
        assert "next_cursor" in data
        assert "has_more" in data
        assert "total" in data

        # Validate data types
        assert isinstance(data["data"], list)
        assert isinstance(data["has_more"], bool)
        assert data["total"] in (None, len(user_activity))
        assert len(data["data"]) == len(user_activity)

        # Validate activity structure
        if len(data["data"]) > 0:
            activity = data["data"][0]
            assert "id" in activity
            assert "user_id" in activity
            assert "action" in activity
            assert "resource" in activity
            assert "details" in activity
            assert "timestamp" in activity
            assert "ip_address" in activity

    def test_user_activity_with_date_range(
        self, client, auth_headers, regular_users, user_activity
    ):
        """Verify activity filtering by date range."""
        user = regular_users[0]
        start_date = (now_sao_paulo_naive() - timedelta(hours=5)).isoformat()
        end_date = now_sao_paulo_naive().isoformat()

        response = client.get(
            f"/api/v2/admin/users/{user.id}/activity",
            headers=auth_headers,
            params={"start_date": start_date, "end_date": end_date}
        )

        assert response.status_code == 200
        data = response.json()

        # Should have activities within the range
        assert len(data["data"]) > 0
        assert len(data["data"]) <= len(user_activity)


class TestNotificationsAPIContract:
    """Test GET /api/v2/auth/notifications endpoint contract."""

    def test_notifications_returns_correct_schema(
        self, client, auth_headers
    ):
        """
        CRITICAL: Verify notifications endpoint returns correct schema.

        Expected Response:
        {
            "data": [...],  # Array of notification objects
            "items": [...],  # Backwards-compatible alias of data
            "next_cursor": str | null,
            "has_more": bool,
            "total": int | null,
            "unread_count": int
        }
        """
        response = client.get(
            "/api/v2/auth/notifications",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Validate schema structure
        assert "data" in data, "Response must have 'data' field"
        assert "items" in data, "Response must have 'items' field"
        assert "next_cursor" in data, "Response must have 'next_cursor' field"
        assert "has_more" in data, "Response must have 'has_more' field"
        assert "total" in data, "Response must have 'total' field"
        assert "unread_count" in data, "Response must have 'unread_count' field"

        # Validate data types
        assert isinstance(data["data"], list)
        assert isinstance(data["items"], list)
        assert isinstance(data["has_more"], bool)
        assert data["total"] is None or isinstance(data["total"], int)
        assert isinstance(data["unread_count"], int)

        notifications = data["items"] or data["data"]

        # Validate notification structure
        if len(notifications) > 0:
            notification = notifications[0]
            assert "id" in notification
            assert "title" in notification
            assert "message" in notification
            assert "type" in notification
            assert "read" in notification
            assert "created_at" in notification

    def test_notifications_unread_count_accuracy(
        self, client, auth_headers
    ):
        """Verify unread_count is accurate."""
        response = client.get(
            "/api/v2/auth/notifications",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Count unread notifications
        notifications = data["items"] or data["data"]
        unread_notifications = [n for n in notifications if not n["read"]]
        assert data["unread_count"] == len(unread_notifications)


class TestSystemStatsAPIContract:
    """Test GET /api/v2/admin/system-stats endpoint contract."""

    def test_system_stats_returns_current_schema(
        self, client, auth_headers
    ):
        """
        CRITICAL: Verify system-stats endpoint returns current schema.

        Expected Response:
        {
            "users": {...},
            "appointments": {...},
            "revenue": {...},
            "system": {...},
            "generated_at": str
        }
        """
        response = client.get(
            "/api/v2/admin/system-stats",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Validate top-level structure
        assert "users" in data
        assert "appointments" in data
        assert "revenue" in data
        assert "system" in data
        assert "generated_at" in data

        # Validate user metrics
        users = data["users"]
        assert "total" in users
        assert "active" in users
        assert "inactive" in users
        assert "new_this_month" in users

        # Validate system metrics
        system = data["system"]
        assert "uptime" in system
        assert "response_time_ms" in system
        assert "error_rate" in system
        assert "active_sessions" in system

    def test_system_stats_caching(
        self, client, auth_headers
    ):
        """Verify system stats are cached for performance."""
        # First request
        response1 = client.get(
            "/api/v2/admin/system-stats",
            headers=auth_headers
        )
        assert response1.status_code == 200

        # Second request (should be cached)
        response2 = client.get(
            "/api/v2/admin/system-stats",
            headers=auth_headers
        )
        assert response2.status_code == 200

        # Both responses should be identical (cached)
        assert response1.json() == response2.json()


class TestAPIPerformance:
    """Performance tests for API endpoints."""

    def test_user_list_response_time(
        self, client, auth_headers, regular_users
    ):
        """Verify user list responds within acceptable time."""
        import time

        start = time.time()
        response = client.get(
            "/api/v2/admin/users",
            headers=auth_headers,
            params={"page": 1, "size": 20}
        )
        end = time.time()

        assert response.status_code == 200
        assert (end - start) < 1.0, "User list should respond in < 1 second"

    def test_system_stats_response_time(
        self, client, auth_headers
    ):
        """Verify system stats responds within acceptable time."""
        import time

        start = time.time()
        response = client.get(
            "/api/v2/admin/system-stats",
            headers=auth_headers
        )
        end = time.time()

        assert response.status_code == 200
        assert (end - start) < 0.5, "System stats should respond in < 500ms"


class TestErrorHandling:
    """Test error handling across all endpoints."""

    def test_unauthorized_access_returns_401(self, client):
        """Verify endpoints require authentication."""
        endpoints = [
            "/api/v2/admin/users",
            "/api/v2/admin/system-stats",
            "/api/v2/auth/notifications"
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code in [401, 403], \
                f"{endpoint} should require authentication"

    def test_invalid_user_id_returns_404(
        self, client, auth_headers
    ):
        """Verify invalid user ID returns 404."""
        fake_id = uuid4()
        response = client.get(
            f"/api/v2/admin/users/{fake_id}/activity",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_invalid_pagination_returns_error(
        self, client, auth_headers
    ):
        """Verify invalid pagination parameters are handled."""
        response = client.get(
            "/api/v2/admin/users",
            headers=auth_headers,
            params={"page": 0, "size": -1}  # Invalid values
        )

        assert response.status_code == 422  # Validation error


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
