"""
Webhook endpoints for external integrations (Evolution API) with HMAC authentication.
SECURITY FIX: Enforces mandatory HMAC-SHA256 signature verification on all webhook endpoints.
"""

import logging
import hmac
import hashlib
import time
from typing import Any, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.services.webhook_processor import WebhookProcessor
from app.integrations.evolution import get_evolution_client
from app.config import settings
from app.models.webhook_event import WebhookEvent


logger = logging.getLogger(__name__)
router = APIRouter()

# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================
# Maximum age for webhook timestamps (5 minutes = 300 seconds)
# Webhooks older than this are rejected to prevent replay attacks
MAX_TIMESTAMP_AGE_SECONDS = 300

# Idempotency window (24 hours)
# Duplicate webhooks within this window are detected and skipped
IDEMPOTENCY_WINDOW_HOURS = 24


async def verify_webhook_signature(
    request: Request,
    x_webhook_signature: str = Header(..., alias="X-Webhook-Signature"),
    x_webhook_timestamp: Optional[str] = Header(None, alias="X-Webhook-Timestamp"),
    x_webhook_id: Optional[str] = Header(None, alias="X-Webhook-Id"),
) -> dict[str, Any]:
    """
    Verify Evolution API webhook signature using HMAC-SHA256 with timestamp validation.

    CRITICAL SECURITY ENHANCEMENTS:
    1. HMAC-SHA256 signature verification (prevents tampering)
    2. Timestamp validation (prevents replay attacks)
    3. Idempotency ID extraction (enables duplicate prevention)

    This function enforces mandatory signature verification.
    Requests without valid signatures are rejected with 401 Unauthorized.

    Args:
        request: FastAPI request object containing the payload
        x_webhook_signature: HMAC signature from webhook header
        x_webhook_timestamp: Unix timestamp when webhook was sent (optional but recommended)
        x_webhook_id: Unique webhook ID for idempotency (optional but recommended)

    Returns:
        dict: Verification metadata including webhook_id and timestamp

    Raises:
        HTTPException: 401 if secret not configured, signature invalid, or timestamp expired
    """
    # CRITICAL: Reject requests if webhook secret not configured
    if not settings.EVOLUTION_WEBHOOK_SECRET:
        logger.error("SECURITY: Webhook secret not configured - rejecting request")
        raise HTTPException(
            status_code=401, detail="Webhook authentication not configured"
        )

    try:
        # Get raw request body for signature verification
        payload = await request.body()

        # SECURITY CHECK 1: Timestamp validation (prevent replay attacks)
        if x_webhook_timestamp:
            try:
                webhook_time = int(x_webhook_timestamp)
                current_time = int(time.time())
                time_diff = abs(current_time - webhook_time)

                if time_diff > MAX_TIMESTAMP_AGE_SECONDS:
                    logger.warning(
                        f"SECURITY: Webhook timestamp too old. "
                        f"Age: {time_diff}s (max: {MAX_TIMESTAMP_AGE_SECONDS}s)"
                    )
                    raise HTTPException(
                        status_code=401,
                        detail=f"Webhook timestamp expired (max age: {MAX_TIMESTAMP_AGE_SECONDS}s)",
                    )

                logger.debug(f"Webhook timestamp validated (age: {time_diff}s)")
            except ValueError:
                logger.warning(
                    f"SECURITY: Invalid timestamp format: {x_webhook_timestamp}"
                )
                raise HTTPException(
                    status_code=401, detail="Invalid webhook timestamp format"
                )
        else:
            logger.warning(
                "SECURITY: Webhook timestamp not provided. "
                "Replay attack protection disabled for this request."
            )

        # SECURITY CHECK 2: HMAC signature verification (prevent tampering)
        # Include timestamp in signature if provided (stronger security)
        if x_webhook_timestamp:
            signature_payload = f"{x_webhook_timestamp}.{payload.decode('utf-8')}"
            signature_bytes = signature_payload.encode("utf-8")
        else:
            signature_bytes = payload

        expected_signature = hmac.new(
            settings.EVOLUTION_WEBHOOK_SECRET.encode("utf-8"),
            signature_bytes,
            hashlib.sha256,
        ).hexdigest()

        # Use constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(x_webhook_signature, expected_signature):
            logger.warning(
                f"SECURITY: Invalid webhook signature received. "
                f"Expected: {expected_signature[:8]}... Got: {x_webhook_signature[:8]}..."
            )
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

        logger.debug("Webhook signature verified successfully")

        # Return verification metadata for idempotency tracking
        return {
            "verified": True,
            "webhook_id": x_webhook_id,
            "timestamp": x_webhook_timestamp,
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error validating webhook signature: {e}", exc_info=True)
        raise HTTPException(
            status_code=401, detail="Webhook signature verification failed"
        )


async def check_webhook_idempotency(
    webhook_id: Optional[str], event_type: str, db: Session
) -> bool:
    """
    Check if webhook has already been processed (idempotency).

    CRITICAL FIX #5: Prevent duplicate webhook processing.

    Args:
        webhook_id: Unique webhook identifier
        event_type: Type of webhook event
        db: Database session

    Returns:
        bool: True if webhook is new (should process), False if duplicate (should skip)
    """
    if not webhook_id:
        # No webhook ID provided, cannot check idempotency
        logger.warning(
            f"Webhook ID not provided for {event_type}. "
            "Duplicate processing prevention disabled."
        )
        return True  # Process anyway

    try:
        # Check if webhook ID already exists in last 24 hours
        cutoff_time = datetime.utcnow() - timedelta(hours=IDEMPOTENCY_WINDOW_HOURS)

        existing = db.execute(
            select(WebhookEvent).where(
                WebhookEvent.webhook_id == webhook_id,
                WebhookEvent.created_at >= cutoff_time,
            )
        ).first()

        if existing:
            logger.warning(
                f"IDEMPOTENCY: Duplicate webhook detected: {webhook_id} ({event_type})"
            )
            return False  # Skip processing (duplicate)

        logger.debug(f"Webhook ID {webhook_id} is new (will process)")
        return True  # Process (new webhook)

    except Exception as e:
        logger.error(f"Error checking webhook idempotency: {e}", exc_info=True)
        # On error, allow processing (fail open for availability)
        return True


@router.post("/evolution/message", response_model=None)
async def evolution_message_webhook(
    request: Request,
    db: Session = Depends(get_db),
    verification: dict = Depends(verify_webhook_signature),
) -> dict[str, Any]:
    """
    Receive incoming message from Evolution API.

    SECURITY ENHANCEMENTS:
    - HMAC signature verification (prevents tampering)
    - Timestamp validation (prevents replay attacks)
    - Idempotency checking (prevents duplicate processing)
    """
    try:
        # Parse request body
        event_data = await request.json()
        event_type = event_data.get("event", "unknown")

        logger.info(f"Received message webhook: {event_type}")

        # CRITICAL FIX #5: Check idempotency (prevent duplicate processing)
        webhook_id = verification.get("webhook_id")
        is_new = await check_webhook_idempotency(webhook_id, event_type, db)

        if not is_new:
            return {
                "status": "duplicate",
                "message": "Webhook already processed (idempotency)",
                "webhook_id": webhook_id,
            }

        # Process the webhook
        webhook_processor = WebhookProcessor(db)
        message_id = await webhook_processor.process_message_webhook(
            event_data, webhook_id=webhook_id
        )

        if message_id:
            return {
                "status": "success",
                "message": "Message processed successfully",
                "message_id": message_id,
                "webhook_id": webhook_id,
            }
        else:
            return {
                "status": "ignored",
                "message": "Message ignored (patient not found or invalid data)",
                "webhook_id": webhook_id,
            }

    except Exception as e:
        logger.error(f"Error processing message webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/evolution/status", response_model=None)
async def evolution_status_webhook(
    request: Request,
    db: Session = Depends(get_db),
    verification: dict = Depends(verify_webhook_signature),
) -> dict[str, Any]:
    """
    Receive message status update from Evolution API.

    SECURITY ENHANCEMENTS:
    - HMAC signature verification (prevents tampering)
    - Timestamp validation (prevents replay attacks)
    - Idempotency checking (prevents duplicate processing)
    """
    try:
        # Parse request body
        event_data = await request.json()
        event_type = event_data.get("event", "unknown")

        logger.info(f"Received status webhook: {event_type}")

        # CRITICAL FIX #5: Check idempotency
        webhook_id = verification.get("webhook_id")
        is_new = await check_webhook_idempotency(webhook_id, event_type, db)

        if not is_new:
            return {
                "status": "duplicate",
                "message": "Webhook already processed (idempotency)",
                "webhook_id": webhook_id,
            }

        # Process the webhook
        webhook_processor = WebhookProcessor(db)
        success = await webhook_processor.process_status_webhook(
            event_data, webhook_id=webhook_id
        )

        if success:
            return {
                "status": "success",
                "message": "Status update processed successfully",
                "webhook_id": webhook_id,
            }
        else:
            return {
                "status": "ignored",
                "message": "Status update ignored (message not found or invalid data)",
                "webhook_id": webhook_id,
            }

    except Exception as e:
        logger.error(f"Error processing status webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/evolution/connection", response_model=None)
async def evolution_connection_webhook(
    request: Request,
    db: Session = Depends(get_db),
    verification: dict = Depends(verify_webhook_signature),
) -> dict[str, Any]:
    """
    Receive connection status from Evolution API.

    SECURITY ENHANCEMENTS:
    - HMAC signature verification (prevents tampering)
    - Timestamp validation (prevents replay attacks)
    - Idempotency checking (prevents duplicate processing)
    """
    try:
        # Parse request body
        event_data = await request.json()
        event_type = event_data.get("event", "unknown")

        logger.info(f"Received connection webhook: {event_type}")

        # CRITICAL FIX #5: Check idempotency
        webhook_id = verification.get("webhook_id")
        is_new = await check_webhook_idempotency(webhook_id, event_type, db)

        if not is_new:
            return {
                "status": "duplicate",
                "message": "Webhook already processed (idempotency)",
                "webhook_id": webhook_id,
            }

        # Process the webhook
        webhook_processor = WebhookProcessor(db)
        success = await webhook_processor.process_connection_webhook(
            event_data, webhook_id=webhook_id
        )

        if success:
            return {
                "status": "success",
                "message": "Connection status processed successfully",
                "webhook_id": webhook_id,
            }
        else:
            return {
                "status": "error",
                "message": "Failed to process connection status",
                "webhook_id": webhook_id,
            }

    except Exception as e:
        logger.error(f"Error processing connection webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/evolution/health", response_model=None)
async def evolution_health_check() -> dict[str, Any]:
    """
    Health check endpoint for Evolution API integration.

    NOTE: Health check endpoint does not require signature verification.
    """
    try:
        evolution_client = await get_evolution_client()
        status = await evolution_client.get_instance_status()

        return {
            "status": "healthy",
            "evolution_api": "connected",
            "instance_status": status,
        }

    except Exception as e:
        logger.error(f"Evolution API health check failed: {e}")
        return {"status": "unhealthy", "evolution_api": "disconnected", "error": str(e)}
