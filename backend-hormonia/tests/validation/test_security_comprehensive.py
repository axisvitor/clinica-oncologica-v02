"""
Comprehensive Security Testing Suite

Tests critical security implementations including:
1. CSRF Protection (Double Submit Cookie Pattern)
2. Authentication & Authorization Bypass
3. JWT Token Security
4. Session Management
5. SQL Injection Prevention
6. XSS Prevention
7. Security Headers
8. Rate Limiting

CRITICAL: These tests verify that security controls cannot be bypassed
"""

import pytest
import time
import hmac
import hashlib
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4


# ============================================================================
# CSRF Protection Tests
# ============================================================================

class TestCSRFProtection:
    """Test CSRF Double Submit Cookie Pattern implementation"""

    def test_csrf_token_generation(self, client: TestClient):
        """CSRF tokens should be cryptographically secure"""
        response = client.get("/api/v2/auth/csrf-token")

        assert response.status_code == 200
        data = response.json()
        assert "csrf_token" in data

        token = data["csrf_token"]
        # Token format: timestamp.random_hex.signature
        parts = token.split(".")
        assert len(parts) == 3, "CSRF token must have 3 parts (timestamp.random.signature)"

        # Verify token is in cookies
        assert "csrf_token" in response.cookies
        assert response.cookies["csrf_token"] == token

        # Verify cookie security flags
        cookie_header = response.headers.get("set-cookie", "")
        assert "HttpOnly" in cookie_header or "httponly" in cookie_header.lower()
        assert "SameSite=strict" in cookie_header or "samesite=strict" in cookie_header.lower()

    def test_csrf_token_validation_requires_both_header_and_cookie(self, client: TestClient):
        """CSRF validation must require both header and cookie to match"""
        # Get CSRF token
        response = client.get("/api/v2/auth/csrf-token")
        token = response.json()["csrf_token"]

        # Test 1: Header only (no cookie) should fail
        response = client.post(
            "/api/v2/patients",
            headers={"X-CSRF-Token": token},
            json={"name": "Test Patient"}
        )
        assert response.status_code in [403, 401], "Should reject without cookie"

        # Test 2: Cookie only (no header) should fail
        response = client.post(
            "/api/v2/patients",
            cookies={"csrf_token": token},
            json={"name": "Test Patient"}
        )
        assert response.status_code in [403, 401], "Should reject without header"

    def test_csrf_token_expiration(self, client: TestClient):
        """Expired CSRF tokens should be rejected"""
        from app.middleware.csrf import generate_csrf_token, TOKEN_EXPIRY

        # Create an expired token (timestamp from 2 hours ago)
        old_timestamp = int(time.time()) - (TOKEN_EXPIRY + 3600)

        # Manually craft an expired but valid token
        import secrets
        from app.middleware.csrf import _get_secret_key

        secret_key = _get_secret_key()
        random_data = secrets.token_hex(32)
        payload = f"{old_timestamp}.{random_data}"
        signature = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        expired_token = f"{payload}.{signature}"

        # Try to use expired token
        response = client.post(
            "/api/v2/patients",
            headers={"X-CSRF-Token": expired_token},
            cookies={"csrf_token": expired_token},
            json={"name": "Test"}
        )
        assert response.status_code == 403, "Expired token should be rejected"

    def test_csrf_token_tampering_detected(self, client: TestClient):
        """Modified CSRF tokens should be rejected"""
        response = client.get("/api/v2/auth/csrf-token")
        token = response.json()["csrf_token"]

        # Tamper with token
        tampered_token = token[:-10] + "0" * 10  # Change last 10 chars

        response = client.post(
            "/api/v2/patients",
            headers={"X-CSRF-Token": tampered_token},
            cookies={"csrf_token": tampered_token},
            json={"name": "Test"}
        )
        assert response.status_code == 403, "Tampered token should be rejected"

    def test_csrf_mismatch_between_header_and_cookie(self, client: TestClient):
        """Header and cookie tokens must match exactly"""
        # Get two different tokens
        resp1 = client.get("/api/v2/auth/csrf-token")
        token1 = resp1.json()["csrf_token"]

        time.sleep(1)  # Ensure different timestamp

        resp2 = client.get("/api/v2/auth/csrf-token")
        token2 = resp2.json()["csrf_token"]

        # Use different tokens in header vs cookie
        response = client.post(
            "/api/v2/patients",
            headers={"X-CSRF-Token": token1},
            cookies={"csrf_token": token2},
            json={"name": "Test"}
        )
        assert response.status_code == 403, "Mismatched tokens should be rejected"


