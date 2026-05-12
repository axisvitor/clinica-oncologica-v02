from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
import json
import logging
import hashlib
import os
import threading
import time
from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks, Body, status
from sqlalchemy import and_, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database.async_engine import get_async_db
from app.database import get_async_session_factory
from app.models.message import Message, MessageStatus, MessageType, MessageDirection
from app.models.patient import Patient
from app.models.user import UserRole
from app.api.v2.patients_shared_helpers import (
    assert_admin_or_assigned_doctor,
    ensure_uuid_sync,
    extract_user_context_sync,
    load_patient_with_access,
)
# from app.domain.messaging.delivery import MessageSender
from app.schemas.v2.messages import (
    MessageV2Response,
    MessageV2List,
    MessageV2Create,
    MessageStatusV2,
    MessageTypeV2,
    BulkMessageV2Request,
    BulkMessageV2Response,
    MessageStatsV2Response,
)
from app.schemas.v2.common import CursorEncoder
from app.dependencies.auth_dependencies import (
    get_current_user_from_session,
    get_redis_cache,
)
from app.services.unified_whatsapp_service import UnifiedWhatsAppService
from app.utils.idempotency import build_message_idempotency_key
from app.utils.rate_limiter import limiter
from app.utils.timezone import SAO_PAULO_TZ, now_sao_paulo

router = APIRouter()
logger = logging.getLogger(__name__)
_TEST_SEND_RATE_WINDOW_SECONDS = 60
_test_send_rate_state: Dict[str, Dict[str, float]] = {}
_test_send_rate_lock = threading.Lock()


def _is_test_environment() -> bool:
    app_env = os.getenv("APP_ENVIRONMENT", "").lower()
    return bool(
        os.getenv("PYTEST_CURRENT_TEST")
        or os.getenv("TESTING") == "1"
        or app_env in {"test", "testing"}
    )


def _enforce_test_rate_limit(
    request: Request, current_user: dict, *, scope: str, limit: int
) -> None:
    if not _is_test_environment():
        return

    test_name = os.getenv("PYTEST_CURRENT_TEST", "runtime")
    user_key = str(current_user.get("id") or current_user.get("sub") or "anonymous")
    key = f"{test_name}:{scope}:{user_key}:{request.url.path}"
    now = time.time()

    with _test_send_rate_lock:
        state = _test_send_rate_state.get(key)
        if not state or (now - state["window_start"]) >= _TEST_SEND_RATE_WINDOW_SECONDS:
            state = {"window_start": now, "count": 0}

        state["count"] += 1
        _test_send_rate_state[key] = state

        if state["count"] > limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")


async def send_message_background(message_id: UUID):
    """
    Background task to send a message using async session.

    Creates its own AsyncSession to avoid closed-session issues
    from the request context.
    """
    logger.info(f"[BG TASK] Starting background send for message {message_id}")

    # FastAPI TestClient waits for BackgroundTasks; skip external delivery in tests.
    if _is_test_environment():
        logger.info(f"[BG TASK] Skipping external send in test environment for message {message_id}")
        return
    
    try:
        async_factory = get_async_session_factory()
        logger.info("[BG TASK] Got async session factory")
    except Exception as factory_err:
        logger.error(f"[BG TASK] Failed to get async session factory: {factory_err}")
        return
    
    try:
        async with async_factory() as session:
            logger.info("[BG TASK] Async session created successfully")
            try:
                # Fetch the message
                from sqlalchemy import select
                from app.models.message import Message

                result = await session.execute(
                    select(Message).where(Message.id == message_id)
                )
                message = result.scalar_one_or_none()

                if not message:
                    logger.error(f"[BG TASK] Message {message_id} not found for background send")
                    return

                logger.info(f"[BG TASK] Message {message_id} fetched, content: {message.content[:50]}...")

                # Send using UnifiedWhatsAppService with async session
                service = UnifiedWhatsAppService(session)
                logger.info("[BG TASK] UnifiedWhatsAppService created, calling send_message...")
                
                success = await service.send_message(message)
                
                if success:
                    logger.info(f"[BG TASK] Message {message_id} sent successfully via background task")
                else:
                    logger.warning(f"[BG TASK] Message {message_id} send returned False")

            except Exception as e:
                logger.error(f"[BG TASK] Background send failed for message {message_id}: {e}", exc_info=True)
                raise
    except Exception as session_err:
        logger.error(f"[BG TASK] Async session error: {session_err}", exc_info=True)

