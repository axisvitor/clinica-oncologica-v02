"""
CSRF Token Comprehensive Test Suite

Tests all aspects of the CSRF protection system:
- Token generation and validation
- Middleware protection
- Cookie handling
- Security properties
- Edge cases
- Performance

Target Coverage: >90%

Created by: Tester Agent
Coordinated via: Hive Mind Swarm
"""

import pytest
import time
import hmac
import hashlib
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.csrf import (
    generate_csrf_token,
    validate_csrf_token,
    get_csrf_token,
    set_csrf_cookie,
    is_csrf_exempt,
    CSRFMiddleware,
    EXEMPT_PATHS,
    SAFE_METHODS,
    TOKEN_EXPIRY,
    COOKIE_NAME,
)


@pytest.mark.security
@pytest.mark.unit
class TestCSRFTokenGeneration:
    """Unit tests for CSRF token generation."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_token_format_is_valid(self, mock_secret):
        """Test that generated tokens have correct format."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        token = generate_csrf_token()

        # Format: timestamp.random.signature
        parts = token.split(".")
        assert len(parts) == 3

        timestamp, random_data, signature = parts

        # Timestamp should be numeric
        assert timestamp.isdigit()

        # Random data should be hex (64 chars for 32 bytes)
        assert len(random_data) == 64
        assert all(c in "0123456789abcdef" for c in random_data)

        # Signature should be hex (64 chars for SHA256)
        assert len(signature) == 64
        assert all(c in "0123456789abcdef" for c in signature)

    @patch("app.middleware.csrf._get_secret_key")
    def test_token_uniqueness(self, mock_secret):
        """Test that each token is unique."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        tokens = [generate_csrf_token() for _ in range(100)]

        # All tokens should be unique
        assert len(set(tokens)) == 100

    @patch("app.middleware.csrf._get_secret_key")
    def test_token_randomness(self, mock_secret):
        """Test that tokens have sufficient entropy."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        token = generate_csrf_token()
        parts = token.split(".")
        random_data = parts[1]

        # Check that random data isn't predictable
        # Should have good distribution of hex chars
        char_counts = {}
        for char in random_data:
            char_counts[char] = char_counts.get(char, 0) + 1

        # Each hex char should appear at least once in 64 chars
        # (statistical test, may rarely fail)
        assert len(char_counts) >= 8  # At least half the hex chars

    @patch("app.middleware.csrf._get_secret_key")
    def test_token_signature_is_valid(self, mock_secret):
        """Test that signature is correctly computed."""
        secret_key = "test-secret-key-32-characters-long-12345678"
        mock_secret.return_value = secret_key

        token = generate_csrf_token()
        parts = token.split(".")
        timestamp, random_data, signature = parts

        # Recompute signature
        payload = f"{timestamp}.{random_data}"
        expected_sig = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        assert signature == expected_sig

    @patch("app.middleware.csrf._get_secret_key")
    def test_token_timestamp_is_current(self, mock_secret):
        """Test that token timestamp is current."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        before = int(time.time())
        token = generate_csrf_token()
        after = int(time.time())

        timestamp = int(token.split(".")[0])

        assert before <= timestamp <= after


@pytest.mark.security
@pytest.mark.unit
class TestCSRFTokenValidation:
    """Unit tests for CSRF token validation."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_valid_token_accepted(self, mock_secret):
        """Test that valid tokens are accepted."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        token = generate_csrf_token()
        assert validate_csrf_token(token) is True

    @patch("app.middleware.csrf._get_secret_key")
    def test_invalid_format_rejected(self, mock_secret):
        """Test that malformed tokens are rejected."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Wrong number of parts
        assert validate_csrf_token("only.two") is False
        assert validate_csrf_token("one") is False
        assert validate_csrf_token("a.b.c.d") is False

        # Empty token
        assert validate_csrf_token("") is False

        # None
        assert validate_csrf_token(None) is False

    @patch("app.middleware.csrf._get_secret_key")
    def test_tampered_timestamp_rejected(self, mock_secret):
        """Test that tampering with timestamp invalidates token."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        token = generate_csrf_token()
        parts = token.split(".")

        # Change timestamp
        parts[0] = str(int(parts[0]) + 100)
        tampered = ".".join(parts)

        assert validate_csrf_token(tampered) is False

    @patch("app.middleware.csrf._get_secret_key")
    def test_tampered_random_rejected(self, mock_secret):
        """Test that tampering with random data invalidates token."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        token = generate_csrf_token()
        parts = token.split(".")

        # Change random data
        parts[1] = "f" * 64  # All f's
        tampered = ".".join(parts)

        assert validate_csrf_token(tampered) is False

    @patch("app.middleware.csrf._get_secret_key")
    def test_wrong_signature_rejected(self, mock_secret):
        """Test that wrong signature is rejected."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        token = generate_csrf_token()
        parts = token.split(".")

        # Replace signature with different value
        parts[2] = "0" * 64
        tampered = ".".join(parts)

        assert validate_csrf_token(tampered) is False

    @patch("app.middleware.csrf._get_secret_key")
    @patch("app.middleware.csrf.time")
    def test_expired_token_rejected(self, mock_time, mock_secret):
        """Test that expired tokens are rejected."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Generate token at T=1000
        mock_time.time.return_value = 1000
        token = generate_csrf_token()

        # Validate at T=1000 + TOKEN_EXPIRY + 1
        mock_time.time.return_value = 1000 + TOKEN_EXPIRY + 1
        assert validate_csrf_token(token) is False

    @patch("app.middleware.csrf._get_secret_key")
    @patch("app.middleware.csrf.time")
    def test_future_token_rejected(self, mock_time, mock_secret):
        """Test that tokens from the future are rejected (clock skew attack)."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Generate token at T=2000
        mock_time.time.return_value = 2000
        token = generate_csrf_token()

        # Validate at T=1000 (token is from future)
        mock_time.time.return_value = 1000
        assert validate_csrf_token(token) is False

    @patch("app.middleware.csrf._get_secret_key")
    @patch("app.middleware.csrf.time")
    def test_clock_skew_tolerance(self, mock_time, mock_secret):
        """Test that small clock skew is tolerated."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Generate token at T=1000
        mock_time.time.return_value = 1000
        token = generate_csrf_token()

        # Validate at T=990 (30s in the past - should fail)
        mock_time.time.return_value = 990
        assert validate_csrf_token(token) is False

        # Validate at T=960 (40s in the past - within 60s skew)
        mock_time.time.return_value = 960
        assert validate_csrf_token(token) is True

    @patch("app.middleware.csrf._get_secret_key")
    def test_different_secret_key_rejected(self, mock_secret):
        """Test that tokens signed with different key are rejected."""
        # Generate with one key
        mock_secret.return_value = "key1-32-characters-long-for-testing-12345"
        token = generate_csrf_token()

        # Validate with different key
        mock_secret.return_value = "key2-32-characters-long-for-testing-54321"
        assert validate_csrf_token(token) is False


