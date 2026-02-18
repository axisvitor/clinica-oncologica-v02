"""
Messages API v2 - Statistics and Analytics
Handles statistics and analytics: get message statistics, get delivery stats.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.message import Message, MessageStatus, MessageDirection
from app.models.patient import Patient
from app.models.user import UserRole
from app.schemas.v2.messages import MessageStatsV2Response
from app.dependencies.auth_dependencies import (
    get_current_user_from_session,
    get_redis_cache,
)
from .helpers import (
    _extract_user_context,
    _get_cached_or_compute,
    _get_patient_with_access,
)
from app.utils.timezone import now_sao_paulo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/patient/{patient_id}/stats",
    response_model=MessageStatsV2Response,
    summary="Get patient message statistics",
    description="Get message statistics for a specific patient (cached 5min)",
)
async def get_patient_message_stats(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    """Get message statistics for a patient."""
    patient_uuid, _ = _get_patient_with_access(
        db=db,
        current_user=current_user,
        patient_id=patient_id,
    )

    # Try cache
    cache_key = f"message_stats:patient:{patient_id}"

    def compute_stats():
        messages = db.query(Message).filter(Message.patient_id == patient_uuid).all()

        total_messages = len(messages)
        sent_count = sum(1 for m in messages if m.status == MessageStatus.SENT)
        delivered_count = sum(
            1 for m in messages if m.status == MessageStatus.DELIVERED
        )
        read_count = sum(1 for m in messages if m.status == MessageStatus.READ)
        failed_count = sum(1 for m in messages if m.status == MessageStatus.FAILED)

        delivery_rate = (delivered_count / sent_count * 100) if sent_count > 0 else 0
        read_rate = (read_count / delivered_count * 100) if delivered_count > 0 else 0

        # Calculate average response time for inbound messages
        inbound_messages = [
            m
            for m in messages
            if m.direction == MessageDirection.INBOUND and m.created_at
        ]
        avg_response_time = None
        if len(inbound_messages) > 1:
            # Simple calculation: average time between consecutive inbound messages
            times = [
                m.created_at
                for m in sorted(inbound_messages, key=lambda x: x.created_at)
            ]
            deltas = [
                (times[i + 1] - times[i]).total_seconds() / 60
                for i in range(len(times) - 1)
            ]
            avg_response_time = sum(deltas) / len(deltas) if deltas else None

        last_message_at = max([m.created_at for m in messages]) if messages else None

        return {
            "patient_id": patient_id,
            "total_messages": total_messages,
            "sent_count": sent_count,
            "delivered_count": delivered_count,
            "read_count": read_count,
            "failed_count": failed_count,
            "delivery_rate": round(delivery_rate, 2),
            "read_rate": round(read_rate, 2),
            "average_response_time_minutes": round(avg_response_time, 2)
            if avg_response_time
            else None,
            "last_message_at": last_message_at.isoformat() if last_message_at else None,
        }

    return await _get_cached_or_compute(redis_cache, cache_key, compute_stats, ttl=300)


@router.get(
    "/statistics",
    summary="Get overall message statistics",
    description="Get overall message statistics (cached 15min)",
)
async def get_statistics(
    days: int = Query(30, ge=1, le=365, description="Period in days"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    """Get overall message statistics."""
    role_enum, user_id = _extract_user_context(current_user)

    # Cache key includes user_id for RBAC
    cache_key = f"message_stats:overall:{user_id}:{days}"

    def compute_stats():
        start_date = now_sao_paulo() - timedelta(days=days)

        query = db.query(Message).filter(Message.created_at >= start_date)

        # RBAC
        if role_enum != UserRole.ADMIN:
            user_uuid = UUID(user_id) if user_id else None
            query = query.join(Patient, Message.patient_id == Patient.id)
            query = query.filter(Patient.doctor_id == user_uuid)

        messages = query.all()

        total_messages = len(messages)

        status_counts = {}
        for msg_status in MessageStatus:
            status_counts[msg_status.value] = sum(1 for m in messages if m.status == msg_status)

        sent_count = status_counts.get(MessageStatus.SENT.value, 0)
        delivered_count = status_counts.get(MessageStatus.DELIVERED.value, 0)
        read_count = status_counts.get(MessageStatus.READ.value, 0)
        status_counts.get(MessageStatus.FAILED.value, 0)

        success_rate = (
            ((sent_count + delivered_count + read_count) / total_messages * 100)
            if total_messages > 0
            else 0
        )

        return {
            "period_start": start_date.isoformat(),
            "period_end": now_sao_paulo().isoformat(),
            "total_messages": total_messages,
            "status_counts": status_counts,
            "success_rate": round(success_rate, 2),
        }

    return await _get_cached_or_compute(redis_cache, cache_key, compute_stats, ttl=900)