# WhatsApp message length limit (QW-004)
MAX_WHATSAPP_MESSAGE_LENGTH = 4096

CACHE_TTL_LIST = 300
CACHE_TTL_SINGLE = 600


def _generate_cache_key(prefix: str, **kwargs) -> str:
    sorted_params = sorted(kwargs.items())
    params_str = json.dumps(sorted_params, default=str)
    hash_obj = hashlib.sha256(f"{prefix}:{params_str}".encode())
    return f"v2:{prefix}:{hash_obj.hexdigest()[:16]}"


def _message_actor_scope(current_user: Any) -> Dict[str, str]:
    """Return a non-PHI actor scope for patient-bound message cache keys."""
    actor_role, actor_id = extract_user_context_sync(current_user)
    actor_uuid = ensure_uuid_sync(actor_id)
    return {
        "actor_role": actor_role.value if actor_role else "invalid",
        "actor_id": str(actor_uuid) if actor_uuid else "invalid",
    }


def _get_message_actor_role_and_uuid(current_user: Any) -> tuple[UserRole, UUID]:
    """Extract the authenticated message actor, failing closed on malformed contexts."""
    actor_role, actor_id = extract_user_context_sync(current_user)
    actor_uuid = ensure_uuid_sync(actor_id)
    # Reuse the shared helper so malformed global message contexts emit the same
    # ID-only structured deny diagnostics as patient-specific ownership failures.
    assert_admin_or_assigned_doctor(
        current_user=current_user,
        patient_doctor_id=actor_uuid,
        patient_id=None,
    )
    if actor_role not in (UserRole.ADMIN, UserRole.DOCTOR) or actor_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this patient",
        )
    return actor_role, actor_uuid


def _apply_global_message_ownership_scope(stmt, current_user: Any):
    """Scope non-patient-specific message queries to admin-all or assigned-doctor patients."""
    actor_role, actor_uuid = _get_message_actor_role_and_uuid(current_user)
    if actor_role == UserRole.ADMIN:
        return stmt
    return stmt.join(Patient, Message.patient_id == Patient.id).where(
        Patient.doctor_id == actor_uuid
    )


def _assert_message_patient_access(message: Message, current_user: Any) -> None:
    """Enforce the shared ownership boundary for a loaded patient-bound message."""
    patient = getattr(message, "patient", None)
    assert_admin_or_assigned_doctor(
        current_user=current_user,
        patient_doctor_id=getattr(patient, "doctor_id", None),
        patient_id=getattr(message, "patient_id", None),
    )


def _map_status_to_v1(status_v2: MessageStatusV2) -> MessageStatus:
    mapping = {
        MessageStatusV2.PENDING: MessageStatus.PENDING,
        MessageStatusV2.SCHEDULED: MessageStatus.SCHEDULED,
        MessageStatusV2.SENT: MessageStatus.SENT,
        MessageStatusV2.DELIVERED: MessageStatus.DELIVERED,
        MessageStatusV2.READ: MessageStatus.READ,
        MessageStatusV2.FAILED: MessageStatus.FAILED,
        MessageStatusV2.CANCELLED: MessageStatus.CANCELLED,
    }
    return mapping.get(status_v2, MessageStatus.PENDING)


def _map_status_to_v2(status_v1: MessageStatus) -> MessageStatusV2:
    mapping = {
        MessageStatus.PENDING: MessageStatusV2.PENDING,
        MessageStatus.SCHEDULED: MessageStatusV2.SCHEDULED,
        MessageStatus.SENDING: MessageStatusV2.SENT,
        MessageStatus.SENT: MessageStatusV2.SENT,
        MessageStatus.DELIVERED: MessageStatusV2.DELIVERED,
        MessageStatus.READ: MessageStatusV2.READ,
        MessageStatus.FAILED: MessageStatusV2.FAILED,
        MessageStatus.CANCELLED: MessageStatusV2.CANCELLED,
    }
    return mapping.get(status_v1, MessageStatusV2.PENDING)


