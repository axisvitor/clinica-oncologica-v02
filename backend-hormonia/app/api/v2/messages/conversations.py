"""
Messages API v2 - Conversation Management
Handles conversation-related operations: history, list, unread counts, mark as read, search, and inbound messages.

6 endpoints:
- GET "/conversations/{patient_id}" - Get conversation history for a patient
- GET "/conversations" - List all conversations
- GET "/conversations/{patient_id}/unread" - Get unread message count
- POST "/conversations/{patient_id}/mark-read" - Mark conversation as read
- GET "/search" - Search messages by content
- POST "/inbound" - Process inbound message from webhook
"""

from typing import Optional, List
from datetime import datetime
from uuid import UUID
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database import get_db
from app.models.message import Message, MessageType, MessageDirection
from app.models.patient import Patient
from app.models.user import UserRole
from app.services.message import MessageService
from app.schemas.v2.messages import (
    MessageV2List,
    InboundMessageV2Request,
    InboundMessageV2Response,
    ConversationV2List,
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


# ============================================================================
# Conversation Operations (6 endpoints)
# ============================================================================

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
    include: Optional[List[str]] = Query(None, description="Eager load relations (patient)"),
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
