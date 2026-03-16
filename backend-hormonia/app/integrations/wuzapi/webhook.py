import hashlib
import json
import logging
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.core.redis_manager import get_async_redis_client
from app.core.database.async_engine import get_async_db
from app.integrations.wuzapi.extractor import (
    RECEIPT_TYPE_TO_STATUS,
    WuzAPIMessageExtractor,
    WuzAPIInboundMessage,
)
from app.integrations.whatsapp.security.hmac_validator import WebhookHMACValidator
from app.models.flow import PatientFlowState
from app.models.message import Message, MessageType, MessageStatus, MessageDirection
from app.models.patient import Patient
from app.models.patient_flow_response import PatientFlowResponse
from app.repositories.patient import PatientRepository
from app.repositories.flow import FlowStateRepository
from app.services.webhook.handlers.message_handler import (
    handle_opt_out,
    is_opt_out_message,
)
from app.services.webhook.idempotency import AtomicWebhookIdempotency
from app.services.webhook.utils.phone_normalizer import PhoneNormalizer
from app.utils.structured_logger import correlation_id as correlation_id_var
from app.utils.timezone import now_sao_paulo

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
    """Handle WuzAPI Message event: extract, find patient, process through flow engine.

    Full processing pipeline:
    1. Extract message data from WuzAPI payload
    2. Route LID senders to DLQ
    3. Detect opt-out keywords (LGPD Art. 18)
    4. Find patient by phone (sync via run_sync bridge)
    5. Create inbound message record
    6. If active flow: persist response to patient_flow_responses (dual-write)
    7. Trigger sequential continuation for flow progression
    """
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

    # Skip outgoing messages echoed back by WuzAPI
    if msg.is_from_me:
        logger.debug(
            "WuzAPI Message: skipping own message id=%s",
            msg.message_id,
            extra=_correlation_extra(message_id=msg.message_id),
        )
        return {
            "status": "skipped",
            "reason": "from_me",
            "message_id": msg.message_id,
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
        "WuzAPI inbound message from %s: id=%s text_len=%d",
        msg.phone,
        msg.message_id,
        len(msg.text or ""),
        extra=_correlation_extra(phone=msg.phone, message_id=msg.message_id),
    )

    # --- Full response processing pipeline ---
    try:
        result = await _process_patient_message(msg, payload, db)
        return result
    except Exception as exc:
        logger.error(
            "WuzAPI message processing failed: %s",
            exc,
            exc_info=True,
            extra=_correlation_extra(
                phone=msg.phone,
                message_id=msg.message_id,
                error_type=type(exc).__name__,
            ),
        )
        return {
            "status": "error",
            "message_id": msg.message_id,
            "error": str(exc),
            "correlation_id": correlation_id_var.get(),
        }


async def _process_patient_message(
    msg: WuzAPIInboundMessage,
    payload: dict[str, Any],
    db: AsyncSession,
) -> dict[str, Any]:
    """Process an inbound patient message through the flow engine.

    Uses db.run_sync() bridge for sync repository operations (patient lookup,
    flow state query, message creation) since repositories use db.query().
    """
    # Step 1: Find patient by phone (sync repos need run_sync bridge)
    def _find_patient(sync_session):
        patient_repo = PatientRepository(sync_session)
        normalizer = PhoneNormalizer(patient_repo)
        return normalizer.find_patient_by_phone(msg.phone)

    patient: Optional[Patient] = await db.run_sync(_find_patient)
    if patient is None:
        logger.warning(
            "WuzAPI message: patient not found for phone",
            extra=_correlation_extra(phone=msg.phone, message_id=msg.message_id),
        )
        return {
            "status": "skipped",
            "reason": "patient_not_found",
            "message_id": msg.message_id,
            "correlation_id": correlation_id_var.get(),
        }

    patient_id: UUID = patient.id

    # Step 2: Check for active flow (sync repo)
    def _get_active_flow(sync_session):
        flow_repo = FlowStateRepository(sync_session)
        return flow_repo.get_active_flow(patient_id)

    active_flow: Optional[PatientFlowState] = await db.run_sync(_get_active_flow)

    # Step 3: Build metadata with flow context
    metadata: dict[str, Any] = {
        "source": "wuzapi",
        "push_name": msg.push_name,
        "wuzapi_message_id": msg.message_id,
    }
    if active_flow:
        step_data = active_flow.step_data or {}
        metadata["context"] = "flow"
        metadata["flow_state_id"] = str(active_flow.id)
        metadata["current_step"] = active_flow.current_step
        metadata["flow_kind"] = step_data.get("flow_kind") or active_flow.flow_type
        metadata["flow_day"] = step_data.get("current_flow_day")
        metadata["message_index"] = step_data.get("current_day_message_index")
        metadata["awaiting_response"] = step_data.get("awaiting_response")
    else:
        metadata["context"] = "general_chat"

    # Step 4: Create inbound message record (sync service)
    def _create_inbound_message(sync_session):
        from app.domain.messaging.core import MessageService

        message_service = MessageService(sync_session)
        return message_service.process_inbound_message(
            patient_id=patient_id,
            content=msg.text,
            whatsapp_id=msg.message_id,
            message_type=MessageType.TEXT,
            message_metadata=metadata,
        )

    inbound_message: Message = await db.run_sync(_create_inbound_message)
    logger.info(
        "WuzAPI: created inbound message %s for patient %s",
        inbound_message.id,
        patient_id,
        extra=_correlation_extra(
            message_id=str(inbound_message.id),
            patient_id=str(patient_id),
            context=metadata["context"],
        ),
    )

    # Step 5: If active flow, persist response and trigger continuation
    if active_flow:
        await _process_flow_response(
            db=db,
            patient_id=patient_id,
            message=inbound_message,
            flow_state=active_flow,
            response_text=msg.text,
        )
    else:
        logger.info(
            "WuzAPI: no active flow for patient %s, message stored as general_chat",
            patient_id,
            extra=_correlation_extra(patient_id=str(patient_id)),
        )

    return {
        "status": "processed",
        "message_id": msg.message_id,
        "internal_message_id": str(inbound_message.id),
        "patient_id": str(patient_id),
        "context": metadata["context"],
        "correlation_id": correlation_id_var.get(),
    }


