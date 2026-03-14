"""
Messages API v2 - Helper Functions
Shared utility functions for all message router modules.
"""

from typing import Optional, List, Tuple, Any, Mapping, Sequence
from datetime import datetime
from uuid import UUID
import json
import base64
import logging
from fastapi import HTTPException, status, Cookie, Depends
from sqlalchemy.orm import Session, Query

from app.database import get_db
from app.models.user import UserRole
from app.models.message import Message
from app.models.patient import Patient
from app.dependencies.auth_dependencies import get_redis_cache
from app.api.v2.auth_session_shared import (
    resolve_session_id,
    get_user_data_from_session,
)
from app.api.v2.patients_shared_helpers import extract_user_context_sync

logger = logging.getLogger(__name__)
CursorData = Optional[Mapping[str, Any]]
PaginatedResult = Tuple[List[Any], bool, Optional[str], Optional[int]]


async def _get_current_user_simple(
    session_cookie_id: str = Cookie(None, alias="session_id"),
    db: Session = Depends(get_db),
    redis_cache=Depends(get_redis_cache),
):
    """Simplified session validation using the canonical session cookie."""
    final_session_id = resolve_session_id(session_cookie_id=session_cookie_id)
    if not final_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session cookie required",
        )
    return await get_user_data_from_session(
        session_id=final_session_id,
        db=db,
        redis_cache=redis_cache,
    )


def _extract_user_context(current_user) -> Tuple[Optional[UserRole], Optional[str]]:
    """Extract user role and ID from current_user."""
    return extract_user_context_sync(current_user)


def _get_patient_with_access(
    *,
    db: Session,
    current_user: Any,
    patient_id: str,
) -> Tuple[UUID, Patient]:
    """Parse patient UUID, ensure patient exists and enforce RBAC access."""
    try:
        patient_uuid = UUID(patient_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format",
        ) from exc

    patient = db.query(Patient).filter(Patient.id == patient_uuid).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN and str(patient.doctor_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return patient_uuid, patient


def _parse_message_uuid(message_id: str) -> UUID:
    """Parse message UUID from path parameter or raise 400."""
    try:
        return UUID(message_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid message ID format"
        ) from exc


def _load_message_with_access(
    *,
    db: Session,
    current_user: Any,
    message_id: str,
    message_service: Any,
) -> Tuple[UUID, Message, Optional[str]]:
    """Load message by ID and enforce RBAC on related patient."""
    msg_uuid = _parse_message_uuid(message_id)
    message = message_service.get_message(msg_uuid)

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Message not found"
        )

    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN:
        patient = db.query(Patient).filter(Patient.id == message.patient_id).first()
        if not patient or str(patient.doctor_id) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

    return msg_uuid, message, user_id


def _build_message_page_response(
    messages: Sequence[Message],
    *,
    has_more: bool,
    next_cursor: Optional[str],
    total: Optional[int],
) -> dict:
    """Standard paginated response payload for message list endpoints."""
    return {
        "data": [_serialize_message(msg) for msg in messages],
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }


def _paginate_messages_query(query: Query, *, limit: int, cursor_data: CursorData) -> dict:
    """Paginate message query and return standard response payload."""
    messages, has_more, next_cursor, total = _paginate_query(
        query,
        limit=limit,
        cursor_data=cursor_data,
        order_columns=(Message.created_at.desc(), Message.id),
    )
    return _build_message_page_response(
        messages,
        has_more=has_more,
        next_cursor=next_cursor,
        total=total,
    )


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
        "type": message.type.value
        if hasattr(message.type, "value")
        else str(message.type),
        "direction": message.direction.value
        if hasattr(message.direction, "value")
        else str(message.direction),
        "status": message.status.value
        if hasattr(message.status, "value")
        else str(message.status),
        "message_metadata": message.message_metadata or {},
        "scheduled_for": message.scheduled_for.isoformat()
        if message.scheduled_for
        else None,
        "sent_at": message.sent_at.isoformat() if message.sent_at else None,
        "delivered_at": message.delivered_at.isoformat()
        if message.delivered_at
        else None,
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
        data["delivery_time_seconds"] = (
            message.delivered_at - message.sent_at
        ).total_seconds()

    if message.delivered_at and message.read_at:
        data["read_time_seconds"] = (
            message.read_at - message.delivered_at
        ).total_seconds()

    # Add eager-loaded patient
    if include_patient and hasattr(message, "patient") and message.patient:
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


def _parse_cursor_uuid(value: Any) -> UUID:
    """Parse cursor value into UUID while accepting UUID or string inputs."""
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _parse_cursor_datetime(value: Any) -> datetime:
    """Parse cursor value into datetime while accepting datetime or ISO strings."""
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _apply_message_created_cursor_filter(
    query: Query, cursor_data: CursorData
) -> Query:
    """
    Apply cursor filter for message timelines ordered by (created_at DESC, id ASC).
    """
    if not cursor_data or "id" not in cursor_data:
        return query

    cursor_created_at_raw = cursor_data.get("created_at")
    if cursor_created_at_raw is None:
        return query

    cursor_id = _parse_cursor_uuid(cursor_data["id"])
    cursor_created_at = _parse_cursor_datetime(cursor_created_at_raw)
    return query.filter(
        (Message.created_at < cursor_created_at)
        | ((Message.created_at == cursor_created_at) & (Message.id > cursor_id))
    )


def _apply_uuid_id_cursor_filter(
    query: Query, id_column: Any, cursor_data: CursorData
) -> Query:
    """Apply simple UUID `id > cursor_id` filtering for cursor-based pagination."""
    if not cursor_data or "id" not in cursor_data:
        return query

    cursor_id = _parse_cursor_uuid(cursor_data["id"])
    return query.filter(id_column > cursor_id)


def _paginate_query(
    query: Query,
    *,
    limit: int,
    cursor_data: CursorData,
    order_columns: Sequence[Any],
    cursor_fields: Optional[List[str]] = None,
) -> PaginatedResult:
    """
    Execute common cursor pagination flow.

    Returns:
        (items, has_more, next_cursor, total)
    """
    total = None if cursor_data else query.count()

    items = query.order_by(*order_columns).limit(limit + 1).all()
    has_more = len(items) > limit
    if has_more:
        items = items[:limit]

    next_cursor = None
    if has_more and items:
        next_cursor = _create_cursor(items[-1], cursor_fields=cursor_fields)

    return items, has_more, next_cursor, total


async def _get_cached_or_compute(
    redis_cache, cache_key: str, compute_fn, ttl: int = 300
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