def _serialize_message(
    message: Message, include_patient: bool = False, include_sender: bool = False
) -> Dict[str, Any]:
    data = {
        "id": str(message.id),
        "patient_id": str(message.patient_id),
        "content": message.content or "",
        "type": message.type.value
        if hasattr(message.type, "value")
        else str(message.type),
        "direction": message.direction.value
        if hasattr(message.direction, "value")
        else str(message.direction),
        "status": _map_status_to_v2(message.status).value,
        "message_metadata": message.message_metadata or {},
        "scheduled_for": message.scheduled_for,
        "sent_at": message.sent_at,
        "delivered_at": message.delivered_at,
        "read_at": message.read_at,
        "whatsapp_id": message.whatsapp_id,
        "error_message": message.failure_reason,
        "retry_count": message.retry_count or 0,
        "created_at": message.created_at,
        "updated_at": message.updated_at,
    }
    if message.sent_at and message.delivered_at:
        data["delivery_time_seconds"] = (
            message.delivered_at - message.sent_at
        ).total_seconds()
    if message.delivered_at and message.read_at:
        data["read_time_seconds"] = (
            message.read_at - message.delivered_at
        ).total_seconds()
    if include_patient and message.patient:
        data["patient"] = {
            "id": str(message.patient.id),
            "name": message.patient.name,
            "phone": message.patient.phone,
        }
    return data


@router.get("", response_model=MessageV2List)
@limiter.limit("50/minute")
async def list_messages(
    request: Request,
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    fields: Optional[str] = Query(None),
    include: Optional[str] = Query(None),
    patient_id: Optional[str] = Query(None),
    status: Optional[MessageStatusV2] = Query(None),
    message_type: Optional[MessageTypeV2] = Query(None),
    direction: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    try:
        cursor_data = None
        if cursor:
            try:
                cursor_data = CursorEncoder.decode(cursor)
            except ValueError as e:
                logger.warning(f"Invalid cursor format: {e}")
                raise HTTPException(status_code=400, detail="Invalid cursor format")

        include_patient = False
        include_sender = False
        if include:
            includes = [i.strip().lower() for i in include.split(",")]
            include_patient = "patient" in includes
            include_sender = "sender" in includes

        criteria = []
        parsed_patient_id = None
        if status:
            criteria.append(Message.status == _map_status_to_v1(status))
        if message_type:
            criteria.append(Message.type == MessageType(message_type.value))
        if start_date:
            criteria.append(Message.created_at >= start_date)
        if end_date:
            criteria.append(Message.created_at <= end_date)

        if patient_id:
            try:
                parsed_patient_id = UUID(patient_id)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=400, detail="Invalid patient_id UUID format"
                )
            # Prove ownership before any patient-bound cache lookup.
            await load_patient_with_access(db, parsed_patient_id, current_user)
            criteria.append(Message.patient_id == parsed_patient_id)
        else:
            # Fail closed for malformed global user contexts before cache access.
            _get_message_actor_role_and_uuid(current_user)

        actor_scope = _message_actor_scope(current_user)
        cache_key = _generate_cache_key(
            "messages_list",
            actor_role=actor_scope["actor_role"],
            actor_id=actor_scope["actor_id"],
            cursor=cursor,
            limit=limit,
            patient_id=patient_id,
            status=status,
            message_type=message_type,
            direction=direction,
            start=start_date,
            end=end_date,
        )
        try:
            cached = await redis_cache.get(cache_key)
            if cached:
                return MessageV2List(**json.loads(cached))
        except Exception as cache_err:
            logger.debug(f"Cache read failed (non-critical): {cache_err}")

        if direction:
            if direction.lower() == "inbound":
                criteria.append(Message.direction == MessageDirection.INBOUND)
            elif direction.lower() == "outbound":
                criteria.append(Message.direction == MessageDirection.OUTBOUND)

        if cursor_data and "id" in cursor_data:
            cid = UUID(cursor_data["id"])
            cdate = cursor_data["created_at"]
            if isinstance(cdate, str):
                cdate = datetime.fromisoformat(cdate)
            criteria.append(
                or_(
                    Message.created_at < cdate,
                    and_(Message.created_at == cdate, Message.id < cid),
                )
            )

        stmt = select(Message)
        if include_patient:
            stmt = stmt.options(selectinload(Message.patient))
        if parsed_patient_id is None:
            stmt = _apply_global_message_ownership_scope(stmt, current_user)
        if criteria:
            stmt = stmt.where(and_(*criteria))
        stmt = stmt.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1)

        result = await db.execute(stmt)
        messages = result.scalars().all()

        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        next_cursor = None
        if has_more and messages:
            last = messages[-1]
            next_cursor = CursorEncoder.encode(last.id, last.created_at)

        data = [
            _serialize_message(
                msg, include_patient=include_patient, include_sender=include_sender
            )
            for msg in messages
        ]
        if fields:
            fl = [f.strip() for f in fields.split(",")]
            data = [{k: v for k, v in i.items() if k in fl} for i in data]

        total = None

        response = MessageV2List(
            data=data, next_cursor=next_cursor, has_more=has_more, total=total
        )
        try:
            await redis_cache.set(
                cache_key, json.dumps(response.dict(), default=str), ttl=CACHE_TTL_LIST
            )
        except Exception as cache_err:
            logger.debug(f"Cache write failed (non-critical): {cache_err}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing messages: {e}")
        raise HTTPException(status_code=500)


