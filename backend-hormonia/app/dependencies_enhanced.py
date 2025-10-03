"""
Enhanced dependencies with automatic fallback for production stability.
This module provides robust dependency injection that gracefully handles failures.
"""
import logging
import os
from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Import the original dependencies as fallback
try:
    from app.dependencies import (
        get_thread_safe_db as _original_get_db,
        get_thread_safe_service_provider as _original_get_service_provider,
        get_current_user as _original_get_current_user,
        get_auth_service as _original_get_auth_service
    )
    ORIGINAL_DEPS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Original dependencies not available: {e}")
    ORIGINAL_DEPS_AVAILABLE = False

# Simple fallback implementations
_fallback_engine = None
_fallback_SessionLocal = None

def get_fallback_database_url():
    """Get database URL with proper encoding."""
    # Get from environment
    database_url = os.getenv("DATABASE_URL", "")

    if not database_url:
        # Try loading from .env file
        from dotenv import load_dotenv
        load_dotenv()
        database_url = os.getenv("DATABASE_URL", "")

    # Fix special character encoding if needed
    if "!Clinicaoncologica1" in database_url:
        database_url = database_url.replace("!Clinicaoncologica1", "%21Clinicaoncologica1")
        logger.info("Fixed database URL encoding for special characters")

    # Ensure postgresql:// not postgres://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        logger.info("Fixed database URL protocol from postgres:// to postgresql://")

    logger.debug(f"Final database URL starts with: {database_url[:30]}...")
    return database_url

def get_fallback_db() -> Generator[Session, None, None]:
    """Fallback database connection when thread-safe fails."""
    global _fallback_engine, _fallback_SessionLocal

    if not _fallback_SessionLocal:
        database_url = get_fallback_database_url()
        if not database_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database configuration not available"
            )

        _fallback_engine = create_engine(
            database_url,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True
        )
        _fallback_SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=_fallback_engine
        )

    db = _fallback_SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_enhanced_db() -> Generator[Session, None, None]:
    """Enhanced database dependency with automatic fallback."""
    if ORIGINAL_DEPS_AVAILABLE:
        try:
            # Try original thread-safe version first
            for db in _original_get_db():
                yield db
                return
        except Exception as e:
            logger.warning(f"Thread-safe DB failed, using fallback: {e}")

    # Use fallback
    logger.info("Using fallback database connection")
    for db in get_fallback_db():
        yield db

def get_simple_service_provider(db: Session):
    """Create a simple ServiceProvider without complex thread management."""
    try:
        from app.services.container import ServiceContainer
        from app.core.redis_unified import get_sync_redis

        # Create simplified provider
        redis_client = None
        try:
            # Try to get Redis but don't fail if unavailable
            redis_client = get_sync_redis()
        except Exception as e:
            logger.warning(f"Redis not available, continuing without it: {e}")

        # Use ServiceContainer instead of ServiceProvider for better dependency management
        provider = ServiceContainer(db, redis_client)
        return provider

    except Exception as e:
        logger.error(f"Failed to create simple ServiceContainer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Service initialization failed"
        )

def get_enhanced_service_provider() -> Generator:
    """Enhanced ServiceProvider with automatic fallback."""
    if ORIGINAL_DEPS_AVAILABLE:
        try:
            # Try original thread-safe version
            for provider in _original_get_service_provider():
                yield provider
                return
        except Exception as e:
            logger.warning(f"Thread-safe ServiceProvider failed: {e}")

    # Use simple fallback
    logger.info("Using fallback ServiceProvider")
    for db in get_enhanced_db():
        provider = get_simple_service_provider(db)
        try:
            yield provider
        finally:
            # Cleanup if needed
            pass

def get_enhanced_auth_service():
    """Enhanced auth service dependency."""
    for provider in get_enhanced_service_provider():
        try:
            return provider.get_auth_service()
        except AttributeError:
            # If get_auth_service doesn't exist, create AuthService directly
            from app.services.auth import AuthService
            from app.repositories.user import UserRepository

            # Create UserRepository with the database session
            user_repo = UserRepository(provider.db)
            auth_service = AuthService(
                db=provider.db,
                user_repository=user_repo,
                redis_client=getattr(provider, 'redis', None)
            )
            return auth_service

security = HTTPBearer()

async def get_enhanced_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service = Depends(get_enhanced_auth_service)
):
    """Enhanced current user dependency that returns the authenticated User object."""
    from app.models.user import User

    try:
        token = credentials.credentials
        token_data = auth_service.verify_token(token, token_type="access")

        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user: Optional[User] = auth_service._get_user_from_token_data(token_data)
        if not user or not getattr(user, 'is_active', True):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Export enhanced versions
__all__ = [
    'get_enhanced_db',
    'get_enhanced_service_provider',
    'get_enhanced_auth_service',
    'get_enhanced_current_user'
]