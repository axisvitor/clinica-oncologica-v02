from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID
import inspect
import logging
import uuid

from fastapi import APIRouter, Depends, status, Request, Response, HTTPException
from fastapi.responses import JSONResponse
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
    get_current_user_from_session,
    get_redis_cache,
)
from app.utils.rate_limiter import limiter, auth_limiter
from app.schemas.v2.auth import (
    LocalLoginRequest,
    LocalLoginResponse,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetConfirmResponse,
    PasswordResetRequest,
    PasswordResetRequestResponse,
    SessionV2Response,
)
from app.config import settings
from app.repositories.user import UserRepository
from app.services.auth import AuthService, LocalAuthFailure
from app.services.password_reset_service import PasswordResetFailure, PasswordResetService
from app.schemas.admin_validation import validate_password_strength
from app.utils.auth_helpers import extract_user_id as _extract_user_id
from app.utils.security import get_password_hash, verify_password
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


def _get_request_id(request: Request) -> Optional[str]:
    """Best-effort request correlation ID used in auth diagnostics."""
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        return request_id

    monitoring_state = getattr(request.state, "monitoring", None)
    if isinstance(monitoring_state, dict):
        monitoring_request_id = monitoring_state.get("request_id")
        if monitoring_request_id:
            return monitoring_request_id

    header_request_id = request.headers.get("X-Request-ID")
    if header_request_id:
        request.state.request_id = header_request_id
        return header_request_id

    generated_request_id = f"auth-{uuid.uuid4().hex}"
    request.state.request_id = generated_request_id
    return generated_request_id



def _auth_error_content(request: Request, *, error: str, message: str) -> dict[str, Any]:
    """Standardized auth failure payload with stable diagnostics."""
    return {
        "error": error,
        "message": message,
        "request_id": _get_request_id(request),
        "timestamp": now_sao_paulo().isoformat(),
    }



def _serialize_authenticated_user(user) -> dict[str, Any]:
    """Normalize authenticated-user metadata for login/session responses."""
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    last_login = user.get_last_login() if hasattr(user, "get_last_login") else getattr(user, "last_login", None)
    photo_url = user.get_photo_url() if hasattr(user, "get_photo_url") else getattr(user, "photo_url", None)
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": role,
        "is_active": bool(getattr(user, "is_active", False)),
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": last_login,
        "photo_url": photo_url,
    }



async def _call_cache_method(method, *args, **kwargs):
    result = method(*args, **kwargs)
    if inspect.isawaitable(result):
        result = await result
    return result



async def _create_canonical_session_cache_entry(
    *,
    redis_cache,
    session_id: str,
    user_payload: dict[str, Any],
    remember_me: bool,
    ttl_seconds: int,
) -> None:
    """Persist the canonical session payload in Redis, supporting legacy cache adapters."""
    metadata = {
        "session_id": session_id,
        "email": user_payload["email"],
        "full_name": user_payload.get("full_name"),
        "role": user_payload["role"],
        "is_active": user_payload["is_active"],
        "created_at": user_payload.get("created_at").isoformat()
        if user_payload.get("created_at")
        else None,
        "updated_at": user_payload.get("updated_at").isoformat()
        if user_payload.get("updated_at")
        else None,
        "last_login": user_payload.get("last_login").isoformat()
        if user_payload.get("last_login")
        else None,
        "remember_me": remember_me,
        "max_age_seconds": ttl_seconds,
    }
    creation_attempts = [
        lambda: _call_cache_method(
            redis_cache.create_session,
            session_id=session_id,
            user_id=user_payload["id"],
            metadata=metadata,
            ttl_seconds=ttl_seconds,
        ),
        lambda: _call_cache_method(
            redis_cache.create_session,
            session_id=session_id,
            user_id=user_payload["id"],
            metadata=metadata,
            ttl=ttl_seconds,
        ),
        lambda: _call_cache_method(
            redis_cache.create_session,
            session_id,
            user_payload["id"],
            None,
            metadata=metadata,
            ttl=ttl_seconds,
        ),
        lambda: _call_cache_method(
            redis_cache.create_session,
            session_id,
            user_payload["id"],
            None,
            ttl=ttl_seconds,
        ),
    ]

    last_error: Optional[Exception] = None
    for attempt in creation_attempts:
        try:
            created = await attempt()
            if created is False:
                raise RuntimeError("Redis create_session returned false")
            return
        except TypeError as exc:
            last_error = exc
            continue
        except Exception as exc:
            raise RuntimeError("Redis session creation failed") from exc

    raise RuntimeError("Redis session creation failed") from last_error



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
    """Extract the canonical session ID from cookie-backed request state only."""
    return request.cookies.get(SESSION_COOKIE_NAME) or request.cookies.get("session_id")


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


