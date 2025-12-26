"""
WhatsApp webhook handlers for Evolution API integration.

SECURITY: Rate limiting added to prevent webhook flooding (HIGH-001)
SECURITY: Idempotency protection added to prevent duplicate message processing
QW-006: Atomic idempotency using Redis SET NX EX to prevent race conditions
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select
import redis.asyncio as redis

from ..models.message import (
    WebhookPayload,
    MessageStatus,
    WhatsAppMessage,
    WhatsAppContact,
    WhatsAppInstance,
)
from app.database import get_db
from app.utils.rate_limiter import limiter
from app.config import settings
from app.services.webhook.idempotency import AtomicWebhookIdempotency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/whatsapp", tags=["WhatsApp Webhooks"])

# Redis client for idempotency tracking
_redis_client: Optional[redis.Redis] = None
_idempotency_service: Optional[AtomicWebhookIdempotency] = None


async def get_redis() -> redis.Redis:
    """Get or create Redis client for idempotency."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL)
    return _redis_client


async def get_idempotency_service() -> AtomicWebhookIdempotency:
    """Get or create atomic idempotency service."""
    global _idempotency_service
    if _idempotency_service is None:
        redis_client = await get_redis()
        _idempotency_service = AtomicWebhookIdempotency(redis_client)
    return _idempotency_service


async def is_event_processed(event_id: str, event_type: str = "webhook") -> bool:
    """
    Check if webhook event was already processed (atomic idempotency protection).

    QW-006: Uses atomic Redis SET NX EX to prevent race conditions where
    multiple workers could both see 'not processed' and both attempt processing.

    Args:
        event_id: Unique event identifier (e.g., message_id)
        event_type: Type of event for logging and TTL selection

    Returns:
        True if event was already processed, False otherwise
    """
    try:
        idempotency = await get_idempotency_service()

        # Atomic check-and-set using SET NX EX
        acquired, reason = await idempotency.try_acquire(
            event_type=event_type, event_id=event_id
        )

        if not acquired:
            logger.info(
                f"Duplicate webhook event detected and ignored: {event_id}",
                extra={
                    "event_id": event_id,
                    "idempotency": "protected",
                    "reason": reason,
                },
            )
            return True

        # We acquired the lock - this is a new event
        return False

    except Exception as e:
        logger.error(f"Idempotency check failed: {e}", exc_info=True)
        # QW-006: Fallback to legacy method if atomic fails
        return await _legacy_is_event_processed(event_id)


async def _legacy_is_event_processed(event_id: str) -> bool:
    """
    Legacy idempotency check (fallback if atomic fails).

    NOTE: This has a race condition but is better than dropping events.
    """
    try:
        redis_client = await get_redis()
        key = f"webhook:processed:{event_id}"

        # Try atomic SET NX directly
        result = await redis_client.set(key, "1", nx=True, ex=86400)
        if result:
            return False  # New event, we set it
        else:
            return True  # Already exists
    except Exception as e:
        logger.error(f"Legacy idempotency also failed: {e}")
        return False  # Fail-open to not drop events


def _webhook_rate_limit_key(request: Request) -> str:
    """Extract rate limit key from request (IP + instance_name)."""
    instance_name = request.path_params.get("instance_name", "unknown")
    client_host = request.client.host if request.client else "unknown"
    return f"{client_host}:{instance_name}"


@router.post("/evolution/{instance_name}")
# WA-007 FIX: Rate limit per IP + instance_name combination
@limiter.limit("500/minute", key_func=_webhook_rate_limit_key)
async def evolution_webhook(
    instance_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
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
                "event_type": payload.get("event", "unknown"),
                "has_data": bool(payload.get("data")),
            },
        )

        # Validate webhook payload
        webhook_data = WebhookPayload(
            instance=instance_name,
            data=payload.get("data", {}),
            event=payload.get("event", "unknown"),
        )

        # Process webhook synchronously with the request's db session
        await process_webhook_event(webhook_data, background_tasks, db)

        return {"status": "received", "timestamp": datetime.now(timezone.utc)}

    except Exception as e:
        logger.error(
            f"Error processing webhook for instance {instance_name}",
            exc_info=True,
            extra={
                "instance_name": instance_name,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
        )
        raise HTTPException(
            status_code=400, detail=f"Webhook processing error: {str(e)}"
        )


async def process_webhook_event(
    webhook_data: WebhookPayload, background_tasks: BackgroundTasks, db
):
    """Process webhook event."""
    # Normalize event name (Evolution sends UPPERCASE, we use lowercase)
    event = webhook_data.event.lower().replace("_", ".")
    data = webhook_data.data
    instance_name = webhook_data.instance

    try:
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
            "Error in webhook event processing",
            exc_info=True,
            extra={
                "event_type": event,
                "instance_name": instance_name,
                "error_type": type(e).__name__,
            },
        )


