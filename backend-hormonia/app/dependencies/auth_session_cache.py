"""Session cache hydration and fallback helpers for auth dependencies."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple, TypeVar

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

TUser = TypeVar("TUser")


def resolve_canonical_user_id(identity_payload: Dict[str, Any]) -> Optional[str]:
    """Return the canonical authenticated user ID from mapping-style payloads."""
    user_id = identity_payload.get("id") or identity_payload.get("user_id")
    if user_id is None or user_id == "":
        return None
    return str(user_id)


def serialize_user_data(user: Any) -> Dict[str, Any]:
    """Normalize a user model into the canonical auth/session cache payload."""
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


def session_payload_to_user_data(session_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return canonical embedded user data when the session payload already carries it."""
    user_id = resolve_canonical_user_id(session_data)
    email = session_data.get("email")
    role = session_data.get("role")
    is_active = session_data.get("is_active")

    if not user_id or email is None or role is None or is_active is None:
        return None

    return {
        "id": user_id,
        "firebase_uid": session_data.get("firebase_uid"),
        "email": email,
        "full_name": session_data.get("full_name"),
        "role": role,
        "is_active": bool(is_active),
        "created_at": session_data.get("created_at"),
        "updated_at": session_data.get("updated_at"),
        "last_login": session_data.get("last_login"),
        "photo_url": session_data.get("photo_url"),
    }


async def cache_user_data_by_identity(
    redis_cache: Any,
    user_data: Dict[str, Any],
    ttl: int = 900,
) -> None:
    """Best-effort cache hydration for canonical user_id and compatibility firebase_uid keys."""
    user_id = resolve_canonical_user_id(user_data)
    firebase_uid = user_data.get("firebase_uid")

    if user_id and hasattr(redis_cache, "cache_user_data_by_user_id"):
        try:
            await redis_cache.cache_user_data_by_user_id(user_id, user_data, ttl=ttl)
        except Exception as exc:
            logger.warning("Failed to cache user data by user_id %s: %s", user_id, exc)

    if firebase_uid and hasattr(redis_cache, "cache_user_data"):
        try:
            await redis_cache.cache_user_data(firebase_uid, user_data, ttl=ttl)
        except Exception as exc:
            logger.warning("Failed to cache user data by firebase_uid %s: %s", firebase_uid, exc)