async def _invalidate_all_user_sessions_cache(redis_cache, identity: Optional[str]) -> int:
    """
    Invalidate all sessions for a canonical user identity in cache.

    The current session-first contract keys global revocation to `user_id`, while
    compatibility cache adapters may still match legacy `firebase_uid` values.
    """
    if not redis_cache or not identity:
        return 0

    invalidate_all = getattr(redis_cache, "invalidate_all_user_sessions", None)
    if callable(invalidate_all):
        try:
            result = invalidate_all(identity)
            if hasattr(result, "__await__"):
                result = await result
            return int(result or 0)
        except Exception as exc:
            logger.warning("Cache bulk session invalidation failed: %s", exc)
            return 0

    delete_pattern = getattr(redis_cache, "delete_pattern", None)
    if callable(delete_pattern):
        try:
            result = delete_pattern(f"session:*{identity}*")
            if hasattr(result, "__await__"):
                result = await result
            return int(result) if isinstance(result, int) else 0
        except Exception as exc:
            logger.warning("Cache delete_pattern fallback failed: %s", exc)
            return 0

    logger.debug("No compatible cache method found for bulk session invalidation")
    return 0



@router.post(
    "/login",
    response_model=LocalLoginResponse,
    summary="Login using local email/password credentials",
)
@auth_limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    payload: LocalLoginRequest,
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache),
):
    """Canonical first-party login endpoint backed by local credentials."""
    auth_service = AuthService(db, UserRepository(db), redis_cache)
    client_ip = request.client.host if request.client else None
    logger.info("Local login received for email=%s from ip=%s", str(payload.email), client_ip)

    try:
        auth_result = await auth_service.authenticate_local_credentials(
            email=str(payload.email),
            password=payload.password,
            remember_me=payload.remember_me,
            client_ip=client_ip,
        )

        user = auth_result.user
        ttl_seconds = AuthService.get_local_session_ttl_seconds(auth_result.remember_me)
        expires_at = now_sao_paulo() + timedelta(seconds=ttl_seconds)

        from app.models.session import Session as SessionModel

        session = SessionModel(
            user_id=user.id,
            session_token=uuid.uuid4().hex,
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent"),
            last_activity=now_sao_paulo(),
            expires_at=expires_at,
            is_active=True,
        )
        db.add(session)
        db.flush()
        db.refresh(session)
        logger.info(
            "Local login progress: session row prepared for user=%s session=%s",
            user.email,
            str(session.id),
        )

        user_payload = _serialize_authenticated_user(user)

        await _create_canonical_session_cache_entry(
            redis_cache=redis_cache,
            session_id=str(session.id),
            user_payload=user_payload,
            remember_me=auth_result.remember_me,
            ttl_seconds=ttl_seconds,
        )
        logger.info(
            "Local login progress: cache entry prepared for user=%s session=%s",
            user.email,
            str(session.id),
        )

        db.commit()
        logger.info(
            "Local login progress: db commit complete for user=%s session=%s",
            user.email,
            str(session.id),
        )

        response_payload = LocalLoginResponse.model_validate(
            {
                "valid": True,
                "message": "Login successful",
                "session_id": str(session.id),
                "user_id": str(user.id),
                "expires_at": expires_at,
                "remember_me": auth_result.remember_me,
                "user": user_payload,
            }
        ).model_dump(mode="json")
        response.status_code = status.HTTP_200_OK
        _apply_auth_security_headers(response)
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=str(session.id),
            httponly=True,
            secure=settings.SESSION_ENABLE_COOKIE_SECURE,
            samesite=settings.SESSION_COOKIE_SAMESITE,
            path="/",
            max_age=ttl_seconds,
        )
        logger.info(
            "Local login progress: response ready for user=%s session=%s",
            user.email,
            str(session.id),
        )
        return response_payload

    except LocalAuthFailure as exc:
        try:
            if exc.commit_required:
                db.commit()
            else:
                db.rollback()
        except Exception as db_exc:
            logger.warning("Failed to finalize local-auth failure state: %s", db_exc)
            db.rollback()

        extra_headers = {"WWW-Authenticate": "Session"} if exc.status_code == status.HTTP_401_UNAUTHORIZED else None
        return _auth_json_response(
            status_code=exc.status_code,
            content=_auth_error_content(
                request,
                error=exc.error_code,
                message=exc.message,
            ),
            extra_headers=extra_headers,
        )
    except Exception as exc:
        logger.error("Local login failed: %s", exc, exc_info=True)
        db.rollback()
        return _auth_json_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_auth_error_content(
                request,
                error="AUTH_SERVICE_UNAVAILABLE",
                message="Authentication failed. Please try again later.",
            ),
        )


