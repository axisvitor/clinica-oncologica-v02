"""
Fallback Dependencies for Production Stability.

This module provides simplified, reliable dependency injection that can be used
when the main complex dependency system fails. Designed to ensure the login
endpoint always works, even when advanced features are unavailable.
"""

import logging
from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

# Import our simplified systems
from app.core.database_direct import get_direct_session, test_direct_connection, initialize_direct_database
from app.core.redis_unified import get_sync_redis
from app.services_simple import SimplifiedServiceProvider, get_simple_service_provider
from app.models.user import User

logger = logging.getLogger(__name__)

# Security scheme for JWT authentication
security = HTTPBearer()


def get_fallback_db() -> Generator[Session, None, None]:
    """
    Get database session using fallback direct connection.

    This is a simplified database dependency that avoids complex session
    management and should work when the main system fails.

    Yields:
        Session: Direct database session

    Raises:
        HTTPException: If database connection fails completely
    """
    try:
        with get_direct_session() as db:
            yield db

    except Exception as e:
        logger.error(f"Fallback database connection failed: {e}")

        # Try to initialize direct database if not done
        try:
            if initialize_direct_database():
                with get_direct_session() as db:
                    yield db
                    return
        except Exception as init_error:
            logger.error(f"Failed to initialize direct database: {init_error}")

        # If all fails, raise HTTP exception
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service temporarily unavailable"
        )


def get_fallback_service_provider(
    db: Session = Depends(get_fallback_db)
) -> Generator[SimplifiedServiceProvider, None, None]:
    """
    Get simplified service provider using fallback systems.

    This dependency provides a basic service provider that should work
    even when the complex session management system fails.

    Args:
        db: Database session from fallback system

    Yields:
        SimplifiedServiceProvider: Simplified service provider

    Raises:
        HTTPException: If service provider creation fails
    """
    try:
        # Initialize simple Redis if needed
        redis_client = get_sync_redis()
        if redis_client is None:
            logger.info("Attempting to initialize simple Redis client")
            try:
                redis_client = get_sync_redis()
            except Exception as redis_error:
                logger.warning(f"Redis initialization failed: {redis_error} - continuing without Redis")

        # Create simplified service provider
        provider = SimplifiedServiceProvider(db, redis_client)

        if not provider.is_initialized:
            raise RuntimeError("Service provider failed to initialize")

        logger.info("Fallback service provider created successfully")
        yield provider

    except Exception as e:
        logger.error(f"Fallback service provider creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication service unavailable: {type(e).__name__}"
        )


async def get_fallback_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    services: SimplifiedServiceProvider = Depends(get_fallback_service_provider)
) -> User:
    """
    Get current authenticated user using fallback systems.

    This is a simplified version of user authentication that should work
    when the complex dependency system fails.

    Args:
        credentials: JWT credentials from Authorization header
        services: Simplified service provider

    Returns:
        User: Authenticated user

    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Validate service provider
        services.validate_session()

        # Verify token using simplified auth service
        token_data = services.auth_service.verify_token(
            credentials.credentials,
            token_type="access"
        )

        if token_data is None:
            logger.warning("Token verification failed - invalid token")
            raise credentials_exception

        # Get user from token data
        user = services.auth_service._get_user_from_token_data(token_data)

        if user is None:
            logger.warning("User not found for valid token")
            raise credentials_exception

        if not user.is_active:
            logger.warning(f"Inactive user attempted login: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive user"
            )

        logger.info(f"User authenticated successfully via fallback: {user.email}")
        return user

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except RuntimeError as e:
        logger.error(f"Service validation failed in fallback auth: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service temporarily unavailable"
        )
    except Exception as e:
        logger.error(f"Unexpected error in fallback authentication: {e}")
        raise credentials_exception


async def get_fallback_current_active_user(
    current_user: User = Depends(get_fallback_current_user)
) -> User:
    """
    Get current active user using fallback system.

    Args:
        current_user: User from fallback authentication

    Returns:
        User: Active user

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def get_fallback_auth_service(
    services: SimplifiedServiceProvider = Depends(get_fallback_service_provider)
) -> 'AuthService':
    """
    Get auth service using fallback systems.

    Args:
        services: Simplified service provider

    Returns:
        AuthService: Authentication service

    Raises:
        HTTPException: If auth service unavailable
    """
    try:
        services.validate_session()
        return services.auth_service

    except Exception as e:
        logger.error(f"Failed to get fallback auth service: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service unavailable"
        )


def test_fallback_systems() -> dict:
    """
    Test all fallback systems and return status.

    Returns:
        dict: Status of all fallback systems
    """
    results = {
        "database": {"status": "unknown", "error": None},
        "redis": {"status": "unknown", "error": None},
        "service_provider": {"status": "unknown", "error": None}
    }

    # Test database
    try:
        db_status = test_direct_connection()
        results["database"] = db_status
    except Exception as e:
        results["database"] = {"status": "failed", "error": str(e)}

    # Test Redis
    try:
        redis_client = get_sync_redis()
        if redis_client:
            redis_status = redis_client.get_status()
            results["redis"] = {"status": "available" if redis_status["available"] else "unavailable", **redis_status}
        else:
            results["redis"] = {"status": "not_configured"}
    except Exception as e:
        results["redis"] = {"status": "failed", "error": str(e)}

    # Test service provider creation
    try:
        with get_fallback_db() as db:
            redis_client = get_sync_redis()
            provider = SimplifiedServiceProvider(db, redis_client)
            results["service_provider"] = {
                "status": "available" if provider.is_initialized else "failed",
                "initialized": provider.is_initialized
            }
    except Exception as e:
        results["service_provider"] = {"status": "failed", "error": str(e)}

    return results


def get_system_health() -> dict:
    """
    Get comprehensive health check of all systems.

    Returns:
        dict: Health status of primary and fallback systems
    """
    fallback_status = test_fallback_systems()

    # Test primary systems
    primary_status = {"status": "unknown", "error": None}
    try:
        from app.database import test_connection
        primary_db = test_connection()
        primary_status = {"status": "available", **primary_db}
    except Exception as e:
        primary_status = {"status": "failed", "error": str(e)}

    return {
        "primary_database": primary_status,
        "fallback_systems": fallback_status,
        "recommendation": "use_fallback" if primary_status["status"] != "healthy" else "use_primary"
    }