def session_cache_metadata_from_user_data(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Return canonical session cache metadata without leaking secrets."""
    return {
        "session_id": None,
        "email": user_data.get("email"),
        "full_name": user_data.get("full_name"),
        "role": user_data.get("role"),
        "is_active": user_data.get("is_active"),
        "created_at": user_data.get("created_at"),
        "updated_at": user_data.get("updated_at"),
        "last_login": user_data.get("last_login"),
        "photo_url": user_data.get("photo_url"),
    }


async def rehydrate_session_cache(
    redis_cache: Any,
    *,
    session_id: str,
    user_data: Dict[str, Any],
    session_ttl: int,
) -> None:
    """Best-effort Redis session rehydration on fallback DB lookups."""
    if not hasattr(redis_cache, "create_session"):
        return

    metadata = session_cache_metadata_from_user_data(user_data)
    metadata["session_id"] = session_id
    metadata["max_age_seconds"] = session_ttl

    try:
        created = await redis_cache.create_session(
            session_id=session_id,
            user_id=resolve_canonical_user_id(user_data),
            firebase_uid=user_data.get("firebase_uid"),
            metadata=metadata,
            ttl=session_ttl,
        )
        if created is False:
            logger.warning(
                "Failed to rehydrate session cache for fallback session %s...",
                session_id[:8],
            )
    except TypeError:
        try:
            await redis_cache.create_session(
                session_id,
                resolve_canonical_user_id(user_data),
                user_data.get("firebase_uid"),
                metadata=metadata,
                ttl=session_ttl,
            )
        except Exception as exc:
            logger.warning(
                "Failed to rehydrate session cache for fallback session %s...: %s",
                session_id[:8],
                exc,
            )
    except Exception as exc:
        logger.warning(
            "Failed to rehydrate session cache for fallback session %s...: %s",
            session_id[:8],
            exc,
        )


async def _lookup_session_identity_user_data(
    *,
    session_id: str,
    session_data: Dict[str, Any],
    redis_cache: Any,
    redis_operation_timeout: float,
    validate_firebase_uid: Callable[[str], None],
    load_user_from_db_by_user_id: Callable[[str], Awaitable[Optional[TUser]]],
    load_user_from_db_by_firebase_uid: Callable[[str], Awaitable[Optional[TUser]]],
    serialize_user: Callable[[TUser], Dict[str, Any]],
) -> Dict[str, Any]:
    user_data = session_payload_to_user_data(session_data)
    if user_data:
        return user_data

    user_id = resolve_canonical_user_id(session_data)
    firebase_uid = session_data.get("firebase_uid")

    if not user_id and not firebase_uid:
        logger.error("Session missing canonical identity: %s...", session_id[:8])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session data",
            headers={"WWW-Authenticate": "Session"},
        )

    if user_id and hasattr(redis_cache, "get_user_by_id"):
        try:
            user_data = await asyncio.wait_for(
                redis_cache.get_user_by_id(str(user_id)),
                timeout=redis_operation_timeout,
            )
        except asyncio.TimeoutError:
            logger.error(
                "Redis operation timeout after %ss on user_id cache lookup",
                redis_operation_timeout,
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="User cache lookup timed out. Please try again.",
            )

    if not user_data and not user_id and firebase_uid and hasattr(redis_cache, "get_user_by_uid"):
        validate_firebase_uid(firebase_uid)
        try:
            user_data = await asyncio.wait_for(
                redis_cache.get_user_by_uid(firebase_uid),
                timeout=redis_operation_timeout,
            )
        except asyncio.TimeoutError:
            logger.error(
                "Redis operation timeout after %ss on firebase_uid cache lookup",
                redis_operation_timeout,
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="User cache lookup timed out. Please try again.",
            )

    if user_data:
        return user_data

    identity = str(user_id or firebase_uid)

    try:
        if user_id:
            user = await load_user_from_db_by_user_id(str(user_id))
        else:
            validate_firebase_uid(firebase_uid)
            user = await load_user_from_db_by_firebase_uid(firebase_uid)
    except asyncio.CancelledError:
        logger.warning(
            "Database query cancelled for session-backed user lookup %s...",
            identity[:8],
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Please try again.",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Database error for session-backed user lookup %s...: %s",
            identity[:8],
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Please try again.",
        )

    if not user:
        logger.error("User not found for session-backed lookup: %s...", identity[:8])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Session"},
        )

    user_data = serialize_user(user)
    await cache_user_data_by_identity(redis_cache, user_data, ttl=900)
    return user_data


async def resolve_session_user_data(
    *,
    session_id: str,
    redis_cache: Any,
    redis_operation_timeout: float,
    session_ttl: int,
    validate_firebase_uid: Callable[[str], None],
    load_user_from_db_by_user_id: Callable[[str], Awaitable[Optional[TUser]]],
    load_user_from_db_by_firebase_uid: Callable[[str], Awaitable[Optional[TUser]]],
    load_user_from_db_by_session: Callable[[str], Awaitable[Optional[TUser]]],
    serialize_user: Callable[[TUser], Dict[str, Any]] = serialize_user_data,
) -> Tuple[Dict[str, Any], str]:
    """Resolve authenticated user data from Redis session, cache, or DB fallback."""
    session_data = None
    use_fallback = False

    try:
        session_data = await asyncio.wait_for(
            redis_cache.get_session(session_id),
            timeout=redis_operation_timeout,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Redis timeout for session %s..., falling back to PostgreSQL",
            session_id[:8],
        )
        use_fallback = True
    except Exception as exc:
        logger.error(
            "Redis error for session %s...: %s. Falling back to PostgreSQL",
            session_id[:8],
            exc,
        )
        use_fallback = True

    if use_fallback:
        try:
            fallback_user = await load_user_from_db_by_session(session_id)
        except asyncio.TimeoutError:
            logger.error("Database timeout during fallback for session %s...", session_id[:8])
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database temporarily unavailable. Please try again.",
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "Database error during fallback for session %s...: %s",
                session_id[:8],
                exc,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database temporarily unavailable. Please try again.",
            )

        if not fallback_user:
            logger.warning("Invalid or expired session during fallback: %s...", session_id[:8])
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session. Please login again.",
                headers={"WWW-Authenticate": "Session"},
            )

        user_data = serialize_user(fallback_user)
        if not user_data.get("is_active", False):
            logger.warning(
                "Inactive user attempted access (fallback): %s",
                user_data.get("email"),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        await cache_user_data_by_identity(redis_cache, user_data, ttl=900)
        await rehydrate_session_cache(
            redis_cache,
            session_id=session_id,
            user_data=user_data,
            session_ttl=session_ttl,
        )

        if hasattr(redis_cache, "update_session_activity"):
            try:
                await asyncio.wait_for(
                    redis_cache.update_session_activity(
                        session_id=session_id,
                        extend_ttl=True,
                        custom_ttl=session_ttl,
                    ),
                    timeout=redis_operation_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Redis timeout extending session TTL for fallback session %s...",
                    session_id[:8],
                )
            except Exception as exc:
                logger.warning(
                    "Failed to extend session TTL for fallback session %s...: %s",
                    session_id[:8],
                    exc,
                )

        return user_data, "fallback"

    if not session_data:
        logger.warning("Invalid or expired session: %s...", session_id[:8])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please login again.",
            headers={"WWW-Authenticate": "Session"},
        )

    if hasattr(redis_cache, "update_session_activity"):
        try:
            await asyncio.wait_for(
                redis_cache.update_session_activity(
                    session_id=session_id,
                    extend_ttl=True,
                ),
                timeout=redis_operation_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Redis timeout updating session activity for %s... (non-critical, continuing)",
                session_id[:8],
            )
        except Exception as exc:
            logger.warning(
                "Failed to update session activity for %s...: %s (non-critical, continuing)",
                session_id[:8],
                exc,
            )

    user_data = await _lookup_session_identity_user_data(
        session_id=session_id,
        session_data=session_data,
        redis_cache=redis_cache,
        redis_operation_timeout=redis_operation_timeout,
        validate_firebase_uid=validate_firebase_uid,
        load_user_from_db_by_user_id=load_user_from_db_by_user_id,
        load_user_from_db_by_firebase_uid=load_user_from_db_by_firebase_uid,
        serialize_user=serialize_user,
    )

    if not user_data.get("is_active", False):
        logger.warning("Inactive user attempted access: %s", user_data.get("email"))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user_data, "redis"