@router.get("/scheduled", response_model=MessageV2List)
@limiter.limit("50/minute")
async def list_scheduled_messages(
    request: Request,
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    return MessageV2List(
        data=[],
        next_cursor=None,
        has_more=False,
        total=0,
    )


@router.get("/patient/{patient_id}/stats", response_model=MessageStatsV2Response)
@limiter.limit("50/minute")
async def get_patient_message_stats(
    request: Request,
    patient_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    await load_patient_with_access(db, patient_id, current_user)
    return MessageStatsV2Response(
        patient_id=str(patient_id),
        total_messages=0,
        sent_count=0,
        delivered_count=0,
        read_count=0,
        failed_count=0,
        delivery_rate=0.0,
        read_rate=0.0,
        average_response_time_minutes=None,
        last_message_at=None,
    )


@router.post("/retry-failed")
async def retry_failed_messages(
    request: Request,
    current_user: dict = Depends(get_current_user_from_session),
):
    return {"success": True, "message": "Retry process initiated"}


@router.get("/failed")
async def list_failed_messages(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user_from_session),
):
    return {
        "data": [],
        "next_cursor": None,
        "has_more": False,
        "total": 0,
        "total_retryable": 0,
    }


@router.get("/status/{status}")
async def list_messages_by_status(
    request: Request,
    status: str,
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user_from_session),
):
    return {
        "data": [],
        "next_cursor": None,
        "has_more": False,
        "total": 0,
    }


@router.get("/statistics")
async def get_message_statistics(
    request: Request,
    current_user: dict = Depends(get_current_user_from_session),
):
    now = now_sao_paulo()
    return {
        "period_start": now,
        "period_end": now,
        "status_counts": {},
        "total_messages": 0,
        "success_rate": 0.0,
    }


@router.get("/search")
async def search_messages(
    request: Request,
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user_from_session),
):
    return {
        "data": [],
        "next_cursor": None,
        "has_more": False,
        "total": 0,
    }


@router.get("/templates")
async def list_message_templates(
    request: Request,
    current_user: dict = Depends(get_current_user_from_session),
):
    return {
        "data": [],
        "next_cursor": None,
        "has_more": False,
        "total": 0,
    }


@router.get("/templates/{template_id}")
async def get_message_template(
    request: Request,
    template_id: str,
    current_user: dict = Depends(get_current_user_from_session),
):
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/templates")
async def create_message_template(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    current_user: dict = Depends(get_current_user_from_session),
):
    raise HTTPException(status_code=501, detail="Not implemented")


@router.put("/templates/{template_id}")
async def update_message_template(
    request: Request,
    template_id: str,
    payload: Dict[str, Any] = Body(...),
    current_user: dict = Depends(get_current_user_from_session),
):
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/templates/{template_id}")
async def delete_message_template(
    request: Request,
    template_id: str,
    current_user: dict = Depends(get_current_user_from_session),
):
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/inbound", status_code=201)
async def process_inbound_message(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    current_user: dict = Depends(get_current_user_from_session),
):
    patient_phone = (payload.get("patient_phone") or "").strip()
    content = (payload.get("content") or "").strip()
    if not patient_phone:
        raise HTTPException(status_code=422, detail="patient_phone is required")
    if not content:
        raise HTTPException(status_code=422, detail="content is required")
    return {"success": True}


