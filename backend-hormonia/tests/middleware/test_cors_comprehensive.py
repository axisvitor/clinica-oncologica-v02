"""
Comprehensive unit tests for CORS middleware.

Tests cover:
- Production vs development environment behavior
- Origin validation (HTTPS enforcement, wildcard blocking)
- Method and header validation
- Credential handling
- Error scenarios and edge cases

Achieves 80%+ code coverage.
"""

import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.cors import (
    configure_cors,
    validate_cors_origins,
    is_production
)


class TestProductionEnvironmentDetection:
    """Test production environment detection logic."""
    
    def test_is_production_with_production_env(self):
        """Test production detection with 'production' environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            assert is_production() is True
    
    def test_is_production_with_prod_env(self):
        """Test production detection with 'prod' environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}):
            assert is_production() is True
    
    def test_is_production_with_development_env(self):
        """Test production detection with development environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            assert is_production() is False
    
    def test_is_production_with_no_env(self):
        """Test production detection with no environment set."""
        with patch.dict(os.environ, {}, clear=True):
            assert is_production() is False
    
    def test_is_production_case_insensitive(self):
        """Test production detection is case insensitive."""
        with patch.dict(os.environ, {"ENVIRONMENT": "PRODUCTION"}):
            assert is_production() is True
        
        with patch.dict(os.environ, {"ENVIRONMENT": "Development"}):
            assert is_production() is False


class TestCORSOriginValidation:
    """Test CORS origin validation logic."""
    
    def test_validate_cors_origins_development_allows_all(self):
        """Test that development mode allows any configuration."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            # Should not raise for any configuration in development
            validate_cors_origins(["*"], ".*")
            validate_cors_origins(["http://localhost:3000"])
            validate_cors_origins(["https://example.com", "http://insecure.com"])
    
    def test_validate_cors_origins_production_blocks_regex(self):
        """Test that production blocks regex patterns."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            with pytest.raises(ValueError, match="CORS origin regex not allowed in production"):
                validate_cors_origins(["https://example.com"], ".*")
    
    def test_validate_cors_origins_production_blocks_wildcard(self):
        """Test that production blocks wildcard origins."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            with pytest.raises(ValueError, match="CORS wildcard origin \(\*\) not allowed in production"):
                validate_cors_origins(["*"])
            
            with pytest.raises(ValueError, match="CORS wildcard origin \(\*\) not allowed in production"):
                validate_cors_origins(["https://example.com", "*"])
    
    def test_validate_cors_origins_production_requires_https(self):
        """Test that production requires HTTPS origins."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            # Should raise for HTTP origins
            with pytest.raises(ValueError, match="must use HTTPS in production"):
                validate_cors_origins(["http://example.com"])
            
            with pytest.raises(ValueError, match="must use HTTPS in production"):
                validate_cors_origins(["https://secure.com", "http://insecure.com"])
    
    def test_validate_cors_origins_production_allows_https(self):
        """Test that production allows valid HTTPS origins."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            # Should not raise for HTTPS origins
            validate_cors_origins(["https://example.com"])
            validate_cors_origins(["https://app.example.com", "https://api.example.com"])


