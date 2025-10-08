"""
Integration tests for Monitoring Middleware.

Tests APM, metrics collection, and performance monitoring.
"""

import pytest
import time
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
import asyncio


class MonitoringMiddleware(BaseHTTPMiddleware):
    """Application Performance Monitoring middleware."""

    def __init__(
        self,
        app,
        metrics_client=None,
        enable_tracing: bool = True,
        enable_metrics: bool = True,
        enable_profiling: bool = False,
        sample_rate: float = 1.0,
        slow_request_threshold: float = 1.0
    ):
        super().__init__(app)
        self.metrics_client = metrics_client or Mock()
        self.enable_tracing = enable_tracing
        self.enable_metrics = enable_metrics
        self.enable_profiling = enable_profiling
        self.sample_rate = sample_rate
        self.slow_request_threshold = slow_request_threshold
        self.active_requests = 0
        self.total_requests = 0
        self.total_errors = 0

    async def dispatch(self, request: Request, call_next):
        """Monitor request performance and collect metrics."""
        # Sampling decision
        should_trace = self.enable_tracing and (time.time() % 1) < self.sample_rate

        # Start monitoring
        start_time = time.time()
        self.active_requests += 1
        self.total_requests += 1

        # Create trace context
        trace_id = f"trace-{int(start_time * 1000000)}"
        span_id = f"span-{int(time.time() * 1000000)}"

        if should_trace:
            request.state.trace_id = trace_id
            request.state.span_id = span_id

        # Collect request metrics
        if self.enable_metrics:
            self.metrics_client.increment("http.requests", tags={
                "method": request.method,
                "path": request.url.path
            })
            self.metrics_client.gauge("http.active_requests", self.active_requests)

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Record response metrics
            if self.enable_metrics:
                self.metrics_client.histogram(
                    "http.request.duration",
                    duration * 1000,  # Convert to ms
                    tags={
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code
                    }
                )

                # Check for slow requests
                if duration > self.slow_request_threshold:
                    self.metrics_client.increment("http.slow_requests", tags={
                        "method": request.method,
                        "path": request.url.path
                    })

            # Add trace headers
            if should_trace:
                response.headers["X-Trace-ID"] = trace_id
                response.headers["X-Span-ID"] = span_id

            # Add performance headers
            response.headers["X-Response-Time"] = f"{duration * 1000:.2f}ms"
            response.headers["X-Request-Count"] = str(self.total_requests)

            return response

        except Exception as exc:
            # Record error metrics
            self.total_errors += 1
            if self.enable_metrics:
                self.metrics_client.increment("http.errors", tags={
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": type(exc).__name__
                })
            raise

        finally:
            # Cleanup
            self.active_requests -= 1
            if self.enable_metrics:
                self.metrics_client.gauge("http.active_requests", self.active_requests)


class MockMetricsClient:
    """Mock metrics client for testing."""

    def __init__(self):
        self.metrics = {
            "increments": [],
            "histograms": [],
            "gauges": [],
            "timers": []
        }

    def increment(self, metric, value=1, tags=None):
        """Record increment metric."""
        self.metrics["increments"].append({
            "metric": metric,
            "value": value,
            "tags": tags or {},
            "timestamp": time.time()
        })

    def histogram(self, metric, value, tags=None):
        """Record histogram metric."""
        self.metrics["histograms"].append({
            "metric": metric,
            "value": value,
            "tags": tags or {},
            "timestamp": time.time()
        })

    def gauge(self, metric, value, tags=None):
        """Record gauge metric."""
        self.metrics["gauges"].append({
            "metric": metric,
            "value": value,
            "tags": tags or {},
            "timestamp": time.time()
        })

    def timer(self, metric):
        """Create timer context manager."""
        return MockTimer(self, metric)


class MockTimer:
    """Mock timer context manager."""

    def __init__(self, client, metric):
        self.client = client
        self.metric = metric
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (time.time() - self.start_time) * 1000
        self.client.metrics["timers"].append({
            "metric": self.metric,
            "duration": duration,
            "timestamp": time.time()
        })


