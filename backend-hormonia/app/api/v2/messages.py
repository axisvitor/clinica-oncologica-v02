"""
Messages API v2
Enhanced message endpoints with cursor pagination, field selection, and caching.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
import json
import base64
import hashlib
import logging

from app.database import get_db
from app.models.message import Message, MessageStatus, MessageType, MessageDirection
from app.models.patient import Patient
from app.models.user import User
from app.schemas.v2.messages import (
    MessageV2Response,
    MessageV2List,
    MessageV2Create,
    MessageV2Update,
    MessageStatusV2,
    MessageTypeV2,
    PatientV2Brief,
    BulkMessageV2Request,
    BulkMessageV2Response,
)
from app.schemas.v2.common import CursorEncoder
from .dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
)
from app.dependencies.auth_dependencies import get_current_user_from_session, get_redis_cache
from app.services.message import MessageService
from app.domain.messaging.delivery import MessageSender
from app.services.unified_whatsapp_service import MessagingMode
from app.services.patient import PatientService
from app.utils.rate_limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)

# Cache TTL configuration
CACHE_TTL_LIST = 300  # 5 minutes for list endpoints
CACHE_TTL_SINGLE = 600  # 10 minutes for single item endpoints


def _generate_cache_key(prefix: str, **kwargs) -> str:
    """
    Generate a deterministic cache key from prefix and parameters.

    Args:
        prefix: Cache key prefix (e.g., "messages_list")
        **kwargs: Key-value pairs to include in cache key

    Returns:
        SHA256-based cache key string
    """
    # Sort kwargs to ensure consistent key generation
    sorted_params = sorted(kwargs.items())
    params_str = json.dumps(sorted_params, default=str)
    hash_obj = hashlib.sha256(f"{prefix}:{params_str}".encode())
    return f"v2:{prefix}:{hash_obj.hexdigest()[:16]}"


def _map_status_to_v1(status_v2: MessageStatusV2) -> MessageStatus:
    """Map V2 status enum to V1 status enum."""
    mapping = {
        MessageStatusV2.PENDING: MessageStatus.PENDING,
        MessageStatusV2.SCHEDULED: MessageStatus.SCHEDULED,
        MessageStatusV2.SENT: MessageStatus.SENT,
        MessageStatusV2.DELIVERED: MessageStatus.DELIVERED,
        MessageStatusV2.READ: MessageStatus.READ,
        MessageStatusV2.FAILED: MessageStatus.FAILED,
        MessageStatusV2.CANCELLED: MessageStatus.CANCELLED,
    }
    return mapping.get(status_v2, MessageStatus.PENDING)


def _map_status_to_v2(status_v1: MessageStatus) -> MessageStatusV2:
    """Map V1 status enum to V2 status enum."""
    mapping = {
        MessageStatus.PENDING: MessageStatusV2.PENDING,
        MessageStatus.SCHEDULED: MessageStatusV2.SCHEDULED,
        MessageStatus.SENDING: MessageStatusV2.SENT,  # Map SENDING to SENT
        MessageStatus.SENT: MessageStatusV2.SENT,
        MessageStatus.DELIVERED: MessageStatusV2.DELIVERED,
        MessageStatus.READ: MessageStatusV2.READ,
        MessageStatus.FAILED: MessageStatusV2.FAILED,
        MessageStatus.CANCELLED: MessageStatusV2.CANCELLED,
    }
    return mapping.get(status_v1, MessageStatusV2.PENDING)


def _serialize_message(
    message: Message,
    include_patient: bool = False,
    include_sender: bool = False
) -> Dict[str, Any]:
    """
    Serialize Message model to V2 response format.

    Args:
        message: Message SQLAlchemy model
        include_patient: Whether to include patient details
        include_sender: Whether to include sender details

    Returns:
        Dictionary with message data in V2 format
    """
    data = {
        "id": str(message.id),
        "patient_id": str(message.patient_id),
        "content": message.content or "",
        "type": message.type.value if hasattr(message.type, 'value') else str(message.type),
        "direction": message.direction.value if hasattr(message.direction, 'value') else str(message.direction),
        "status": _map_status_to_v2(message.status).value,
        "message_metadata": message.message_metadata or {},
        "scheduled_for": message.scheduled_for,
        "sent_at": message.sent_at,
        "delivered_at": message.delivered_at,
        "read_at": message.read_at,
        "whatsapp_id": message.whatsapp_id,
        "error_message": message.failure_reason,
        "retry_count": message.retry_count or 0,
        "created_at": message.created_at,
        "updated_at": message.updated_at,
    }

    # Add computed fields
    if message.sent_at and message.delivered_at:
        delta = (message.delivered_at - message.sent_at).total_seconds()
        data["delivery_time_seconds"] = delta

    if message.delivered_at and message.read_at:
        delta = (message.read_at - message.delivered_at).total_seconds()
        data["read_time_seconds"] = delta

    # Include relationships if requested
    if include_patient and hasattr(message, 'patient') and message.patient:
        data["patient"] = {
            "id": str(message.patient.id),
            "name": message.patient.name,
            "phone": message.patient.phone,
        }

    return data


@router.get("", response_model=MessageV2List)
@limiter.limit("50/minute")
async def list_messages(
    request: Request,
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    fields: Optional[str] = Query(None, description="Comma-separated fields to include"),
    include: Optional[str] = Query(None, description="Comma-separated relations (patient,sender)"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    status: Optional[MessageStatusV2] = Query(None, description="Filter by status"),
    message_type: Optional[MessageTypeV2] = Query(None, description="Filter by type"),
    direction: Optional[str] = Query(None, description="Filter by direction (inbound/outbound)"),
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    List messages with cursor-based pagination and advanced filtering.

    **Features:**
    - Cursor-based pagination for efficient large dataset traversal
    - Field selection to reduce payload size (?fields=id,status,content)
    - Eager loading of relationships (?include=patient,sender)
    - Redis caching (5 min TTL) for improved performance
    - Comprehensive filtering by patient, status, type, direction, date range

    **Rate Limit:** 50 requests/minute

    **Cache Strategy:**
    - Cache key includes all query parameters for accurate invalidation
    - Automatic cache invalidation on message updates
    """
    try:
        # Generate cache key
        cache_key = _generate_cache_key(
            "messages_list",
            cursor=cursor,
            limit=limit,
            patient_id=patient_id,
            status=status.value if status else None,
            message_type=message_type.value if message_type else None,
            direction=direction,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
        )

        # Try to get from cache
        try:
            cached = await redis_cache.get(cache_key)
            if cached:
                logger.debug(f"Cache HIT for key: {cache_key}")
                return MessageV2List(**json.loads(cached))
        except Exception as e:
            logger.warning(f"Cache retrieval error: {e}")

        # Parse cursor
        cursor_data = None
        if cursor:
            try:
                cursor_data = CursorEncoder.decode(cursor)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid cursor: {str(e)}"
                )

        # Parse includes
        include_patient = False
        include_sender = False
        if include:
            includes = [i.strip().lower() for i in include.split(",")]
            include_patient = "patient" in includes
            include_sender = "sender" in includes

        # Build query
        message_service = MessageService(db)
        query = db.query(Message)

        # Apply eager loading
        if include_patient:
            query = query.options(joinedload(Message.patient))

        # Apply cursor pagination
        if cursor_data:
            cursor_id = cursor_data.get("id")
            cursor_created_at = cursor_data.get("created_at")
            if cursor_created_at:
                cursor_created_at = datetime.fromisoformat(cursor_created_at)

            if cursor_id and cursor_created_at:
                query = query.filter(
                    (Message.created_at < cursor_created_at) |
                    ((Message.created_at == cursor_created_at) & (Message.id < UUID(cursor_id)))
                )

        # Apply filters
        if patient_id:
            try:
                query = query.filter(Message.patient_id == UUID(patient_id))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid patient_id format"
                )

        if status:
            status_v1 = _map_status_to_v1(status)
            query = query.filter(Message.status == status_v1)

        if message_type:
            # Map V2 type to V1 type if needed
            query = query.filter(Message.type == message_type.value)

        if direction:
            if direction.lower() == "inbound":
                query = query.filter(Message.direction == MessageDirection.INBOUND)
            elif direction.lower() == "outbound":
                query = query.filter(Message.direction == MessageDirection.OUTBOUND)

        if start_date:
            query = query.filter(Message.created_at >= start_date)

        if end_date:
            query = query.filter(Message.created_at <= end_date)

        # Order by created_at DESC, id DESC for stable pagination
        query = query.order_by(Message.created_at.desc(), Message.id.desc())

        # Fetch limit + 1 to determine if there are more results
        messages = query.limit(limit + 1).all()

        # Check if there are more results
        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        # Generate next cursor
        next_cursor = None
        if has_more and messages:
            last_message = messages[-1]
            next_cursor = CursorEncoder.encode(last_message.id, last_message.created_at)

        # Serialize messages
        data = [
            _serialize_message(msg, include_patient=include_patient, include_sender=include_sender)
            for msg in messages
        ]

        # Apply field selection if specified
        if fields:
            field_list = [f.strip() for f in fields.split(",")]
            data = [
                {k: v for k, v in item.items() if k in field_list}
                for item in data
            ]

        # Get total count (expensive, consider removing for large datasets)
        total_query = db.query(Message)
        if patient_id:
            total_query = total_query.filter(Message.patient_id == UUID(patient_id))
        if status:
            total_query = total_query.filter(Message.status == _map_status_to_v1(status))
        total = total_query.count()

        # Build response
        response = MessageV2List(
            data=data,
            next_cursor=next_cursor,
            has_more=has_more,
            total=total,
        )

        # Cache response
        try:
            await redis_cache.set(
                cache_key,
                json.dumps(response.dict(), default=str),
                ttl=CACHE_TTL_LIST
            )
        except Exception as e:
            logger.warning(f"Cache storage error: {e}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing messages: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve messages"
        )