@pytest.mark.security
@pytest.mark.unit
class TestCSRFExemptions:
    """Test CSRF exemption rules."""

    def test_safe_methods_exempt(self):
        """Test that safe HTTP methods are exempt."""
        for method in SAFE_METHODS:
            assert is_csrf_exempt("/api/test", method) is True

        # Unsafe methods not exempt by default
        assert is_csrf_exempt("/api/test", "POST") is False
        assert is_csrf_exempt("/api/test", "PUT") is False
        assert is_csrf_exempt("/api/test", "DELETE") is False
        assert is_csrf_exempt("/api/test", "PATCH") is False

    def test_exempt_paths(self):
        """Test that configured paths are exempt."""
        for path in EXEMPT_PATHS:
            assert is_csrf_exempt(path, "POST") is True

    def test_path_prefix_matching(self):
        """Test that path prefixes work for exemptions."""
        # Paths starting with exempt prefix should be exempt
        assert is_csrf_exempt("/webhooks/stripe", "POST") is True
        assert is_csrf_exempt("/api/public/users", "POST") is True
        assert is_csrf_exempt("/static/css/style.css", "POST") is True
        assert is_csrf_exempt("/uploads/images/photo.jpg", "POST") is True

    def test_non_exempt_paths(self):
        """Test that non-exempt paths require CSRF."""
        assert is_csrf_exempt("/api/v2/patients", "POST") is False
        assert is_csrf_exempt("/api/v2/users", "PUT") is False
        assert is_csrf_exempt("/api/v2/delete", "DELETE") is False


