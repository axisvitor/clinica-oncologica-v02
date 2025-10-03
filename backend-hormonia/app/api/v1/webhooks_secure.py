"""
Webhook endpoints for external integrations (Evolution API) with HMAC authentication.
SECURITY FIX: Enforces mandatory HMAC-SHA256 signature verification on all webhook endpoints.
"""
import logging
import hmac
import hashlib
from typing import Any

from fastapi import APIRouter, Request, HTTPException, Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.webhook_processor import WebhookProcessor
from app.integrations.evolution import get_evolution_client
from app.config import settings


logger = logging.getLogger(__name__)
router = APIRouter()


async def verify_webhook_signature(
    request: Request,
    x_webhook_signature: str = Header(..., alias="X-Webhook-Signature")
) -> bool:
    """
    Verify Evolution API webhook signature using HMAC-SHA256.
    
    SECURITY: This function enforces mandatory signature verification.
    Requests without valid signatures are rejected with 401 Unauthorized.
    
    Args:
        request: FastAPI request object containing the payload
        x_webhook_signature: HMAC signature from webhook header
        
    Returns:
        bool: True if signature is valid
        
    Raises:
        HTTPException: 401 if secret not configured or signature invalid
    """
    # CRITICAL: Reject requests if webhook secret not configured
    if not settings.EVOLUTION_WEBHOOK_SECRET:
        logger.error("SECURITY: Webhook secret not configured - rejecting request")
        raise HTTPException(
            status_code=401,
            detail="Webhook authentication not configured"
        )
    
    try:
        # Get raw request body for signature verification
        payload = await request.body()
        
        # Compute expected HMAC signature
        expected_signature = hmac.new(
            settings.EVOLUTION_WEBHOOK_SECRET.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Use constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(x_webhook_signature, expected_signature):
            logger.warning(
                f"SECURITY: Invalid webhook signature received. "
                f"Expected: {expected_signature[:8]}... Got: {x_webhook_signature[:8]}..."
            )
            raise HTTPException(
                status_code=401,
                detail="Invalid webhook signature"
            )
        
        logger.debug("Webhook signature verified successfully")
        return True
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error validating webhook signature: {e}", exc_info=True)
        raise HTTPException(
            status_code=401,
            detail="Webhook signature verification failed"
        )


@router.post("/evolution/message", response_model=None, dependencies=[Depends(verify_webhook_signature)])
async def evolution_message_webhook(
    request: Request,
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """
    Receive incoming message from Evolution API.
    
    SECURITY: Protected by HMAC signature verification dependency.
    """
    try:
        # Parse request body
        event_data = await request.json()
        logger.info(f"Received message webhook: {event_data.get('event', 'unknown')}")
        
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


@router.post("/evolution/status", response_model=None, dependencies=[Depends(verify_webhook_signature)])
async def evolution_status_webhook(
    request: Request,
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """
    Receive message status update from Evolution API.
    
    SECURITY: Protected by HMAC signature verification dependency.
    """
    try:
        # Parse request body
        event_data = await request.json()
        logger.info(f"Received status webhook: {event_data.get('event', 'unknown')}")
        
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


@router.post("/evolution/connection", response_model=None, dependencies=[Depends(verify_webhook_signature)])
async def evolution_connection_webhook(
    request: Request,
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """
    Receive connection status from Evolution API.
    
    SECURITY: Protected by HMAC signature verification dependency.
    """
    try:
        # Parse request body
        event_data = await request.json()
        logger.info(f"Received connection webhook: {event_data.get('event', 'unknown')}")
        
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
            "instance_status": status
        }
        
    except Exception as e:
        logger.error(f"Evolution API health check failed: {e}")
        return {
            "status": "unhealthy",
            "evolution_api": "disconnected",
            "error": str(e)
        }
