"""
Rate limiting utility - DISABLED per admin request.

This module now provides a no-op limiter that doesn't actually limit anything.
All rate limiting has been disabled to resolve admin operation issues.
"""
from typing import Callable, Any
from fastapi import Request
from functools import wraps

from app.utils.logging import get_logger

logger = get_logger(__name__)


class NoOpLimiter:
    """
    No-operation rate limiter that doesn't actually limit anything.
    
    This class provides the same interface as slowapi.Limiter but
    doesn't perform any rate limiting. All decorators become no-ops.
    """
    
    def limit(self, rate_limit: str):
        """
        Decorator that does nothing - rate limiting disabled.
        
        Args:
            rate_limit: Rate limit string (ignored)
            
        Returns:
            Decorator that passes through the function unchanged
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    def __call__(self, *args, **kwargs):
        """Make the limiter callable for compatibility."""
        return self.limit(*args, **kwargs)


# Create the disabled limiter instance
limiter = NoOpLimiter()

logger.info("⚠️  Rate limiting DISABLED - using no-op limiter")


def rate_limit_handler(request: Request, exc: Exception):
    """
    No-op rate limit exception handler for compatibility.
    
    Since rate limiting is disabled, this should never be called,
    but it's here for compatibility with the application factory.
    
    Args:
        request: FastAPI request
        exc: Exception (ignored)
        
    Returns:
        None (rate limiting disabled)
    """
    pass


def get_rate_limit(limit_type: str) -> str:
    """
    Get rate limit string for a specific endpoint type.
    
    NOTE: Rate limiting is disabled, this is for compatibility only.
    
    Args:
        limit_type: Type of endpoint (ignored)
        
    Returns:
        Empty string (rate limiting disabled)
    """
    return ""  # No rate limiting
