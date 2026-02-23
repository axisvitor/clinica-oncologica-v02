"""
WhatsApp webhook handlers for Evolution API integration.

SECURITY: Rate limiting added to prevent webhook flooding (HIGH-001)
SECURITY: Idempotency protection added to prevent duplicate message processing
QW-006: Atomic idempotency using Redis SET NX EX to prevent race conditions
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as redis

from ..models.message import (
    WebhookPayload,
    MessageStatus,
    WhatsAppMessage,
    WhatsAppContact,
    WhatsAppInstance,
)
from app.models.message_events import MessageStatusEvent
from app.database import get_async_db
from app.utils.rate_limiter import limiter, check_rate_limit_redis
from app.config import settings
from app.services.webhook.idempotency import AtomicWebhookIdempotency
from app.core.redis_manager import get_async_redis_client
from app.integrations.whatsapp.security.hmac_validator import WebhookHMACValidator
from app.integrations.whatsapp.metrics import whatsapp_metrics
from app.monitoring.metrics import (
    webhook_signature_failures_total,
    webhook_processed_total,
)
from app.utils.timezone import SAO_PAULO_TZ, now_sao_paulo, now_sao_paulo_naive

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/whatsapp", tags=["WhatsApp Webhooks"])

# Redis client for idempotency tracking
_redis_client: Optional[redis.Redis] = None
_idempotency_service: Optional[AtomicWebhookIdempotency] = None

HMAC_FAILURE_RATE_LIMIT = 10
HMAC_FAILURE_RATE_WINDOW = 60
HMAC_FAILURE_BLOCK_THRESHOLD = 5
HMAC_FAILURE_BLOCK_SECONDS = 900
HMAC_FAILURE_TTL_SECONDS = 900


async def get_redis() -> redis.Redis:
    """Get or create Redis client for idempotency."""
    global _redis_client
    if _redis_client is None:
        _redis_client = await get_async_redis_client()
    return _redis_client


async def get_idempotency_service() -> AtomicWebhookIdempotency:
    """Get or create atomic idempotency service."""
    global _idempotency_service
    if _idempotency_service is None:
        redis_client = await get_redis()
        _idempotency_service = AtomicWebhookIdempotency(redis_client)
    return _idempotency_service


def _get_client_ip(request: Request) -> str:
    """
    Resolve client IP.

    Proxy headers are trusted only when explicitly enabled to avoid spoofing.
    """
    trust_proxy_headers = getattr(
        settings, "WHATSAPP_WEBHOOK_TRUST_PROXY_HEADERS", False
    )
    if trust_proxy_headers:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

    return request.client.host if request.client else "unknown"


def _get_hmac_identity(request: Request, instance_name: str) -> str:
    """Build identity key for HMAC failure tracking."""
    client_ip = _get_client_ip(request)
    return f"{client_ip}:{instance_name}"


def _get_hmac_failure_keys(identity: str) -> Dict[str, str]:
    """Get Redis keys for HMAC failure tracking and blocking."""
    return {
        "failure": f"whatsapp:webhook:hmac_failures:{identity}",
        "block": f"whatsapp:webhook:hmac_block:{identity}",
        "rate_limit": f"rate_limit:whatsapp:hmac_failure:{identity}",
    }


async def _is_hmac_blocked(redis_client: redis.Redis, identity: str) -> bool:
    """Check if identity is temporarily blocked for HMAC failures."""
    try:
        keys = _get_hmac_failure_keys(identity)
        blocked = await redis_client.get(keys["block"])
        return blocked is not None
    except Exception as e:
        logger.warning(f"Failed to check HMAC block status: {e}")
        return False


async def _register_hmac_failure(
    redis_client: redis.Redis, identity: str, instance_name: str
) -> None:
    """Record HMAC failure with rate limiting and temporary block."""
    try:
        keys = _get_hmac_failure_keys(identity)
        allowed, retry_after = await check_rate_limit_redis(
            keys["rate_limit"],
            HMAC_FAILURE_RATE_LIMIT,
            HMAC_FAILURE_RATE_WINDOW,
            redis_client,
        )
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Too many invalid webhook signatures",
                headers={"Retry-After": str(retry_after)},
            )

        failure_count = await redis_client.incr(keys["failure"])
        if failure_count == 1:
            await redis_client.expire(keys["failure"], HMAC_FAILURE_TTL_SECONDS)

        if failure_count >= HMAC_FAILURE_BLOCK_THRESHOLD:
            await redis_client.setex(keys["block"], HMAC_FAILURE_BLOCK_SECONDS, "1")
            logger.warning(
                "Webhook HMAC blocked due to consecutive failures",
                extra={
                    "instance_name": instance_name,
                    "identity": identity,
                    "failure_count": failure_count,
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Failed to register HMAC failure: {e}")


async def _reset_hmac_failures(redis_client: redis.Redis, identity: str) -> None:
    """Reset HMAC failure counters on successful validation."""
    try:
        keys = _get_hmac_failure_keys(identity)
        await redis_client.delete(keys["failure"])
        await redis_client.delete(keys["block"])
    except Exception as e:
        logger.debug(f"Failed to reset HMAC failure counters: {e}")


def _validate_webhook_timestamp(timestamp_header: str, max_age_seconds: int) -> bool:
    """Validate webhook timestamp to prevent replay attacks."""
    try:
        timestamp_value = float(timestamp_header)
    except (TypeError, ValueError):
        return False

    current_time = time.time()
    age_seconds = current_time - timestamp_value

    # Allow small clock skew (60s) but reject future timestamps beyond that.
    if age_seconds < -60:
        return False

    return age_seconds <= max_age_seconds


async def is_event_processed(
    event_id: str, event_type: str = "webhook", instance_name: Optional[str] = None
) -> bool:
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
        worker_id = os.getenv("HOSTNAME", "unknown")

        # Atomic check-and-set using SET NX EX
        acquired, reason = await idempotency.try_acquire(
            event_type=event_type, event_id=event_id, worker_id=worker_id
        )

        if not acquired and reason == "infrastructure_failure":
            logger.warning(
                "Idempotency infrastructure unavailable, falling back to non-atomic check",
                extra={
                    "event_id": event_id,
                    "event_type": event_type,
                    "instance_name": instance_name,
                },
            )
            return await _fallback_is_event_processed(event_id, event_type)

        if not acquired:
            logger.info(
                "Duplicate webhook event detected and ignored",
                extra={
                    "event_id": event_id,
                    "event_type": event_type,
                    "worker_id": worker_id,
                    "timestamp": now_sao_paulo().isoformat(),
                    "idempotency": "protected",
                    "reason": reason,
                },
            )
            if instance_name:
                whatsapp_metrics.record_webhook_duplicate(instance_name)
            return True

        # We acquired the lock - this is a new event
        return False

    except Exception as e:
        logger.error(f"Idempotency check failed: {e}", exc_info=True)
        # QW-006: Fallback method if atomic idempotency fails
        return await _fallback_is_event_processed(event_id, event_type)


async def _fallback_is_event_processed(
    event_id: str, event_type: str = "webhook"
) -> bool:
    """
    Fallback idempotency check (used if atomic idempotency fails).

    NOTE: This has a race condition but is better than dropping events.
    """
    try:
        redis_client = await get_redis()
        key = f"webhook:processed:{event_id}"

        # Try atomic SET NX directly
        ttl_seconds = (
            7200 if "status" in event_type.lower() else 86400
        )
        result = await redis_client.set(key, "1", nx=True, ex=ttl_seconds)
        if result:
            return False  # New event, we set it
        else:
            return True  # Already exists
    except Exception as e:
        logger.error(f"Fallback idempotency also failed: {e}")
        return False  # Fail-open to not drop events


def _webhook_rate_limit_key(request: Request) -> str:
    """Extract rate limit key from request (IP + instance_name)."""
    instance_name = request.path_params.get("instance_name", "unknown")
    client_ip = _get_client_ip(request)
    return f"{client_ip}:{instance_name}"

EVENT_PATH_ALIASES = {
    "send-message": "send.message",
    "messages-update": "messages.update",
    "messages-upsert": "messages.upsert",
    "contacts-update": "contacts.upsert",
    "contacts-upsert": "contacts.upsert",
    "chats-update": "chats.upsert",
    "chats-upsert": "chats.upsert",
    "connection-update": "connection.update",
    "presence-update": "presence.update",
}


def _normalize_event_from_path(event_name: str) -> str:
    """Normalize Evolution event from path segment to payload format."""
    normalized = (event_name or "").strip().lower()
    if not normalized:
        return "unknown"
    return EVENT_PATH_ALIASES.get(normalized, normalized.replace("-", "."))


async def _handle_evolution_webhook(
    instance_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession,
    event_override: Optional[str] = None,
):
    """Shared Evolution webhook handler for base and event-specific routes."""
    try:
        # Handle client disconnect gracefully to prevent cascading failures
        try:
            raw_payload = await request.body()
        except Exception as body_error:
            # Client disconnected before we could read the body
            logger.warning(
                "Webhook request body read failed (client likely disconnected)",
                extra={
                    "instance_name": instance_name,
                    "error_type": type(body_error).__name__,
                    "error_message": str(body_error),
                },
            )
            # Return 499 (Client Closed Request) - nginx convention
            raise HTTPException(status_code=499, detail="Client closed connection")
        client_ip = _get_client_ip(request)
        ip_whitelist = getattr(settings, "WHATSAPP_WEBHOOK_IP_WHITELIST", [])
        if ip_whitelist:
            if client_ip == "unknown" or client_ip not in ip_whitelist:
                logger.warning(
                    "Webhook IP rejected by whitelist",
                    extra={
                        "instance_name": instance_name,
                        "client_ip": client_ip,
                    },
                )
                raise HTTPException(
                    status_code=403, detail="Webhook IP not allowed"
                )

        hmac_enabled = getattr(settings, "WHATSAPP_WEBHOOK_HMAC_ENABLED", True)
        if hmac_enabled:
            secret = (
                settings.WHATSAPP_WEBHOOK_SECRET
                or settings.WHATSAPP_EVOLUTION_WEBHOOK_SECRET
            )
            if not secret:
                logger.error("Webhook HMAC enabled but secret is not configured")
                raise HTTPException(
                    status_code=500, detail="Webhook signature secret not configured"
                )

            redis_client = await get_redis()
            identity = _get_hmac_identity(request, instance_name)
            if await _is_hmac_blocked(redis_client, identity):
                raise HTTPException(
                    status_code=403,
                    detail="Webhook signature temporarily blocked",
                )

            timestamp_header = request.headers.get(
                "X-Webhook-Timestamp"
            ) or request.headers.get("X-Evolution-Timestamp")
            timestamp_required = getattr(
                settings, "WHATSAPP_WEBHOOK_TIMESTAMP_REQUIRED", False
            )
            max_timestamp_age = getattr(
                settings, "WHATSAPP_WEBHOOK_MAX_TIMESTAMP_AGE_SECONDS", 300
            )
            if timestamp_required and not timestamp_header:
                webhook_signature_failures_total.labels(source="evolution").inc()
                await _register_hmac_failure(redis_client, identity, instance_name)
                raise HTTPException(
                    status_code=401, detail="Missing webhook timestamp"
                )
            if timestamp_header and not _validate_webhook_timestamp(
                timestamp_header, max_timestamp_age
            ):
                webhook_signature_failures_total.labels(source="evolution").inc()
                await _register_hmac_failure(redis_client, identity, instance_name)
                raise HTTPException(
                    status_code=401, detail="Invalid webhook timestamp"
                )

            signature = request.headers.get("X-Webhook-Signature") or request.headers.get(
                "X-Evolution-Signature"
            )
            if not signature:
                webhook_signature_failures_total.labels(source="evolution").inc()
                await _register_hmac_failure(redis_client, identity, instance_name)
                raise HTTPException(status_code=401, detail="Missing webhook signature")

            if not WebhookHMACValidator.validate_signature(
                raw_payload, signature, secret
            ):
                webhook_signature_failures_total.labels(source="evolution").inc()
                await _register_hmac_failure(redis_client, identity, instance_name)
                raise HTTPException(status_code=401, detail="Invalid webhook signature")

            await _reset_hmac_failures(redis_client, identity)

        # Parse payload after HMAC validation
        payload = json.loads(raw_payload or b"{}")
        if event_override:
            normalized_event = _normalize_event_from_path(event_override)
            if not payload.get("event") or payload.get("event") == "unknown":
                payload["event"] = normalized_event
            elif payload.get("event") != normalized_event:
                logger.debug(
                    "Webhook event mismatch, keeping payload event",
                    extra={
                        "instance_name": instance_name,
                        "payload_event": payload.get("event"),
                        "path_event": normalized_event,
                    },
                )

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

        return {"status": "received", "timestamp": now_sao_paulo()}

    except HTTPException:
        # Re-raise HTTPException to preserve 401/403/429 status codes
        raise

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


@router.post("/evolution/{instance_name}")
# WA-007 FIX: Rate limit per IP + instance_name combination
@limiter.limit("500/minute", key_func=_webhook_rate_limit_key)
async def evolution_webhook(
    instance_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Handle Evolution API webhooks for WhatsApp events.

    Rate limited: 500 requests per minute per IP+instance to prevent DDoS/spam attacks.
    WA-007: Rate limit applied per IP AND instance_name combination
    """
    return await _handle_evolution_webhook(
        instance_name=instance_name,
        request=request,
        background_tasks=background_tasks,
        db=db,
    )


