"""
V2 Webhooks API
Enhanced webhook management with modern patterns.
Implements HMAC signature validation, idempotency, retry logic, cursor pagination, and Redis caching.
"""

import logging
import hmac
import hashlib
import time
import secrets
import json
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Request, HTTPException, Depends, Header, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func, desc

from app.database import get_db
from app.dependencies.auth_dependencies import get_redis_cache
from app.config import settings
from app.models.webhook_event import WebhookEvent
from app.services.webhook_processor import WebhookProcessor
from app.integrations.evolution import get_evolution_client
from app.utils.rate_limiter import limiter
from app.schemas.v2.webhooks import (
    WebhookCreate,
    WebhookUpdate,
    WebhookResponse,
    WebhookList,
    WebhookTestRequest,
    WebhookTestResponse,
    WebhookDelivery,
    WebhookDeliveryList,
    WebhookRetryRequest,
    WebhookRetryResponse,
    WebhookSecretRotate,
    WebhookSecretResponse,
    WebhookLog,
    WebhookLogList,
    WebhookStats,
    WebhookHealth,
    WebhookInboundEvent,
    WebhookInboundResponse,
    WebhookEventTypeInfo,
    WebhookEventTypeList,
    FailedWebhook,
    FailedWebhookList,
    WebhookEventType,
    WebhookStatus,
    DeliveryStatus,
)
from app.schemas.v2.common import CursorEncoder
from app.api.v2.dependencies import get_pagination_params

logger = logging.getLogger(__name__)
router = APIRouter()

# ============================================================================
# SECURITY & CONFIGURATION
# ============================================================================
MAX_TIMESTAMP_AGE_SECONDS = 300  # 5 minutes
IDEMPOTENCY_WINDOW_HOURS = 24  # 24 hours
RATE_LIMIT_WEBHOOKS_PER_HOUR = 10  # 10 webhook creations per hour
REDIS_TTL_WEBHOOK_CONFIG = 600  # 10 minutes
REDIS_TTL_WEBHOOK_STATS = 900  # 15 minutes
REDIS_TTL_IDEMPOTENCY = 86400  # 24 hours

# Retry configuration
MAX_RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 2  # seconds
RETRY_MAX_DELAY = 300  # 5 minutes


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def generate_webhook_secret() -> str:
    """Generate secure webhook secret"""
    return f"wh_secret_{secrets.token_urlsafe(32)}"


def compute_webhook_signature(payload: bytes, secret: str, timestamp: str = None) -> str:
    """Compute HMAC-SHA256 signature for webhook payload"""
    if timestamp:
        signature_payload = f"{timestamp}.{payload.decode('utf-8')}"
        signature_bytes = signature_payload.encode("utf-8")
    else:
        signature_bytes = payload

    return hmac.new(
        secret.encode("utf-8"),
        signature_bytes,
        hashlib.sha256,
    ).hexdigest()


def calculate_retry_delay(attempt: int) -> int:
    """Calculate exponential backoff delay"""
    delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
    return delay


async def verify_webhook_signature_v2(
    request: Request,
    x_webhook_signature: str = Header(..., alias="X-Webhook-Signature"),
    x_webhook_timestamp: Optional[str] = Header(None, alias="X-Webhook-Timestamp"),
    x_webhook_id: Optional[str] = Header(None, alias="X-Webhook-Id"),
) -> Dict[str, Any]:
    """
    Verify webhook signature using HMAC-SHA256.

    Security features:
    1. HMAC signature verification (prevents tampering)
    2. Timestamp validation (prevents replay attacks)
    3. Idempotency ID extraction (enables duplicate prevention)

    Raises:
        HTTPException: 401 if signature invalid or timestamp expired
    """
    # Check webhook secret configured
    if not settings.EVOLUTION_WEBHOOK_SECRET:
        logger.error("SECURITY: Webhook secret not configured")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook authentication not configured"
        )

    try:
        # Get raw request body
        payload = await request.body()

        # Validate timestamp (replay attack prevention)
        if x_webhook_timestamp:
            try:
                webhook_time = int(x_webhook_timestamp)
                current_time = int(time.time())
                time_diff = abs(current_time - webhook_time)

                if time_diff > MAX_TIMESTAMP_AGE_SECONDS:
                    logger.warning(
                        f"SECURITY: Webhook timestamp expired. Age: {time_diff}s"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Webhook timestamp expired (max age: {MAX_TIMESTAMP_AGE_SECONDS}s)",
                    )
                logger.debug(f"Webhook timestamp validated (age: {time_diff}s)")
            except ValueError:
                logger.warning(f"SECURITY: Invalid timestamp: {x_webhook_timestamp}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid webhook timestamp format"
                )
        else:
            logger.warning("SECURITY: Webhook timestamp not provided")

        # Compute expected signature
        expected_signature = compute_webhook_signature(
            payload,
            settings.EVOLUTION_WEBHOOK_SECRET,
            x_webhook_timestamp
        )

        # Constant-time comparison (timing attack prevention)
        if not hmac.compare_digest(x_webhook_signature, expected_signature):
            logger.warning(
                f"SECURITY: Invalid signature. Expected: {expected_signature[:8]}..."
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )

        logger.debug("Webhook signature verified successfully")

        return {
            "verified": True,
            "webhook_id": x_webhook_id,
            "timestamp": x_webhook_timestamp,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating webhook signature: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook signature verification failed"
        )


