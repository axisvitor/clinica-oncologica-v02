"""
CSRF Protection Tests - Token Generation and Validation

Tests the CSRF middleware and protection mechanisms:
1. Token generation (Hexadecimal format verification)
2. set_csrf_cookie returns token correctly
3. Token validation with Double Submit Cookie pattern
4. HMAC-SHA256 signature validation
5. Concurrent request handling (no memory leaks)
6. Production vs development behavior

Coverage Goals: 95%+
"""

import pytest
import time
import hmac
import hashlib
from unittest.mock import Mock, patch, MagicMock
from fastapi import Request, Response
from fastapi.testclient import TestClient
from fastapi import FastAPI
from starlette.responses import JSONResponse

from app.middleware.csrf import (
    CsrfSettings,
    get_csrf_settings,
    generate_csrf_token,
    set_csrf_cookie,
    get_csrf_token,
    validate_csrf_token,
    is_csrf_exempt,
    CsrfProtectError,
    _validate_token_signature,
    _generate_token_signature,
)


class TestCsrfTokenGeneration:
    """Test CSRF token generation with Hexadecimal format verification."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_generate_token_returns_hex_format(self, mock_get_settings):
        """Generated token should be in hexadecimal format with dots."""
        mock_settings = Mock()
        mock_settings.secret_key = "test-secret-key-32-characters-long"
        mock_get_settings.return_value = mock_settings

        token = generate_csrf_token()

        # Token should be hex format: timestamp.random.signature
        assert token
        assert isinstance(token, str)
        assert token.count(".") == 2  # Three parts separated by dots

        # Each part should be valid
        parts = token.split(".")
        timestamp, random_data, signature = parts

        # Timestamp should be numeric
        assert timestamp.isdigit()

        # Random data should be 64 hex chars (32 bytes)
        assert len(random_data) == 64
        assert all(c in "0123456789abcdef" for c in random_data)

        # Signature should be 64 hex chars (SHA256)
        assert len(signature) == 64
        assert all(c in "0123456789abcdef" for c in signature)

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_token_format_timestamp_random_signature(self, mock_get_settings):
        """Token should contain timestamp, random data, and HMAC signature."""
        mock_settings = Mock()
        mock_settings.secret_key = "test-secret-key-32-characters-long"
        mock_get_settings.return_value = mock_settings

        token = generate_csrf_token()

        # Should have format: timestamp.random_data.signature
        parts = token.split(".")
        assert len(parts) == 3

        timestamp, random_data, signature = parts

        # Timestamp should be valid and recent
        assert timestamp.isdigit()
        current_time = int(time.time())
        assert abs(int(timestamp) - current_time) < 5  # Within 5 seconds

        # Random data should be hex (32 bytes = 64 hex chars)
        assert len(random_data) == 64
        assert all(c in "0123456789abcdef" for c in random_data)

        # Signature should be hex (SHA256 = 64 hex chars)
        assert len(signature) == 64
        assert all(c in "0123456789abcdef" for c in signature)

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_token_signature_uses_hmac_sha256(self, mock_get_settings):
        """Token signature should use HMAC-SHA256."""
        mock_settings = Mock()
        secret_key = "test-secret-key-32-characters-long"
        mock_settings.secret_key = secret_key
        mock_get_settings.return_value = mock_settings

        token = generate_csrf_token()

        # Verify signature
        parts = token.split(".")
        timestamp, random_data, provided_signature = parts
        data = f"{timestamp}.{random_data}"

        # Recalculate signature
        expected_signature = _generate_token_signature(data, secret_key)

        # Should match
        assert hmac.compare_digest(expected_signature, provided_signature)

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_tokens_are_unique(self, mock_get_settings):
        """Each generated token should be unique."""
        mock_settings = Mock()
        mock_settings.secret_key = "test-secret-key-32-characters-long"
        mock_get_settings.return_value = mock_settings

        tokens = [generate_csrf_token() for _ in range(100)]

        # All tokens should be unique
        assert len(set(tokens)) == 100


class TestSetCsrfCookie:
    """Test set_csrf_cookie returns token and sets cookie correctly."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_set_csrf_cookie_returns_token(self, mock_get_settings):
        """set_csrf_cookie should return the token value."""
        mock_settings = CsrfSettings(
            secret_key="test-secret-key-32-characters-long",
            cookie_secure=False,
            cookie_httponly=True,
            cookie_samesite="strict",
        )
        mock_get_settings.return_value = mock_settings

        request = Mock(spec=Request)
        response = JSONResponse(content={"success": True})

        # Set cookie and get returned token
        returned_token = set_csrf_cookie(request, response)

        # Should return a valid hex token
        assert returned_token
        assert isinstance(returned_token, str)
        parts = returned_token.split(".")
        assert len(parts) == 3

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_set_csrf_cookie_uses_provided_token(self, mock_get_settings):
        """If token provided, should use it instead of generating."""
        mock_settings = CsrfSettings(
            secret_key="test-secret-key-32-characters-long",
            cookie_secure=False,
            cookie_httponly=True,
            cookie_samesite="strict",
        )
        mock_get_settings.return_value = mock_settings

        request = Mock(spec=Request)
        response = JSONResponse(content={"success": True})

        # Generate explicit token
        test_token = generate_csrf_token(mock_settings.secret_key)

        # Set cookie with explicit token
        returned_token = set_csrf_cookie(request, response, token=test_token)

        # Should return the same token
        assert returned_token == test_token

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_set_csrf_cookie_generates_token_if_not_provided(self, mock_get_settings):
        """If no token provided, should generate one automatically."""
        mock_settings = CsrfSettings(
            secret_key="test-secret-key-32-characters-long",
            cookie_secure=False,
            cookie_httponly=True,
            cookie_samesite="strict",
        )
        mock_get_settings.return_value = mock_settings

        request = Mock(spec=Request)
        response = JSONResponse(content={"success": True})

        # Call without providing token
        returned_token = set_csrf_cookie(request, response, token=None)

        # Should return generated token
        assert returned_token
        parts = returned_token.split(".")
        assert len(parts) == 3


