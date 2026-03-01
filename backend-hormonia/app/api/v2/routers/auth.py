from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
import logging
import uuid

from fastapi import APIRouter, Depends, status, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from pydantic import (
    BaseModel,
    EmailStr,
    TypeAdapter,
    ValidationError as PydanticValidationError,
)
from sqlalchemy import text

from app.core.exceptions import (
    BusinessRuleError,
    ForbiddenError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationError,
)
from app.database import get_db
from app.dependencies.auth_dependencies import (
    _firebase_service,
    _validate_firebase_uid,
    get_current_user_from_session,
    get_redis_cache,
    verify_firebase_token as verify_token,
)
from app.utils.rate_limiter import limiter, auth_limiter
from app.schemas.v2.auth import (
    FirebaseTokenVerifyRequest,
    FirebaseTokenVerifyResponse,
    SessionV2Response,
)
from app.config import settings
from app.utils.auth_helpers import extract_user_id as _extract_user_id
from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
from app.api.v2.routers.notifications import router as notifications_router

router = APIRouter()
logger = logging.getLogger(__name__)
SESSION_COOKIE_NAME = settings.SESSION_COOKIE_NAME

# Legacy contract compatibility: keep notifications under /api/v2/auth/notifications/*
# while canonical paths stay in /api/v2/notifications/*.
router.include_router(notifications_router, prefix="/notifications")


def _auth_security_headers() -> dict[str, str]:
    """Security headers enforced for auth responses."""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    }


def _apply_auth_security_headers(response: Response) -> None:
    for key, value in _auth_security_headers().items():
        response.headers.setdefault(key, value)


def _auth_json_response(
    *,
    status_code: int,
    content: dict,
    extra_headers: Optional[dict[str, str]] = None,
) -> JSONResponse:
    headers = _auth_security_headers()
    if extra_headers:
        headers.update(extra_headers)
    return JSONResponse(status_code=status_code, content=content, headers=headers)


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
                return dt.fromisoformat(value)
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


def _normalize_session_uuid(raw_session_id: Optional[str]) -> Optional[str]:
    """Normalize session identifiers that may include legacy prefixes."""
    if not raw_session_id:
        return None
    try:
        UUID(raw_session_id)
        return raw_session_id
    except (ValueError, TypeError):
        candidate = str(raw_session_id)[-36:]
        try:
            UUID(candidate)
            return candidate
        except (ValueError, TypeError):
            return None


def _get_session_id_from_request(request: Request) -> Optional[str]:
    """Extract session ID from cookie, header, or Authorization bearer."""
    cookie_id = request.cookies.get(SESSION_COOKIE_NAME) or request.cookies.get("session_id")
    if cookie_id:
        return cookie_id

    header_id = request.headers.get("X-Session-ID")
    if header_id:
        return header_id

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]

    return None


async def _invalidate_session_cache(redis_cache, session_id: str) -> bool:
    """
    Invalidate a single session in cache with compatibility fallbacks.

    Supports current and legacy cache contracts used across test fixtures and
    service implementations.
    """
    if not redis_cache or not session_id:
        return False

    for method_name in ("invalidate_session", "delete_session", "delete"):
        method = getattr(redis_cache, method_name, None)
        if not callable(method):
            continue
        try:
            result = method(session_id)
            if hasattr(result, "__await__"):
                result = await result
            # Treat None as non-fatal for compatibility with noop implementations.
            return True if result is None else bool(result)
        except TypeError:
            # Try next contract variant when signature does not match.
            continue
        except Exception as exc:
            logger.warning("Cache session invalidation failed via %s: %s", method_name, exc)
            return False

    logger.debug("No compatible cache method found for session invalidation")
    return False


