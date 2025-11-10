"""
Specialized middleware for public monthly quiz endpoints.

Provides enhanced security, monitoring, and CORS handling
specifically for public endpoints that don't require authentication.
"""
import time
import logging
from typing import Callable
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
from app.utils.security import generate_security_headers
from app.utils.logging import get_logger

logger = get_logger(__name__)


class PublicEndpointMiddleware(BaseHTTPMiddleware):
    """
    Middleware for public endpoints with enhanced security and monitoring.
    
    Features:
    - Enhanced security headers
    - Request/response logging
    - Performance monitoring
    - CORS preflight handling
    - Content type validation
    """
    
    def __init__(
        self,
        app,
        allowed_endpoints: list = None,
        enable_logging: bool = True
    ):
        super().__init__(app)
        self.allowed_endpoints = allowed_endpoints or [
            "/api/v2/quiz-extensions/monthly/public",
            "/api/v2/quiz-extensions/monthly/public/current",
        ]
        self.enable_logging = enable_logging
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through public endpoint middleware.
        """
        start_time = time.time()
        
        # Check if this is a public endpoint
        is_public_endpoint = any(
            request.url.path.startswith(endpoint) or request.url.path == endpoint
            for endpoint in self.allowed_endpoints
        )
        
        if not is_public_endpoint:
            # Not a public endpoint, pass through
            return await call_next(request)
        
        # Log public endpoint access
        if self.enable_logging:
            logger.info(
                f"Public endpoint access: {request.method} {request.url.path}",
                extra={
                    'event_type': 'public_endpoint_access',
                    'method': request.method,
                    'path': request.url.path,
                    'client_ip': self._extract_client_ip(request),
                    'user_agent': request.headers.get('user-agent', 'unknown'),
                    'referer': request.headers.get('referer', 'unknown'),
                    'origin': request.headers.get('origin', 'unknown')
                }
            )
        
        # Handle CORS preflight requests
        if request.method == "OPTIONS":
            return self._create_cors_preflight_response(request)
        
        # Validate content type for POST requests
        if request.method == "POST":
            content_type = request.headers.get("content-type", "")
            if not content_type.startswith("application/json"):
                logger.warning(
                    f"Invalid content type for public endpoint: {content_type}",
                    extra={'event_type': 'public_endpoint_invalid_content_type'}
                )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Add security headers
            security_headers = generate_security_headers()
            for header_name, header_value in security_headers.items():
                response.headers[header_name] = header_value
            
            # Add CORS headers
            self._add_cors_headers(response, request)
            
            # Add performance headers
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            
            # Log response
            if self.enable_logging:
                logger.info(
                    f"Public endpoint response: {response.status_code} in {process_time:.4f}s",
                    extra={
                        'event_type': 'public_endpoint_response',
                        'status_code': response.status_code,
                        'process_time': process_time,
                        'path': request.url.path
                    }
                )
            
            return response
            
        except Exception as e:
            # Log error
            process_time = time.time() - start_time
            logger.error(
                f"Public endpoint error: {str(e)} in {process_time:.4f}s",
                extra={
                    'event_type': 'public_endpoint_error',
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'process_time': process_time,
                    'path': request.url.path
                },
                exc_info=True
            )
            raise
    
    def _extract_client_ip(self, request: Request) -> str:
        """Extract client IP address."""
        # Check X-Forwarded-For header
        if "x-forwarded-for" in request.headers:
            return request.headers["x-forwarded-for"].split(",")[0].strip()
        
        # Check X-Real-IP header
        if "x-real-ip" in request.headers:
            return request.headers["x-real-ip"]
        
        # Fallback to client host
        return request.client.host if request.client else "unknown"
    
    def _create_cors_preflight_response(self, request: Request) -> Response:
        """Create CORS preflight response."""
        response = Response(status_code=200)
        self._add_cors_headers(response, request)
        return response
    
    def _add_cors_headers(self, response: Response, request: Request) -> None:
        """
        Add CORS headers to response.

        Note: This method is now a no-op as CORS is fully handled by CORSMiddleware.
        Keeping for backward compatibility but delegating to main CORS middleware.
        """
        # Delegate all CORS handling to CORSMiddleware - do not add duplicate headers
        # CORSMiddleware will properly handle origin validation, credentials, and all CORS headers
        pass


class PublicEndpointCORSMiddleware(BaseHTTPMiddleware):
    """
    Specialized CORS middleware for public monthly quiz endpoints.
    
    Provides more permissive CORS settings specifically for public endpoints
    while maintaining security for authenticated endpoints.
    """
    
    def __init__(
        self,
        app,
        public_endpoints: list = None,
        allowed_origins: list = None
    ):
        super().__init__(app)
        self.public_endpoints = public_endpoints or [
            "/api/v2/quiz-extensions/monthly/public"
        ]
        self.allowed_origins = allowed_origins or ["*"]
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Apply CORS handling based on endpoint type.
        """
        # Check if this is a public endpoint
        is_public = any(
            request.url.path.startswith(endpoint)
            for endpoint in self.public_endpoints
        )
        
        # Handle CORS preflight for public endpoints
        if is_public and request.method == "OPTIONS":
            return self._create_public_preflight_response(request)
        
        # Process request
        response = await call_next(request)
        
        # Add appropriate CORS headers
        if is_public:
            self._add_public_cors_headers(response, request)
        
        return response
    
    def _create_public_preflight_response(self, request: Request) -> Response:
        """Create permissive CORS preflight response for public endpoints."""
        response = Response(status_code=200)
        self._add_public_cors_headers(response, request)
        return response
    
    def _add_public_cors_headers(self, response: Response, request: Request) -> None:
        """
        Add permissive CORS headers for public endpoints.

        Note: This method is now a no-op as CORS is fully handled by CORSMiddleware.
        Keeping for backward compatibility but delegating to main CORS middleware.
        """
        # Log origin for monitoring only
        origin = request.headers.get("origin")
        if origin:
            logger.info(
                f"Public endpoint CORS request from origin: {origin}",
                extra={'event_type': 'public_cors_request', 'origin': origin}
            )

        # Delegate all CORS handling to CORSMiddleware - do not add duplicate headers
        # CORSMiddleware will properly handle origin validation, credentials, and all CORS headers
        pass
