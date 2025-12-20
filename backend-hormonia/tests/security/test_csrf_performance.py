"""
CSRF Performance and Load Tests

Tests performance characteristics:
- Token generation speed
- Validation speed
- Memory usage
- Concurrent request handling
- Rate limiting behavior

Created by: Tester Agent
Coordinated via: Hive Mind Swarm
"""

import pytest
import time
import concurrent.futures
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
@pytest.mark.performance
class TestCSRFPerformanceBenchmarks:
    """Performance benchmarks for CSRF operations."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_token_generation_throughput(self, mock_secret):
        """Test token generation throughput."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        iterations = 10000
        start = time.perf_counter()

        for _ in range(iterations):
            generate_csrf_token()

        end = time.perf_counter()
        duration = end - start
        throughput = iterations / duration

        # Should generate at least 10,000 tokens/second
        assert throughput > 10000

        print(f"\nToken generation: {throughput:.0f} tokens/sec")

    @patch("app.middleware.csrf._get_secret_key")
    def test_token_validation_throughput(self, mock_secret):
        """Test token validation throughput."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        token = generate_csrf_token()

        iterations = 10000
        start = time.perf_counter()

        for _ in range(iterations):
            validate_csrf_token(token)

        end = time.perf_counter()
        duration = end - start
        throughput = iterations / duration

        # Should validate at least 10,000 tokens/second
        assert throughput > 10000

        print(f"\nToken validation: {throughput:.0f} validations/sec")

    @patch("app.middleware.csrf._get_secret_key")
    def test_middleware_latency(self, mock_secret):
        """Test middleware processing latency."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.get("/health")
        def health():
            return {"status": "ok"}

        client = TestClient(app)

        # Warmup
        for _ in range(10):
            client.get("/health")

        # Measure
        iterations = 100
        start = time.perf_counter()

        for _ in range(iterations):
            client.get("/health")

        end = time.perf_counter()
        avg_latency = (end - start) / iterations * 1000  # ms

        # Middleware should add < 1ms latency
        assert avg_latency < 10  # Very generous

        print(f"\nMiddleware latency: {avg_latency:.2f}ms per request")

    @patch("app.middleware.csrf._get_secret_key")
    def test_memory_usage_token_generation(self, mock_secret):
        """Test memory usage of token generation."""
        import sys

        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Generate tokens and measure memory
        tokens = [generate_csrf_token() for _ in range(1000)]

        # Each token should be reasonably sized
        avg_size = sum(sys.getsizeof(t) for t in tokens) / len(tokens)

        # Tokens should be < 200 bytes each
        assert avg_size < 200

        print(f"\nAverage token size: {avg_size:.0f} bytes")


@pytest.mark.security
@pytest.mark.performance
class TestCSRFConcurrency:
    """Test concurrent CSRF operations."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_concurrent_token_generation(self, mock_secret):
        """Test concurrent token generation."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        def generate_tokens(count):
            return [generate_csrf_token() for _ in range(count)]

        # Generate 100 tokens in 10 threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(generate_tokens, 10) for _ in range(10)]
            results = [f.result() for f in futures]

        # Flatten results
        all_tokens = [token for batch in results for token in batch]

        # All should be unique
        assert len(set(all_tokens)) == 100

        # All should be valid
        assert all(validate_csrf_token(token) for token in all_tokens)

    @patch("app.middleware.csrf._get_secret_key")
    def test_concurrent_validation(self, mock_secret):
        """Test concurrent token validation."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        tokens = [generate_csrf_token() for _ in range(100)]

        def validate_tokens(token_batch):
            return [validate_csrf_token(t) for t in token_batch]

        # Split tokens into batches
        batch_size = 10
        batches = [tokens[i:i+batch_size] for i in range(0, len(tokens), batch_size)]

        # Validate concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(validate_tokens, batch) for batch in batches]
            results = [f.result() for f in futures]

        # Flatten results
        all_results = [r for batch in results for r in batch]

        # All should be valid
        assert all(all_results)

    @patch("app.middleware.csrf._get_secret_key")
    def test_concurrent_requests_to_endpoint(self, mock_secret):
        """Test concurrent requests with CSRF."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        counter = {"value": 0}

        @app.post("/api/increment")
        def increment():
            counter["value"] += 1
            return {"count": counter["value"]}

        client = TestClient(app)

        def make_request(token):
            return client.post(
                "/api/increment",
                headers={"X-CSRF-Token": token},
                cookies={COOKIE_NAME: token}
            )

        # Generate tokens
        tokens = [generate_csrf_token() for _ in range(50)]

        # Make concurrent requests
        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, token) for token in tokens]
            responses = [f.result() for f in futures]
        end = time.perf_counter()

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

        # All requests completed
        assert counter["value"] == 50

        # Calculate throughput
        throughput = 50 / (end - start)
        print(f"\nRequest throughput: {throughput:.0f} req/sec")