async def handle_message_upsert(
    instance_name: str,
    data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session,
):
    """Handle incoming messages with idempotency protection and proper transaction management."""
    try:
        messages = data if isinstance(data, list) else [data]

        for message_data in messages:
            message_info = message_data.get("message", {})
            key = message_data.get("key", {})

            # Skip status messages
            if message_info.get("messageStubType"):
                continue

            # Extract message details
            message_id = key.get("id", "")
            chat_id = key.get("remoteJid", "")
            sender_id = key.get("participant") or key.get("remoteJid", "")

            # IDEMPOTENCY: Check if this message was already processed (QW-006: Atomic)
            if await is_event_processed(message_id, event_type="message"):
                logger.debug(f"Skipping duplicate message: {message_id}")
                continue

            # Determine message type and content
            message_type = "text"
            content = ""
            media_url = None
            media_caption = None

            if "conversation" in message_info:
                content = message_info["conversation"]
            elif "extendedTextMessage" in message_info:
                content = message_info["extendedTextMessage"].get("text", "")
            elif "imageMessage" in message_info:
                message_type = "image"
                media_caption = message_info["imageMessage"].get("caption", "")
                media_url = message_info["imageMessage"].get("url", "")
            elif "documentMessage" in message_info:
                message_type = "document"
                media_caption = message_info["documentMessage"].get("caption", "")
                media_url = message_info["documentMessage"].get("url", "")
            elif "audioMessage" in message_info:
                message_type = "audio"
                media_url = message_info["audioMessage"].get("url", "")
            elif "videoMessage" in message_info:
                message_type = "video"
                media_caption = message_info["videoMessage"].get("caption", "")
                media_url = message_info["videoMessage"].get("url", "")

            # Database transaction with proper error handling
            try:
                # Check if message already exists
                stmt = select(WhatsAppMessage).where(
                    WhatsAppMessage.external_id == message_id
                )
                result = db.execute(stmt)
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
                        # FIX P1-006: Use timezone-aware datetime
                        created_at=datetime.fromtimestamp(
                            message_data.get("messageTimestamp", 0), tz=timezone.utc
                        ),
                        delivered_at=datetime.now(timezone.utc),
                        message_data={"incoming": True, "message_data": message_data},
                    )

                    db.add(message)
                    # FIX P1-005: Use flush() first to get message ID, schedule background
                    # task, then commit. This ensures both message storage and flow trigger
                    # are part of the same logical transaction.
                    db.flush()

                    logger.info(f"Stored incoming message {message_id} from {sender_id}")

                    # ---------------------------------------------------------
                    # REACTIVE FLOW TRIGGER (Refactored)
                    # ---------------------------------------------------------
                    flow_scheduled = False
                    try:
                        # Clean phone number (remove suffix)
                        phone_number = (
                            sender_id.split("@")[0] if "@" in sender_id else sender_id
                        )

                        # Find patient by phone (LGPD: use phone_hash lookup)
                        from app.models.patient import Patient
                        from app.services.encryption import get_lgpd_encryption_service

                        lgpd_service = get_lgpd_encryption_service()
                        phone_hash = lgpd_service.hash_phone(phone_number)
                        stmt = select(Patient).where(Patient.phone_hash == phone_hash)
                        result = db.execute(stmt)
                        patient = result.scalar_one_or_none()

                        if patient:
                            logger.info(
                                f"Message from patient {patient.id} detected. Triggering flow engine in background."
                            )

                            # Add to background tasks to avoid blocking the webhook response
                            # and to manage the sync/async impedance mismatch separately
                            background_tasks.add_task(
                                _trigger_flow_response_async, patient.id, content
                            )
                            flow_scheduled = True
                        else:
                            logger.debug(f"No patient found for phone {phone_number}")

                    except Exception as flow_error:
                        logger.error(f"Error triggering flow engine: {flow_error}")
                    # ---------------------------------------------------------

                    # FIX P1-005: Commit AFTER background task is scheduled to ensure
                    # atomicity - if scheduling fails, we can rollback the message too
                    db.commit()

                    if flow_scheduled:
                        logger.debug(f"Transaction committed with flow task scheduled for message {message_id}")

            except Exception as db_error:
                # Rollback transaction on error
                db.rollback()
                logger.error(
                    f"Database error processing message {message_id}: {db_error}",
                    exc_info=True,
                )
                raise

    except Exception as e:
        logger.error(f"Error handling message upsert: {e}", exc_info=True)


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
                loop.run_until_complete(
                    engine.process_patient_response(patient_id, content)
                )

            loop.close()
            logger.info(
                f"Completed background flow processing for patient {patient_id}"
            )

        except Exception as e:
            logger.error(
                f"Error in background flow thread for patient {patient_id}: {e}",
                exc_info=True,
            )
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


