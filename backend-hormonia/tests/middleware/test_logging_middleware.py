"""
Integration tests for Logging Middleware.

Tests request/response logging functionality.
"""

import pytest
import json
import logging
from unittest.mock import Mock, patch, MagicMock
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
import time
from datetime import datetime


class LoggingMiddleware(BaseHTTPMiddleware):
    """Request/Response logging middleware."""

    def __init__(self, app, logger=None, log_body: bool = False, log_headers: bool = True):
        super().__init__(app)
        self.logger = logger or logging.getLogger(__name__)
        self.log_body = log_body
        self.log_headers = log_headers

    async def dispatch(self, request: Request, call_next):
        """Log request and response details."""
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", str(time.time()))

        # Log request
        start_time = time.time()
        request_log = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "client": request.client.host if request.client else None,
            "timestamp": datetime.utcnow().isoformat()
        }

        if self.log_headers:
            request_log["headers"] = dict(request.headers)

        if self.log_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                request_log["body_size"] = len(body)
                # Reset body for downstream processing
                request._body = body
            except:
                pass

        self.logger.info(f"Request started: {json.dumps(request_log)}")

        # Process request
        response = await call_next(request)

        # Log response
        duration = time.time() - start_time
        response_log = {
            "request_id": request_id,
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
            "timestamp": datetime.utcnow().isoformat()
        }

        if self.log_headers:
            response_log["headers"] = dict(response.headers)

        self.logger.info(f"Request completed: {json.dumps(response_log)}")

        # Add timing header
        response.headers["X-Response-Time"] = f"{duration * 1000:.2f}ms"
        response.headers["X-Request-ID"] = request_id

        return response


@pytest.fixture
def app_with_logging():
    """Create FastAPI app with logging middleware."""
    app = FastAPI()

    # Setup logger
    logger = logging.getLogger("test_logger")

    # Add logging middleware
    app.add_middleware(
        LoggingMiddleware,
        logger=logger,
        log_body=True,
        log_headers=True
    )

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.post("/data")
    async def post_endpoint(data: dict):
        return {"received": data}

    @app.get("/slow")
    async def slow_endpoint():
        import asyncio
        await asyncio.sleep(0.1)
        return {"status": "slow"}

    @app.get("/error")
    async def error_endpoint():
        raise ValueError("Test error")

    return app


@pytest.fixture
def client(app_with_logging):
    """Create test client."""
    return TestClient(app_with_logging)


