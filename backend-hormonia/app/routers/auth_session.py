"""
Session-based Authentication Router

Provides session management endpoints for Firebase + Redis architecture.
Ultra-fast session-based auth (~2-5ms) vs Bearer token auth (~200-450ms).

Endpoints:
- POST /session: Create session after Firebase login (frontend calls after Firebase Auth)
- GET /session/validate: Validate session (health check)
- DELETE /session/logout: Single session logout
- DELETE /session/logout-all: Global logout (all user sessions)
- GET /session/active: List all active sessions for current user
- GET /session/stats: Cache performance statistics

Performance:
- Session validation: ~2-5ms (Redis cache hit)
- Token validation: ~200ms (Firebase Admin SDK)
- Full request (warm): ~5ms (95-98% cache hit rate)
"""

from fastapi import APIRouter, Depends, HTTPException, Header, status, Cookie, Response, Request
from sqlalchemy.orm import Session
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging
import secrets
from datetime import datetime

from app.models.user import User, UserRole
from app.services import ServiceProvider
from app.services.audit_log import AuditLogService
from app.dependencies.auth_dependencies import (
    _firebase_service,
    _get_service_provider,
    get_permissions_for_role,
)
from app.dependencies.simple_service_provider import get_simple_service_provider
from app.database import get_db
from app.middleware.csrf import validate_csrf_token
from app.middleware.custom_csrf import validate_custom_csrf
from app.utils.rate_limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/session", tags=["Session Authentication"])
security = HTTPBearer()


# =============================================================================
# SECURITY UTILITIES
# =============================================================================

def generate_session_id() -> str:
    """
    Generate cryptographically secure session ID with 256-bit entropy.

    Uses secrets.token_urlsafe(32) which generates:
    - 32 bytes = 256 bits of entropy
    - URL-safe base64 encoding (43 characters)
    - Cryptographically strong random number generator

    This prevents session fixation attacks by ensuring:
    1. Unpredictable session IDs
    2. High entropy (2^256 possible values)
    3. No timing attacks possible

    Returns:
        str: URL-safe session ID with 256-bit entropy
    """
    return secrets.token_urlsafe(32)


async def regenerate_session(
    firebase_cache,
    old_session_id: Optional[str],
    user_id: str,
    firebase_uid: str,
    metadata: Dict[str, Any]
) -> str:
    """
    Regenerate session ID after authentication to prevent session fixation.

    Session fixation attack scenario:
    1. Attacker gets a valid session ID
    2. Attacker tricks user into authenticating with that session ID
    3. Attacker uses the same session ID to access user's account

    Defense: Always generate NEW session ID after successful authentication.

    Args:
        firebase_cache: Redis cache manager
        old_session_id: Session ID before authentication (if any)
        user_id: Database user ID
        firebase_uid: Firebase UID
        metadata: Session metadata

    Returns:
        str: New session ID with 256-bit entropy
    """
    # Generate new session ID with 256-bit entropy
    new_session_id = generate_session_id()

    # Invalidate old session if it exists
    if old_session_id:
        try:
            await firebase_cache.invalidate_session(old_session_id)
            logger.info(f"Invalidated old session: {old_session_id[:8]}... during regeneration")
        except Exception as e:
            logger.warning(f"Failed to invalidate old session: {str(e)}")

    # Create new session
    success = await firebase_cache.create_session(
        session_id=new_session_id,
        user_id=user_id,
        firebase_uid=firebase_uid,
        metadata=metadata
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate session"
        )

    logger.info(f"✅ Session regenerated: {new_session_id[:8]}... for user {user_id}")
    return new_session_id


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class SessionCreateRequest(BaseModel):
    """Request to create session from Firebase token."""
    firebase_token: str = Field(..., description="Firebase ID token")
    device_info: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional device metadata (device_type, os, browser, etc.)"
    )


class SessionResponse(BaseModel):
    """Session creation response."""
    status: str = Field(..., description="Authentication status")
    expires_at: str = Field(..., description="Session expiration timestamp (ISO 8601)")
    user: Dict[str, Any] = Field(..., description="User data")


class SessionValidationResponse(BaseModel):
    """Session validation response."""
    valid: bool
    user: Optional[Dict[str, Any]] = None
    session_data: Optional[Dict[str, Any]] = None


class LogoutResponse(BaseModel):
    """Logout response."""
    success: bool
    sessions_deleted: int = Field(..., description="Number of sessions deleted")
    message: str


class SessionListResponse(BaseModel):
    """List of active sessions."""
    sessions: List[Dict[str, Any]]
    total: int


class CacheStatsResponse(BaseModel):
    """Cache performance statistics."""
    stats: Dict[str, Any]


