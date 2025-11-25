"""
Messages API v2 - Helper Functions
Shared utility functions for all message router modules.
"""

from typing import Optional, List, Tuple, Any
from datetime import datetime
from uuid import UUID
import json
import base64
import logging
from fastapi import HTTPException, status, Cookie, Header, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.message import Message
from app.dependencies.auth_dependencies import get_redis_cache

logger = logging.getLogger(__name__)


async def _get_current_user_simple(
    session_cookie_id: str = Cookie(None, alias="session_id"),
    x_session_id: str = Header(None, alias="X-Session-ID"),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
):
    """Simplified session validation."""
    final_session_id = session_cookie_id or x_session_id
    if not final_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID not provided"
        )

    session_data = await redis_cache.get_session(final_session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )

    firebase_uid = session_data.get("firebase_uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session data"
        )

    user_data = await redis_cache.get_user_by_uid(firebase_uid)
    if not user_data:
        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        user_data = {
            "id": str(user.id),
            "firebase_uid": user.firebase_uid,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            "is_active": user.is_active
        }
        await redis_cache.cache_user_data(firebase_uid, user_data, ttl=900)

    if not user_data.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return user_data


def _extract_user_context(current_user) -> Tuple[Optional[UserRole], Optional[str]]:
    """Extract user role and ID from current_user."""
    role = None
    user_id = None

    if isinstance(current_user, dict):
        role = current_user.get("role")
        user_id = current_user.get("id")
    else:
        user_id = getattr(current_user, "id", None)
        role = getattr(current_user, "role", None)

    if isinstance(role, UserRole):
        role_enum = role
    elif isinstance(role, str):
        try:
            role_enum = UserRole(role.lower())
        except ValueError:
            role_enum = None
    else:
        role_enum = None

    if user_id is not None:
        user_id = str(user_id)

    return role_enum, user_id


def _is_admin(current_user) -> bool:
    """Check if user is admin."""
    role_enum, _ = _extract_user_context(current_user)
    return role_enum == UserRole.ADMIN


def _serialize_message(message: Message, include_patient: bool = False) -> dict:
    """Serialize Message model to dict."""
    if message is None:
        return None

    data = {
        "id": str(message.id),
        "patient_id": str(message.patient_id),
        "content": message.content,
        "type": message.type.value if hasattr(message.type, 'value') else str(message.type),
        "direction": message.direction.value if hasattr(message.direction, 'value') else str(message.direction),
        "status": message.status.value if hasattr(message.status, 'value') else str(message.status),
        "message_metadata": message.message_metadata or {},
        "scheduled_for": message.scheduled_for.isoformat() if message.scheduled_for else None,
        "sent_at": message.sent_at.isoformat() if message.sent_at else None,
        "delivered_at": message.delivered_at.isoformat() if message.delivered_at else None,
        "read_at": message.read_at.isoformat() if message.read_at else None,
        "failed_at": getattr(message, "failed_at", None),
        "whatsapp_id": message.whatsapp_id,
        "error_message": getattr(message, "failure_reason", None),
        "retry_count": message.retry_count or 0,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "updated_at": message.updated_at.isoformat() if message.updated_at else None,
    }

    # Add computed fields
    if message.sent_at and message.delivered_at:
        data["delivery_time_seconds"] = (message.delivered_at - message.sent_at).total_seconds()

    if message.delivered_at and message.read_at:
        data["read_time_seconds"] = (message.read_at - message.delivered_at).total_seconds()

    # Add eager-loaded patient
    if include_patient and hasattr(message, 'patient') and message.patient:
        data["patient"] = {
            "id": str(message.patient.id),
            "name": message.patient.name,
            "phone": message.patient.phone,
        }

    return data


def _create_cursor(last_item: Any, cursor_fields: Optional[List[str]] = None) -> str:  # type: ignore[assignment]
    """Create base64-encoded cursor."""
    if cursor_fields is None:
        cursor_fields = ["id", "created_at"]

    cursor_data = {}
    for field in cursor_fields:
        value = getattr(last_item, field, None)
        if isinstance(value, UUID):
            cursor_data[field] = str(value)
        elif isinstance(value, datetime):
            cursor_data[field] = value.isoformat()
        else:
            cursor_data[field] = value  # type: ignore[assignment]

    cursor_json = json.dumps(cursor_data)
    return base64.b64encode(cursor_json.encode("utf-8")).decode("utf-8")


async def _get_cached_or_compute(
    redis_cache,
    cache_key: str,
    compute_fn,
    ttl: int = 300
):
    """Get from cache or compute and cache."""
    try:
        cached = await redis_cache.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Cache read failed: {e}")

    result = compute_fn()

    try:
        await redis_cache.set(cache_key, json.dumps(result), expire=ttl)
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")

    return result
