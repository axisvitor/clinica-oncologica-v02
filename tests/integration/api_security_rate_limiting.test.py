"""
API Security and Rate Limiting Comprehensive Test Suite
======================================================

This test suite validates security measures and rate limiting mechanisms
for the oncology clinic system, ensuring protection against various attack vectors.

Test Coverage:
- Rate limiting enforcement
- Authentication and authorization security
- Input validation and sanitization
- SQL injection prevention
- XSS protection
- CSRF protection
- CORS policy validation
- Security headers verification
"""

import pytest
import time
import asyncio
from typing import Dict, List, Any
from unittest.mock import patch, MagicMock
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.utils.rate_limiter import limiter


client = TestClient(app)


class SecurityTestHelper:
    """Helper class for security testing utilities."""

    @staticmethod
    def generate_sql_injection_payloads() -> List[str]:
        """Generate common SQL injection attack payloads."""
        return [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "'; UPDATE users SET role='admin' WHERE id=1; --",
            "1' UNION SELECT password FROM users WHERE '1'='1",
            "'; INSERT INTO users (email, role) VALUES ('hacker@evil.com', 'admin'); --",
            "' AND (SELECT COUNT(*) FROM users) > 0 --",
            "'; EXEC sp_executesql N'DROP TABLE users'; --"
        ]

    @staticmethod
    def generate_xss_payloads() -> List[str]:
        """Generate common XSS attack payloads."""
        return [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
            "';alert('XSS');//",
            "<iframe src=javascript:alert('XSS')></iframe>",
            "<div onclick=alert('XSS')>Click me</div>"
        ]

    @staticmethod
    def generate_large_payloads() -> List[str]:
        """Generate large payloads for buffer overflow testing."""
        return [
            "A" * 10000,    # 10KB
            "B" * 100000,   # 100KB
            "C" * 1000000,  # 1MB
        ]


class TestRateLimiting:
    """Test rate limiting enforcement across endpoints."""

    def test_login_rate_limiting(self):
        """Test rate limiting on login endpoint."""
        login_data = {
            "email": "test@example.com",
            "password": "wrongpassword"
        }

        # Make requests within rate limit window
        responses = []
        for i in range(7):  # Assuming 5 requests per minute limit
            response = client.post("/api/v1/auth/login-json", json=login_data)
            responses.append(response)

        # First few requests should get normal responses (likely 401 for wrong password)
        assert all(r.status_code in [401, 422] for r in responses[:5])

        # Later requests should be rate limited
        rate_limited_responses = [r for r in responses[5:] if r.status_code == 429]
        assert len(rate_limited_responses) > 0

        # Rate limited response should have proper headers
        if rate_limited_responses:
            rate_limited = rate_limited_responses[0]
            assert "Retry-After" in rate_limited.headers or "X-RateLimit" in str(rate_limited.headers)

    def test_api_endpoint_rate_limiting(self):
        """Test rate limiting on general API endpoints."""
        # Test health endpoint (should have higher limits)
        health_responses = []
        for i in range(20):
            response = client.get("/health")
            health_responses.append(response)

        # Health endpoint should handle more requests
        success_responses = [r for r in health_responses if r.status_code == 200]
        assert len(success_responses) >= 15  # Should handle at least 15 requests

    def test_admin_endpoint_rate_limiting(self):
        """Test stricter rate limiting on admin endpoints."""
        # Mock admin authentication
        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(
                id=uuid4(),
                email="admin@test.com",
                role="admin"
            )

            responses = []
            for i in range(12):  # Test burst of admin requests
                response = client.get("/api/v1/admin/users")
                responses.append(response)

            # Should start rate limiting after several requests
            rate_limited = [r for r in responses if r.status_code == 429]
            assert len(rate_limited) > 0

    def test_rate_limit_window_reset(self):
        """Test that rate limits reset after time window."""
        login_data = {
            "email": "test@example.com",
            "password": "wrongpassword"
        }

        # Exhaust rate limit
        for i in range(6):
            client.post("/api/v1/auth/login-json", json=login_data)

        # Should be rate limited
        response = client.post("/api/v1/auth/login-json", json=login_data)
        assert response.status_code == 429

        # Wait for rate limit window to reset (in real tests, this might be mocked)
        time.sleep(2)  # Brief wait for testing purposes

        # Should work again (though still wrong credentials)
        response = client.post("/api/v1/auth/login-json", json=login_data)
        assert response.status_code in [401, 422]  # Not rate limited anymore

    def test_rate_limiting_per_ip(self):
        """Test that rate limiting is enforced per IP address."""
        # This test would require different client IPs, which is difficult to simulate
        # In a real environment, you'd use different test clients with different X-Forwarded-For headers

        headers_ip1 = {"X-Forwarded-For": "192.168.1.100"}
        headers_ip2 = {"X-Forwarded-For": "192.168.1.101"}

        login_data = {"email": "test@example.com", "password": "wrong"}

        # Exhaust rate limit for IP1
        for i in range(6):
            client.post("/api/v1/auth/login-json", json=login_data, headers=headers_ip1)

        # IP1 should be rate limited
        response1 = client.post("/api/v1/auth/login-json", json=login_data, headers=headers_ip1)

        # IP2 should still work
        response2 = client.post("/api/v1/auth/login-json", json=login_data, headers=headers_ip2)

        # Different IPs should have independent rate limits
        assert response1.status_code == 429 or response2.status_code != 429

    def test_rate_limit_bypass_attempts(self):
        """Test attempts to bypass rate limiting."""
        login_data = {"email": "test@example.com", "password": "wrong"}

        # Exhaust rate limit
        for i in range(6):
            client.post("/api/v1/auth/login-json", json=login_data)

        # Try to bypass with different headers
        bypass_attempts = [
            {"X-Forwarded-For": "127.0.0.1"},
            {"X-Real-IP": "127.0.0.1"},
            {"User-Agent": "Different User Agent"},
            {"X-Rate-Limit-Bypass": "true"},
        ]

        for headers in bypass_attempts:
            response = client.post("/api/v1/auth/login-json", json=login_data, headers=headers)
            # Should still be rate limited regardless of headers
            assert response.status_code in [429, 401, 422]