@router.post(
    "/password/reset-request",
    response_model=PasswordResetRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a password reset email",
)
@auth_limiter.limit("3/hour")
async def request_password_reset(
    request: Request,
    payload: PasswordResetRequest,
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache),
):
    """Start the public password recovery flow without enumerating accounts."""
    reset_service = PasswordResetService(db, redis_cache=redis_cache)

    try:
        await reset_service.request_password_reset(str(payload.email))
        return _auth_json_response(
            status_code=status.HTTP_202_ACCEPTED,
            content=PasswordResetRequestResponse().model_dump(),
        )
    except PasswordResetFailure as exc:
        db.rollback()
        return _auth_json_response(
            status_code=exc.status_code,
            content=_auth_error_content(
                request,
                error=exc.error_code,
                message=exc.message,
            ),
        )
    except Exception as exc:
        logger.error("Password reset request failed: %s", exc, exc_info=True)
        db.rollback()
        return _auth_json_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_auth_error_content(
                request,
                error="AUTH_PASSWORD_RESET_SERVICE_UNAVAILABLE",
                message="Password reset failed. Please try again later.",
            ),
        )


@router.post(
    "/password/reset-confirm",
    response_model=PasswordResetConfirmResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm a password reset token",
)
@auth_limiter.limit("5/hour")
async def confirm_password_reset(
    request: Request,
    payload: PasswordResetConfirm,
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache),
):
    """Complete password reset, migrate to local auth, and revoke active sessions."""
    reset_service = PasswordResetService(db, redis_cache=redis_cache)

    try:
        await reset_service.confirm_password_reset(
            token=payload.token,
            new_password=payload.new_password,
        )
        return _auth_json_response(
            status_code=status.HTTP_200_OK,
            content=PasswordResetConfirmResponse().model_dump(),
        )
    except PasswordResetFailure as exc:
        db.rollback()
        request_id = _get_request_id(request)
        logger.info(
            "Password reset confirmation rejected",
            extra={
                "request_id": request_id,
                "outcome_class": "denied",
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "token_consumption_reason": getattr(exc, "reason", "unspecified"),
            },
        )
        return _auth_json_response(
            status_code=exc.status_code,
            content=_auth_error_content(
                request,
                error=exc.error_code,
                message=exc.message,
            ),
        )
    except Exception as exc:
        logger.error("Password reset confirmation failed: %s", exc, exc_info=True)
        db.rollback()
        return _auth_json_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_auth_error_content(
                request,
                error="AUTH_PASSWORD_RESET_SERVICE_UNAVAILABLE",
                message="Password reset failed. Please try again later.",
            ),
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
            "last_login": current_user.get_last_login() if hasattr(current_user, "get_last_login") else getattr(current_user, "last_login", None),
        }

    # Enrich user data with database timestamps if not in cache
    current_user["is_active"] = bool(db_user.is_active)
    if not current_user.get("created_at") or not current_user.get("updated_at"):
        current_user["created_at"] = db_user.created_at
        current_user["updated_at"] = db_user.updated_at
        current_user["last_login"] = db_user.get_last_login() if hasattr(db_user, "get_last_login") else getattr(db_user, "last_login", None)

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

    deleted_count = await _invalidate_all_user_sessions_cache(redis_cache, user_id)

    # Revoke all in DB with proper error handling
    from app.models.session import Session as SessionModel

    try:
        user_uuid = UUID(user_id)
        db_deleted_count = (
            db.query(SessionModel)
            .filter(SessionModel.user_id == user_uuid, SessionModel.is_active)
            .update(
                {SessionModel.is_active: False, SessionModel.revoked_at: now_sao_paulo()}
            )
        )
        db.commit()
    except Exception as e:
        logger.error(f"Error revoking all DB sessions: {e}")
        db.rollback()
        raise BusinessRuleError("Failed to revoke all sessions")

    # The runtime source of truth for session count is DB state; Redis may be empty in
    # legitimate bootstrap conditions even when DB had active sessions.
    sessions_deleted = max(int(deleted_count or 0), int(db_deleted_count or 0))

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
        "sessions_deleted": sessions_deleted,
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
    
    if update_data.phone is not None:
        if hasattr(user, "set_phone"):
            user.set_phone(update_data.phone)
        else:
            user.phone = update_data.phone
        updated = True
    if update_data.specialty is not None:
        if hasattr(user, "set_specialty"):
            user.set_specialty(update_data.specialty)
            if update_data.specialty and hasattr(user, "get_specialties_data") and hasattr(user, "set_specialties_data"):
                existing_specialties = user.get_specialties_data()
                if not existing_specialties:
                    user.set_specialties_data([update_data.specialty])
        else:
            user.specialty = update_data.specialty
        updated = True

    if updated:
        user.updated_at = now_sao_paulo()
        db.commit()
        db.refresh(user)

    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.get_phone() if hasattr(user, "get_phone") else getattr(user, "phone", None),
        "specialty": user.get_specialty() if hasattr(user, "get_specialty") else getattr(user, "specialty", None),
        "avatar_url": user.get_avatar_url() if hasattr(user, "get_avatar_url") else getattr(user, "avatar_url", None),
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


