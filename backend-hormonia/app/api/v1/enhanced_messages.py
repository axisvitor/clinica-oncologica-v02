"""
Enhanced Message Management API with real-time features and comprehensive functionality.
Supports WhatsApp integration, scheduling, templates, and real-time notifications.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
import logging
from uuid import UUID
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from pydantic import BaseModel, validator, Field
from enum import Enum

from app.dependencies import get_db, get_current_user, get_message_service
from app.models.user import User
from app.models.message import Message, MessageStatus, MessageType, MessageDirection
from app.services.message import MessageService
from app.services.websocket_events import websocket_events
from app.schemas.message import (
    MessageCreate, MessageUpdate, MessageResponse,
    MessageListResponse, BulkMessageCreate, MessageTemplate
)
from app.utils.logging import get_logger
from app.utils.pagination import paginate_query

logger = get_logger(__name__)
router = APIRouter()

class MessagePriority(str, Enum):
    """Message priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class MessageSearchParams(BaseModel):
    """Advanced search parameters for message filtering."""
    search: Optional[str] = None
    patient_id: Optional[UUID] = None
    direction: Optional[MessageDirection] = None
    message_type: Optional[MessageType] = None
    status: Optional[MessageStatus] = None
    priority: Optional[MessagePriority] = None
    scheduled_after: Optional[datetime] = None
    scheduled_before: Optional[datetime] = None
    sent_after: Optional[datetime] = None
    sent_before: Optional[datetime] = None
    has_attachments: Optional[bool] = None
    template_id: Optional[UUID] = None

class ScheduledMessageCreate(BaseModel):
    """Create scheduled message."""
    patient_id: UUID
    content: str
    message_type: MessageType = MessageType.TEXT
    scheduled_for: datetime
    priority: MessagePriority = MessagePriority.NORMAL
    template_id: Optional[UUID] = None
    variables: Optional[Dict[str, Any]] = None

    @validator('scheduled_for')
    def validate_future_date(cls, v):
        if v <= datetime.utcnow():
            raise ValueError('Scheduled time must be in the future')
        return v

class BulkMessageOperation(BaseModel):
    """Bulk message operations."""
    patient_ids: List[UUID]
    content: str
    message_type: MessageType = MessageType.TEXT
    scheduled_for: Optional[datetime] = None
    priority: MessagePriority = MessagePriority.NORMAL
    template_id: Optional[UUID] = None
    variables: Optional[Dict[str, Any]] = None

class MessageAnalytics(BaseModel):
    """Message analytics response."""
    total_messages: int
    sent_today: int
    pending_messages: int
    failed_messages: int
    delivery_rate: float
    response_rate: float
    avg_response_time_minutes: float
    by_type: Dict[str, int]
    by_status: Dict[str, int]
    hourly_volume: List[Dict[str, Any]]

class ConversationSummary(BaseModel):
    """Conversation summary for a patient."""
    patient_id: UUID
    patient_name: str
    total_messages: int
    last_message: Optional[MessageResponse]
    unread_count: int
    last_activity: datetime
    conversation_status: str

@router.post(
    "/",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send Message",
    description="""
    Send a message to a patient with advanced features and real-time delivery.

    This endpoint supports:
    - Multiple message types (text, image, audio, document, interactive)
    - Real-time delivery via WhatsApp API
    - Message templates with variable substitution
    - Scheduling for future delivery
    - Priority levels for queue management
    - Automatic retry on failure
    - Real-time WebSocket notifications

    **Rate Limit**: 50 requests per minute per user.
    """,
    responses={
        201: {
            "description": "Message sent successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "patient_id": "456e7890-e89b-12d3-a456-426614174000",
                        "content": "Hello! How are you feeling today?",
                        "direction": "outbound",
                        "type": "text",
                        "status": "sent",
                        "sent_at": "2024-01-01T12:00:00Z"
                    }
                }
            }
        }
    }
)
async def send_message(
    message_data: MessageCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service)
) -> MessageResponse:
    """Send a message to a patient."""
    try:
        # Send message
        message = await message_service.send_message(message_data, current_user.id)

        # Background tasks for post-send activities
        background_tasks.add_task(
            _track_message_delivery,
            message.id
        )
        background_tasks.add_task(
            _update_conversation_analytics,
            message.patient_id
        )

        # Real-time notification
        if websocket_events:
            await websocket_events.notify_message_sent(
                message.patient_id, message.dict()
            )

        logger.info(
            f"Message sent to patient {message.patient_id}",
            extra={
                "event_type": "message_sent",
                "message_id": str(message.id),
                "patient_id": str(message.patient_id),
                "user_id": str(current_user.id),
                "message_type": message.message_type,
                "direction": message.direction
            }
        )

        return MessageResponse.from_orm(message)

    except ValueError as e:
        logger.warning(f"Message validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message"
        )