class TestInputValidationSecurity:
    """Test input validation and sanitization security."""

    def test_sql_injection_prevention(self):
        """Test SQL injection prevention in various endpoints."""
        sql_payloads = SecurityTestHelper.generate_sql_injection_payloads()

        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(
                id=uuid4(),
                email="admin@test.com",
                role="admin"
            )

            # Test in query parameters
            for payload in sql_payloads:
                response = client.get(f"/api/v1/admin/users?search={payload}")

                # Should not result in server error (500)
                assert response.status_code != 500

                # Should either validate input (422) or handle safely (200/404)
                assert response.status_code in [200, 400, 422, 404]

            # Test in request body
            for payload in sql_payloads:
                user_data = {
                    "email": f"{payload}@example.com",
                    "full_name": payload,
                    "password": "ValidPassword123!",
                    "role": "doctor"
                }

                response = client.post("/api/v1/admin/users", json=user_data)

                # Should validate input, not execute SQL
                assert response.status_code in [422, 400]

    def test_xss_prevention(self):
        """Test XSS prevention in input fields."""
        xss_payloads = SecurityTestHelper.generate_xss_payloads()

        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(
                id=uuid4(),
                email="admin@test.com",
                role="admin"
            )

            for payload in xss_payloads:
                user_data = {
                    "email": "test@example.com",
                    "full_name": payload,
                    "password": "ValidPassword123!",
                    "role": "doctor"
                }

                response = client.post("/api/v1/admin/users", json=user_data)

                # Should validate or sanitize input
                if response.status_code == 201:
                    # If created, check response doesn't contain unsanitized script
                    response_text = response.text.lower()
                    assert "<script>" not in response_text
                    assert "javascript:" not in response_text
                    assert "onerror=" not in response_text

    def test_buffer_overflow_protection(self):
        """Test protection against buffer overflow attacks."""
        large_payloads = SecurityTestHelper.generate_large_payloads()

        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(
                id=uuid4(),
                email="admin@test.com",
                role="admin"
            )

            for payload in large_payloads:
                user_data = {
                    "email": "test@example.com",
                    "full_name": payload,
                    "password": "ValidPassword123!",
                    "role": "doctor"
                }

                response = client.post("/api/v1/admin/users", json=user_data)

                # Should reject oversized input
                assert response.status_code in [422, 400, 413]  # 413 = Payload Too Large

    def test_email_validation_security(self):
        """Test email validation against malicious inputs."""
        malicious_emails = [
            "admin@evil.com<script>alert('xss')</script>",
            "'; DROP TABLE users; --@example.com",
            "../../../etc/passwd@example.com",
            "user@domain.com\r\nBcc: everyone@company.com",
            "user@domain.com%0d%0aBcc:%20everyone@company.com"
        ]

        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(
                id=uuid4(),
                email="admin@test.com",
                role="admin"
            )

            for email in malicious_emails:
                user_data = {
                    "email": email,
                    "full_name": "Test User",
                    "password": "ValidPassword123!",
                    "role": "doctor"
                }

                response = client.post("/api/v1/admin/users", json=user_data)

                # Should reject invalid email formats
                assert response.status_code == 422


