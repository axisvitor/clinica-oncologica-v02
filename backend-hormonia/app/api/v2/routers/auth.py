from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response

from app.database import get_db
from app.dependencies.auth_dependencies import (
    get_current_user_from_session,
    get_redis_cache,
    verify_firebase_token as verify_token,
)
from app.utils.rate_limiter import limiter
from app.schemas.v2.auth import (
    FirebaseTokenVerifyRequest,
    FirebaseTokenVerifyResponse,
    SessionV2Response,
)
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


def _serialize_session(
    session, current_user=None, current_session_id: Optional[str] = None
) -> dict:
    """
    Serialize Session model to API-friendly dict matching SessionV2Response schema.

    Args:
        session: Session database model
        current_user: User data dict from auth (with id, email, role, etc.)
        current_session_id: Optional session ID to mark as current

    Returns:
        Dict matching SessionV2Response schema
    """
    from datetime import datetime as dt

    # Helper to parse ISO string or pass through datetime objects
    def _parse_datetime(value):
        if value is None:
            return None
        if isinstance(value, str):
            # Parse ISO format string from cache
            try:
                return dt.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return None
        return value  # Already a datetime object

    # Format user data to match UserV2Response schema if provided
    user_data = None
    if current_user:
        # Extract user fields - current_user is a dict from get_current_user_from_session
        user_data = {
            "id": current_user.get("id"),
            "email": current_user.get("email"),
            "full_name": current_user.get("full_name"),
            "role": current_user.get("role", "doctor"),
            "is_active": current_user.get("is_active", True),
            # Parse timestamps (may be ISO strings from cache or datetime objects from DB)
            "created_at": _parse_datetime(current_user.get("created_at"))
            or session.created_at,
            "updated_at": _parse_datetime(current_user.get("updated_at"))
            or session.last_activity,
            "last_login": _parse_datetime(current_user.get("last_login")),
        }

    return {
        "session_id": str(session.id),
        "user_id": str(session.user_id),
        "created_at": session.created_at,
        "expires_at": session.expires_at,
        "ip_address": session.ip_address,
        "user_agent": session.user_agent,
        "is_current": str(session.id) == current_session_id
        if current_session_id
        else False,
        "valid": True,
        "user": user_data,
    }


def _extract_user_id(current_user) -> str:
    if isinstance(current_user, dict):
        return current_user.get("id")
    return str(getattr(current_user, "id", None))