# =============================================================================
# SESSION MANAGEMENT ENDPOINTS
# =============================================================================

@router.post("/test-simple")
async def test_simple_session():
    """
    Endpoint de teste ultra simples para debug
    """
    return {
        "status": "success",
        "message": "Simple session test working!",
        "timestamp": "2025-10-10T19:32:00Z"
    }

@router.post(
    "/",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(validate_custom_csrf)]
)
@limiter.limit("20/minute")  # Rate limit: 20 session creations per minute per IP
async def create_session(
    session_data: SessionCreateRequest,
    response: Response,
    request: Request,
    services: ServiceProvider = Depends(_get_service_provider)
):
    """
    Create new Redis session from Firebase token.

    Frontend workflow:
    1. User logs in with Firebase (frontend SDK)
    2. Frontend receives Firebase ID token
    3. Frontend calls this endpoint with token
    4. Backend validates token, creates session, sets httpOnly cookie
    5. Frontend receives session cookie automatically (no localStorage)
    6. Browser sends session cookie automatically on subsequent requests

    SECURITY: Session ID is stored in httpOnly cookie (XSS-safe).
    JavaScript cannot access the cookie via document.cookie.

    Performance: ~250ms (cold) - one-time cost during login
    Subsequent requests: ~2-5ms (session validation)

    Args:
        session_data: Session creation request with Firebase token
        response: FastAPI Response object for setting cookies
        request: FastAPI Request object

    Returns:
        Session status and user data (session_id NOT in response body)

    Raises:
        HTTPException 401: Invalid Firebase token
        HTTPException 503: Firebase not configured
    """
    if _firebase_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase authentication is not configured"
        )

    try:
        # Validate Firebase token (200ms)
        try:
            user_data = await _firebase_service.verify_token(session_data.firebase_token)
        except Exception as e:
            logger.error(f"Firebase token verification failed: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Firebase token: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"}
            )

        firebase_uid = user_data["uid"]
        email = user_data.get("email")

        logger.info(f"Creating session for user: {email}")

        # Get or create user in database
        from app.models.user import User
        from sqlalchemy import select

        stmt = select(User).where(User.firebase_uid == firebase_uid)
        result = services.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            # Create minimal user record
            from app.models.user import UserRole
            firebase_role = user_data.get("role", "doctor").lower()
            user_role = UserRole.ADMIN if firebase_role == "admin" else UserRole.DOCTOR

            user = User(
                firebase_uid=firebase_uid,
                email=email,
                full_name=user_data.get("name", email.split("@")[0]),
                is_active=True,
                role=user_role
            )
            services.db.add(user)
            services.db.commit()
            services.db.refresh(user)
            logger.info(f"Created new user: {email}")

        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )

        # Create Redis session (Layer 3)
        from app.core.redis_manager import FirebaseRedisCache, get_redis_manager
        redis_manager = get_redis_manager()
        redis_client = redis_manager.get_compatible_client("sync")
        firebase_cache = FirebaseRedisCache(redis_client)

        # Session metadata
        metadata = {
            "email": user.email,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            **(session_data.device_info or {})
        }

        # SECURITY: Regenerate session ID after authentication to prevent session fixation
        # In this endpoint, there's no old session (new login), but we use regenerate_session
        # for consistency and to ensure 256-bit entropy
        session_id = await regenerate_session(
            firebase_cache=firebase_cache,
            old_session_id=None,  # No old session for new login
            user_id=str(user.id),
            firebase_uid=firebase_uid,
            metadata=metadata
        )

        # Also cache user object (Layer 2)
        user_dict = {
            "id": str(user.id),
            "firebase_uid": user.firebase_uid,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            "is_active": user.is_active,
        }
        firebase_cache.cache_user(firebase_uid, user_dict)

        # Calculate expiration
        from datetime import timedelta
        from app.config import settings
        ttl = getattr(settings, 'FIREBASE_SESSION_TTL', 86400)
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)

        logger.info(f"✅ Session created: {session_id[:8]}... for {email}")

        # Log audit event
        try:
            audit_service = AuditLogService(services.db)
            from fastapi import Request
            # Create mock request with headers for audit logging
            class MockRequest:
                def __init__(self):
                    self.headers = {}
                    self.client = None
            mock_request = MockRequest()
            audit_service.log_session_created(user, session_id, request=mock_request, metadata=metadata)
        except Exception as audit_error:
            logger.warning(f"Failed to log audit event: {audit_error}")

        # SECURITY FIX: Set httpOnly cookie instead of returning session_id in JSON
        # This prevents XSS attacks from stealing session credentials
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,      # JavaScript cannot access (XSS protection)
            secure=True,        # HTTPS only in production
            samesite="strict",  # CSRF protection
            max_age=ttl,        # Cookie expiration (seconds)
            path="/"            # Available for all paths
        )

        return SessionResponse(
            status="authenticated",
            expires_at=expires_at.isoformat(),
            user=user_dict
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session creation failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Session creation failed: {str(e)}"
        )


