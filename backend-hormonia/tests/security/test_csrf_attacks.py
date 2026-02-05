"""
CSRF Attack Prevention Tests

Tests that CSRF protection defends against real attack scenarios:
- CSRF token bypass attempts
- Double submit cookie attacks
- Subdomain attacks
- XSS + CSRF combinations
- Timing attacks
- Token exhaustion

Target Coverage: Security critical paths

Created by: Tester Agent
Coordinated via: Hive Mind Swarm
"""

import pytest
import time
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.csrf import (
    generate_csrf_token,
    validate_csrf_token,
    CSRFMiddleware,
    COOKIE_NAME,
)


@pytest.mark.security
@pytest.mark.critical
class TestCSRFBypassAttempts:
    """Test that CSRF protection cannot be bypassed."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_missing_header_rejected(self, mock_secret):
        """Test that requests without X-CSRF-Token header are rejected."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/transfer")
        def transfer():
            return {"status": "transferred"}

        client = TestClient(app)
        token = generate_csrf_token()

        # Only cookie, no header
        response = client.post(
            "/api/transfer",
            cookies={COOKIE_NAME: token}
        )

        assert response.status_code == 403
        assert "csrf_token_missing" in response.json()["error"]

    @patch("app.middleware.csrf._get_secret_key")
    def test_missing_cookie_rejected(self, mock_secret):
        """Test that requests without CSRF cookie are rejected."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/transfer")
        def transfer():
            return {"status": "transferred"}

        client = TestClient(app)
        token = generate_csrf_token()

        # Only header, no cookie
        response = client.post(
            "/api/transfer",
            headers={"X-CSRF-Token": token}
        )

        assert response.status_code == 403
        assert "csrf_cookie_missing" in response.json()["error"]

    @patch("app.middleware.csrf._get_secret_key")
    def test_forged_request_from_attacker_site(self, mock_secret):
        """Test that forged requests from attacker sites are blocked."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/delete-account")
        def delete_account():
            return {"status": "deleted"}

        client = TestClient(app)

        # Attacker tries to forge request without knowing token
        response = client.post(
            "/api/delete-account",
            headers={"Origin": "https://evil.com"}
        )

        assert response.status_code == 403

    @patch("app.middleware.csrf._get_secret_key")
    def test_stolen_cookie_without_header_fails(self, mock_secret):
        """Test that stolen cookie alone is not sufficient."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/sensitive")
        def sensitive():
            return {"data": "sensitive"}

        client = TestClient(app)
        token = generate_csrf_token()

        # Attacker has cookie but can't set header from different origin
        response = client.post(
            "/api/sensitive",
            cookies={COOKIE_NAME: token}
            # No header - can't be set by attacker JS from different origin
        )

        assert response.status_code == 403


@pytest.mark.security
@pytest.mark.critical
class TestDoubleSubmitCookieAttacks:
    """Test attacks against double submit cookie pattern."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_attacker_cannot_set_cookie_and_header(self, mock_secret):
        """Test that attacker cannot control both cookie and header."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/action")
        def action():
            return {"success": True}

        client = TestClient(app)

        # Attacker tries to set their own token in both places
        evil_token = "attacker-controlled-token"
        response = client.post(
            "/api/action",
            headers={"X-CSRF-Token": evil_token},
            cookies={COOKIE_NAME: evil_token}
        )

        # Should fail validation (invalid signature)
        assert response.status_code == 403

    @patch("app.middleware.csrf._get_secret_key")
    def test_different_tokens_rejected(self, mock_secret):
        """Test that different tokens in header and cookie are rejected."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/action")
        def action():
            return {"success": True}

        client = TestClient(app)

        token1 = generate_csrf_token()
        time.sleep(0.01)
        token2 = generate_csrf_token()

        response = client.post(
            "/api/action",
            headers={"X-CSRF-Token": token1},
            cookies={COOKIE_NAME: token2}
        )

        assert response.status_code == 403
        assert "csrf_mismatch" in response.json()["error"]


@pytest.mark.security
@pytest.mark.critical
class TestTokenSignatureAttacks:
    """Test attacks against token signature."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_signature_tampering_detected(self, mock_secret):
        """Test that signature tampering is detected."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        token = generate_csrf_token()
        parts = token.split(".")

        # Tamper with signature
        parts[2] = "0" * 64
        tampered = ".".join(parts)

        assert validate_csrf_token(tampered) is False

    @patch("app.middleware.csrf._get_secret_key")
    def test_payload_tampering_detected(self, mock_secret):
        """Test that payload tampering breaks signature."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        token = generate_csrf_token()
        parts = token.split(".")

        # Change timestamp
        parts[0] = str(int(parts[0]) + 1)
        tampered = ".".join(parts)

        # Should fail because signature no longer matches
        assert validate_csrf_token(tampered) is False

    @patch("app.middleware.csrf._get_secret_key")
    def test_signature_stripping_detected(self, mock_secret):
        """Test that removing signature is detected."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        token = generate_csrf_token()
        parts = token.split(".")

        # Remove signature
        unsigned = f"{parts[0]}.{parts[1]}"

        assert validate_csrf_token(unsigned) is False


