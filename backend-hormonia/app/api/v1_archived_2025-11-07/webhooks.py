"""
Webhook endpoints for external integrations (Evolution API).
"""
import logging
from typing import Any

from fastapi import APIRouter, Request, HTTPException, Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.webhook_processor import WebhookProcessor
from app.integrations.evolution import get_evolution_client
from app.config import settings


logger = logging.getLogger(__name__)
router = APIRouter()


async def validate_webhook_signature(
    request: Request,
    x_signature: str = Header(None, alias="x-signature")
) -> bool:
    """
    Validate webhook signature for security.

    P0 FIX: Enforces signature validation in production environment.
    """
    if not settings.EVOLUTION_WEBHOOK_SECRET:
        logger.warning("Webhook signature validation skipped - no secret configured")
        # P0 FIX: Reject webhooks in production without proper configuration
        if getattr(settings, 'ENVIRONMENT', 'development') == 'production':
            logger.error("Webhook secret required in production environment")
            return False
        return True  # Allow in development

    if not x_signature:
        logger.warning("No signature header found in webhook request")
        # P0 FIX: In production, require signature header
        if getattr(settings, 'ENVIRONMENT', 'development') == 'production':
            logger.error("Signature header required in production")
            return False
        return True  # Allow in development for testing

    try:
        body = await request.body()
        evolution_client = await get_evolution_client()

        is_valid = evolution_client.validate_webhook_signature(
            payload=body,
            signature=x_signature,
            secret=settings.EVOLUTION_WEBHOOK_SECRET
        )

        if not is_valid:
            logger.warning("Invalid webhook signature")

        return is_valid

    except Exception as e:
        logger.error(f"Error validating webhook signature: {e}")
        return False


@router.post("/evolution/message", response_model=None)
async def evolution_message_webhook(
    request: Request,
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Receive incoming message from Evolution API."""
    try:
        # Validate signature
        if not await validate_webhook_signature(request):
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse request body
        event_data = await request.json()
        logger.info(f"Received message webhook: {event_data}")
        
        # Process the webhook
        webhook_processor = WebhookProcessor(db)
        message_id = await webhook_processor.process_message_webhook(event_data)
        
        if message_id:
            return {
                "status": "success",
                "message": "Message processed successfully",
                "message_id": message_id
            }
        else:
            return {
                "status": "ignored",
                "message": "Message ignored (patient not found or invalid data)"
            }
            
    except Exception as e:
        logger.error(f"Error processing message webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/evolution/status", response_model=None)
async def evolution_status_webhook(
    request: Request,
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Receive message status update from Evolution API."""
    try:
        # Validate signature
        if not await validate_webhook_signature(request):
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse request body
        event_data = await request.json()
        logger.info(f"Received status webhook: {event_data}")
        
        # Process the webhook
        webhook_processor = WebhookProcessor(db)
        success = await webhook_processor.process_status_webhook(event_data)
        
        if success:
            return {
                "status": "success",
                "message": "Status update processed successfully"
            }
        else:
            return {
                "status": "ignored",
                "message": "Status update ignored (message not found or invalid data)"
            }
            
    except Exception as e:
        logger.error(f"Error processing status webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/evolution/connection", response_model=None)
async def evolution_connection_webhook(
    request: Request,
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Receive connection status from Evolution API."""
    try:
        # Validate signature
        if not await validate_webhook_signature(request):
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse request body
        event_data = await request.json()
        logger.info(f"Received connection webhook: {event_data}")
        
        # Process the webhook
        webhook_processor = WebhookProcessor(db)
        success = await webhook_processor.process_connection_webhook(event_data)
        
        if success:
            return {
                "status": "success",
                "message": "Connection status processed successfully"
            }
        else:
            return {
                "status": "error",
                "message": "Failed to process connection status"
            }
            
    except Exception as e:
        logger.error(f"Error processing connection webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/evolution/qrcode", response_model=None)
async def evolution_qrcode_webhook(
    request: Request,
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """
    Receive QR code update from Evolution API.

    P0 FIX #5: Handles qrcode.updated events for WhatsApp instance initialization.
    """
    try:
        # Validate signature
        if not await validate_webhook_signature(request):
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Parse request body
        event_data = await request.json()
        logger.info(f"Received QR code webhook: {event_data}")

        # Process the webhook
        webhook_processor = WebhookProcessor(db)
        success = await webhook_processor.process_qrcode_webhook(event_data)

        if success:
            return {
                "status": "success",
                "message": "QR code processed successfully"
            }
        else:
            return {
                "status": "error",
                "message": "Failed to process QR code"
            }

    except Exception as e:
        logger.error(f"Error processing QR code webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/evolution/health", response_model=None)
async def evolution_health_check() -> dict[str, Any]:
    """Health check endpoint for Evolution API integration."""
    try:
        evolution_client = await get_evolution_client()
        status = await evolution_client.get_instance_status()

        return {
            "status": "healthy",
            "evolution_api": "connected",
            "instance_status": status
        }

    except Exception as e:
        logger.error(f"Evolution API health check failed: {e}")
        return {
            "status": "unhealthy",
            "evolution_api": "disconnected",
            "error": str(e)
        }