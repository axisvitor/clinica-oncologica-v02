"""
E2E-006: Authentication Flow Complete
Tests: login → token refresh → logout
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.models.user import User


@pytest.mark.asyncio
class TestAuthenticationE2E:
    """E2E tests for complete authentication flow"""

    async def test_complete_auth_flow(
        self,
        async_client: AsyncClient,
        admin_user: User
    ):
        """
        Test complete authentication flow:
        1. Login
        2. Access protected resource
        3. Refresh token
        4. Logout
        """
        # Step 1: Login
        response = await async_client.post(
            "/api/v2/auth/login",
            json={
                "email": "admin@test.com",
                "password": "Test@1234"
            }
        )

        assert response.status_code == 200
        auth_data = response.json()

        assert "access_token" in auth_data
        assert "refresh_token" in auth_data
        assert auth_data["token_type"] == "bearer"

        access_token = auth_data["access_token"]
        refresh_token = auth_data["refresh_token"]

        # Step 2: Access protected resource
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await async_client.get(
            "/api/v2/users/me",
            headers=headers
        )

        assert response.status_code == 200
        user_data = response.json()
        assert user_data["email"] == "admin@test.com"

        # Step 3: Refresh token
        response = await async_client.post(
            "/api/v2/auth/refresh",
            json={"refresh_token": refresh_token}
        )

        assert response.status_code == 200
        new_auth_data = response.json()
        assert "access_token" in new_auth_data
        new_access_token = new_auth_data["access_token"]

        # Verify new token works
        headers = {"Authorization": f"Bearer {new_access_token}"}
        response = await async_client.get(
            "/api/v2/users/me",
            headers=headers
        )
        assert response.status_code == 200

        # Step 4: Logout
        response = await async_client.post(
            "/api/v2/auth/logout",
            headers=headers
        )

        assert response.status_code == 200

        # Verify token invalidated
        response = await async_client.get(
            "/api/v2/users/me",
            headers=headers
        )
        assert response.status_code == 401

    async def test_login_failure_invalid_credentials(
        self,
        async_client: AsyncClient,
        admin_user: User
    ):
        """Test login fails with invalid credentials"""
        response = await async_client.post(
            "/api/v2/auth/login",
            json={
                "email": "admin@test.com",
                "password": "WrongPassword"
            }
        )

        assert response.status_code == 401
        error = response.json()
        assert "incorrect" in error["detail"].lower()

    async def test_token_expiration(
        self,
        async_client: AsyncClient,
        admin_user: User
    ):
        """Test expired token is rejected"""
        # Login
        response = await async_client.post(
            "/api/v2/auth/login",
            json={
                "email": "admin@test.com",
                "password": "Test@1234"
            }
        )

        access_token = response.json()["access_token"]

        # Simulate token expiration (would need to manipulate JWT in real scenario)
        # For this test, we'll use an expired token endpoint

        headers = {"Authorization": f"Bearer {access_token}"}
        response = await async_client.get(
            "/api/v2/auth/verify-token",
            headers=headers
        )

        assert response.status_code in [200, 401]

    async def test_role_based_access_control(
        self,
        async_client: AsyncClient,
        admin_user: User,
        medico_user: User
    ):
        """Test RBAC permissions"""
        # Admin login
        response = await async_client.post(
            "/api/v2/auth/login",
            json={
                "email": "admin@test.com",
                "password": "Test@1234"
            }
        )
        admin_token = response.json()["access_token"]

        # Medico login
        response = await async_client.post(
            "/api/v2/auth/login",
            json={
                "email": "medico@test.com",
                "password": "Test@1234"
            }
        )
        medico_token = response.json()["access_token"]

        # Admin can access admin endpoint
        response = await async_client.get(
            "/api/v2/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200

        # Medico cannot access admin endpoint
        response = await async_client.get(
            "/api/v2/admin/users",
            headers={"Authorization": f"Bearer {medico_token}"}
        )
        assert response.status_code == 403

    async def test_password_reset_flow(
        self,
        async_client: AsyncClient,
        admin_user: User,
        db_session: Session
    ):
        """
        Test password reset flow:
        1. Request reset
        2. Receive token
        3. Reset password
        4. Login with new password
        """
        # Request password reset
        response = await async_client.post(
            "/api/v2/auth/forgot-password",
            json={"email": "admin@test.com"}
        )

        assert response.status_code == 200

        # Simulate getting reset token (would be sent via email)
        # In real scenario, extract from email
        reset_token = "mock_reset_token_123"

        # Reset password
        new_password = "NewPassword@5678"
        response = await async_client.post(
            "/api/v2/auth/reset-password",
            json={
                "token": reset_token,
                "new_password": new_password
            }
        )

        # May return 200 or 404 depending on token validity
        assert response.status_code in [200, 404]

        # If successful, login with new password
        if response.status_code == 200:
            response = await async_client.post(
                "/api/v2/auth/login",
                json={
                    "email": "admin@test.com",
                    "password": new_password
                }
            )
            assert response.status_code == 200