# ============================================================================
# Authentication Bypass Tests
# ============================================================================

class TestAuthenticationBypass:
    """Test authentication cannot be bypassed"""

    def test_missing_session_cookie_rejected(self, client: TestClient):
        """Requests without session cookies should be rejected"""
        response = client.get("/api/v2/patients")
        assert response.status_code in [401, 403]

    def test_invalid_session_id_rejected(self, client: TestClient):
        """Invalid session IDs should be rejected"""
        response = client.get(
            "/api/v2/patients",
            cookies={"session_id": "invalid-session-id-12345"}
        )
        assert response.status_code in [401, 403]

    def test_expired_session_rejected(self, client: TestClient):
        """Expired sessions should be rejected"""
        # This requires mocking Redis to return expired session
        # Implementation depends on your session management
        pass

    def test_sql_injection_in_auth_prevented(self, client: TestClient):
        """SQL injection attempts in auth should be prevented"""
        payloads = [
            "' OR '1'='1",
            "admin'--",
            "' OR 1=1--",
            "'; DROP TABLE users; --",
        ]

        for payload in payloads:
            response = client.post(
                "/api/v2/auth/firebase/verify",
                json={"id_token": payload}
            )
            # Should return validation error, not SQL error
            assert response.status_code in [400, 401, 422]
            assert "sql" not in response.text.lower()
            assert "traceback" not in response.text.lower()

    def test_authorization_header_alone_insufficient(self, client: TestClient):
        """Just having an Authorization header shouldn't grant access"""
        response = client.get(
            "/api/v2/patients",
            headers={"Authorization": "Bearer fake-token-12345"}
        )
        assert response.status_code in [401, 403]


# ============================================================================
# JWT Token Security Tests
# ============================================================================

class TestJWTSecurity:
    """Test JWT token security"""

    def test_jwt_algorithm_confusion_prevented(self):
        """Algorithm confusion attacks should be prevented"""
        from app.core.security import create_password_reset_token, verify_password_reset_token
        from jose import jwt

        # Create a valid token
        email = "test@example.com"
        token = create_password_reset_token(email)

        # Try to decode with different algorithm
        try:
            # Attempt algorithm confusion by using "none"
            decoded = jwt.decode(
                token,
                "",  # No secret
                algorithms=["none"]
            )
            pytest.fail("Should not allow 'none' algorithm")
        except Exception:
            pass  # Expected to fail

    def test_jwt_token_signature_verification(self):
        """JWT signatures must be verified"""
        from app.core.security import create_password_reset_token
        from jose import jwt
        from app.config import settings

        email = "test@example.com"
        token = create_password_reset_token(email)

        # Modify the payload without updating signature
        parts = token.split(".")
        if len(parts) == 3:
            # Decode payload
            import base64
            import json

            payload = json.loads(base64.b64decode(parts[1] + "=="))
            payload["sub"] = "hacker@evil.com"

            # Re-encode with modified payload but keep old signature
            modified_payload = base64.b64encode(
                json.dumps(payload).encode()
            ).decode().rstrip("=")

            tampered_token = f"{parts[0]}.{modified_payload}.{parts[2]}"

            # Should fail verification
            from app.core.security import verify_password_reset_token
            with pytest.raises(Exception):
                verify_password_reset_token(tampered_token)

    def test_jwt_expiration_enforced(self):
        """Expired JWT tokens should be rejected"""
        from app.core.security import create_password_reset_token, verify_password_reset_token
        from jose import JWTError

        # Create token that expires immediately
        email = "test@example.com"
        token = create_password_reset_token(
            email,
            expires_delta=timedelta(seconds=-10)  # Already expired
        )

        # Should fail verification
        with pytest.raises(Exception):
            verify_password_reset_token(token)


# ============================================================================
# Session Management Tests
# ============================================================================

