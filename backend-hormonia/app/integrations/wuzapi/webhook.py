import hashlib
import json
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.async_engine import get_async_db
from app.integrations.whatsapp.security.hmac_validator import WebhookHMACValidator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["wuzapi-webhooks"])


@router.post("/wuzapi")
async def wuzapi_webhook(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    raw_body = await request.body()

    secret = os.environ.get("WHATSAPP_WUZAPI_WEBHOOK_SECRET")
    if secret:
        signature = request.headers.get("x-hmac-signature", "")
        if not WebhookHMACValidator.validate_signature(raw_body, signature, secret):
            logger.warning("WuzAPI webhook HMAC validation failed")
            raise HTTPException(status_code=403, detail="Invalid HMAC signature")
    else:
        logger.warning("WHATSAPP_WUZAPI_WEBHOOK_SECRET not configured; skipping HMAC")

    try:
        payload: dict[str, Any] = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

    event_type = payload.get("type", "unknown")

    if event_type == "Message":
        return await _handle_message(payload, db)
    if event_type == "ReadReceipt":
        return await _handle_receipt(payload, db)

    logger.debug("WuzAPI webhook: unhandled event type %r", event_type)
    return {"status": "ignored", "type": event_type}


async def _handle_message(payload: dict[str, Any], db: AsyncSession) -> dict[str, Any]:
    """Stub handler for Message events. Wired in plan 34-03."""
    _ = db
    event = payload.get("event") or payload
    info = event.get("Info") or {}
    message_id = info.get("ID", "")
    logger.info("WuzAPI Message received: %s", message_id)
    return {"status": "received", "message_id": message_id, "type": "Message"}


async def _handle_receipt(payload: dict[str, Any], db: AsyncSession) -> dict[str, Any]:
    """Stub handler for ReadReceipt events. Wired in plan 34-03."""
    _ = db
    event = payload.get("event") or payload
    info = event.get("Info") or {}
    receipt = event.get("Receipt") or {}
    message_id = info.get("ID", "")
    receipt_type = receipt.get("Type", "")
    logger.info("WuzAPI Receipt received: %s (type=%s)", message_id, receipt_type)
    return {
        "status": "received",
        "message_id": message_id,
        "type": "ReadReceipt",
        "receipt_type": receipt_type,
    }


def _extract_event_id(payload: dict[str, Any], raw_body: bytes) -> str:
    """Extract event ID from payload, fallback to body hash."""
    event = payload.get("event") or payload
    info = event.get("Info") or {}
    event_id = info.get("ID") or ""
    if not event_id:
        event_id = hashlib.sha256(raw_body).hexdigest()[:32]
        logger.warning("WuzAPI event missing ID, using body hash: %s", event_id)
    return event_id
