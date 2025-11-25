"""
Messages API v2 - Retry Operations
Handles retry and resend operations: retry failed message, resend message.
"""

from typing import Optional
from datetime import datetime
from uuid import UUID
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.message import Message, MessageStatus
from app.models.patient import Patient
from app.models.user import UserRole
from app.domain.messaging.core import MessageService
from app.domain.messaging.delivery import MessageSender
from app.services.unified_whatsapp_service import MessagingMode
from app.schemas.v2.messages import (
    MessageV2Response,
    RetryMessageV2Request,
    FailedMessagesV2List,
)
from ..dependencies import get_pagination_params
from app.dependencies.auth_dependencies import get_current_user_from_session
from .helpers import (
    _extract_user_context,
    _serialize_message,
    _create_cursor,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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
    message_sender = MessageSender(db, messaging_mode=MessagingMode.LEGACY)  # type: ignore[call-arg]
    background_tasks.add_task(message_sender.send_message, message)  # type: ignore[call-arg]

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
    message_sender = MessageSender(db, messaging_mode=MessagingMode.LEGACY)  # type: ignore[call-arg]

    retry_count = await message_sender.retry_failed_messages(limit)  # type: ignore[attr-defined]

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