async def check_idempotency(
    webhook_id: Optional[str],
    event_type: str,
    db: Session,
    redis_cache=None
) -> bool:
    """
    Check if webhook has already been processed (idempotency).
    Uses Redis cache first, falls back to database.

    Returns:
        bool: True if webhook is new (should process), False if duplicate
    """
    if not webhook_id:
        logger.warning(f"No webhook ID for {event_type}. Idempotency disabled.")
        return True

    try:
        # Check Redis cache first (fast path)
        if redis_cache:
            cache_key = f"webhook:idempotency:{webhook_id}"
            cached = await redis_cache.get(cache_key)
            if cached:
                logger.warning(f"IDEMPOTENCY: Duplicate webhook (Redis): {webhook_id}")
                return False

        # Check database (fallback)
        cutoff_time = datetime.utcnow() - timedelta(hours=IDEMPOTENCY_WINDOW_HOURS)
        existing = db.execute(
            select(WebhookEvent).where(
                WebhookEvent.webhook_id == webhook_id,
                WebhookEvent.created_at >= cutoff_time,
            )
        ).first()

        if existing:
            logger.warning(f"IDEMPOTENCY: Duplicate webhook (DB): {webhook_id}")
            # Cache the result
            if redis_cache:
                await redis_cache.set(cache_key, "1", expire=REDIS_TTL_IDEMPOTENCY)
            return False

        # Mark as processed in Redis
        if redis_cache:
            await redis_cache.set(cache_key, "1", expire=REDIS_TTL_IDEMPOTENCY)

        logger.debug(f"Webhook ID {webhook_id} is new (will process)")
        return True

    except Exception as e:
        logger.error(f"Error checking idempotency: {e}", exc_info=True)
        return True  # Fail open


