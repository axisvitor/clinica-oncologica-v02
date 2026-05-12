"""
WhatsApp API routes for message management and instance control.
"""

import logging
from datetime import datetime
from typing import Optional, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.message import (
    MessageRequest,
    MessageResponse,
    WhatsAppContact,
    WhatsAppInstance,
)
from ..services.message_service import WhatsAppMessageService, MessageQueue
from app.integrations.wuzapi import get_wuzapi_client
from app.database import get_async_db
from app.config import settings
from app.dependencies.auth_dependencies import get_current_active_admin
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

# This router is mounted under /api/v2 in the main v2 router.
router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])
management_router = APIRouter(dependencies=[Depends(get_current_active_admin)])


def _serialize_message_entry(msg, *, include_error_message: bool) -> dict:
    payload = {
        "id": msg.id,
        "external_id": msg.external_id,
        "message_type": msg.message_type,
        "content": msg.content,
        "media_url": msg.media_url,
        "media_caption": msg.media_caption,
        "status": msg.status,
        "sender_id": msg.sender_id,
        "recipient_id": msg.recipient_id,
        "created_at": msg.created_at,
        "sent_at": msg.sent_at,
        "delivered_at": msg.delivered_at,
        "read_at": msg.read_at,
        "retry_count": msg.retry_count,
        "message_data": msg.message_data,
    }
    if include_error_message:
        payload["error_message"] = msg.error_message
    return payload


def _build_messages_response(
    *,
    messages: list,
    limit: int,
    offset: int,
    include_error_message: bool,
) -> dict:
    return {
        "messages": [
            _serialize_message_entry(msg, include_error_message=include_error_message)
            for msg in messages
        ],
        "total": len(messages),
        "limit": limit,
        "offset": offset,
    }


async def get_wuzapi_for_queue():
    """Get WuzAPI client for queue message service (outbound messages only)."""
    token = getattr(settings, "WHATSAPP_WUZAPI_TOKEN", None)
    base_url = getattr(settings, "WHATSAPP_WUZAPI_BASE_URL", "")
    if not token:
        raise HTTPException(
            status_code=501,
            detail="WuzAPI not configured: WHATSAPP_WUZAPI_TOKEN missing",
        )

    client = get_wuzapi_client(base_url=base_url, token=token)
    await client.connect()
    try:
        yield client
    finally:
        try:
            await client.disconnect()
        except Exception as e:
            logger.warning("Failed to disconnect WuzAPI client: %s", e)


async def get_message_service(
    db: AsyncSession = Depends(get_async_db),
    wuzapi_client=Depends(get_wuzapi_for_queue),
) -> AsyncGenerator[WhatsAppMessageService, None]:
    """Get WhatsApp message service instance with queue resource cleanup."""
    message_queue = MessageQueue(redis_url=settings.REDIS_URL)
    service = WhatsAppMessageService(wuzapi_client, db, message_queue)
    try:
        yield service
    finally:
        try:
            await message_queue.disconnect()
        except Exception as e:
            logger.warning("Failed to disconnect message queue client: %s", e)


# Message Management Endpoints
@management_router.post("/messages", response_model=MessageResponse)
async def send_message(
    request: MessageRequest,
    message_service: WhatsAppMessageService = Depends(get_message_service),
):
    """Send WhatsApp message."""
    try:
        return await message_service.send_message(request)
    except ValueError as e:
        logger.warning(f"Invalid message request: {e}")
        raise HTTPException(status_code=400, detail="Invalid message parameters")
    except Exception as e:
        logger.error(f"Error sending message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send message")


@management_router.get("/messages")
async def list_messages(
    instance: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    message_service: WhatsAppMessageService = Depends(get_message_service),
):
    """List recent messages for an instance (Frontend compatibility)."""
    try:
        messages = await message_service.get_instance_messages(
            instance, limit, offset
        )
        return _build_messages_response(
            messages=messages,
            limit=limit,
            offset=offset,
            include_error_message=True,
        )
    except Exception as e:
        logger.error(f"Error listing messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list messages")

@management_router.get("/messages/stats")
async def get_message_stats_alias(
    instance: str,
    message_service: WhatsAppMessageService = Depends(get_message_service),
):
    """Get message statistics (Frontend compatibility alias)."""
    return await get_message_statistics(instance, message_service=message_service)


@management_router.get("/messages/{instance_name}/statistics")
async def get_message_statistics(
    instance_name: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    message_service: WhatsAppMessageService = Depends(get_message_service),
):
    """Get message statistics for an instance."""
    try:
        stats = await message_service.get_message_statistics(
            instance_name, start_date, end_date
        )
        return {
            "instance_name": instance_name,
            "period": {"start_date": start_date, "end_date": end_date},
            "statistics": stats,
            "generated_at": now_sao_paulo(),
        }
    except Exception as e:
        logger.error(f"Error getting message statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get message statistics")


