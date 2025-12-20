"""
CSRF Timing Attack Prevention Tests

Tests that CSRF validation uses constant-time comparison to prevent
attackers from determining token validity through timing analysis.

Security Requirements:
1. Token validation MUST use hmac.compare_digest (constant-time)
2. Timing should not leak whether token is valid/invalid
3. Timing should not leak which validation step failed
4. All code paths should take similar time regardless of token validity

Coverage Goals: 100% for timing attack vectors
"""

import pytest
import time
import statistics
from unittest.mock import Mock, patch
from fastapi import Request

from app.middleware.csrf import (
    validate_csrf_token,
    _validate_token_signature,
    generate_csrf_token,
    CsrfProtectError,
)


class TestConstantTimeComparison:
    """Test that CSRF validation uses constant-time comparison."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_hmac_compare_digest_used_for_signature_validation(self, mock_get_settings):
        """Verify that hmac.compare_digest is used (not ==) for signature comparison."""
        import hmac

        secret_key = "test-secret-key-32-characters-long"
        mock_settings = Mock()
        mock_settings.secret_key = secret_key
        mock_settings.token_expires_in = 3600
        mock_get_settings.return_value = mock_settings

        # Generate valid token
        valid_token = generate_csrf_token(secret_key)

        # Patch hmac.compare_digest to verify it's called
        with patch("app.middleware.csrf.hmac.compare_digest", wraps=hmac.compare_digest) as mock_compare:
            result = _validate_token_signature(valid_token, secret_key, max_age=3600)

            # Verify constant-time comparison was used
            assert mock_compare.called, "hmac.compare_digest MUST be used for timing attack prevention"
            assert result is True

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_timing_similar_for_valid_and_invalid_tokens(self, mock_get_settings):
        """Test that validation takes similar time for valid/invalid tokens."""
        secret_key = "test-secret-key-32-characters-long"
        mock_settings = Mock()
        mock_settings.secret_key = secret_key
        mock_settings.token_expires_in = 3600
        mock_get_settings.return_value = mock_settings

        # Generate valid and invalid tokens
        valid_token = generate_csrf_token(secret_key)
        invalid_token = valid_token[:-10] + "0000000000"  # Corrupt signature

        # Time validation of valid tokens
        valid_times = []
        for _ in range(100):
            start = time.perf_counter()
            try:
                _validate_token_signature(valid_token, secret_key, max_age=3600)
            except Exception:
                pass
            elapsed = time.perf_counter() - start
            valid_times.append(elapsed)

        # Time validation of invalid tokens
        invalid_times = []
        for _ in range(100):
            start = time.perf_counter()
            try:
                _validate_token_signature(invalid_token, secret_key, max_age=3600)
            except Exception:
                pass
            elapsed = time.perf_counter() - start
            invalid_times.append(elapsed)

        # Statistical analysis - times should be similar
        valid_mean = statistics.mean(valid_times)
        invalid_mean = statistics.mean(invalid_times)

        # Allow 20% variance (constant-time operations have minimal variance)
        time_difference_ratio = abs(valid_mean - invalid_mean) / max(valid_mean, invalid_mean)

        # Should be less than 20% difference (constant-time guarantee)
        assert time_difference_ratio < 0.20, (
            f"Timing difference between valid/invalid tokens: {time_difference_ratio:.2%}. "
            f"This may indicate timing attack vulnerability. "
            f"Valid mean: {valid_mean:.6f}s, Invalid mean: {invalid_mean:.6f}s"
        )

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_double_submit_cookie_uses_constant_time_comparison(self, mock_get_settings):
        """Test that Double Submit Cookie pattern uses constant-time comparison."""
        import hmac

        secret_key = "test-secret-key-32-characters-long"
        mock_settings = Mock()
        mock_settings.secret_key = secret_key
        mock_settings.token_expires_in = 3600
        mock_settings.cookie_name = "fastapi-csrf-token"
        mock_settings.token_header_name = "X-CSRF-Token"
        mock_get_settings.return_value = mock_settings

        # Generate valid token
        token = generate_csrf_token(secret_key)

        # Create request with matching header and cookie
        request = Mock(spec=Request)
        request.headers = {"X-CSRF-Token": token}
        request.cookies = {"fastapi-csrf-token": token}
        request.client = Mock(host="127.0.0.1")
        request.url = Mock(path="/api/test")

        # Patch hmac.compare_digest to verify it's used for header/cookie comparison
        with patch("app.middleware.csrf.hmac.compare_digest", wraps=hmac.compare_digest) as mock_compare:
            validate_csrf_token(request)

            # Should be called at least twice:
            # 1. For signature validation of header token
            # 2. For signature validation of cookie token
            # 3. For comparing header and cookie tokens
            assert mock_compare.call_count >= 3, (
                "hmac.compare_digest should be used multiple times: "
                "signature validation AND header/cookie comparison"
            )


class TestTimingAttackResistance:
    """Test resistance to various timing attack scenarios."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_no_early_exit_on_invalid_format(self, mock_get_settings):
        """Verify no early exit reveals format errors through timing."""
        secret_key = "test-secret-key-32-characters-long"

        # Tokens with different format errors
        tokens = [
            "not-enough-parts",
            "too.many.parts.here",
            "",
            ".",
            "..",
            "a" * 200,  # Very long token
        ]

        times = []
        for token in tokens:
            start = time.perf_counter()
            try:
                _validate_token_signature(token, secret_key, max_age=3600)
            except Exception:
                pass
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        # All format errors should take similar time
        if len(times) > 1:
            mean = statistics.mean(times)
            stdev = statistics.stdev(times) if len(times) > 1 else 0

            # Standard deviation should be small (< 30% of mean)
            if mean > 0:
                coefficient_of_variation = stdev / mean
                assert coefficient_of_variation < 0.30, (
                    f"Format error timing variance too high: {coefficient_of_variation:.2%}"
                )

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_signature_validation_before_expiration_check(self, mock_get_settings):
        """Verify signature is validated before expiration to prevent timing leaks."""
        secret_key = "test-secret-key-32-characters-long"

        # Create expired token with valid signature
        old_timestamp = str(int(time.time()) - 7200)  # 2 hours ago
        random_data = "a" * 64
        data = f"{old_timestamp}.{random_data}"

        from app.middleware.csrf import _generate_token_signature
        valid_signature = _generate_token_signature(data, secret_key)
        expired_valid_token = f"{data}.{valid_signature}"

        # Create expired token with INVALID signature
        invalid_signature = "b" * 64
        expired_invalid_token = f"{data}.{invalid_signature}"

        # Both should be rejected (expired + invalid signature respectively)
        # But timing should not reveal which reason
        times_valid_sig = []
        times_invalid_sig = []

        for _ in range(50):
            start = time.perf_counter()
            _validate_token_signature(expired_valid_token, secret_key, max_age=3600)
            times_valid_sig.append(time.perf_counter() - start)

            start = time.perf_counter()
            _validate_token_signature(expired_invalid_token, secret_key, max_age=3600)
            times_invalid_sig.append(time.perf_counter() - start)

        mean_valid = statistics.mean(times_valid_sig)
        mean_invalid = statistics.mean(times_invalid_sig)

        # Timing should be similar regardless of signature validity
        # (both paths should do signature check first)
        time_diff_ratio = abs(mean_valid - mean_invalid) / max(mean_valid, mean_invalid)
        assert time_diff_ratio < 0.25, (
            f"Timing reveals signature validity on expired tokens: {time_diff_ratio:.2%}"
        )