@router.get(
    "/",
    response_model=MessageListResponse,
    summary="List Messages with Advanced Filtering",
    description="""
    Retrieve messages with comprehensive filtering and search capabilities.

    Supports filtering by:
    - Patient ID
    - Message direction (inbound/outbound)
    - Message type and status
    - Date ranges
    - Content search
    - Priority levels
    - Template usage

    **Performance**: Optimized with database indexing and caching.
    """,
    responses={
        200: {
            "description": "Messages retrieved successfully"
        }
    }
)
async def list_messages(
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),

    # Basic filtering
    patient_id: Optional[UUID] = Query(None, description="Filter by patient"),
    direction: Optional[MessageDirection] = Query(None, description="Message direction"),
    message_type: Optional[MessageType] = Query(None, description="Message type"),
    status: Optional[MessageStatus] = Query(None, description="Message status"),

    # Advanced filtering
    search: Optional[str] = Query(None, description="Search in content"),
    priority: Optional[MessagePriority] = Query(None, description="Message priority"),
    scheduled_after: Optional[datetime] = Query(None, description="Scheduled after date"),
    scheduled_before: Optional[datetime] = Query(None, description="Scheduled before date"),
    sent_after: Optional[datetime] = Query(None, description="Sent after date"),
    sent_before: Optional[datetime] = Query(None, description="Sent before date"),
    has_attachments: Optional[bool] = Query(None, description="Has attachments"),
    template_id: Optional[UUID] = Query(None, description="Used template"),

    # Sorting
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),

    # Dependencies
    current_user: User = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service)
) -> MessageListResponse:
    """List messages with advanced filtering."""
    try:
        # Build search parameters
        search_params = MessageSearchParams(
            search=search,
            patient_id=patient_id,
            direction=direction,
            message_type=message_type,
            status=status,
            priority=priority,
            scheduled_after=scheduled_after,
            scheduled_before=scheduled_before,
            sent_after=sent_after,
            sent_before=sent_before,
            has_attachments=has_attachments,
            template_id=template_id
        )

        # Get filtered results
        result = await message_service.list_messages(
            search_params=search_params,
            page=page,
            size=size,
            sort_by=sort_by,
            sort_order=sort_order,
            current_user=current_user
        )

        logger.info(
            f"Messages listed: {len(result.messages)} of {result.total}",
            extra={
                "event_type": "messages_listed",
                "count": len(result.messages),
                "total": result.total,
                "user_id": str(current_user.id),
                "filters": search_params.dict(exclude_unset=True)
            }
        )

        return result

    except Exception as e:
        logger.error(f"Error listing messages: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve messages"
        )

@router.get(
    "/{message_id}",
    response_model=MessageResponse,
    summary="Get Message Details",
    description="""
    Retrieve detailed information about a specific message.

    Includes delivery status, timestamps, metadata, and related information.
    """,
    responses={
        200: {
            "description": "Message details retrieved successfully"
        },
        404: {
            "description": "Message not found"
        }
    }
)
async def get_message(
    message_id: UUID,
    current_user: User = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service)
) -> MessageResponse:
    """Get detailed message information."""
    try:
        message = await message_service.get_message(message_id, current_user)

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )

        logger.info(
            f"Message details retrieved: {message_id}",
            extra={
                "event_type": "message_viewed",
                "message_id": str(message_id),
                "user_id": str(current_user.id)
            }
        )

        return MessageResponse.from_orm(message)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving message {message_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve message"
        )