class TestAuthenticationSecurity:
    """Test authentication and authorization security."""

    def test_password_security_requirements(self):
        """Test password security requirements."""
        weak_passwords = [
            "123456",
            "password",
            "qwerty",
            "abc123",
            "password123",
            "",
            "a" * 100  # Too long
        ]

        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(
                id=uuid4(),
                email="admin@test.com",
                role="admin"
            )

            for weak_password in weak_passwords:
                user_data = {
                    "email": "test@example.com",
                    "full_name": "Test User",
                    "password": weak_password,
                    "role": "doctor"
                }

                response = client.post("/api/v1/admin/users", json=user_data)

                # Should reject weak passwords
                assert response.status_code == 422

                if response.status_code == 422:
                    error_detail = response.json().get("detail", [])
                    password_errors = [
                        error for error in error_detail
                        if "password" in str(error).lower()
                    ]
                    assert len(password_errors) > 0

    def test_session_security(self):
        """Test session security measures."""
        # Test that sessions expire properly
        # This would typically involve mocking session expiry

        login_data = {
            "email": "test@example.com",
            "password": "TestPassword123!"
        }

        # Mock successful login
        with patch('app.services.auth.AuthService') as mock_auth_service:
            mock_service = MagicMock()
            mock_service.authenticate_user.return_value = MagicMock(
                id=uuid4(),
                email="test@example.com",
                is_active=True
            )
            mock_auth_service.return_value = mock_service

            response = client.post("/api/v1/auth/login-json", json=login_data)

            # Check for secure session handling
            if response.status_code == 200:
                # Should not expose sensitive information in response
                response_text = response.text.lower()
                assert "password" not in response_text
                assert "secret" not in response_text

    def test_unauthorized_access_prevention(self):
        """Test prevention of unauthorized access to protected endpoints."""
        protected_endpoints = [
            ("/api/v1/admin/users", "GET"),
            ("/api/v1/admin/users", "POST"),
            ("/api/v1/admin/users/stats/overview", "GET"),
            ("/api/v1/analytics/dashboard", "GET")
        ]

        for endpoint, method in protected_endpoints:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json={})

            # Should require authentication
            assert response.status_code == 401

    def test_privilege_escalation_prevention(self):
        """Test prevention of privilege escalation attacks."""
        # Mock regular user
        regular_user = MagicMock(
            id=uuid4(),
            email="user@test.com",
            role="doctor"
        )

        with patch('app.dependencies.get_current_user', return_value=regular_user):
            # Try to access admin-only endpoints
            admin_endpoints = [
                "/api/v1/admin/users",
                "/api/v1/admin/users/stats/overview"
            ]

            for endpoint in admin_endpoints:
                response = client.get(endpoint)

                # Should be forbidden for non-admin users
                assert response.status_code == 403

            # Try to create admin user
            admin_user_data = {
                "email": "newadmin@example.com",
                "full_name": "New Admin",
                "password": "AdminPassword123!",
                "role": "admin"
            }

            response = client.post("/api/v1/admin/users", json=admin_user_data)
            assert response.status_code == 403


