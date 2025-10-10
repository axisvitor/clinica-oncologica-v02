"""
Custom CSRF Protection for Cross-Domain Production Environment

This module provides a simplified CSRF protection that works better
in Railway's cross-domain environment where frontend and backend
are on different subdomains.
"""

import hmac
import hashlib
import secrets
import time
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class CustomCSRFProtection:
    """
    Custom CSRF protection that works with cross-domain requests.
    
    Uses HMAC-SHA256 for token generation and validation.
    Validates tokens from X-CSRF-Token header only (no cookie dependency).
    """
    
    def __init__(self, secret_key: str, token_expiry: int = 3600):
        """
        Initialize CSRF protection.
        
        Args:
            secret_key: Secret key for HMAC signing
            token_expiry: Token expiration time in seconds (default: 1 hour)
        """
        self.secret_key = secret_key.encode('utf-8')
        self.token_expiry = token_expiry
    
    def generate_token(self) -> str:
        """
        Generate a new CSRF token.
        
        Token format: base64(timestamp:random_data:hmac_signature)
        
        Returns:
            str: CSRF token
        """
        timestamp = str(int(time.time()))
        random_data = secrets.token_hex(16)
        
        # Create payload
        payload = f"{timestamp}:{random_data}"
        
        # Create HMAC signature
        signature = hmac.new(
            self.secret_key,
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Combine payload and signature
        token = f"{payload}:{signature}"
        
        # Base64 encode for safe transport
        import base64
        return base64.b64encode(token.encode('utf-8')).decode('utf-8')
    
    def validate_token(self, token: str) -> bool:
        """
        Validate a CSRF token.
        
        Args:
            token: CSRF token to validate
            
        Returns:
            bool: True if token is valid, False otherwise
        """
        try:
            # Base64 decode
            import base64
            decoded = base64.b64decode(token.encode('utf-8')).decode('utf-8')
            
            # Split components
            parts = decoded.split(':')
            if len(parts) != 3:
                logger.warning("CSRF token has invalid format")
                return False
            
            timestamp_str, random_data, provided_signature = parts
            
            # Check expiration
            timestamp = int(timestamp_str)
            current_time = int(time.time())
            
            if current_time - timestamp > self.token_expiry:
                logger.warning("CSRF token has expired")
                return False
            
            # Recreate payload and verify signature
            payload = f"{timestamp_str}:{random_data}"
            expected_signature = hmac.new(
                self.secret_key,
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Constant-time comparison
            if not hmac.compare_digest(expected_signature, provided_signature):
                logger.warning("CSRF token signature is invalid")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"CSRF token validation error: {e}")
            return False
    
    def get_token_from_request(self, request: Request) -> Optional[str]:
        """
        Extract CSRF token from request headers.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Optional[str]: CSRF token if found, None otherwise
        """
        # Check X-CSRF-Token header
        token = request.headers.get("X-CSRF-Token")
        if token:
            return token
        
        # Check alternative header names
        token = request.headers.get("X-CSRFToken")
        if token:
            return token
        
        return None
    
    def validate_request(self, request: Request) -> bool:
        """
        Validate CSRF token from request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            bool: True if valid, False otherwise
        """
        token = self.get_token_from_request(request)
        if not token:
            logger.warning(f"CSRF token missing for {request.url.path}")
            return False
        
        return self.validate_token(token)


# Global instance
_csrf_protection: Optional[CustomCSRFProtection] = None


def get_custom_csrf_protection() -> CustomCSRFProtection:
    """
    Get or create the global CSRF protection instance.
    
    Returns:
        CustomCSRFProtection: CSRF protection instance
    """
    global _csrf_protection
    
    if _csrf_protection is None:
        from app.config import settings
        
        if not settings.CSRF_SECRET_KEY:
            raise ValueError("CSRF_SECRET_KEY is required")
        
        _csrf_protection = CustomCSRFProtection(
            secret_key=settings.CSRF_SECRET_KEY,
            token_expiry=3600  # 1 hour
        )
        
        logger.info("Custom CSRF protection initialized")
    
    return _csrf_protection


async def validate_custom_csrf(request: Request):
    """
    FastAPI dependency for CSRF validation.
    
    Args:
        request: FastAPI request object
        
    Raises:
        HTTPException: If CSRF validation fails
    """
    csrf = get_custom_csrf_protection()
    
    if not csrf.validate_request(request):
        logger.warning(
            f"Custom CSRF validation failed for {request.url.path}",
            extra={
                "client_ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", "unknown"),
                "has_csrf_header": bool(csrf.get_token_from_request(request))
            }
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "csrf_validation_failed",
                "message": "CSRF token validation failed. Please refresh and try again.",
                "timestamp": time.time()
            }
        )
    
    logger.debug(f"Custom CSRF validation successful for {request.url.path}")


def create_csrf_token_response() -> JSONResponse:
    """
    Create a JSON response with a new CSRF token.
    
    Returns:
        JSONResponse: Response with CSRF token
    """
    csrf = get_custom_csrf_protection()
    token = csrf.generate_token()
    
    return JSONResponse(content={
        "csrf_token": token,
        "expires_in": 3600,
        "usage": "Include this token in X-CSRF-Token header for POST/PUT/DELETE requests"
    })