async def handle_message_update(
    instance_name: str, data: Dict[str, Any], db: Session
):
    """Handle message status updates with idempotency protection and transaction management."""
    try:
        updates = data if isinstance(data, list) else [data]

        for update_data in updates:
            key = update_data.get("key", {})
            update_info = update_data.get("update", {})

            message_id = key.get("id", "")
            status_update = update_info.get("status")

            if not message_id or not status_update:
                continue

            # IDEMPOTENCY: Check if this status update was already processed (QW-006: Atomic)
            event_id = f"{message_id}:{status_update}"
            if await is_event_processed(event_id, event_type="status"):
                logger.debug(f"Skipping duplicate status update: {event_id}")
                continue

            # Map Evolution API status to our status
            status_map = {
                1: MessageStatus.SENT,
                2: MessageStatus.DELIVERED,
                3: MessageStatus.READ,
            }

            new_status = status_map.get(status_update, MessageStatus.SENT)

            # Database transaction with proper error handling
            try:
                # Update message status
                stmt = select(WhatsAppMessage).where(
                    WhatsAppMessage.external_id == message_id
                )
                result = db.execute(stmt)
                message = result.scalar_one_or_none()

                if message:
                    message.status = new_status
                    message.updated_at = datetime.now(timezone.utc)

                    if new_status == MessageStatus.DELIVERED:
                        message.delivered_at = datetime.now(timezone.utc)
                    elif new_status == MessageStatus.READ:
                        message.read_at = datetime.now(timezone.utc)

                    db.commit()
                    logger.info(f"Updated message {message_id} status to {new_status}")

            except Exception as db_error:
                # Rollback transaction on error
                db.rollback()
                logger.error(
                    f"Database error updating message {message_id}: {db_error}",
                    exc_info=True,
                )
                raise

    except Exception as e:
        logger.error(f"Error handling message update: {e}", exc_info=True)


async def handle_send_message(
    instance_name: str, data: Dict[str, Any], db: Session
):
    """Handle outgoing message confirmation."""
    try:
        key = data.get("key", {})
        message_id = key.get("id", "")

        if message_id:
            # Update message with external ID
            stmt = select(WhatsAppMessage).where(
                WhatsAppMessage.instance_name == instance_name,
                WhatsAppMessage.external_id.is_(None),
                WhatsAppMessage.status == MessageStatus.PENDING,
            )
            result = db.execute(stmt)
            message = result.first()

            if message:
                message[0].external_id = message_id
                message[0].status = MessageStatus.SENT
                message[0].sent_at = datetime.now(timezone.utc)
                db.commit()

                logger.info(f"Updated outgoing message with external ID {message_id}")

    except Exception as e:
        logger.error(f"Error handling send message: {e}")