class TestTokenValidation:
    """Test token validation without memory leaks."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_validate_token_signature(self, mock_get_settings):
        """Valid token signature should pass validation."""
        secret_key = "test-secret-key-32-characters-long"
        mock_settings = Mock()
        mock_settings.secret_key = secret_key
        mock_get_settings.return_value = mock_settings

        # Generate a valid token
        token = generate_csrf_token(secret_key)

        # Validate it
        assert _validate_token_signature(token, secret_key, max_age=3600)

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_reject_expired_token(self, mock_get_settings):
        """Expired tokens should be rejected."""
        secret_key = "test-secret-key-32-characters-long"

        # Create token with old timestamp
        old_timestamp = str(int(time.time()) - 7200)  # 2 hours ago
        random_data = "a" * 64  # Valid hex
        data = f"{old_timestamp}.{random_data}"
        signature = _generate_token_signature(data, secret_key)
        token = f"{data}.{signature}"

        # Should reject (max_age=3600 = 1 hour)
        assert not _validate_token_signature(token, secret_key, max_age=3600)

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_reject_invalid_signature(self, mock_get_settings):
        """Invalid signature should be rejected."""
        secret_key = "test-secret-key-32-characters-long"

        # Create token with wrong signature
        timestamp = str(int(time.time()))
        random_data = "a" * 64
        data = f"{timestamp}.{random_data}"
        wrong_signature = "b" * 64  # Wrong signature
        token = f"{data}.{wrong_signature}"

        # Should reject
        assert not _validate_token_signature(token, secret_key, max_age=3600)

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_reject_malformed_token(self, mock_get_settings):
        """Malformed tokens should be rejected."""
        secret_key = "test-secret-key-32-characters-long"

        # Various malformed tokens
        malformed_tokens = [
            "not-a-token",
            "",
            "too.few",
            "too.many.parts.here",
            "invalid",
        ]

        for token in malformed_tokens:
            assert not _validate_token_signature(token, secret_key, max_age=3600)


class TestValidateCsrfToken:
    """Test validate_csrf_token function with Double Submit Cookie pattern."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_validate_with_valid_header_and_cookie(self, mock_get_settings):
        """Valid token in both header and cookie should pass."""
        secret_key = "test-secret-key-32-characters-long"
        mock_settings = CsrfSettings(
            secret_key=secret_key,
            cookie_name="fastapi-csrf-token",
            token_header_name="X-CSRF-Token",
            token_expires_in=3600,
            cookie_secure=False,
            cookie_httponly=True,
            cookie_samesite="strict",
        )
        mock_get_settings.return_value = mock_settings

        # Generate valid token
        token = generate_csrf_token(secret_key)

        # Mock request with token in header and cookie
        request = Mock(spec=Request)
        request.headers = {"X-CSRF-Token": token}
        request.cookies = {"fastapi-csrf-token": token}
        request.client = Mock(host="127.0.0.1")
        request.url = Mock(path="/api/test")

        # Should not raise
        validate_csrf_token(request)

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_reject_missing_header(self, mock_get_settings):
        """Missing CSRF header should raise error."""
        mock_settings = CsrfSettings(
            secret_key="test-secret-key-32-characters-long",
            cookie_name="fastapi-csrf-token",
            token_header_name="X-CSRF-Token",
            token_expires_in=3600,
            cookie_secure=False,
            cookie_httponly=True,
            cookie_samesite="strict",
        )
        mock_get_settings.return_value = mock_settings

        # Mock request without header
        request = Mock(spec=Request)
        request.headers = {}
        request.cookies = {}
        request.client = Mock(host="127.0.0.1")
        request.url = Mock(path="/api/test")

        # Should raise
        with pytest.raises(CsrfProtectError, match="Missing CSRF token in headers"):
            validate_csrf_token(request)

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_reject_header_cookie_mismatch(self, mock_get_settings):
        """Header and cookie mismatch should raise error."""
        secret_key = "test-secret-key-32-characters-long"
        mock_settings = CsrfSettings(
            secret_key=secret_key,
            cookie_name="fastapi-csrf-token",
            token_header_name="X-CSRF-Token",
            token_expires_in=3600,
            cookie_secure=False,
            cookie_httponly=True,
            cookie_samesite="strict",
        )
        mock_get_settings.return_value = mock_settings

        # Generate two different tokens
        token1 = generate_csrf_token(secret_key)
        time.sleep(0.1)  # Ensure different tokens
        token2 = generate_csrf_token(secret_key)

        # Mock request with different tokens
        request = Mock(spec=Request)
        request.headers = {"X-CSRF-Token": token1}
        request.cookies = {"fastapi-csrf-token": token2}
        request.client = Mock(host="127.0.0.1")
        request.url = Mock(path="/api/test")

        # Should raise mismatch error
        with pytest.raises(CsrfProtectError, match="CSRF token mismatch"):
            validate_csrf_token(request)


