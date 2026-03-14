"""
Shared session-auth utilities for V2 API routers.
"""

from __future__ import annotations

import inspect
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy import select

from app.models.user import User
from app.api.v2.user_cache_shared import get_or_cache_user_data, ensure_user_is_active


CANONICAL_SESSION_USER_FIELDS = {
    "email": "email",
    "full_name": "full_name",
    "role": "role",
    "is_active": "is_active",
    "created_at": "created_at",
    "updated_at": "updated_at",
    "last_login": "last_login",
    "photo_url": "photo_url",
    "firebase_uid": "firebase_uid",
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
    """
    Resolve session ID from supported sources in priority order:
    1. Authorization: Bearer <session_id>
    2. X-Session-ID header
    3. session_id cookie
    4. session_id query param (lowest-priority websocket/browser fallback)
    """
    final_session_id = None

    if authorization and authorization.startswith("Bearer "):
        final_session_id = authorization.split(" ")[1]

    if not final_session_id and x_session_id:
        final_session_id = x_session_id

    if not final_session_id and session_cookie_id:
        final_session_id = session_cookie_id

    if not final_session_id and query_session_id:
        final_session_id = query_session_id

    return final_session_id


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


async def get_user_data_from_session(
    *,
    session_id: str,
    db: Any,
    redis_cache: Any,
) -> Dict[str, Any]:
    """
    Validate session and load active user data from cache/database.
    """
    session_data = await redis_cache.get_session(session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    embedded_user = extract_canonical_user_from_session(session_data)
    if embedded_user:
        return ensure_user_is_active(embedded_user)

    user_id = resolve_canonical_session_user_id(session_data)
    firebase_uid = session_data.get("firebase_uid")
    if not user_id and not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session data",
        )

    async def _fetch_user_by_id(resolved_user_id: str):
        stmt = select(User).where(User.id == resolved_user_id)
        result = db.execute(stmt)
        if inspect.isawaitable(result):
            result = await result
        return result.scalar_one_or_none()

    async def _fetch_user_by_uid(uid: str):
        stmt = select(User).where(User.firebase_uid == uid)
        result = db.execute(stmt)
        if inspect.isawaitable(result):
            result = await result
        return result.scalar_one_or_none()

    user_data = await get_or_cache_user_data(
        user_id=user_id,
        firebase_uid=firebase_uid,
        redis_cache=redis_cache,
        fetch_user_by_id=_fetch_user_by_id,
        fetch_user_by_uid=_fetch_user_by_uid,
    )
    return ensure_user_is_active(user_data)
