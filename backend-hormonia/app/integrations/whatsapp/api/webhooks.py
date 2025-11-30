"""
WhatsApp webhook handlers for Evolution API integration.

SECURITY: Rate limiting added to prevent webhook flooding (HIGH-001)
SECURITY: Idempotency protection added to prevent duplicate message processing
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as redis

from ..models.message import (
    WebhookPayload, MessageStatus, WhatsAppMessage, WhatsAppContact,
    WhatsAppInstance
)
from ..services.message_service import WhatsAppMessageService
from app.database import get_db
from app.utils.rate_limiter import limiter
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/whatsapp", tags=["WhatsApp Webhooks"])

# Redis client for idempotency tracking
_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """Get or create Redis client for idempotency."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL)
    return _redis_client


async def is_event_processed(event_id: str) -> bool:
    """
    Check if webhook event was already processed (idempotency protection).

    Args:
        event_id: Unique event identifier (e.g., message_id)

    Returns:
        True if event was already processed, False otherwise
    """
    redis_client = await get_redis()
    key = f"webhook:processed:{event_id}"

    # Check if key exists
    exists = await redis_client.exists(key)
    if exists:
        logger.info(
            f"Duplicate webhook event detected and ignored: {event_id}",
            extra={"event_id": event_id, "idempotency": "protected"}
        )
        return True

    # Mark as processed with 24h TTL (prevents indefinite growth)
    await redis_client.setex(key, 86400, "1")
    return False


