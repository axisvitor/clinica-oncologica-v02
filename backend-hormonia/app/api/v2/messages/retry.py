"""
Messages API v2 - Retry Operations
Handles retry and resend operations: retry failed message, resend message.
"""

from typing import Optional
from uuid import UUID
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.message import Message, MessageStatus
from app.models.user import UserRole
from app.domain.messaging.core import MessageService
from app.tasks.messaging import (
    send_scheduled_message,
    retry_failed_messages as retry_failed_messages_task,
)
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
    _apply_message_created_cursor_filter,
    _paginate_query,
    _load_message_with_access,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/{message_id}/retry",
    response_model=MessageV2Response,
    summary="Retry failed message",
    description="Retry sending a specific failed message",
)
async def retry_message(
    message_id: str,
    retry_request: Optional[RetryMessageV2Request] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """Retry sending a failed message."""
    message_service = MessageService(db)
    msg_uuid, message, _ = _load_message_with_access(
        db=db,
        current_user=current_user,
        message_id=message_id,
        message_service=message_service,
    )

    # Check if message can be retried
    if message.status not in [MessageStatus.FAILED, MessageStatus.PENDING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message can only be retried if it's in FAILED or PENDING status",
        )

    # Update content if provided
    if retry_request and retry_request.new_content:
        message.content = retry_request.new_content
        db.commit()

    # Update status to pending with atomic increment (prevents race condition)
    # Uses pessimistic locking to ensure retry_count is atomically incremented
    db.query(Message).filter(Message.id == message.id).with_for_update().update(
        {
            Message.status: MessageStatus.PENDING,
            Message.retry_count: func.coalesce(Message.retry_count, 0) + 1,
        },
        synchronize_session="fetch",
    )
    db.commit()
    db.refresh(message)

    # Retry the message via Celery task (after atomic update to avoid race condition)
    send_scheduled_message.delay(str(message.id))

    return _serialize_message(message)


@router.post(
    "/retry-failed",
    summary="Retry all failed messages",
    description="Retry sending all failed messages (batch operation)",
)
async def retry_failed_messages(
    limit: int = Query(50, ge=1, le=100, description="Max messages to retry"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """Retry all failed messages via Celery task."""
    # Dispatch Celery task for async processing
    task_result = retry_failed_messages_task.delay(limit=limit, max_retries=3)

    return {
        "success": True,
        "message": "Retry process initiated",
        "task_id": task_result.id,
        "limit": limit,
    }


@router.get(
    "/failed",
    response_model=FailedMessagesV2List,
    summary="List failed messages",
    description="Get list of failed messages with cursor pagination",
)
async def list_failed_messages(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    pagination=Depends(get_pagination_params),
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

    query = _apply_message_created_cursor_filter(query, cursor_data)
    messages, has_more, next_cursor, total = _paginate_query(
        query,
        limit=limit,
        cursor_data=cursor_data,
        order_columns=(Message.created_at.desc(), Message.id),
    )

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
