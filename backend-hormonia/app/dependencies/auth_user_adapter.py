"""Session and auth user-data adaptation helpers."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import inspect

from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


def resolve_user_role(
    firebase_custom_claims: Optional[Dict[str, Any]] = None,
    db_role: Optional[UserRole] = None,
    default_role: UserRole = UserRole.DOCTOR,
) -> UserRole:
    """Resolve a user role from Firebase claims or a database value."""
    claims = firebase_custom_claims or {}
    role_value = None

    if isinstance(claims, dict):
        if "role" in claims:
            role_value = claims.get("role")
        elif "roles" in claims:
            role_value = claims.get("roles")

    def _normalize_role(candidate: Any) -> Optional[UserRole]:
        if isinstance(candidate, UserRole):
            return candidate
        if isinstance(candidate, str):
            normalized = candidate.strip().lower()
            if not normalized:
                return None
            try:
                return UserRole(normalized)
            except ValueError:
                logger.warning("Invalid role '%s' in Firebase custom claims", candidate)
                return None
        return None

    if role_value is not None:
        if isinstance(role_value, (list, tuple, set)):
            for entry in role_value:
                resolved = _normalize_role(entry)
                if resolved:
                    logger.debug(
                        "Resolved role from Firebase custom claims: %s",
                        resolved.value,
                    )
                    return resolved
            logger.warning(
                "No valid roles found in Firebase custom claims list: %s", role_value
            )
        else:
            resolved = _normalize_role(role_value)
            if resolved:
                logger.debug(
                    "Resolved role from Firebase custom claims: %s",
                    resolved.value,
                )
                return resolved

    if db_role is not None:
        if isinstance(db_role, UserRole):
            logger.debug("Resolved role from database: %s", db_role.value)
            return db_role
        if isinstance(db_role, str):
            try:
                normalized_db_role = UserRole(db_role.lower())
                logger.debug(
                    "Resolved role from database: %s", normalized_db_role.value
                )
                return normalized_db_role
            except ValueError:
                logger.warning("Invalid database role '%s'", db_role)

    logger.debug("Defaulting role to: %s", default_role.value)
    return default_role


def user_to_cache_dict(user: User) -> Dict[str, Any]:
    """Convert a ``User`` model to the canonical runtime cache payload."""
    last_login = user.get_last_login() if hasattr(user, "get_last_login") else getattr(user, "last_login", getattr(user, "firebase_last_sign_in", None))
    photo_url = user.get_photo_url() if hasattr(user, "get_photo_url") else getattr(user, "photo_url", getattr(user, "firebase_photo_url", None))
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "last_login": last_login.isoformat() if last_login else None,
        "photo_url": photo_url,
    }


def session_user_data_to_user(user_data: Dict[str, Any]) -> User:
    """Convert mapping-style session payloads into a ``User`` model instance."""
    try:
        user_dict = user_data.copy()

        user_dict.pop("permissions", None)
        user_dict.pop("cached_at", None)

        if "id" not in user_dict and user_dict.get("user_id"):
            user_dict["id"] = user_dict.get("user_id")
        user_dict.pop("user_id", None)

        if user_dict.get("id") and isinstance(user_dict["id"], str):
            try:
                user_dict["id"] = UUID(user_dict["id"])
            except ValueError as exc:
                raise ValueError("Invalid session user id") from exc

        if "last_login" in user_dict:
            last_login = user_dict.pop("last_login")
            if last_login and not user_dict.get("last_login"):
                user_dict["last_login"] = last_login
            if last_login and not user_dict.get("firebase_last_sign_in"):
                user_dict["firebase_last_sign_in"] = last_login

        if "photo_url" in user_dict:
            photo_url = user_dict.pop("photo_url")
            if photo_url and not user_dict.get("photo_url"):
                user_dict["photo_url"] = photo_url
            if photo_url and not user_dict.get("firebase_photo_url"):
                user_dict["firebase_photo_url"] = photo_url

        for ts_field in ["created_at", "updated_at", "last_login", "firebase_last_sign_in"]:
            if user_dict.get(ts_field) and isinstance(user_dict[ts_field], str):
                try:
                    user_dict[ts_field] = datetime.fromisoformat(user_dict[ts_field])
                except ValueError:
                    pass

        role_value = user_dict.get("role")
        if isinstance(role_value, str):
            try:
                user_dict["role"] = UserRole(role_value.lower())
            except ValueError:
                logger.warning("Invalid role '%s', defaulting to DOCTOR", role_value)
                user_dict["role"] = UserRole.DOCTOR
        elif not isinstance(role_value, UserRole):
            user_dict["role"] = UserRole.DOCTOR

        mapper = inspect(User)
        allowed_keys = set(mapper.columns.keys())
        filtered_user_dict = {
            key: value for key, value in user_dict.items() if key in allowed_keys
        }

        return User(**filtered_user_dict)
    except Exception as exc:
        logger.error("Failed to convert session data to User object: %s", exc)
        try:
            logger.error("User dict keys: %s", list(user_data.keys()))
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session data error - please try logging out and back in",
        )


__all__ = [
    "resolve_user_role",
    "user_to_cache_dict",
    "session_user_data_to_user",
]