@router.post("/evolution/{instance_name}")
# WA-007 FIX: Rate limit per IP + instance_name combination
@limiter.limit(
    "500/minute",
    key_func=lambda: f"{request.client.host}:{request.path_params.get('instance_name', 'unknown')}"
)
async def evolution_webhook(
    instance_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Evolution API webhooks for WhatsApp events.

    Rate limited: 500 requests per minute per IP+instance to prevent DDoS/spam attacks.
    WA-007: Rate limit applied per IP AND instance_name combination
    """
    try:
        # Get raw payload
        payload = await request.json()

        # Log incoming webhook with structured data
        logger.info(
            f"Received webhook for instance {instance_name}",
            extra={
                "instance_name": instance_name,
                "event_type": payload.get('event', 'unknown'),
                "has_data": bool(payload.get('data')),
            }
        )

        # Validate webhook payload
        webhook_data = WebhookPayload(
            instance=instance_name,
            data=payload.get('data', {}),
            event=payload.get('event', 'unknown')
        )

        # Process webhook in background
        background_tasks.add_task(
            process_webhook_event,
            webhook_data,
            background_tasks, # Pass background_tasks down
            db
        )

        return {"status": "received", "timestamp": datetime.utcnow()}

    except Exception as e:
        logger.error(
            f"Error processing webhook for instance {instance_name}",
            exc_info=True,
            extra={
                "instance_name": instance_name,
                "error_type": type(e).__name__,
                "error_message": str(e),
            }
        )
        raise HTTPException(status_code=400, detail=f"Webhook processing error: {str(e)}")


async def process_webhook_event(webhook_data: WebhookPayload, background_tasks: BackgroundTasks, db: AsyncSession):
    """Process webhook event in background."""
    try:
        event = webhook_data.event
        data = webhook_data.data
        instance_name = webhook_data.instance

        # Route to appropriate handler based on event type
        if event == "messages.upsert":
            await handle_message_upsert(instance_name, data, background_tasks, db)
        elif event == "messages.update":
            await handle_message_update(instance_name, data, db)
        elif event == "send.message":
            await handle_send_message(instance_name, data, db)
        elif event == "contacts.upsert":
            await handle_contact_upsert(instance_name, data, db)
        elif event == "connection.update":
            await handle_connection_update(instance_name, data, db)
        elif event == "presence.update":
            await handle_presence_update(instance_name, data, db)
        elif event == "chats.upsert":
            await handle_chat_upsert(instance_name, data, db)
        else:
            logger.info(f"Unhandled webhook event: {event}")

    except Exception as e:
        logger.error(
            f"Error in webhook event processing",
            exc_info=True,
            extra={
                "event_type": event,
                "instance_name": instance_name,
                "error_type": type(e).__name__,
            }
        )


async def handle_message_upsert(instance_name: str, data: Dict[str, Any], background_tasks: BackgroundTasks, db: AsyncSession):
    """Handle incoming messages with idempotency protection."""
    try:
        messages = data if isinstance(data, list) else [data]

        for message_data in messages:
            message_info = message_data.get('message', {})
            key = message_data.get('key', {})

            # Skip status messages
            if message_info.get('messageStubType'):
                continue

            # Extract message details
            message_id = key.get('id', '')
            chat_id = key.get('remoteJid', '')
            sender_id = key.get('participant') or key.get('remoteJid', '')

            # IDEMPOTENCY: Check if this message was already processed
            if await is_event_processed(f"message:{message_id}"):
                logger.debug(f"Skipping duplicate message: {message_id}")
                continue

            # Determine message type and content
            message_type = "text"
            content = ""
            media_url = None
            media_caption = None

            if 'conversation' in message_info:
                content = message_info['conversation']
            elif 'extendedTextMessage' in message_info:
                content = message_info['extendedTextMessage'].get('text', '')
            elif 'imageMessage' in message_info:
                message_type = "image"
                media_caption = message_info['imageMessage'].get('caption', '')
                media_url = message_info['imageMessage'].get('url', '')
            elif 'documentMessage' in message_info:
                message_type = "document"
                media_caption = message_info['documentMessage'].get('caption', '')
                media_url = message_info['documentMessage'].get('url', '')
            elif 'audioMessage' in message_info:
                message_type = "audio"
                media_url = message_info['audioMessage'].get('url', '')
            elif 'videoMessage' in message_info:
                message_type = "video"
                media_caption = message_info['videoMessage'].get('caption', '')
                media_url = message_info['videoMessage'].get('url', '')

            # Check if message already exists
            stmt = select(WhatsAppMessage).where(WhatsAppMessage.external_id == message_id)
            result = await db.execute(stmt)
            existing_message = result.scalar_one_or_none()

            if not existing_message:
                # Create new message record
                message = WhatsAppMessage(
                    id=f"incoming_{message_id}",
                    instance_name=instance_name,
                    chat_id=chat_id,
                    sender_id=sender_id,
                    recipient_id="self",  # This is an incoming message
                    message_type=message_type,
                    content=content,
                    media_url=media_url,
                    media_caption=media_caption,
                    status=MessageStatus.DELIVERED,
                    external_id=message_id,
                    created_at=datetime.fromtimestamp(message_data.get('messageTimestamp', 0)),
                    delivered_at=datetime.utcnow(),
                    message_data={
                        "incoming": True,
                        "message_data": message_data
                    }
                )

                db.add(message)
                await db.commit()

                logger.info(f"Stored incoming message {message_id} from {sender_id}")

                # ---------------------------------------------------------
                # REACTIVE FLOW TRIGGER (Refactored)
                # ---------------------------------------------------------
                try:
                    # Clean phone number (remove suffix)
                    phone_number = sender_id.split('@')[0] if '@' in sender_id else sender_id

                    # Find patient by phone
                    from app.models.patient import Patient
                    stmt = select(Patient).where(Patient.phone == phone_number)
                    result = await db.execute(stmt)
                    patient = result.scalar_one_or_none()

                    if patient:
                        logger.info(f"Message from patient {patient.id} detected. Triggering flow engine in background.")
                        
                        # Add to background tasks to avoid blocking the webhook response
                        # and to manage the sync/async impedance mismatch separately
                        background_tasks.add_task(
                            _trigger_flow_response_async, 
                            patient.id, 
                            content
                        )
                    else:
                        logger.debug(f"No patient found for phone {phone_number}")

                except Exception as flow_error:
                    logger.error(f"Error triggering flow engine: {flow_error}")
                # ---------------------------------------------------------


    except Exception as e:
        logger.error(f"Error handling message upsert: {e}")


async def _trigger_flow_response_async(patient_id: str, content: str):
    """
    Async helper to trigger the flow engine.
    Offloads the sync/async hybrid execution to a separate thread to avoid blocking the main loop.
    """
    import asyncio
    from app.database import get_scoped_session
    from app.services.enhanced_flow_engine import get_enhanced_flow_engine
    
    logger.info(f"Starting background flow processing for patient {patient_id}")

    def _run_hybrid_flow():
        try:
            # Create a new event loop for this thread to handle async calls within the engine
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            with get_scoped_session() as sync_db:
                # Initialize engine with sync session
                engine = get_enhanced_flow_engine(sync_db)
                
                # Run the async method in the thread's loop
                # This allows sync DB calls to block the thread (fine) 
                # while async AI calls are awaited properly
                loop.run_until_complete(engine.process_patient_response(patient_id, content))
                
            loop.close()
            logger.info(f"Completed background flow processing for patient {patient_id}")
            
        except Exception as e:
            logger.error(f"Error in background flow thread for patient {patient_id}: {e}", exc_info=True)
            try:
                loop.close()
            except Exception as close_err:
                logger.debug(f"Event loop close error (non-critical): {close_err}")

    # Run in executor to avoid blocking the main event loop with sync DB calls
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _run_hybrid_flow)
    except Exception as e:
        logger.error(f"Failed to schedule background flow task: {e}", exc_info=True)


async def handle_message_update(instance_name: str, data: Dict[str, Any], db: AsyncSession):
    """Handle message status updates with idempotency protection."""
    try:
        updates = data if isinstance(data, list) else [data]

        for update_data in updates:
            key = update_data.get('key', {})
            update_info = update_data.get('update', {})

            message_id = key.get('id', '')
            status_update = update_info.get('status')

            if not message_id or not status_update:
                continue

            # IDEMPOTENCY: Check if this status update was already processed
            event_id = f"status:{message_id}:{status_update}"
            if await is_event_processed(event_id):
                logger.debug(f"Skipping duplicate status update: {event_id}")
                continue

            # Map Evolution API status to our status
            status_map = {
                1: MessageStatus.SENT,
                2: MessageStatus.DELIVERED,
                3: MessageStatus.READ
            }

            new_status = status_map.get(status_update, MessageStatus.SENT)

            # Update message status
            stmt = select(WhatsAppMessage).where(WhatsAppMessage.external_id == message_id)
            result = await db.execute(stmt)
            message = result.scalar_one_or_none()

            if message:
                message.status = new_status
                message.updated_at = datetime.utcnow()

                if new_status == MessageStatus.DELIVERED:
                    message.delivered_at = datetime.utcnow()
                elif new_status == MessageStatus.READ:
                    message.read_at = datetime.utcnow()

                await db.commit()
                logger.info(f"Updated message {message_id} status to {new_status}")

    except Exception as e:
        logger.error(f"Error handling message update: {e}")


async def handle_send_message(instance_name: str, data: Dict[str, Any], db: AsyncSession):
    """Handle outgoing message confirmation."""
    try:
        key = data.get('key', {})
        message_id = key.get('id', '')

        if message_id:
            # Update message with external ID
            stmt = select(WhatsAppMessage).where(
                WhatsAppMessage.instance_name == instance_name,
                WhatsAppMessage.external_id.is_(None),
                WhatsAppMessage.status == MessageStatus.PENDING
            )
            result = await db.execute(stmt)
            message = result.first()

            if message:
                message[0].external_id = message_id
                message[0].status = MessageStatus.SENT
                message[0].sent_at = datetime.utcnow()
                await db.commit()

                logger.info(f"Updated outgoing message with external ID {message_id}")

    except Exception as e:
        logger.error(f"Error handling send message: {e}")


async def handle_contact_upsert(instance_name: str, data: Dict[str, Any], db: AsyncSession):
    """Handle contact updates."""
    try:
        contacts = data if isinstance(data, list) else [data]

        for contact_data in contacts:
            contact_id = contact_data.get('id', '')
            phone_number = contact_id.split('@')[0] if '@' in contact_id else contact_id

            # Check if contact exists
            stmt = select(WhatsAppContact).where(
                WhatsAppContact.instance_name == instance_name,
                WhatsAppContact.phone_number == phone_number
            )
            result = await db.execute(stmt)
            existing_contact = result.scalar_one_or_none()

            if existing_contact:
                # Update existing contact
                existing_contact.name = contact_data.get('pushName') or contact_data.get('name')
                existing_contact.profile_picture_url = contact_data.get('profilePictureUrl')
                existing_contact.updated_at = datetime.utcnow()
            else:
                # Create new contact
                contact = WhatsAppContact(
                    id=f"contact_{contact_id}",
                    instance_name=instance_name,
                    phone_number=phone_number,
                    formatted_number=contact_id,
                    name=contact_data.get('pushName') or contact_data.get('name'),
                    profile_picture_url=contact_data.get('profilePictureUrl')
                )
                db.add(contact)

            await db.commit()

    except Exception as e:
        logger.error(f"Error handling contact upsert: {e}")


async def handle_connection_update(instance_name: str, data: Dict[str, Any], db: AsyncSession):
    """Handle instance connection updates."""
    try:
        state = data.get('state', '')

        # Update instance status
        stmt = select(WhatsAppInstance).where(WhatsAppInstance.name == instance_name)
        result = await db.execute(stmt)
        instance = result.scalar_one_or_none()

        if instance:
            instance.status = state
            instance.is_connected = state == 'open'
            instance.last_activity = datetime.utcnow()
            instance.updated_at = datetime.utcnow()

            # Update phone number and profile if available
            if 'number' in data:
                instance.phone_number = data['number']
            if 'profileName' in data:
                instance.profile_name = data['profileName']

            await db.commit()
            logger.info(f"Updated instance {instance_name} connection status to {state}")

    except Exception as e:
        logger.error(f"Error handling connection update: {e}")


async def handle_presence_update(instance_name: str, data: Dict[str, Any], db: AsyncSession):
    """Handle presence updates (online/offline status)."""
    try:
        contact_id = data.get('id', '')
        presence = data.get('presences', {})

        if contact_id and presence:
            phone_number = contact_id.split('@')[0] if '@' in contact_id else contact_id

            # Update contact last seen
            stmt = select(WhatsAppContact).where(
                WhatsAppContact.instance_name == instance_name,
                WhatsAppContact.phone_number == phone_number
            )
            result = await db.execute(stmt)
            contact = result.scalar_one_or_none()

            if contact:
                last_seen_timestamp = presence.get('lastSeen')
                if last_seen_timestamp:
                    contact.last_seen = datetime.fromtimestamp(last_seen_timestamp)
                    contact.updated_at = datetime.utcnow()
                    await db.commit()

    except Exception as e:
        logger.error(f"Error handling presence update: {e}")


async def handle_chat_upsert(instance_name: str, data: Dict[str, Any], db: AsyncSession):
    """Handle chat updates."""
    try:
        chats = data if isinstance(data, list) else [data]

        for chat_data in chats:
            chat_id = chat_data.get('id', '')

            # For individual chats, update contact information
            if '@s.whatsapp.net' in chat_id:
                phone_number = chat_id.split('@')[0]

                stmt = select(WhatsAppContact).where(
                    WhatsAppContact.instance_name == instance_name,
                    WhatsAppContact.phone_number == phone_number
                )
                result = await db.execute(stmt)
                contact = result.scalar_one_or_none()

                if contact:
                    # Update contact with chat information
                    if 'name' in chat_data:
                        contact.name = chat_data['name']
                    contact.updated_at = datetime.utcnow()
                    await db.commit()

    except Exception as e:
        logger.error(f"Error handling chat upsert: {e}")


# Health check endpoint for webhooks
@router.get("/health")
async def webhook_health():
    """Health check for webhook endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "service": "whatsapp-webhooks"
    }


# Webhook validation endpoint
@router.post("/validate")
async def validate_webhook(request: Request):
    """Validate webhook configuration."""
    try:
        payload = await request.json()
        return {
            "status": "valid",
            "received_data": payload,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid webhook payload: {str(e)}")