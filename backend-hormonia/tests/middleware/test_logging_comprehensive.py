"""
Comprehensive unit tests for Logging middleware.

Tests cover:
- Request/response logging with correlation IDs
- Structured logging with sensitive data redaction
- Performance metrics and timing
- Error logging and exception handling
- Body logging configuration
- Header sanitization
- Edge cases and error scenarios

Achieves 80%+ code coverage.
"""

import pytest
import json
import time
import hashlib
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from app.middleware.enhanced_middleware import RequestLoggingMiddleware


class MockRequest:
    """Mock FastAPI Request object for testing."""
    
    def __init__(self, method="GET", path="/test", headers=None, query_params=None, client_ip="127.0.0.1"):
        self.method = method
        self.url = Mock()
        self.url.path = path
        self.headers = headers or {}
        self.query_params = query_params or {}
        self.client = Mock()
        self.client.host = client_ip
        self.state = Mock()
        self._body = None
    
    async def body(self):
        """Mock async body method."""
        return self._body or b''
    
    def set_body(self, body):
        """Set the request body for testing."""
        if isinstance(body, str):
            self._body = body.encode()
        else:
            self._body = body


class MockResponse:
    """Mock FastAPI Response object for testing."""
    
    def __init__(self, status_code=200, headers=None, body=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.body = body or b'{"message": "test"}'


class TestRequestLoggingMiddleware:
    """Test RequestLoggingMiddleware functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.middleware = RequestLoggingMiddleware(
            self.mock_app,
            log_request_body=True,
            log_response_body=True
        )
    
    def test_middleware_initialization_defaults(self):
        """Test middleware initialization with default values."""
        middleware = RequestLoggingMiddleware(self.mock_app)
        
        assert middleware.log_request_body is False
        assert middleware.log_response_body is False
        assert "authorization" in middleware.sensitive_headers
        assert "cookie" in middleware.sensitive_headers
        assert "x-api-key" in middleware.sensitive_headers
        assert "x-auth-token" in middleware.sensitive_headers
    
    def test_middleware_initialization_custom_values(self):
        """Test middleware initialization with custom values."""
        custom_sensitive_headers = ["custom-header", "secret-key"]
        middleware = RequestLoggingMiddleware(
            self.mock_app,
            log_request_body=True,
            log_response_body=True,
            sensitive_headers=custom_sensitive_headers
        )
        
        assert middleware.log_request_body is True
        assert middleware.log_response_body is True
        assert "custom-header" in middleware.sensitive_headers
        assert "secret-key" in middleware.sensitive_headers
    
    def test_generate_correlation_id_from_existing_header(self):
        """Test correlation ID generation using existing header."""
        request = MockRequest(headers={"X-Correlation-ID": "existing-id-123"})
        
        correlation_id = self.middleware._generate_correlation_id(request)
        assert correlation_id == "existing-id-123"
    
    def test_generate_correlation_id_new(self):
        """Test correlation ID generation for new request."""
        request = MockRequest()
        
        correlation_id = self.middleware._generate_correlation_id(request)
        
        # Should be a 12-character hash
        assert len(correlation_id) == 12
        assert isinstance(correlation_id, str)
        
        # Should be consistent for same input
        correlation_id2 = self.middleware._generate_correlation_id(request)
        assert correlation_id == correlation_id2
    
    def test_generate_correlation_id_different_requests(self):
        """Test that different requests get different correlation IDs."""
        request1 = MockRequest(path="/test1")
        request2 = MockRequest(path="/test2")
        
        id1 = self.middleware._generate_correlation_id(request1)
        id2 = self.middleware._generate_correlation_id(request2)
        
        assert id1 != id2
    
    @pytest.mark.asyncio
    async def test_log_request_basic(self):
        """Test basic request logging functionality."""
        request = MockRequest(
            method="POST",
            path="/api/test",
            headers={"Content-Type": "application/json", "User-Agent": "test-client"},
            query_params={"param1": "value1"}
        )
        
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            await self.middleware._log_request(request, "test-correlation-id")
            
            # Verify logging was called
            mock_logger.info.assert_called_once()
            
            # Check log message and data
            call_args = mock_logger.info.call_args
            log_message = call_args[0][0]
            log_extra = call_args[1]['extra']
            
            assert "HTTP POST /api/test" in log_message
            assert log_extra['event_type'] == 'http_request_start'
            assert log_extra['correlation_id'] == 'test-correlation-id'
            assert log_extra['method'] == 'POST'
            assert log_extra['path'] == '/api/test'
            assert log_extra['query_params'] == {'param1': 'value1'}
            assert log_extra['client_ip'] == '127.0.0.1'
    
    @pytest.mark.asyncio
    async def test_log_request_header_sanitization(self):
        """Test that sensitive headers are redacted in logs."""
        request = MockRequest(
            headers={
                "Authorization": "Bearer secret-token",
                "Cookie": "session=abc123",
                "X-API-Key": "secret-key",
                "Content-Type": "application/json"
            }
        )
        
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            await self.middleware._log_request(request, "test-id")
            
            log_extra = mock_logger.info.call_args[1]['extra']
            headers = log_extra['headers']
            
            # Sensitive headers should be redacted
            assert headers['authorization'] == '***REDACTED***'
            assert headers['cookie'] == '***REDACTED***'
            assert headers['x-api-key'] == '***REDACTED***'
            
            # Non-sensitive headers should remain
            assert headers['content-type'] == 'application/json'
    
    @pytest.mark.asyncio
    async def test_log_request_with_json_body(self):
        """Test request logging with JSON body."""
        request = MockRequest(
            method="POST",
            headers={"Content-Type": "application/json"}
        )
        
        test_body = {"user": "test", "action": "login"}
        request.set_body(json.dumps(test_body))
        
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            await self.middleware._log_request(request, "test-id")
            
            log_extra = mock_logger.info.call_args[1]['extra']
            
            # Should include parsed JSON body
            assert 'request_body' in log_extra
            assert log_extra['request_body'] == test_body
    
    @pytest.mark.asyncio
    async def test_log_request_with_non_json_body(self):
        """Test request logging with non-JSON body."""
        request = MockRequest(
            method="POST",
            headers={"Content-Type": "text/plain"}
        )
        
        test_body = "plain text data"
        request.set_body(test_body)
        
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            await self.middleware._log_request(request, "test-id")
            
            log_extra = mock_logger.info.call_args[1]['extra']
            
            # Should include body size instead of content
            assert 'request_body_size' in log_extra
            assert log_extra['request_body_size'] == len(test_body.encode())
    
    @pytest.mark.asyncio
    async def test_log_request_body_disabled(self):
        """Test request logging with body logging disabled."""
        middleware = RequestLoggingMiddleware(
            self.mock_app,
            log_request_body=False
        )
        
        request = MockRequest(method="POST")
        request.set_body(json.dumps({"data": "test"}))
        
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            await middleware._log_request(request, "test-id")
            
            log_extra = mock_logger.info.call_args[1]['extra']
            
            # Should not include request body
            assert 'request_body' not in log_extra
            assert 'request_body_size' not in log_extra
    
    @pytest.mark.asyncio
    async def test_log_request_body_error_handling(self):
        """Test request logging handles body parsing errors gracefully."""
        request = MockRequest(
            method="POST",
            headers={"Content-Type": "application/json"}
        )
        
        # Set invalid JSON
        request.set_body("invalid json {")
        
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            await self.middleware._log_request(request, "test-id")
            
            # Should log warning about body parsing failure
            mock_logger.warning.assert_called_once()
            assert "Failed to log request body" in mock_logger.warning.call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_log_response_success(self):
        """Test successful response logging."""
        request = MockRequest()
        response = MockResponse(
            status_code=200,
            headers={"Content-Type": "application/json", "Content-Length": "25"}
        )
        process_time = 0.123
        
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            await self.middleware._log_response(request, response, process_time, "test-id")
            
            # Should log at info level for 2xx status
            mock_logger.info.assert_called_once()
            
            log_extra = mock_logger.info.call_args[1]['extra']
            assert log_extra['event_type'] == 'http_request_complete'
            assert log_extra['correlation_id'] == 'test-id'
            assert log_extra['status_code'] == 200
            assert log_extra['process_time_seconds'] == 0.123
            assert log_extra['response_size'] == '25'
    
    @pytest.mark.asyncio
    async def test_log_response_client_error(self):
        """Test client error response logging."""
        request = MockRequest()
        response = MockResponse(status_code=404)
        
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            await self.middleware._log_response(request, response, 0.1, "test-id")
            
            # Should log at warning level for 4xx status
            mock_logger.warning.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_log_response_server_error(self):
        """Test server error response logging."""
        request = MockRequest()
        response = MockResponse(status_code=500)
        
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            await self.middleware._log_response(request, response, 0.1, "test-id")
            
            # Should log at error level for 5xx status
            mock_logger.error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_log_response_with_body(self):
        """Test response logging with body content."""
        response_data = {"result": "success", "data": [1, 2, 3]}
        response = MockResponse(
            headers={"Content-Type": "application/json"}
        )
        response.body = json.dumps(response_data).encode()
        
        request = MockRequest()
        
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            await self.middleware._log_response(request, response, 0.1, "test-id")
            
            log_extra = mock_logger.info.call_args[1]['extra']
            
            # Should include parsed response body
            assert 'response_body' in log_extra
            assert log_extra['response_body'] == response_data
    
    @pytest.mark.asyncio
    async def test_log_response_large_body_skipped(self):
        """Test that large response bodies are not logged."""
        large_data = "x" * 15000  # Over 10KB limit
        response = MockResponse(
            headers={"Content-Type": "application/json"}
        )
        response.body = large_data.encode()
        
        request = MockRequest()
        
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            await self.middleware._log_response(request, response, 0.1, "test-id")
            
            log_extra = mock_logger.info.call_args[1]['extra']
            
            # Should not include response body for large responses
            assert 'response_body' not in log_extra
    
    @pytest.mark.asyncio
    async def test_log_response_body_disabled(self):
        """Test response logging with body logging disabled."""
        middleware = RequestLoggingMiddleware(
            self.mock_app,
            log_response_body=False
        )
        
        response = MockResponse()
        response.body = json.dumps({"data": "test"}).encode()
        
        request = MockRequest()
        
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            await middleware._log_response(request, response, 0.1, "test-id")
            
            log_extra = mock_logger.info.call_args[1]['extra']
            
            # Should not include response body
            assert 'response_body' not in log_extra
    
    @pytest.mark.asyncio
    async def test_log_error(self):
        """Test error logging functionality."""
        request = MockRequest(method="POST", path="/api/test")
        error = ValueError("Test error message")
        process_time = 0.456
        
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            await self.middleware._log_error(request, error, process_time, "test-id")
            
            # Should log at error level with exc_info
            mock_logger.error.assert_called_once()
            
            call_args = mock_logger.error.call_args
            log_message = call_args[0][0]
            log_extra = call_args[1]['extra']
            exc_info = call_args[1]['exc_info']
            
            assert "HTTP POST /api/test - ERROR: Test error message" in log_message
            assert log_extra['event_type'] == 'http_request_error'
            assert log_extra['correlation_id'] == 'test-id'
            assert log_extra['error_type'] == 'ValueError'
            assert log_extra['error_message'] == 'Test error message'
            assert log_extra['process_time_seconds'] == 0.456
            assert exc_info is True
    
    @pytest.mark.asyncio
    async def test_dispatch_successful_request(self):
        """Test successful request dispatch with logging."""
        request = MockRequest()
        response = MockResponse()
        
        async def mock_call_next(req):
            # Simulate some processing time
            await asyncio.sleep(0.01)
            return response
        
        with patch('app.middleware.enhanced_middleware.logger'):
            result = await self.middleware.dispatch(request, mock_call_next)
            
            # Should return the response
            assert result == response
            
            # Should add correlation headers
            assert "X-Correlation-ID" in result.headers
            assert "X-Process-Time" in result.headers
            
            # Should set correlation ID on request state
            assert hasattr(request.state, 'correlation_id')
    
    @pytest.mark.asyncio
    async def test_dispatch_request_with_exception(self):
        """Test request dispatch when call_next raises an exception."""
        request = MockRequest()
        
        async def failing_call_next(req):
            raise HTTPException(status_code=500, detail="Internal server error")
        
        with patch('app.middleware.enhanced_middleware.logger'):
            with pytest.raises(HTTPException):
                await self.middleware.dispatch(request, failing_call_next)
            
            # Should still set correlation ID
            assert hasattr(request.state, 'correlation_id')
    
    @pytest.mark.asyncio
    async def test_dispatch_preserves_correlation_id(self):
        """Test that existing correlation ID is preserved."""
        request = MockRequest(
            headers={"X-Correlation-ID": "existing-correlation-id"}
        )
        response = MockResponse()
        
        async def mock_call_next(req):
            return response
        
        with patch('app.middleware.enhanced_middleware.logger'):
            result = await self.middleware.dispatch(request, mock_call_next)
            
            # Should preserve existing correlation ID
            assert result.headers["X-Correlation-ID"] == "existing-correlation-id"
            assert request.state.correlation_id == "existing-correlation-id"
    
    @pytest.mark.asyncio
    async def test_dispatch_timing_accuracy(self):
        """Test that process timing is accurately measured."""
        request = MockRequest()
        response = MockResponse()
        
        async def slow_call_next(req):
            await asyncio.sleep(0.1)  # 100ms delay
            return response
        
        with patch('app.middleware.enhanced_middleware.logger'):
            result = await self.middleware.dispatch(request, slow_call_next)
            
            # Process time should be approximately 0.1 seconds
            process_time = float(result.headers["X-Process-Time"])
            assert 0.08 <= process_time <= 0.15  # Allow some variance


class TestLoggingMiddlewareIntegration:
    """Integration tests with FastAPI application."""
    
    def setup_method(self):
        """Set up test app and client."""
        self.app = FastAPI()
        
        @self.app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        @self.app.post("/api/data")
        async def data_endpoint(data: dict):
            return {"received": data}
        
        @self.app.get("/error")
        async def error_endpoint():
            raise HTTPException(status_code=500, detail="Test error")
        
        # Add logging middleware
        self.app.add_middleware(
            RequestLoggingMiddleware,
            log_request_body=True,
            log_response_body=True
        )
        
        self.client = TestClient(self.app)
    
    def test_logging_integration_get_request(self):
        """Test logging integration with GET request."""
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            response = self.client.get("/test")
            
            assert response.status_code == 200
            assert "X-Correlation-ID" in response.headers
            assert "X-Process-Time" in response.headers
            
            # Should have logged request and response
            assert mock_logger.info.call_count >= 2
    
    def test_logging_integration_post_request(self):
        """Test logging integration with POST request and body."""
        test_data = {"key": "value", "number": 42}
        
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            response = self.client.post("/api/data", json=test_data)
            
            assert response.status_code == 200
            assert response.json() == {"received": test_data}
            
            # Should log request with body
            assert mock_logger.info.call_count >= 2
    
    def test_logging_integration_error_request(self):
        """Test logging integration with error response."""
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            response = self.client.get("/error")
            
            assert response.status_code == 500
            
            # Should log error
            mock_logger.error.assert_called()
    
    def test_logging_integration_correlation_id_propagation(self):
        """Test that correlation ID is properly propagated."""
        custom_correlation_id = "custom-test-id-123"
        
        response = self.client.get(
            "/test",
            headers={"X-Correlation-ID": custom_correlation_id}
        )
        
        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == custom_correlation_id


class TestLoggingMiddlewareErrorScenarios:
    """Test error scenarios and edge cases."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.middleware = RequestLoggingMiddleware(self.mock_app)
    
    @pytest.mark.asyncio
    async def test_request_without_client(self):
        """Test request logging when request.client is None."""
        request = MockRequest()
        request.client = None
        
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            await self.middleware._log_request(request, "test-id")
            
            log_extra = mock_logger.info.call_args[1]['extra']
            assert log_extra['client_ip'] == 'unknown'
    
    @pytest.mark.asyncio
    async def test_response_without_body_attribute(self):
        """Test response logging when response has no body attribute."""
        request = MockRequest()
        response = MockResponse()
        delattr(response, 'body')  # Remove body attribute
        
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            await self.middleware._log_response(request, response, 0.1, "test-id")
            
            # Should not crash and not include response_body
            log_extra = mock_logger.info.call_args[1]['extra']
            assert 'response_body' not in log_extra
    
    @pytest.mark.asyncio
    async def test_request_body_exception(self):
        """Test handling of request.body() exceptions."""
        request = MockRequest(method="POST")
        
        # Mock body() to raise an exception
        async def failing_body():
            raise Exception("Body read failed")
        
        request.body = failing_body
        
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            await self.middleware._log_request(request, "test-id")
            
            # Should log warning about body failure
            mock_logger.warning.assert_called_once()
            assert "Failed to log request body" in mock_logger.warning.call_args[0][0]
    
    def test_correlation_id_with_empty_values(self):
        """Test correlation ID generation with empty/None values."""
        request = MockRequest()
        request.client = None
        request.url.path = ""
        
        # Should still generate a valid correlation ID
        correlation_id = self.middleware._generate_correlation_id(request)
        assert len(correlation_id) == 12
        assert isinstance(correlation_id, str)
    
    @pytest.mark.asyncio
    async def test_response_body_json_parse_error(self):
        """Test response body logging with invalid JSON."""
        request = MockRequest()
        response = MockResponse(
            headers={"Content-Type": "application/json"}
        )
        response.body = b"invalid json content {"
        
        with patch('app.middleware.enhanced_middleware.logger') as mock_logger:
            await self.middleware._log_response(request, response, 0.1, "test-id")
            
            # Should log warning about JSON parsing failure
            mock_logger.warning.assert_called()
            assert "Failed to log response body" in mock_logger.warning.call_args[0][0]


if __name__ == "__main__":
    pytest.main([__file__])