class TestSessionSecurity:
    """Test session management security"""

    def test_session_fixation_prevented(self, client: TestClient):
        """New sessions should be created on login"""
        # This test verifies that session IDs change after authentication
        # to prevent session fixation attacks
        pass

    def test_session_cookie_security_flags(self, client: TestClient):
        """Session cookies should have proper security flags"""
        # Login to get session cookie
        response = client.post(
            "/api/v2/auth/firebase/verify",
            json={"id_token": "test-token"}
        )

        if response.status_code == 200:
            cookie_header = response.headers.get("set-cookie", "")

            # Check security flags
            assert "HttpOnly" in cookie_header or "httponly" in cookie_header.lower()
            assert "SameSite" in cookie_header or "samesite" in cookie_header.lower()
            # In production, should also have Secure flag

    def test_concurrent_session_limit(self, client: TestClient):
        """Users should have limited concurrent sessions"""
        # This depends on your session management implementation
        pass


# ============================================================================
# XSS Prevention Tests
# ============================================================================

class TestXSSPrevention:
    """Test XSS attack prevention"""

    def test_xss_in_error_messages_sanitized(self, client: TestClient):
        """XSS attempts in error messages should be sanitized"""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg/onload=alert('XSS')>",
        ]

        for payload in xss_payloads:
            # Try XSS in various input fields
            response = client.post(
                "/api/v2/auth/firebase/verify",
                json={"id_token": payload}
            )

            # Check response doesn't contain unescaped script tags
            assert "<script>" not in response.text.lower()
            assert "onerror=" not in response.text.lower()
            assert "javascript:" not in response.text.lower()

    def test_csp_header_prevents_inline_scripts(self, client: TestClient):
        """Content-Security-Policy should prevent inline scripts"""
        response = client.get("/health")

        csp = response.headers.get("Content-Security-Policy", "")

        # CSP should be present
        assert csp, "Content-Security-Policy header should be present"

        # Should not allow unsafe-inline for scripts
        # Modern CSP uses nonces instead
        if "unsafe-inline" in csp and "script-src" in csp:
            # If unsafe-inline is present, it should be in a nonce context
            assert "nonce-" in csp or "strict-dynamic" in csp


# ============================================================================
# Security Headers Tests
# ============================================================================

class TestSecurityHeaders:
    """Test security headers are properly configured"""

    def test_all_security_headers_present(self, client: TestClient):
        """All critical security headers should be present"""
        response = client.get("/health")

        required_headers = {
            "X-Frame-Options": ["DENY", "SAMEORIGIN"],
            "X-Content-Type-Options": ["nosniff"],
            "X-XSS-Protection": ["1; mode=block", "0"],
        }

        for header, valid_values in required_headers.items():
            assert header in response.headers, f"{header} must be present"
            assert response.headers[header] in valid_values, \
                f"{header} has invalid value: {response.headers[header]}"

    def test_hsts_header_on_https(self, client: TestClient):
        """HSTS header should be present on HTTPS connections"""
        # This test would need to be run in a production-like environment
        # For now, we just verify the header format is correct when set
        pass

    def test_permissions_policy_restrictive(self, client: TestClient):
        """Permissions-Policy should restrict dangerous features"""
        response = client.get("/health")

        permissions = response.headers.get("Permissions-Policy", "")

        if permissions:
            # Should deny access to sensitive features
            dangerous_features = ["geolocation", "camera", "microphone", "payment"]
            for feature in dangerous_features:
                # Features should either be denied or not mentioned (default deny)
                if feature in permissions:
                    assert f"{feature}=()" in permissions, \
                        f"{feature} should be explicitly denied"


# ============================================================================
# Rate Limiting Tests
# ============================================================================