@router.post(
    "/firebase/verify",
    response_model=FirebaseTokenVerifyResponse,
    summary="Verify Firebase token",
)
@limiter.limit("5/minute")
async def verify_firebase_token(
    request: Request,
    response: Response,
    payload: FirebaseTokenVerifyRequest,
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache),
):
    """Verify Firebase ID token and create/update user session."""
    logger.info("🔥 Firebase login request received: Starting processing")

    try:
        # Standard Firebase Verification
        # Use dependency helper which handles service initialization and validation
        user_data = await verify_token(payload.id_token)
        logger.info(f"✅ Token verified for user: {user_data.get('email')}")

        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid Firebase token")

        firebase_uid = user_data.get("uid")
        email = user_data.get("email")

        if not firebase_uid or not email:
            raise HTTPException(status_code=400, detail="Token missing fields")

        # Use FirebaseUserSyncService for secure synchronization and domain validation
        from app.services.firebase_user_sync_service import FirebaseUserSyncService
        from app.dependencies.auth_dependencies import _firebase_service

        sync_service = FirebaseUserSyncService(db, _firebase_service)
        try:
            user, created = await sync_service.sync_firebase_user(
                firebase_uid=firebase_uid,
                firebase_data=user_data,
                auto_create=True
            )
        except ValueError as e:
            # Handle unauthorized domain or invalid claims
            logger.warning(f"Firebase sync validation failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )

        # Check account lock status with proper transaction handling
        if getattr(user, "is_locked", False):
            if user.locked_until and datetime.now(timezone.utc) < user.locked_until:
                raise HTTPException(status_code=403, detail="Account locked")
            # Use update query to avoid race conditions
            from app.models.user import User
            db.query(User).filter(User.id == user.id).update({
                "is_locked": False,
                "locked_until": None,
                "failed_login_attempts": 0
            })
            db.commit()
            db.refresh(user)

        # Create Session
        from app.models.session import Session as SessionModel

        session_id_hex = uuid.uuid4().hex
        session = SessionModel(
            user_id=user.id,
            session_token=session_id_hex,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            last_activity=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=5),  # 5 days default
            is_active=True,
        )
        db.add(session)

        # CRITICAL FIX: Use flush() instead of commit() to get session ID without persisting
        # This allows us to rollback if Redis creation fails
        db.flush()
        db.refresh(session)
        logger.info(f"🔄 DB Session flushed (not committed): session_id={session.id}")

        try:
            # Create Redis Session (Critical Fix)
            redis_result = await redis_cache.create_session(
                session_id=str(session.id),
                user_id=str(user.id),
                firebase_uid=user.firebase_uid,
                metadata={
                    "ip_address": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                },
                ttl_seconds=432000,  # 5 days
            )

            if not redis_result:
                logger.error("Redis create_session FAILED (returned False)")
                # Rollback DB session since Redis failed
                db.rollback()
                raise HTTPException(
                    status_code=500, detail="Failed to create Redis session"
                )

            logger.info(
                f"✅ Redis Session created: session_id={session.id}, result={redis_result}"
            )

            # CRITICAL FIX: Only commit DB after Redis succeeds
            db.commit()
            logger.info(f"✅ DB Session committed: session_id={session.id}")

        except HTTPException:
            # Re-raise HTTP exceptions (already logged and rolled back)
            raise
        except Exception as e:
            # Unexpected error during Redis creation - rollback DB and cleanup
            logger.error(f"Unexpected error during session creation: {e}")
            db.rollback()

            # Attempt to cleanup Redis session if it was partially created
            try:
                await redis_cache.invalidate_session(str(session.id))
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup Redis session: {cleanup_error}")

            raise HTTPException(
                status_code=500,
                detail="Failed to create session - transaction rolled back"
            )

        # Set HttpOnly Cookie
        response.set_cookie(
            key="session_id",
            value=str(session.id),
            httponly=True,
            secure=settings.SESSION_ENABLE_COOKIE_SECURE,
            samesite=settings.SESSION_COOKIE_SAMESITE,
            path="/",  # Important: ensure cookie is sent on all routes
            max_age=432000,  # 5 days
        )
        logger.info(f"✅ Cookie set: session_id={session.id}, path=/")

        # Set X-Session-ID header for compatibility
        if (
            settings.APP_ENABLE_DEBUG
            and settings.APP_ENVIRONMENT.lower() != "production"
        ):
            response.headers["X-Session-ID"] = str(session.id)

        # Return correct response structure matching FirebaseTokenVerifyResponse
        if (
            settings.APP_ENABLE_DEBUG
            and settings.APP_ENVIRONMENT.lower() != "production"
        ):
            return {
                "valid": True,
                "session_id": str(session.id),
                "message": "Login successful",
            }

        return {"valid": True, "message": "Login successful"}

    except ValueError as e:
        logger.warning(f"Invalid Firebase token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Firebase token: {str(e)}",
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        import traceback

        logger.error(f"Auth error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


@router.get("/verify-session", response_model=SessionV2Response)
@limiter.limit("100/minute")
async def verify_session(
    request: Request,
    response: Response,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
):
    """
    Verify current session and return session + user details.

    Returns:
        SessionV2Response with full user data including timestamps
    """
    user_id = _extract_user_id(current_user)
    try:
        user_uuid = UUID(user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid user_id UUID")

    from app.models.session import Session as SessionModel
    from app.models.user import User

    # Get active session with user data
    session = (
        db.query(SessionModel)
        .filter(
            SessionModel.user_id == user_uuid,
            SessionModel.is_active,
            SessionModel.revoked_at.is_(None),
        )
        .order_by(SessionModel.last_activity.desc())
        .first()
    )

    if not session or session.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")

    # Enrich user data with database timestamps if not in cache
    # The current_user dict from cache might not have created_at/updated_at
    if not current_user.get("created_at") or not current_user.get("updated_at"):
        db_user = db.query(User).filter(User.id == user_uuid).first()
        if db_user:
            current_user["created_at"] = db_user.created_at
            current_user["updated_at"] = db_user.updated_at
            current_user["last_login"] = db_user.firebase_last_sign_in

    # Get session_id from cookie or header for is_current check
    session_id_from_request = request.cookies.get("session_id") or request.headers.get(
        "X-Session-ID"
    )

    return _serialize_session(
        session, current_user=current_user, current_session_id=session_id_from_request
    )


@router.delete("/logout", status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
async def logout(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
    db=Depends(get_db),
):
    """Logout current session."""
    session_id = request.cookies.get("session_id") or request.headers.get(
        "X-Session-ID"
    )
    if session_id:
        # Validate session_id is a valid UUID before using in query
        try:
            session_uuid = UUID(session_id)
        except (ValueError, TypeError):
            logger.warning(f"Invalid session_id format: {session_id}")
            raise HTTPException(status_code=400, detail="Invalid session ID")

        await redis_cache.invalidate_session(session_id)

        # Also mark as revoked in DB with proper error handling
        from app.models.session import Session as SessionModel

        try:
            db_session = (
                db.query(SessionModel).filter(SessionModel.id == session_uuid).first()
            )
            if db_session:
                db_session.is_active = False
                db_session.revoked_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as e:
            logger.error(f"Error revoking DB session: {e}")
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to revoke session")

    return {"message": "Logged out successfully", "success": True}


@router.delete("/logout-all", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def logout_all(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
    db=Depends(get_db),
):
    """Logout from all devices."""
    user_id = _extract_user_id(current_user)
    firebase_uid = (
        current_user.get("firebase_uid")
        if isinstance(current_user, dict)
        else current_user.firebase_uid
    )

    deleted_count = 0
    if firebase_uid:
        deleted_count = await redis_cache.invalidate_all_user_sessions(firebase_uid)

    # Revoke all in DB with proper error handling
    from app.models.session import Session as SessionModel

    try:
        user_uuid = UUID(user_id)
        db.query(SessionModel).filter(
            SessionModel.user_id == user_uuid, SessionModel.is_active
        ).update(
            {SessionModel.is_active: False, SessionModel.revoked_at: datetime.now(timezone.utc)}
        )
        db.commit()
    except Exception as e:
        logger.error(f"Error revoking all DB sessions: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to revoke all sessions")

    return {
        "message": "Logged out from all devices",
        "success": True,
        "sessions_deleted": deleted_count,
    }


@router.get("/csrf-token")
@limiter.limit("100/minute")
async def get_csrf_token_endpoint(request: Request, response: Response):
    """
    Generate and return a cryptographically signed CSRF token.

    Security Model (Double Submit Cookie Pattern):
        1. Server generates signed token with HMAC-SHA256
        2. Token stored in httpOnly cookie (automatic browser management)
        3. Token returned in response body (for header inclusion)
        4. Client sends token in X-CSRF-Token header for protected requests

    Token Properties:
        - Format: {timestamp}.{random_hex}.{hmac_signature}
        - Encoding: Hexadecimal (URL-safe, auditable)
        - Entropy: 256 bits of cryptographically secure randomness
        - Signature: HMAC-SHA256 (prevents tampering)
        - Expiration: 1 hour (configurable)

    Response Format:
        {
            "csrf_token": "1734695123.a1b2c3d4e5f6...signature"
        }

    Cookie Configuration:
        - Name: csrf_token
        - Flags: httpOnly, secure (production), SameSite=Strict
        - Max-Age: 3600 seconds (1 hour)

    Usage Example:
        1. GET /api/v2/auth/csrf-token
        2. Extract token from response body
        3. Include in header: X-CSRF-Token: {token}
        4. Make state-changing request (POST, PUT, DELETE, PATCH)

    Rate Limiting:
        100 requests per minute per IP address

    Security Notes:
        - Token is cryptographically signed (prevents forgery)
        - Token expires after 1 hour (prevents replay attacks)
        - Cookie is httpOnly (prevents XSS token theft)
        - SameSite=Strict (prevents CSRF from external sites)

    Returns:
        dict: Response containing the CSRF token

    Raises:
        HTTPException: If rate limit exceeded (429 Too Many Requests)
    """
    from app.middleware.csrf import get_csrf_token, set_csrf_cookie

    try:
        # Generate cryptographically secure CSRF token
        token = get_csrf_token()

        # Set token in httpOnly cookie (returns token for convenience)
        set_csrf_cookie(response, token)

        # Log token generation (without exposing token value)
        client_ip = request.client.host if request.client else "unknown"
        logger.info(f"CSRF token generated for client: {client_ip}")

        # Return token in response body for client-side storage
        return {"csrf_token": token}

    except ValueError as e:
        # Handle invalid secret key or configuration errors
        logger.error(f"CSRF token generation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="CSRF token generation failed. Please contact administrator."
        )
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error generating CSRF token: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
