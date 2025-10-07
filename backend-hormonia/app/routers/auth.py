"""
Authentication Router with Session Management

Provides endpoints for Firebase authentication, session management,
and user authentication flow with Redis-based session storage.
"""

from datetime import datetime, timedelta
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.redis_manager import FirebaseRedisCache
from app.dependencies.auth_dependencies import (
    get_current_user_from_session,
    get_redis_cache,
    verify_firebase_token
)
from app.models.user import User
from app.core.config import settings


router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


# ============================================================================
# Request/Response Models
# ============================================================================

class SessionCreate(BaseModel):
    """Request model for creating a new session"""
    id_token: str = Field(..., description="Firebase ID token")


class SessionResponse(BaseModel):
    """Response model for session creation"""
    session_id: str = Field(..., description="Unique session identifier")
    user: dict = Field(..., description="User information")
    expires_in: int = Field(..., description="Session expiration time in seconds")


class LogoutResponse(BaseModel):
    """Response model for logout"""
    message: str


class LogoutAllResponse(BaseModel):
    """Response model for logout all sessions"""
    message: str
    sessions_deleted: int


class SessionStatusResponse(BaseModel):
    """Response model for session status check"""
    valid: bool
    expires_in: Optional[int] = None
    last_activity: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/session", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: SessionCreate,
    db: Session = Depends(get_db),
    redis_cache: FirebaseRedisCache = Depends(get_redis_cache)
):
    """
    Create a new session from Firebase ID token.

    Workflow:
    1. Validate Firebase token (with Layer 1 cache)
    2. Get/create user in PostgreSQL (with Layer 2 cache)
    3. Create Redis session (Layer 3)
    4. Generate and return session_id

    Args:
        session_data: Contains Firebase ID token
        db: Database session
        redis_cache: Redis cache instance (injected)

    Returns:
        Session information including session_id and user data

    Raises:
        HTTPException 401: Invalid or expired token
        HTTPException 403: User account is inactive
        HTTPException 500: Internal server error
    """
    try:

        # Step 1: Validate Firebase token (uses Layer 1 cache)
        firebase_user = await verify_firebase_token(session_data.id_token)
        if not firebase_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired Firebase token"
            )

        firebase_uid = firebase_user.get("uid")
        email = firebase_user.get("email")

        # Step 2: Get/create user in PostgreSQL (uses Layer 2 cache)
        user = await redis_cache.get_or_create_user(
            db=db,
            firebase_uid=firebase_uid,
            email=email,
            display_name=firebase_user.get("name"),
            photo_url=firebase_user.get("picture")
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create or retrieve user"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )

        # Step 3: Create Redis session (Layer 3)
        session_id = str(uuid.uuid4())
        session_ttl = settings.SESSION_TTL_SECONDS  # Default: 86400 (24 hours)

        session_created = await redis_cache.create_session(
            session_id=session_id,
            firebase_uid=firebase_uid,
            user_id=user.id,
            ttl=session_ttl
        )

        if not session_created:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create session"
            )

        # Step 4: Return session information
        user_data = {
            "id": user.id,
            "firebase_uid": user.firebase_uid,
            "email": user.email,
            "display_name": user.display_name,
            "photo_url": user.photo_url,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": user.last_login.isoformat() if user.last_login else None
        }

        return SessionResponse(
            session_id=session_id,
            user=user_data,
            expires_in=session_ttl
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Session creation failed: {str(e)}"
        )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    x_session_id: str = Header(..., description="Session ID to invalidate"),
    redis_cache: FirebaseRedisCache = Depends(get_redis_cache)
):
    """
    Logout and invalidate current session.

    Args:
        x_session_id: Session ID from request header
        redis_cache: Redis cache instance (injected)

    Returns:
        Success message

    Raises:
        HTTPException 401: Invalid session
        HTTPException 500: Internal server error
    """
    try:

        # Invalidate session in Redis
        success = await redis_cache.invalidate_session(x_session_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session not found or already expired"
            )

        return LogoutResponse(message="Logout successful")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}"
        )


@router.post("/logout-all", response_model=LogoutAllResponse)
async def logout_all(
    current_user: User = Depends(get_current_user_from_session),
    redis_cache: FirebaseRedisCache = Depends(get_redis_cache)
):
    """
    Logout from all sessions for current user.

    Invalidates all active sessions associated with the user's Firebase UID.

    Args:
        current_user: Current authenticated user
        redis_cache: Redis cache instance (injected)

    Returns:
        Success message with count of deleted sessions

    Raises:
        HTTPException 500: Internal server error
    """
    try:

        # Invalidate all sessions for this user's firebase_uid
        deleted_count = await redis_cache.invalidate_all_user_sessions(
            current_user.firebase_uid
        )

        return LogoutAllResponse(
            message=f"Successfully logged out from all devices",
            sessions_deleted=deleted_count
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout all failed: {str(e)}"
        )


@router.get("/me")
async def get_current_user(
    current_user: User = Depends(get_current_user_from_session)
):
    """
    Get current authenticated user information.

    Args:
        current_user: Current user from session

    Returns:
        User information
    """
    return {
        "id": current_user.id,
        "firebase_uid": current_user.firebase_uid,
        "email": current_user.email,
        "display_name": current_user.display_name,
        "photo_url": current_user.photo_url,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None
    }


@router.get("/session/status", response_model=SessionStatusResponse)
async def get_session_status(
    x_session_id: str = Header(..., description="Session ID to check"),
    redis_cache: FirebaseRedisCache = Depends(get_redis_cache)
):
    """
    Check session status and validity.

    Args:
        x_session_id: Session ID from request header
        redis_cache: Redis cache instance (injected)

    Returns:
        Session status information including validity and expiration

    Raises:
        HTTPException 401: Invalid or expired session
        HTTPException 500: Internal server error
    """
    try:

        # Get session data from Redis
        session_data = await redis_cache.get_session(x_session_id)

        if not session_data:
            return SessionStatusResponse(
                valid=False,
                expires_in=None,
                last_activity=None
            )

        # Get TTL for session
        ttl = await redis_cache.get_session_ttl(x_session_id)

        return SessionStatusResponse(
            valid=True,
            expires_in=ttl if ttl > 0 else 0,
            last_activity=session_data.get("last_activity")
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Session status check failed: {str(e)}"
        )


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health")
async def health_check():
    """
    Authentication service health check.

    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "service": "authentication",
        "timestamp": datetime.utcnow().isoformat()
    }
