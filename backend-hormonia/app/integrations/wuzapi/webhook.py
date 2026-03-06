import hashlib
import json
import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.redis_manager import get_async_redis_client
from app.core.database.async_engine import get_async_db
from app.integrations.wuzapi.extractor import (
    RECEIPT_TYPE_TO_STATUS,
    WuzAPIMessageExtractor,
)
from app.integrations.whatsapp.security.hmac_validator import WebhookHMACValidator
from app.repositories.patient import PatientRepository
from app.services.webhook.handlers.message_handler import (
    handle_opt_out,
    is_opt_out_message,
)
from app.services.webhook.idempotency import AtomicWebhookIdempotency
from app.services.webhook.utils.phone_normalizer import PhoneNormalizer
from app.utils.structured_logger import correlation_id as correlation_id_var

logger = logging.getLogger(__name__)
router = APIRouter(tags=["wuzapi-webhooks"])


def _correlation_extra(**extra: Any) -> dict[str, Any]:
    return {
        "correlation_id": correlation_id_var.get(),
        **extra,
    }


@router.post("/wuzapi")
async def wuzapi_webhook(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    correlation_id_var.set(request.headers.get("x-correlation-id") or str(uuid4()))
    raw_body = await request.body()

    secret = settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET
    if secret:
        signature = request.headers.get("x-hmac-signature", "")
        if not WebhookHMACValidator.validate_signature(raw_body, signature, secret):
            logger.warning(
                "WuzAPI webhook HMAC validation failed",
                extra=_correlation_extra(),
            )
            raise HTTPException(status_code=403, detail="Invalid HMAC signature")
    else:
        logger.warning(
            "WHATSAPP_WUZAPI_WEBHOOK_SECRET not configured; skipping HMAC",
            extra=_correlation_extra(),
        )

    try:
        payload: dict[str, Any] = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

    event_type = payload.get("type", "unknown")
    event_id = _extract_event_id(payload, raw_body)
    event_type_key = (
        f"wuzapi:{str(event_type).lower()}"
        if event_type != "unknown"
        else "wuzapi:unknown"
    )

    try:
        redis_client = await get_async_redis_client()
        idempotency = AtomicWebhookIdempotency(redis_client=redis_client)
        acquired, _reason = await idempotency.try_acquire(event_type_key, event_id)
        if not acquired:
            logger.info(
                "WuzAPI duplicate event: %s (type=%s)",
                event_id,
                event_type,
                extra=_correlation_extra(event_id=event_id, event_type=event_type),
            )
            return {
                "status": "duplicate",
                "event_id": event_id,
                "correlation_id": correlation_id_var.get(),
            }
    except Exception as exc:
        logger.error(
            "WuzAPI idempotency check failed: %s",
            exc,
            exc_info=True,
            extra=_correlation_extra(error_type=type(exc).__name__),
        )

    if event_type == "Message":
        return await _handle_message(payload, db)
    if event_type == "ReadReceipt":
        return await _handle_receipt(payload, db)

    logger.debug(
        "WuzAPI webhook: unhandled event type %r",
        event_type,
        extra=_correlation_extra(event_type=event_type),
    )
    return {
        "status": "ignored",
        "type": event_type,
        "correlation_id": correlation_id_var.get(),
    }


async def _handle_message(payload: dict[str, Any], db: AsyncSession) -> dict[str, Any]:
    """Handle WuzAPI Message event: extract, check LID, detect opt-out."""
    msg = WuzAPIMessageExtractor.extract_message(payload)
    if msg is None:
        logger.warning(
            "WuzAPI Message: could not extract message data",
            extra=_correlation_extra(),
        )
        return {
            "status": "skipped",
            "reason": "unextractable",
            "correlation_id": correlation_id_var.get(),
        }

    if msg.is_lid:
        await _route_lid_to_dlq(payload, msg)
        return {
            "status": "queued_for_review",
            "reason": "lid_sender",
            "message_id": msg.message_id,
            "correlation_id": correlation_id_var.get(),
        }

    if is_opt_out_message(msg.text):
        await _process_opt_out(msg.phone, db)
        return {
            "status": "opt_out_processed",
            "message_id": msg.message_id,
            "phone": msg.phone,
            "correlation_id": correlation_id_var.get(),
        }

    logger.info(
        "WuzAPI inbound message from %s: id=%s",
        msg.phone,
        msg.message_id,
        extra=_correlation_extra(phone=msg.phone, message_id=msg.message_id),
    )
    return {
        "status": "processed",
        "message_id": msg.message_id,
        "correlation_id": correlation_id_var.get(),
    }


async def _handle_receipt(payload: dict[str, Any], db: AsyncSession) -> dict[str, Any]:
    """Handle WuzAPI ReadReceipt event: extract and map to internal status."""
    _ = db
    receipt = WuzAPIMessageExtractor.extract_receipt(payload)
    if receipt is None:
        logger.warning(
            "WuzAPI Receipt: could not extract receipt data",
            extra=_correlation_extra(),
        )
        return {
            "status": "skipped",
            "reason": "unextractable",
            "correlation_id": correlation_id_var.get(),
        }

    internal_status = RECEIPT_TYPE_TO_STATUS.get(receipt.receipt_type)
    if internal_status is None:
        logger.warning(
            "WuzAPI Receipt: unknown receipt type %r",
            receipt.receipt_type,
            extra=_correlation_extra(receipt_type=receipt.receipt_type),
        )
        return {
            "status": "skipped",
            "reason": "unknown_receipt_type",
            "receipt_type": receipt.receipt_type,
            "correlation_id": correlation_id_var.get(),
        }

    logger.info(
        "WuzAPI receipt: status=%s for messages=%s from=%s",
        internal_status,
        receipt.message_ids,
        receipt.sender_phone,
        extra=_correlation_extra(
            internal_status=internal_status,
            sender_phone=receipt.sender_phone,
        ),
    )
    return {
        "status": "processed",
        "internal_status": internal_status,
        "message_ids": receipt.message_ids,
        "correlation_id": correlation_id_var.get(),
    }


async def _route_lid_to_dlq(payload: dict[str, Any], msg: Any) -> None:
    """Route LID sender event to DLQ for manual review."""
    try:
        from app.services.webhook_dlq import WebhookDLQ

        redis_client = await get_async_redis_client()
        dlq = WebhookDLQ(db=None, redis=redis_client)
        await dlq.send_to_dlq(
            event_id=uuid4(),
            event_type="wuzapi:lid_sender",
            event_data=payload,
            error=f"LID sender detected: phone={msg.phone}, message_id={msg.message_id}",
        )
        logger.info(
            "WuzAPI LID sender routed to DLQ: phone=%s id=%s",
            msg.phone,
            msg.message_id,
            extra=_correlation_extra(phone=msg.phone, message_id=msg.message_id),
        )
    except Exception as exc:
        logger.error(
            "Failed to route LID sender to DLQ: %s",
            exc,
            exc_info=True,
            extra=_correlation_extra(error_type=type(exc).__name__),
        )


async def _process_opt_out(phone: str, db: AsyncSession) -> None:
    """Process opt-out for a patient identified via phone hash lookup."""
    try:
        patient_repo = PatientRepository(db)
        normalizer = PhoneNormalizer(patient_repo)
        patient = normalizer.find_patient_by_phone(phone)

        if patient:
            await handle_opt_out(patient, db)
            logger.info(
                "WuzAPI opt-out processed for patient id=%s",
                patient.id,
                extra=_correlation_extra(patient_id=str(patient.id)),
            )
        else:
            logger.warning(
                "WuzAPI opt-out: no patient found for phone (hash lookup)",
                extra=_correlation_extra(phone=phone),
            )
    except Exception as exc:
        logger.error(
            "WuzAPI opt-out processing failed: %s",
            exc,
            exc_info=True,
            extra=_correlation_extra(error_type=type(exc).__name__),
        )
        try:
            await db.rollback()
        except Exception:
            pass


def _extract_event_id(payload: dict[str, Any], raw_body: bytes) -> str:
    """Extract event ID from payload, fallback to body hash."""
    event = payload.get("event") or payload
    info = event.get("Info") or {}
    event_id = info.get("ID") or ""
    if not event_id:
        event_id = hashlib.sha256(raw_body).hexdigest()
        logger.warning(
            "WuzAPI event missing ID, using body hash: %s",
            event_id,
            extra=_correlation_extra(event_id=event_id),
        )
    return event_id
