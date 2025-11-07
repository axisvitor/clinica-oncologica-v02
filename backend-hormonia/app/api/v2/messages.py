"""
Messages API v2
Enhanced message endpoints with cursor pagination, field selection, eager loading, and caching.

26 endpoints total:
- Core Message Operations (13): list, get, conversations, send, scheduled, cancel, stats, status, retry, retry-failed, failed, status filter, statistics
- Enhanced Messages (13): bulk send, templates (5), inbound, conversations list, unread, mark-read, search, analytics (2)
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from uuid import UUID
import json
import base64
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, BackgroundTasks, Cookie, Header
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, or_, desc

from app.database import get_db
from app.models.message import Message, MessageStatus, MessageType, MessageDirection
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.services.message import MessageService
from app.services.message_sender import MessageSender
from app.services.unified_whatsapp_service import MessagingMode
from app.services.patient import PatientService
from app.schemas.v2.messages import (
    MessageV2Response,
    MessageV2List,
    MessageV2Create,
    MessageV2Update,
    SendMessageV2Request,
    SendMessageV2Response,
    ScheduleMessageV2Request,
    ScheduleMessageV2Response,
    CancelMessageV2Response,
    RetryMessageV2Request,
    BulkMessageV2Request,
    BulkMessageV2Response,
    MessageStatsV2Response,
    MessageStatusDistributionV2Response,
    FailedMessageV2Response,
    FailedMessagesV2List,
    InboundMessageV2Request,
    InboundMessageV2Response,
    ConversationV2Response,
    ConversationV2List,
    MessageTemplateV2Response,
    MessageTemplateV2List,
    MessageStatusV2,
    PatientV2Brief,
)
from app.schemas.v2.common import ErrorResponse
from .dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
    apply_field_selection,
)
from app.dependencies.auth_dependencies import get_current_user_from_session, get_redis_cache
from app.utils.rate_limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

async def _get_current_user_simple(
    session_id: str = Cookie(None, alias="session_id"),
    x_session_id: str = Header(None, alias="X-Session-ID"),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
):
    """Simplified session validation."""
    final_session_id = session_id or x_session_id
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


def _create_cursor(last_item: Any, cursor_fields: List[str] = None) -> str:
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
            cursor_data[field] = value

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


# ============================================================================
# A. Core Message Operations (13 endpoints)
# ============================================================================

@router.get(
    "",
    response_model=MessageV2List,
    summary="List messages with filters",
    description="Get paginated list of messages with cursor pagination and optional filters"
)
async def list_messages(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    pagination = Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    status_filter: Optional[MessageStatusV2] = Query(None, alias="status", description="Filter by status"),
    direction: Optional[str] = Query(None, description="Filter by direction (inbound/outbound)"),
    message_type: Optional[str] = Query(None, alias="type", description="Filter by message type"),
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
):
    """
    List messages with cursor-based pagination.

    Features:
    - Cursor pagination (efficient for large datasets)
    - Field selection (?fields=id,content,status)
    - Eager loading (?include=patient)
    - Multiple filters (patient, status, direction, type, dates)
    """
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    # Build base query with eager loading
    query = db.query(Message)

    if include and "patient" in include:
        query = query.options(joinedload(Message.patient))

    # Apply filters
    filters = []
    role_enum, user_id = _extract_user_context(current_user)

    # RBAC: Non-admin users can only see messages for their patients
    if role_enum != UserRole.ADMIN:
        user_uuid = UUID(user_id) if user_id else None
        if not user_uuid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to determine user permissions"
            )
        # Join with patients to filter by doctor_id
        query = query.join(Patient, Message.patient_id == Patient.id)
        filters.append(Patient.doctor_id == user_uuid)

    # Cursor pagination
    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"])
        cursor_created_at = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
        filters.append(
            (Message.created_at < cursor_created_at) |
            ((Message.created_at == cursor_created_at) & (Message.id > cursor_id))
        )

    # Additional filters
    if patient_id:
        filters.append(Message.patient_id == UUID(patient_id))

    if status_filter:
        # Map V2 status to V1 status
        status_map = {
            MessageStatusV2.PENDING: MessageStatus.PENDING,
            MessageStatusV2.SCHEDULED: MessageStatus.SCHEDULED,
            MessageStatusV2.SENT: MessageStatus.SENT,
            MessageStatusV2.DELIVERED: MessageStatus.DELIVERED,
            MessageStatusV2.READ: MessageStatus.READ,
            MessageStatusV2.FAILED: MessageStatus.FAILED,
            MessageStatusV2.CANCELLED: MessageStatus.CANCELLED,
        }
        db_status = status_map.get(status_filter)
        if db_status:
            filters.append(Message.status == db_status)

    if direction:
        if direction.lower() == "inbound":
            filters.append(Message.direction == MessageDirection.INBOUND)
        elif direction.lower() == "outbound":
            filters.append(Message.direction == MessageDirection.OUTBOUND)

    if message_type:
        try:
            type_enum = MessageType(message_type.lower())
            filters.append(Message.type == type_enum)
        except ValueError:
            pass

    if start_date:
        filters.append(Message.created_at >= start_date)

    if end_date:
        filters.append(Message.created_at <= end_date)

    if filters:
        query = query.filter(and_(*filters))

    # Count total (only on first page)
    total = None
    if not cursor_data:
        total = query.count()

    # Order and limit
    query = query.order_by(Message.created_at.desc(), Message.id)
    messages = query.limit(limit + 1).all()

    # Check if there are more results
    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    # Create next cursor
    next_cursor = None
    if has_more and messages:
        next_cursor = _create_cursor(messages[-1])

    # Convert to response models
    message_responses = []
    for message in messages:
        msg_dict = _serialize_message(message, include_patient="patient" in (include or []))

        # Apply field selection
        if fields:
            msg_dict = apply_field_selection(msg_dict, fields)

        message_responses.append(msg_dict)

    return {
        "data": message_responses,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }


@router.get(
    "/{message_id}",
    response_model=MessageV2Response,
    summary="Get message by ID",
    description="Get a single message with optional field selection and eager loading"
)
async def get_message(
    message_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    """Get a single message by ID."""
    try:
        msg_uuid = UUID(message_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid message ID format"
        )

    query = db.query(Message)

    if include and "patient" in include:
        query = query.options(joinedload(Message.patient))

    message = query.filter(Message.id == msg_uuid).first()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message {message_id} not found"
        )

    # RBAC check
    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN:
        patient = db.query(Patient).filter(Patient.id == message.patient_id).first()
        if not patient or str(patient.doctor_id) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

    msg_dict = _serialize_message(message, include_patient="patient" in (include or []))

    if fields:
        msg_dict = apply_field_selection(msg_dict, fields)

    return msg_dict


@router.get(
    "/conversations/{patient_id}",
    response_model=MessageV2List,
    summary="Get conversation history",
    description="Get conversation history for a specific patient with cursor pagination"
)
async def get_conversation_history(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    pagination = Depends(get_pagination_params),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    """Get conversation history for a patient."""
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )

    # Verify patient exists and user has access
    patient = db.query(Patient).filter(Patient.id == patient_uuid).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )

    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN and str(patient.doctor_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    query = db.query(Message).filter(Message.patient_id == patient_uuid)

    if include and "patient" in include:
        query = query.options(joinedload(Message.patient))

    # Cursor pagination
    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"])
        cursor_created_at = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
        query = query.filter(
            (Message.created_at < cursor_created_at) |
            ((Message.created_at == cursor_created_at) & (Message.id > cursor_id))
        )

    total = None
    if not cursor_data:
        total = query.count()

    query = query.order_by(Message.created_at.desc(), Message.id)
    messages = query.limit(limit + 1).all()

    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    next_cursor = None
    if has_more and messages:
        next_cursor = _create_cursor(messages[-1])

    message_responses = [
        _serialize_message(msg, include_patient="patient" in (include or []))
        for msg in messages
    ]

    return {
        "data": message_responses,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }


@router.post(
    "/send",
    response_model=SendMessageV2Response,
    summary="Send immediate message",
    description="Send a message immediately to a patient"
)
@limiter.limit("60/minute")
async def send_message(
    request: Request,
    message_data: SendMessageV2Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Send an immediate message to a patient."""
    try:
        patient_uuid = UUID(message_data.patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )

    # Verify patient exists
    patient_service = PatientService(db)
    patient = patient_service.get_patient(patient_uuid)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )

    # RBAC check
    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN and str(patient.doctor_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    message_service = MessageService(db)
    message_sender = MessageSender(db, messaging_mode=MessagingMode.LEGACY)

    # Map V2 type to V1 type
    type_map = {
        "text": MessageType.TEXT,
        "image": MessageType.MEDIA,
        "video": MessageType.MEDIA,
        "audio": MessageType.MEDIA,
        "document": MessageType.MEDIA,
        "interactive": MessageType.BUTTON,
        "template": MessageType.TEXT,
    }
    msg_type = type_map.get(message_data.type, MessageType.TEXT)

    # Create and send message
    message = message_service.schedule_message(
        patient_id=patient_uuid,
        content=message_data.content,
        scheduled_for=datetime.utcnow(),
        message_type=msg_type,
        message_metadata=message_data.message_metadata or {}
    )

    # Send immediately
    try:
        await message_sender.send_message(message)
        db.refresh(message)
    except Exception as e:
        logger.error(f"Failed to send message: {e}")

    return {
        "success": message.status != MessageStatus.FAILED,
        "message": _serialize_message(message, include_patient=True),
        "estimated_delivery": (datetime.utcnow() + timedelta(seconds=3)).isoformat() if message.status == MessageStatus.SENT else None,
    }


@router.get(
    "/scheduled",
    response_model=MessageV2List,
    summary="List scheduled messages",
    description="Get list of scheduled/pending messages with cursor pagination"
)
async def list_scheduled_messages(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    pagination = Depends(get_pagination_params),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
):
    """List scheduled messages."""
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    query = db.query(Message).filter(
        or_(
            Message.status == MessageStatus.PENDING,
            Message.status == MessageStatus.SCHEDULED
        )
    )

    # RBAC
    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN:
        user_uuid = UUID(user_id) if user_id else None
        query = query.join(Patient, Message.patient_id == Patient.id)
        query = query.filter(Patient.doctor_id == user_uuid)

    if patient_id:
        query = query.filter(Message.patient_id == UUID(patient_id))

    # Cursor pagination
    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"])
        cursor_created_at = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
        query = query.filter(
            (Message.created_at < cursor_created_at) |
            ((Message.created_at == cursor_created_at) & (Message.id > cursor_id))
        )

    total = None
    if not cursor_data:
        total = query.count()

    query = query.order_by(Message.created_at.desc(), Message.id)
    messages = query.limit(limit + 1).all()

    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    next_cursor = None
    if has_more and messages:
        next_cursor = _create_cursor(messages[-1])

    return {
        "data": [_serialize_message(msg) for msg in messages],
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }


@router.put(
    "/{message_id}/cancel",
    response_model=CancelMessageV2Response,
    summary="Cancel scheduled message",
    description="Cancel a scheduled/pending message"
)
async def cancel_message(
    message_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Cancel a scheduled message."""
    try:
        msg_uuid = UUID(message_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid message ID format"
        )

    message_service = MessageService(db)
    message = message_service.get_message(msg_uuid)

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )

    # RBAC check
    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN:
        patient = db.query(Patient).filter(Patient.id == message.patient_id).first()
        if not patient or str(patient.doctor_id) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

    # Only allow canceling pending/scheduled messages
    if message.status not in [MessageStatus.PENDING, MessageStatus.SCHEDULED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel message with status: {message.status.value}"
        )

    previous_status = message.status

    # Mark as cancelled
    message_service.mark_as_failed(
        msg_uuid,
        {"reason": "cancelled_by_user", "cancelled_by": user_id}
    )

    return {
        "success": True,
        "message_id": message_id,
        "previous_status": previous_status.value,
        "cancelled_at": datetime.utcnow().isoformat(),
        "message": "Message cancelled successfully",
    }


@router.get(
    "/patient/{patient_id}/stats",
    response_model=MessageStatsV2Response,
    summary="Get patient message statistics",
    description="Get message statistics for a specific patient (cached 5min)"
)
async def get_patient_message_stats(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """Get message statistics for a patient."""
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )

    # Verify patient exists and access
    patient = db.query(Patient).filter(Patient.id == patient_uuid).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )

    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN and str(patient.doctor_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Try cache
    cache_key = f"message_stats:patient:{patient_id}"

    def compute_stats():
        messages = db.query(Message).filter(Message.patient_id == patient_uuid).all()

        total_messages = len(messages)
        sent_count = sum(1 for m in messages if m.status == MessageStatus.SENT)
        delivered_count = sum(1 for m in messages if m.status == MessageStatus.DELIVERED)
        read_count = sum(1 for m in messages if m.status == MessageStatus.READ)
        failed_count = sum(1 for m in messages if m.status == MessageStatus.FAILED)

        delivery_rate = (delivered_count / sent_count * 100) if sent_count > 0 else 0
        read_rate = (read_count / delivered_count * 100) if delivered_count > 0 else 0

        # Calculate average response time for inbound messages
        inbound_messages = [m for m in messages if m.direction == MessageDirection.INBOUND and m.created_at]
        avg_response_time = None
        if len(inbound_messages) > 1:
            # Simple calculation: average time between consecutive inbound messages
            times = [m.created_at for m in sorted(inbound_messages, key=lambda x: x.created_at)]
            deltas = [(times[i+1] - times[i]).total_seconds() / 60 for i in range(len(times) - 1)]
            avg_response_time = sum(deltas) / len(deltas) if deltas else None

        last_message_at = max([m.created_at for m in messages]) if messages else None

        return {
            "patient_id": patient_id,
            "total_messages": total_messages,
            "sent_count": sent_count,
            "delivered_count": delivered_count,
            "read_count": read_count,
            "failed_count": failed_count,
            "delivery_rate": round(delivery_rate, 2),
            "read_rate": round(read_rate, 2),
            "average_response_time_minutes": round(avg_response_time, 2) if avg_response_time else None,
            "last_message_at": last_message_at.isoformat() if last_message_at else None,
        }

    return await _get_cached_or_compute(redis_cache, cache_key, compute_stats, ttl=300)


@router.get(
    "/{message_id}/status",
    summary="Get message delivery status",
    description="Get detailed delivery status for a message"
)
async def get_message_status(
    message_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Get detailed delivery status for a message."""
    try:
        msg_uuid = UUID(message_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid message ID format"
        )

    message_sender = MessageSender(db, messaging_mode=MessagingMode.LEGACY)
    status_info = await message_sender.get_message_delivery_status(msg_uuid)

    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )

    return status_info


@router.post(
    "/{message_id}/retry",
    response_model=MessageV2Response,
    summary="Retry failed message",
    description="Retry sending a specific failed message"
)
async def retry_message(
    message_id: str,
    retry_request: Optional[RetryMessageV2Request] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Retry sending a failed message."""
    try:
        msg_uuid = UUID(message_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid message ID format"
        )

    message_service = MessageService(db)
    message = message_service.get_message(msg_uuid)

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )

    # RBAC check
    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN:
        patient = db.query(Patient).filter(Patient.id == message.patient_id).first()
        if not patient or str(patient.doctor_id) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

    # Check if message can be retried
    if message.status not in [MessageStatus.FAILED, MessageStatus.PENDING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message can only be retried if it's in FAILED or PENDING status"
        )

    # Update content if provided
    if retry_request and retry_request.new_content:
        message.content = retry_request.new_content
        db.commit()

    # Retry the message in background
    message_sender = MessageSender(db, messaging_mode=MessagingMode.LEGACY)
    background_tasks.add_task(message_sender.send_message, message)

    # Update status to pending
    message.status = MessageStatus.PENDING
    message.retry_count = (message.retry_count or 0) + 1
    db.commit()
    db.refresh(message)

    return _serialize_message(message)


@router.post(
    "/retry-failed",
    summary="Retry all failed messages",
    description="Retry sending all failed messages (batch operation)"
)
async def retry_failed_messages(
    background_tasks: BackgroundTasks,
    limit: int = Query(50, ge=1, le=100, description="Max messages to retry"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Retry all failed messages."""
    message_sender = MessageSender(db, messaging_mode=MessagingMode.LEGACY)

    retry_count = await message_sender.retry_failed_messages(limit)

    return {
        "success": True,
        "message": "Retry process initiated",
        "retried_count": retry_count,
        "limit": limit,
    }


@router.get(
    "/failed",
    response_model=FailedMessagesV2List,
    summary="List failed messages",
    description="Get list of failed messages with cursor pagination"
)
async def list_failed_messages(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    pagination = Depends(get_pagination_params),
):
    """List failed messages."""
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    query = db.query(Message).filter(Message.status == MessageStatus.FAILED)

    # RBAC
    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN:
        user_uuid = UUID(user_id) if user_id else None
        query = query.join(Patient, Message.patient_id == Patient.id)
        query = query.filter(Patient.doctor_id == user_uuid)

    # Cursor pagination
    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"])
        cursor_created_at = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
        query = query.filter(
            (Message.created_at < cursor_created_at) |
            ((Message.created_at == cursor_created_at) & (Message.id > cursor_id))
        )

    total = None
    if not cursor_data:
        total = query.count()

    query = query.order_by(Message.created_at.desc(), Message.id)
    messages = query.limit(limit + 1).all()

    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    next_cursor = None
    if has_more and messages:
        next_cursor = _create_cursor(messages[-1])

    # Count retryable messages
    total_retryable = sum(1 for m in messages if (m.retry_count or 0) < 3)

    # Build failed message responses
    failed_responses = []
    for msg in messages:
        msg_dict = _serialize_message(msg)
        msg_dict["failure_reason"] = getattr(msg, "failure_reason", "Unknown error")
        msg_dict["can_retry"] = (msg.retry_count or 0) < 3
        msg_dict["next_retry_at"] = None
        failed_responses.append(msg_dict)

    return {
        "data": failed_responses,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
        "total_retryable": total_retryable,
    }


@router.get(
    "/status/{status}",
    response_model=MessageV2List,
    summary="Filter messages by status",
    description="Get messages filtered by specific status with cursor pagination"
)
async def filter_by_status(
    status: MessageStatusV2,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    pagination = Depends(get_pagination_params),
):
    """Filter messages by status."""
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    # Map V2 status to V1 status
    status_map = {
        MessageStatusV2.PENDING: MessageStatus.PENDING,
        MessageStatusV2.SCHEDULED: MessageStatus.SCHEDULED,
        MessageStatusV2.SENT: MessageStatus.SENT,
        MessageStatusV2.DELIVERED: MessageStatus.DELIVERED,
        MessageStatusV2.READ: MessageStatus.READ,
        MessageStatusV2.FAILED: MessageStatus.FAILED,
        MessageStatusV2.CANCELLED: MessageStatus.CANCELLED,
    }
    db_status = status_map.get(status)

    if not db_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status"
        )

    query = db.query(Message).filter(Message.status == db_status)

    # RBAC
    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN:
        user_uuid = UUID(user_id) if user_id else None
        query = query.join(Patient, Message.patient_id == Patient.id)
        query = query.filter(Patient.doctor_id == user_uuid)

    # Cursor pagination
    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"])
        cursor_created_at = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
        query = query.filter(
            (Message.created_at < cursor_created_at) |
            ((Message.created_at == cursor_created_at) & (Message.id > cursor_id))
        )

    total = None
    if not cursor_data:
        total = query.count()

    query = query.order_by(Message.created_at.desc(), Message.id)
    messages = query.limit(limit + 1).all()

    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    next_cursor = None
    if has_more and messages:
        next_cursor = _create_cursor(messages[-1])

    return {
        "data": [_serialize_message(msg) for msg in messages],
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }


@router.get(
    "/statistics",
    summary="Get overall message statistics",
    description="Get overall message statistics (cached 15min)"
)
async def get_statistics(
    days: int = Query(30, ge=1, le=365, description="Period in days"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """Get overall message statistics."""
    role_enum, user_id = _extract_user_context(current_user)

    # Cache key includes user_id for RBAC
    cache_key = f"message_stats:overall:{user_id}:{days}"

    def compute_stats():
        start_date = datetime.utcnow() - timedelta(days=days)

        query = db.query(Message).filter(Message.created_at >= start_date)

        # RBAC
        if role_enum != UserRole.ADMIN:
            user_uuid = UUID(user_id) if user_id else None
            query = query.join(Patient, Message.patient_id == Patient.id)
            query = query.filter(Patient.doctor_id == user_uuid)

        messages = query.all()

        total_messages = len(messages)

        status_counts = {}
        for status in MessageStatus:
            status_counts[status.value] = sum(1 for m in messages if m.status == status)

        sent_count = status_counts.get(MessageStatus.SENT.value, 0)
        delivered_count = status_counts.get(MessageStatus.DELIVERED.value, 0)
        read_count = status_counts.get(MessageStatus.READ.value, 0)
        failed_count = status_counts.get(MessageStatus.FAILED.value, 0)

        success_rate = ((sent_count + delivered_count + read_count) / total_messages * 100) if total_messages > 0 else 0

        return {
            "period_start": start_date.isoformat(),
            "period_end": datetime.utcnow().isoformat(),
            "total_messages": total_messages,
            "status_counts": status_counts,
            "success_rate": round(success_rate, 2),
        }

    return await _get_cached_or_compute(redis_cache, cache_key, compute_stats, ttl=900)


# ============================================================================
# B. Enhanced Messages (13 endpoints)
# ============================================================================

@router.post(
    "/bulk/send",
    response_model=BulkMessageV2Response,
    summary="Send bulk messages",
    description="Send messages to multiple patients at once"
)
@limiter.limit("10/minute")
async def bulk_send_messages(
    request: Request,
    bulk_request: BulkMessageV2Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Send bulk messages to multiple patients."""
    role_enum, user_id = _extract_user_context(current_user)

    # Verify all patients exist and user has access
    patient_uuids = []
    failed_patients = []

    for patient_id in bulk_request.patient_ids:
        try:
            patient_uuid = UUID(patient_id)
            patient = db.query(Patient).filter(Patient.id == patient_uuid).first()

            if not patient:
                failed_patients.append(patient_id)
                continue

            # RBAC check
            if role_enum != UserRole.ADMIN and str(patient.doctor_id) != user_id:
                failed_patients.append(patient_id)
                continue

            patient_uuids.append(patient_uuid)
        except ValueError:
            failed_patients.append(patient_id)

    # Create messages for valid patients
    message_service = MessageService(db)
    batch_id = f"batch_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    scheduled_count = 0
    for patient_uuid in patient_uuids:
        try:
            metadata = bulk_request.message_metadata or {}
            metadata["batch_id"] = batch_id

            message_service.schedule_message(
                patient_id=patient_uuid,
                content=bulk_request.content,
                scheduled_for=bulk_request.scheduled_for or datetime.utcnow(),
                message_type=MessageType.TEXT,
                message_metadata=metadata
            )
            scheduled_count += 1
        except Exception as e:
            logger.error(f"Failed to schedule message for patient {patient_uuid}: {e}")
            failed_patients.append(str(patient_uuid))

    return {
        "success": scheduled_count > 0,
        "batch_id": batch_id,
        "total_messages": len(bulk_request.patient_ids),
        "scheduled_count": scheduled_count,
        "failed_count": len(failed_patients),
        "failed_patients": failed_patients,
        "estimated_completion": (bulk_request.scheduled_for or datetime.utcnow() + timedelta(minutes=5)).isoformat() if scheduled_count > 0 else None,
    }


@router.get(
    "/templates",
    response_model=MessageTemplateV2List,
    summary="List message templates",
    description="Get list of message templates (feature not yet implemented)"
)
async def list_templates(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    pagination = Depends(get_pagination_params),
):
    """List message templates (stub implementation)."""
    # Templates are not yet implemented in the database
    # Return empty list for now
    return {
        "data": [],
        "next_cursor": None,
        "has_more": False,
        "total": 0,
    }


@router.get(
    "/templates/{template_id}",
    response_model=MessageTemplateV2Response,
    summary="Get message template",
    description="Get a specific message template (feature not yet implemented)"
)
async def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Get a message template (stub implementation)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Message templates feature not yet implemented"
    )


@router.post(
    "/templates",
    response_model=MessageTemplateV2Response,
    summary="Create message template",
    description="Create a new message template (feature not yet implemented)"
)
async def create_template(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Create a message template (stub implementation)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Message templates feature not yet implemented"
    )


@router.put(
    "/templates/{template_id}",
    response_model=MessageTemplateV2Response,
    summary="Update message template",
    description="Update a message template (feature not yet implemented)"
)
async def update_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Update a message template (stub implementation)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Message templates feature not yet implemented"
    )


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete message template",
    description="Delete a message template (feature not yet implemented)"
)
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Delete a message template (stub implementation)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Message templates feature not yet implemented"
    )


@router.post(
    "/inbound",
    response_model=InboundMessageV2Response,
    summary="Process inbound message",
    description="Process an inbound message from webhook"
)
async def process_inbound_message(
    inbound_data: InboundMessageV2Request,
    db: Session = Depends(get_db),
):
    """Process an inbound message (webhook endpoint)."""
    # Find patient by phone
    patient = db.query(Patient).filter(Patient.phone == inbound_data.patient_phone).first()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with phone {inbound_data.patient_phone} not found"
        )

    # Create inbound message
    message_service = MessageService(db)

    # Map V2 type to V1 type
    type_map = {
        "text": MessageType.TEXT,
        "image": MessageType.MEDIA,
        "video": MessageType.MEDIA,
        "audio": MessageType.MEDIA,
        "document": MessageType.MEDIA,
    }
    msg_type = type_map.get(inbound_data.type, MessageType.TEXT)

    message = message_service.create_inbound_message(
        patient_id=patient.id,
        content=inbound_data.content,
        whatsapp_id=inbound_data.whatsapp_id,
        message_type=msg_type,
        received_at=inbound_data.received_at or datetime.utcnow(),
        metadata=inbound_data.message_metadata or {}
    )

    return {
        "success": True,
        "message": _serialize_message(message),
        "patient": {
            "id": str(patient.id),
            "name": patient.name,
            "phone": patient.phone,
        },
        "auto_reply_sent": False,
        "auto_reply_message_id": None,
        "conversation_id": None,
    }


@router.get(
    "/conversations",
    response_model=ConversationV2List,
    summary="List all conversations",
    description="Get list of all conversations with cursor pagination"
)
async def list_conversations(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    pagination = Depends(get_pagination_params),
):
    """List all conversations."""
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    role_enum, user_id = _extract_user_context(current_user)

    # Get patients with their latest messages
    query = db.query(Patient)

    # RBAC
    if role_enum != UserRole.ADMIN:
        user_uuid = UUID(user_id) if user_id else None
        query = query.filter(Patient.doctor_id == user_uuid)

    # Filter patients with messages
    query = query.join(Message, Patient.id == Message.patient_id, isouter=False)
    query = query.distinct(Patient.id)

    # Cursor pagination
    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"])
        query = query.filter(Patient.id > cursor_id)

    total = None
    if not cursor_data:
        total = query.count()

    query = query.order_by(Patient.id)
    patients = query.limit(limit + 1).all()

    has_more = len(patients) > limit
    if has_more:
        patients = patients[:limit]

    next_cursor = None
    if has_more and patients:
        next_cursor = _create_cursor(patients[-1], cursor_fields=["id"])

    # Build conversation responses
    conversations = []
    total_unread = 0

    for patient in patients:
        # Get latest messages
        messages = db.query(Message).filter(
            Message.patient_id == patient.id
        ).order_by(Message.created_at.desc()).limit(10).all()

        # Count unread (inbound messages not read)
        unread_count = db.query(func.count(Message.id)).filter(
            Message.patient_id == patient.id,
            Message.direction == MessageDirection.INBOUND,
            Message.read_at.is_(None)
        ).scalar()

        total_unread += unread_count

        last_message_at = messages[0].created_at if messages else None

        conversations.append({
            "patient_id": str(patient.id),
            "patient": {
                "id": str(patient.id),
                "name": patient.name,
                "phone": patient.phone,
            },
            "messages": [_serialize_message(msg) for msg in messages],
            "unread_count": unread_count,
            "last_message_at": last_message_at.isoformat() if last_message_at else None,
            "messaging_mode": "conversational",
        })

    return {
        "data": conversations,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
        "total_unread": total_unread,
    }


@router.get(
    "/conversations/{patient_id}/unread",
    summary="Get unread message count",
    description="Get count of unread messages for a patient"
)
async def get_unread_count(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Get unread message count for a patient."""
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )

    # Verify patient exists and access
    patient = db.query(Patient).filter(Patient.id == patient_uuid).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )

    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN and str(patient.doctor_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    unread_count = db.query(func.count(Message.id)).filter(
        Message.patient_id == patient_uuid,
        Message.direction == MessageDirection.INBOUND,
        Message.read_at.is_(None)
    ).scalar()

    return {
        "patient_id": patient_id,
        "unread_count": unread_count,
    }


@router.post(
    "/conversations/{patient_id}/mark-read",
    summary="Mark conversation as read",
    description="Mark all messages in a conversation as read"
)
async def mark_conversation_read(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Mark all messages in a conversation as read."""
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )

    # Verify patient exists and access
    patient = db.query(Patient).filter(Patient.id == patient_uuid).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )

    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN and str(patient.doctor_id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Mark all inbound messages as read
    updated = db.query(Message).filter(
        Message.patient_id == patient_uuid,
        Message.direction == MessageDirection.INBOUND,
        Message.read_at.is_(None)
    ).update({"read_at": datetime.utcnow()})

    db.commit()

    return {
        "success": True,
        "patient_id": patient_id,
        "marked_read_count": updated,
    }


@router.get(
    "/search",
    response_model=MessageV2List,
    summary="Search messages",
    description="Search messages by content with cursor pagination"
)
async def search_messages(
    q: str = Query(..., min_length=1, description="Search query"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    pagination = Depends(get_pagination_params),
):
    """Search messages by content."""
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    query = db.query(Message).filter(Message.content.ilike(f"%{q}%"))

    # RBAC
    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN:
        user_uuid = UUID(user_id) if user_id else None
        query = query.join(Patient, Message.patient_id == Patient.id)
        query = query.filter(Patient.doctor_id == user_uuid)

    # Cursor pagination
    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"])
        cursor_created_at = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
        query = query.filter(
            (Message.created_at < cursor_created_at) |
            ((Message.created_at == cursor_created_at) & (Message.id > cursor_id))
        )

    total = None
    if not cursor_data:
        total = query.count()

    query = query.order_by(Message.created_at.desc(), Message.id)
    messages = query.limit(limit + 1).all()

    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    next_cursor = None
    if has_more and messages:
        next_cursor = _create_cursor(messages[-1])

    return {
        "data": [_serialize_message(msg) for msg in messages],
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }


@router.get(
    "/analytics/delivery-rate",
    summary="Get delivery rate analytics",
    description="Get delivery rate analytics over time (cached 15min)"
)
async def get_delivery_rate_analytics(
    days: int = Query(30, ge=1, le=365, description="Period in days"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """Get delivery rate analytics."""
    role_enum, user_id = _extract_user_context(current_user)

    cache_key = f"analytics:delivery_rate:{user_id}:{days}"

    def compute_analytics():
        start_date = datetime.utcnow() - timedelta(days=days)

        query = db.query(Message).filter(
            Message.created_at >= start_date,
            Message.direction == MessageDirection.OUTBOUND
        )

        # RBAC
        if role_enum != UserRole.ADMIN:
            user_uuid = UUID(user_id) if user_id else None
            query = query.join(Patient, Message.patient_id == Patient.id)
            query = query.filter(Patient.doctor_id == user_uuid)

        messages = query.all()

        total_sent = len(messages)
        delivered = sum(1 for m in messages if m.status in [MessageStatus.DELIVERED, MessageStatus.READ])
        failed = sum(1 for m in messages if m.status == MessageStatus.FAILED)

        delivery_rate = (delivered / total_sent * 100) if total_sent > 0 else 0
        failure_rate = (failed / total_sent * 100) if total_sent > 0 else 0

        return {
            "period_start": start_date.isoformat(),
            "period_end": datetime.utcnow().isoformat(),
            "total_sent": total_sent,
            "delivered": delivered,
            "failed": failed,
            "delivery_rate": round(delivery_rate, 2),
            "failure_rate": round(failure_rate, 2),
        }

    return await _get_cached_or_compute(redis_cache, cache_key, compute_analytics, ttl=900)


@router.get(
    "/analytics/response-time",
    summary="Get response time analytics",
    description="Get average response time analytics (cached 15min)"
)
async def get_response_time_analytics(
    days: int = Query(30, ge=1, le=365, description="Period in days"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """Get response time analytics."""
    role_enum, user_id = _extract_user_context(current_user)

    cache_key = f"analytics:response_time:{user_id}:{days}"

    def compute_analytics():
        start_date = datetime.utcnow() - timedelta(days=days)

        query = db.query(Message).filter(
            Message.created_at >= start_date,
            Message.sent_at.isnot(None),
            Message.delivered_at.isnot(None)
        )

        # RBAC
        if role_enum != UserRole.ADMIN:
            user_uuid = UUID(user_id) if user_id else None
            query = query.join(Patient, Message.patient_id == Patient.id)
            query = query.filter(Patient.doctor_id == user_uuid)

        messages = query.all()

        if not messages:
            return {
                "period_start": start_date.isoformat(),
                "period_end": datetime.utcnow().isoformat(),
                "total_messages": 0,
                "average_delivery_time_seconds": 0,
                "average_read_time_seconds": 0,
            }

        delivery_times = [(m.delivered_at - m.sent_at).total_seconds() for m in messages if m.delivered_at and m.sent_at]
        read_times = [(m.read_at - m.delivered_at).total_seconds() for m in messages if m.read_at and m.delivered_at]

        avg_delivery = sum(delivery_times) / len(delivery_times) if delivery_times else 0
        avg_read = sum(read_times) / len(read_times) if read_times else 0

        return {
            "period_start": start_date.isoformat(),
            "period_end": datetime.utcnow().isoformat(),
            "total_messages": len(messages),
            "average_delivery_time_seconds": round(avg_delivery, 2),
            "average_read_time_seconds": round(avg_read, 2),
        }

    return await _get_cached_or_compute(redis_cache, cache_key, compute_analytics, ttl=900)
