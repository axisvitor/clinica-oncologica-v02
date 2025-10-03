"""
SECURITY-HARDENED FastAPI dependency injection with session-per-request pattern.

CRITICAL SECURITY FIXES:
1. Session-per-request pattern - NO shared database sessions
2. Proper session cleanup guarantees
3. Thread safety for multi-worker deployment
4. HIPAA compliance for patient data isolation
"""
from fastapi import Depends, HTTPException, status, Path, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, Union
from jose import jwt, JWTError
from datetime import datetime
from uuid import UUID
import logging

from app.database import get_db, get_supabase
from app.config import settings
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.repositories.user import UserRepository
import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Security scheme for JWT authentication
security = HTTPBearer()


class SecureServiceProvider:
    """
    SECURITY-HARDENED Service Provider - NO session sharing, request-scoped only.
    
    Key Security Features:
    - Fresh database session per request (prevents patient data mixing)
    - Automatic session cleanup via context managers
    - Thread-safe service instantiation
    - HIPAA-compliant data isolation
    """
    
    def __init__(self, db: Session, redis_client):
        # Store session reference for cleanup
        self._db = db
        self.redis_client = redis_client
        
        # Initialize repositories with isolated session
        self._user_repository = None
        self._patient_repository = None
        self._services_cache = {}
        
        logger.debug(f"SecureServiceProvider initialized with session: {id(self._db)}")

    @property
    def db(self) -> Session:
        """Get isolated database session for this request."""
        return self._db
    
    @property
    def user_repository(self) -> UserRepository:
        """Get user repository with isolated session."""
        if self._user_repository is None:
            self._user_repository = UserRepository(self._db)
        return self._user_repository

    @property
    def patient_repository(self):
        """Get patient repository with isolated session."""
        if 'patient_repository' not in self._services_cache:
            from app.repositories.patient import PatientRepository
            self._services_cache['patient_repository'] = PatientRepository(self._db)
        return self._services_cache['patient_repository']

    @property
    def auth_service(self):
        """Get auth service with isolated session."""
        if 'auth_service' not in self._services_cache:
            from app.services.auth import AuthService
            # AuthService expects async redis client, pass raw client or None
            self._services_cache['auth_service'] = AuthService(
                db=self._db,
                user_repository=self.user_repository,
                redis_client=self.redis_client
            )
        return self._services_cache['auth_service']


async def get_secure_service_provider(db: Session = Depends(get_db)) -> SecureServiceProvider:
    """
    SECURITY-CRITICAL: Get service provider with ISOLATED database session.

    This dependency ensures:
    1. Each request gets a FRESH database session
    2. No session sharing between concurrent requests
    3. Automatic session cleanup when request completes
    4. HIPAA-compliant patient data isolation
    """
    # Get async Redis client from unified module
    try:
        from app.core.redis_unified import get_async_redis
        redis_client = await get_async_redis()
    except Exception as e:
        logger.warning(f"Could not get Redis client: {e}")
        redis_client = None

    logger.debug(f"Creating SecureServiceProvider with fresh session: {id(db)}")
    return SecureServiceProvider(db=db, redis_client=redis_client)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    services: SecureServiceProvider = Depends(get_secure_service_provider)
) -> User:
    """
    Get current authenticated user from JWT token with ISOLATED session.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_data = services.auth_service.verify_token(credentials.credentials, token_type="access")
    
    if token_data is None:
        raise credentials_exception
    
    user = services.auth_service._get_user_from_token_data(token_data)
    
    if user is None:
        raise credentials_exception
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user"
        )
    
    return user
