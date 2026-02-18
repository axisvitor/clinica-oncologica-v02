"""
Messages API v2 - CRUD Operations
Handles basic CRUD operations: list, get, create, update, delete messages.
"""

from typing import Optional, List
from datetime import datetime
from uuid import UUID
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_

from app.database import get_db
from app.models.message import Message, MessageStatus, MessageType, MessageDirection
from app.models.patient import Patient
from app.models.user import UserRole
from app.schemas.v2.messages import (
    MessageV2Response,
    MessageV2List,
    MessageStatusV2,
)
from ..dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
    apply_field_selection,
)
from app.dependencies.auth_dependencies import get_current_user_from_session
from .helpers import (
    _extract_user_context,
    _serialize_message,
    _apply_message_created_cursor_filter,
    _paginate_messages_query,
    _paginate_query,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/",
    response_model=MessageV2List,
    summary="List messages with filters",
    description="Get paginated list of messages with cursor pagination and optional filters",
)
async def list_messages(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    pagination=Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    status_filter: Optional[MessageStatusV2] = Query(
        None, alias="status", description="Filter by status"
    ),
    direction: Optional[str] = Query(
        None, description="Filter by direction (inbound/outbound)"
    ),
    message_type: Optional[str] = Query(
        None, alias="type", description="Filter by message type"
    ),
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
                detail="Unable to determine user permissions",
            )
        # Join with patients to filter by doctor_id
        query = query.join(Patient, Message.patient_id == Patient.id)
        filters.append(Patient.doctor_id == user_uuid)

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
    query = _apply_message_created_cursor_filter(query, cursor_data)
    messages, has_more, next_cursor, total = _paginate_query(
        query,
        limit=limit,
        cursor_data=cursor_data,
        order_columns=(Message.created_at.desc(), Message.id),
    )

    # Convert to response models
    message_responses = []
    for message in messages:
        msg_dict = _serialize_message(
            message, include_patient="patient" in (include or [])
        )

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
    description="Get a single message with optional field selection and eager loading",
)
async def get_message(
    message_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    """Get a single message by ID."""
    try:
        msg_uuid = UUID(message_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid message ID format"
        )

    query = db.query(Message)

    if include and "patient" in include:
        query = query.options(joinedload(Message.patient))

    message = query.filter(Message.id == msg_uuid).first()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message {message_id} not found",
        )

    # RBAC check
    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN:
        patient = db.query(Patient).filter(Patient.id == message.patient_id).first()
        if not patient or str(patient.doctor_id) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

    msg_dict = _serialize_message(message, include_patient="patient" in (include or []))

    if fields:
        msg_dict = apply_field_selection(msg_dict, fields)

    return msg_dict


@router.get(
    "/status/{status}",
    response_model=MessageV2List,
    summary="Filter messages by status",
    description="Get messages filtered by specific status with cursor pagination",
)
async def filter_by_status(
    status: MessageStatusV2,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    pagination=Depends(get_pagination_params),
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
            status_code=status.HTTP_400_BAD_REQUEST,  # type: ignore[attr-defined]
            detail="Invalid status",
        )

    query = db.query(Message).filter(Message.status == db_status)

    # RBAC
    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN:
        user_uuid = UUID(user_id) if user_id else None
        query = query.join(Patient, Message.patient_id == Patient.id)
        query = query.filter(Patient.doctor_id == user_uuid)

    query = _apply_message_created_cursor_filter(query, cursor_data)
    return _paginate_messages_query(query, limit=limit, cursor_data=cursor_data)