async def _process_flow_response(
    *,
    db: AsyncSession,
    patient_id: UUID,
    message: Message,
    flow_state: PatientFlowState,
    response_text: str,
) -> None:
    """Persist patient response to patient_flow_responses and step_data (dual-write).

    Then triggers sequential continuation so the flow can advance.
    """
    step_data = flow_state.step_data or {}
    day_number = step_data.get("current_flow_day")
    message_index = step_data.get("current_day_message_index")
    flow_kind = step_data.get("flow_kind") or flow_state.flow_type
    prompt_message_id = step_data.get("pending_response_context", {}).get("prompt_message_id") if isinstance(step_data.get("pending_response_context"), dict) else None

    # Dual-write 1: Persist to patient_flow_responses table
    def _persist_flow_response(sync_session):
        flow_response = PatientFlowResponse(
            flow_state_id=flow_state.id,
            patient_id=patient_id,
            day_number=day_number,
            message_index=message_index,
            response_text=response_text,
            responded_at=now_sao_paulo(),
            prompt_message_id=str(prompt_message_id) if prompt_message_id else None,
            response_message_id=str(message.id),
        )
        sync_session.add(flow_response)
        sync_session.flush()

        # Dual-write 2: Update step_data with response info
        current_step_data = dict(flow_state.step_data or {})
        current_step_data.setdefault("responses_by_message", {})
        response_key = (
            f"day_{day_number}_msg_{message_index}"
            if day_number is not None and message_index is not None
            else f"day_{day_number}" if day_number is not None
            else "latest"
        )
        current_step_data["responses_by_message"][response_key] = {
            "response_text": response_text,
            "response_message_id": str(message.id),
            "prompt_message_id": str(prompt_message_id) if prompt_message_id else None,
            "timestamp": now_sao_paulo().isoformat(),
            "flow_day": day_number,
            "flow_kind": flow_kind,
            "message_index": message_index,
        }
        current_step_data["last_response"] = {
            "response_message_id": str(message.id),
            "timestamp": now_sao_paulo().isoformat(),
            "text_length": len(response_text),
        }
        flow_state.step_data = current_step_data
        flag_modified(flow_state, "step_data")
        sync_session.commit()
        return flow_response

    flow_response = await db.run_sync(_persist_flow_response)

    logger.info(
        "WuzAPI: persisted flow response for patient %s (day=%s, msg_idx=%s)",
        patient_id,
        day_number,
        message_index,
        extra=_correlation_extra(
            patient_id=str(patient_id),
            flow_response_id=str(flow_response.id),
            day_number=day_number,
            message_index=message_index,
        ),
    )

    # Step 6: Trigger sequential continuation (async flow engine)
    response_context = {
        "flow_day": day_number,
        "flow_kind": flow_kind,
        "message_index": message_index,
        "awaiting_response": step_data.get("awaiting_response"),
        "prompt_message_id": str(prompt_message_id) if prompt_message_id else None,
        "response_message_id": str(message.id),
    }
    response_context = {k: v for k, v in response_context.items() if v is not None}

    try:
        from app.services.flow.sequential_message_handler import SequentialMessageHandler

        def _create_handler(sync_session):
            return SequentialMessageHandler(sync_session)

        handler = await db.run_sync(_create_handler)
        continuation_result = await handler.handle_response_and_continue(
            patient_id=patient_id,
            response_context=response_context,
        )
        status = continuation_result.get("status") if isinstance(continuation_result, dict) else None
        logger.info(
            "WuzAPI: sequential continuation result for patient %s: status=%s",
            patient_id,
            status,
            extra=_correlation_extra(
                patient_id=str(patient_id),
                continuation_status=status,
            ),
        )
    except Exception as exc:
        logger.error(
            "WuzAPI: sequential continuation failed for patient %s: %s",
            patient_id,
            exc,
            exc_info=True,
            extra=_correlation_extra(
                patient_id=str(patient_id),
                error_type=type(exc).__name__,
            ),
        )


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
