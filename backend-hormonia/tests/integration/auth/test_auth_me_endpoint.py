"""
Integration tests for GET /api/v1/auth/me endpoint.

Tests comprehensive endpoint behavior including:
- Response time performance (<500ms requirement)
- User data accuracy and completeness
- Firebase custom claims inclusion
- Authentication failure scenarios
- Cache effectiveness
"""
import pytest
from typing import Dict
import time
from datetime import datetime
from fastapi import status
from httpx import AsyncClient

from app.models.user import User, UserRole


class TestAuthMeEndpoint:
    """Test suite for /api/v1/auth/me endpoint performance and behavior."""

    @pytest.mark.asyncio
    async def test_auth_me_returns_200_under_500ms(
        self,
        http_client: AsyncClient,
        doctor_a_credentials: Dict[str, str],
        auth_headers,
        performance_timer
    ):
        """
        Test /auth/me returns 200 OK in under 500ms.

        CRITICAL REQUIREMENT: Response time must be <500ms for
        good user experience on dashboard load.
        """
        headers = auth_headers(doctor_a_credentials)

        # Act - measure performance
        with performance_timer() as timer:
            response = await http_client.get("/api/v1/auth/me", headers=headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK, \
            f"Expected 200 OK, got {response.status_code}: {response.text}"

        assert timer.elapsed_ms < 500, \
            f"Response took {timer.elapsed_ms:.2f}ms, should be <500ms"

    @pytest.mark.asyncio
    async def test_auth_me_returns_complete_user_data(
        self,
        http_client: AsyncClient,
        doctor_a_credentials: Dict[str, str],
        auth_headers
    ):
        """
        Test /auth/me returns complete user profile data.

        Should include:
        - id, email, full_name
        - role
        - is_active
        - Firebase UID
        - Custom claims
        """
        headers = auth_headers(doctor_a_credentials)

        # Act
        response = await http_client.get("/api/v1/auth/me", headers=headers)
        data = response.json()

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert "id" in data
        assert "email" in data
        assert "full_name" in data
        assert "role" in data
        assert "is_active" in data

        # Verify user data matches credentials
        assert data["email"] == doctor_a_credentials["email"]
        assert data["role"] == "doctor"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_auth_me_includes_firebase_custom_claims(
        self,
        http_client: AsyncClient,
        doctor_a_credentials: Dict[str, str],
        auth_headers
    ):
        """
        Test /auth/me includes Firebase custom claims.

        Custom claims should be accessible for frontend to
        use for role-based UI rendering.
        """
        headers = auth_headers(doctor_a_credentials)

        # Act
        response = await http_client.get("/api/v1/auth/me", headers=headers)
        data = response.json()

        # Assert
        assert response.status_code == status.HTTP_200_OK
        # Custom claims might be in metadata or dedicated field
        assert "firebase_custom_claims" in data or "metadata" in data

    @pytest.mark.asyncio
    async def test_auth_me_fails_with_invalid_token(
        self,
        http_client: AsyncClient
    ):
        """
        Test /auth/me returns 401 with invalid token.

        Security requirement: Invalid tokens should be rejected.
        """
        headers = {
            "Authorization": "Bearer invalid_token_12345",
            "Content-Type": "application/json"
        }

        # Act
        response = await http_client.get("/api/v1/auth/me", headers=headers)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_auth_me_fails_with_expired_token(
        self,
        http_client: AsyncClient,
        expired_token_credentials: Dict[str, str],
        auth_headers
    ):
        """
        Test /auth/me returns 401 with expired token.

        Security requirement: Expired tokens should be rejected.
        """
        headers = auth_headers(expired_token_credentials)

        # Act
        response = await http_client.get("/api/v1/auth/me", headers=headers)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_auth_me_fails_without_authorization_header(
        self,
        http_client: AsyncClient
    ):
        """
        Test /auth/me returns 401 without Authorization header.

        Security requirement: Authentication required.
        """
        # Act
        response = await http_client.get("/api/v1/auth/me")

        # Assert
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ]

    @pytest.mark.asyncio
    async def test_auth_me_performance_with_cold_cache(
        self,
        http_client: AsyncClient,
        doctor_a_credentials: Dict[str, str],
        auth_headers,
        performance_timer
    ):
        """
        Test /auth/me performance on first request (cold cache).

        Even with cold cache (no cached profile), response should
        be <500ms.
        """
        headers = auth_headers(doctor_a_credentials)

        # Clear any existing cache (if cache utility available)
        try:
            from app.utils.user_cache import invalidate_user_cache
            invalidate_user_cache(
                doctor_a_credentials["firebase_uid"],
                None  # User ID unknown
            )
        except ImportError:
            pass

        # Act - measure cold cache performance
        with performance_timer() as timer:
            response = await http_client.get("/api/v1/auth/me", headers=headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert timer.elapsed_ms < 500, \
            f"Cold cache request took {timer.elapsed_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_auth_me_performance_with_warm_cache(
        self,
        http_client: AsyncClient,
        doctor_a_credentials: Dict[str, str],
        auth_headers,
        performance_timer
    ):
        """
        Test /auth/me performance on subsequent requests (warm cache).

        With warm cache, response should be significantly faster.
        """
        headers = auth_headers(doctor_a_credentials)

        # Prime the cache
        await http_client.get("/api/v1/auth/me", headers=headers)

        # Act - measure warm cache performance
        with performance_timer() as timer:
            response = await http_client.get("/api/v1/auth/me", headers=headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert timer.elapsed_ms < 200, \
            f"Warm cache request took {timer.elapsed_ms:.2f}ms, should be <200ms"

    @pytest.mark.asyncio
    async def test_auth_me_admin_user(
        self,
        http_client: AsyncClient,
        admin_credentials: Dict[str, str],
        auth_headers
    ):
        """
        Test /auth/me for admin user returns admin role.

        Admin users should have role='admin' in response.
        """
        headers = auth_headers(admin_credentials)

        # Act
        response = await http_client.get("/api/v1/auth/me", headers=headers)
        data = response.json()

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert data["role"] == "admin"
        assert data["email"] == admin_credentials["email"]

    @pytest.mark.asyncio
    async def test_auth_me_concurrent_requests_performance(
        self,
        http_client: AsyncClient,
        doctor_a_credentials: Dict[str, str],
        auth_headers
    ):
        """
        Test /auth/me handles concurrent requests efficiently.

        Simulates dashboard making multiple parallel requests.
        All should complete in reasonable time.
        """
        import asyncio
        headers = auth_headers(doctor_a_credentials)

        # Act - make 10 concurrent requests
        start_time = time.time()
        tasks = [
            http_client.get("/api/v1/auth/me", headers=headers)
            for _ in range(10)
        ]
        responses = await asyncio.gather(*tasks)
        elapsed_ms = (time.time() - start_time) * 1000

        # Assert
        assert all(r.status_code == status.HTTP_200_OK for r in responses)
        assert elapsed_ms < 1000, \
            f"10 concurrent requests took {elapsed_ms:.2f}ms, should be <1000ms"
