"""
Message handling endpoints for Hormonia Backend System.
"""
from typing import List, Optional, Any
import asyncio
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.middleware.rls_middleware import (
    get_jwt_token, get_user_context, require_authentication,
    optional_authentication, rls_middleware
)
from app.core.database import RLSError, RLSAccessDeniedError
from app.models.user import User
from app.models.message import MessageStatus, MessageType
from app.services.message import MessageService
from app.services.message_sender import MessageSender
from app.services.unified_whatsapp_service import MessagingMode
from app.services.patient import PatientService
from app.schemas.message import (
    MessageResponse, 
    MessageListResponse, 
    ScheduleMessageRequest,
    InboundMessageRequest,
    MessageUpdate,
)
from app.schemas.common import PaginationParams


router = APIRouter()


@router.get("", response_model=MessageListResponse)
async def get_messages(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    patient_id: Optional[UUID] = Query(None, description="Filter by patient ID"),
    status: Optional[MessageStatus] = Query(None, description="Filter by message status"),
    message_type: Optional[MessageType] = Query(None, description="Filter by message type"),
    start_date: Optional[datetime] = Query(None, description="Filter messages from this date"),
    end_date: Optional[datetime] = Query(None, description="Filter messages until this date"),
    current_user: User = Depends(get_current_user),
    user_context: dict = Depends(require_authentication),
    jwt_token: Optional[str] = Depends(get_jwt_token),
):
    """Get messages with optional filters."""
    try:
        # Get RLS-aware database session
        from app.core.database import get_db
        async for db in get_db(jwt_token=jwt_token, user_id=user_context.get('user_id')):
            message_service = MessageService(db)

            # Get messages with filters
            messages = message_service.get_messages_with_filters(
                skip=skip,
                limit=limit,
                patient_id=patient_id,
                status=status,
                message_type=message_type,
                start_date=start_date,
                end_date=end_date
            )

            # Get total count with same filters
            total = message_service.count_messages_with_filters(
                patient_id=patient_id,
                status=status,
                message_type=message_type,
                start_date=start_date,
                end_date=end_date
            )

            return MessageListResponse(
                messages=[MessageResponse.from_orm(msg) for msg in messages],
                total=total,
                skip=skip,
                limit=limit
            )

    except RLSError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"RLS error in get_messages: {e}")
        raise rls_middleware.handle_rls_error(e, user_context)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting messages: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve messages"
        )