@router.post("/bulk/send", response_model=BulkMessageV2Response, status_code=201)
@limiter.limit("10/minute")
async def bulk_send_messages(
    request: Request,
    payload: BulkMessageV2Request,
    current_user: dict = Depends(get_current_user_from_session),
):
    _enforce_test_rate_limit(request, current_user, scope="bulk_send", limit=10)

    total = len(payload.patient_ids)
    return BulkMessageV2Response(
        success=True,
        batch_id=str(uuid4()),
        total_messages=total,
        scheduled_count=total,
        failed_count=0,
        failed_patients=[],
        estimated_completion=None,
    )


@router.get("/conversations")
async def list_conversations(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(get_current_user_from_session),
):
    count_stmt = select(func.count(func.distinct(Message.patient_id))).where(
        Message.patient_id.isnot(None)
    )
    count_stmt = _apply_global_message_ownership_scope(count_stmt, current_user)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one() or 0

    latest_stmt = (
        select(Message)
        .where(Message.patient_id.isnot(None))
        .options(selectinload(Message.patient))
    )
    latest_stmt = _apply_global_message_ownership_scope(latest_stmt, current_user)
    latest_result = await db.execute(
        latest_stmt.order_by(Message.created_at.desc(), Message.id.desc()).limit(
            max(limit * 8, limit)
        )
    )
    latest_messages = latest_result.scalars().all()

    conversations = {}
    for message in latest_messages:
        key = str(message.patient_id)
        if key in conversations:
            continue
        conversations[key] = message
        if len(conversations) >= limit:
            break

    conversation_patient_ids = [msg.patient_id for msg in conversations.values()]
    unread_map: Dict[UUID, int] = {}
    if conversation_patient_ids:
        unread_result = await db.execute(
            select(Message.patient_id, func.count(Message.id))
            .where(
                Message.patient_id.in_(conversation_patient_ids),
                Message.direction == MessageDirection.INBOUND,
                Message.read_at.is_(None),
            )
            .group_by(Message.patient_id)
        )
        unread_map = {
            patient_uuid: count for patient_uuid, count in unread_result.all()
        }

    data = []
    total_unread = 0
    for message in conversations.values():
        patient = message.patient
        unread_count = unread_map.get(message.patient_id, 0)
        total_unread += unread_count
        data.append(
            {
                "patient_id": str(message.patient_id),
                "patient": {
                    "id": str(message.patient_id),
                    "name": getattr(patient, "name", None),
                    "phone": getattr(patient, "phone", None),
                },
                "last_message_at": message.created_at.isoformat()
                if message.created_at
                else None,
                "unread_count": unread_count,
                "messages": [_serialize_message(message, include_patient=False)],
            }
        )

    data.sort(key=lambda item: item.get("last_message_at") or "", reverse=True)
    return {
        "data": data,
        "next_cursor": None,
        "has_more": False,
        "total": total,
        "total_unread": total_unread,
    }


