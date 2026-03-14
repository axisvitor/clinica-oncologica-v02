"""
Shared helpers for loading and caching authenticated user data.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

from fastapi import HTTPException, status

TUser = TypeVar("TUser")


def resolve_canonical_user_id(user_data: Dict[str, Any]) -> Optional[str]:
    """Return the canonical authenticated user ID from mapping-style payloads."""
    user_id = user_data.get("id") or user_data.get("user_id")
    if user_id is None or user_id == "":
        return None
    return str(user_id)


def serialize_user_data(user: Any) -> Dict[str, Any]:
    """Normalize user model attributes into session-cache payload."""
    return {
        "id": str(user.id),
        "firebase_uid": user.firebase_uid,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if getattr(user, "created_at", None) else None,
        "updated_at": user.updated_at.isoformat() if getattr(user, "updated_at", None) else None,
        "last_login": user.firebase_last_sign_in.isoformat()
        if getattr(user, "firebase_last_sign_in", None)
        else None,
        "photo_url": getattr(user, "firebase_photo_url", None),
    }


async def get_or_cache_user_data(
    *,
    redis_cache: Any,
    user_id: Optional[str] = None,
    firebase_uid: Optional[str] = None,
    fetch_user_by_id: Optional[Callable[[str], Awaitable[Optional[TUser]]]] = None,
    fetch_user_by_uid: Optional[Callable[[str], Awaitable[Optional[TUser]]]] = None,
) -> Dict[str, Any]:
    """Read user profile from cache, fallback to DB/service and repopulate cache."""
    canonical_user_id = str(user_id) if user_id not in (None, "") else None

    if canonical_user_id and hasattr(redis_cache, "get_user_by_id"):
        user_data = await redis_cache.get_user_by_id(canonical_user_id)
        if user_data:
            return user_data

    if not canonical_user_id and firebase_uid and hasattr(redis_cache, "get_user_by_uid"):
        user_data = await redis_cache.get_user_by_uid(firebase_uid)
        if user_data:
            return user_data

    user = None
    if canonical_user_id and fetch_user_by_id:
        user = await fetch_user_by_id(canonical_user_id)
    elif firebase_uid and fetch_user_by_uid:
        user = await fetch_user_by_uid(firebase_uid)

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    user_data = serialize_user_data(user)

    canonical_user_id = resolve_canonical_user_id(user_data)
    if canonical_user_id and hasattr(redis_cache, "cache_user_data_by_user_id"):
        await redis_cache.cache_user_data_by_user_id(canonical_user_id, user_data, ttl=900)
    if user_data.get("firebase_uid") and hasattr(redis_cache, "cache_user_data"):
        await redis_cache.cache_user_data(user_data["firebase_uid"], user_data, ttl=900)

    return user_data


def ensure_user_is_active(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate active user status for authenticated endpoints."""
    if not user_data.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return user_data