@router.get("/{id}", response_model=MessageV2Response)
@limiter.limit("100/minute")
async def get_message(
    id: str,
    request: Request,
    include: Optional[str] = Query(None, description="Comma-separated relations (patient,sender)"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Get a single message by ID with optional relationship loading.

    **Features:**
    - Single message retrieval with full details
    - Eager loading of patient and sender relationships
    - Redis caching (10 min TTL) for frequently accessed messages

    **Rate Limit:** 100 requests/minute

    **Error Codes:**
    - 400: Invalid message ID format
    - 404: Message not found
    - 500: Server error
    """
    try:
        # Validate UUID format
        try:
            message_uuid = UUID(id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid message ID format"
            )

        # Generate cache key
        cache_key = _generate_cache_key("message_single", id=id, include=include)

        # Try cache
        try:
            cached = await redis_cache.get(cache_key)
            if cached:
                logger.debug(f"Cache HIT for message: {id}")
                return MessageV2Response(**json.loads(cached))
        except Exception as e:
            logger.warning(f"Cache retrieval error: {e}")

        # Parse includes
        include_patient = False
        include_sender = False
        if include:
            includes = [i.strip().lower() for i in include.split(",")]
            include_patient = "patient" in includes
            include_sender = "sender" in includes

        # Build query
        query = db.query(Message).filter(Message.id == message_uuid)

        if include_patient:
            query = query.options(joinedload(Message.patient))

        message = query.first()

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message {id} not found"
            )

        # Serialize
        data = _serialize_message(message, include_patient=include_patient, include_sender=include_sender)
        response = MessageV2Response(**data)

        # Cache response
        try:
            await redis_cache.set(
                cache_key,
                json.dumps(response.dict(), default=str),
                ttl=CACHE_TTL_SINGLE
            )
        except Exception as e:
            logger.warning(f"Cache storage error: {e}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving message {id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve message"
        )


@router.post("", response_model=MessageV2Response, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def send_message(
    message_data: MessageV2Create,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Send a new message to a patient.

    **Features:**
    - Immediate or scheduled message delivery
    - Template support with variable substitution
    - Background task queuing for async delivery
    - Idempotency key generation to prevent duplicates

    **Rate Limit:** 20 requests/minute

    **Request Body:**
    ```json
    {
        "patient_id": "uuid",
        "content": "Message content",
        "type": "text",
        "direction": "outbound",
        "scheduled_for": "2025-11-08T09:00:00Z",
        "message_metadata": {}
    }
    ```

    **Error Codes:**
    - 400: Invalid request data
    - 404: Patient not found
    - 500: Server error
    """
    try:
        # Validate patient exists
        try:
            patient_uuid = UUID(message_data.patient_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid patient_id format"
            )

        patient_service = PatientService(db)
        patient = patient_service.get_patient(patient_uuid)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient {message_data.patient_id} not found"
            )

        # Create message
        message_service = MessageService(db)

        # Generate idempotency key
        scheduled_time = message_data.scheduled_for or datetime.utcnow()
        idempotency_key = hashlib.sha256(
            f"{message_data.patient_id}:{message_data.content}:{scheduled_time.isoformat()}".encode()
        ).hexdigest()[:32]

        # Map V2 type to V1
        message_type_v1 = MessageType.TEXT  # Default
        if message_data.type == MessageTypeV2.TEXT:
            message_type_v1 = MessageType.TEXT
        elif message_data.type == MessageTypeV2.INTERACTIVE:
            message_type_v1 = MessageType.BUTTON

        message = message_service.schedule_message(
            patient_id=patient_uuid,
            content=message_data.content,
            scheduled_for=scheduled_time,
            message_type=message_type_v1,
            message_metadata=message_data.message_metadata or {},
            idempotency_key=idempotency_key,
        )

        # Send immediately if scheduled for now or past
        if scheduled_time <= datetime.utcnow():
            message_sender = MessageSender(db, messaging_mode=MessagingMode.LEGACY)
            background_tasks.add_task(message_sender.send_message, message)

        # Invalidate cache
        try:
            list_cache_pattern = _generate_cache_key("messages_list", patient_id=message_data.patient_id)
            await redis_cache.delete_pattern(f"v2:messages_list:*")
        except Exception as e:
            logger.warning(f"Cache invalidation error: {e}")

        # Serialize and return
        data = _serialize_message(message, include_patient=True)
        return MessageV2Response(**data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message"
        )


@router.patch("/{id}/read", response_model=MessageV2Response)
@limiter.limit("50/minute")
async def mark_message_as_read(
    id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Mark a message as read.

    **Features:**
    - Updates message status to READ
    - Records read timestamp
    - Invalidates cache for affected message

    **Rate Limit:** 50 requests/minute

    **Error Codes:**
    - 400: Invalid message ID or cannot mark as read
    - 404: Message not found
    - 500: Server error
    """
    try:
        # Validate UUID
        try:
            message_uuid = UUID(id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid message ID format"
            )

        message_service = MessageService(db)
        message = message_service.get_message(message_uuid)

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message {id} not found"
            )

        # Only allow marking delivered messages as read
        if message.status not in [MessageStatus.DELIVERED, MessageStatus.SENT]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot mark message as read. Current status: {message.status.value}"
            )

        # Update to READ status
        from app.schemas.message import MessageUpdate
        updated_message = message_service.update_message(
            message_uuid,
            MessageUpdate(status=MessageStatus.READ, read_at=datetime.utcnow())
        )

        # Invalidate cache
        try:
            cache_key = _generate_cache_key("message_single", id=id, include=None)
            await redis_cache.delete(cache_key)
            await redis_cache.delete_pattern(f"v2:messages_list:*")
        except Exception as e:
            logger.warning(f"Cache invalidation error: {e}")

        data = _serialize_message(updated_message)
        return MessageV2Response(**data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking message as read: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark message as read"
        )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def delete_message(
    id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Delete a message (soft delete by marking as cancelled).

    **Features:**
    - Soft delete: marks message as CANCELLED instead of hard delete
    - Only allows deletion of PENDING or SCHEDULED messages
    - Invalidates all related caches

    **Rate Limit:** 20 requests/minute

    **Error Codes:**
    - 400: Invalid ID or cannot delete message in current status
    - 404: Message not found
    - 500: Server error
    """
    try:
        # Validate UUID
        try:
            message_uuid = UUID(id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid message ID format"
            )

        message_service = MessageService(db)
        message = message_service.get_message(message_uuid)

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message {id} not found"
            )

        # Only allow deletion of pending/scheduled messages
        if message.status not in [MessageStatus.PENDING, MessageStatus.SCHEDULED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete message with status: {message.status.value}"
            )

        # Soft delete by marking as cancelled
        from app.schemas.message import MessageUpdate
        message_service.update_message(
            message_uuid,
            MessageUpdate(status=MessageStatus.CANCELLED)
        )

        # Invalidate cache
        try:
            cache_key = _generate_cache_key("message_single", id=id, include=None)
            await redis_cache.delete(cache_key)
            await redis_cache.delete_pattern(f"v2:messages_list:*")
        except Exception as e:
            logger.warning(f"Cache invalidation error: {e}")

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete message"
        )


