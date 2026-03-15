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
    """Normalize user model attributes into the canonical runtime session-cache payload."""
    last_login = user.get_last_login() if hasattr(user, "get_last_login") else getattr(user, "last_login", getattr(user, "firebase_last_sign_in", None))
    photo_url = user.get_photo_url() if hasattr(user, "get_photo_url") else getattr(user, "photo_url", getattr(user, "firebase_photo_url", None))
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if getattr(user, "created_at", None) else None,
        "updated_at": user.updated_at.isoformat() if getattr(user, "updated_at", None) else None,
        "last_login": last_login.isoformat() if last_login else None,
        "photo_url": photo_url,
    }


def sanitize_cached_user_data(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Drop legacy runtime identity fields from cached user payloads before returning them."""
    sanitized = dict(user_data)
    sanitized.pop("firebase_uid", None)
    return sanitized


async def get_or_cache_user_data(
    *,
    redis_cache: Any,
    user_id: Optional[str] = None,
    fetch_user_by_id: Optional[Callable[[str], Awaitable[Optional[TUser]]]] = None,
) -> Dict[str, Any]:
    """Read user profile from cache or DB using the canonical ``user_id`` contract only."""
    canonical_user_id = str(user_id) if user_id not in (None, "") else None
    if not canonical_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session data",
        )

    if hasattr(redis_cache, "get_user_by_id"):
        user_data = await redis_cache.get_user_by_id(canonical_user_id)
        if user_data:
            return sanitize_cached_user_data(user_data)

    user = None
    if fetch_user_by_id:
        user = await fetch_user_by_id(canonical_user_id)

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    user_data = serialize_user_data(user)

    canonical_user_id = resolve_canonical_user_id(user_data)
    if canonical_user_id and hasattr(redis_cache, "cache_user_data_by_user_id"):
        await redis_cache.cache_user_data_by_user_id(canonical_user_id, user_data, ttl=900)

    return user_data


def ensure_user_is_active(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate active user status for authenticated endpoints."""
    if not user_data.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return user_data