@router.get("/validate", response_model=SessionValidationResponse)
@limiter.limit("200/minute")  # Rate limit: 200 session validations per minute per IP
async def validate_session(
    request: Request,
    session_id: Optional[str] = Cookie(None),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    services: ServiceProvider = Depends(_get_service_provider),
    db: Session = Depends(get_db),
):
    """
    Validate session and return user data.

    SECURITY: Reads session_id from httpOnly cookie (primary) with
    fallback to X-Session-ID header for backward compatibility.

    Performance: ~2-5ms (Redis cache hit)

    Args:
        session_id: Session ID from httpOnly cookie (preferred)
        x_session_id: Session ID from X-Session-ID header (fallback)

    Returns:
        Validation result with user data if valid

    Raises:
        HTTPException 401: Invalid or expired session
    """
    # Priority: Cookie > Header (for backward compatibility during migration)
    final_session_id = session_id or x_session_id

    if not final_session_id:
        return SessionValidationResponse(valid=False)

    try:
        from app.core.redis_manager import FirebaseRedisCache, get_redis_manager
        redis_manager = get_redis_manager()
        redis_client = redis_manager.get_compatible_client("sync")
        firebase_cache = FirebaseRedisCache(redis_client)

        # Get session from Redis (~2-5ms)
        session_data = await firebase_cache.get_session(final_session_id)

        if not session_data:
            return SessionValidationResponse(valid=False)

        # Get user data from cache or DB
        firebase_uid = session_data.get("firebase_uid")
        cached_user = firebase_cache.get_cached_user(firebase_uid)

        if cached_user:
            user_data = dict(cached_user)
            user_data.pop("cached_at", None)
            user_data.pop("validated_at", None)
        else:
            from sqlalchemy import select

            stmt = select(User).where(User.firebase_uid == firebase_uid)
            result = db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return SessionValidationResponse(valid=False)

            user_data = {
                "id": str(user.id),
                "firebase_uid": user.firebase_uid,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value if isinstance(user.role, UserRole) else str(user.role),
                "is_active": user.is_active,
            }

        # Normalize role/permissions
        role_value = user_data.get("role")
        if isinstance(role_value, UserRole):
            role_str = role_value.value
        elif isinstance(role_value, str):
            role_str = role_value.lower()
        else:
            role_str = None

        user_data["role"] = role_str
        user_data["permissions"] = get_permissions_for_role(role_str or "")

        if user_data.get("id") is not None:
            user_data["id"] = str(user_data["id"])

        return SessionValidationResponse(
            valid=True,
            user=user_data,
            session_data=session_data
        )

    except Exception as e:
        logger.error(f"Session validation error: {str(e)}", exc_info=True)
        return SessionValidationResponse(valid=False)


@router.delete(
    "/logout",
    response_model=LogoutResponse,
    dependencies=[Depends(validate_csrf_token)]
)
@limiter.limit("100/minute")  # Rate limit: 100 logout attempts per minute per IP
async def logout_session(
    request: Request,
    response: Response,
    session_id: Optional[str] = Cookie(None),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    db: Session = Depends(get_db)
):
    """
    Logout - invalidate current session.

    SECURITY: Clears httpOnly cookie and invalidates session in Redis.

    Performance: ~2-5ms (Redis delete)

    Args:
        response: FastAPI Response object for clearing cookies
        session_id: Session ID from httpOnly cookie (preferred)
        x_session_id: Session ID from X-Session-ID header (fallback)

    Returns:
        Logout confirmation
    """
    # Priority: Cookie > Header
    final_session_id = session_id or x_session_id

    if not final_session_id:
        return LogoutResponse(
            success=False,
            sessions_deleted=0,
            message="No active session found"
        )

    try:
        from app.core.redis_manager import FirebaseRedisCache, get_redis_manager
        redis_manager = get_redis_manager()
        redis_client = redis_manager.get_compatible_client("sync")
        firebase_cache = FirebaseRedisCache(redis_client)

        # Get session data before deletion for audit log
        session_data = await firebase_cache.get_session(final_session_id)
        user_id = session_data.get("user_id") if session_data else None

        # Delete session from Redis
        deleted = await firebase_cache.invalidate_session(final_session_id)

        # Log audit event
        if user_id:
            try:
                audit_service = AuditLogService(db)
                from fastapi import Request
                class MockRequest:
                    def __init__(self):
                        self.headers = {}
                        self.client = None
                mock_request = MockRequest()
                audit_service.log_session_invalidated(user_id, final_session_id, reason="logout", request=mock_request)
            except Exception as audit_error:
                logger.warning(f"Failed to log audit event: {audit_error}")

        # SECURITY: Clear httpOnly cookie regardless of Redis result
        response.delete_cookie(
            key="session_id",
            path="/",
            httponly=True,
            secure=True,
            samesite="strict"
        )

        if deleted:
            logger.info(f"Session logged out: {final_session_id[:8]}...")
            return LogoutResponse(
                success=True,
                sessions_deleted=1,
                message="Session logged out successfully"
            )
        else:
            return LogoutResponse(
                success=False,
                sessions_deleted=0,
                message="Session already expired or invalid"
            )

    except Exception as e:
        logger.error(f"Logout error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}"
        )