@router.get("/conversations/{patient_id}", response_model=MessageV2List)
@limiter.limit("50/minute")
async def get_patient_conversation(
    patient_id: str,
    request: Request,
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    include: Optional[str] = Query(None, description="Comma-separated relations (patient)"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Get conversation history for a specific patient.

    **Features:**
    - Chronological conversation view (newest first)
    - Cursor-based pagination for efficient browsing
    - Optional patient details inclusion
    - Redis caching (5 min TTL)

    **Rate Limit:** 50 requests/minute

    **Use Case:**
    Perfect for chat interfaces where you need to display message history
    between the system and a specific patient.

    **Error Codes:**
    - 400: Invalid patient ID format
    - 404: Patient not found
    - 500: Server error
    """
    try:
        # Validate UUID
        try:
            patient_uuid = UUID(patient_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid patient_id format"
            )

        # Verify patient exists
        patient_service = PatientService(db)
        patient = patient_service.get_patient(patient_uuid)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient {patient_id} not found"
            )

        # Generate cache key
        cache_key = _generate_cache_key(
            "conversation",
            patient_id=patient_id,
            cursor=cursor,
            limit=limit
        )

        # Try cache
        try:
            cached = await redis_cache.get(cache_key)
            if cached:
                logger.debug(f"Cache HIT for conversation: {patient_id}")
                return MessageV2List(**json.loads(cached))
        except Exception as e:
            logger.warning(f"Cache retrieval error: {e}")

        # Parse cursor
        cursor_data = None
        if cursor:
            try:
                cursor_data = CursorEncoder.decode(cursor)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid cursor: {str(e)}"
                )

        # Parse includes
        include_patient = False
        if include:
            includes = [i.strip().lower() for i in include.split(",")]
            include_patient = "patient" in includes

        # Build query
        query = db.query(Message).filter(Message.patient_id == patient_uuid)

        if include_patient:
            query = query.options(joinedload(Message.patient))

        # Apply cursor
        if cursor_data:
            cursor_id = cursor_data.get("id")
            cursor_created_at = cursor_data.get("created_at")
            if cursor_created_at:
                cursor_created_at = datetime.fromisoformat(cursor_created_at)

            if cursor_id and cursor_created_at:
                query = query.filter(
                    (Message.created_at < cursor_created_at) |
                    ((Message.created_at == cursor_created_at) & (Message.id < UUID(cursor_id)))
                )

        # Order by created_at DESC for conversation view
        query = query.order_by(Message.created_at.desc(), Message.id.desc())

        # Fetch limit + 1
        messages = query.limit(limit + 1).all()

        # Check for more
        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        # Generate next cursor
        next_cursor = None
        if has_more and messages:
            last_message = messages[-1]
            next_cursor = CursorEncoder.encode(last_message.id, last_message.created_at)

        # Serialize
        data = [
            _serialize_message(msg, include_patient=include_patient)
            for msg in messages
        ]

        # Get total
        total = db.query(Message).filter(Message.patient_id == patient_uuid).count()

        response = MessageV2List(
            data=data,
            next_cursor=next_cursor,
            has_more=has_more,
            total=total,
        )

        # Cache
        try:
            await redis_cache.set(
                cache_key,
                json.dumps(response.dict(), default=str),
                ttl=CACHE_TTL_LIST
            )
        except Exception as e:
            logger.warning(f"Cache storage error: {e}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving conversation for patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversation"
        )


@router.post("/bulk", response_model=BulkMessageV2Response, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def send_bulk_messages(
    bulk_data: BulkMessageV2Request,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache),
):
    """
    Send bulk messages to multiple patients.

    **Features:**
    - Send same message to up to 1000 patients
    - Immediate or scheduled delivery
    - Batch ID tracking for monitoring
    - Background processing for performance
    - Detailed failure reporting

    **Rate Limit:** 10 requests/minute (strict due to resource intensity)

    **Request Body:**
    ```json
    {
        "patient_ids": ["uuid1", "uuid2", "uuid3"],
        "content": "Bulk message content",
        "type": "text",
        "scheduled_for": "2025-11-08T09:00:00Z",
        "message_metadata": {"campaign": "weekly_reminder"}
    }
    ```

    **Response:**
    - batch_id: Unique identifier for tracking
    - scheduled_count: Successfully scheduled messages
    - failed_count: Failed validations
    - failed_patients: List of patient IDs that failed

    **Error Codes:**
    - 400: Invalid request (empty list, invalid IDs, etc.)
    - 500: Server error
    """
    try:
        # Validate request
        if not bulk_data.patient_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="patient_ids cannot be empty"
            )

        if len(bulk_data.patient_ids) > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot send to more than 1000 patients at once"
            )

        # Generate batch ID
        batch_id = hashlib.sha256(
            f"{datetime.utcnow().isoformat()}:{len(bulk_data.patient_ids)}".encode()
        ).hexdigest()[:16]

        message_service = MessageService(db)
        patient_service = PatientService(db)

        scheduled_count = 0
        failed_count = 0
        failed_patients = []

        # Process each patient
        for patient_id_str in bulk_data.patient_ids:
            try:
                # Validate patient
                patient_uuid = UUID(patient_id_str)
                patient = patient_service.get_patient(patient_uuid)

                if not patient:
                    failed_patients.append(patient_id_str)
                    failed_count += 1
                    continue

                # Create message
                scheduled_time = bulk_data.scheduled_for or datetime.utcnow()

                # Add batch_id to metadata
                metadata = bulk_data.message_metadata or {}
                metadata["batch_id"] = batch_id

                # Generate idempotency key
                idempotency_key = hashlib.sha256(
                    f"{patient_id_str}:{bulk_data.content}:{scheduled_time.isoformat()}:{batch_id}".encode()
                ).hexdigest()[:32]

                message = message_service.schedule_message(
                    patient_id=patient_uuid,
                    content=bulk_data.content,
                    scheduled_for=scheduled_time,
                    message_type=MessageType.TEXT,
                    message_metadata=metadata,
                    idempotency_key=idempotency_key,
                )

                scheduled_count += 1

                # Send immediately if needed
                if scheduled_time <= datetime.utcnow():
                    message_sender = MessageSender(db, messaging_mode=MessagingMode.LEGACY)
                    background_tasks.add_task(message_sender.send_message, message)

            except ValueError:
                # Invalid UUID
                failed_patients.append(patient_id_str)
                failed_count += 1
            except Exception as e:
                logger.error(f"Error creating message for patient {patient_id_str}: {e}")
                failed_patients.append(patient_id_str)
                failed_count += 1

        # Invalidate cache
        try:
            await redis_cache.delete_pattern(f"v2:messages_list:*")
            await redis_cache.delete_pattern(f"v2:conversation:*")
        except Exception as e:
            logger.warning(f"Cache invalidation error: {e}")

        # Calculate estimated completion
        estimated_completion = None
        if bulk_data.scheduled_for:
            # Assume 1 message per second processing rate
            estimated_completion = bulk_data.scheduled_for + timedelta(seconds=scheduled_count)

        return BulkMessageV2Response(
            success=scheduled_count > 0,
            batch_id=batch_id,
            total_messages=len(bulk_data.patient_ids),
            scheduled_count=scheduled_count,
            failed_count=failed_count,
            failed_patients=failed_patients,
            estimated_completion=estimated_completion,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending bulk messages: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send bulk messages"
        )