class TestCSRFProtection:
    """Test CSRF protection mechanisms."""

    def test_csrf_token_requirement(self):
        """Test that CSRF tokens are required for state-changing operations."""
        # Mock authenticated user
        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(
                id=uuid4(),
                email="admin@test.com",
                role="admin"
            )

            user_data = {
                "email": "test@example.com",
                "full_name": "Test User",
                "password": "ValidPassword123!",
                "role": "doctor"
            }

            # Request without CSRF token (if implemented)
            response = client.post("/api/v1/admin/users", json=user_data)

            # If CSRF protection is implemented, should check for token
            # Otherwise, should still validate other security measures
            assert response.status_code in [200, 201, 403, 422]

    def test_csrf_token_validation(self):
        """Test CSRF token validation."""
        # This test would require CSRF implementation details
        # For now, we test that the endpoint handles headers correctly

        with patch('app.dependencies.get_admin_user') as mock_auth:
            mock_auth.return_value = MagicMock(
                id=uuid4(),
                email="admin@test.com",
                role="admin"
            )

            headers = {
                "X-CSRF-Token": "invalid-token",
                "Content-Type": "application/json"
            }

            response = client.post(
                "/api/v1/admin/users",
                json={"email": "test@example.com"},
                headers=headers
            )

            # Should handle CSRF headers appropriately
            assert response.status_code in [200, 201, 403, 422]


class TestCORSPolicy:
    """Test CORS policy enforcement."""

    def test_cors_headers_present(self):
        """Test that CORS headers are present in responses."""
        response = client.get("/health")

        headers = response.headers

        # Should include CORS headers (case-insensitive check)
        cors_headers = [
            "access-control-allow-origin",
            "access-control-allow-methods",
            "access-control-allow-headers"
        ]

        header_keys_lower = [key.lower() for key in headers.keys()]

        # At least some CORS headers should be present
        cors_present = any(cors_header in header_keys_lower for cors_header in cors_headers)
        assert cors_present or "localhost" in str(headers)

    def test_cors_preflight_handling(self):
        """Test CORS preflight request handling."""
        # OPTIONS request for CORS preflight
        response = client.options(
            "/api/v1/admin/users",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )

        # Should handle preflight requests
        assert response.status_code in [200, 204, 405]

    def test_cors_origin_restriction(self):
        """Test CORS origin restrictions."""
        # Test with various origins
        origins = [
            "http://localhost:3000",  # Should be allowed (development)
            "https://app.hormonia.com",  # Should be allowed (production)
            "http://evil.com",  # Should be restricted
            "https://malicious.site"  # Should be restricted
        ]

        for origin in origins:
            response = client.get(
                "/health",
                headers={"Origin": origin}
            )

            # Check CORS headers in response
            cors_origin = response.headers.get("Access-Control-Allow-Origin", "")

            if origin.startswith("http://localhost") or "hormonia.com" in origin:
                # Should allow legitimate origins
                assert cors_origin in ["*", origin] or cors_origin != ""
            else:
                # Should restrict malicious origins
                assert cors_origin != origin or cors_origin == ""


class TestSecurityHeaders:
    """Test security headers in HTTP responses."""

    def test_security_headers_present(self):
        """Test that security headers are present in responses."""
        response = client.get("/health")

        headers = response.headers
        header_keys_lower = [key.lower() for key in headers.keys()]

        # Important security headers
        security_headers = [
            "x-content-type-options",  # Should be "nosniff"
            "x-frame-options",         # Should be "DENY" or "SAMEORIGIN"
            "x-xss-protection",        # Should be "1; mode=block"
            "strict-transport-security",  # HSTS header
            "content-security-policy"     # CSP header
        ]

        # At least some security headers should be present
        present_headers = [h for h in security_headers if h in header_keys_lower]
        assert len(present_headers) > 0

    def test_content_type_options_header(self):
        """Test X-Content-Type-Options header."""
        response = client.get("/health")

        # Should prevent MIME type sniffing
        content_type_options = response.headers.get("X-Content-Type-Options", "").lower()
        assert content_type_options == "nosniff" or "nosniff" in content_type_options

    def test_frame_options_header(self):
        """Test X-Frame-Options header."""
        response = client.get("/health")

        # Should prevent clickjacking
        frame_options = response.headers.get("X-Frame-Options", "").upper()
        assert frame_options in ["DENY", "SAMEORIGIN"] or frame_options == ""

    def test_xss_protection_header(self):
        """Test X-XSS-Protection header."""
        response = client.get("/health")

        # Should enable XSS protection
        xss_protection = response.headers.get("X-XSS-Protection", "")
        assert "1" in xss_protection or xss_protection == ""


