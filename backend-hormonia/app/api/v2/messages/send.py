"""
Messages API v2 - Send Operations
Handles message sending operations: send message, schedule message, cancel scheduled.
"""

from typing import Optional
from datetime import datetime, timedelta
from uuid import UUID
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.message import Message, MessageStatus, MessageType
from app.models.patient import Patient
from app.models.user import UserRole
from app.domain.messaging.core import MessageService
from app.domain.messaging.delivery import MessageSender
from app.services.unified_whatsapp_service import MessagingMode
from app.repositories.patient import PatientRepository
from app.schemas.v2.messages import (
    MessageV2List,
    SendMessageV2Request,
    SendMessageV2Response,
    CancelMessageV2Response,
)
from ..dependencies import get_pagination_params
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.utils.rate_limiter import limiter
from .helpers import (
    _extract_user_context,
    _serialize_message,
    _create_cursor,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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
    patient_repo = PatientRepository(db)
    patient = patient_repo.get_by_id(patient_uuid)
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
    message_sender = MessageSender(db, messaging_mode=MessagingMode.QUEUE)  # type: ignore[call-arg]

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
        await message_sender.send_message(message)  # type: ignore[call-arg]
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

    message_sender = MessageSender(db, messaging_mode=MessagingMode.QUEUE)  # type: ignore[call-arg]
    status_info = await message_sender.get_message_delivery_status(msg_uuid)  # type: ignore[attr-defined]

    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )

    return status_info
