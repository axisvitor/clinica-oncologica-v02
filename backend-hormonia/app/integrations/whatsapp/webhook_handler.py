"""
WhatsApp Webhook Handler with Idempotency

Handles WhatsApp webhooks with automatic duplicate detection and prevention.
Integrates with IdempotencyMiddleware for reliable webhook processing.
"""

import logging
from fastapi import APIRouter, Request, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.integrations.whatsapp.api.webhooks import evolution_webhook

logger = logging.getLogger(__name__)

# Create router with idempotency middleware
router = APIRouter(prefix="/api/v2/webhooks/whatsapp", tags=["WhatsApp Webhooks"])


@router.post("/evolution/{instance_name}")
async def whatsapp_webhook_with_idempotency(
    instance_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Handle Evolution API webhooks with idempotency protection.

    This endpoint automatically prevents duplicate webhook processing by:
    1. Extracting event IDs from webhook payloads
    2. Checking if the event has been processed before
    3. Returning cached responses for duplicates
    4. Processing new events normally

    Args:
        instance_name: WhatsApp instance name
        request: HTTP request with webhook payload
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Processing result or cached response for duplicates
    """
    # The IdempotencyMiddleware will handle duplicate detection
    # This endpoint just needs to process the webhook normally
    return await evolution_webhook(
        instance_name=instance_name,
        request=request,
        background_tasks=background_tasks,
        db=db,
    )


@router.get("/idempotency/stats")
async def get_idempotency_stats(db: Session = Depends(get_db)):
    """
    Get idempotency statistics for monitoring.

    Returns:
        Statistics about webhook processing and duplicates
    """
    from app.services.idempotency_cleanup import get_cleanup_service

    cleanup_service = get_cleanup_service()
    stats = await cleanup_service.get_cleanup_stats(db)

    return {"status": "success", "data": stats}


@router.post("/idempotency/cleanup")
async def trigger_cleanup(db: Session = Depends(get_db)):
    """
    Manually trigger cleanup of expired idempotency records.

    This is normally run by a scheduled job, but can be triggered manually
    for maintenance or debugging.

    Returns:
        Cleanup results
    """
    from app.services.idempotency_cleanup import get_cleanup_service

    cleanup_service = get_cleanup_service()
    result = await cleanup_service.run_cleanup(db)

    return {"status": "success", "data": result}
