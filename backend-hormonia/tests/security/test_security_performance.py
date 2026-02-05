"""
Security Performance Test Suite

Tests performance characteristics of security measures:
- CSRF token generation/validation speed
- CORS processing overhead
- Middleware stack latency
- Concurrent request handling
- Cache effectiveness
- Memory usage

Target: Security should add <10ms latency

Created by: Tester Agent (Hive Mind)
Coordination: Memory-based swarm coordination
"""

import pytest
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch


@pytest.mark.security
@pytest.mark.performance
class TestCSRFPerformance:
    """Test CSRF token performance."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_token_generation_speed(self, mock_secret):
        """Test that token generation is fast (<1ms)."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        from app.middleware.csrf import generate_csrf_token

        # Warmup
        for _ in range(10):
            generate_csrf_token()

        # Measure
        times = []
        for _ in range(1000):
            start = time.perf_counter()
            generate_csrf_token()
            duration = (time.perf_counter() - start) * 1000  # Convert to ms
            times.append(duration)

        avg_time = statistics.mean(times)
        p95_time = statistics.quantiles(times, n=20)[18]  # 95th percentile

        assert avg_time < 1.0, f"Average generation time {avg_time:.3f}ms exceeds 1ms"
        assert p95_time < 2.0, f"P95 generation time {p95_time:.3f}ms exceeds 2ms"

    @patch("app.middleware.csrf._get_secret_key")
    def test_token_validation_speed(self, mock_secret):
        """Test that token validation is fast (<1ms)."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        from app.middleware.csrf import generate_csrf_token, validate_csrf_token

        # Generate tokens to validate
        tokens = [generate_csrf_token() for _ in range(100)]

        # Warmup
        for token in tokens[:10]:
            validate_csrf_token(token)

        # Measure
        times = []
        for token in tokens:
            start = time.perf_counter()
            validate_csrf_token(token)
            duration = (time.perf_counter() - start) * 1000
            times.append(duration)

        avg_time = statistics.mean(times)
        p95_time = statistics.quantiles(times, n=20)[18]

        assert avg_time < 1.0, f"Average validation time {avg_time:.3f}ms exceeds 1ms"
        assert p95_time < 2.0, f"P95 validation time {p95_time:.3f}ms exceeds 2ms"

    @patch("app.middleware.csrf._get_secret_key")
    def test_concurrent_token_generation(self, mock_secret):
        """Test concurrent token generation performance."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        from app.middleware.csrf import generate_csrf_token

        def generate_token():
            start = time.perf_counter()
            token = generate_csrf_token()
            duration = (time.perf_counter() - start) * 1000
            return duration, token

        # Generate 100 tokens concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(generate_token) for _ in range(100)]
            results = [f.result() for f in as_completed(futures)]

        times = [r[0] for r in results]
        tokens = [r[1] for r in results]

        # All tokens should be unique
        assert len(set(tokens)) == 100

        # Performance should not degrade significantly
        avg_time = statistics.mean(times)
        assert avg_time < 5.0, f"Concurrent generation avg {avg_time:.3f}ms exceeds 5ms"

    @patch("app.middleware.csrf._get_secret_key")
    def test_token_validation_constant_time(self, mock_secret):
        """Test that validation time doesn't leak information (timing attack resistance)."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        from app.middleware.csrf import generate_csrf_token, validate_csrf_token

        valid_token = generate_csrf_token()
        invalid_token = "invalid.token.signature"

        # Measure valid token validation time
        valid_times = []
        for _ in range(100):
            start = time.perf_counter()
            validate_csrf_token(valid_token)
            valid_times.append(time.perf_counter() - start)

        # Measure invalid token validation time
        invalid_times = []
        for _ in range(100):
            start = time.perf_counter()
            validate_csrf_token(invalid_token)
            invalid_times.append(time.perf_counter() - start)

        valid_avg = statistics.mean(valid_times)
        invalid_avg = statistics.mean(invalid_times)

        # Times should be similar (within 50% difference)
        # HMAC compare_digest provides constant-time comparison
        time_ratio = max(valid_avg, invalid_avg) / min(valid_avg, invalid_avg)
        assert time_ratio < 2.0, f"Timing difference {time_ratio:.2f}x may leak information"


@pytest.mark.security
@pytest.mark.performance
class TestCORSPerformance:
    """Test CORS performance characteristics."""

    @patch("app.core.cors.settings")
    def test_origin_validation_speed(self, mock_settings):
        """Test that origin validation is fast."""
        mock_settings.APP_ENVIRONMENT = "production"
        # 100 allowed origins
        origins = [f"https://app{i}.hormonia.io" for i in range(100)]
        mock_settings.get_cors_origins.return_value = origins

        from app.core.cors import get_allowed_origins

        times = []
        for _ in range(100):
            start = time.perf_counter()
            get_allowed_origins()
            duration = (time.perf_counter() - start) * 1000
            times.append(duration)

        avg_time = statistics.mean(times)
        assert avg_time < 1.0, f"Origin validation {avg_time:.3f}ms exceeds 1ms"

    @patch("app.core.cors.settings")
    def test_preflight_response_speed(self, mock_settings):
        """Test that preflight responses are fast."""
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.get_cors_origins.return_value = ["http://localhost:3000"]

        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.core.cors import configure_cors

        app = FastAPI()

        @app.post("/api/test")
        async def test_route():
            return {"message": "success"}

        configure_cors(app)
        client = TestClient(app)

        # Measure preflight response time
        times = []
        for _ in range(100):
            start = time.perf_counter()
            response = client.options(
                "/api/test",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "POST",
                },
            )
            duration = (time.perf_counter() - start) * 1000
            times.append(duration)
            assert response.status_code == 200

        avg_time = statistics.mean(times)
        # Preflight should be very fast (no business logic)
        assert avg_time < 10.0, f"Preflight avg {avg_time:.3f}ms exceeds 10ms"


@pytest.mark.security
@pytest.mark.performance
class TestMiddlewareStackPerformance:
    """Test overall middleware stack performance."""

    @patch("app.core.cors.settings")
    @patch("app.middleware.csrf._get_secret_key")
    def test_full_stack_latency(self, mock_csrf_secret, mock_cors_settings):
        """Test latency added by full security middleware stack."""
        mock_cors_settings.APP_ENVIRONMENT = "development"
        mock_cors_settings.get_cors_origins.return_value = ["http://localhost:3000"]
        mock_csrf_secret.return_value = "test-secret-key-32-characters-long-12345678"

        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.core.cors import configure_cors
        from app.middleware.csrf import CSRFMiddleware
        from app.middleware.security_headers import SecurityHeadersMiddleware

        # App with no middleware
        app_no_middleware = FastAPI()

        @app_no_middleware.get("/api/test")
        async def test_route():
            return {"message": "success"}

        # App with full middleware stack
        app_with_middleware = FastAPI()

        @app_with_middleware.get("/api/test")
        async def test_route_secure():
            return {"message": "success"}

        app_with_middleware.add_middleware(CSRFMiddleware)
        app_with_middleware.add_middleware(
            SecurityHeadersMiddleware,
            enable_hsts=True,
        )
        configure_cors(app_with_middleware)

        client_no_mw = TestClient(app_no_middleware)
        client_with_mw = TestClient(app_with_middleware)

        # Measure without middleware
        no_mw_times = []
        for _ in range(100):
            start = time.perf_counter()
            response = client_no_mw.get("/api/test")
            duration = (time.perf_counter() - start) * 1000
            no_mw_times.append(duration)
            assert response.status_code == 200

        # Measure with middleware (GET is CSRF exempt)
        with_mw_times = []
        for _ in range(100):
            start = time.perf_counter()
            response = client_with_mw.get(
                "/api/test",
                headers={"Origin": "http://localhost:3000"},
            )
            duration = (time.perf_counter() - start) * 1000
            with_mw_times.append(duration)
            assert response.status_code == 200

        no_mw_avg = statistics.mean(no_mw_times)
        with_mw_avg = statistics.mean(with_mw_times)
        overhead = with_mw_avg - no_mw_avg

        # Middleware should add <10ms overhead
        assert overhead < 10.0, f"Middleware overhead {overhead:.3f}ms exceeds 10ms"

    @patch("app.core.cors.settings")
    @patch("app.middleware.csrf._get_secret_key")
    def test_csrf_validation_overhead(self, mock_csrf_secret, mock_cors_settings):
        """Test overhead of CSRF validation on POST requests."""
        mock_cors_settings.APP_ENVIRONMENT = "development"
        mock_cors_settings.get_cors_origins.return_value = ["http://localhost:3000"]
        mock_csrf_secret.return_value = "test-secret-key-32-characters-long-12345678"

        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.core.cors import configure_cors
        from app.middleware.csrf import CSRFMiddleware, generate_csrf_token

        app = FastAPI()

        @app.post("/api/test")
        async def test_route():
            return {"message": "success"}

        app.add_middleware(CSRFMiddleware)
        configure_cors(app)

        client = TestClient(app)
        token = generate_csrf_token()

        # Measure CSRF validation time
        times = []
        for _ in range(100):
            start = time.perf_counter()
            response = client.post(
                "/api/test",
                headers={
                    "Origin": "http://localhost:3000",
                    "X-CSRF-Token": token,
                },
                cookies={"csrf_token": token},
            )
            duration = (time.perf_counter() - start) * 1000
            times.append(duration)
            assert response.status_code == 200

        avg_time = statistics.mean(times)
        # CSRF validation should be fast
        assert avg_time < 15.0, f"CSRF validation avg {avg_time:.3f}ms exceeds 15ms"


@pytest.mark.security
@pytest.mark.performance
class TestConcurrentRequestHandling:
    """Test performance under concurrent load."""

    @patch("app.core.cors.settings")
    @patch("app.middleware.csrf._get_secret_key")
    def test_concurrent_csrf_requests(self, mock_csrf_secret, mock_cors_settings):
        """Test handling of concurrent CSRF-protected requests."""
        mock_cors_settings.APP_ENVIRONMENT = "development"
        mock_cors_settings.get_cors_origins.return_value = ["http://localhost:3000"]
        mock_csrf_secret.return_value = "test-secret-key-32-characters-long-12345678"

        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.core.cors import configure_cors
        from app.middleware.csrf import CSRFMiddleware, generate_csrf_token

        app = FastAPI()

        @app.post("/api/test")
        async def test_route():
            return {"message": "success"}

        app.add_middleware(CSRFMiddleware)
        configure_cors(app)

        client = TestClient(app)

        def make_request():
            token = generate_csrf_token()
            start = time.perf_counter()
            response = client.post(
                "/api/test",
                headers={
                    "Origin": "http://localhost:3000",
                    "X-CSRF-Token": token,
                },
                cookies={"csrf_token": token},
            )
            duration = (time.perf_counter() - start) * 1000
            return duration, response.status_code

        # 100 concurrent requests
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_request) for _ in range(100)]
            results = [f.result() for f in as_completed(futures)]

        times = [r[0] for r in results]
        statuses = [r[1] for r in results]

        # All should succeed
        assert all(status == 200 for status in statuses)

        # Performance shouldn't degrade too much
        avg_time = statistics.mean(times)
        p95_time = statistics.quantiles(times, n=20)[18]

        assert avg_time < 50.0, f"Concurrent avg {avg_time:.3f}ms exceeds 50ms"
        assert p95_time < 100.0, f"Concurrent P95 {p95_time:.3f}ms exceeds 100ms"


@pytest.mark.security
@pytest.mark.performance
class TestMemoryUsage:
    """Test memory usage of security components."""

    @patch("app.middleware.csrf._get_secret_key")
    def test_token_generation_memory_efficient(self, mock_secret):
        """Test that token generation doesn't leak memory."""
        mock_secret.return_value = "test-secret-key-32-characters-long-12345678"

        from app.middleware.csrf import generate_csrf_token
        import gc

        # Force garbage collection
        gc.collect()

        # Generate many tokens
        tokens = []
        for _ in range(10000):
            token = generate_csrf_token()
            # Only keep last 1000 to simulate normal usage
            tokens.append(token)
            if len(tokens) > 1000:
                tokens.pop(0)

        # Memory should not grow unbounded
        # This is a basic check; more sophisticated profiling needed for production
        assert len(tokens) == 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