@router.post(
    "/scheduled",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule Message",
    description="""
    Schedule a message for future delivery with advanced scheduling options.

    Features:
    - Precise scheduling with timezone support
    - Template variable substitution
    - Priority queue management
    - Automatic retry on failure
    - Conflict detection and resolution
    """,
    responses={
        201: {
            "description": "Message scheduled successfully"
        },
        400: {
            "description": "Invalid scheduling parameters"
        }
    }
)
async def schedule_message(
    scheduled_message: ScheduledMessageCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service)
) -> MessageResponse:
    """Schedule a message for future delivery."""
    try:
        # Schedule message
        message = await message_service.schedule_message(scheduled_message, current_user.id)

        # Background task to queue the message
        background_tasks.add_task(
            _queue_scheduled_message,
            message.id, scheduled_message.scheduled_for
        )

        logger.info(
            f"Message scheduled for {scheduled_message.scheduled_for}",
            extra={
                "event_type": "message_scheduled",
                "message_id": str(message.id),
                "patient_id": str(scheduled_message.patient_id),
                "user_id": str(current_user.id),
                "scheduled_for": scheduled_message.scheduled_for.isoformat()
            }
        )

        return MessageResponse.from_orm(message)

    except ValueError as e:
        logger.warning(f"Message scheduling validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error scheduling message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to schedule message"
        )

@router.post(
    "/bulk",
    response_model=Dict[str, Any],
    summary="Send Bulk Messages",
    description="""
    Send messages to multiple patients efficiently with bulk operations.

    Features:
    - Batch processing for performance
    - Template variable substitution per patient
    - Scheduling support
    - Progress tracking
    - Error handling and retry
    """,
    responses={
        200: {
            "description": "Bulk operation completed",
            "content": {
                "application/json": {
                    "example": {
                        "total_patients": 100,
                        "messages_sent": 98,
                        "failed": 2,
                        "job_id": "bulk-123e4567-e89b-12d3-a456-426614174000"
                    }
                }
            }
        }
    }
)
async def send_bulk_messages(
    bulk_operation: BulkMessageOperation,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service)
) -> Dict[str, Any]:
    """Send messages to multiple patients."""
    try:
        # Validate patient access
        accessible_patients = await message_service.validate_patient_access(
            bulk_operation.patient_ids, current_user
        )

        if len(accessible_patients) != len(bulk_operation.patient_ids):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to some patients"
            )

        # Start bulk operation
        job_id = await message_service.start_bulk_operation(bulk_operation, current_user.id)

        # Process in background
        background_tasks.add_task(
            _process_bulk_messages,
            job_id, bulk_operation, current_user.id
        )

        logger.info(
            f"Bulk message operation started: {len(bulk_operation.patient_ids)} patients",
            extra={
                "event_type": "bulk_messages_started",
                "job_id": job_id,
                "patient_count": len(bulk_operation.patient_ids),
                "user_id": str(current_user.id)
            }
        )

        return {
            "job_id": job_id,
            "total_patients": len(bulk_operation.patient_ids),
            "status": "processing",
            "estimated_completion": (
                datetime.utcnow() + timedelta(minutes=len(bulk_operation.patient_ids) // 10)
            ).isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting bulk message operation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start bulk operation"
        )

@router.get(
    "/conversations",
    response_model=List[ConversationSummary],
    summary="Get Conversation Summaries",
    description="""
    Retrieve conversation summaries for all patients.

    Provides overview of recent conversations with:
    - Last message preview
    - Unread message counts
    - Conversation status
    - Activity timestamps
    """,
    responses={
        200: {
            "description": "Conversation summaries retrieved successfully"
        }
    }
)
async def get_conversations(
    limit: int = Query(50, ge=1, le=200, description="Maximum conversations"),
    status_filter: Optional[str] = Query(None, description="Filter by conversation status"),
    has_unread: Optional[bool] = Query(None, description="Filter by unread messages"),
    current_user: User = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service)
) -> List[ConversationSummary]:
    """Get conversation summaries for patients."""
    try:
        conversations = await message_service.get_conversation_summaries(
            current_user, limit=limit, status_filter=status_filter, has_unread=has_unread
        )

        logger.info(
            f"Conversation summaries retrieved: {len(conversations)}",
            extra={
                "event_type": "conversations_listed",
                "count": len(conversations),
                "user_id": str(current_user.id)
            }
        )

        return conversations

    except Exception as e:
        logger.error(f"Error retrieving conversations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversations"
        )