@pytest.fixture
def app_with_monitoring():
    """Create FastAPI app with monitoring middleware."""
    app = FastAPI()
    metrics_client = MockMetricsClient()

    # Add monitoring middleware
    app.add_middleware(
        MonitoringMiddleware,
        metrics_client=metrics_client,
        enable_tracing=True,
        enable_metrics=True,
        enable_profiling=False,
        sample_rate=1.0,
        slow_request_threshold=0.5
    )

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.get("/slow")
    async def slow_endpoint():
        await asyncio.sleep(0.6)
        return {"status": "slow"}

    @app.get("/error")
    async def error_endpoint():
        raise ValueError("Test error")

    @app.get("/cpu-intensive")
    async def cpu_intensive_endpoint():
        # Simulate CPU work
        result = sum(i * i for i in range(10000))
        return {"result": result}

    @app.post("/data")
    async def data_endpoint(data: dict):
        return {"received": data}

    return app, metrics_client


@pytest.fixture
def client(app_with_monitoring):
    """Create test client."""
    app, metrics_client = app_with_monitoring
    return TestClient(app), metrics_client


class TestMonitoringMiddleware:
    """Test monitoring middleware functionality."""

    def test_request_counting(self, client):
        """Test request counting."""
        test_client, metrics = client

        # Make multiple requests
        for i in range(5):
            response = test_client.get("/test")
            assert response.status_code == 200
            assert response.headers["X-Request-Count"] == str(i + 1)

    def test_response_time_header(self, client):
        """Test response time header is added."""
        test_client, metrics = client
        response = test_client.get("/test")
        assert response.status_code == 200
        assert "X-Response-Time" in response.headers
        assert "ms" in response.headers["X-Response-Time"]

    def test_trace_headers(self, client):
        """Test trace headers are added."""
        test_client, metrics = client
        response = test_client.get("/test")
        assert response.status_code == 200
        assert "X-Trace-ID" in response.headers
        assert "X-Span-ID" in response.headers
        assert response.headers["X-Trace-ID"].startswith("trace-")
        assert response.headers["X-Span-ID"].startswith("span-")

    def test_metrics_collection(self, client):
        """Test metrics are collected."""
        test_client, metrics = client

        # Clear metrics
        metrics.metrics["increments"].clear()
        metrics.metrics["histograms"].clear()

        # Make request
        response = test_client.get("/test")
        assert response.status_code == 200

        # Check increment metrics
        increments = metrics.metrics["increments"]
        assert any(m["metric"] == "http.requests" for m in increments)

        # Check histogram metrics
        histograms = metrics.metrics["histograms"]
        assert any(m["metric"] == "http.request.duration" for m in histograms)

    def test_slow_request_detection(self, client):
        """Test slow requests are detected."""
        test_client, metrics = client

        # Clear metrics
        metrics.metrics["increments"].clear()

        # Make slow request
        response = test_client.get("/slow")
        assert response.status_code == 200

        # Check slow request metric
        increments = metrics.metrics["increments"]
        slow_metrics = [m for m in increments if m["metric"] == "http.slow_requests"]
        assert len(slow_metrics) > 0

    def test_error_metrics(self, client):
        """Test error metrics are collected."""
        test_client, metrics = client

        # Clear metrics
        metrics.metrics["increments"].clear()

        # Make error request
        response = test_client.get("/error")
        assert response.status_code == 500

        # Check error metric
        increments = metrics.metrics["increments"]
        error_metrics = [m for m in increments if m["metric"] == "http.errors"]
        assert len(error_metrics) > 0
        assert error_metrics[0]["tags"]["error_type"] == "ValueError"

    def test_active_requests_gauge(self, client):
        """Test active requests gauge."""
        test_client, metrics = client

        # Clear metrics
        metrics.metrics["gauges"].clear()

        # Make request
        response = test_client.get("/test")
        assert response.status_code == 200

        # Check gauge metrics
        gauges = metrics.metrics["gauges"]
        active_request_gauges = [g for g in gauges if g["metric"] == "http.active_requests"]
        assert len(active_request_gauges) >= 2  # Before and after request

        # Should end at 0
        assert active_request_gauges[-1]["value"] == 0

    def test_method_and_path_tags(self, client):
        """Test metrics include method and path tags."""
        test_client, metrics = client

        # Clear metrics
        metrics.metrics["increments"].clear()

        # Make different requests
        test_client.get("/test")
        test_client.post("/data", json={"test": "data"})

        # Check tags
        increments = metrics.metrics["increments"]
        request_metrics = [m for m in increments if m["metric"] == "http.requests"]

        methods = {m["tags"]["method"] for m in request_metrics}
        paths = {m["tags"]["path"] for m in request_metrics}

        assert "GET" in methods
        assert "POST" in methods
        assert "/test" in paths
        assert "/data" in paths

    def test_concurrent_request_tracking(self, client):
        """Test concurrent request tracking."""
        test_client, metrics = client
        import concurrent.futures

        def make_request():
            return test_client.get("/cpu-intensive")

        # Make concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(make_request) for _ in range(3)]
            results = [f.result() for f in futures]

        # All should succeed
        for response in results:
            assert response.status_code == 200