async def _invalidate_all_user_sessions_cache(redis_cache, firebase_uid: Optional[str]) -> int:
    """
    Invalidate all sessions for a user in cache with compatibility fallbacks.
    """
    if not redis_cache or not firebase_uid:
        return 0

    invalidate_all = getattr(redis_cache, "invalidate_all_user_sessions", None)
    if callable(invalidate_all):
        try:
            result = invalidate_all(firebase_uid)
            if hasattr(result, "__await__"):
                result = await result
            return int(result or 0)
        except Exception as exc:
            logger.warning("Cache bulk session invalidation failed: %s", exc)
            return 0

    delete_pattern = getattr(redis_cache, "delete_pattern", None)
    if callable(delete_pattern):
        try:
            result = delete_pattern(f"session:*{firebase_uid}*")
            if hasattr(result, "__await__"):
                result = await result
            return int(result) if isinstance(result, int) else 0
        except Exception as exc:
            logger.warning("Cache delete_pattern fallback failed: %s", exc)
            return 0

    logger.debug("No compatible cache method found for bulk session invalidation")
    return 0


@router.post(
    "/firebase/verify",
    response_model=FirebaseTokenVerifyResponse,
    summary="Verify Firebase token",
)
@auth_limiter.limit("5/minute")
async def verify_firebase_token(
    request: Request,
    response: Response,
    payload: FirebaseTokenVerifyRequest,
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache),
):
    """Verify Firebase ID token and create/update user session."""
    logger.info("Firebase login request received: Starting processing")
    try:
        id_token = (payload.id_token or "").strip()
        if not id_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="id_token is required",
            )
        # Defensive input bound: Firebase ID tokens are typically small JWT strings.
        if len(id_token) > 8192:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="id_token exceeds maximum allowed length",
            )
        token_parts = id_token.split(".")
        if len(token_parts) != 3 or any(not part for part in token_parts):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token format",
            )
        try:
            user_data = await verify_token(id_token)
        except HTTPException as verify_err:
            logger.warning(f"Firebase token verification failed: {verify_err.detail}")
            if verify_err.status_code == status.HTTP_401_UNAUTHORIZED:
                return _auth_json_response(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "valid": False,
                        "message": "Invalid Firebase token",
                        "detail": "Invalid Firebase token",
                    },
                    extra_headers={"WWW-Authenticate": "Bearer"},
                )
            return _auth_json_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "valid": False,
                    "message": "Authentication failed. Please try again later.",
                    "detail": "Authentication failed",
                },
            )
        except ValueError as verify_err:
            logger.warning(f"Firebase token verification failed: {verify_err}")
            return _auth_json_response(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "valid": False,
                    "message": "Invalid Firebase token",
                    "detail": "Invalid Firebase token",
                },
                extra_headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as verify_err:
            logger.warning(f"Firebase token verification failed: {verify_err}")
            return _auth_json_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "valid": False,
                    "message": "Authentication failed. Please try again later.",
                    "detail": "Authentication failed",
                },
            )

        logger.info(f"Token verified for user: {user_data.get('email') if user_data else None}")

        if not user_data:
            return _auth_json_response(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "valid": False,
                    "message": "Invalid or expired authentication token",
                    "detail": "Invalid or expired authentication token",
                },
            )

        firebase_uid = user_data.get("uid")
        email = user_data.get("email")

        if not firebase_uid or not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token missing required fields",
            )

        try:
            _validate_firebase_uid(str(firebase_uid))
        except HTTPException as uid_exc:
            # Token payload validation errors should return 400 on login endpoint.
            if uid_exc.status_code == status.HTTP_401_UNAUTHORIZED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid UID format in token",
                ) from uid_exc
            raise

        # Defensive validation for mocked/providers responses before persistence
        # and before FastAPI response-model serialization.
        try:
            email = str(TypeAdapter(EmailStr).validate_python(email))
        except (PydanticValidationError, ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format in token",
            )



        # Try the sync service first, then gracefully fallback to a direct upsert.
        from app.models.user import User, UserRole, AuthProvider

        user = None
        try:
            from app.services.firebase_user_sync_service import FirebaseUserSyncService

            sync_service = FirebaseUserSyncService(db, _firebase_service)
            user, created = await sync_service.sync_firebase_user(
                firebase_uid=firebase_uid,
                firebase_data=user_data,
                auto_create=True
            )
        except Exception as sync_err:
            logger.warning(f"Firebase sync fallback activated: {sync_err}")
            user = (
                db.query(User)
                .filter((User.firebase_uid == firebase_uid) | (User.email == email))
                .first()
            )
            if not user:
                user = User(
                    email=email,
                    full_name=user_data.get("name") or email.split("@")[0],
                    role=UserRole.DOCTOR,
                    is_active=True,
                    firebase_uid=firebase_uid,
                    auth_provider=AuthProvider.FIREBASE,
                )
                db.add(user)

        # Check account lock status before mutating profile fields.
        if getattr(user, "is_locked", False):
            if user.locked_until:
                current_time = (
                    now_sao_paulo_naive()
                    if getattr(user.locked_until, "tzinfo", None) is None
                    else now_sao_paulo()
                )
                if current_time < user.locked_until:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Account locked",
                    )
            user.is_locked = False
            user.locked_until = None
            user.failed_login_attempts = 0

        # Normalize key profile fields from Firebase payload regardless of sync path.
        display_name = user_data.get("name") or user_data.get("display_name")
        picture_url = user_data.get("picture") or user_data.get("photo_url")

        user.email = email
        user.firebase_uid = firebase_uid
        user.auth_provider = AuthProvider.FIREBASE
        if display_name:
            user.full_name = display_name
            user.firebase_display_name = display_name
        elif not user.full_name:
            user.full_name = email.split("@")[0]
        if picture_url:
            user.firebase_photo_url = picture_url
        user.firebase_last_sign_in = now_sao_paulo()
        db.flush()



        # Create Session
        from app.models.session import Session as SessionModel

        session_id_hex = uuid.uuid4().hex
        session = SessionModel(
            user_id=user.id,
            session_token=session_id_hex,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            last_activity=now_sao_paulo(),
            expires_at=now_sao_paulo() + timedelta(days=5),  # 5 days default
            is_active=True,
        )
        db.add(session)

        # CRITICAL FIX: Use flush() instead of commit() to get session ID without persisting
        # This allows us to rollback if Redis creation fails
        db.flush()
        db.refresh(session)

        # Best-effort Redis session cache: never block successful authentication.
        try:
            try:
                await redis_cache.create_session(
                    session_id=str(session.id),
                    user_id=str(user.id),
                    firebase_uid=user.firebase_uid,
                    metadata={
                        "ip_address": request.client.host if request.client else None,
                        "user_agent": request.headers.get("user-agent"),
                    },
                    ttl_seconds=432000,  # 5 days
                )
            except TypeError:
                # Legacy signature compatibility used by some test doubles.
                await redis_cache.create_session(
                    str(session.id),
                    str(user.id),
                    user.firebase_uid,
                    ttl=432000,
                )
        except Exception as redis_err:
            logger.warning(f"Redis create_session skipped: {redis_err}")

        # CRITICAL FIX: Commit DB session regardless of Redis cache availability.
        db.commit()

        # Set HttpOnly Cookie
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=str(session.id),
            httponly=True,
            secure=settings.SESSION_ENABLE_COOKIE_SECURE,
            samesite=settings.SESSION_COOKIE_SAMESITE,
            path="/",  # Important: ensure cookie is sent on all routes
            max_age=432000,  # 5 days
        )
        logger.info("Cookie set: %s=%s, path=/", SESSION_COOKIE_NAME, session.id)

        # Set X-Session-ID header for compatibility
        if (
            settings.APP_ENABLE_DEBUG
            and settings.APP_ENVIRONMENT.lower() != "production"
        ):
            response.headers["X-Session-ID"] = str(session.id)

        _apply_auth_security_headers(response)
        return {
            "valid": True,
            "session_id": str(session.id),
            "message": "Login successful",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
                "is_active": getattr(user, 'is_active', True),
                "created_at": user.created_at or now_sao_paulo(),
                "updated_at": user.updated_at or now_sao_paulo(),
                "last_login": getattr(user, 'firebase_last_sign_in', None),
                "photo_url": getattr(user, "firebase_photo_url", None),
            },
        }

    except HTTPException as exc:
        headers = _auth_security_headers()
        if exc.headers:
            headers.update(exc.headers)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=headers,
        )
    except ValueError as e:
        logger.warning(f"Invalid Firebase token: {e}")
        raise UnauthorizedError("Invalid or expired authentication token")
    except (ServiceUnavailableError, UnauthorizedError, ForbiddenError, ValidationError):
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()

        logger.error(f"Auth error: {e}\n{tb}")
        # Improve reliability by rolling back if session is active
        try:
            db.rollback()
        except Exception as rollback_err:
            logger.warning(f"Rollback failed during auth error recovery: {rollback_err}")

        raise ServiceUnavailableError("Authentication failed. Please try again later.")


