"""
Shared helpers for loading and caching authenticated user data.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

from fastapi import HTTPException, status

TUser = TypeVar("TUser")


def serialize_user_data(user: Any) -> Dict[str, Any]:
    """Normalize user model attributes into session-cache payload."""
    return {
        "id": str(user.id),
        "firebase_uid": user.firebase_uid,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "is_active": user.is_active,
    }


async def get_or_cache_user_data(
    *,
    firebase_uid: str,
    redis_cache: Any,
    fetch_user_by_uid: Callable[[str], Awaitable[Optional[TUser]]],
) -> Dict[str, Any]:
    """Read user profile from cache, fallback to DB/service and repopulate cache."""
    user_data = await redis_cache.get_user_by_uid(firebase_uid)
    if user_data:
        return user_data

    user = await fetch_user_by_uid(firebase_uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    user_data = serialize_user_data(user)
    await redis_cache.cache_user_data(firebase_uid, user_data, ttl=900)
    return user_data


def ensure_user_is_active(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate active user status for authenticated endpoints."""
    if not user_data.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return user_data
