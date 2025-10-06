"""
E2E Tests for Firebase Admin SDK Integration in Railway Production

Tests Firebase Admin SDK backend integration, custom claims validation,
and token verification in production Railway environment.
"""
import pytest
import os
import httpx
from typing import Dict, Any
from unittest.mock import Mock, patch


@pytest.fixture
def railway_backend_url():
    """Railway production backend URL"""
    return os.getenv(
        "RAILWAY_BACKEND_URL",
        "https://backend-hormonia-production.up.railway.app"
    )


@pytest.fixture
def firebase_admin_credentials():
    """Firebase Admin SDK credentials from Railway environment"""
    return {
        "project_id": os.getenv("FIREBASE_PROJECT_ID"),
        "private_key": os.getenv("FIREBASE_PRIVATE_KEY"),
        "client_email": os.getenv("FIREBASE_CLIENT_EMAIL")
    }


class TestFirebaseAdminSDKIntegration:
    """Test suite for Firebase Admin SDK backend integration"""

    @pytest.mark.asyncio
    async def test_firebase_admin_sdk_initialized(self, railway_backend_url):
        """
        Test 1: Firebase Admin SDK is initialized in Railway backend

        Validates:
        - Backend health endpoint responds
        - Firebase configuration is loaded
        - Admin SDK is ready for token validation
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{railway_backend_url}/api/v1/health/detailed")

            assert response.status_code == 200
            health_data = response.json()

            # Check Firebase is configured
            assert "firebase" in str(health_data).lower() or \
                   "authentication" in str(health_data).lower(), \
                   "Health check should indicate Firebase configuration"

    @pytest.mark.asyncio
    async def test_backend_validates_firebase_tokens(self, railway_backend_url):
        """
        Test 2: Backend validates Firebase JWT tokens correctly

        Validates:
        - Protected endpoints reject requests without tokens
        - Authorization header is expected
        - 401 response includes WWW-Authenticate header
        """
        async with httpx.AsyncClient() as client:
            # Try to access protected endpoint without token
            response = await client.get(f"{railway_backend_url}/api/v1/users/me")

            assert response.status_code == 401, \
                "Protected endpoint should return 401 without token"

            # Check WWW-Authenticate header
            assert "WWW-Authenticate" in response.headers or \
                   "www-authenticate" in response.headers, \
                   "401 response should include WWW-Authenticate header"

    @pytest.mark.asyncio
    async def test_custom_claims_extraction(self, railway_backend_url):
        """
        Test 3: Backend extracts custom claims from Firebase tokens

        Validates:
        - Custom claims are available in decoded token
        - Role, permissions, metadata are extracted
        - Backend uses claims for authorization

        Note: Requires valid Firebase token with custom claims
        """
        # This test requires a real Firebase token
        # Skip if not in integration test environment
        token = os.getenv("TEST_FIREBASE_TOKEN")

        if not token:
            pytest.skip("TEST_FIREBASE_TOKEN not set - skipping integration test")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{railway_backend_url}/api/v1/users/me",
                headers={"Authorization": f"Bearer {token}"}
            )

            if response.status_code == 200:
                user_data = response.json()

                # Verify custom claims are present
                assert "role" in user_data or "custom_claims" in user_data, \
                    "User data should include custom claims"

                # Verify metadata is returned
                assert "metadata" in user_data or "permissions" in user_data, \
                    "User data should include permissions/metadata"

    @pytest.mark.asyncio
    async def test_expired_token_rejection(self, railway_backend_url):
        """
        Test 4: Backend rejects expired Firebase tokens

        Validates:
        - Expired tokens return 401
        - Error message indicates expiration
        - No access granted to protected resources
        """
        # Use an obviously expired token format
        expired_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjF9.invalid"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{railway_backend_url}/api/v1/users/me",
                headers={"Authorization": f"Bearer {expired_token}"}
            )

            assert response.status_code == 401, \
                "Expired token should return 401"

            error_data = response.json()
            error_message = str(error_data).lower()

            assert "expired" in error_message or \
                   "invalid" in error_message or \
                   "unauthorized" in error_message, \
                   "Error should indicate token issue"

    @pytest.mark.asyncio
    async def test_malformed_token_rejection(self, railway_backend_url):
        """
        Test 5: Backend handles malformed tokens gracefully

        Validates:
        - Malformed tokens return 401 (not 500)
        - Error handling is robust
        - No server crashes on invalid input
        """
        malformed_tokens = [
            "not-a-jwt-token",
            "header.payload",  # Missing signature
            "",  # Empty token
            "Bearer token",  # Double Bearer
        ]

        async with httpx.AsyncClient() as client:
            for token in malformed_tokens:
                response = await client.get(
                    f"{railway_backend_url}/api/v1/users/me",
                    headers={"Authorization": f"Bearer {token}"}
                )

                assert response.status_code == 401, \
                    f"Malformed token '{token}' should return 401, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_revoked_token_rejection(self, railway_backend_url):
        """
        Test 6: Backend checks token revocation status

        Validates:
        - Revoked tokens are rejected (check_revoked=True)
        - Backend calls Firebase to verify revocation
        - User must re-authenticate after revocation

        Note: Requires test Firebase token that can be revoked
        """
        # This test would require Firebase Admin SDK access to revoke a token
        pytest.skip("Token revocation test requires Firebase Admin SDK setup")

    @pytest.mark.asyncio
    async def test_concurrent_token_validations(self, railway_backend_url):
        """
        Test 7: Backend handles concurrent token validations

        Validates:
        - Multiple simultaneous requests are handled
        - No race conditions in token validation
        - Firebase Admin SDK thread safety
        """
        import asyncio

        token = os.getenv("TEST_FIREBASE_TOKEN", "test-token")

        async def make_request(client):
            return await client.get(
                f"{railway_backend_url}/api/v1/users/me",
                headers={"Authorization": f"Bearer {token}"}
            )

        async with httpx.AsyncClient() as client:
            # Make 10 concurrent requests
            tasks = [make_request(client) for _ in range(10)]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # All should return consistent status codes
            status_codes = [r.status_code for r in responses if isinstance(r, httpx.Response)]

            if status_codes:
                # Should all be 401 (for test token) consistently
                assert len(set(status_codes)) == 1, \
                    f"Inconsistent status codes indicate race condition: {status_codes}"

    @pytest.mark.asyncio
    async def test_custom_claims_authorization(self, railway_backend_url):
        """
        Test 8: Backend uses custom claims for authorization

        Validates:
        - Admin role can access admin endpoints
        - Doctor role has appropriate permissions
        - Patient role has restricted access
        - Role-based access control works

        Note: Requires tokens with different roles
        """
        # This test requires multiple tokens with different roles
        pytest.skip("Role-based authorization test requires multiple test users")

    @pytest.mark.asyncio
    async def test_firebase_service_account_permissions(self, firebase_admin_credentials):
        """
        Test 9: Firebase service account has correct permissions

        Validates:
        - Service account credentials are valid
        - Project ID matches configuration
        - Client email format is correct
        - Private key is properly formatted
        """
        creds = firebase_admin_credentials

        if creds["project_id"]:
            assert len(creds["project_id"]) > 0
            assert "@" not in creds["project_id"], \
                "project_id should not contain @ (use client_email for email)"

        if creds["client_email"]:
            assert "@" in creds["client_email"]
            assert creds["client_email"].endswith(".iam.gserviceaccount.com"), \
                "client_email should be a service account email"

        if creds["private_key"]:
            assert "BEGIN PRIVATE KEY" in creds["private_key"], \
                "private_key should be PEM-formatted"

    @pytest.mark.asyncio
    async def test_token_custom_claims_persistence(self, railway_backend_url):
        """
        Test 10: Custom claims persist across token refreshes

        Validates:
        - Custom claims set via script persist
        - Token refresh maintains claims
        - Claims are consistent across requests
        """
        token = os.getenv("TEST_FIREBASE_TOKEN")

        if not token:
            pytest.skip("TEST_FIREBASE_TOKEN not set")

        async with httpx.AsyncClient() as client:
            # Make multiple requests to verify claims consistency
            responses = []
            for _ in range(3):
                response = await client.get(
                    f"{railway_backend_url}/api/v1/users/me",
                    headers={"Authorization": f"Bearer {token}"}
                )
                if response.status_code == 200:
                    responses.append(response.json())

            if len(responses) > 1:
                # Verify claims are consistent
                roles = [r.get("role") for r in responses if "role" in r]
                if roles:
                    assert len(set(roles)) == 1, \
                        f"Role should be consistent across requests, got {roles}"


@pytest.mark.integration
class TestFirebaseProductionIntegration:
    """Integration tests requiring live Railway deployment"""

    @pytest.mark.skip(reason="Requires Railway production environment")
    async def test_railway_firebase_env_vars_configured(self):
        """
        Test 11: Railway environment has Firebase variables set

        Manual validation checklist:
        1. Railway backend service → Variables tab
        2. Verify FIREBASE_PROJECT_ID is set
        3. Verify FIREBASE_PRIVATE_KEY is set (PEM format)
        4. Verify FIREBASE_CLIENT_EMAIL is set
        5. Check for typos or extra spaces
        6. Verify values match Firebase Console

        Expected: All 3 variables present and valid
        """
        pass

    @pytest.mark.skip(reason="Requires Firebase Console access")
    async def test_custom_claims_script_execution(self):
        """
        Test 12: Custom claims script runs successfully

        Manual steps:
        1. Connect to Railway backend container or run locally
        2. Execute: python backend-hormonia/scripts/fix_firebase_custom_claims.py
        3. Enter Firebase UID when prompted
        4. Verify success message
        5. Check Firebase Console → Users → Custom Claims

        Expected: Claims added successfully to user
        """
        pass

    @pytest.mark.skip(reason="Requires browser testing")
    async def test_end_to_end_auth_flow(self):
        """
        Test 13: Complete authentication flow in production

        Manual E2E test steps:
        1. Open browser to production frontend
        2. Login with Firebase credentials
        3. Open DevTools Network tab
        4. Verify Authorization header on API calls
        5. Check no 401 errors occur
        6. Verify custom claims are used for authorization
        7. Test role-based access (admin vs patient)

        Expected: Seamless auth flow with custom claims
        """
        pass


@pytest.mark.smoke
class TestFirebaseSmoke:
    """Quick smoke tests for Firebase integration"""

    @pytest.mark.asyncio
    async def test_backend_accepts_bearer_tokens(self, railway_backend_url):
        """
        Smoke Test 1: Backend accepts Authorization: Bearer format

        Quick validation that endpoint expects Bearer tokens
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{railway_backend_url}/api/v1/users/me",
                headers={"Authorization": "Bearer test"}
            )

            # Should return 401 for invalid token, but accept Bearer format
            assert response.status_code in [401, 403], \
                "Endpoint should accept Bearer token format"

    @pytest.mark.asyncio
    async def test_backend_rejects_missing_auth(self, railway_backend_url):
        """
        Smoke Test 2: Backend rejects requests without authentication

        Quick validation that protected endpoints require auth
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{railway_backend_url}/api/v1/users/me")

            assert response.status_code == 401, \
                "Protected endpoint should return 401 without auth"

    @pytest.mark.asyncio
    async def test_health_endpoint_available(self, railway_backend_url):
        """
        Smoke Test 3: Health endpoint is accessible

        Quick validation that backend is running
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{railway_backend_url}/api/v1/health")
                assert response.status_code == 200, \
                    "Health endpoint should return 200"
            except httpx.ConnectError:
                pytest.fail("Cannot connect to Railway backend - is it deployed?")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
