"""
CSRF Race Condition Tests

Tests that CSRF token fetching and validation handles concurrent requests
correctly without race conditions or memory leaks.

Security Requirements:
1. Concurrent token generation must produce unique tokens
2. Concurrent validation must not interfere with each other
3. No memory leaks during concurrent operations
4. Thread-safe token generation and validation

Coverage Goals: 100% for concurrency scenarios
"""

import pytest
import time
import concurrent.futures
import threading
from unittest.mock import Mock, patch
from fastapi import Request

from app.middleware.csrf import (
    generate_csrf_token,
    validate_csrf_token,
    _validate_token_signature,
    set_csrf_cookie,
    CsrfProtectError,
)


class TestConcurrentTokenGeneration:
    """Test concurrent CSRF token generation."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_concurrent_token_generation_produces_unique_tokens(self, mock_get_settings):
        """Verify that concurrent token generation produces unique tokens."""
        secret_key = "test-secret-key-32-characters-long"
        mock_settings = Mock()
        mock_settings.secret_key = secret_key
        mock_get_settings.return_value = mock_settings

        # Generate 1000 tokens concurrently from 10 threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(generate_csrf_token, secret_key)
                for _ in range(1000)
            ]
            tokens = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All tokens should be unique (no collisions)
        assert len(tokens) == 1000
        assert len(set(tokens)) == 1000, "Token generation has collisions under concurrency"

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_high_concurrency_token_generation(self, mock_get_settings):
        """Test token generation under high concurrency (100 threads)."""
        secret_key = "test-secret-key-32-characters-long"
        mock_settings = Mock()
        mock_settings.secret_key = secret_key
        mock_get_settings.return_value = mock_settings

        # Extreme concurrency test
        num_tokens = 500
        num_threads = 50

        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(generate_csrf_token, secret_key)
                for _ in range(num_tokens)
            ]
            tokens = [f.result() for f in concurrent.futures.as_completed(futures)]

        elapsed = time.time() - start_time

        # Verify all tokens are unique
        assert len(tokens) == num_tokens
        assert len(set(tokens)) == num_tokens

        # Should complete in reasonable time (< 5 seconds for 500 tokens)
        assert elapsed < 5.0, f"Token generation too slow under concurrency: {elapsed:.2f}s"

        # All tokens should be valid format
        for token in tokens:
            parts = token.split(".")
            assert len(parts) == 3
            assert all(c in "0123456789abcdef." for c in token)


class TestConcurrentTokenValidation:
    """Test concurrent CSRF token validation."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_concurrent_validation_same_token(self, mock_get_settings):
        """Test that same token can be validated concurrently by multiple requests."""
        secret_key = "test-secret-key-32-characters-long"
        mock_settings = Mock()
        mock_settings.secret_key = secret_key
        mock_get_settings.return_value = mock_settings

        # Generate single token
        token = generate_csrf_token(secret_key)

        # Validate concurrently 100 times
        def validate_token():
            return _validate_token_signature(token, secret_key, max_age=3600)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(validate_token) for _ in range(100)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All validations should succeed
        assert all(results), "Token validation failed under concurrency"
        assert len(results) == 100

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_concurrent_validation_different_tokens(self, mock_get_settings):
        """Test validating different tokens concurrently."""
        secret_key = "test-secret-key-32-characters-long"
        mock_settings = Mock()
        mock_settings.secret_key = secret_key
        mock_get_settings.return_value = mock_settings

        # Generate 100 different tokens
        tokens = [generate_csrf_token(secret_key) for _ in range(100)]

        # Validate all tokens concurrently
        def validate_token(token):
            return _validate_token_signature(token, secret_key, max_age=3600)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(validate_token, token) for token in tokens]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should validate successfully
        assert all(results)
        assert len(results) == 100

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_concurrent_validation_mixed_valid_invalid(self, mock_get_settings):
        """Test concurrent validation of mix of valid and invalid tokens."""
        secret_key = "test-secret-key-32-characters-long"
        mock_settings = Mock()
        mock_settings.secret_key = secret_key
        mock_get_settings.return_value = mock_settings

        # Generate 50 valid tokens and 50 invalid tokens
        valid_tokens = [generate_csrf_token(secret_key) for _ in range(50)]
        invalid_tokens = [token[:-10] + "0000000000" for token in valid_tokens]

        all_tokens = valid_tokens + invalid_tokens
        expected_results = [True] * 50 + [False] * 50

        # Validate concurrently
        def validate_token(token):
            return _validate_token_signature(token, secret_key, max_age=3600)

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            # Shuffle to mix valid/invalid
            import random
            combined = list(zip(all_tokens, expected_results))
            random.shuffle(combined)
            shuffled_tokens, shuffled_expected = zip(*combined)

            futures = [executor.submit(validate_token, token) for token in shuffled_tokens]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Count valid and invalid results
        valid_count = sum(results)
        invalid_count = len(results) - valid_count

        assert valid_count == 50, f"Expected 50 valid, got {valid_count}"
        assert invalid_count == 50, f"Expected 50 invalid, got {invalid_count}"