@router.get("/conversations/{patient_id}", response_model=MessageListResponse)
async def get_patient_conversations(
    patient_id: UUID,
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    user_context: dict = Depends(require_authentication),
    jwt_token: Optional[str] = Depends(get_jwt_token),
):
    """Get conversation history for a specific patient."""
    # Get RLS-aware database session
    from app.core.database import get_db
    async for db in get_db(jwt_token=jwt_token, user_id=user_context.get('user_id')):
        message_service = MessageService(db)
        patient_service = PatientService(db)

        # Verify patient exists and user has access
        patient = patient_service.get_patient(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        # Get conversation history
        messages = message_service.get_conversation_history(patient_id, skip, limit)

        return MessageListResponse(
            messages=[MessageResponse.from_orm(msg) for msg in messages],
            total=message_service.count_conversation_history(patient_id),
            skip=skip,
            limit=limit
        )


@router.post("/send", response_model=MessageResponse)
async def send_manual_message(
    request: ScheduleMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send a manual message to a patient."""
    message_service = MessageService(db)
    message_sender = MessageSender(db, messaging_mode=MessagingMode.LEGACY)
    patient_service = PatientService(db)
    
    # Verify patient exists
    patient = patient_service.get_patient(request.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Create message
    message = message_service.schedule_message(
        patient_id=request.patient_id,
        content=request.content,
        scheduled_for=request.scheduled_for,
        message_type=request.type,
        message_metadata=request.message_metadata
    )
    
    # Send immediately if scheduled for now or past
    if request.scheduled_for <= datetime.utcnow():
        try:
            await message_sender.send_message(message)
        except Exception as e:
            # Message will be marked as failed by the sender
            pass
    
    return MessageResponse.from_orm(message)


@router.get("/scheduled", response_model=MessageListResponse)
async def get_scheduled_messages(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    patient_id: Optional[UUID] = Query(None),
    status: Optional[MessageStatus] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get scheduled messages with optional filtering."""
    message_service = MessageService(db)
    if patient_id:
        if status:
            messages = message_service.get_messages_by_status(status, skip, limit)
            messages = [msg for msg in messages if msg.patient_id == patient_id]
            total = message_service.count_by_status(status, patient_id)
        else:
            messages = message_service.get_pending_messages(skip, limit, patient_id)
            total = message_service.count_pending_messages(patient_id)
    else:
        if status:
            messages = message_service.get_messages_by_status(status, skip, limit)
            total = message_service.count_by_status(status)
        else:
            messages = message_service.get_pending_messages(skip, limit)
            total = message_service.count_pending_messages()

    return MessageListResponse(
        messages=[MessageResponse.from_orm(msg) for msg in messages],
        total=total,
        skip=skip,
        limit=limit
    )


@router.put("/{message_id}/cancel", response_model=MessageResponse)
async def cancel_scheduled_message(
    message_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancel a scheduled message."""
    message_service = MessageService(db)
    
    message = message_service.get_message(message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Only allow canceling pending messages
    if message.status != MessageStatus.PENDING:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel message with status: {message.status.value}"
        )
    
    # Mark as failed with cancellation reason
    updated_message = message_service.mark_as_failed(
        message_id, 
        {"reason": "cancelled_by_user", "cancelled_by": str(current_user.id)}
    )
    
    if not updated_message:
        raise HTTPException(status_code=500, detail="Failed to cancel message")
    
    return MessageResponse.from_orm(updated_message)


@router.get("/patient/{patient_id}/stats", response_model=None)
async def get_patient_message_stats(
    patient_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Get message statistics for a patient."""
    message_service = MessageService(db)
    patient_service = PatientService(db)
    
    # Verify patient exists
    patient = patient_service.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Get all messages for patient
    all_messages = message_service.get_patient_messages(patient_id, skip=0, limit=1000)
    
    # Calculate statistics
    stats = {
        "total_messages": len(all_messages),
        "inbound_messages": len([m for m in all_messages if m.direction.value == "inbound"]),
        "outbound_messages": len([m for m in all_messages if m.direction.value == "outbound"]),
        "pending_messages": len([m for m in all_messages if m.status == MessageStatus.PENDING]),
        "sent_messages": len([m for m in all_messages if m.status == MessageStatus.SENT]),
        "delivered_messages": len([m for m in all_messages if m.status == MessageStatus.DELIVERED]),
        "read_messages": len([m for m in all_messages if m.status == MessageStatus.READ]),
        "failed_messages": len([m for m in all_messages if m.status == MessageStatus.FAILED]),
        "last_message_at": max([m.created_at for m in all_messages]) if all_messages else None,
        "message_types": {
            "text": len([m for m in all_messages if m.type == MessageType.TEXT]),
            "button": len([m for m in all_messages if m.type == MessageType.BUTTON]),
            "list": len([m for m in all_messages if m.type == MessageType.LIST]),
            "media": len([m for m in all_messages if m.type == MessageType.MEDIA])
        }
    }
    
    return stats


@router.get("/{message_id}/status", response_model=None)
async def get_message_status(
    message_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Get detailed delivery status for a message."""
    message_sender = MessageSender(db, messaging_mode=MessagingMode.LEGACY)
    
    status_info = await message_sender.get_message_delivery_status(message_id)
    
    if not status_info:
        raise HTTPException(status_code=404, detail="Message not found")
    
    return status_info


@router.post("/{message_id}/retry", response_model=MessageResponse)
async def retry_message(
    message_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retry sending a specific failed message."""
    message_service = MessageService(db)
    message_sender = MessageSender(db, messaging_mode=MessagingMode.LEGACY)

    # Get message
    message = message_service.get_message(message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Check if message can be retried
    if message.status not in [MessageStatus.FAILED, MessageStatus.PENDING]:
        raise HTTPException(
            status_code=400,
            detail="Message can only be retried if it's in FAILED or PENDING status"
        )

    # Retry the message em background (Starlette suporta corrotinas em BackgroundTasks)
    background_tasks.add_task(message_sender.send_message, message)

    # Update status to pending (por ID)
    message_service.update_message(message_id, MessageUpdate(status=MessageStatus.PENDING))

    # Return updated message
    updated_message = message_service.get_message(message_id)
    return MessageResponse.from_orm(updated_message)


@router.post("/retry-failed", response_model=None)
async def retry_failed_messages(
    background_tasks: BackgroundTasks,
    limit: int = Query(50, ge=1, le=100),
    max_retries: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Retry sending failed messages."""
    message_sender = MessageSender(db, messaging_mode=MessagingMode.LEGACY)
    
    retry_count = await message_sender.retry_failed_messages(limit)
    
    return {
        "message": f"Retry process completed",
        "retried_count": retry_count,
        "limit": limit,
        "max_retries": max_retries
    }


@router.get("/failed", response_model=MessageListResponse)
async def get_failed_messages(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get failed messages for review and retry."""
    message_service = MessageService(db)
    
    failed_messages = message_service.get_failed_messages(skip, limit)

    return MessageListResponse(
        messages=[MessageResponse.from_orm(msg) for msg in failed_messages],
        total=message_service.count_failed_messages(),
        skip=skip,
        limit=limit
    )


@router.get("/status/{status}", response_model=MessageListResponse)
async def get_messages_by_status(
    status: MessageStatus,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get messages by status."""
    message_service = MessageService(db)
    
    messages = message_service.get_messages_by_status(status, skip, limit)

    return MessageListResponse(
        messages=[MessageResponse.from_orm(msg) for msg in messages],
        total=message_service.count_by_status(status),
        skip=skip,
        limit=limit
    )


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific message by ID."""
    message_service = MessageService(db)

    message = message_service.get_message(message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    return MessageResponse.from_orm(message)


@router.get("/statistics", response_model=None)
async def get_message_statistics(
    days: int = Query(30, ge=1, le=365),
    patient_id: Optional[UUID] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Get message statistics with optional filtering."""
    message_service = MessageService(db)
    
    statistics = message_service.get_message_statistics(patient_id, start_date, end_date)
    
    return {
        "statistics": statistics,
        "filters": {
            "patient_id": str(patient_id) if patient_id else None,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        }
    }