@router.post(
    "/login",
    response_model=FirebaseTokenVerifyResponse,
    summary="Create session using Firebase token (compat)",
)
@auth_limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    payload: FirebaseTokenVerifyRequest,
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache),
):
    """Compatibility endpoint to create a session using Firebase ID token."""
    return await verify_firebase_token(
        request=request,
        response=response,
        payload=payload,
        db=db,
        redis_cache=redis_cache,
    )


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
        raise ValidationError("Invalid user_id UUID", field="user_id")

    session_id_from_request = _get_session_id_from_request(request) or getattr(
        request.state, "session_id", None
    )
    normalized_session_id = _normalize_session_uuid(session_id_from_request)
    if session_id_from_request and not normalized_session_id:
        raise ValidationError("Invalid session ID", field="session_id")
    if not normalized_session_id:
        raise UnauthorizedError("Session ID is required")

    from app.models.session import Session as SessionModel
    from app.models.user import User

    session_uuid = UUID(normalized_session_id)
    session_query = (
        db.query(SessionModel)
        .filter(
            SessionModel.id == session_uuid,
            SessionModel.user_id == user_uuid,
            SessionModel.is_active,
            SessionModel.revoked_at.is_(None),
        )
    )
    session = session_query.first()

    # Compatibility path for legacy prefixed session identifiers used in older
    # clients/tests (e.g. "session_<uuid>"), while keeping UUID-exact behavior
    # for canonical request values.
    if (
        session is None
        and session_id_from_request
        and str(session_id_from_request) != str(normalized_session_id)
    ):
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

    if not session:
        raise UnauthorizedError("Session expired")

    current_time = (
        now_sao_paulo_naive()
        if getattr(session.expires_at, "tzinfo", None) is None
        else now_sao_paulo()
    )
    if session.expires_at < current_time:
        raise UnauthorizedError("Session expired")

    # Re-check user status in database to avoid stale cache authorizing
    # deactivated accounts.
    db_user = db.query(User).filter(User.id == user_uuid).first()
    if not db_user:
        raise UnauthorizedError("User not found")
    if not getattr(db_user, "is_active", True):
        raise ForbiddenError("User account is inactive")

    if not isinstance(current_user, dict):
        current_user = {
            "id": str(getattr(current_user, "id", "")),
            "email": getattr(current_user, "email", None),
            "full_name": getattr(current_user, "full_name", None),
            "role": getattr(getattr(current_user, "role", None), "value", None)
            or getattr(current_user, "role", None)
            or "doctor",
            "created_at": getattr(current_user, "created_at", None),
            "updated_at": getattr(current_user, "updated_at", None),
            "last_login": getattr(current_user, "firebase_last_sign_in", None),
        }

    # Enrich user data with database timestamps if not in cache
    current_user["is_active"] = bool(db_user.is_active)
    if not current_user.get("created_at") or not current_user.get("updated_at"):
        current_user["created_at"] = db_user.created_at
        current_user["updated_at"] = db_user.updated_at
        current_user["last_login"] = db_user.firebase_last_sign_in

    return _serialize_session(
        session, current_user=current_user, current_session_id=normalized_session_id
    )