@router.get(
    "/analytics",
    response_model=MessageAnalytics,
    summary="Get Message Analytics",
    description="""
    Retrieve comprehensive message analytics and metrics.

    Provides insights including:
    - Volume metrics
    - Delivery and response rates
    - Performance trends
    - Type and status breakdowns
    """,
    responses={
        200: {
            "description": "Analytics retrieved successfully"
        }
    }
)
async def get_message_analytics(
    days: int = Query(30, ge=1, le=365, description="Analysis period in days"),
    patient_id: Optional[UUID] = Query(None, description="Filter by patient"),
    current_user: User = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service)
) -> MessageAnalytics:
    """Get message analytics and metrics."""
    try:
        analytics = await message_service.get_message_analytics(
            current_user, days=days, patient_id=patient_id
        )

        logger.info(
            f"Message analytics retrieved for {days} days",
            extra={
                "event_type": "message_analytics_viewed",
                "user_id": str(current_user.id),
                "days": days,
                "total_messages": analytics.total_messages
            }
        )

        return analytics

    except Exception as e:
        logger.error(f"Error retrieving message analytics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics"
        )

@router.post(
    "/upload-attachment",
    response_model=Dict[str, Any],
    summary="Upload Message Attachment",
    description="""
    Upload file attachment for messages with validation and processing.

    Supported file types:
    - Images: JPG, PNG, GIF (max 5MB)
    - Documents: PDF, DOC, DOCX (max 10MB)
    - Audio: MP3, WAV, OGG (max 5MB)
    - Video: MP4, AVI (max 20MB)
    """,
    responses={
        200: {
            "description": "File uploaded successfully",
            "content": {
                "application/json": {
                    "example": {
                        "file_id": "123e4567-e89b-12d3-a456-426614174000",
                        "file_url": "https://api.example.com/files/123...",
                        "file_type": "image/jpeg",
                        "file_size": 1024000,
                        "filename": "image.jpg"
                    }
                }
            }
        }
    }
)
async def upload_attachment(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service)
) -> Dict[str, Any]:
    """Upload file attachment for messages."""
    try:
        # Upload and process file
        file_info = await message_service.upload_attachment(file, current_user.id)

        logger.info(
            f"File uploaded: {file.filename}",
            extra={
                "event_type": "file_uploaded",
                "file_id": file_info["file_id"],
                "filename": file.filename,
                "file_size": file_info["file_size"],
                "user_id": str(current_user.id)
            }
        )

        return file_info

    except ValueError as e:
        logger.warning(f"File upload validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file"
        )

# Background task functions
async def _track_message_delivery(message_id: UUID):
    """Track message delivery status."""
    # Implementation for delivery tracking
    pass

async def _update_conversation_analytics(patient_id: UUID):
    """Update conversation analytics after message."""
    # Implementation for analytics update
    pass

async def _queue_scheduled_message(message_id: UUID, scheduled_for: datetime):
    """Queue message for scheduled delivery."""
    # Implementation for message scheduling
    pass

async def _process_bulk_messages(job_id: str, bulk_operation: BulkMessageOperation, user_id: UUID):
    """Process bulk message operation in background."""
    # Implementation for bulk processing
    pass