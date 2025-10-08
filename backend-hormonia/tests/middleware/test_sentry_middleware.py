"""
Integration tests for Sentry Middleware.

Tests error tracking and performance monitoring integration.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.monitoring.sentry_config import SentryConfig, SentryMiddleware
import os


@pytest.fixture
def mock_sentry():
    """Mock Sentry SDK."""
    with patch('app.monitoring.sentry_config.sentry_sdk') as mock_sdk:
        mock_sdk.init = Mock()
        mock_sdk.set_tag = Mock()
        mock_sdk.set_context = Mock()
        mock_sdk.capture_exception = Mock(return_value="test-event-id")
        mock_sdk.capture_message = Mock(return_value="test-message-id")
        mock_sdk.set_user = Mock()
        mock_sdk.add_breadcrumb = Mock()
        yield mock_sdk


@pytest.fixture
def app_with_sentry(mock_sentry):
    """Create FastAPI app with Sentry middleware."""
    app = FastAPI()

    # Initialize Sentry (mocked)
    with patch.dict(os.environ, {
        'SENTRY_DSN': 'https://test@sentry.io/123456',
        'ENVIRONMENT': 'test'
    }):
        SentryConfig.init_sentry()

    # Add Sentry middleware
    app.add_middleware(SentryMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.get("/error")
    async def error_endpoint():
        raise ValueError("Test error")

    @app.get("/http-error")
    async def http_error_endpoint():
        raise HTTPException(status_code=404, detail="Not found")

    @app.post("/data")
    async def data_endpoint(data: dict):
        return {"received": data}

    return app


@pytest.fixture
def client(app_with_sentry):
    """Create test client."""
    return TestClient(app_with_sentry)


class TestSentryMiddleware:
    """Test Sentry middleware functionality."""

    def test_successful_request_tracking(self, client, mock_sentry):
        """Test successful requests are tracked."""
        response = client.get("/test")
        assert response.status_code == 200

        # Should add breadcrumb for successful request
        mock_sentry.add_breadcrumb.assert_called()

    def test_error_capture(self, client, mock_sentry):
        """Test errors are captured by Sentry."""
        response = client.get("/error")
        assert response.status_code == 500

        # Should capture exception
        mock_sentry.capture_exception.assert_called()

    def test_http_exception_not_captured(self, client, mock_sentry):
        """Test HTTP exceptions are not captured as errors."""
        response = client.get("/http-error")
        assert response.status_code == 404

        # Should not capture HTTPException as error
        mock_sentry.capture_exception.assert_not_called()

    def test_request_context_added(self, client, mock_sentry):
        """Test request context is added to Sentry."""
        response = client.get("/test", headers={"User-Agent": "TestClient/1.0"})
        assert response.status_code == 200

        # Should set context
        mock_sentry.set_context.assert_called()

    def test_user_context_from_headers(self, client, mock_sentry):
        """Test user context is extracted from headers."""
        response = client.get(
            "/test",
            headers={"Authorization": "Bearer test-token"}
        )
        assert response.status_code == 200

    def test_performance_tracking(self, client, mock_sentry):
        """Test performance tracking for requests."""
        with patch('app.monitoring.sentry_config.start_transaction') as mock_transaction:
            mock_span = MagicMock()
            mock_transaction.return_value = mock_span

            response = client.get("/test")
            assert response.status_code == 200

    def test_post_request_tracking(self, client, mock_sentry):
        """Test POST requests are tracked."""
        response = client.post("/data", json={"test": "data"})
        assert response.status_code == 200

        # Should add breadcrumb
        mock_sentry.add_breadcrumb.assert_called()

    def test_error_with_request_id(self, client, mock_sentry):
        """Test errors include request ID."""
        response = client.get(
            "/error",
            headers={"X-Request-ID": "test-request-123"}
        )
        assert response.status_code == 500

        # Should set context with request ID
        calls = mock_sentry.set_context.call_args_list
        assert any("request_id" in str(call) for call in calls)

    def test_sensitive_data_filtering(self, client, mock_sentry):
        """Test sensitive data is filtered."""
        response = client.post(
            "/data",
            json={"password": "secret", "data": "safe"},
            headers={"Authorization": "Bearer token"}
        )
        assert response.status_code == 200

        # Check breadcrumbs don't contain sensitive data
        for call in mock_sentry.add_breadcrumb.call_args_list:
            args = str(call)
            assert "secret" not in args
            assert "token" not in args


class TestSentryConfig:
    """Test Sentry configuration."""

    def test_init_without_dsn(self, mock_sentry):
        """Test Sentry doesn't initialize without DSN."""
        with patch.dict(os.environ, {}, clear=True):
            SentryConfig.init_sentry()
            mock_sentry.init.assert_not_called()

    def test_init_with_dsn(self, mock_sentry):
        """Test Sentry initializes with DSN."""
        with patch.dict(os.environ, {
            'SENTRY_DSN': 'https://test@sentry.io/123456',
            'ENVIRONMENT': 'production'
        }):
            SentryConfig.init_sentry()
            mock_sentry.init.assert_called_once()

    def test_environment_configuration(self, mock_sentry):
        """Test environment-specific configuration."""
        with patch.dict(os.environ, {
            'SENTRY_DSN': 'https://test@sentry.io/123456',
            'ENVIRONMENT': 'staging',
            'SENTRY_TRACES_SAMPLE_RATE': '0.5'
        }):
            SentryConfig.init_sentry()

            init_call = mock_sentry.init.call_args
            assert init_call[1]['environment'] == 'staging'
            assert init_call[1]['traces_sample_rate'] == 0.5

    def test_capture_exception_method(self, mock_sentry):
        """Test capture exception method."""
        error = ValueError("Test error")
        event_id = SentryConfig.capture_exception(error, {"context": "test"})

        mock_sentry.capture_exception.assert_called_with(
            error,
            extra={"context": "test"}
        )
        assert event_id == "test-event-id"

    def test_capture_message_method(self, mock_sentry):
        """Test capture message method."""
        message_id = SentryConfig.capture_message(
            "Test message",
            level="warning",
            extra={"detail": "test"}
        )

        mock_sentry.capture_message.assert_called_with(
            "Test message",
            level="warning",
            extra={"detail": "test"}
        )
        assert message_id == "test-message-id"

    def test_set_user_context(self, mock_sentry):
        """Test setting user context."""
        SentryConfig.set_user_context({
            "id": "user-123",
            "email": "test@example.com",
            "role": "admin"
        })

        mock_sentry.set_user.assert_called_with({
            "id": "user-123",
            "email": "test@example.com",
            "role": "admin"
        })

    def test_add_breadcrumb(self, mock_sentry):
        """Test adding breadcrumb."""
        SentryConfig.add_breadcrumb(
            message="Test action",
            category="test",
            level="info",
            data={"key": "value"}
        )

        mock_sentry.add_breadcrumb.assert_called_with(
            message="Test action",
            category="test",
            level="info",
            data={"key": "value"}
        )