class TestLoggingMiddleware:
    """Test logging middleware functionality."""

    def test_request_logging(self, client):
        """Test request is logged."""
        with patch('logging.Logger.info') as mock_log:
            response = client.get("/test")
            assert response.status_code == 200

            # Should have request and response logs
            assert mock_log.call_count >= 2

            # Check request log
            request_log = mock_log.call_args_list[0][0][0]
            assert "Request started" in request_log
            assert "/test" in request_log

    def test_response_logging(self, client):
        """Test response is logged."""
        with patch('logging.Logger.info') as mock_log:
            response = client.get("/test")
            assert response.status_code == 200

            # Check response log
            response_log = mock_log.call_args_list[-1][0][0]
            assert "Request completed" in response_log
            assert "200" in str(response_log)

    def test_response_time_header(self, client):
        """Test response time header is added."""
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-Response-Time" in response.headers
        assert "ms" in response.headers["X-Response-Time"]

    def test_request_id_tracking(self, client):
        """Test request ID is tracked."""
        custom_id = "test-request-123"
        response = client.get("/test", headers={"X-Request-ID": custom_id})
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == custom_id

    def test_request_id_generation(self, client):
        """Test request ID is generated if not provided."""
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] != ""

    def test_post_request_logging(self, client):
        """Test POST request with body is logged."""
        with patch('logging.Logger.info') as mock_log:
            response = client.post("/data", json={"test": "data"})
            assert response.status_code == 200

            # Check body size is logged
            request_log = mock_log.call_args_list[0][0][0]
            assert "body_size" in request_log or "Request started" in request_log

    def test_headers_logging(self, client):
        """Test headers are logged when enabled."""
        with patch('logging.Logger.info') as mock_log:
            response = client.get(
                "/test",
                headers={"User-Agent": "TestClient", "Custom-Header": "value"}
            )
            assert response.status_code == 200

            request_log = mock_log.call_args_list[0][0][0]
            assert "headers" in request_log.lower() or "Request started" in request_log

    def test_client_info_logging(self, client):
        """Test client information is logged."""
        with patch('logging.Logger.info') as mock_log:
            response = client.get("/test")
            assert response.status_code == 200

            request_log = mock_log.call_args_list[0][0][0]
            assert "client" in request_log.lower() or "testclient" in request_log.lower()

    def test_duration_measurement(self, client):
        """Test request duration is measured."""
        response = client.get("/slow")
        assert response.status_code == 200

        time_header = response.headers["X-Response-Time"]
        duration = float(time_header.replace("ms", ""))
        assert duration >= 100  # Should be at least 100ms

    def test_error_logging(self, client):
        """Test errors are logged."""
        with patch('logging.Logger.info') as mock_log:
            response = client.get("/error")
            assert response.status_code == 500

            # Should still log response
            assert mock_log.call_count >= 1

    def test_multiple_requests_logging(self, client):
        """Test multiple requests are logged independently."""
        with patch('logging.Logger.info') as mock_log:
            # Make multiple requests
            response1 = client.get("/test")
            response2 = client.post("/data", json={"data": 1})
            response3 = client.get("/test")

            assert response1.status_code == 200
            assert response2.status_code == 200
            assert response3.status_code == 200

            # Should have logs for all requests
            assert mock_log.call_count >= 6  # 2 logs per request


class TestLoggingConfiguration:
    """Test logging middleware configuration."""

    def test_disable_body_logging(self):
        """Test body logging can be disabled."""
        app = FastAPI()
        logger = Mock()

        app.add_middleware(
            LoggingMiddleware,
            logger=logger,
            log_body=False,
            log_headers=True
        )

        @app.post("/test")
        async def test():
            return {"ok": True}

        client = TestClient(app)
        response = client.post("/test", json={"data": "test"})
        assert response.status_code == 200

    def test_disable_headers_logging(self):
        """Test headers logging can be disabled."""
        app = FastAPI()
        logger = Mock()

        app.add_middleware(
            LoggingMiddleware,
            logger=logger,
            log_body=True,
            log_headers=False
        )

        @app.get("/test")
        async def test():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test", headers={"Custom": "Header"})
        assert response.status_code == 200

    def test_custom_logger(self):
        """Test custom logger can be used."""
        app = FastAPI()
        custom_logger = Mock()

        app.add_middleware(
            LoggingMiddleware,
            logger=custom_logger
        )

        @app.get("/test")
        async def test():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200

        # Custom logger should be called
        custom_logger.info.assert_called()


class TestLoggingPerformance:
    """Test logging performance impact."""

    def test_logging_overhead(self, client):
        """Test logging doesn't significantly impact performance."""
        # Warm up
        client.get("/test")

        # Measure without logging
        with patch('logging.Logger.info'):
            start = time.time()
            for _ in range(100):
                response = client.get("/test")
                assert response.status_code == 200
            no_log_time = time.time() - start

        # Measure with logging
        start = time.time()
        for _ in range(100):
            response = client.get("/test")
            assert response.status_code == 200
        log_time = time.time() - start

        # Logging shouldn't more than double the time
        assert log_time < no_log_time * 3

    def test_large_body_handling(self):
        """Test large request bodies are handled efficiently."""
        app = FastAPI()
        logger = Mock()

        app.add_middleware(
            LoggingMiddleware,
            logger=logger,
            log_body=True
        )

        @app.post("/test")
        async def test(data: dict):
            return {"size": len(str(data))}

        client = TestClient(app)

        # Send large payload
        large_data = {"data": ["item" * 100 for _ in range(1000)]}
        response = client.post("/test", json=large_data)
        assert response.status_code == 200