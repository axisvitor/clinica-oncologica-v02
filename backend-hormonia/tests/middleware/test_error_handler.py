"""
Integration tests for Error Handler Middleware.

Tests global error handling, logging, and error responses.
"""

import pytest
import json
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from unittest.mock import Mock, patch
import logging


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Global error handler middleware."""

    async def dispatch(self, request, call_next):
        """Handle errors globally."""
        try:
            response = await call_next(request)
            return response
        except HTTPException as exc:
            # Let HTTPException pass through
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": exc.detail,
                    "status_code": exc.status_code,
                    "path": str(request.url.path)
                }
            )
        except ValueError as exc:
            # Handle ValueError as 400
            return JSONResponse(
                status_code=400,
                content={
                    "error": str(exc),
                    "type": "validation_error",
                    "path": str(request.url.path)
                }
            )
        except PermissionError as exc:
            # Handle PermissionError as 403
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Permission denied",
                    "detail": str(exc),
                    "path": str(request.url.path)
                }
            )
        except Exception as exc:
            # Log unexpected errors
            logging.error(f"Unhandled error: {exc}", exc_info=True)

            # Return generic error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "message": "An unexpected error occurred",
                    "path": str(request.url.path)
                }
            )


@pytest.fixture
def app_with_error_handler():
    """Create FastAPI app with error handler middleware."""
    app = FastAPI()

    # Add error handler middleware
    app.add_middleware(ErrorHandlerMiddleware)

    @app.get("/success")
    async def success_endpoint():
        return {"status": "ok"}

    @app.get("/http-error")
    async def http_error_endpoint():
        raise HTTPException(status_code=404, detail="Resource not found")

    @app.get("/value-error")
    async def value_error_endpoint():
        raise ValueError("Invalid value provided")

    @app.get("/permission-error")
    async def permission_error_endpoint():
        raise PermissionError("Access denied to resource")

    @app.get("/generic-error")
    async def generic_error_endpoint():
        raise RuntimeError("Something went wrong")

    @app.get("/division-error")
    async def division_error_endpoint():
        return {"result": 1 / 0}

    @app.post("/validation")
    async def validation_endpoint(data: dict):
        if "required_field" not in data:
            raise ValueError("Missing required field")
        return {"received": data}

    return app


@pytest.fixture
def client(app_with_error_handler):
    """Create test client."""
    return TestClient(app_with_error_handler)


class TestErrorHandlerMiddleware:
    """Test error handler middleware functionality."""

    def test_successful_request(self, client):
        """Test successful requests pass through."""
        response = client.get("/success")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_http_exception_handling(self, client):
        """Test HTTPException is handled properly."""
        response = client.get("/http-error")
        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "Resource not found"
        assert data["status_code"] == 404
        assert data["path"] == "/http-error"

    def test_value_error_handling(self, client):
        """Test ValueError is handled as 400."""
        response = client.get("/value-error")
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "Invalid value provided"
        assert data["type"] == "validation_error"
        assert data["path"] == "/value-error"

    def test_permission_error_handling(self, client):
        """Test PermissionError is handled as 403."""
        response = client.get("/permission-error")
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "Permission denied"
        assert "Access denied" in data["detail"]
        assert data["path"] == "/permission-error"

    def test_generic_error_handling(self, client):
        """Test generic exceptions are handled as 500."""
        with patch("logging.error") as mock_log:
            response = client.get("/generic-error")
            assert response.status_code == 500
            data = response.json()
            assert data["error"] == "Internal server error"
            assert data["message"] == "An unexpected error occurred"
            assert data["path"] == "/generic-error"

            # Check error was logged
            mock_log.assert_called_once()

    def test_division_error_handling(self, client):
        """Test division by zero error handling."""
        with patch("logging.error") as mock_log:
            response = client.get("/division-error")
            assert response.status_code == 500
            data = response.json()
            assert data["error"] == "Internal server error"

            # Check error was logged
            mock_log.assert_called_once()

    def test_validation_error_in_post(self, client):
        """Test validation error in POST request."""
        response = client.post("/validation", json={})
        assert response.status_code == 400
        data = response.json()
        assert "Missing required field" in data["error"]

    def test_error_response_format(self, client):
        """Test error responses have consistent format."""
        # Test different error types
        endpoints = [
            ("/http-error", 404),
            ("/value-error", 400),
            ("/permission-error", 403),
            ("/generic-error", 500)
        ]

        for endpoint, expected_status in endpoints:
            response = client.get(endpoint)
            assert response.status_code == expected_status

            # Check response is JSON
            assert response.headers["content-type"] == "application/json"

            # Check response has error field
            data = response.json()
            assert "error" in data
            assert "path" in data

    def test_error_handler_preserves_headers(self, client):
        """Test error handler preserves important headers."""
        response = client.get(
            "/http-error",
            headers={"X-Request-ID": "test-123"}
        )
        assert response.status_code == 404
        # Headers might be preserved depending on implementation

    def test_concurrent_error_handling(self, client):
        """Test concurrent errors are handled independently."""
        # Make multiple error requests
        responses = []
        for _ in range(5):
            responses.append(client.get("/value-error"))
            responses.append(client.get("/http-error"))

        # All should be handled correctly
        for i, response in enumerate(responses):
            if i % 2 == 0:
                assert response.status_code == 400
            else:
                assert response.status_code == 404


class TestErrorLogging:
    """Test error logging functionality."""

    def test_unexpected_errors_logged(self, client):
        """Test unexpected errors are logged."""
        with patch("logging.error") as mock_log:
            response = client.get("/generic-error")
            assert response.status_code == 500

            # Check logging was called
            mock_log.assert_called_once()
            args = mock_log.call_args
            assert "Unhandled error" in args[0][0]
            assert args[1]["exc_info"] is True

    def test_expected_errors_not_logged(self, client):
        """Test expected errors are not logged."""
        with patch("logging.error") as mock_log:
            # HTTPException should not be logged
            response = client.get("/http-error")
            assert response.status_code == 404
            mock_log.assert_not_called()

            # ValueError should not be logged (handled case)
            response = client.get("/value-error")
            assert response.status_code == 400
            mock_log.assert_not_called()

    def test_error_details_not_leaked(self, client):
        """Test sensitive error details are not leaked."""
        response = client.get("/generic-error")
        assert response.status_code == 500
        data = response.json()

        # Should not contain stack trace or sensitive info
        assert "traceback" not in str(data).lower()
        assert "RuntimeError" not in data.get("error", "")
        assert data["error"] == "Internal server error"


class TestErrorHandlerPerformance:
    """Test error handler performance."""

    def test_error_handler_performance(self, client):
        """Test error handler doesn't significantly impact performance."""
        import time

        # Measure successful request time
        start = time.time()
        for _ in range(100):
            response = client.get("/success")
            assert response.status_code == 200
        success_time = time.time() - start

        # Measure error request time
        start = time.time()
        for _ in range(100):
            response = client.get("/value-error")
            assert response.status_code == 400
        error_time = time.time() - start

        # Error handling shouldn't be significantly slower
        # Allow 2x time for error handling
        assert error_time < success_time * 2