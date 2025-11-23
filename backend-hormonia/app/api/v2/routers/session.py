"""
Session Router - Backward Compatibility Wrapper for Auth Endpoints

This router provides compatibility for frontend code that expects session-based
endpoints at /api/v2/session/* instead of /api/v2/auth/*.

**Compatibility Endpoints:**
- POST /session/login -> /auth/firebase/verify
- POST /session/verify -> /auth/verify-session
- GET /session/user -> /auth/me (from users router)

**Migration Notice:**
This router will be deprecated once frontend is updated to use /auth endpoints directly.
All authentication logic is delegated to the auth and users routers.
"""

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
# from sqlalchemy.orm import Session,

from app.database import get_db
from app.dependencies.auth_dependencies import (
    get_current_user_from_session,
    get_redis_cache,
    verify_firebase_token as verify_token
)
from app.utils.rate_limiter import limiter
from app.schemas.v2.auth import (
    FirebaseTokenVerifyRequest,
    FirebaseTokenVerifyResponse,
    SessionV2Response,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _serialize_session(session, current_session_id: Optional[str] = None) -> dict:
    """Serialize Session model to API-friendly dict."""
    return {
        "session_id": str(session.id),
        "user_id": str(session.user_id),
        "created_at": session.created_at,
        "expires_at": session.expires_at,
        "ip_address": session.ip_address,
        "user_agent": session.user_agent,
        "is_current": str(session.id) == current_session_id if current_session_id else False,
    }


def _extract_user_id(current_user) -> str:
    """Extract user ID from user object or dict."""
    if isinstance(current_user, dict):
        return current_user.get("id")
    return str(getattr(current_user, "id", None))


# ============================================================================
# Compatibility Endpoint: POST /session/login -> /auth/firebase/verify
# ============================================================================

@router.post(
    "/login",
    response_model=FirebaseTokenVerifyResponse,
    summary="Login via Firebase (Compatibility Alias)",
    description="""
    **DEPRECATED**: Legacy endpoint for Firebase authentication.
    
    This endpoint provides backward compatibility for frontend applications
    that call `/api/v2/session/login` instead of `/api/v2/auth/firebase/verify`.
    
    **Recommended**: Update your frontend to use `/api/v2/auth/firebase/verify` instead.
    
    This alias will be removed in a future version.
    """,
    tags=["session-v2", "auth-v2", "deprecated"],
    deprecated=True
)
@limiter.limit("60/minute")
async def session_login_compat(
    request: Request,
    payload: FirebaseTokenVerifyRequest,
    db = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
):
    """
    Backward compatibility alias for Firebase login endpoint.
    
    Delegates to /auth/firebase/verify logic.
    """
    logger.warning(
        "Session login accessed via deprecated compatibility endpoint /api/v2/session/login",
        extra={
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
            "migration_note": "Frontend should be updated to use /api/v2/auth/firebase/verify"
        }
    )
    
    # Import auth router logic to avoid code duplication
    from app.api.v2.routers.auth import verify_firebase_token
    return await verify_firebase_token(request, payload, db, redis_cache)


# ============================================================================
# Compatibility Endpoint: POST /session/verify -> /auth/verify-session
# ============================================================================

@router.post(
    "/verify",
    response_model=SessionV2Response,
    summary="Verify session (Compatibility Alias)",
    description="""
    **DEPRECATED**: Legacy endpoint for session verification.
    
    This endpoint provides backward compatibility for frontend applications
    that call `/api/v2/session/verify` instead of `/api/v2/auth/verify-session`.
    
    **Recommended**: Update your frontend to use `/api/v2/auth/verify-session` instead.
    
    This alias will be removed in a future version.
    """,
    tags=["session-v2", "auth-v2", "deprecated"],
    deprecated=True
)
@limiter.limit("100/minute")
async def session_verify_compat(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db = Depends(get_db),
):
    """
    Backward compatibility alias for session verification endpoint.
    
    Delegates to /auth/verify-session logic.
    """
    logger.warning(
        "Session verify accessed via deprecated compatibility endpoint /api/v2/session/verify",
        extra={
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
            "migration_note": "Frontend should be updated to use /api/v2/auth/verify-session"
        }
    )
    
    # Import auth router logic
    from app.api.v2.routers.auth import verify_session
    return await verify_session(request, current_user, db)


# ============================================================================
# Compatibility Endpoint: GET /session/user -> /auth/me
# ============================================================================

@router.get(
    "/user",
    response_model=dict,  # Explicitly set response_model to dict
    summary="Get current user (Compatibility Alias)",
    description="""
    **DEPRECATED**: Legacy endpoint for retrieving current user information.
    
    This endpoint provides backward compatibility for frontend applications
    that call `/api/v2/session/user` instead of `/api/v2/auth/me`.
    
    **Recommended**: Update your frontend to use `/api/v2/auth/me` instead.
    
    This alias will be removed in a future version.
    """,
    tags=["session-v2", "auth-v2", "deprecated"],
    deprecated=True
)
@limiter.limit("100/minute")
async def session_user_compat(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db = Depends(get_db),
):
    """
    Backward compatibility alias for get current user endpoint.
    
    Delegates to /auth/me logic (users router).
    """
    logger.warning(
        "Session user accessed via deprecated compatibility endpoint /api/v2/session/user",
        extra={
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
            "migration_note": "Frontend should be updated to use /api/v2/auth/me"
        }
    )
    
    # Check if /auth/me endpoint exists in users router
    try:
        from app.api.v2.routers.users import get_current_user_me
        return await get_current_user_me(request, current_user, db)
    except ImportError:
        # Fallback: return basic user info
        user_id = _extract_user_id(current_user)
        
        from app.models.user import User
        user = db.query(User).filter(User.id == UUID(user_id)).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            "is_active": user.is_active,
            "firebase_uid": user.firebase_uid
        }


# ============================================================================
# Health Check
# ============================================================================

@router.get(
    "/health",
    summary="Session compatibility router health check",
    description="Check if session compatibility router is operational"
)
async def session_health_check():
    """Health check endpoint for session compatibility router."""
    return {
        "status": "healthy",
        "service": "session-compatibility-v2",
        "version": "2.0.0",
        "endpoints": {
            "login": "/session/login (deprecated, use /auth/firebase/verify)",
            "verify": "/session/verify (deprecated, use /auth/verify-session)",
            "user": "/session/user (deprecated, use /auth/me)"
        },
        "deprecation_notice": "This router provides backward compatibility only. Please migrate to /auth endpoints."
    }