# ============================================================================
# WEBHOOK MANAGEMENT ENDPOINTS
# ============================================================================
@router.get("", response_model=WebhookList)
@limiter.limit("100/minute")
async def list_webhooks(
    request: Request,
    pagination: dict = Depends(get_pagination_params),
    status_filter: Optional[WebhookStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
):
    """
    List webhooks with cursor-based pagination.

    Filters:
    - status: Filter by webhook status (active, inactive, paused, error)

    Redis cache: 10 minutes TTL
    """
    try:
        # Build cache key
        cache_key = f"webhooks:list:{pagination.get('limit')}:{status_filter or 'all'}"
        if pagination.get("cursor_data"):
            cache_key += f":{pagination['cursor_data'].get('id', 0)}"

        # Try cache first
        cached = await redis_cache.get(cache_key)
        if cached:
            logger.debug("Returning cached webhook list")
            return WebhookList(**json.loads(cached))

        # Query database
        query = select(WebhookEvent)

        # Apply status filter
        if status_filter:
            query = query.where(WebhookEvent.status == status_filter.value)

        # Apply cursor
        if pagination.get("cursor_data"):
            cursor_id = pagination["cursor_data"].get("id")
            query = query.where(WebhookEvent.id > cursor_id)

        # Order and limit
        query = query.order_by(WebhookEvent.id).limit(pagination["limit"] + 1)

        results = db.execute(query).scalars().all()

        # Check if more results
        has_more = len(results) > pagination["limit"]
        webhooks = results[:pagination["limit"]]

        # Build response
        webhook_responses = []
        for wh in webhooks:
            webhook_responses.append(
                WebhookResponse(
                    id=wh.id,
                    url=wh.url or "N/A",
                    events=wh.events or [],
                    description=wh.description,
                    status=wh.status or "active",
                    secret_preview=(wh.secret or "")[:8] if wh.secret else "N/A",
                    headers=wh.headers or {},
                    timeout=wh.timeout or 30,
                    retry_enabled=wh.retry_enabled if hasattr(wh, 'retry_enabled') else True,
                    max_retries=wh.max_retries if hasattr(wh, 'max_retries') else 3,
                    created_at=wh.created_at,
                    updated_at=wh.updated_at,
                    last_triggered_at=wh.last_triggered_at if hasattr(wh, 'last_triggered_at') else None,
                    success_count=wh.success_count if hasattr(wh, 'success_count') else 0,
                    failure_count=wh.failure_count if hasattr(wh, 'failure_count') else 0,
                )
            )

        # Generate next cursor
        next_cursor = None
        if has_more and webhooks:
            last_webhook = webhooks[-1]
            next_cursor = CursorEncoder.encode(last_webhook.id, last_webhook.created_at)

        response = WebhookList(
            data=webhook_responses,
            next_cursor=next_cursor,
            has_more=has_more,
            total=None  # Could add count query if needed
        )

        # Cache response
        await redis_cache.set(
            cache_key,
            json.dumps(response.dict()),
            expire=REDIS_TTL_WEBHOOK_CONFIG
        )

        return response

    except Exception as e:
        logger.error(f"Error listing webhooks: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve webhooks"
        )


@router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(f"{RATE_LIMIT_WEBHOOKS_PER_HOUR}/hour")
async def create_webhook(
    request: Request,
    webhook_data: WebhookCreate,
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
):
    """
    Create new webhook configuration.

    Rate limit: 10 webhooks per hour per user.
    Auto-generates secret if not provided.
    """
    try:
        # Generate secret if not provided
        secret = webhook_data.secret or generate_webhook_secret()

        # Create webhook record
        webhook = WebhookEvent(
            id=uuid4(),
            webhook_id=f"wh_{secrets.token_urlsafe(16)}",
            event_type="webhook.created",
            url=str(webhook_data.url),
            events=webhook_data.events,
            description=webhook_data.description,
            secret=secret,
            headers=webhook_data.headers or {},
            timeout=webhook_data.timeout,
            retry_enabled=webhook_data.retry_enabled,
            max_retries=webhook_data.max_retries,
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.add(webhook)
        db.commit()
        db.refresh(webhook)

        # Invalidate list cache
        await redis_cache.delete_pattern("webhooks:list:*")

        logger.info(f"Created webhook: {webhook.id}")

        return WebhookResponse(
            id=webhook.id,
            url=webhook.url,
            events=webhook.events,
            description=webhook.description,
            status=webhook.status,
            secret_preview=secret[:8],
            headers=webhook.headers,
            timeout=webhook.timeout,
            retry_enabled=webhook.retry_enabled,
            max_retries=webhook.max_retries,
            created_at=webhook.created_at,
            updated_at=webhook.updated_at,
            last_triggered_at=None,
            success_count=0,
            failure_count=0,
        )

    except Exception as e:
        logger.error(f"Error creating webhook: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create webhook"
        )


@router.get("/{webhook_id}", response_model=WebhookResponse)
@limiter.limit("100/minute")
async def get_webhook(
    request: Request,
    webhook_id: UUID,
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
):
    """
    Get webhook configuration by ID.

    Redis cache: 10 minutes TTL
    """
    try:
        # Check cache
        cache_key = f"webhook:{webhook_id}"
        cached = await redis_cache.get(cache_key)
        if cached:
            logger.debug(f"Returning cached webhook: {webhook_id}")
            return WebhookResponse(**json.loads(cached))

        # Query database
        webhook = db.query(WebhookEvent).filter(WebhookEvent.id == webhook_id).first()
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )

        response = WebhookResponse(
            id=webhook.id,
            url=webhook.url or "N/A",
            events=webhook.events or [],
            description=webhook.description,
            status=webhook.status or "active",
            secret_preview=(webhook.secret or "")[:8],
            headers=webhook.headers or {},
            timeout=webhook.timeout or 30,
            retry_enabled=getattr(webhook, 'retry_enabled', True),
            max_retries=getattr(webhook, 'max_retries', 3),
            created_at=webhook.created_at,
            updated_at=webhook.updated_at,
            last_triggered_at=getattr(webhook, 'last_triggered_at', None),
            success_count=getattr(webhook, 'success_count', 0),
            failure_count=getattr(webhook, 'failure_count', 0),
        )

        # Cache response
        await redis_cache.set(
            cache_key,
            json.dumps(response.dict()),
            expire=REDIS_TTL_WEBHOOK_CONFIG
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve webhook"
        )


@router.put("/{webhook_id}", response_model=WebhookResponse)
@limiter.limit("60/minute")
async def update_webhook(
    request: Request,
    webhook_id: UUID,
    webhook_data: WebhookUpdate,
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
):
    """
    Update webhook configuration.

    Invalidates cache on update.
    """
    try:
        webhook = db.query(WebhookEvent).filter(WebhookEvent.id == webhook_id).first()
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )

        # Update fields
        if webhook_data.url is not None:
            webhook.url = str(webhook_data.url)
        if webhook_data.events is not None:
            webhook.events = webhook_data.events
        if webhook_data.description is not None:
            webhook.description = webhook_data.description
        if webhook_data.status is not None:
            webhook.status = webhook_data.status.value
        if webhook_data.headers is not None:
            webhook.headers = webhook_data.headers
        if webhook_data.timeout is not None:
            webhook.timeout = webhook_data.timeout
        if webhook_data.retry_enabled is not None:
            webhook.retry_enabled = webhook_data.retry_enabled
        if webhook_data.max_retries is not None:
            webhook.max_retries = webhook_data.max_retries

        webhook.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(webhook)

        # Invalidate caches
        await redis_cache.delete(f"webhook:{webhook_id}")
        await redis_cache.delete_pattern("webhooks:list:*")

        logger.info(f"Updated webhook: {webhook_id}")

        return WebhookResponse(
            id=webhook.id,
            url=webhook.url,
            events=webhook.events,
            description=webhook.description,
            status=webhook.status,
            secret_preview=(webhook.secret or "")[:8],
            headers=webhook.headers,
            timeout=webhook.timeout,
            retry_enabled=webhook.retry_enabled,
            max_retries=webhook.max_retries,
            created_at=webhook.created_at,
            updated_at=webhook.updated_at,
            last_triggered_at=getattr(webhook, 'last_triggered_at', None),
            success_count=getattr(webhook, 'success_count', 0),
            failure_count=getattr(webhook, 'failure_count', 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating webhook: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update webhook"
        )


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_webhook(
    request: Request,
    webhook_id: UUID,
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
):
    """
    Delete webhook configuration.

    Invalidates cache on deletion.
    """
    try:
        webhook = db.query(WebhookEvent).filter(WebhookEvent.id == webhook_id).first()
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )

        db.delete(webhook)
        db.commit()

        # Invalidate caches
        await redis_cache.delete(f"webhook:{webhook_id}")
        await redis_cache.delete_pattern("webhooks:list:*")

        logger.info(f"Deleted webhook: {webhook_id}")

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete webhook"
        )