@router.delete("/logout", status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
async def logout(
    request: Request,
    response: Response,
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
    db=Depends(get_db),
):
    """Logout current session."""
    user_id = _extract_user_id(current_user)
    try:
        current_user_uuid = UUID(user_id)
    except (ValueError, TypeError):
        raise ValidationError("Invalid user_id UUID", field="user_id")

    session_id = _get_session_id_from_request(request)
    if session_id:
        normalized_session_id = _normalize_session_uuid(session_id)
        if not normalized_session_id:
            logger.warning(f"Invalid session_id format: {session_id}")
            raise ValidationError("Invalid session ID", field="session_id")
        session_uuid = UUID(normalized_session_id)

        await _invalidate_session_cache(redis_cache, normalized_session_id)

        # Also mark as revoked in DB with proper error handling
        from app.models.session import Session as SessionModel

        try:
            db_session = (
                db.query(SessionModel)
                .filter(
                    SessionModel.id == session_uuid,
                    SessionModel.user_id == current_user_uuid,
                )
                .first()
            )
            if db_session:
                db_session.is_active = False
                db_session.revoked_at = now_sao_paulo()
                db.commit()
            else:
                logger.info(
                    "Logout requested for non-owned or missing session %s by user %s",
                    normalized_session_id,
                    current_user_uuid,
                )
        except Exception as e:
            logger.error(f"Error revoking DB session: {e}")
            db.rollback()
            raise BusinessRuleError("Failed to revoke session")

    # Clear session cookie
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.SESSION_ENABLE_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )

    return {"message": "Logged out successfully", "success": True}


