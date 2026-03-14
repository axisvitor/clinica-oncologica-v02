"""Session request contract helpers for auth dependencies."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import HTTPException, Request, status

from app.config import settings

from . import auth_session_cache

logger = logging.getLogger(__name__)

session_payload_to_user_data = auth_session_cache.session_payload_to_user_data


def resolve_request_session_id(
    *,
    session_cookie_id: Optional[str] = None,
    x_session_id: Optional[str] = None,
    authorization: Optional[str] = None,
    enable_cookie_priority: Optional[bool] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Resolve the canonical staff session ID from cookie-backed request state only."""
    _ = x_session_id, authorization, enable_cookie_priority, settings

    if session_cookie_id:
        return session_cookie_id, "cookie"

    return None, None


def apply_session_request_state(request: Request, *, session_id: str) -> None:
    """Persist resolved session ID onto request.state."""
    request.state.session_id = session_id


def apply_session_user_request_state(request: Request, *, user_data: Dict[str, Any]) -> None:
    """Persist resolved user identity onto request.state."""
    request.state.user_id = user_data.get("id") or user_data.get("user_id")
    request.state.user_role = user_data.get("role")


def enrich_user_permissions(
    user_data: Dict[str, Any],
    *,
    get_permissions_for_role: Callable[[str], List[str]],
) -> Dict[str, Any]:
    """Add role-derived permissions to the mapping-style session payload."""
    role = user_data.get("role", "doctor")
    user_data["permissions"] = get_permissions_for_role(role)
    return user_data


async def resolve_authenticated_session_user(
    *,
    request: Request,
    session_cookie_id: Optional[str],
    x_session_id: Optional[str],
    authorization: Optional[str],
    redis_cache: Any,
    get_permissions_for_role: Callable[[str], List[str]],
    validate_firebase_uid: Callable[[str], None],
    load_user_from_db_by_user_id: Callable[[str], Any],
    load_user_from_db_by_firebase_uid: Callable[[str], Any],
    load_user_from_db_by_session: Callable[[str], Any],
    serialize_user: Callable[[Any], Dict[str, Any]],
) -> Dict[str, Any]:
    """Resolve session-backed authentication while preserving the public request contract."""
    try:
        legacy_transports = []
        if x_session_id:
            legacy_transports.append("x-session-id")
        if authorization and authorization.startswith("Bearer "):
            legacy_transports.append("authorization")

        logger.debug(
            "Auth check - cookie: %s..., legacy_session_transports: %s",
            session_cookie_id[:8] if session_cookie_id else "None",
            legacy_transports or ["none"],
        )

        final_session_id, session_source = resolve_request_session_id(
            session_cookie_id=session_cookie_id,
            x_session_id=x_session_id,
            authorization=authorization,
        )

        if final_session_id:
            logger.debug("Session ID resolved from %s", session_source)
            apply_session_request_state(request, session_id=final_session_id)

        if not final_session_id:
            if legacy_transports:
                logger.warning(
                    "Rejected legacy session transport(s) for staff auth: %s",
                    ", ".join(legacy_transports),
                )
            else:
                logger.warning("Session cookie required for staff auth")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session cookie required",
                headers={"WWW-Authenticate": "Session"},
            )

        session_ttl = (
            getattr(settings, "SESSION_TTL_SECONDS", None)
            or getattr(settings, "FIREBASE_SESSION_TTL_SECONDS", None)
            or getattr(redis_cache, "session_ttl", 86400)
        )

        user_data, resolution_mode = await auth_session_cache.resolve_session_user_data(
            session_id=final_session_id,
            redis_cache=redis_cache,
            redis_operation_timeout=settings.REDIS_OPERATION_TIMEOUT,
            session_ttl=session_ttl,
            validate_firebase_uid=validate_firebase_uid,
            load_user_from_db_by_user_id=load_user_from_db_by_user_id,
            load_user_from_db_by_firebase_uid=load_user_from_db_by_firebase_uid,
            load_user_from_db_by_session=load_user_from_db_by_session,
            serialize_user=serialize_user,
        )

        enriched_user_data = enrich_user_permissions(
            user_data,
            get_permissions_for_role=get_permissions_for_role,
        )
        apply_session_user_request_state(request, user_data=enriched_user_data)

        role = enriched_user_data.get("role", "doctor")
        if resolution_mode == "fallback":
            logger.debug(
                "Session validated via PostgreSQL fallback for user: %s (role: %s)",
                enriched_user_data.get("email"),
                role,
            )
        else:
            logger.debug(
                "Session validated for user: %s (role: %s)",
                enriched_user_data.get("email"),
                role,
            )

        return enriched_user_data

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Session validation failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Session validation failed: {str(exc)}",
            headers={"WWW-Authenticate": "Session"},
        )