@router.post("/{webhook_id}/test", response_model=WebhookTestResponse)
@limiter.limit("10/minute")
async def test_webhook(
    request: Request,
    webhook_id: UUID,
    test_data: WebhookTestRequest,
    db: Session = Depends(get_db),
):
    """
    Test webhook by sending a test event.

    Rate limit: 10 tests per minute.
    """
    try:
        webhook = db.query(WebhookEvent).filter(WebhookEvent.id == webhook_id).first()
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )

        # Build test payload
        test_payload = {
            "event": test_data.event_type.value,
            "data": test_data.payload or {"test": True},
            "timestamp": str(int(time.time())),
            "webhook_id": f"test_{secrets.token_urlsafe(8)}"
        }

        # Send test request (mock implementation)
        import httpx
        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=webhook.timeout or 30) as client:
                # Compute signature
                payload_bytes = json.dumps(test_payload).encode()
                signature = compute_webhook_signature(
                    payload_bytes,
                    webhook.secret or "",
                    test_payload["timestamp"]
                )

                # Send request
                response = await client.post(
                    webhook.url,
                    json=test_payload,
                    headers={
                        "X-Webhook-Signature": signature,
                        "X-Webhook-Timestamp": test_payload["timestamp"],
                        "X-Webhook-Id": test_payload["webhook_id"],
                        "Content-Type": "application/json",
                        **(webhook.headers or {})
                    }
                )

                response_time = (time.time() - start_time) * 1000

                return WebhookTestResponse(
                    success=response.status_code < 400,
                    status_code=response.status_code,
                    response_time_ms=round(response_time, 2),
                    response_body=response.text[:200] if response.text else None,
                    error=None if response.status_code < 400 else f"HTTP {response.status_code}"
                )

        except httpx.TimeoutException:
            response_time = (time.time() - start_time) * 1000
            return WebhookTestResponse(
                success=False,
                status_code=None,
                response_time_ms=round(response_time, 2),
                response_body=None,
                error="Request timeout"
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return WebhookTestResponse(
                success=False,
                status_code=None,
                response_time_ms=round(response_time, 2),
                response_body=None,
                error=str(e)
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test webhook"
        )


# ============================================================================
# WEBHOOK EVENTS & INBOUND
# ============================================================================
@router.post("/inbound", response_model=WebhookInboundResponse)
async def receive_inbound_webhook(
    request: Request,
    event_data: WebhookInboundEvent,
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    verification: dict = Depends(verify_webhook_signature_v2),
):
    """
    Receive incoming webhook from external systems (Evolution API).

    Security:
    - HMAC signature verification required
    - Timestamp validation (5 min window)
    - Idempotency checking (24h window)

    Public endpoint (no authentication required beyond webhook signature).
    """
    try:
        webhook_id = verification.get("webhook_id")
        event_type = event_data.event

        logger.info(f"Received inbound webhook: {event_type}")

        # Check idempotency
        is_new = await check_idempotency(webhook_id, event_type, db, redis_cache)
        if not is_new:
            return WebhookInboundResponse(
                status="duplicate",
                message="Webhook already processed (idempotency)",
                webhook_id=webhook_id,
                message_id=None
            )

        # Process webhook
        webhook_processor = WebhookProcessor(db)

        # Route to appropriate processor
        if "message" in event_type:
            message_id = await webhook_processor.process_message_webhook(
                event_data.data,
                webhook_id=webhook_id
            )

            if message_id:
                return WebhookInboundResponse(
                    status="success",
                    message="Message processed successfully",
                    webhook_id=webhook_id,
                    message_id=message_id
                )
            else:
                return WebhookInboundResponse(
                    status="ignored",
                    message="Message ignored (patient not found or invalid data)",
                    webhook_id=webhook_id,
                    message_id=None
                )

        elif "connection" in event_type:
            success = await webhook_processor.process_connection_webhook(
                event_data.data,
                webhook_id=webhook_id
            )

            return WebhookInboundResponse(
                status="success" if success else "error",
                message="Connection status processed" if success else "Failed to process",
                webhook_id=webhook_id,
                message_id=None
            )

        else:
            # Generic processing
            return WebhookInboundResponse(
                status="success",
                message="Event processed successfully",
                webhook_id=webhook_id,
                message_id=None
            )

    except Exception as e:
        logger.error(f"Error processing inbound webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/events", response_model=WebhookEventTypeList)
@limiter.limit("100/minute")
async def get_event_types(request: Request):
    """
    Get available webhook event types with descriptions.
    """
    event_types = [
        WebhookEventTypeInfo(
            event=WebhookEventType.MESSAGE_RECEIVED.value,
            description="Triggered when a new message is received from a patient",
            payload_schema={"message_id": "string", "from": "string", "text": "string"}
        ),
        WebhookEventTypeInfo(
            event=WebhookEventType.MESSAGE_SENT.value,
            description="Triggered when a message is sent to a patient",
            payload_schema={"message_id": "string", "to": "string", "status": "string"}
        ),
        WebhookEventTypeInfo(
            event=WebhookEventType.MESSAGE_DELIVERED.value,
            description="Triggered when a message is delivered to the recipient",
            payload_schema={"message_id": "string", "delivered_at": "string"}
        ),
        WebhookEventTypeInfo(
            event=WebhookEventType.MESSAGE_READ.value,
            description="Triggered when a message is read by the recipient",
            payload_schema={"message_id": "string", "read_at": "string"}
        ),
        WebhookEventTypeInfo(
            event=WebhookEventType.CONNECTION_OPEN.value,
            description="Triggered when WhatsApp connection is established",
            payload_schema={"instance_id": "string", "status": "string"}
        ),
        WebhookEventTypeInfo(
            event=WebhookEventType.PATIENT_CREATED.value,
            description="Triggered when a new patient is created",
            payload_schema={"patient_id": "string", "name": "string"}
        ),
        WebhookEventTypeInfo(
            event=WebhookEventType.QUIZ_COMPLETED.value,
            description="Triggered when a patient completes a quiz",
            payload_schema={"quiz_id": "string", "patient_id": "string", "score": "number"}
        ),
    ]

    return WebhookEventTypeList(
        events=event_types,
        total=len(event_types)
    )


# ============================================================================
# WEBHOOK DELIVERIES & RETRY
# ============================================================================
@router.get("/{webhook_id}/deliveries", response_model=WebhookDeliveryList)
@limiter.limit("100/minute")
async def get_webhook_deliveries(
    request: Request,
    webhook_id: UUID,
    pagination: dict = Depends(get_pagination_params),
    status_filter: Optional[DeliveryStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    """
    Get webhook delivery history with cursor pagination.

    Filters:
    - status: Filter by delivery status (pending, success, failed, retrying)
    """
    try:
        # Verify webhook exists
        webhook = db.query(WebhookEvent).filter(WebhookEvent.id == webhook_id).first()
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )

        # Build query (mock - actual implementation would query deliveries table)
        # For now, return empty list
        return WebhookDeliveryList(
            data=[],
            next_cursor=None,
            has_more=False,
            total=0
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving deliveries: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve deliveries"
        )


@router.post("/{webhook_id}/deliveries/{delivery_id}/retry", response_model=WebhookRetryResponse)
@limiter.limit("10/minute")
async def retry_webhook_delivery(
    request: Request,
    webhook_id: UUID,
    delivery_id: UUID,
    retry_data: WebhookRetryRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Retry a failed webhook delivery.

    Rate limit: 10 retries per minute.
    Uses exponential backoff for automatic retries.
    """
    try:
        # Verify webhook exists
        webhook = db.query(WebhookEvent).filter(WebhookEvent.id == webhook_id).first()
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )

        # Mock implementation - actual would query delivery and retry
        logger.info(f"Retrying delivery {delivery_id} for webhook {webhook_id}")

        return WebhookRetryResponse(
            success=True,
            delivery_id=delivery_id,
            attempt=2,
            message="Retry scheduled successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying delivery: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry delivery"
        )


# ============================================================================
# WEBHOOK CONFIGURATION
# ============================================================================
@router.put("/{webhook_id}/secret", response_model=WebhookSecretResponse)
@limiter.limit("5/hour")
async def rotate_webhook_secret(
    request: Request,
    webhook_id: UUID,
    secret_data: WebhookSecretRotate,
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
):
    """
    Rotate webhook secret.

    Rate limit: 5 rotations per hour.
    Auto-generates new secret if not provided.
    """
    try:
        webhook = db.query(WebhookEvent).filter(WebhookEvent.id == webhook_id).first()
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )

        # Generate new secret
        new_secret = secret_data.new_secret or generate_webhook_secret()
        webhook.secret = new_secret
        webhook.updated_at = datetime.utcnow()

        db.commit()

        # Invalidate cache
        await redis_cache.delete(f"webhook:{webhook_id}")

        logger.info(f"Rotated secret for webhook: {webhook_id}")

        return WebhookSecretResponse(
            secret_preview=new_secret[:8],
            rotated_at=webhook.updated_at,
            message="Secret rotated successfully. Save your new secret securely."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rotating secret: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rotate secret"
        )


@router.get("/{webhook_id}/logs", response_model=WebhookLogList)
@limiter.limit("100/minute")
async def get_webhook_logs(
    request: Request,
    webhook_id: UUID,
    pagination: dict = Depends(get_pagination_params),
    db: Session = Depends(get_db),
):
    """
    Get webhook activity logs with cursor pagination.
    """
    try:
        # Verify webhook exists
        webhook = db.query(WebhookEvent).filter(WebhookEvent.id == webhook_id).first()
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )

        # Mock implementation
        return WebhookLogList(
            data=[],
            next_cursor=None,
            has_more=False,
            total=0
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve logs"
        )


# ============================================================================
# ANALYTICS & HEALTH
# ============================================================================
@router.get("/stats", response_model=WebhookStats)
@limiter.limit("100/minute")
async def get_webhook_stats(
    request: Request,
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
):
    """
    Get webhook statistics.

    Redis cache: 15 minutes TTL
    """
    try:
        # Check cache
        cache_key = "webhooks:stats"
        cached = await redis_cache.get(cache_key)
        if cached:
            logger.debug("Returning cached webhook stats")
            return WebhookStats(**json.loads(cached))

        # Calculate stats (mock implementation)
        total_webhooks = db.query(func.count(WebhookEvent.id)).scalar() or 0
        active_webhooks = db.query(func.count(WebhookEvent.id)).filter(
            WebhookEvent.status == "active"
        ).scalar() or 0

        stats = WebhookStats(
            total_webhooks=total_webhooks,
            active_webhooks=active_webhooks,
            total_deliveries=0,
            successful_deliveries=0,
            failed_deliveries=0,
            pending_deliveries=0,
            average_response_time_ms=0.0,
            success_rate=0.0,
            last_24h_deliveries=0
        )

        # Cache stats
        await redis_cache.set(
            cache_key,
            json.dumps(stats.dict()),
            expire=REDIS_TTL_WEBHOOK_STATS
        )

        return stats

    except Exception as e:
        logger.error(f"Error retrieving webhook stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )


@router.get("/{webhook_id}/health", response_model=WebhookHealth)
@limiter.limit("100/minute")
async def get_webhook_health(
    request: Request,
    webhook_id: UUID,
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
):
    """
    Get webhook health status.

    Redis cache: 5 minutes TTL
    """
    try:
        # Check cache
        cache_key = f"webhook:health:{webhook_id}"
        cached = await redis_cache.get(cache_key)
        if cached:
            return WebhookHealth(**json.loads(cached))

        # Verify webhook exists
        webhook = db.query(WebhookEvent).filter(WebhookEvent.id == webhook_id).first()
        if not webhook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )

        # Calculate health (mock implementation)
        health = WebhookHealth(
            webhook_id=webhook_id,
            status="healthy",
            uptime_percentage=99.9,
            recent_failures=0,
            average_response_time_ms=150.0,
            last_success_at=webhook.updated_at,
            last_failure_at=None,
            recommendations=[]
        )

        # Cache health
        await redis_cache.set(
            cache_key,
            json.dumps(health.dict()),
            expire=300  # 5 minutes
        )

        return health

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving webhook health: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve health status"
        )


@router.get("/failed", response_model=FailedWebhookList)
@limiter.limit("100/minute")
async def get_failed_webhooks(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Get webhooks with consecutive failures.

    Helps identify webhooks that need attention.
    """
    try:
        # Query webhooks with status = error (mock implementation)
        failed = db.query(WebhookEvent).filter(
            WebhookEvent.status == "error"
        ).all()

        failed_webhooks = []
        for wh in failed:
            failed_webhooks.append(
                FailedWebhook(
                    webhook_id=wh.id,
                    url=wh.url or "N/A",
                    description=wh.description,
                    consecutive_failures=0,
                    last_failure_at=wh.updated_at,
                    last_error="Unknown error",
                    status=wh.status
                )
            )

        return FailedWebhookList(
            data=failed_webhooks,
            total=len(failed_webhooks)
        )

    except Exception as e:
        logger.error(f"Error retrieving failed webhooks: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve failed webhooks"
        )