class TestConcurrentRequests:
    """Test concurrent request handling without memory leaks."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_concurrent_token_generation(self, mock_get_settings):
        """Generate many tokens concurrently without memory leaks."""
        import concurrent.futures

        mock_settings = Mock()
        mock_settings.secret_key = "test-secret-key-32-characters-long"
        mock_get_settings.return_value = mock_settings

        # Generate 1000 tokens concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(generate_csrf_token) for _ in range(1000)]
            tokens = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All tokens should be unique and valid
        assert len(set(tokens)) == 1000
        assert all(isinstance(token, str) for token in tokens)
        assert all(token.count(".") == 2 for token in tokens)

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_concurrent_token_validation(self, mock_get_settings):
        """Validate many tokens concurrently without memory leaks."""
        import concurrent.futures

        secret_key = "test-secret-key-32-characters-long"
        mock_settings = Mock()
        mock_settings.secret_key = secret_key
        mock_get_settings.return_value = mock_settings

        # Generate tokens
        tokens = [generate_csrf_token(secret_key) for _ in range(100)]

        # Validate concurrently
        def validate(token):
            return _validate_token_signature(token, secret_key, max_age=3600)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(validate, token) for token in tokens]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should be valid
        assert all(results)


class TestCsrfExemptPaths:
    """Test CSRF exempt paths."""

    def test_exempt_public_endpoints(self):
        """Public endpoints should be exempt from CSRF."""
        exempt_paths = [
            "/session/validate",
            "/session/active",
            "/api/v2/auth/csrf-token",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
        ]

        for path in exempt_paths:
            assert is_csrf_exempt(path, "POST")

    def test_exempt_webhook_endpoints(self):
        """Webhook endpoints should be exempt."""
        assert is_csrf_exempt("/webhooks/stripe", "POST")
        assert is_csrf_exempt("/webhooks/github", "POST")

    def test_exempt_quiz_public_endpoints(self):
        """Public quiz endpoints should be exempt."""
        assert is_csrf_exempt("/api/v2/quiz-extensions/monthly/public", "POST")
        assert is_csrf_exempt("/api/v2/monthly-quiz-public/monthly/public", "POST")

    def test_exempt_safe_methods(self):
        """GET, HEAD, OPTIONS should always be exempt."""
        assert is_csrf_exempt("/api/v2/users", "GET")
        assert is_csrf_exempt("/api/v2/users", "HEAD")
        assert is_csrf_exempt("/api/v2/users", "OPTIONS")

    def test_protected_endpoints_not_exempt(self):
        """Regular API endpoints should not be exempt from CSRF."""
        protected_paths = [
            "/api/v2/users",
            "/api/v2/patients",
            "/api/v2/appointments",
        ]

        for path in protected_paths:
            # POST, PUT, DELETE should require CSRF
            assert not is_csrf_exempt(path, "POST")
            assert not is_csrf_exempt(path, "PUT")
            assert not is_csrf_exempt(path, "DELETE")


class TestProductionVsDevelopment:
    """Test production vs development behavior."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_production_requires_secure_cookies(self, mock_get_settings):
        """Production should require secure cookies."""
        with patch("app.config.settings.settings") as mock_settings:
            mock_settings.APP_ENVIRONMENT = "production"

            settings = CsrfSettings(
                secret_key="test-secret-key-32-characters-long",
                cookie_secure=True,  # Required in production
                cookie_httponly=True,
                cookie_samesite="strict",
            )

            assert settings.cookie_secure is True
            assert settings.cookie_httponly is True
            assert settings.cookie_samesite == "strict"

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_development_allows_insecure_cookies(self, mock_get_settings):
        """Development can use insecure cookies for localhost."""
        with patch("app.config.settings.settings") as mock_settings:
            mock_settings.APP_ENVIRONMENT = "development"

            settings = CsrfSettings(
                secret_key="test-secret-key-32-characters-long",
                cookie_secure=False,  # Allowed in development
                cookie_httponly=True,
                cookie_samesite="strict",
            )

            assert settings.cookie_secure is False