@router.post("/evolution/{instance_name}/{event_name}")
# WA-007 FIX: Rate limit per IP + instance_name combination
@limiter.limit("500/minute", key_func=_webhook_rate_limit_key)
async def evolution_webhook_by_event(
    instance_name: str,
    event_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
):
    """Handle Evolution webhooks when events are sent as path segments."""
    return await _handle_evolution_webhook(
        instance_name=instance_name,
        request=request,
        background_tasks=background_tasks,
        db=db,
        event_override=event_name,
    )



async def process_webhook_event(
    webhook_data: WebhookPayload, background_tasks: BackgroundTasks, db
):
    """Process webhook event."""
    start_time = time.monotonic()
    # Normalize event name (Evolution sends UPPERCASE, we use lowercase)
    event = webhook_data.event.lower().replace("_", ".")
    data = webhook_data.data
    instance_name = webhook_data.instance

    whatsapp_metrics.record_webhook_event(instance_name, event)

    processing_status = "success"

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
        processing_status = "failed"
        logger.error(
            "Error in webhook event processing",
            exc_info=True,
            extra={
                "event_type": event,
                "instance_name": instance_name,
                "error_type": type(e).__name__,
            },
        )
        raise
    finally:
        duration = time.monotonic() - start_time
        whatsapp_metrics.observe_webhook_processing_duration(
            instance_name, event, duration
        )
        webhook_processed_total.labels(
            source="evolution", event_type=event, status=processing_status
        ).inc()


