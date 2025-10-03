"""API decorators for common functionality across endpoints.

This module provides decorators for handling common API patterns like service
exception handling, validation, response formatting and response caching.
"""
import json
import hashlib
import logging
from functools import wraps
from typing import Callable, Any, Dict, Optional

import redis.asyncio as aioredis
from fastapi import HTTPException, status

from app.config import settings
from app.exceptions import (
    NotFoundError,
    ValidationError,
    ConflictError,
    AuthenticationError,
    AuthorizationError,
    ExternalServiceError,
    DatabaseError
)

logger = logging.getLogger(__name__)


redis_client: Optional[aioredis.Redis] = None


async def get_redis_client() -> Optional[aioredis.Redis]:
    """Get or create a Redis client instance.

    Returns ``None`` if Redis is not available so that the decorator can
    gracefully degrade and simply execute the wrapped function.
    """
    global redis_client
    if redis_client is not None:
        return redis_client

    try:
        client = aioredis.from_url(settings.REDIS_URL)
        # Confirm connection works
        await client.ping()
        redis_client = client
    except Exception as e:  # pragma: no cover - connection errors
        logger.warning(f"Redis not available for caching: {e}")
        redis_client = None
    return redis_client


def handle_service_exceptions(func: Callable) -> Callable:
    """
    Decorator to handle service layer exceptions and convert them to HTTP exceptions.
    
    This decorator catches common service exceptions and converts them to
    appropriate HTTP responses with consistent error formatting.
    
    Args:
        func: The function to decorate
        
    Returns:
        Decorated function with exception handling
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except NotFoundError as e:
            logger.warning(f"Resource not found: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "resource_not_found",
                    "message": e.message,
                    "details": e.details
                }
            )
        except ValidationError as e:
            logger.warning(f"Validation error: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation_error",
                    "message": e.message,
                    "details": e.details
                }
            )
        except ConflictError as e:
            logger.warning(f"Conflict error: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "conflict_error",
                    "message": e.message,
                    "details": e.details
                }
            )
        except AuthenticationError as e:
            logger.warning(f"Authentication error: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "authentication_error",
                    "message": e.message,
                    "details": e.details
                }
            )
        except AuthorizationError as e:
            logger.warning(f"Authorization error: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "authorization_error",
                    "message": e.message,
                    "details": e.details
                }
            )
        except ExternalServiceError as e:
            logger.error(f"External service error: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "error": "external_service_error",
                    "message": "External service temporarily unavailable",
                    "details": {"service_error": e.message}
                }
            )
        except DatabaseError as e:
            logger.error(f"Database error: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "database_error",
                    "message": "Database operation failed",
                    "details": {}  # Don't expose internal database errors
                }
            )
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "internal_server_error",
                    "message": "An unexpected error occurred",
                    "details": {}
                }
            )
    
    return wrapper


def validate_pagination(max_limit: int = 200) -> Callable:
    """
    Decorator to validate pagination parameters.
    
    Args:
        max_limit: Maximum allowed limit value
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract pagination parameters from kwargs
            skip = kwargs.get('skip', 0)
            limit = kwargs.get('limit', 100)
            
            if skip < 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "invalid_pagination",
                        "message": "Skip parameter must be non-negative",
                        "details": {"skip": skip}
                    }
                )
            
            if limit <= 0 or limit > max_limit:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error": "invalid_pagination",
                        "message": f"Limit must be between 1 and {max_limit}",
                        "details": {"limit": limit, "max_limit": max_limit}
                    }
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_permissions(*required_permissions: str) -> Callable:
    """
    Decorator to require specific permissions for endpoint access.
    
    Args:
        required_permissions: List of required permission strings
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract current_user from kwargs (injected by FastAPI dependency)
            current_user = kwargs.get('current_user')
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error": "authentication_required",
                        "message": "Authentication required for this endpoint"
                    }
                )
            
            # Check if user has required permissions
            user_permissions = getattr(current_user, 'permissions', [])
            user_role = getattr(current_user, 'role', None)
            
            # Admin users have all permissions
            if user_role == 'admin':
                return await func(*args, **kwargs)
            
            # Check specific permissions
            for permission in required_permissions:
                if permission not in user_permissions:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "error": "insufficient_permissions",
                            "message": f"Permission '{permission}' required",
                            "details": {
                                "required_permissions": list(required_permissions),
                                "user_permissions": user_permissions
                            }
                        }
                    )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def log_api_call(include_response: bool = False) -> Callable:
    """
    Decorator to log API calls for monitoring and debugging.
    
    Args:
        include_response: Whether to include response data in logs
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Log the API call
            logger.info(f"API call: {func.__name__} with args: {args}, kwargs: {kwargs}")
            
            try:
                result = await func(*args, **kwargs)
                
                if include_response:
                    logger.info(f"API response for {func.__name__}: {result}")
                else:
                    logger.info(f"API call {func.__name__} completed successfully")
                
                return result
                
            except Exception as e:
                logger.error(f"API call {func.__name__} failed: {e}")
                raise
        
        return wrapper
    return decorator


def cache_response(ttl_seconds: int = 300) -> Callable:
    """Decorator to cache API responses in Redis.

    A cache key is generated from the wrapped function's module, name and
    parameters. Responses are serialized as JSON and stored in Redis with the
    provided ``ttl_seconds``. If Redis is unavailable the function executes
    normally without caching.

    Args:
        ttl_seconds: Time to live for cached responses

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key_data = {
                "func": f"{func.__module__}.{func.__qualname__}",
                "args": args,
                "kwargs": kwargs,
            }
            raw_key = json.dumps(cache_key_data, sort_keys=True, default=str)
            cache_key = f"cache:{hashlib.md5(raw_key.encode()).hexdigest()}"

            client = await get_redis_client()
            if client:
                try:
                    cached = await client.get(cache_key)
                    if cached:
                        return json.loads(cached)
                except Exception as e:  # pragma: no cover - redis failure
                    logger.warning(f"Redis cache retrieval error: {e}")

            result = await func(*args, **kwargs)

            if client:
                try:
                    await client.setex(cache_key, ttl_seconds, json.dumps(result, default=str))
                except Exception as e:  # pragma: no cover - redis failure
                    logger.warning(f"Redis cache store error: {e}")

            return result

        return wrapper

    return decorator
