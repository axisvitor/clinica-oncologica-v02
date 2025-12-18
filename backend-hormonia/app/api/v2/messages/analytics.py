"""
Messages API v2 - Analytics
Handles analytics operations: delivery rate and response time analytics.

2 endpoints:
- GET "/analytics/delivery-rate" - Get delivery rate analytics over time
- GET "/analytics/response-time" - Get average response time analytics
"""

from datetime import datetime, timedelta
from uuid import UUID
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.message import Message, MessageStatus, MessageDirection
from app.models.patient import Patient
from app.models.user import UserRole
from app.dependencies.auth_dependencies import (
    get_current_user_from_session,
    get_redis_cache,
)
from .helpers import (
    _extract_user_context,
    _get_cached_or_compute,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Analytics Operations (2 endpoints)
# ============================================================================


@router.get(
    "/analytics/delivery-rate",
    summary="Get delivery rate analytics",
    description="Get delivery rate analytics over time (cached 15min)",
)
async def get_delivery_rate_analytics(
    days: int = Query(30, ge=1, le=365, description="Period in days"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    """Get delivery rate analytics."""
    role_enum, user_id = _extract_user_context(current_user)

    cache_key = f"analytics:delivery_rate:{user_id}:{days}"

    def compute_analytics():
        start_date = datetime.utcnow() - timedelta(days=days)

        query = db.query(Message).filter(
            Message.created_at >= start_date,
            Message.direction == MessageDirection.OUTBOUND,
        )

        # RBAC
        if role_enum != UserRole.ADMIN:
            user_uuid = UUID(user_id) if user_id else None
            query = query.join(Patient, Message.patient_id == Patient.id)
            query = query.filter(Patient.doctor_id == user_uuid)

        messages = query.all()

        total_sent = len(messages)
        delivered = sum(
            1
            for m in messages
            if m.status in [MessageStatus.DELIVERED, MessageStatus.READ]
        )
        failed = sum(1 for m in messages if m.status == MessageStatus.FAILED)

        delivery_rate = (delivered / total_sent * 100) if total_sent > 0 else 0
        failure_rate = (failed / total_sent * 100) if total_sent > 0 else 0

        return {
            "period_start": start_date.isoformat(),
            "period_end": datetime.utcnow().isoformat(),
            "total_sent": total_sent,
            "delivered": delivered,
            "failed": failed,
            "delivery_rate": round(delivery_rate, 2),
            "failure_rate": round(failure_rate, 2),
        }

    return await _get_cached_or_compute(
        redis_cache, cache_key, compute_analytics, ttl=900
    )


@router.get(
    "/analytics/response-time",
    summary="Get response time analytics",
    description="Get average response time analytics (cached 15min)",
)
async def get_response_time_analytics(
    days: int = Query(30, ge=1, le=365, description="Period in days"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    redis_cache=Depends(get_redis_cache),
):
    """Get response time analytics."""
    role_enum, user_id = _extract_user_context(current_user)

    cache_key = f"analytics:response_time:{user_id}:{days}"

    def compute_analytics():
        start_date = datetime.utcnow() - timedelta(days=days)

        query = db.query(Message).filter(
            Message.created_at >= start_date,
            Message.sent_at.isnot(None),
            Message.delivered_at.isnot(None),
        )

        # RBAC
        if role_enum != UserRole.ADMIN:
            user_uuid = UUID(user_id) if user_id else None
            query = query.join(Patient, Message.patient_id == Patient.id)
            query = query.filter(Patient.doctor_id == user_uuid)

        messages = query.all()

        if not messages:
            return {
                "period_start": start_date.isoformat(),
                "period_end": datetime.utcnow().isoformat(),
                "total_messages": 0,
                "average_delivery_time_seconds": 0,
                "average_read_time_seconds": 0,
            }

        delivery_times = [
            (m.delivered_at - m.sent_at).total_seconds()
            for m in messages
            if m.delivered_at and m.sent_at
        ]
        read_times = [
            (m.read_at - m.delivered_at).total_seconds()
            for m in messages
            if m.read_at and m.delivered_at
        ]

        avg_delivery = (
            sum(delivery_times) / len(delivery_times) if delivery_times else 0
        )
        avg_read = sum(read_times) / len(read_times) if read_times else 0

        return {
            "period_start": start_date.isoformat(),
            "period_end": datetime.utcnow().isoformat(),
            "total_messages": len(messages),
            "average_delivery_time_seconds": round(avg_delivery, 2),
            "average_read_time_seconds": round(avg_read, 2),
        }

    return await _get_cached_or_compute(
        redis_cache, cache_key, compute_analytics, ttl=900
    )