@management_router.get("/messages/{instance_name}/history/{chat_id}")
@management_router.get("/messages/{instance_name}/{chat_id}", include_in_schema=False)
async def get_message_history(
    instance_name: str,
    chat_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    message_service: WhatsAppMessageService = Depends(get_message_service),
):
    """Get message history for a chat."""
    try:
        messages = await message_service.get_message_history(
            instance_name, chat_id, limit, offset
        )
        return _build_messages_response(
            messages=messages,
            limit=limit,
            offset=offset,
            include_error_message=False,
        )
    except Exception as e:
        logger.error(f"Error getting message history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get message history")


# Contact Management Endpoints
@management_router.post("/contacts/{instance_name}/sync")
async def sync_contacts(instance_name: str):
    """Contacts sync is not supported by WuzAPI.

    WuzAPI (whatsmeow-based) does not expose a contacts API equivalent to
    Evolution API. This endpoint is retained for API compatibility and returns
    HTTP 501 to avoid silent failures from the previous stub implementation.
    """
    raise HTTPException(
        status_code=501,
        detail=(
            "Contacts sync is not supported by WuzAPI. "
            "This operation has no equivalent in the current WhatsApp provider."
        ),
    )


@management_router.get("/contacts/{instance_name}")
async def get_contacts(
    instance_name: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
):
    """Get contacts for an instance."""
    try:
        stmt = select(WhatsAppContact).where(
            WhatsAppContact.instance_name == instance_name
        )

        if search:
            search_term = f"%{search}%"
            stmt = stmt.where(
                (WhatsAppContact.name.ilike(search_term))
                | (WhatsAppContact.phone_number.ilike(search_term))
            )

        stmt = stmt.order_by(WhatsAppContact.name.asc()).limit(limit).offset(offset)

        result = await db.execute(stmt)
        contacts = result.scalars().all()

        return {
            "contacts": [
                {
                    "id": contact.id,
                    "phone_number": contact.phone_number,
                    "formatted_number": contact.formatted_number,
                    "name": contact.name,
                    "profile_picture_url": contact.profile_picture_url,
                    "is_whatsapp_user": contact.is_whatsapp_user,
                    "last_seen": contact.last_seen,
                    "created_at": contact.created_at,
                    "updated_at": contact.updated_at,
                }
                for contact in contacts
            ],
            "total": len(contacts),
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"Error getting contacts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get contacts")


# Queue Management Endpoints
@management_router.get("/queue/stats")
async def get_queue_stats():
    """Get message queue statistics."""
    message_queue = MessageQueue(redis_url=settings.REDIS_URL)
    try:
        stats = await message_queue.get_queue_stats()
        return {"queue_statistics": stats, "timestamp": now_sao_paulo()}
    except Exception as e:
        logger.error(f"Error getting queue stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get queue statistics")
    finally:
        try:
            await message_queue.disconnect()
        except Exception as disconnect_error:
            logger.warning("Failed to disconnect queue client: %s", disconnect_error)


@management_router.post("/queue/process")
async def process_queue_batch(
    max_messages: int = Query(100, ge=1, le=1000),
    message_service: WhatsAppMessageService = Depends(get_message_service),
):
    """Process a bounded queue batch to avoid unmanaged background workers."""
    try:
        result = await message_service.process_queue_batch(max_messages=max_messages)
        return {
            "status": "queue_batch_processed",
            "timestamp": now_sao_paulo(),
            **result,
        }
    except Exception as e:
        logger.error(f"Error processing queue batch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process queue batch")


# Health and Status Endpoints
@router.get("/health")
async def health_check():
    """Health check for WhatsApp service."""
    return {
        "status": "healthy",
        "service": "whatsapp-integration",
        "timestamp": now_sao_paulo(),
        "version": "1.0.0",
    }


@management_router.get("/instances")
async def list_instances(db: AsyncSession = Depends(get_async_db)):
    """List all WhatsApp instances."""
    try:
        stmt = select(WhatsAppInstance).order_by(WhatsAppInstance.created_at.desc())
        result = await db.execute(stmt)
        instances = result.scalars().all()

        return {
            "instances": [
                {
                    "id": instance.id,
                    "name": instance.name,
                    "status": instance.status,
                    "is_connected": instance.is_connected,
                    "phone_number": instance.phone_number,
                    "profile_name": instance.profile_name,
                    "created_at": instance.created_at,
                    "last_activity": instance.last_activity,
                }
                for instance in instances
            ],
            "total": len(instances),
            "timestamp": now_sao_paulo(),
        }
    except Exception as e:
        logger.error(f"Error listing instances: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list instances")


router.include_router(management_router)