@router.put("/password")
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    response: Response,
    payload: PasswordChangeRequest,
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
    db=Depends(get_db),
):
    """Change the current user's password using first-party credentials only."""
    from app.models.session import Session as SessionModel
    from app.models.user import AuthProvider, User

    user_id = _extract_user_id(current_user)
    try:
        user_uuid = UUID(user_id)
    except (ValueError, TypeError):
        return _auth_json_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=_auth_error_content(
                request,
                error="AUTH_SESSION_INVALID",
                message="Invalid or expired session.",
            ),
            extra_headers={"WWW-Authenticate": "Session"},
        )

    user = db.query(User).filter(User.id == user_uuid).first()
    if user is None:
        return _auth_json_response(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_auth_error_content(
                request,
                error="AUTH_USER_NOT_FOUND",
                message="User not found.",
            ),
        )

    if not getattr(user, "is_active", False):
        return _auth_json_response(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_auth_error_content(
                request,
                error="AUTH_ACCOUNT_INACTIVE",
                message="Account is inactive.",
            ),
        )

    if not getattr(user, "hashed_password", None):
        return _auth_json_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_auth_error_content(
                request,
                error="AUTH_PASSWORD_CHANGE_PASSWORD_NOT_SET",
                message="Password change requires a local password. Use password recovery instead.",
            ),
        )

    if not verify_password(payload.current_password, user.hashed_password):
        return _auth_json_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_auth_error_content(
                request,
                error="AUTH_PASSWORD_CURRENT_PASSWORD_INVALID",
                message="Current password is incorrect.",
            ),
        )

    if verify_password(payload.new_password, user.hashed_password):
        return _auth_json_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_auth_error_content(
                request,
                error="AUTH_PASSWORD_UNCHANGED",
                message="New password must be different from the current password.",
            ),
        )

    try:
        validate_password_strength(payload.new_password)
    except ValueError:
        return _auth_json_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_auth_error_content(
                request,
                error="AUTH_PASSWORD_WEAK",
                message="Password does not meet security requirements.",
            ),
        )

    now = now_sao_paulo()

    try:
        user.hashed_password = get_password_hash(payload.new_password)
        user.auth_provider = AuthProvider.LOCAL
        user.force_change_password = False
        user.last_password_change = now
        user.failed_login_attempts = 0
        user.is_locked = False
        user.locked_until = None
        user.updated_at = now
        db.add(user)
        db.flush()

        db.query(SessionModel).filter(
            SessionModel.user_id == user_uuid,
            SessionModel.is_active,
        ).update(
            {
                SessionModel.is_active: False,
                SessionModel.revoked_at: now,
                SessionModel.revocation_reason: "password_change",
            },
            synchronize_session=False,
        )

        await _invalidate_all_user_sessions_cache(redis_cache, str(user.id))
        db.commit()
    except Exception as exc:
        logger.error("Password change failed for user %s: %s", user.id, exc, exc_info=True)
        db.rollback()
        return _auth_json_response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_auth_error_content(
                request,
                error="AUTH_PASSWORD_CHANGE_FAILED",
                message="Password change failed. Please try again later.",
            ),
        )

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.SESSION_ENABLE_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )

    logger.info("Password changed and active sessions revoked for user %s", user.id)
    return {"message": "Password changed successfully", "success": True}


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
        if hasattr(user, "set_avatar_url"):
            user.set_avatar_url(avatar_url)
        else:
            user.avatar_url = avatar_url
        user.updated_at = now_sao_paulo()
        db.commit()
    
    logger.info(f"Avatar uploaded for user: {user_id}")
    
    return {"avatar_url": avatar_url, "success": True}