class TestRaceConditionPrevention:
    """Test prevention of race conditions in CSRF operations."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_no_race_condition_in_cookie_setting(self, mock_get_settings):
        """Test that setting CSRF cookies concurrently doesn't cause races."""
        from fastapi.responses import JSONResponse

        secret_key = "test-secret-key-32-characters-long"
        mock_settings = Mock()
        mock_settings.secret_key = secret_key
        mock_settings.cookie_name = "fastapi-csrf-token"
        mock_settings.cookie_secure = False
        mock_settings.cookie_httponly = True
        mock_settings.cookie_samesite = "strict"
        mock_settings.cookie_path = "/"
        mock_settings.cookie_domain = None
        mock_settings.token_expires_in = 3600
        mock_get_settings.return_value = mock_settings

        # Simulate concurrent cookie setting
        def set_cookie():
            request = Mock(spec=Request)
            response = JSONResponse(content={"success": True})
            token = set_csrf_cookie(request, response)
            return token

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(set_cookie) for _ in range(100)]
            tokens = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All tokens should be unique
        assert len(tokens) == 100
        assert len(set(tokens)) == 100

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_thread_safety_of_validation(self, mock_get_settings):
        """Test thread safety of CSRF validation."""
        secret_key = "test-secret-key-32-characters-long"
        mock_settings = Mock()
        mock_settings.secret_key = secret_key
        mock_settings.token_expires_in = 3600
        mock_settings.cookie_name = "fastapi-csrf-token"
        mock_settings.token_header_name = "X-CSRF-Token"
        mock_get_settings.return_value = mock_settings

        # Generate tokens
        tokens = [generate_csrf_token(secret_key) for _ in range(50)]

        # Validate concurrently with full request validation
        errors = []
        successes = []

        def validate_full_request(token):
            try:
                request = Mock(spec=Request)
                request.headers = {"X-CSRF-Token": token}
                request.cookies = {"fastapi-csrf-token": token}
                request.client = Mock(host="127.0.0.1")
                request.url = Mock(path="/api/test")

                validate_csrf_token(request)
                return True
            except CsrfProtectError as e:
                errors.append(str(e))
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(validate_full_request, token) for token in tokens]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed (no races causing false failures)
        assert all(results), f"Race condition detected. Errors: {errors}"


class TestMemoryLeakPrevention:
    """Test that concurrent operations don't cause memory leaks."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_no_memory_leak_in_token_generation(self, mock_get_settings):
        """Test that generating many tokens doesn't leak memory."""
        import gc
        import sys

        secret_key = "test-secret-key-32-characters-long"
        mock_settings = Mock()
        mock_settings.secret_key = secret_key
        mock_get_settings.return_value = mock_settings

        # Force garbage collection and get baseline
        gc.collect()
        baseline_objects = len(gc.get_objects())

        # Generate 1000 tokens
        for _ in range(1000):
            generate_csrf_token(secret_key)

        # Force garbage collection
        gc.collect()

        # Check object count hasn't grown significantly
        final_objects = len(gc.get_objects())
        object_growth = final_objects - baseline_objects

        # Allow some growth but not proportional to number of tokens
        # (should be < 100 new objects for 1000 tokens)
        assert object_growth < 100, f"Memory leak detected: {object_growth} new objects"

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_no_memory_leak_in_validation(self, mock_get_settings):
        """Test that validating many tokens doesn't leak memory."""
        import gc

        secret_key = "test-secret-key-32-characters-long"
        mock_settings = Mock()
        mock_settings.secret_key = secret_key
        mock_get_settings.return_value = mock_settings

        # Generate tokens
        tokens = [generate_csrf_token(secret_key) for _ in range(100)]

        # Force GC and get baseline
        gc.collect()
        baseline_objects = len(gc.get_objects())

        # Validate tokens many times
        for _ in range(10):
            for token in tokens:
                _validate_token_signature(token, secret_key, max_age=3600)

        # Force GC
        gc.collect()

        final_objects = len(gc.get_objects())
        object_growth = final_objects - baseline_objects

        # Should not accumulate objects
        assert object_growth < 50, f"Memory leak in validation: {object_growth} new objects"