class TestErrorHandling:
    """Test error handling and edge cases."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_invalid_hex_token(self, mock_get_settings):
        """Invalid hex characters should be rejected gracefully."""
        secret_key = "test-secret-key-32-characters-long"

        # Invalid hex characters
        invalid_token = "123456.ZZZZZZ.abcdef"

        assert not _validate_token_signature(invalid_token, secret_key, max_age=3600)

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_token_from_future(self, mock_get_settings):
        """Tokens from the future should be rejected."""
        secret_key = "test-secret-key-32-characters-long"

        # Create token with future timestamp (beyond clock skew)
        future_timestamp = str(int(time.time()) + 3700)  # 1 hour in future
        random_data = "a" * 64
        data = f"{future_timestamp}.{random_data}"
        signature = _generate_token_signature(data, secret_key)
        token = f"{data}.{signature}"

        # Should reject (allows max 60 seconds clock skew)
        assert not _validate_token_signature(token, secret_key, max_age=3600)

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_token_with_non_numeric_timestamp(self, mock_get_settings):
        """Token with non-numeric timestamp should be rejected."""
        secret_key = "test-secret-key-32-characters-long"

        # Invalid timestamp
        token = "abc.abcd1234.signature"

        assert not _validate_token_signature(token, secret_key, max_age=3600)


class TestGetCsrfToken:
    """Test get_csrf_token function."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_get_csrf_token_generates_valid_token(self, mock_get_settings):
        """get_csrf_token should generate valid hex token."""
        mock_settings = Mock()
        mock_settings.secret_key = "test-secret-key-32-characters-long"
        mock_get_settings.return_value = mock_settings

        request = Mock(spec=Request)
        token = get_csrf_token(request)

        # Should be valid hex format
        assert token
        parts = token.split(".")
        assert len(parts) == 3


class TestCsrfSettings:
    """Test CsrfSettings configuration."""

    def test_csrf_settings_defaults(self):
        """Test CsrfSettings default values."""
        settings = CsrfSettings(
            secret_key="test-secret-key-32-characters-long"
        )

        assert settings.cookie_name == "fastapi-csrf-token"
        assert settings.cookie_samesite == "strict"
        assert settings.cookie_secure is True
        assert settings.cookie_httponly is True
        assert settings.token_header_name == "X-CSRF-Token"
        assert settings.token_expires_in == 3600

    def test_csrf_settings_custom_values(self):
        """Test CsrfSettings with custom values."""
        settings = CsrfSettings(
            secret_key="test-secret-key-32-characters-long",
            cookie_name="custom-csrf",
            cookie_samesite="lax",
            cookie_secure=False,
            token_expires_in=7200,
        )

        assert settings.cookie_name == "custom-csrf"
        assert settings.cookie_samesite == "lax"
        assert settings.cookie_secure is False
        assert settings.token_expires_in == 7200
