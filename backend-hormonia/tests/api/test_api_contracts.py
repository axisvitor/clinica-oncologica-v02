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
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from uuid import uuid4

from app.main import app
from app.models.user import User, UserRole
from app.models.audit import AuditLog
from app.utils.security import get_password_hash


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


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
        created_at=datetime.utcnow()
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
            created_at=datetime.utcnow() - timedelta(days=i)
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

    for i in range(10):
        log = AuditLog(
            id=uuid4(),
            user_id=user.id,
            event_type=f"action_{i}",
            event_category="user_action",
            severity="info",
            ip_address="127.0.0.1",
            user_agent="TestAgent/1.0",
            event_data={"action": f"test_action_{i}"},
            result="success",
            created_at=datetime.utcnow() - timedelta(hours=i)
        )
        logs.append(log)
        db_session.add(log)

    db_session.commit()
    return logs


@pytest.fixture
def auth_headers(client, admin_user):
    """Get authentication headers for admin user."""
    # Note: In real implementation, use proper Firebase token
    # This is a simplified version for testing
    return {
        "Authorization": f"Bearer test_token_for_{admin_user.id}"
    }


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
        assert "user_id" in data
        assert "activities" in data
        assert "total" in data

        # Validate data types
        assert isinstance(data["activities"], list)
        assert isinstance(data["total"], int)
        assert data["total"] == len(user_activity)

        # Validate activity structure
        if len(data["activities"]) > 0:
            activity = data["activities"][0]
            assert "event_type" in activity
            assert "event_category" in activity
            assert "severity" in activity
            assert "created_at" in activity
            assert "ip_address" in activity

    def test_user_activity_with_date_range(
        self, client, auth_headers, regular_users, user_activity
    ):
        """Verify activity filtering by date range."""
        user = regular_users[0]
        start_date = (datetime.utcnow() - timedelta(hours=5)).isoformat()
        end_date = datetime.utcnow().isoformat()

        response = client.get(
            f"/api/v2/admin/users/{user.id}/activity",
            headers=auth_headers,
            params={"start_date": start_date, "end_date": end_date}
        )

        assert response.status_code == 200
        data = response.json()

        # Should have activities within the range
        assert data["total"] > 0
        assert data["total"] <= len(user_activity)


class TestNotificationsAPIContract:
    """Test GET /api/v2/auth/notifications endpoint contract."""

    def test_notifications_returns_correct_schema(
        self, client, auth_headers
    ):
        """
        CRITICAL: Verify notifications endpoint returns correct schema.

        Expected Response:
        {
            "notifications": [...],  # Array of notification objects (NOT "items")
            "total": int,
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
        assert "notifications" in data, "Response must have 'notifications' field"
        assert "total" in data, "Response must have 'total' field"
        assert "unread_count" in data, "Response must have 'unread_count' field"

        # Validate data types
        assert isinstance(data["notifications"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["unread_count"], int)

        # Validate notification structure
        if len(data["notifications"]) > 0:
            notification = data["notifications"][0]
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
        unread_notifications = [n for n in data["notifications"] if not n["read"]]
        assert data["unread_count"] == len(unread_notifications)


class TestSystemStatsAPIContract:
    """Test GET /api/v2/admin/stats and system-stats endpoint contracts."""

    def test_system_stats_returns_trend_deltas(
        self, client, auth_headers
    ):
        """
        CRITICAL: Verify stats endpoint includes trend deltas.

        Expected Response:
        {
            "system": {...},
            "users": {
                "total": int,
                "active_now": int,
                "by_role": {...},
                "trend": {  # NEW: Must include trend data
                    "total_change": int,
                    "total_change_percent": float,
                    "active_change": int
                }
            },
            "database": {...},
            "timestamp": str
        }
        """
        response = client.get(
            "/api/v2/admin/stats",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Validate top-level structure
        assert "system" in data
        assert "users" in data
        assert "database" in data
        assert "timestamp" in data

        # Validate system metrics
        system = data["system"]
        assert "cpu_percent" in system
        assert "memory_percent" in system
        assert "disk_percent" in system
        assert "uptime_seconds" in system

        # Validate user metrics with trends
        users = data["users"]
        assert "total" in users
        assert "active_now" in users
        assert "by_role" in users
        assert "trend" in users, "CRITICAL: Must include trend data"

        # Validate trend structure
        trend = users["trend"]
        assert "total_change" in trend
        assert "total_change_percent" in trend
        assert isinstance(trend["total_change"], int)
        assert isinstance(trend["total_change_percent"], (int, float))

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