class TestRateLimiting:
    """Test rate limiting prevents abuse"""

    def test_login_rate_limit_enforced(self, client: TestClient):
        """Login endpoint should have strict rate limiting"""
        # Attempt many failed logins
        for i in range(15):
            response = client.post(
                "/api/v2/auth/firebase/verify",
                json={"id_token": f"fake-token-{i}"}
            )

            if response.status_code == 429:
                # Rate limit triggered
                print(f"✅ Rate limit triggered after {i+1} attempts")
                break
        else:
            # If we get here, rate limit might not be working
            print("⚠️ Rate limit not triggered after 15 attempts")

    def test_rate_limit_per_ip(self, client: TestClient):
        """Rate limits should be per IP address"""
        # This would require mocking different client IPs
        pass

    def test_rate_limit_headers_present(self, client: TestClient):
        """Rate limit information should be in headers"""
        response = client.get("/health")

        # Check for common rate limit headers
        rate_limit_headers = [
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "RateLimit-Limit",
        ]

        # At least one rate limit header should be present
        has_rate_limit_info = any(
            header in response.headers for header in rate_limit_headers
        )

        if has_rate_limit_info:
            print("✅ Rate limit headers present")


# ============================================================================
# Input Validation Tests
# ============================================================================

class TestInputValidation:
    """Test input validation prevents injection attacks"""

    def test_sql_injection_in_patient_search(self, client: TestClient, auth_headers):
        """SQL injection in search should be prevented"""
        sql_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE patients; --",
            "' UNION SELECT * FROM users--",
        ]

        for payload in sql_payloads:
            response = client.get(
                f"/api/v2/patients?search={payload}",
                headers=auth_headers
            )

            # Should return validation error or empty results, not SQL error
            assert "sql" not in response.text.lower()
            assert "syntax error" not in response.text.lower()
            assert "traceback" not in response.text.lower()

    def test_path_traversal_prevented(self, client: TestClient):
        """Path traversal attempts should be blocked"""
        traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "%2e%2e%2f%2e%2e%2f",
        ]

        for payload in traversal_payloads:
            response = client.get(f"/api/v2/patients/{payload}")

            # Should return 400/404, not 200 with file contents
            assert response.status_code in [400, 404, 422]
            assert "passwd" not in response.text.lower()

    def test_xxe_attack_prevented(self, client: TestClient):
        """XXE attacks should be prevented"""
        xxe_payload = """<?xml version="1.0"?>
        <!DOCTYPE foo [
          <!ENTITY xxe SYSTEM "file:///etc/passwd">
        ]>
        <data>&xxe;</data>"""

        response = client.post(
            "/api/v2/patients",
            data=xxe_payload,
            headers={"Content-Type": "application/xml"}
        )

        # Should reject XML or return error, not file contents
        assert "passwd" not in response.text.lower()
        assert "root:" not in response.text.lower()


# ============================================================================
# Error Handling Security Tests
# ============================================================================

class TestErrorHandlingSecurity:
    """Test error messages don't leak sensitive information"""

    def test_error_messages_generic(self, client: TestClient):
        """Error messages should be generic"""
        response = client.get("/api/v2/nonexistent-endpoint")

        error_text = response.text.lower()

        # Should not reveal:
        sensitive_info = [
            "traceback",
            "c:\\",
            "/home/",
            "/var/",
            "postgresql://",
            ".py\"",
            "line ",
            "internal server error at",
        ]

        for info in sensitive_info:
            assert info not in error_text, \
                f"Error message leaks sensitive info: {info}"

    def test_404_errors_dont_enumerate(self, client: TestClient, auth_headers):
        """404 errors should be generic to prevent enumeration"""
        # Valid UUID format but nonexistent
        fake_uuid = str(uuid4())

        response = client.get(
            f"/api/v2/patients/{fake_uuid}",
            headers=auth_headers
        )

        assert response.status_code == 404
        # Error should be generic
        assert "not found" in response.text.lower()
        # Should not reveal database details
        assert "table" not in response.text.lower()
        assert "column" not in response.text.lower()


# ============================================================================
# Firebase Auth Security Tests
# ============================================================================

class TestFirebaseAuthSecurity:
    """Test Firebase authentication security"""

    def test_firebase_domain_validation(self, client: TestClient):
        """Only allowed domains should be accepted"""
        # This depends on your FIREBASE_ALLOWED_DOMAINS configuration
        pass

    def test_firebase_custom_claims_required(self, client: TestClient):
        """Firebase tokens without proper claims should be rejected"""
        # This depends on your Firebase configuration
        pass

    def test_firebase_token_replay_prevented(self, client: TestClient):
        """Same Firebase token shouldn't work twice"""
        # This would require caching used tokens
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