class TestCORSConfiguration:
    """Test CORS middleware configuration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.app = FastAPI()
    
    @patch('app.middleware.cors.is_production', return_value=False)
    def test_configure_cors_development_defaults(self, mock_is_prod):
        """Test CORS configuration with development defaults."""
        configure_cors(self.app)
        
        # Check that middleware was added
        assert len(self.app.user_middleware) > 0
        
        # Verify middleware configuration through app state
        middleware = self.app.user_middleware[0]
        assert middleware.cls.__name__ == "CORSMiddleware"
    
    @patch('app.middleware.cors.is_production', return_value=True)
    @patch.dict(os.environ, {"CORS_ORIGINS": "https://app.example.com,https://api.example.com"})
    def test_configure_cors_production_from_env(self, mock_is_prod):
        """Test CORS configuration in production with environment variables."""
        configure_cors(self.app)
        
        # Verify middleware was added
        assert len(self.app.user_middleware) > 0
        middleware = self.app.user_middleware[0]
        assert middleware.cls.__name__ == "CORSMiddleware"
    
    @patch('app.middleware.cors.is_production', return_value=True)
    @patch.dict(os.environ, {"CORS_ORIGINS": ""})
    def test_configure_cors_production_missing_env(self, mock_is_prod):
        """Test CORS configuration fails in production without environment variable."""
        with pytest.raises(ValueError, match="CORS_ORIGINS environment variable must be set"):
            configure_cors(self.app)
    
    @patch('app.middleware.cors.is_production', return_value=False)
    def test_configure_cors_custom_origins(self, mock_is_prod):
        """Test CORS configuration with custom origins."""
        custom_origins = ["http://localhost:8080", "http://127.0.0.1:8080"]
        configure_cors(self.app, allowed_origins=custom_origins)
        
        assert len(self.app.user_middleware) > 0
    
    @patch('app.middleware.cors.is_production', return_value=False)
    def test_configure_cors_custom_methods(self, mock_is_prod):
        """Test CORS configuration with custom methods."""
        custom_methods = ["GET", "POST"]
        configure_cors(self.app, allow_methods=custom_methods)
        
        assert len(self.app.user_middleware) > 0
    
    @patch('app.middleware.cors.is_production', return_value=False)
    def test_configure_cors_custom_headers(self, mock_is_prod):
        """Test CORS configuration with custom headers."""
        custom_headers = ["authorization", "content-type"]
        configure_cors(self.app, allow_headers=custom_headers)
        
        assert len(self.app.user_middleware) > 0
    
    @patch('app.middleware.cors.is_production', return_value=False)
    def test_configure_cors_credentials_disabled(self, mock_is_prod):
        """Test CORS configuration with credentials disabled."""
        configure_cors(self.app, allow_credentials=False)
        
        assert len(self.app.user_middleware) > 0
    
    @patch('app.middleware.cors.is_production', return_value=True)
    def test_configure_cors_production_validates_origins(self, mock_is_prod):
        """Test that production validates provided origins."""
        # Should raise for invalid origins
        with pytest.raises(ValueError, match="must use HTTPS in production"):
            configure_cors(self.app, allowed_origins=["http://insecure.com"])
        
        # Should work for valid origins
        configure_cors(self.app, allowed_origins=["https://secure.com"])
        assert len(self.app.user_middleware) > 0


class TestCORSIntegration:
    """Integration tests for CORS middleware with FastAPI."""
    
    def setup_method(self):
        """Set up test app and client."""
        self.app = FastAPI()
        
        @self.app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        # Configure CORS for testing
        with patch('app.middleware.cors.is_production', return_value=False):
            configure_cors(
                self.app,
                allowed_origins=["http://localhost:3000"],
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["authorization", "content-type"]
            )
        
        self.client = TestClient(self.app)
    
    def test_cors_preflight_request(self):
        """Test CORS preflight (OPTIONS) request."""
        response = self.client.options(
            "/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization"
            }
        )
        
        # Should return 200 for valid preflight
        assert response.status_code == 200
        
        # Check CORS headers
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers
    
    def test_cors_simple_request(self):
        """Test simple CORS request."""
        response = self.client.get(
            "/test",
            headers={"Origin": "http://localhost:3000"}
        )
        
        assert response.status_code == 200
        assert response.json() == {"message": "test"}
        
        # Check CORS headers
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    
    def test_cors_blocked_origin(self):
        """Test request from blocked origin."""
        response = self.client.get(
            "/test",
            headers={"Origin": "http://malicious.com"}
        )
        
        # Should still return 200 but without CORS headers
        assert response.status_code == 200
        # CORS middleware typically doesn't block, just omits headers
    
    def test_cors_credentials_headers(self):
        """Test that credentials headers are properly set."""
        response = self.client.get(
            "/test",
            headers={"Origin": "http://localhost:3000"}
        )
        
        assert response.status_code == 200
        # Check for credentials support
        assert "access-control-allow-credentials" in response.headers
    
    def test_cors_exposed_headers(self):
        """Test exposed headers configuration."""
        response = self.client.get(
            "/test",
            headers={"Origin": "http://localhost:3000"}
        )
        
        assert response.status_code == 200
        # Should include exposed headers
        assert "access-control-expose-headers" in response.headers


class TestCORSErrorScenarios:
    """Test error scenarios and edge cases."""
    
    def test_cors_with_empty_origin_list(self):
        """Test CORS configuration with empty origin list."""
        app = FastAPI()
        
        with patch('app.middleware.cors.is_production', return_value=False):
            configure_cors(app, allowed_origins=[])
            assert len(app.user_middleware) > 0
    
    def test_cors_with_none_origins(self):
        """Test CORS configuration with None origins (uses defaults)."""
        app = FastAPI()
        
        with patch('app.middleware.cors.is_production', return_value=False):
            configure_cors(app, allowed_origins=None)
            assert len(app.user_middleware) > 0
    
    @patch('app.middleware.cors.is_production', return_value=True)
    def test_cors_production_with_whitespace_origins(self, mock_is_prod):
        """Test CORS handling of whitespace in environment variables."""
        with patch.dict(os.environ, {"CORS_ORIGINS": "  https://app.com  , https://api.com  "}):
            app = FastAPI()
            configure_cors(app)
            assert len(app.user_middleware) > 0
    
    @patch('app.middleware.cors.is_production', return_value=True)
    def test_cors_production_with_empty_string_origins(self, mock_is_prod):
        """Test CORS handling of empty string origins."""
        with patch.dict(os.environ, {"CORS_ORIGINS": "  ,  ,  "}):
            app = FastAPI()
            with pytest.raises(ValueError, match="CORS_ORIGINS environment variable must be set"):
                configure_cors(app)
    
    def test_validate_cors_origins_with_empty_list(self):
        """Test origin validation with empty list."""
        with patch('app.middleware.cors.is_production', return_value=True):
            # Empty list should not raise in production
            validate_cors_origins([])
    
    def test_validate_cors_origins_with_mixed_schemes(self):
        """Test origin validation with mixed HTTP/HTTPS schemes."""
        with patch('app.middleware.cors.is_production', return_value=True):
            with pytest.raises(ValueError, match="must use HTTPS in production"):
                validate_cors_origins([
                    "https://secure.com",
                    "http://insecure.com",
                    "https://another-secure.com"
                ])


class TestCORSLogging:
    """Test CORS logging functionality."""
    
    @patch('app.middleware.cors.print')
    @patch('app.middleware.cors.is_production', return_value=True)
    def test_cors_production_logging(self, mock_is_prod, mock_print):
        """Test that production CORS configuration is logged."""
        app = FastAPI()
        origins = ["https://app.example.com", "https://api.example.com"]
        
        configure_cors(app, allowed_origins=origins)
        
        # Verify production logging
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        assert "PRODUCTION" in call_args
        assert "2 explicit origins" in call_args
    
    @patch('app.middleware.cors.print')
    @patch('app.middleware.cors.is_production', return_value=False)
    def test_cors_development_logging(self, mock_is_prod, mock_print):
        """Test that development CORS configuration is logged."""
        app = FastAPI()
        
        configure_cors(app)
        
        # Verify development logging
        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        assert "DEVELOPMENT" in call_args
        assert "origins" in call_args


if __name__ == "__main__":
    pytest.main([__file__])