async def handle_message_upsert(
    instance_name: str,
    data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: AsyncSession,
):
    """Handle incoming messages with idempotency protection and proper transaction management."""
    try:
        message_handler = None
        messages = []
        if isinstance(data, list):
            messages = data
        elif isinstance(data, dict):
            if "messages" in data:
                nested = data.get("messages")
                if isinstance(nested, list):
                    messages = nested
                elif isinstance(nested, dict):
                    messages = [nested]
            else:
                messages = [data]

        for message_data in messages:
            message_info = message_data.get("message", {})
            key = message_data.get("key", {})
            from_me = bool(key.get("fromMe"))

            # Skip status messages
            if message_info.get("messageStubType"):
                continue

            # Extract message details
            message_id = key.get("id", "")
            chat_id = key.get("remoteJid", "")
            sender_id = key.get("participant") or key.get("remoteJid", "")

            # IDEMPOTENCY: Check if this message was already processed (QW-006: Atomic)
            if await is_event_processed(
                message_id, event_type="message", instance_name=instance_name
            ):
                logger.debug(f"Skipping duplicate message: {message_id}")
                continue

            if not from_me:
                try:
                    if message_handler is None:
                        from app.services.webhook.handlers.message_handler import (
                            MessageWebhookHandler,
                        )

                        message_handler = MessageWebhookHandler(db)
                    handler_payload = dict(message_data)
                    handler_payload.setdefault("instance", instance_name)
                    await message_handler.process_message(handler_payload)
                except Exception as handler_error:
                    logger.error(
                        "MessageWebhookHandler failed",
                        exc_info=True,
                        extra={
                            "instance_name": instance_name,
                            "message_id": message_id,
                            "error_type": type(handler_error).__name__,
                        },
                    )

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
                            message_data.get("messageTimestamp", 0), tz=SAO_PAULO_TZ
                        ).replace(tzinfo=None),
                        delivered_at=now_sao_paulo_naive(),
                        message_data={"incoming": True, "message_data": message_data},
                    )

                    db.add(message)
                    # FIX P1-005: Use flush() first to get message ID, schedule background
                    # task, then commit. This ensures both message storage and flow trigger
                    # are part of the same logical transaction.
                    db.flush()

                    logger.info(f"Stored incoming message {message_id} from {sender_id}")

                    # FIX P1-005: Commit after message persistence to keep storage atomic.
                    db.commit()

                    try:
                        idempotency = await get_idempotency_service()
                        await idempotency.mark_completed("message", message_id)
                    except Exception as mark_error:
                        logger.debug(
                            f"Failed to mark idempotency completed for message {message_id}: {mark_error}"
                        )

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
        raise


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
            if await is_event_processed(
                event_id, event_type="status", instance_name=instance_name
            ):
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
                    # Store previous status for audit trail
                    previous_status = message.status.value if message.status else None

                    message.status = new_status
                    message.updated_at = now_sao_paulo_naive()

                    if new_status == MessageStatus.DELIVERED:
                        message.delivered_at = now_sao_paulo_naive()
                    elif new_status == MessageStatus.READ:
                        message.read_at = now_sao_paulo_naive()

                    # Create audit trail event for message status change
                    status_event = MessageStatusEvent(
                        message_id=message.id,
                        status=new_status.value,
                        previous_status=previous_status,
                        whatsapp_id=key.get("id"),
                        created_at=now_sao_paulo(),
                        event_metadata={"source": "evolution_webhook", "raw_status": status_update}
                    )
                    db.add(status_event)

                    db.commit()
                    logger.info(f"Updated message {message_id} status to {new_status}")
                    try:
                        idempotency = await get_idempotency_service()
                        await idempotency.mark_completed("status", event_id)
                    except Exception as mark_error:
                        logger.debug(
                            f"Failed to mark idempotency completed for status {event_id}: {mark_error}"
                        )

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
        raise