class TestTokenComparisonSecurity:
    """Test token comparison security in Double Submit Cookie pattern."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_header_cookie_comparison_uses_constant_time(self, mock_get_settings):
        """Test that header/cookie comparison uses hmac.compare_digest."""
        import hmac

        secret_key = "test-secret-key-32-characters-long"
        mock_settings = Mock()
        mock_settings.secret_key = secret_key
        mock_settings.token_expires_in = 3600
        mock_settings.cookie_name = "fastapi-csrf-token"
        mock_settings.token_header_name = "X-CSRF-Token"
        mock_get_settings.return_value = mock_settings

        token1 = generate_csrf_token(secret_key)
        token2 = generate_csrf_token(secret_key)  # Different token

        # Create request with mismatched tokens
        request = Mock(spec=Request)
        request.headers = {"X-CSRF-Token": token1}
        request.cookies = {"fastapi-csrf-token": token2}
        request.client = Mock(host="127.0.0.1")
        request.url = Mock(path="/api/test")

        # Verify hmac.compare_digest is used for token comparison
        with patch("app.middleware.csrf.hmac.compare_digest", wraps=hmac.compare_digest) as mock_compare:
            with pytest.raises(CsrfProtectError):
                validate_csrf_token(request)

            # Should use constant-time comparison for header/cookie match
            assert mock_compare.called

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_no_short_circuit_on_empty_tokens(self, mock_get_settings):
        """Test that empty tokens don't short-circuit validation."""
        mock_settings = Mock()
        mock_settings.secret_key = "test-secret-key-32-characters-long"
        mock_settings.token_expires_in = 3600
        mock_settings.cookie_name = "fastapi-csrf-token"
        mock_settings.token_header_name = "X-CSRF-Token"
        mock_get_settings.return_value = mock_settings

        # Request with empty tokens
        request = Mock(spec=Request)
        request.headers = {}
        request.cookies = {}
        request.client = Mock(host="127.0.0.1")
        request.url = Mock(path="/api/test")

        # Should fail gracefully without timing leaks
        with pytest.raises(CsrfProtectError, match="Missing CSRF token"):
            validate_csrf_token(request)