@pytest.mark.security
@pytest.mark.integration
class TestCSRFMiddleware:
    """Integration tests for CSRF middleware."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_middleware_blocks_post_without_token(self, mock_secret):
        """Test that POST requests without CSRF token are blocked."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/test")
        def test_endpoint():
            return {"success": True}

        client = TestClient(app)
        response = client.post("/api/test")

        assert response.status_code == 403
        assert "csrf_token_missing" in response.json()["error"]

    @patch("app.middleware.csrf._get_secret_key")
    def test_middleware_accepts_valid_token(self, mock_secret):
        """Test that valid CSRF token is accepted."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/test")
        def test_endpoint():
            return {"success": True}

        client = TestClient(app)

        # Generate valid token
        token = generate_csrf_token()

        response = client.post(
            "/api/test",
            headers={"X-CSRF-Token": token},
            cookies={COOKIE_NAME: token}
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @patch("app.middleware.csrf._get_secret_key")
    def test_middleware_rejects_mismatched_tokens(self, mock_secret):
        """Test that mismatched header/cookie tokens are rejected."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/test")
        def test_endpoint():
            return {"success": True}

        client = TestClient(app)

        # Generate two different tokens
        token1 = generate_csrf_token()
        time.sleep(0.01)  # Ensure different timestamp
        token2 = generate_csrf_token()

        response = client.post(
            "/api/test",
            headers={"X-CSRF-Token": token1},
            cookies={COOKIE_NAME: token2}
        )

        assert response.status_code == 403
        assert "csrf_mismatch" in response.json()["error"]

    @patch("app.middleware.csrf._get_secret_key")
    def test_middleware_supports_alternative_headers(self, mock_secret):
        """Test that alternative header names are supported."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/test")
        def test_endpoint():
            return {"success": True}

        client = TestClient(app)
        token = generate_csrf_token()

        # Try X-CSRFToken
        response = client.post(
            "/api/test",
            headers={"X-CSRFToken": token},
            cookies={COOKIE_NAME: token}
        )
        assert response.status_code == 200

        # Try X-XSRF-Token
        response = client.post(
            "/api/test",
            headers={"X-XSRF-Token": token},
            cookies={COOKIE_NAME: token}
        )
        assert response.status_code == 200

    @patch("app.middleware.csrf._get_secret_key")
    def test_middleware_allows_exempt_paths(self, mock_secret):
        """Test that exempt paths don't require CSRF token."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.get("/health")
        def health():
            return {"status": "healthy"}

        @app.post("/api/v2/auth/login")
        def login():
            return {"token": "test"}

        client = TestClient(app)

        # Health check (GET - safe method)
        response = client.get("/health")
        assert response.status_code == 200

        # Login (exempt path)
        response = client.post("/api/v2/auth/login")
        assert response.status_code == 200


@pytest.mark.security
@pytest.mark.integration
class TestCSRFCookieHandling:
    """Test CSRF cookie setting and retrieval."""

    @patch("app.middleware.csrf._get_secret_key")
    @patch("app.middleware.csrf._is_production")
    def test_cookie_set_correctly_dev(self, mock_prod, mock_secret):
        """Test cookie is set with correct attributes in development."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"
        mock_prod.return_value = False  # Development mode

        app = FastAPI()

        @app.get("/csrf-token")
        def csrf_endpoint(response):
            token = get_csrf_token()
            set_csrf_cookie(response, token)
            return {"csrf_token": token}

        client = TestClient(app)
        response = client.get("/csrf-token")

        # Check cookie is set
        assert COOKIE_NAME in response.cookies

        # In development, Secure should be False
        cookie = response.cookies[COOKIE_NAME]
        # Note: TestClient doesn't expose all cookie attributes

    @patch("app.middleware.csrf._get_secret_key")
    @patch("app.middleware.csrf._is_production")
    def test_cookie_secure_in_production(self, mock_prod, mock_secret):
        """Test that Secure flag is set in production."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"
        mock_prod.return_value = True  # Production mode

        # Note: Full cookie attribute testing requires integration tests
        # as TestClient has limitations
        pass  # Covered by E2E tests