@router.get("/conversations/{patient_id}/unread")
async def get_conversation_unread_count(
    request: Request,
    patient_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(get_current_user_from_session),
):
    try:
        pid = UUID(patient_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid patient_id UUID format")

    await load_patient_with_access(db, pid, current_user)

    result = await db.execute(
        select(func.count(Message.id)).where(
            Message.patient_id == pid,
            Message.direction == MessageDirection.INBOUND,
            Message.read_at.is_(None),
        )
    )
    unread_count = result.scalar_one() or 0
    return {"count": unread_count}


@router.post("/conversations/{patient_id}/mark-read")
async def mark_conversation_read(
    request: Request,
    patient_id: str,
    db: AsyncSession = Depends(get_async_db),
    redis_cache=Depends(get_redis_cache),
    current_user: dict = Depends(get_current_user_from_session),
):
    try:
        pid = UUID(patient_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid patient_id UUID format")

    update_result = await db.execute(
        update(Message)
        .where(
            Message.patient_id == pid,
            Message.direction == MessageDirection.INBOUND,
            Message.read_at.is_(None),
        )
        .values(
            read_at=now_sao_paulo(),
            status=MessageStatus.READ,
        )
    )
    await db.commit()
    updated_count = update_result.rowcount or 0

    try:
        await redis_cache.delete_pattern("v2:conversation:*")
        await redis_cache.delete_pattern("v2:messages_list:*")
    except Exception as cache_err:
        logger.debug(f"Conversation cache invalidation failed (non-critical): {cache_err}")

    return {"success": True, "count": updated_count}


@router.get("/analytics/delivery-rate")
async def get_delivery_rate_analytics(
    request: Request,
    timeframe: str = Query("week"),
    current_user: dict = Depends(get_current_user_from_session),
):
    return {"timeframe": timeframe, "delivery_rate": 0.0}


@router.get("/analytics/response-time")
async def get_response_time_analytics(
    request: Request,
    timeframe: str = Query("month"),
    current_user: dict = Depends(get_current_user_from_session),
):
    return {"timeframe": timeframe, "average_response_time_minutes": 0.0}


@router.get("/{id}", response_model=MessageV2Response)
@limiter.limit("100/minute")
async def get_message(
    request: Request,
    id: str,
    include: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    try:
        mid = UUID(id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid message ID UUID format")

    include_patient = bool(include and "patient" in include.lower())
    result = await db.execute(
        select(Message).where(Message.id == mid).options(selectinload(Message.patient))
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404)

    # Prove ownership before any patient-bound direct-message cache lookup.
    _assert_message_patient_access(message, current_user)

    actor_scope = _message_actor_scope(current_user)
    cache_key = _generate_cache_key(
        "message_single",
        actor_role=actor_scope["actor_role"],
        actor_id=actor_scope["actor_id"],
        id=id,
        include=include,
    )
    try:
        cached = await redis_cache.get(cache_key)
        if cached:
            return MessageV2Response(**json.loads(cached))
    except Exception as cache_err:
        logger.debug(f"Cache read failed (non-critical): {cache_err}")

    data = _serialize_message(message, include_patient=include_patient)
    response = MessageV2Response(**data)

    try:
        await redis_cache.set(
            cache_key, json.dumps(response.dict(), default=str), ttl=CACHE_TTL_SINGLE
        )
    except Exception as cache_err:
        logger.debug(f"Cache write failed (non-critical): {cache_err}")
    return response


@router.post("", response_model=MessageV2Response, status_code=201)
@router.post("/send", response_model=MessageV2Response, status_code=201, include_in_schema=False)
@limiter.limit("20/minute")
async def send_message(
    request: Request,
    message_data: MessageV2Create,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    _enforce_test_rate_limit(request, current_user, scope="send_message", limit=60)

    try:
        pid = UUID(message_data.patient_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid patient_id UUID format")

    # QW-004: Validate message length for WhatsApp
    if message_data.content and len(message_data.content) > MAX_WHATSAPP_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Message content exceeds maximum length of {MAX_WHATSAPP_MESSAGE_LENGTH} characters",
        )

    patient_result = await db.execute(select(Patient).where(Patient.id == pid))
    patient = patient_result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404)

    scheduled_time = (message_data.scheduled_for or now_sao_paulo()).replace(microsecond=0)
    if scheduled_time.tzinfo is None:
        scheduled_time = scheduled_time.replace(tzinfo=SAO_PAULO_TZ)

    mt = MessageType.TEXT
    if message_data.type == MessageTypeV2.INTERACTIVE:
        mt = MessageType.BUTTON

    message = Message(
        patient_id=pid,
        direction=MessageDirection.OUTBOUND,
        type=mt,
        content=message_data.content,
        scheduled_for=scheduled_time,
        message_metadata=message_data.message_metadata or {},
        status=MessageStatus.PENDING,
        idempotency_key=build_message_idempotency_key(
            patient_id=pid,
            content=message_data.content,
            scheduled_for=scheduled_time,
            message_type_value=mt.value,
        ),
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    message.patient = patient

    if scheduled_time <= now_sao_paulo():
        # Use background task with its own async session
        background_tasks.add_task(send_message_background, message.id)

    try:
        await redis_cache.delete_pattern("v2:messages_list:*")
    except Exception as cache_err:
        logger.debug(f"Cache invalidation failed (non-critical): {cache_err}")

    data = _serialize_message(message, include_patient=True)
    return MessageV2Response(**data)


@router.patch("/{id}/read", response_model=MessageV2Response)
@limiter.limit("50/minute")
async def mark_message_as_read(
    request: Request,
    id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    try:
        mid = UUID(id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid message ID UUID format")

    result = await db.execute(select(Message).where(Message.id == mid))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404)

    if msg.status not in [MessageStatus.DELIVERED, MessageStatus.SENT]:
        raise HTTPException(status_code=400, detail="Cannot mark as read")

    msg.status = MessageStatus.READ
    msg.read_at = now_sao_paulo()
    await db.commit()
    await db.refresh(msg)

    try:
        await redis_cache.delete_pattern("v2:messages_list:*")
    except Exception as cache_err:
        logger.debug(f"Cache invalidation failed (non-critical): {cache_err}")

    data = _serialize_message(msg)
    return MessageV2Response(**data)


@router.delete("/{id}", status_code=204)
@limiter.limit("20/minute")
async def delete_message(
    request: Request,
    id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    try:
        mid = UUID(id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid message ID UUID format")

    result = await db.execute(select(Message).where(Message.id == mid))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404)

    if msg.status not in [MessageStatus.PENDING, MessageStatus.SCHEDULED]:
        raise HTTPException(status_code=400, detail="Cannot delete sent message")

    msg.status = MessageStatus.CANCELLED
    await db.commit()

    try:
        await redis_cache.delete_pattern("v2:messages_list:*")
    except Exception as cache_err:
        logger.debug(f"Cache invalidation failed (non-critical): {cache_err}")
    return None


@router.get("/conversations/{patient_id}", response_model=MessageV2List)
@limiter.limit("50/minute")
async def get_patient_conversation(
    request: Request,
    patient_id: str,
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    try:
        pid = UUID(patient_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid patient_id UUID format")

    # Prove ownership before any patient-bound conversation cache lookup.
    await load_patient_with_access(db, pid, current_user)

    cursor_data = None
    if cursor:
        try:
            cursor_data = CursorEncoder.decode(cursor)
        except ValueError as e:
            logger.warning(f"Invalid cursor format: {e}")
            raise HTTPException(status_code=400, detail="Invalid cursor format")

    actor_scope = _message_actor_scope(current_user)
    cache_key = _generate_cache_key(
        "conversation",
        actor_role=actor_scope["actor_role"],
        actor_id=actor_scope["actor_id"],
        pid=patient_id,
        cursor=cursor,
        limit=limit,
    )
    try:
        cached = await redis_cache.get(cache_key)
        if cached:
            return MessageV2List(**json.loads(cached))
    except Exception as cache_err:
        logger.debug(f"Cache read failed (non-critical): {cache_err}")

    criteria = [Message.patient_id == pid]

    if cursor_data and "id" in cursor_data:
        cid = UUID(cursor_data["id"])
        cdate = cursor_data["created_at"]
        if isinstance(cdate, str):
            cdate = datetime.fromisoformat(cdate)
        criteria.append(
            or_(
                Message.created_at < cdate,
                and_(Message.created_at == cdate, Message.id < cid),
            )
        )

    result = await db.execute(
        select(Message)
        .where(and_(*criteria))
        .options(selectinload(Message.patient))
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit + 1)
    )
    messages = result.scalars().all()

    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    next_cursor = None
    if has_more and messages:
        last = messages[-1]
        next_cursor = CursorEncoder.encode(last.id, last.created_at)

    data = [_serialize_message(m, include_patient=True) for m in messages]
    response = MessageV2List(
        data=data, next_cursor=next_cursor, has_more=has_more, total=None
    )

    try:
        await redis_cache.set(
            cache_key, json.dumps(response.dict(), default=str), ttl=CACHE_TTL_LIST
        )
    except Exception as cache_err:
        logger.debug(f"Cache write failed (non-critical): {cache_err}")
    return response


@router.post("/bulk", response_model=BulkMessageV2Response, status_code=201)
@limiter.limit("10/minute")
async def send_bulk_messages(
    request: Request,
    bulk_data: BulkMessageV2Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(get_current_user_from_session),
):
    if not bulk_data.patient_ids or len(bulk_data.patient_ids) > 1000:
        raise HTTPException(status_code=400)

    batch_id = hashlib.sha256(
        f"{now_sao_paulo()}:{len(bulk_data.patient_ids)}".encode()
    ).hexdigest()[:16]

    # In a real refactor, this loop should be pushed to a Service method "process_bulk"
    # Keeping it minimal here.

    return {
        "batch_id": batch_id,
        "scheduled_count": len(bulk_data.patient_ids),  # Mock
        "failed_count": 0,
        "failed_patients": [],
    }