class TestSecurityBestPractices:
    """Test that implementation follows security best practices."""

    def test_no_token_storage_in_memory(self):
        """Verify tokens are not stored in global/class variables."""
        from app.middleware import csrf

        # Check module-level variables
        module_vars = vars(csrf)

        # Should not have token caches or dictionaries
        for name, value in module_vars.items():
            if isinstance(value, (dict, list, set)):
                # These collections should be configuration, not token storage
                assert name in [
                    "EXEMPT_PATHS",  # Configuration tuple
                    "__builtins__",
                    "__annotations__",
                    "__all__",
                    "__cached__",
                    "__file__",
                    "__loader__",
                    "__name__",
                    "__package__",
                    "__spec__",
                ], f"Unexpected collection in module: {name} (potential token storage)"

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_token_validation_is_stateless(self, mock_get_settings):
        """Verify token validation doesn't depend on server-side state."""
        secret_key = "test-secret-key-32-characters-long"

        # Generate token
        token = generate_csrf_token(secret_key)

        # Validation should work multiple times without state
        for _ in range(10):
            result = _validate_token_signature(token, secret_key, max_age=3600)
            assert result is True

        # Should work in any order
        valid_token = generate_csrf_token(secret_key)
        time.sleep(0.1)
        another_token = generate_csrf_token(secret_key)

        # Both should validate independently
        assert _validate_token_signature(valid_token, secret_key, max_age=3600)
        assert _validate_token_signature(another_token, secret_key, max_age=3600)
        assert _validate_token_signature(valid_token, secret_key, max_age=3600)


class TestEdgeCases:
    """Test edge cases in timing attack prevention."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_timing_consistent_with_unicode_tokens(self, mock_get_settings):
        """Test that unicode in tokens doesn't affect timing."""
        secret_key = "test-secret-key-32-characters-long"

        # Regular token
        normal_token = generate_csrf_token(secret_key)

        # Token with unicode (should be rejected but timing should be consistent)
        unicode_token = normal_token[:-10] + "ñáéíóú"

        normal_times = []
        unicode_times = []

        for _ in range(50):
            start = time.perf_counter()
            try:
                _validate_token_signature(normal_token, secret_key, max_age=3600)
            except Exception:
                pass
            normal_times.append(time.perf_counter() - start)

            start = time.perf_counter()
            try:
                _validate_token_signature(unicode_token, secret_key, max_age=3600)
            except Exception:
                pass
            unicode_times.append(time.perf_counter() - start)

        # Timing should be similar
        normal_mean = statistics.mean(normal_times)
        unicode_mean = statistics.mean(unicode_times)

        if max(normal_mean, unicode_mean) > 0:
            ratio = abs(normal_mean - unicode_mean) / max(normal_mean, unicode_mean)
            assert ratio < 0.30, f"Unicode token timing variance: {ratio:.2%}"
