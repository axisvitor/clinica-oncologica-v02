from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
import logging

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
@limiter.limit("10/minute")
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

        from app.repositories.user import UserRepository

        user_repo = UserRepository(db)
        user = user_repo.get_by_firebase_uid(firebase_uid)

        if user:
            # Update existing
            user.firebase_last_sign_in = datetime.utcnow()
            user.firebase_email_verified = user_data.get("email_verified", False)
            if user_data.get("name"):
                user.firebase_display_name = user_data.get("name")
            if user_data.get("picture"):
                user.firebase_photo_url = user_data.get("picture")
            user.firebase_custom_claims = user_data.get("custom_claims", {})
            user.last_firebase_sync = datetime.utcnow()

            # Lock check
            if getattr(user, "is_locked", False):
                if user.locked_until and datetime.utcnow() < user.locked_until:
                    raise HTTPException(status_code=403, detail="Account locked")
                user.is_locked = False
                user.locked_until = None
                user.failed_login_attempts = 0

            db.commit()
            db.refresh(user)
        else:
            # Create new
            from app.models.user import User, AuthProvider, UserRole

            custom_claims = user_data.get("custom_claims", {})
            firebase_role = custom_claims.get("role", "doctor").lower()
            user_role = UserRole.ADMIN if firebase_role == "admin" else UserRole.DOCTOR

            user = User(
                firebase_uid=firebase_uid,
                email=email,
                full_name=user_data.get("name", email.split("@")[0]),
                is_active=True,
                role=user_role,
                auth_provider=AuthProvider.FIREBASE,
                firebase_email_verified=user_data.get("email_verified", False),
                firebase_display_name=user_data.get("name"),
                firebase_photo_url=user_data.get("picture"),
                firebase_custom_claims=custom_claims,
                firebase_created_at=datetime.utcnow(),
                firebase_last_sign_in=datetime.utcnow(),
            )
            db.add(user)
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
            last_activity=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=5),  # 5 days default
            is_active=True,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        logger.info(f"✅ DB Session created: session_id={session.id}")

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
            raise HTTPException(
                status_code=500, detail="Failed to create Redis session"
            )

        logger.info(
            f"✅ Redis Session created: session_id={session.id}, result={redis_result}"
        )

        # Set HttpOnly Cookie
        response.set_cookie(
            key="session_id",
            value=str(session.id),
            httponly=True,
            secure=settings.SESSION_ENABLE_COOKIE_SECURE,
            samesite="strict",
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


import uuid
from datetime import timedelta


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
        await redis_cache.invalidate_session(session_id)

        # Also mark as revoked in DB
        from app.models.session import Session as SessionModel

        try:
            db_session = (
                db.query(SessionModel).filter(SessionModel.id == session_id).first()
            )
            if db_session:
                db_session.is_active = False
                db_session.revoked_at = datetime.utcnow()
                db.commit()
        except Exception as e:
            logger.error(f"Error revoking DB session: {e}")

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

    # Revoke all in DB
    from app.models.session import Session as SessionModel

    try:
        user_uuid = UUID(user_id)
        db.query(SessionModel).filter(
            SessionModel.user_id == user_uuid, SessionModel.is_active
        ).update(
            {SessionModel.is_active: False, SessionModel.revoked_at: datetime.utcnow()}
        )
        db.commit()
    except Exception as e:
        logger.error(f"Error revoking all DB sessions: {e}")

    return {
        "message": "Logged out from all devices",
        "success": True,
        "sessions_deleted": deleted_count,
    }


@router.get("/csrf-token")
async def get_csrf_token_endpoint(request: Request, response: Response):
    """
    Get signed CSRF token.

    Generates a cryptographically signed CSRF token using HMAC-SHA256.
    The token is also set as a cookie for Double Submit Cookie pattern.

    Note: In this API-first design, we rely primarily on HTTP-only cookies
    and SameSite=Strict for CSRF protection, but this endpoint is provided
    for clients that require explicit CSRF tokens.
    """
    from app.middleware.csrf import get_csrf_token, set_csrf_cookie

    token = get_csrf_token(request)
    set_csrf_cookie(request, response, token)
    return {"csrf_token": token}
