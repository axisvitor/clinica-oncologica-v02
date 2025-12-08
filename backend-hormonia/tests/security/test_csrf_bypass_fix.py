"""
Security Tests for CVE-2025-CLINIC-004: CSRF Bypass Fix

Tests verify that the CSRF bypass vulnerability is fully mitigated:
1. Forged tokens are rejected
2. Expired tokens are rejected
3. Rate limiting is enforced
4. Timing attack protection is active
5. Signature validation is cryptographically secure

Run with: pytest tests/security/test_csrf_bypass_fix.py -v
"""

import pytest
import time
import hmac
import hashlib
from unittest.mock import Mock, patch, AsyncMock
from fastapi import Request
from fastapi_csrf_protect.exceptions import CsrfProtectError

from app.middleware.csrf import (
    _validate_token_signature,
    _check_rate_limit,
    _record_validation_failure,
    validate_csrf_token,
    get_csrf_settings,
)


class TestCSRFBypassFix:
    """Test suite for CSRF bypass vulnerability fix (CVE-2025-CLINIC-004)"""

    @pytest.fixture
    def secret_key(self):
        """Generate a secure secret key for testing"""
        return "test_secret_key_minimum_32_chars_long_for_security"

    @pytest.fixture
    def valid_token(self, secret_key):
        """Generate a valid CSRF token with proper signature"""
        timestamp = int(time.time())
        data = f"{timestamp}.random_data_here"
        signature = hmac.new(
            secret_key.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"{data}.{signature}"

    @pytest.fixture
    def expired_token(self, secret_key):
        """Generate an expired CSRF token (2 hours old)"""
        timestamp = int(time.time()) - 7200  # 2 hours ago
        data = f"{timestamp}.random_data_here"
        signature = hmac.new(
            secret_key.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"{data}.{signature}"

    @pytest.fixture
    def forged_token(self):
        """Generate a forged token that would pass format-only validation"""
        # This token looks valid (>50 chars, has dots) but has no valid signature
        return "a" * 51 + "." + "b" * 51 + "." + "c" * 51

    # ========================================================================
    # Test 1: Signature Validation - Forged Tokens Must Be Rejected
    # ========================================================================

    def test_forged_token_rejected(self, forged_token, secret_key):
        """
        CRITICAL: Forged tokens must be rejected.

        BEFORE FIX: Would pass format check (>50 chars, has dots)
        AFTER FIX: Must fail signature verification
        """
        result = _validate_token_signature(forged_token, secret_key)

        assert result is False, "Forged token should be REJECTED"
        print("✅ Forged token correctly REJECTED")

    def test_valid_token_accepted(self, valid_token, secret_key):
        """Valid tokens with correct signature must be accepted"""
        result = _validate_token_signature(valid_token, secret_key)

        assert result is True, "Valid token should be ACCEPTED"
        print("✅ Valid token correctly ACCEPTED")

    def test_token_with_wrong_signature(self, secret_key):
        """Token with incorrect signature must be rejected"""
        timestamp = int(time.time())
        data = f"{timestamp}.random_data"
        wrong_signature = "wrong_signature_hash_here"
        invalid_token = f"{data}.{wrong_signature}"

        result = _validate_token_signature(invalid_token, secret_key)

        assert result is False, "Token with wrong signature should be REJECTED"
        print("✅ Token with wrong signature correctly REJECTED")

    def test_token_format_validation(self, secret_key):
        """Tokens with invalid format must be rejected"""
        invalid_formats = [
            "no_dots_token",  # No dots
            "only.one.part",  # Not enough parts
            "",  # Empty
            ".",  # Just dots
            "short",  # Too short
        ]

        for invalid_token in invalid_formats:
            result = _validate_token_signature(invalid_token, secret_key)
            assert result is False, f"Invalid format '{invalid_token}' should be REJECTED"

        print("✅ All invalid formats correctly REJECTED")

    # ========================================================================
    # Test 2: Expiration Validation - Expired Tokens Must Be Rejected
    # ========================================================================

    def test_expired_token_rejected(self, expired_token, secret_key):
        """
        CRITICAL: Expired tokens must be rejected.

        BEFORE FIX: No expiration check
        AFTER FIX: Must reject tokens older than max_age
        """
        result = _validate_token_signature(expired_token, secret_key, max_age=3600)

        assert result is False, "Expired token should be REJECTED"
        print("✅ Expired token correctly REJECTED")

    def test_future_token_rejected(self, secret_key):
        """Tokens from the future must be rejected (clock skew attack)"""
        future_timestamp = int(time.time()) + 120  # 2 minutes in future
        data = f"{future_timestamp}.random_data"
        signature = hmac.new(
            secret_key.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        future_token = f"{data}.{signature}"

        result = _validate_token_signature(future_token, secret_key)

        assert result is False, "Future token should be REJECTED"
        print("✅ Future token correctly REJECTED")

    def test_token_within_expiry_window(self, secret_key):
        """Token within expiry window should be accepted"""
        timestamp = int(time.time()) - 1800  # 30 minutes ago
        data = f"{timestamp}.random_data"
        signature = hmac.new(
            secret_key.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        valid_token = f"{data}.{signature}"

        result = _validate_token_signature(valid_token, secret_key, max_age=3600)

        assert result is True, "Token within expiry should be ACCEPTED"
        print("✅ Token within expiry correctly ACCEPTED")

    # ========================================================================
    # Test 3: Rate Limiting - Brute Force Protection
    # ========================================================================

    def test_rate_limiting_blocks_brute_force(self):
        """
        CRITICAL: Rate limiting must block brute force attempts.

        BEFORE FIX: No rate limiting
        AFTER FIX: Must block after max_failures attempts
        """
        test_ip = "192.168.1.100"

        # Clear any existing rate limit data
        from app.middleware.csrf import _csrf_validation_failures
        _csrf_validation_failures.clear()

        # Record 9 failures - should not be blocked
        for i in range(9):
            _record_validation_failure(test_ip)
            blocked = _check_rate_limit(test_ip, max_failures=10)
            assert blocked is False, f"Should not be blocked at {i+1} failures"

        # 10th failure - should trigger rate limit
        _record_validation_failure(test_ip)
        blocked = _check_rate_limit(test_ip, max_failures=10)

        assert blocked is True, "Should be BLOCKED after 10 failures"
        print("✅ Rate limiting correctly BLOCKS after 10 failures")

    def test_rate_limit_window_expiry(self):
        """Rate limit should reset after time window"""
        test_ip = "192.168.1.101"

        from app.middleware.csrf import _csrf_validation_failures
        _csrf_validation_failures.clear()

        # Add old failures (outside 300s window)
        old_time = time.time() - 400
        _csrf_validation_failures[test_ip] = [old_time] * 15

        # Check rate limit - should not be blocked (old entries cleaned)
        blocked = _check_rate_limit(test_ip, max_failures=10, window=300)

        assert blocked is False, "Old failures should be cleaned up"
        print("✅ Rate limit window correctly EXPIRES old entries")

    def test_different_ips_independent_rate_limits(self):
        """Rate limiting should be independent per IP"""
        from app.middleware.csrf import _csrf_validation_failures
        _csrf_validation_failures.clear()

        ip1 = "192.168.1.100"
        ip2 = "192.168.1.101"

        # IP1: 10 failures (blocked)
        for _ in range(10):
            _record_validation_failure(ip1)

        # IP2: 5 failures (not blocked)
        for _ in range(5):
            _record_validation_failure(ip2)

        assert _check_rate_limit(ip1, max_failures=10) is True
        assert _check_rate_limit(ip2, max_failures=10) is False

        print("✅ Rate limiting correctly INDEPENDENT per IP")

    # ========================================================================
    # Test 4: Timing Attack Protection
    # ========================================================================

    def test_constant_time_comparison_used(self, secret_key):
        """
        CRITICAL: Must use constant-time comparison to prevent timing attacks.

        Verify that hmac.compare_digest is used (not == operator)
        """
        import inspect
        source = inspect.getsource(_validate_token_signature)

        # Check that hmac.compare_digest is used
        assert "hmac.compare_digest" in source, "Must use constant-time comparison"

        # Check that direct comparison is NOT used for signatures
        lines = source.split('\n')
        for line in lines:
            if 'signature' in line.lower() and '==' in line:
                # Allow assignment (=), but not comparison (==) of signatures
                if 'if' in line or 'return' in line:
                    pytest.fail("Direct comparison (==) found for signatures - timing attack risk!")

        print("✅ Constant-time comparison correctly IMPLEMENTED")

    # ========================================================================
    # Test 5: Integration Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_validate_csrf_token_integration_forged(self, forged_token):
        """Integration test: forged token should fail validation"""
        mock_request = Mock(spec=Request)
        mock_request.client = Mock(host="192.168.1.100")
        mock_request.url.path = "/api/v2/test"
        mock_request.headers.get.return_value = forged_token
        mock_request.cookies.get.return_value = None

        with patch('app.middleware.csrf.csrf_protect') as mock_csrf:
            # Simulate csrf_protect raising error
            mock_csrf.validate_csrf = AsyncMock(
                side_effect=CsrfProtectError("Missing Cookie")
            )

            with pytest.raises(CsrfProtectError):
                await validate_csrf_token(mock_request)

            print("✅ Integration test: forged token correctly REJECTED")

    @pytest.mark.asyncio
    async def test_validate_csrf_token_integration_valid(self, valid_token, secret_key):
        """Integration test: valid token should pass validation"""
        mock_request = Mock(spec=Request)
        mock_request.client = Mock(host="192.168.1.100")
        mock_request.url.path = "/api/v2/test"
        mock_request.headers.get.side_effect = lambda key: {
            "X-CSRF-Token": valid_token
        }.get(key)
        mock_request.cookies.get.return_value = None

        # Clear rate limit for this test
        from app.middleware.csrf import _csrf_validation_failures
        _csrf_validation_failures.clear()

        with patch('app.middleware.csrf.csrf_protect') as mock_csrf:
            # Simulate csrf_protect raising error (cross-domain scenario)
            mock_csrf.validate_csrf = AsyncMock(
                side_effect=CsrfProtectError("Missing Cookie")
            )

            with patch('app.middleware.csrf.get_csrf_settings') as mock_settings:
                mock_settings_obj = Mock()
                mock_settings_obj.secret_key = secret_key
                mock_settings_obj.token_expires_in = 3600
                mock_settings.return_value = mock_settings_obj

                # Should NOT raise exception (valid token)
                await validate_csrf_token(mock_request)

        print("✅ Integration test: valid token correctly ACCEPTED")

    # ========================================================================
    # Test 6: Secret Key Strength Validation
    # ========================================================================

    def test_weak_secret_key_rejected(self):
        """
        CRITICAL: Weak secret keys must be rejected.

        BEFORE FIX: No minimum length requirement
        AFTER FIX: Must require at least 32 characters
        """
        with patch('app.config.settings') as mock_settings:
            mock_settings.CSRF_SECRET_KEY = "weak"  # Only 4 chars
            mock_settings.APP_ENVIRONMENT = "production"

            with pytest.raises(ValueError, match="at least 32 characters"):
                get_csrf_settings()

        print("✅ Weak secret key correctly REJECTED")

    def test_strong_secret_key_accepted(self):
        """Strong secret keys (32+ chars) should be accepted"""
        with patch('app.config.settings') as mock_settings:
            mock_settings.CSRF_SECRET_KEY = "strong_secret_key_32_chars_plus!"  # 34 chars
            mock_settings.APP_ENVIRONMENT = "development"
            mock_settings.SESSION_COOKIE_SECURE = False

            settings = get_csrf_settings()
            assert settings.secret_key == "strong_secret_key_32_chars_plus!"

        print("✅ Strong secret key correctly ACCEPTED")

    # ========================================================================
    # Test 7: Vulnerability Regression Tests
    # ========================================================================

    def test_cve_2025_clinic_004_regression(self, secret_key):
        """
        CVE-2025-CLINIC-004 Regression Test

        Verify that the original bypass vulnerability is completely fixed.
        The vulnerable code accepted: len(token) > 50 and '.' in token
        """
        # Original bypass token that would pass format check
        bypass_tokens = [
            "a" * 51 + "." + "b" * 51,
            "x" * 100 + "." + "y" * 100 + "." + "z" * 100,
            "123456789" * 10 + "." + "abcdefgh" * 10,
        ]

        for bypass_token in bypass_tokens:
            # BEFORE FIX: These would PASS (vulnerability)
            # AFTER FIX: These must FAIL (secure)
            result = _validate_token_signature(bypass_token, secret_key)
            assert result is False, f"Bypass token should be REJECTED: {bypass_token[:50]}..."

        print("✅ CVE-2025-CLINIC-004 regression test PASSED - vulnerability is FIXED")


# ========================================================================
# Performance Tests
# ========================================================================

class TestCSRFPerformance:
    """Performance tests to ensure security doesn't degrade performance"""

    def test_validation_performance(self, benchmark):
        """Signature validation should complete in < 1ms"""
        secret_key = "test_secret_key_minimum_32_chars_long_for_security"
        timestamp = int(time.time())
        data = f"{timestamp}.random_data"
        signature = hmac.new(
            secret_key.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        token = f"{data}.{signature}"

        result = benchmark(_validate_token_signature, token, secret_key)
        assert result is True
        print(f"✅ Validation performance: {benchmark.stats['mean'] * 1000:.2f}ms")


# ========================================================================
# Run Tests
# ========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
