"""
Test Utilities for Security Tests

Provides clean, reusable fixtures and utilities for CORS and CSRF testing.
No pytest hacks - just proper fixtures and helper functions.
"""

import time
import hmac
import hashlib
from typing import Optional
from unittest.mock import Mock
import pytest


def generate_test_csrf_token(
    secret_key: str,
    timestamp: Optional[int] = None,
    random_data: Optional[str] = None,
) -> str:
    """
    Generate a test CSRF token with valid hexadecimal format.

    Args:
        secret_key: Secret key for HMAC signing
        timestamp: Optional timestamp (defaults to current time)
        random_data: Optional random data (defaults to 64 hex chars)

    Returns:
        Hex-encoded CSRF token in format: timestamp.random.signature
    """
    if timestamp is None:
        timestamp = int(time.time())

    if random_data is None:
        random_data = "a" * 64  # 64 hex characters

    data = f"{timestamp}.{random_data}"
    signature = hmac.new(
        secret_key.encode("utf-8"), data.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    return f"{data}.{signature}"


def generate_expired_token(secret_key: str, age_seconds: int = 7200) -> str:
    """
    Generate an expired CSRF token.

    Args:
        secret_key: Secret key for HMAC signing
        age_seconds: How old the token should be (default: 2 hours)

    Returns:
        Hex-encoded expired CSRF token
    """
    old_timestamp = int(time.time()) - age_seconds
    return generate_test_csrf_token(secret_key, timestamp=old_timestamp)


def generate_invalid_token(secret_key: str) -> str:
    """
    Generate a token with invalid signature.

    Args:
        secret_key: Secret key (not used for signature)

    Returns:
        Token with wrong signature
    """
    timestamp = int(time.time())
    random_data = "a" * 64
    data = f"{timestamp}.{random_data}"
    wrong_signature = "b" * 64  # Wrong signature

    return f"{data}.{wrong_signature}"


def create_mock_request(
    method: str = "POST",
    path: str = "/api/test",
    headers: Optional[dict] = None,
    cookies: Optional[dict] = None,
    client_host: str = "127.0.0.1",
) -> Mock:
    """
    Create a mock FastAPI Request object.

    Args:
        method: HTTP method
        path: Request path
        headers: Request headers
        cookies: Request cookies
        client_host: Client IP address

    Returns:
        Mock Request object
    """
    request = Mock()
    request.method = method
    request.headers = headers or {}
    request.cookies = cookies or {}
    request.client = Mock(host=client_host)
    request.url = Mock(path=path)

    return request


def create_mock_response():
    """
    Create a mock Response object for testing cookie setting.

    Returns:
        Mock Response object with set_cookie method
    """
    response = Mock()
    response.raw_headers = []
    response.set_cookie = Mock()

    def mock_set_cookie(**kwargs):
        # Simulate cookie header
        response.raw_headers.append(("set-cookie", "mock-cookie"))

    response.set_cookie.side_effect = mock_set_cookie

    return response


def create_mock_csrf_settings(
    secret_key: str = "test-secret-key-32-characters-long",
    cookie_secure: bool = False,
    cookie_httponly: bool = True,
    cookie_samesite: str = "strict",
    token_expires_in: int = 3600,
):
    """
    Create a mock CSRF settings object.

    Args:
        secret_key: CSRF secret key
        cookie_secure: Secure cookie flag
        cookie_httponly: HttpOnly cookie flag
        cookie_samesite: SameSite cookie policy
        token_expires_in: Token expiration time in seconds

    Returns:
        Mock settings object with CSRF configuration
    """
    settings = Mock()
    settings.secret_key = secret_key
    settings.cookie_secure = cookie_secure
    settings.cookie_httponly = cookie_httponly
    settings.cookie_samesite = cookie_samesite
    settings.token_expires_in = token_expires_in
    return settings


def create_mock_security_settings(
    environment: str = "development",
    cors_origins: Optional[list] = None,
):
    """
    Create a mock SecuritySettings object.

    Args:
        environment: Environment (production/development)
        cors_origins: List of allowed CORS origins

    Returns:
        Mock SecuritySettings object
    """
    mock_settings = Mock()
    mock_settings.APP_ENVIRONMENT = environment
    mock_settings.CORS_FRONTEND_URL = "http://localhost:5173"
    mock_settings.CORS_QUIZ_URL = "http://localhost:3001"
    mock_settings.CORS_ALLOWED_ORIGINS = cors_origins or []
    mock_settings.SECURITY_CSRF_SECRET_KEY = "test-secret-key-32-characters-long"

    def get_cors_origins():
        if cors_origins:
            return cors_origins
        if environment == "production":
            return ["https://example.com"]
        return ["http://localhost:5173", "http://localhost:3001"]

    mock_settings.get_cors_origins = Mock(side_effect=get_cors_origins)

    return mock_settings


# Pytest fixtures for common test data


@pytest.fixture
def test_secret_key():
    """Fixture: Test secret key."""
    return "test-secret-key-32-characters-long"


@pytest.fixture
def valid_csrf_token(test_secret_key):
    """Fixture: Valid CSRF token in hex format."""
    return generate_test_csrf_token(test_secret_key)


@pytest.fixture
def expired_csrf_token(test_secret_key):
    """Fixture: Expired CSRF token."""
    return generate_expired_token(test_secret_key)


@pytest.fixture
def invalid_csrf_token(test_secret_key):
    """Fixture: Invalid CSRF token."""
    return generate_invalid_token(test_secret_key)


@pytest.fixture
def mock_request():
    """Fixture: Mock FastAPI request."""
    return create_mock_request()


@pytest.fixture
def mock_response():
    """Fixture: Mock Response object."""
    return create_mock_response()


@pytest.fixture
def mock_csrf_settings(test_secret_key):
    """Fixture: Mock CSRF settings."""
    return create_mock_csrf_settings(secret_key=test_secret_key)


@pytest.fixture
def mock_dev_settings():
    """Fixture: Mock development settings."""
    return create_mock_security_settings(environment="development")


@pytest.fixture
def mock_prod_settings():
    """Fixture: Mock production settings."""
    return create_mock_security_settings(
        environment="production",
        cors_origins=["https://example.com"],
    )


# Test the utility functions themselves


class TestUtilityFunctions:
    """Test utility functions work correctly."""

    def test_generate_test_csrf_token_format(self, test_secret_key):
        """Test CSRF token generation produces correct format."""
        token = generate_test_csrf_token(test_secret_key)

        # Should be hex format with 3 parts
        parts = token.split(".")
        assert len(parts) == 3

        timestamp, random_data, signature = parts

        # Timestamp should be numeric
        assert timestamp.isdigit()

        # Random data should be 64 hex chars
        assert len(random_data) == 64
        assert all(c in "0123456789abcdef" for c in random_data)

        # Signature should be 64 hex chars (SHA256)
        assert len(signature) == 64
        assert all(c in "0123456789abcdef" for c in signature)

    def test_generate_expired_token(self, test_secret_key):
        """Test expired token generation."""
        token = generate_expired_token(test_secret_key, age_seconds=3600)

        # Should be valid format
        parts = token.split(".")
        assert len(parts) == 3

        # Timestamp should be old
        timestamp = int(parts[0])
        current_time = int(time.time())
        assert current_time - timestamp >= 3600

    def test_generate_invalid_token(self, test_secret_key):
        """Test invalid token generation."""
        token = generate_invalid_token(test_secret_key)

        # Should be valid format but wrong signature
        parts = token.split(".")
        assert len(parts) == 3

    def test_create_mock_request(self):
        """Test mock request creation."""
        request = create_mock_request(
            method="POST",
            path="/api/test",
            headers={"X-CSRF-Token": "test"},
            cookies={"session": "abc"},
        )

        assert request.method == "POST"
        assert request.url.path == "/api/test"
        assert request.headers["X-CSRF-Token"] == "test"
        assert request.cookies["session"] == "abc"

    def test_create_mock_response(self):
        """Test mock response creation."""
        response = create_mock_response()

        # Should have set_cookie method
        assert hasattr(response, "set_cookie")

        # Call set_cookie
        response.set_cookie(key="test", value="value")

        # Should have added header
        assert len(response.raw_headers) > 0