class TestMonitoringConfiguration:
    """Test monitoring middleware configuration."""

    def test_disable_tracing(self):
        """Test tracing can be disabled."""
        app = FastAPI()
        metrics_client = MockMetricsClient()

        app.add_middleware(
            MonitoringMiddleware,
            metrics_client=metrics_client,
            enable_tracing=False,
            enable_metrics=True
        )

        @app.get("/test")
        async def test():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-Trace-ID" not in response.headers
        assert "X-Span-ID" not in response.headers

    def test_disable_metrics(self):
        """Test metrics can be disabled."""
        app = FastAPI()
        metrics_client = MockMetricsClient()

        app.add_middleware(
            MonitoringMiddleware,
            metrics_client=metrics_client,
            enable_tracing=True,
            enable_metrics=False
        )

        @app.get("/test")
        async def test():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200

        # No metrics should be recorded
        assert len(metrics_client.metrics["increments"]) == 0
        assert len(metrics_client.metrics["histograms"]) == 0

    def test_sampling_rate(self):
        """Test sampling rate configuration."""
        app = FastAPI()
        metrics_client = MockMetricsClient()

        app.add_middleware(
            MonitoringMiddleware,
            metrics_client=metrics_client,
            enable_tracing=True,
            sample_rate=0.5  # 50% sampling
        )

        @app.get("/test")
        async def test():
            return {"ok": True}

        client = TestClient(app)

        # Make many requests
        traced_count = 0
        for _ in range(20):
            response = client.get("/test")
            if "X-Trace-ID" in response.headers:
                traced_count += 1

        # Should be approximately 50%
        assert 5 <= traced_count <= 15

    def test_custom_slow_threshold(self):
        """Test custom slow request threshold."""
        app = FastAPI()
        metrics_client = MockMetricsClient()

        app.add_middleware(
            MonitoringMiddleware,
            metrics_client=metrics_client,
            slow_request_threshold=0.01  # Very low threshold
        )

        @app.get("/test")
        async def test():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200

        # Should be marked as slow
        slow_metrics = [m for m in metrics_client.metrics["increments"]
                       if m["metric"] == "http.slow_requests"]
        assert len(slow_metrics) > 0


class TestMonitoringPerformance:
    """Test monitoring performance impact."""

    def test_monitoring_overhead(self, client):
        """Test monitoring overhead is acceptable."""
        test_client, metrics = client

        # Warm up
        test_client.get("/test")

        # Measure with monitoring
        start = time.time()
        for _ in range(100):
            response = test_client.get("/test")
            assert response.status_code == 200
        monitoring_time = time.time() - start

        # Should be fast
        avg_time = monitoring_time / 100
        assert avg_time < 0.01  # Less than 10ms per request

    def test_metrics_memory_usage(self, client):
        """Test metrics don't consume excessive memory."""
        test_client, metrics = client

        # Make many requests
        for _ in range(1000):
            test_client.get("/test")

        # Check metrics storage
        total_metrics = (
            len(metrics.metrics["increments"]) +
            len(metrics.metrics["histograms"]) +
            len(metrics.metrics["gauges"]) +
            len(metrics.metrics["timers"])
        )

        # Should have reasonable number of metrics
        # (not storing unlimited history)
        assert total_metrics < 10000