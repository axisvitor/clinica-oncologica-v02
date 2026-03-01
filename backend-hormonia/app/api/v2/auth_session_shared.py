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


def resolve_session_id(
    *,
    authorization: Optional[str] = None,
    x_session_id: Optional[str] = None,
    session_cookie_id: Optional[str] = None,
) -> Optional[str]:
    """
    Resolve session ID from supported sources in priority order:
    1. Authorization: Bearer <session_id>
    2. X-Session-ID header
    3. session_id cookie
    """
    final_session_id = None

    if authorization and authorization.startswith("Bearer "):
        final_session_id = authorization.split(" ")[1]

    if not final_session_id and x_session_id:
        final_session_id = x_session_id

    if not final_session_id and session_cookie_id:
        final_session_id = session_cookie_id

    return final_session_id


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

    firebase_uid = session_data.get("firebase_uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session data",
        )

    async def _fetch_user_by_uid(uid: str):
        stmt = select(User).where(User.firebase_uid == uid)
        result = db.execute(stmt)
        if inspect.isawaitable(result):
            result = await result
        return result.scalar_one_or_none()

    user_data = await get_or_cache_user_data(
        firebase_uid=firebase_uid,
        redis_cache=redis_cache,
        fetch_user_by_uid=_fetch_user_by_uid,
    )
    return ensure_user_is_active(user_data)