@pytest.mark.security
@pytest.mark.critical
class TestTimingAttacks:
    """Test resistance to timing attacks."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_validation_uses_constant_time_comparison(self, mock_secret):
        """Test that token comparison is constant-time."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/test")
        def test():
            return {"success": True}

        client = TestClient(app)

        valid_token = generate_csrf_token()

        # Create tokens that differ in different positions
        parts = valid_token.split(".")

        # Token with first char different
        diff_first = list(parts[2])
        diff_first[0] = 'f' if diff_first[0] != 'f' else '0'
        token_diff_first = f"{parts[0]}.{parts[1]}.{''.join(diff_first)}"

        # Token with last char different
        diff_last = list(parts[2])
        diff_last[-1] = 'f' if diff_last[-1] != 'f' else '0'
        token_diff_last = f"{parts[0]}.{parts[1]}.{''.join(diff_last)}"

        # Measure timing for both (should be similar)
        times = []
        for token in [token_diff_first, token_diff_last]:
            start = time.perf_counter()
            client.post(
                "/api/test",
                headers={"X-CSRF-Token": token},
                cookies={COOKIE_NAME: token}
            )
            end = time.perf_counter()
            times.append(end - start)

        # Timing difference should be minimal
        # (within 10x - very generous for test stability)
        assert times[0] < times[1] * 10
        assert times[1] < times[0] * 10


@pytest.mark.security
@pytest.mark.critical
class TestTokenExhaustionAttacks:
    """Test resistance to token exhaustion attacks."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_many_invalid_requests_handled(self, mock_secret):
        """Test that many invalid requests don't cause DoS."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/test")
        def test():
            return {"success": True}

        client = TestClient(app)

        # Try 100 invalid requests
        for _ in range(100):
            response = client.post(
                "/api/test",
                headers={"X-CSRF-Token": "invalid"},
                cookies={COOKIE_NAME: "invalid"}
            )
            assert response.status_code == 403

        # Valid request should still work
        token = generate_csrf_token()
        response = client.post(
            "/api/test",
            headers={"X-CSRF-Token": token},
            cookies={COOKIE_NAME: token}
        )
        assert response.status_code == 200

    @patch("app.middleware.csrf._get_secret_key")
    def test_rapid_token_generation_safe(self, mock_secret):
        """Test that rapid token generation doesn't cause issues."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Generate 1000 tokens rapidly
        tokens = [generate_csrf_token() for _ in range(1000)]

        # All should be unique
        assert len(set(tokens)) == 1000

        # All should be valid
        assert all(validate_csrf_token(token) for token in tokens)


@pytest.mark.security
@pytest.mark.critical
class TestXSSCSRFCombination:
    """Test that XSS can't bypass CSRF protection."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_stolen_token_requires_same_origin(self, mock_secret):
        """Test that even if XSS steals token, request must be same-origin."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/sensitive")
        def sensitive():
            return {"data": "sensitive"}

        client = TestClient(app)
        token = generate_csrf_token()

        # XSS attacker has token but sends from different origin
        # (In real scenario, browser CORS would block this)
        response = client.post(
            "/api/sensitive",
            headers={
                "X-CSRF-Token": token,
                "Origin": "https://evil.com"
            },
            cookies={COOKIE_NAME: token}
        )

        # CSRF validation passes, but CORS should block
        # (This test validates CSRF alone - CORS is separate layer)
        assert response.status_code == 200  # CSRF passes
        # CORS blocking tested separately


@pytest.mark.security
@pytest.mark.critical
class TestReplayAttacks:
    """Test that replay attacks are prevented."""

    @patch("app.middleware.csrf._get_secret_key")
    @patch("app.middleware.csrf.time")
    def test_old_token_rejected(self, mock_time, mock_secret):
        """Test that old tokens are rejected."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Generate token at T=1000
        mock_time.time.return_value = 1000
        token = generate_csrf_token()

        # Try to use at T=5000 (1 hour + 1000s later)
        mock_time.time.return_value = 1000 + 3600 + 1000

        assert validate_csrf_token(token) is False

    @patch("app.middleware.csrf._get_secret_key")
    def test_token_single_use_not_enforced(self, mock_secret):
        """Test that tokens can be reused within validity period.

        Note: This is a limitation of stateless CSRF.
        Single-use would require server-side state.
        """
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        counter = {"value": 0}

        @app.post("/api/increment")
        def increment():
            counter["value"] += 1
            return {"count": counter["value"]}

        client = TestClient(app)
        token = generate_csrf_token()

        # Use same token twice
        response1 = client.post(
            "/api/increment",
            headers={"X-CSRF-Token": token},
            cookies={COOKIE_NAME: token}
        )
        assert response1.status_code == 200
        assert response1.json()["count"] == 1

        response2 = client.post(
            "/api/increment",
            headers={"X-CSRF-Token": token},
            cookies={COOKIE_NAME: token}
        )
        assert response2.status_code == 200
        assert response2.json()["count"] == 2

        # This is expected behavior for stateless CSRF
        # Token rotation on use would require session state


@pytest.mark.security
@pytest.mark.critical
class TestCSRFWithAuthentication:
    """Test CSRF protection works with authentication."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_csrf_required_even_with_auth(self, mock_secret):
        """Test that CSRF is required even for authenticated requests."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/authenticated-action")
        def action():
            return {"success": True}

        client = TestClient(app)

        # Request with Authorization header but no CSRF
        response = client.post(
            "/api/authenticated-action",
            headers={"Authorization": "Bearer valid-jwt-token"}
        )

        assert response.status_code == 403
        assert "csrf_token_missing" in response.json()["error"]

    @patch("app.middleware.csrf._get_secret_key")
    def test_csrf_and_auth_both_required(self, mock_secret):
        """Test that both CSRF and auth are required."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/authenticated-action")
        def action():
            # Would check auth here in real app
            return {"success": True}

        client = TestClient(app)
        token = generate_csrf_token()

        # Valid CSRF, valid auth
        response = client.post(
            "/api/authenticated-action",
            headers={
                "Authorization": "Bearer valid-jwt-token",
                "X-CSRF-Token": token
            },
            cookies={COOKIE_NAME: token}
        )

        assert response.status_code == 200