async def handle_contact_upsert(
    instance_name: str, data: Dict[str, Any], db: Session
):
    """Handle contact updates."""
    try:
        contacts = data if isinstance(data, list) else [data]

        for contact_data in contacts:
            contact_id = contact_data.get("id", "")
            phone_number = contact_id.split("@")[0] if "@" in contact_id else contact_id

            # Check if contact exists
            stmt = select(WhatsAppContact).where(
                WhatsAppContact.instance_name == instance_name,
                WhatsAppContact.phone_number == phone_number,
            )
            result = db.execute(stmt)
            existing_contact = result.scalar_one_or_none()

            if existing_contact:
                # Update existing contact
                existing_contact.name = contact_data.get(
                    "pushName"
                ) or contact_data.get("name")
                existing_contact.profile_picture_url = contact_data.get(
                    "profilePictureUrl"
                )
                existing_contact.updated_at = datetime.now(timezone.utc)
            else:
                # Create new contact
                contact = WhatsAppContact(
                    id=f"contact_{contact_id}",
                    instance_name=instance_name,
                    phone_number=phone_number,
                    formatted_number=contact_id,
                    name=contact_data.get("pushName") or contact_data.get("name"),
                    profile_picture_url=contact_data.get("profilePictureUrl"),
                )
                db.add(contact)

            db.commit()

    except Exception as e:
        logger.error(f"Error handling contact upsert: {e}")


async def handle_connection_update(
    instance_name: str, data: Dict[str, Any], db: Session
):
    """Handle instance connection updates with proper transaction management."""
    try:
        state = data.get("state", "")

        # Database transaction with proper error handling
        try:
            # Update instance status
            stmt = select(WhatsAppInstance).where(WhatsAppInstance.name == instance_name)
            result = db.execute(stmt)
            instance = result.scalar_one_or_none()

            if instance:
                instance.status = state
                instance.is_connected = state == "open"
                instance.last_activity = datetime.now(timezone.utc)
                instance.updated_at = datetime.now(timezone.utc)

                # Update phone number and profile if available
                if "number" in data:
                    instance.phone_number = data["number"]
                if "profileName" in data:
                    instance.profile_name = data["profileName"]

                db.commit()
                logger.info(
                    f"Updated instance {instance_name} connection status to {state}"
                )

        except Exception as db_error:
            # Rollback transaction on error
            db.rollback()
            logger.error(
                f"Database error updating connection for {instance_name}: {db_error}",
                exc_info=True,
            )
            raise

    except Exception as e:
        logger.error(f"Error handling connection update: {e}", exc_info=True)


async def handle_presence_update(
    instance_name: str, data: Dict[str, Any], db: Session
):
    """Handle presence updates (online/offline status)."""
    try:
        contact_id = data.get("id", "")
        presence = data.get("presences", {})

        if contact_id and presence:
            phone_number = contact_id.split("@")[0] if "@" in contact_id else contact_id

            # Update contact last seen
            stmt = select(WhatsAppContact).where(
                WhatsAppContact.instance_name == instance_name,
                WhatsAppContact.phone_number == phone_number,
            )
            result = db.execute(stmt)
            contact = result.scalar_one_or_none()

            if contact:
                last_seen_timestamp = presence.get("lastSeen")
                if last_seen_timestamp:
                    # FIX P1-006: Use timezone-aware datetime
                    contact.last_seen = datetime.fromtimestamp(last_seen_timestamp, tz=timezone.utc)
                    contact.updated_at = datetime.now(timezone.utc)
                    db.commit()

    except Exception as e:
        logger.error(f"Error handling presence update: {e}")


async def handle_chat_upsert(
    instance_name: str, data: Dict[str, Any], db: Session
):
    """Handle chat updates."""
    try:
        chats = data if isinstance(data, list) else [data]

        for chat_data in chats:
            chat_id = chat_data.get("id", "")

            # For individual chats, update contact information
            if "@s.whatsapp.net" in chat_id:
                phone_number = chat_id.split("@")[0]

                stmt = select(WhatsAppContact).where(
                    WhatsAppContact.instance_name == instance_name,
                    WhatsAppContact.phone_number == phone_number,
                )
                result = db.execute(stmt)
                contact = result.scalar_one_or_none()

                if contact:
                    # Update contact with chat information
                    if "name" in chat_data:
                        contact.name = chat_data["name"]
                    contact.updated_at = datetime.now(timezone.utc)
                    db.commit()

    except Exception as e:
        logger.error(f"Error handling chat upsert: {e}")


# Health check endpoint for webhooks
@router.get("/health")
async def webhook_health():
    """Health check for webhook endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc),
        "service": "whatsapp-webhooks",
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
            "timestamp": datetime.now(timezone.utc),
        }
    except Exception as e:
        # FIX P2-001: Chain exception to preserve original traceback
        raise HTTPException(
            status_code=400, detail=f"Invalid webhook payload: {str(e)}"
        ) from e