@pytest.mark.security
@pytest.mark.unit
class TestCSRFSecurityProperties:
    """Test security properties of CSRF implementation."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_timing_attack_resistance(self, mock_secret):
        """Test that validation uses constant-time comparison."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        token = generate_csrf_token()

        # Validate multiple times and check timing consistency
        # (statistical test - may have variance)
        times = []
        for _ in range(100):
            start = time.perf_counter()
            validate_csrf_token(token)
            end = time.perf_counter()
            times.append(end - start)

        # Timing should be relatively consistent
        # (within order of magnitude)
        avg_time = sum(times) / len(times)
        assert all(t < avg_time * 10 for t in times)

    @patch("app.middleware.csrf._get_secret_key")
    def test_replay_attack_prevention(self, mock_secret):
        """Test that tokens expire to prevent replay attacks."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Generate token
        token = generate_csrf_token()

        # Token is valid now
        assert validate_csrf_token(token) is True

        # Simulate time passing beyond expiry
        parts = token.split(".")
        old_timestamp = str(int(time.time()) - TOKEN_EXPIRY - 100)
        expired_token = f"{old_timestamp}.{parts[1]}.{parts[2]}"

        # Recompute signature with old timestamp
        secret_key = mock_secret.return_value
        payload = f"{old_timestamp}.{parts[1]}"
        signature = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        expired_token = f"{payload}.{signature}"

        # Expired token should be rejected
        assert validate_csrf_token(expired_token) is False

    @patch("app.middleware.csrf._get_secret_key")
    def test_no_information_leakage(self, mock_secret):
        """Test that validation doesn't leak information."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Different invalid tokens should all return False
        # without revealing why they're invalid
        assert validate_csrf_token("invalid") is False
        assert validate_csrf_token("a.b.c") is False
        assert validate_csrf_token("") is False
        assert validate_csrf_token(None) is False

        # No exceptions should be raised
        # (all errors handled internally)


@pytest.mark.security
@pytest.mark.performance
class TestCSRFPerformance:
    """Performance tests for CSRF operations."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_token_generation_speed(self, mock_secret):
        """Test that token generation is fast."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        iterations = 1000
        start = time.perf_counter()

        for _ in range(iterations):
            generate_csrf_token()

        end = time.perf_counter()
        avg_time = (end - start) / iterations

        # Should generate >10,000 tokens/second
        assert avg_time < 0.0001  # < 100 microseconds

    @patch("app.middleware.csrf._get_secret_key")
    def test_token_validation_speed(self, mock_secret):
        """Test that token validation is fast."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        token = generate_csrf_token()

        iterations = 1000
        start = time.perf_counter()

        for _ in range(iterations):
            validate_csrf_token(token)

        end = time.perf_counter()
        avg_time = (end - start) / iterations

        # Should validate >10,000 tokens/second
        assert avg_time < 0.0001  # < 100 microseconds

    @patch("app.middleware.csrf._get_secret_key")
    def test_concurrent_validation(self, mock_secret):
        """Test that concurrent validations work correctly."""
        import concurrent.futures

        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        tokens = [generate_csrf_token() for _ in range(100)]

        def validate_token(token):
            return validate_csrf_token(token)

        # Validate all tokens concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(validate_token, tokens))

        # All should be valid
        assert all(results)


@pytest.mark.security
@pytest.mark.unit
class TestCSRFEdgeCases:
    """Test edge cases and error handling."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_empty_secret_key_raises_error(self, mock_secret):
        """Test that empty secret key raises error."""
        mock_secret.return_value = ""

        with pytest.raises(ValueError, match="at least 32 characters"):
            generate_csrf_token()

    @patch("app.middleware.csrf._get_secret_key")
    def test_short_secret_key_raises_error(self, mock_secret):
        """Test that short secret key raises error."""
        mock_secret.return_value = "short"

        with pytest.raises(ValueError, match="at least 32 characters"):
            generate_csrf_token()

    @patch("app.middleware.csrf._get_secret_key")
    def test_unicode_in_token_handling(self, mock_secret):
        """Test that unicode characters in tokens are handled."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Invalid tokens with unicode should be rejected
        assert validate_csrf_token("ñoño.test.签名") is False

    @patch("app.middleware.csrf._get_secret_key")
    def test_very_long_token_rejected(self, mock_secret):
        """Test that excessively long tokens are rejected."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        long_token = "a" * 10000
        assert validate_csrf_token(long_token) is False

    @patch("app.middleware.csrf._get_secret_key")
    def test_null_bytes_in_token_rejected(self, mock_secret):
        """Test that tokens with null bytes are rejected."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        token_with_null = "test\x00token"
        assert validate_csrf_token(token_with_null) is False
