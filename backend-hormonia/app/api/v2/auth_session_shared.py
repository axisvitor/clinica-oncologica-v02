"""
Shared session-auth utilities for V2 API routers.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select

from app.api.v2.user_cache_shared import ensure_user_is_active, serialize_user_data
from app.dependencies import auth_session_cache
from app.models.session import Session as SessionModel
from app.models.user import User
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

CANONICAL_SESSION_USER_FIELDS = {
    "email": "email",
    "full_name": "full_name",
    "role": "role",
    "is_active": "is_active",
    "created_at": "created_at",
    "updated_at": "updated_at",
    "last_login": "last_login",
    "photo_url": "photo_url",
}


def resolve_canonical_session_user_id(session_data: Dict[str, Any]) -> Optional[str]:
    """Return the canonical authenticated user ID from session payload aliases."""
    user_id = session_data.get("id") or session_data.get("user_id")
    if user_id is None or user_id == "":
        return None
    return str(user_id)


def resolve_session_id(
    *,
    authorization: Optional[str] = None,
    x_session_id: Optional[str] = None,
    session_cookie_id: Optional[str] = None,
    query_session_id: Optional[str] = None,
) -> Optional[str]:
    """Resolve the canonical staff session ID from cookie-backed request state only."""
    _ = authorization, x_session_id, query_session_id
    return session_cookie_id or None


def extract_canonical_user_from_session(session_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return embedded canonical user envelope when present in the session payload."""
    user_id = resolve_canonical_session_user_id(session_data)
    email = session_data.get("email")
    role = session_data.get("role")
    is_active = session_data.get("is_active")

    if not user_id or email is None or role is None or is_active is None:
        return None

    embedded_user = {
        "id": user_id,
        **{
            target_key: session_data.get(source_key)
            for source_key, target_key in CANONICAL_SESSION_USER_FIELDS.items()
        },
    }
    return embedded_user


async def _execute_scalar_one_or_none(db: Any, stmt: Any) -> Optional[User]:
    """Execute a sync or async SQLAlchemy statement and return one scalar result."""
    result = db.execute(stmt)
    if inspect.isawaitable(result):
        result = await result
    return result.scalar_one_or_none()


async def _load_user_from_db_by_session(db: Any, session_id: str) -> Optional[User]:
    """Fetch the user for an active, unrevoked, unexpired DB session row."""
    if not session_id or not isinstance(session_id, str):
        logger.warning("Invalid session ID value for shared session fallback lookup")
        return None

    base_stmt = (
        select(User)
        .join(SessionModel, SessionModel.user_id == User.id)
        .where(SessionModel.is_active.is_(True))
        .where(SessionModel.revoked_at.is_(None))
        .where(SessionModel.expires_at > now_sao_paulo())
    )

    try:
        session_uuid = UUID(session_id)
        stmt = base_stmt.where(SessionModel.id == session_uuid)
    except (TypeError, ValueError):
        stmt = base_stmt.where(SessionModel.session_token == session_id)

    return await _execute_scalar_one_or_none(db, stmt)


async def _load_authoritative_user_data_from_session(
    *,
    session_id: str,
    db: Any,
    diagnostic_context: str,
) -> Dict[str, Any]:
    """Load canonical user data after DB session-state validation."""
    try:
        user = await _load_user_from_db_by_session(db, session_id)
    except asyncio.TimeoutError:
        logger.error(
            "Database timeout during %s for shared session %s...",
            diagnostic_context,
            session_id[:8],
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Please try again.",
        )
    except asyncio.CancelledError:
        logger.warning(
            "Database query cancelled during %s for shared session %s...",
            diagnostic_context,
            session_id[:8],
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Please try again.",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Database error during %s for shared session %s... (class=%s)",
            diagnostic_context,
            session_id[:8],
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Please try again.",
        )

    if not user:
        logger.warning(
            "Invalid or expired shared session during %s: %s...",
            diagnostic_context,
            session_id[:8],
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    return ensure_user_is_active(serialize_user_data(user))


async def _maybe_rehydrate_shared_session_cache(
    *,
    session_id: str,
    redis_cache: Any,
    user_data: Dict[str, Any],
) -> None:
    """Best-effort Redis rehydration for direct helper cache misses/errors."""
    await auth_session_cache.cache_user_data_by_identity(redis_cache, user_data, ttl=900)
    await auth_session_cache.rehydrate_session_cache(
        redis_cache,
        session_id=session_id,
        user_data=user_data,
        session_ttl=getattr(redis_cache, "session_ttl", 86400),
    )


async def get_user_data_from_session(
    *,
    session_id: str,
    db: Any,
    redis_cache: Any,
) -> Dict[str, Any]:
    """
    Validate session and load active user data from the DB-authoritative session row.
    """
    session_data = None
    resolution_mode = "redis"

    try:
        session_data = await redis_cache.get_session(session_id)
    except asyncio.TimeoutError:
        logger.warning(
            "Redis timeout for shared session %s..., falling back to PostgreSQL",
            session_id[:8],
        )
        resolution_mode = "fallback"
    except Exception as exc:
        logger.error(
            "Redis error for shared session %s... (class=%s). Falling back to PostgreSQL",
            session_id[:8],
            type(exc).__name__,
        )
        resolution_mode = "fallback"

    if not session_data:
        if resolution_mode == "redis":
            logger.warning(
                "Shared session cache miss for %s..., falling back to PostgreSQL",
                session_id[:8],
            )
        resolution_mode = "fallback"

    user_data = await _load_authoritative_user_data_from_session(
        session_id=session_id,
        db=db,
        diagnostic_context=(
            "cache_miss_fallback" if resolution_mode == "fallback" else "cache_hit_validation"
        ),
    )

    if resolution_mode == "fallback":
        await _maybe_rehydrate_shared_session_cache(
            session_id=session_id,
            redis_cache=redis_cache,
            user_data=user_data,
        )

    return user_data