async def handle_send_message(
    instance_name: str, data: Dict[str, Any], db: Session
):
    """
    Handle outgoing message confirmation.

    Correlation is strict to avoid linking Evolution message IDs to the wrong
    pending message when multiple sends are in flight.
    """
    try:
        events = data if isinstance(data, list) else [data]

        for event_data in events:
            if not isinstance(event_data, dict):
                continue

            key = event_data.get("key", {})
            message_id = key.get("id", "")
            if not message_id:
                continue

            # Skip if we already linked this Evolution message id.
            existing_stmt = select(WhatsAppMessage).where(
                WhatsAppMessage.instance_name == instance_name,
                WhatsAppMessage.external_id == message_id,
            )
            existing_result = db.execute(existing_stmt)
            if existing_result.scalar_one_or_none():
                continue

            remote_jid = key.get("remoteJid", "")
            recipient_phone = remote_jid.split("@")[0] if "@" in remote_jid else remote_jid

            message_info = event_data.get("message", {})
            outbound_content = ""
            outbound_media_url = None

            if "conversation" in message_info:
                outbound_content = message_info.get("conversation", "")
            elif "extendedTextMessage" in message_info:
                outbound_content = (
                    message_info.get("extendedTextMessage", {}).get("text", "")
                )
            elif "imageMessage" in message_info:
                outbound_content = message_info.get("imageMessage", {}).get("caption", "")
                outbound_media_url = message_info.get("imageMessage", {}).get("url", "")
            elif "documentMessage" in message_info:
                outbound_content = message_info.get("documentMessage", {}).get("caption", "")
                outbound_media_url = message_info.get("documentMessage", {}).get("url", "")
            elif "videoMessage" in message_info:
                outbound_content = message_info.get("videoMessage", {}).get("caption", "")
                outbound_media_url = message_info.get("videoMessage", {}).get("url", "")

            stmt = select(WhatsAppMessage).where(
                WhatsAppMessage.instance_name == instance_name,
                WhatsAppMessage.external_id.is_(None),
                WhatsAppMessage.status == MessageStatus.PENDING,
            )

            if remote_jid:
                stmt = stmt.where(WhatsAppMessage.chat_id == remote_jid)
            elif recipient_phone:
                stmt = stmt.where(WhatsAppMessage.recipient_id == recipient_phone)
            else:
                logger.warning(
                    "Skipping send.message correlation without destination",
                    extra={
                        "instance_name": instance_name,
                        "external_id": message_id,
                    },
                )
                continue

            if outbound_content:
                stmt = stmt.where(WhatsAppMessage.content == outbound_content)
            if outbound_media_url:
                stmt = stmt.where(WhatsAppMessage.media_url == outbound_media_url)

            stmt = stmt.order_by(WhatsAppMessage.created_at.desc()).limit(5)
            result = db.execute(stmt)
            candidates = result.scalars().all()

            if not candidates:
                logger.warning(
                    "No pending message candidate found for send.message confirmation",
                    extra={
                        "instance_name": instance_name,
                        "external_id": message_id,
                        "chat_id": remote_jid,
                    },
                )
                continue

            selected_message = None
            if len(candidates) == 1:
                selected_message = candidates[0]
            else:
                timestamp_hint = event_data.get("messageTimestamp") or event_data.get(
                    "timestamp"
                )
                if timestamp_hint:
                    try:
                        webhook_time = datetime.fromtimestamp(
                            float(timestamp_hint), tz=SAO_PAULO_TZ
                        ).replace(tzinfo=None)
                        scored_candidates = []
                        for candidate in candidates:
                            created_at = candidate.created_at
                            if created_at is None:
                                continue
                            if created_at.tzinfo is not None:
                                created_at = created_at.astimezone(SAO_PAULO_TZ).replace(
                                    tzinfo=None
                                )
                            delta_seconds = abs((created_at - webhook_time).total_seconds())
                            scored_candidates.append((delta_seconds, candidate))
                        scored_candidates.sort(key=lambda item: item[0])
                        if scored_candidates and (
                            len(scored_candidates) == 1
                            or scored_candidates[0][0] < scored_candidates[1][0]
                        ):
                            selected_message = scored_candidates[0][1]
                    except (TypeError, ValueError):
                        selected_message = None

            if selected_message is None:
                logger.warning(
                    "Ambiguous send.message correlation; skipping to avoid wrong linkage",
                    extra={
                        "instance_name": instance_name,
                        "external_id": message_id,
                        "chat_id": remote_jid,
                        "candidate_count": len(candidates),
                    },
                )
                continue

            selected_message.external_id = message_id
            selected_message.status = MessageStatus.SENT
            now = now_sao_paulo_naive()
            selected_message.sent_at = now
            selected_message.updated_at = now
            db.commit()

            logger.info(
                "Updated outgoing message with external ID %s (message=%s)",
                message_id,
                selected_message.id,
            )

    except Exception as e:
        logger.error(f"Error handling send message: {e}", exc_info=True)
        raise


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
                existing_contact.updated_at = now_sao_paulo_naive()
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
        db.rollback()
        logger.error(f"Error handling contact upsert: {e}", exc_info=True)
        raise


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
                instance.last_activity = now_sao_paulo_naive()
                instance.updated_at = now_sao_paulo_naive()

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
        raise


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
                    contact.last_seen = datetime.fromtimestamp(
                        last_seen_timestamp, tz=SAO_PAULO_TZ
                    ).replace(tzinfo=None)
                    contact.updated_at = now_sao_paulo_naive()
                    db.commit()

    except Exception as e:
        db.rollback()
        logger.error(f"Error handling presence update: {e}", exc_info=True)
        raise


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
                    contact.updated_at = now_sao_paulo_naive()
                    db.commit()

    except Exception as e:
        db.rollback()
        logger.error(f"Error handling chat upsert: {e}", exc_info=True)
        raise


# Health check endpoint for webhooks
@router.get("/health")
async def webhook_health():
    """Health check for webhook endpoint."""
    return {
        "status": "healthy",
        "timestamp": now_sao_paulo(),
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
            "timestamp": now_sao_paulo(),
        }
    except Exception as e:
        # FIX P2-001: Chain exception to preserve original traceback
        raise HTTPException(
            status_code=400, detail=f"Invalid webhook payload: {str(e)}"
        ) from e