@router.delete("/logout-all", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def logout_all(
    request: Request,
    response: Response,
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
        deleted_count = await _invalidate_all_user_sessions_cache(redis_cache, firebase_uid)

    # Revoke all in DB with proper error handling
    from app.models.session import Session as SessionModel

    try:
        user_uuid = UUID(user_id)
        db.query(SessionModel).filter(
            SessionModel.user_id == user_uuid, SessionModel.is_active
        ).update(
            {SessionModel.is_active: False, SessionModel.revoked_at: now_sao_paulo()}
        )
        db.commit()
    except Exception as e:
        logger.error(f"Error revoking all DB sessions: {e}")
        db.rollback()
        raise BusinessRuleError("Failed to revoke all sessions")

    # Clear session cookie
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.SESSION_ENABLE_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )

    return {
        "message": "Logged out from all devices",
        "success": True,
        "sessions_deleted": deleted_count,
    }


@router.get("/health", include_in_schema=False)
@limiter.limit("120/minute")
async def auth_health(
    request: Request,
    db=Depends(get_db),
):
    """Legacy auth health endpoint used by compatibility tests/clients."""
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    redis_ok = False
    try:
        from app.api.v2.routers import users as users_router_module

        redis_client = await users_router_module._get_redis_client()
        if redis_client:
            ping_result = redis_client.ping()
            if hasattr(ping_result, "__await__"):
                ping_result = await ping_result
            redis_ok = bool(ping_result)
    except Exception:
        redis_ok = False

    services = {
        "database": db_ok,
        "redis": redis_ok,
        "firebase": None,
    }
    return {
        "status": "healthy" if db_ok and redis_ok else "degraded",
        "timestamp": now_sao_paulo().isoformat(),
        "services": services,
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
        BusinessRuleError: If token generation fails
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
        raise BusinessRuleError("CSRF token generation failed. Please contact administrator.")
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error generating CSRF token: {str(e)}")
        raise BusinessRuleError("Internal server error")


# ============================================================================
# Profile Management Endpoints
# ============================================================================


@router.put("/profile")
@limiter.limit("10/minute")
async def update_profile(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
):
    """
    Update current user's profile information.
    
    Accepts: full_name, email, phone, specialty
    """
    from app.models.user import User
    from pydantic import BaseModel, EmailStr
    from typing import Optional
    
    class ProfileUpdateRequest(BaseModel):
        email: Optional[EmailStr] = None
        full_name: Optional[str] = None
        phone: Optional[str] = None
        specialty: Optional[str] = None
    
    user_id = _extract_user_id(current_user)
    
    try:
        user_uuid = UUID(user_id)
    except (ValueError, TypeError):
        raise ValidationError("Invalid user_id UUID", field="user_id")
    
    # Parse request body
    body = await request.json()
    update_data = ProfileUpdateRequest(**body)
    
    # Get user from database
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise BusinessRuleError("User not found")
    
    # Update fields
    updated = False
    if update_data.full_name is not None:
        user.full_name = update_data.full_name
        updated = True
    if update_data.email is not None:
        # Check if email is already taken
        existing = db.query(User).filter(User.email == update_data.email, User.id != user_uuid).first()
        if existing:
            raise ValidationError("Email already in use", field="email")
        user.email = update_data.email
        updated = True
    
    # Store phone and specialty in firebase_custom_claims (or a dedicated field)
    claims = user.firebase_custom_claims or {}
    if update_data.phone is not None:
        claims["phone"] = update_data.phone
        updated = True
    if update_data.specialty is not None:
        claims["specialty"] = update_data.specialty
        updated = True
    
    if updated:
        user.firebase_custom_claims = claims
        user.updated_at = now_sao_paulo()
        db.commit()
        db.refresh(user)
    
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "phone": claims.get("phone"),
        "specialty": claims.get("specialty"),
        "avatar_url": claims.get("avatar_url"),
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


@router.put("/password")
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    current_user=Depends(get_current_user_from_session),
):
    """
    Change user password via Firebase.
    
    Note: This endpoint delegates to Firebase for password management.
    The client should reauthenticate with Firebase before calling this.
    """
    from pydantic import BaseModel
    
    class PasswordChangeRequest(BaseModel):
        new_password: str
    
    body = await request.json()
    password_data = PasswordChangeRequest(**body)
    
    firebase_uid = (
        current_user.get("firebase_uid")
        if isinstance(current_user, dict)
        else getattr(current_user, "firebase_uid", None)
    )
    
    if not firebase_uid:
        raise ValidationError("Firebase UID not found", field="firebase_uid")
    
    # Update password in Firebase
    try:
        from app.dependencies.auth_dependencies import _firebase_service
        
        if _firebase_service and hasattr(_firebase_service, "update_user"):
            await _firebase_service.update_user(
                firebase_uid,
                password=password_data.new_password
            )
        else:
            # Fallback to Firebase Admin SDK directly
            import firebase_admin.auth as firebase_auth
            firebase_auth.update_user(firebase_uid, password=password_data.new_password)
        
        logger.info(f"Password changed for user: {firebase_uid}")
        return {"message": "Password changed successfully", "success": True}
    
    except Exception as e:
        logger.error(f"Password change failed: {e}")
        raise BusinessRuleError("Failed to change password. Please try again.")


@router.post("/avatar")
@limiter.limit("5/minute")
async def upload_avatar(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
):
    """
    Upload user avatar image.
    
    Accepts multipart/form-data with 'file' field.
    Stores in local storage or cloud storage based on configuration.
    """
    from fastapi import UploadFile
    from app.models.user import User
    import os
    import hashlib
    
    user_id = _extract_user_id(current_user)
    
    try:
        user_uuid = UUID(user_id)
    except (ValueError, TypeError):
        raise ValidationError("Invalid user_id UUID", field="user_id")
    
    # Parse multipart form data
    form = await request.form()
    file: UploadFile = form.get("file")
    
    if not file:
        raise ValidationError("No file provided", field="file")
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/gif"]
    content_type = file.content_type or ""
    if content_type not in allowed_types:
        raise ValidationError(
            f"Invalid file type. Allowed: {', '.join(allowed_types)}",
            field="file"
        )
    
    # Read file content
    content = await file.read()
    
    # Validate file size (max 5MB)
    if len(content) > 5 * 1024 * 1024:
        raise ValidationError("File too large. Maximum size is 5MB", field="file")
    
    # Generate unique filename
    file_hash = hashlib.md5(content).hexdigest()[:12]
    ext = content_type.split("/")[-1]
    if ext == "jpeg":
        ext = "jpg"
    filename = f"avatar_{user_id}_{file_hash}.{ext}"
    
    # Save to uploads directory (create if needed)
    uploads_dir = os.path.join(settings.BASE_DIR if hasattr(settings, 'BASE_DIR') else ".", "uploads", "avatars")
    os.makedirs(uploads_dir, exist_ok=True)
    
    file_path = os.path.join(uploads_dir, filename)
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Generate URL (assuming static file serving is configured)
    avatar_url = f"/uploads/avatars/{filename}"
    
    # Update user's avatar_url in database
    user = db.query(User).filter(User.id == user_uuid).first()
    if user:
        claims = user.firebase_custom_claims or {}
        claims["avatar_url"] = avatar_url
        user.firebase_custom_claims = claims
        user.updated_at = now_sao_paulo()
        db.commit()
    
    logger.info(f"Avatar uploaded for user: {user_id}")
    
    return {"avatar_url": avatar_url, "success": True}
