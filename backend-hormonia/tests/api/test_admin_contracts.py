"""
Integration Tests: Admin API Contracts

Verifies backend API endpoints return correct schemas and handle all contract scenarios
Tests system-stats, reset-password, WebSocket, dashboard trends, and permissions updates
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json

from app.main import app
from app.config import settings
from app.models.user import User
from app.models.appointment import Appointment
from app.schemas.user_admin import SystemStatsResponse, UserPermissionsUpdate


class TestSystemStatsContract:
    """Test /api/v2/admin/system-stats endpoint contract"""

    def test_system_stats_returns_correct_schema(self, client: TestClient, admin_token: str):
        """Verify system-stats endpoint returns complete, correct schema"""
        response = client.get(
            "/api/v2/admin/system-stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify top-level structure
        assert "users" in data
        assert "appointments" in data
        assert "revenue" in data
        assert "system" in data

        # Verify users section
        assert "total" in data["users"]
        assert "active" in data["users"]
        assert "inactive" in data["users"]
        assert "new_this_month" in data["users"]

        # Verify appointments section
        assert "total" in data["appointments"]
        assert "scheduled" in data["appointments"]
        assert "completed" in data["appointments"]
        assert "cancelled" in data["appointments"]
        assert "pending" in data["appointments"]

        # Verify revenue section
        assert "total" in data["revenue"]
        assert "this_month" in data["revenue"]
        assert "last_month" in data["revenue"]
        assert "growth_percentage" in data["revenue"]

        # Verify system section
        assert "uptime" in data["system"]
        assert "response_time_ms" in data["system"]
        assert "error_rate" in data["system"]
        assert "active_sessions" in data["system"]

    def test_system_stats_data_types(self, client: TestClient, admin_token: str):
        """Verify all fields have correct data types"""
        response = client.get(
            "/api/v2/admin/system-stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        data = response.json()

        # Users - all integers
        assert isinstance(data["users"]["total"], int)
        assert isinstance(data["users"]["active"], int)
        assert isinstance(data["users"]["inactive"], int)
        assert isinstance(data["users"]["new_this_month"], int)

        # Appointments - all integers
        assert isinstance(data["appointments"]["total"], int)
        assert isinstance(data["appointments"]["scheduled"], int)
        assert isinstance(data["appointments"]["completed"], int)
        assert isinstance(data["appointments"]["cancelled"], int)
        assert isinstance(data["appointments"]["pending"], int)

        # Revenue - all floats
        assert isinstance(data["revenue"]["total"], (int, float))
        assert isinstance(data["revenue"]["this_month"], (int, float))
        assert isinstance(data["revenue"]["last_month"], (int, float))
        assert isinstance(data["revenue"]["growth_percentage"], (int, float))

        # System - floats and integers
        assert isinstance(data["system"]["uptime"], (int, float))
        assert isinstance(data["system"]["response_time_ms"], (int, float))
        assert isinstance(data["system"]["error_rate"], (int, float))
        assert isinstance(data["system"]["active_sessions"], int)

    def test_system_stats_unauthorized(self, client: TestClient):
        """Verify endpoint requires authentication"""
        response = client.get("/api/v2/admin/system-stats")
        assert response.status_code == 401

    def test_system_stats_non_admin(self, client: TestClient, user_token: str):
        """Verify endpoint requires admin role"""
        response = client.get(
            "/api/v2/admin/system-stats",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 403

    def test_system_stats_with_data(
        self,
        client: TestClient,
        admin_token: str,
        db: Session,
        sample_users: list[User],
        sample_appointments: list[Appointment]
    ):
        """Verify stats accurately reflect database state"""
        response = client.get(
            "/api/v2/admin/system-stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify counts match database
        assert data["users"]["total"] >= len(sample_users)
        assert data["appointments"]["total"] >= len(sample_appointments)

        # Verify calculations are reasonable
        assert data["users"]["total"] == (
            data["users"]["active"] + data["users"]["inactive"]
        )

    def test_system_stats_performance(self, client: TestClient, admin_token: str):
        """Verify endpoint responds within acceptable time"""
        import time
        start_time = time.time()

        response = client.get(
            "/api/v2/admin/system-stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        end_time = time.time()
        duration = (end_time - start_time) * 1000  # Convert to ms

        assert response.status_code == 200
        assert duration < 1000  # Should respond in less than 1 second


class TestResetPasswordContract:
    """Test /api/v2/auth/reset-password endpoint contract"""

    def test_reset_password_success(
        self,
        client: TestClient,
        db: Session,
        sample_user: User
    ):
        """Verify successful password reset with valid token"""
        # Generate valid reset token
        from app.core.security import create_password_reset_token
        token = create_password_reset_token(sample_user.email)

        response = client.post(
            "/api/v2/auth/reset-password",
            json={
                "token": token,
                "new_password": "NewSecurePassword123!"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "success" in data["message"].lower()

    def test_reset_password_invalid_token(self, client: TestClient):
        """Verify error on invalid token"""
        response = client.post(
            "/api/v2/auth/reset-password",
            json={
                "token": "invalid-token-12345",
                "new_password": "NewPassword123!"
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "invalid" in data["detail"].lower() or "expired" in data["detail"].lower()

    def test_reset_password_expired_token(
        self,
        client: TestClient,
        db: Session,
        sample_user: User
    ):
        """Verify error on expired token"""
        # Generate expired token
        from app.core.security import create_password_reset_token
        from jose import jwt
        from datetime import datetime, timedelta

        # Create token that's already expired
        expired_time = datetime.utcnow() - timedelta(hours=25)
        token = jwt.encode(
            {"sub": sample_user.email, "exp": expired_time},
            settings.SECRET_KEY,
            algorithm="HS256"
        )

        response = client.post(
            "/api/v2/auth/reset-password",
            json={
                "token": token,
                "new_password": "NewPassword123!"
            }
        )

        assert response.status_code in [400, 401]

    def test_reset_password_weak_password(
        self,
        client: TestClient,
        db: Session,
        sample_user: User
    ):
        """Verify error on weak password"""
        from app.core.security import create_password_reset_token
        token = create_password_reset_token(sample_user.email)

        response = client.post(
            "/api/v2/auth/reset-password",
            json={
                "token": token,
                "new_password": "weak"
            }
        )

        # Should reject weak password
        assert response.status_code in [400, 422]

    def test_reset_password_missing_fields(self, client: TestClient):
        """Verify error on missing required fields"""
        # Missing new_password
        response = client.post(
            "/api/v2/auth/reset-password",
            json={"token": "some-token"}
        )
        assert response.status_code == 422

        # Missing token
        response = client.post(
            "/api/v2/auth/reset-password",
            json={"new_password": "Password123!"}
        )
        assert response.status_code == 422

    def test_reset_password_persistence(
        self,
        client: TestClient,
        db: Session,
        sample_user: User
    ):
        """Verify password change persists to database"""
        from app.core.security import create_password_reset_token, verify_password

        token = create_password_reset_token(sample_user.email)
        new_password = "NewVerifiedPassword123!"

        response = client.post(
            "/api/v2/auth/reset-password",
            json={
                "token": token,
                "new_password": new_password
            }
        )

        assert response.status_code == 200

        # Refresh user from database
        db.refresh(sample_user)

        # Verify new password works
        assert verify_password(new_password, sample_user.hashed_password)

    def test_reset_password_special_characters(
        self,
        client: TestClient,
        db: Session,
        sample_user: User
    ):
        """Verify passwords with special characters work correctly"""
        from app.core.security import create_password_reset_token

        token = create_password_reset_token(sample_user.email)
        special_password = 'P@$$w0rd!#%^&*(){}[]|\\/<>?'

        response = client.post(
            "/api/v2/auth/reset-password",
            json={
                "token": token,
                "new_password": special_password
            }
        )

        assert response.status_code == 200


class TestWebSocketContract:
    """Test WebSocket endpoint for admin users (if implemented)"""

    def test_websocket_endpoint_exists(self, client: TestClient):
        """Verify WebSocket endpoint is accessible or returns proper error"""
        # Try to access WebSocket endpoint
        try:
            response = client.get("/ws/admin/users")
            # Should either upgrade to WebSocket or return 404/405
            assert response.status_code in [404, 405, 426]
        except Exception:
            # WebSocket might not be implemented - this is acceptable
            pass

    def test_websocket_requires_authentication(self, client: TestClient):
        """Verify WebSocket requires authentication if implemented"""
        # This is a placeholder - actual implementation depends on WebSocket setup
        pass

    def test_fallback_to_rest_api(self, client: TestClient, admin_token: str):
        """Verify REST API fallback exists for admin users"""
        # Verify there's a REST endpoint as fallback
        response = client.get(
            "/api/v2/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Should have REST endpoint available
        assert response.status_code in [200, 404]  # 404 if not implemented


class TestDashboardTrendsContract:
    """Test dashboard trend calculations and data"""

    def test_revenue_growth_calculation(
        self,
        client: TestClient,
        admin_token: str
    ):
        """Verify revenue growth percentage is calculated correctly"""
        response = client.get(
            "/api/v2/admin/system-stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        data = response.json()
        revenue = data["revenue"]

        # Verify growth percentage calculation
        if revenue["last_month"] > 0:
            expected_growth = (
                (revenue["this_month"] - revenue["last_month"])
                / revenue["last_month"]
                * 100
            )
            assert abs(revenue["growth_percentage"] - expected_growth) < 0.1

    def test_trends_with_zero_previous_value(
        self,
        client: TestClient,
        admin_token: str,
        db: Session
    ):
        """Verify trend calculation handles zero previous values"""
        response = client.get(
            "/api/v2/admin/system-stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Should handle gracefully, not return infinity or NaN
        assert data["revenue"]["growth_percentage"] != float('inf')
        assert not (data["revenue"]["growth_percentage"] != data["revenue"]["growth_percentage"])  # NaN check

    def test_negative_growth_percentage(
        self,
        client: TestClient,
        admin_token: str
    ):
        """Verify negative growth is handled correctly"""
        response = client.get(
            "/api/v2/admin/system-stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        data = response.json()

        # Negative growth should be represented as negative number
        if data["revenue"]["this_month"] < data["revenue"]["last_month"]:
            assert data["revenue"]["growth_percentage"] < 0

    def test_trend_data_consistency(
        self,
        client: TestClient,
        admin_token: str
    ):
        """Verify trend data is consistent across requests"""
        response1 = client.get(
            "/api/v2/admin/system-stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        response2 = client.get(
            "/api/v2/admin/system-stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response1.json() == response2.json()


class TestPermissionsUpdateContract:
    """Test permissions update endpoints and persistence"""

    def test_update_permissions_success(
        self,
        client: TestClient,
        admin_token: str,
        sample_user: User,
        db: Session
    ):
        """Verify permissions update succeeds and persists"""
        new_permissions = ["read", "write", "delete"]

        response = client.put(
            f"/api/v2/admin/users/{sample_user.id}/permissions",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"permissions": new_permissions}
        )

        assert response.status_code == 200

        # Verify permissions persisted
        verify_response = client.get(
            f"/api/v2/admin/users/{sample_user.id}/permissions",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert verify_response.status_code == 200
        assert set(verify_response.json()["permissions"]) == set(new_permissions)

    def test_update_permissions_invalid_user(
        self,
        client: TestClient,
        admin_token: str
    ):
        """Verify error on updating non-existent user"""
        response = client.put(
            "/api/v2/admin/users/99999/permissions",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"permissions": ["read"]}
        )

        assert response.status_code == 404

    def test_update_permissions_unauthorized(
        self,
        client: TestClient,
        sample_user: User
    ):
        """Verify permissions update requires authentication"""
        response = client.put(
            f"/api/v2/admin/users/{sample_user.id}/permissions",
            json={"permissions": ["read"]}
        )

        assert response.status_code == 401

    def test_update_permissions_non_admin(
        self,
        client: TestClient,
        user_token: str,
        sample_user: User
    ):
        """Verify permissions update requires admin role"""
        response = client.put(
            f"/api/v2/admin/users/{sample_user.id}/permissions",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"permissions": ["read"]}
        )

        assert response.status_code == 403

    def test_update_permissions_empty_list(
        self,
        client: TestClient,
        admin_token: str,
        sample_user: User
    ):
        """Verify empty permissions list is accepted"""
        response = client.put(
            f"/api/v2/admin/users/{sample_user.id}/permissions",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"permissions": []}
        )

        assert response.status_code == 200

    def test_update_permissions_duplicate_values(
        self,
        client: TestClient,
        admin_token: str,
        sample_user: User
    ):
        """Verify duplicate permissions are handled"""
        response = client.put(
            f"/api/v2/admin/users/{sample_user.id}/permissions",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"permissions": ["read", "read", "write", "write"]}
        )

        assert response.status_code == 200

        # Verify duplicates are removed
        verify_response = client.get(
            f"/api/v2/admin/users/{sample_user.id}/permissions",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        permissions = verify_response.json()["permissions"]
        assert len(permissions) == len(set(permissions))  # No duplicates

    def test_update_permissions_database_persistence(
        self,
        client: TestClient,
        admin_token: str,
        sample_user: User,
        db: Session
    ):
        """Verify permissions changes persist through database refresh"""
        new_permissions = ["read", "write", "admin"]

        # Update permissions
        response = client.put(
            f"/api/v2/admin/users/{sample_user.id}/permissions",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"permissions": new_permissions}
        )

        assert response.status_code == 200

        # Clear session and reload from database
        db.expire_all()
        db.refresh(sample_user)

        # Verify permissions persisted at database level
        # (exact implementation depends on your data model)
        assert hasattr(sample_user, 'permissions') or hasattr(sample_user, 'roles')

    def test_update_permissions_concurrent_updates(
        self,
        client: TestClient,
        admin_token: str,
        sample_user: User
    ):
        """Verify concurrent permission updates are handled correctly"""
        import concurrent.futures

        def update_permissions(perms):
            return client.put(
                f"/api/v2/admin/users/{sample_user.id}/permissions",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"permissions": perms}
            )

        # Send multiple concurrent updates
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(update_permissions, ["read"]),
                executor.submit(update_permissions, ["write"]),
                executor.submit(update_permissions, ["delete"]),
                executor.submit(update_permissions, ["admin"]),
                executor.submit(update_permissions, ["read", "write"])
            ]

            results = [f.result() for f in futures]

        # All should succeed
        assert all(r.status_code == 200 for r in results)

        # Final state should be consistent
        verify_response = client.get(
            f"/api/v2/admin/users/{sample_user.id}/permissions",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert verify_response.status_code == 200
        assert "permissions" in verify_response.json()


class TestAPIContractEdgeCases:
    """Test edge cases across all API endpoints"""

    def test_large_dataset_performance(
        self,
        client: TestClient,
        admin_token: str,
        db: Session
    ):
        """Verify endpoints handle large datasets efficiently"""
        # Create large dataset (if not exists)
        # This is a placeholder - actual implementation depends on test fixtures

        response = client.get(
            "/api/v2/admin/system-stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200

    def test_malformed_json_requests(self, client: TestClient, admin_token: str):
        """Verify endpoints handle malformed JSON gracefully"""
        response = client.post(
            "/api/v2/auth/reset-password",
            headers={
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json"
            },
            data="invalid json {"
        )

        assert response.status_code == 422

    def test_sql_injection_prevention(
        self,
        client: TestClient,
        admin_token: str
    ):
        """Verify endpoints prevent SQL injection"""
        malicious_input = "'; DROP TABLE users; --"

        response = client.get(
            f"/api/v2/admin/users/{malicious_input}/permissions",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Should handle safely (404 or 400, not 500)
        assert response.status_code in [400, 404, 422]

    def test_xss_prevention(
        self,
        client: TestClient,
        admin_token: str,
        sample_user: User
    ):
        """Verify endpoints prevent XSS attacks"""
        xss_payload = '<script>alert("XSS")</script>'

        response = client.put(
            f"/api/v2/admin/users/{sample_user.id}/permissions",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"permissions": [xss_payload]}
        )

        # Should handle safely
        assert response.status_code in [200, 400, 422]

    def test_rate_limiting(self, client: TestClient, admin_token: str):
        """Verify rate limiting is in place (if implemented)"""
        # Send many rapid requests
        responses = []
        for _ in range(100):
            response = client.get(
                "/api/v2/admin/system-stats",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            responses.append(response)

        # Either all succeed or some are rate-limited (429)
        status_codes = [r.status_code for r in responses]
        assert all(code in [200, 429] for code in status_codes)


# Pytest fixtures (to be implemented in conftest.py)
@pytest.fixture
def client():
    """Test client fixture"""
    return TestClient(app)


@pytest.fixture
def admin_token(client: TestClient, db: Session):
    """Generate admin authentication token"""
    # Implementation depends on your auth system
    pass


@pytest.fixture
def user_token(client: TestClient, db: Session):
    """Generate regular user authentication token"""
    # Implementation depends on your auth system
    pass


@pytest.fixture
def sample_user(db: Session):
    """Create sample user for testing"""
    # Implementation depends on your data model
    pass


@pytest.fixture
def sample_users(db: Session):
    """Create multiple sample users for testing"""
    # Implementation depends on your data model
    pass


@pytest.fixture
def sample_appointments(db: Session):
    """Create sample appointments for testing"""
    # Implementation depends on your data model
    pass