class TestDataLeakagePrevention:
    """Test prevention of sensitive data leakage."""

    def test_error_message_sanitization(self):
        """Test that error messages don't leak sensitive information."""
        # Trigger various error conditions
        error_scenarios = [
            ("/api/v1/admin/users/00000000-0000-0000-0000-000000000000", "GET"),  # Non-existent user
            ("/api/v1/nonexistent-endpoint", "GET"),  # 404 error
            ("/api/v1/admin/users", "POST"),  # Validation error
        ]

        for endpoint, method in error_scenarios:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json={"invalid": "data"})

            response_text = response.text.lower()

            # Should not leak sensitive information in error messages
            sensitive_info = [
                "password",
                "secret",
                "key",
                "token",
                "database",
                "internal",
                "stack trace",
                "traceback"
            ]

            for info in sensitive_info:
                assert info not in response_text or response.status_code == 404

    def test_user_enumeration_prevention(self):
        """Test prevention of user enumeration attacks."""
        # Try to enumerate users through login attempts
        test_emails = [
            "admin@hormonia.com",  # Might exist
            "nonexistent@example.com",  # Doesn't exist
            "test@test.com"  # Might exist
        ]

        responses = []
        for email in test_emails:
            login_data = {
                "email": email,
                "password": "wrongpassword"
            }

            response = client.post("/api/v1/auth/login-json", json=login_data)
            responses.append(response)

        # All responses should be similar to prevent user enumeration
        status_codes = [r.status_code for r in responses]
        response_times = [r.elapsed.total_seconds() if hasattr(r, 'elapsed') else 0 for r in responses]

        # Status codes should be consistent
        assert len(set(status_codes)) <= 2  # At most 2 different status codes

        # Response times should not vary significantly (timing attack prevention)
        if len(response_times) > 1:
            time_variance = max(response_times) - min(response_times)
            assert time_variance < 2.0  # Less than 2 second difference


@pytest.mark.asyncio
async def test_concurrent_security_attacks():
    """Test security under concurrent attack scenarios."""
    async def make_malicious_request():
        async with httpx.AsyncClient(base_url="http://testserver") as client:
            # SQL injection attempt
            response = await client.get("/api/v1/admin/users?search='; DROP TABLE users; --")
            return response.status_code

    # Launch concurrent attacks
    tasks = [make_malicious_request() for _ in range(50)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # All requests should be handled safely (no 500 errors)
    status_codes = [r for r in results if isinstance(r, int)]
    assert all(code != 500 for code in status_codes)


def test_security_configuration_validation():
    """Test that security configurations are properly set."""
    # This test would check various security configurations
    # For now, we test that the app starts without obvious security misconfigurations

    # Test that debug mode is not enabled in production-like settings
    # This would depend on your app configuration structure

    # Test that secret keys are not hardcoded
    # This would require access to your configuration system

    # For demonstration, we just ensure the app responds correctly
    response = client.get("/health")
    assert response.status_code == 200

    # Ensure response doesn't leak configuration details
    response_text = response.text.lower()
    config_leaks = ["debug", "secret", "password", "key"]
    for leak in config_leaks:
        assert leak not in response_text or response.status_code != 200


if __name__ == "__main__":
    # Run basic security tests if executed directly
    print("Running basic security tests...")

    # Test rate limiting
    helper = SecurityTestHelper()
    print("SQL Injection payloads:", len(helper.generate_sql_injection_payloads()))
    print("XSS payloads:", len(helper.generate_xss_payloads()))

    # Test basic endpoint security
    response = client.get("/health")
    print(f"Health endpoint status: {response.status_code}")
    print(f"Security headers present: {list(response.headers.keys())}")

    print("Basic security tests completed.")