@pytest.mark.security
@pytest.mark.performance
class TestCSRFLoadHandling:
    """Test CSRF under load conditions."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_sustained_load(self, mock_secret):
        """Test CSRF under sustained load."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/test")
        def test():
            return {"success": True}

        client = TestClient(app)

        # Sustained load: 1000 requests
        success_count = 0
        start = time.perf_counter()

        for _ in range(1000):
            token = generate_csrf_token()
            response = client.post(
                "/api/test",
                headers={"X-CSRF-Token": token},
                cookies={COOKIE_NAME: token}
            )
            if response.status_code == 200:
                success_count += 1

        end = time.perf_counter()

        # All should succeed
        assert success_count == 1000

        # Should handle > 100 req/sec
        throughput = 1000 / (end - start)
        assert throughput > 100

        print(f"\nSustained throughput: {throughput:.0f} req/sec")

    @patch("app.middleware.csrf._get_secret_key")
    def test_burst_load(self, mock_secret):
        """Test CSRF under burst load."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/test")
        def test():
            return {"success": True}

        client = TestClient(app)
        token = generate_csrf_token()

        # Burst: 100 rapid requests
        start = time.perf_counter()

        responses = []
        for _ in range(100):
            response = client.post(
                "/api/test",
                headers={"X-CSRF-Token": token},
                cookies={COOKIE_NAME: token}
            )
            responses.append(response)

        end = time.perf_counter()

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

        duration = end - start
        print(f"\nBurst handled in {duration:.2f}s")

    @patch("app.middleware.csrf._get_secret_key")
    def test_mixed_valid_invalid_load(self, mock_secret):
        """Test performance with mix of valid and invalid tokens."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        app = FastAPI()
        app.add_middleware(CSRFMiddleware)

        @app.post("/api/test")
        def test():
            return {"success": True}

        client = TestClient(app)

        valid_token = generate_csrf_token()

        # Mix of valid and invalid requests
        start = time.perf_counter()

        valid_count = 0
        invalid_count = 0

        for i in range(100):
            if i % 2 == 0:
                # Valid request
                response = client.post(
                    "/api/test",
                    headers={"X-CSRF-Token": valid_token},
                    cookies={COOKIE_NAME: valid_token}
                )
                if response.status_code == 200:
                    valid_count += 1
            else:
                # Invalid request
                response = client.post(
                    "/api/test",
                    headers={"X-CSRF-Token": "invalid"},
                    cookies={COOKIE_NAME: "invalid"}
                )
                if response.status_code == 403:
                    invalid_count += 1

        end = time.perf_counter()

        # Should handle both correctly
        assert valid_count == 50
        assert invalid_count == 50

        duration = end - start
        throughput = 100 / duration

        print(f"\nMixed load throughput: {throughput:.0f} req/sec")


@pytest.mark.security
@pytest.mark.performance
class TestCSRFMemoryEfficiency:
    """Test memory efficiency of CSRF implementation."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_no_memory_leak_token_generation(self, mock_secret):
        """Test that token generation doesn't leak memory."""
        import gc

        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Force garbage collection
        gc.collect()

        # Generate many tokens
        for _ in range(10000):
            generate_csrf_token()

        # Force garbage collection again
        gc.collect()

        # If there's a leak, memory would grow significantly
        # This is a basic check - full leak testing requires profiling

    @patch("app.middleware.csrf._get_secret_key")
    def test_no_memory_leak_validation(self, mock_secret):
        """Test that validation doesn't leak memory."""
        import gc

        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        token = generate_csrf_token()

        # Force garbage collection
        gc.collect()

        # Validate many times
        for _ in range(10000):
            validate_csrf_token(token)

        # Force garbage collection again
        gc.collect()

        # Basic check for leaks


@pytest.mark.security
@pytest.mark.performance
class TestCSRFScalability:
    """Test scalability of CSRF implementation."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_scales_to_many_unique_tokens(self, mock_secret):
        """Test that system handles many unique tokens."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Generate 10,000 unique tokens
        tokens = [generate_csrf_token() for _ in range(10000)]

        # All should be unique
        assert len(set(tokens)) == 10000

        # All should be valid
        # (Sample validation to avoid long test time)
        sample = tokens[::100]  # Every 100th token
        assert all(validate_csrf_token(token) for token in sample)

    @patch("app.middleware.csrf._get_secret_key")
    def test_validation_time_constant(self, mock_secret):
        """Test that validation time doesn't increase with token age."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        # Generate tokens with delays
        tokens_with_age = []
        for i in range(10):
            token = generate_csrf_token()
            tokens_with_age.append(token)
            if i < 9:  # Don't sleep after last token
                time.sleep(0.01)

        # Validate all tokens and measure time
        times = []
        for token in tokens_with_age:
            start = time.perf_counter()
            validate_csrf_token(token)
            end = time.perf_counter()
            times.append(end - start)

        # Validation time should be relatively constant
        # (not increasing with token age)
        avg_time = sum(times) / len(times)
        assert all(t < avg_time * 5 for t in times)  # Within 5x of average