class TestConcurrentDoubleSubmitCookie:
    """Test Double Submit Cookie pattern under concurrency."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_concurrent_double_submit_validation(self, mock_get_settings):
        """Test concurrent validation with Double Submit Cookie pattern."""
        secret_key = "test-secret-key-32-characters-long"
        mock_settings = Mock()
        mock_settings.secret_key = secret_key
        mock_settings.token_expires_in = 3600
        mock_settings.cookie_name = "fastapi-csrf-token"
        mock_settings.token_header_name = "X-CSRF-Token"
        mock_get_settings.return_value = mock_settings

        # Generate 50 tokens
        tokens = [generate_csrf_token(secret_key) for _ in range(50)]

        def validate_with_double_submit(token):
            request = Mock(spec=Request)
            request.headers = {"X-CSRF-Token": token}
            request.cookies = {"fastapi-csrf-token": token}
            request.client = Mock(host="127.0.0.1")
            request.url = Mock(path="/api/test")

            try:
                validate_csrf_token(request)
                return True
            except CsrfProtectError:
                return False

        # Validate concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(validate_with_double_submit, token) for token in tokens]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed
        assert all(results)

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_concurrent_mismatch_detection(self, mock_get_settings):
        """Test that mismatches are detected correctly under concurrency."""
        secret_key = "test-secret-key-32-characters-long"
        mock_settings = Mock()
        mock_settings.secret_key = secret_key
        mock_settings.token_expires_in = 3600
        mock_settings.cookie_name = "fastapi-csrf-token"
        mock_settings.token_header_name = "X-CSRF-Token"
        mock_get_settings.return_value = mock_settings

        # Generate pairs of different tokens
        token_pairs = [
            (generate_csrf_token(secret_key), generate_csrf_token(secret_key))
            for _ in range(50)
        ]

        def validate_mismatched(header_token, cookie_token):
            request = Mock(spec=Request)
            request.headers = {"X-CSRF-Token": header_token}
            request.cookies = {"fastapi-csrf-token": cookie_token}
            request.client = Mock(host="127.0.0.1")
            request.url = Mock(path="/api/test")

            try:
                validate_csrf_token(request)
                return False  # Should have failed
            except CsrfProtectError:
                return True  # Correctly detected mismatch

        # Validate concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(validate_mismatched, header, cookie)
                for header, cookie in token_pairs
            ]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should detect mismatch
        assert all(results), "Failed to detect token mismatch under concurrency"


class TestDeadlockPrevention:
    """Test that concurrent operations don't cause deadlocks."""

    @patch("app.middleware.csrf.get_csrf_settings")
    def test_no_deadlock_in_mixed_operations(self, mock_get_settings):
        """Test mixed generation and validation doesn't deadlock."""
        secret_key = "test-secret-key-32-characters-long"
        mock_settings = Mock()
        mock_settings.secret_key = secret_key
        mock_settings.token_expires_in = 3600
        mock_get_settings.return_value = mock_settings

        results = []
        timeout_occurred = False

        def mixed_operation():
            # Generate token
            token = generate_csrf_token(secret_key)

            # Validate it
            is_valid = _validate_token_signature(token, secret_key, max_age=3600)

            return is_valid

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(mixed_operation) for _ in range(100)]

                # Wait with timeout to detect deadlocks
                for future in concurrent.futures.as_completed(futures, timeout=10):
                    results.append(future.result())
        except concurrent.futures.TimeoutError:
            timeout_occurred = True

        assert not timeout_occurred, "Deadlock detected in concurrent operations"
        assert len(results) == 100
        assert all(results)
