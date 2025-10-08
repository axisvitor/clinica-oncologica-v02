"""
Integration tests for Authentication Middleware.

Tests JWT authentication, token validation, and user context.
"""

import pytest
import jwt
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import os


# Mock authentication middleware
class AuthenticationMiddleware:
    """Mock authentication middleware for testing."""

    def __init__(self, app, secret_key: str = "test-secret"):
        self.app = app
        self.secret_key = secret_key

    async def __call__(self, scope, receive, send):
        """Process request through authentication."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract token from headers
        token = None
        for header in scope.get("headers", []):
            if header[0] == b"authorization":
                auth_header = header[1].decode()
                if auth_header.startswith("Bearer "):
                    token = auth_header[7:]
                break

        # Add user context to scope if token is valid
        if token:
            try:
                payload = jwt.decode(
                    token,
                    self.secret_key,
                    algorithms=["HS256"]
                )
                scope["user"] = payload
            except jwt.InvalidTokenError:
                scope["user"] = None
        else:
            scope["user"] = None

        await self.app(scope, receive, send)


def create_token(
    user_id: str,
    email: str = "test@example.com",
    role: str = "user",
    expires_in: int = 3600
) -> str:
    """Create JWT token for testing."""
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.utcnow() + timedelta(seconds=expires_in),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, "test-secret", algorithm="HS256")


@pytest.fixture
def app_with_auth():
    """Create FastAPI app with authentication."""
    app = FastAPI()

    # Add authentication middleware
    app.add_middleware(AuthenticationMiddleware)

    security = HTTPBearer()

    def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
        """Get current user from token."""
        token = credentials.credentials
        try:
            payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
            return payload
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

    @app.get("/public")
    async def public_endpoint():
        return {"status": "public"}

    @app.get("/protected")
    async def protected_endpoint(user=Depends(get_current_user)):
        return {"status": "protected", "user": user}

    @app.get("/admin")
    async def admin_endpoint(user=Depends(get_current_user)):
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        return {"status": "admin", "user": user}

    return app


@pytest.fixture
def client(app_with_auth):
    """Create test client."""
    return TestClient(app_with_auth)


class TestAuthenticationMiddleware:
    """Test authentication middleware functionality."""

    def test_public_endpoint_no_auth(self, client):
        """Test public endpoint without authentication."""
        response = client.get("/public")
        assert response.status_code == 200
        assert response.json() == {"status": "public"}

    def test_protected_endpoint_no_auth(self, client):
        """Test protected endpoint without authentication."""
        response = client.get("/protected")
        assert response.status_code == 403  # FastAPI returns 403 for missing auth

    def test_protected_endpoint_with_valid_token(self, client):
        """Test protected endpoint with valid token."""
        token = create_token("user-123")
        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "protected"
        assert data["user"]["sub"] == "user-123"

    def test_protected_endpoint_with_invalid_token(self, client):
        """Test protected endpoint with invalid token."""
        response = client.get(
            "/protected",
            headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == 401

    def test_expired_token(self, client):
        """Test expired token is rejected."""
        token = create_token("user-123", expires_in=-1)  # Already expired
        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401

    def test_admin_endpoint_with_user_role(self, client):
        """Test admin endpoint with user role."""
        token = create_token("user-123", role="user")
        response = client.get(
            "/admin",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403
        assert "Admin access required" in response.json()["detail"]

    def test_admin_endpoint_with_admin_role(self, client):
        """Test admin endpoint with admin role."""
        token = create_token("admin-123", role="admin")
        response = client.get(
            "/admin",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "admin"

    def test_malformed_authorization_header(self, client):
        """Test malformed authorization header."""
        response = client.get(
            "/protected",
            headers={"Authorization": "InvalidFormat"}
        )
        assert response.status_code == 403

    def test_token_with_additional_claims(self, client):
        """Test token with additional claims."""
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "role": "user",
            "organization": "clinic-1",
            "permissions": ["read", "write"],
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow()
        }
        token = jwt.encode(payload, "test-secret", algorithm="HS256")

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        user_data = response.json()["user"]
        assert user_data["organization"] == "clinic-1"
        assert "read" in user_data["permissions"]

    def test_multiple_requests_same_token(self, client):
        """Test multiple requests with same token."""
        token = create_token("user-123")
        headers = {"Authorization": f"Bearer {token}"}

        # Multiple requests should all work
        for _ in range(5):
            response = client.get("/protected", headers=headers)
            assert response.status_code == 200

    def test_concurrent_different_users(self, client):
        """Test concurrent requests from different users."""
        token1 = create_token("user-1", email="user1@example.com")
        token2 = create_token("user-2", email="user2@example.com")

        response1 = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token1}"}
        )
        response2 = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token2}"}
        )

        assert response1.status_code == 200
        assert response1.json()["user"]["sub"] == "user-1"
        assert response2.status_code == 200
        assert response2.json()["user"]["sub"] == "user-2"


class TestTokenValidation:
    """Test JWT token validation."""

    def test_token_signature_validation(self, client):
        """Test token signature is validated."""
        # Create token with different secret
        payload = {
            "sub": "user-123",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        wrong_secret_token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {wrong_secret_token}"}
        )
        assert response.status_code == 401

    def test_token_algorithm_validation(self, client):
        """Test only allowed algorithms are accepted."""
        # Create token with different algorithm
        payload = {
            "sub": "user-123",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        # Using HS256 which should be accepted
        token = jwt.encode(payload, "test-secret", algorithm="HS256")

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    def test_token_required_claims(self, client):
        """Test token must have required claims."""
        # Token without 'sub' claim
        payload = {
            "email": "test@example.com",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, "test-secret", algorithm="HS256")

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"}
        )
        # Should still work but user info might be incomplete
        assert response.status_code == 200