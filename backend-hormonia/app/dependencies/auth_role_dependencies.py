"""Role-gated auth wrapper helpers."""

from __future__ import annotations

from typing import Any, Mapping, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole


def _normalize_role_value(candidate: Any) -> Optional[str]:
    if isinstance(candidate, UserRole):
        return candidate.value.upper()
    if isinstance(candidate, str):
        normalized = candidate.strip().upper()
        return normalized or None
    return None


async def require_active_user(current_user: User) -> User:
    """Ensure the current user is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    return current_user


async def require_admin_user(
    current_user: User,
    *,
    detail: str = "Not enough permissions",
) -> User:
    """Ensure the current user has admin privileges."""
    if _normalize_role_value(getattr(current_user, "role", None)) != UserRole.ADMIN.value.upper():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    return current_user


async def require_doctor_user(
    current_user: User,
    *,
    detail: str = "Not enough permissions",
) -> User:
    """Ensure the current user can access doctor-level routes."""
    role_value = _normalize_role_value(getattr(current_user, "role", None))
    if role_value not in {
        UserRole.DOCTOR.value.upper(),
        UserRole.ADMIN.value.upper(),
    }:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    return current_user


async def require_admin_session_user(
    current_user: Mapping[str, Any],
    *,
    detail: str = "Not enough permissions",
) -> Mapping[str, Any]:
    """Ensure a mapping-style session payload belongs to an admin."""
    role_value = _normalize_role_value(current_user.get("role"))
    if role_value != UserRole.ADMIN.value.upper():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    return current_user


async def get_active_admin_user_from_session(
    current_user: Mapping[str, Any],
    db: AsyncSession,
) -> User:
    """Load the active admin ``User`` for a validated session payload.

    Canonical ``id`` / ``user_id`` identities are authoritative. ``firebase_uid`` is
    retained as a compatibility fallback when canonical IDs are absent.
    """
    await require_admin_session_user(current_user, detail="Admin access required")

    canonical_user_id = current_user.get("id") or current_user.get("user_id")
    if canonical_user_id:
        try:
            user_uuid = UUID(str(canonical_user_id))
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session data",
            ) from exc

        result = await db.execute(
            select(User).where(User.id == user_uuid, User.is_active.is_(True))
        )
        user = result.scalar_one_or_none()
        if user:
            return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin user not found or inactive",
        )

    firebase_uid = current_user.get("firebase_uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session data",
        )

    result = await db.execute(
        select(User).where(User.firebase_uid == firebase_uid, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user:
        return user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin user not found or inactive",
    )


__all__ = [
    "get_active_admin_user_from_session",
    "require_active_user",
    "require_admin_user",
    "require_doctor_user",
    "require_admin_session_user",
]