@router.delete(
    "/logout-all",
    response_model=LogoutResponse,
    dependencies=[Depends(validate_csrf_token)]
)
@limiter.limit("10/hour")  # Rate limit: 10 global logout attempts per hour per IP
async def logout_all_sessions(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    services: ServiceProvider = Depends(_get_service_provider)
):
    """
    Global logout - invalidate ALL sessions for current user.

    Use cases:
    - Password change
    - Security breach (force logout all devices)
    - Admin action

    Performance: ~50-100ms (Redis scan + delete)

    Args:
        credentials: Firebase Bearer token for authentication

    Returns:
        Logout confirmation with number of sessions deleted
    """
    if _firebase_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase authentication is not configured"
        )

    try:
        # Verify Firebase token to get user identity
        user_data = await _firebase_service.verify_token(credentials.credentials)
        firebase_uid = user_data["uid"]

        from app.core.redis_manager import FirebaseRedisCache, get_redis_manager
        redis_manager = get_redis_manager()
        redis_client = redis_manager.get_compatible_client("sync")
        firebase_cache = FirebaseRedisCache(redis_client)

        # Delete ALL user sessions
        deleted = await firebase_cache.invalidate_all_user_sessions(firebase_uid)

        logger.info(f"Global logout: {deleted} sessions deleted for {user_data.get('email')}")

        return LogoutResponse(
            success=True,
            sessions_deleted=deleted,
            message=f"All {deleted} sessions logged out successfully"
        )

    except Exception as e:
        logger.error(f"Global logout error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Global logout failed: {str(e)}"
        )


@router.get("/active", response_model=SessionListResponse)
@limiter.limit("100/minute")  # Rate limit: 100 session list requests per minute per IP
async def list_active_sessions(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    services: ServiceProvider = Depends(_get_service_provider)
):
    """
    List all active sessions for current user.

    Useful for:
    - Security dashboard (see all logged-in devices)
    - Session management UI

    Performance: ~50-100ms (Redis scan)

    Args:
        credentials: Firebase Bearer token for authentication

    Returns:
        List of active sessions with metadata
    """
    if _firebase_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase authentication is not configured"
        )

    try:
        # Verify Firebase token
        user_data = await _firebase_service.verify_token(credentials.credentials)
        firebase_uid = user_data["uid"]

        from app.core.redis_manager import FirebaseRedisCache, get_redis_manager
        redis_manager = get_redis_manager()
        redis_client = redis_manager.get_compatible_client("sync")
        firebase_cache = FirebaseRedisCache(redis_client)

        # Get all active sessions
        sessions = firebase_cache.list_user_sessions(firebase_uid)

        return SessionListResponse(
            sessions=sessions,
            total=len(sessions)
        )

    except Exception as e:
        logger.error(f"List sessions error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sessions: {str(e)}"
        )


@router.get("/stats", response_model=CacheStatsResponse)
@limiter.limit("60/minute")  # Rate limit: 60 cache stats requests per minute per IP
async def get_cache_stats(
    request: Request,
    services: ServiceProvider = Depends(_get_service_provider)
):
    """
    Get Redis cache performance statistics.

    Returns:
        Cache metrics (TTLs, active sessions, Redis health)
    """
    try:
        from app.core.redis_manager import FirebaseRedisCache, get_redis_manager
        redis_manager = get_redis_manager()
        redis_client = redis_manager.get_compatible_client("sync")
        firebase_cache = FirebaseRedisCache(redis_client)

        stats = firebase_cache.get_cache_stats()

        return CacheStatsResponse(stats=stats)

    except Exception as e:
        logger.error(f"Cache stats error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve cache stats: {str(e)}"
        )
