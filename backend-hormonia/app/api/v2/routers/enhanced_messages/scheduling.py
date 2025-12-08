"""
Scheduled Message Management Endpoints

Handles scheduling of messages including:
- Creating scheduled messages with optional recurrence
- Listing scheduled messages with filtering
- Getting scheduled message details
- Canceling scheduled messages
"""

from typing import Optional
from datetime import datetime
from uuid import uuid4
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient
from app.dependencies.auth_dependencies import get_current_user_from_session, get_redis_cache
from app.schemas.v2.enhanced_messages import (
    ScheduledMessageV2Create,
    ScheduledMessageV2Response,
    ScheduledMessageV2List,
)
from app.api.v2.dependencies import (
    get_pagination_params,
    create_cursor,
)
from app.utils.rate_limiter import limiter
from .dependencies import _render_template

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/scheduled",
    response_model=ScheduledMessageV2Response,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule message",
    description="Schedule a message for future delivery with optional recurrence"
)
@limiter.limit("30/minute")
async def schedule_message(
    request: Request,
    schedule_data: ScheduledMessageV2Create,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user_from_session),
    db = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
) -> ScheduledMessageV2Response:
    """
    Schedule a message with optional recurrence.

    Features:
    - One-time scheduling
    - Recurring messages (daily, weekly, monthly)
    - Delivery optimization
    - Template support
    """
    try:
        # Validate patient access
        patient = db.query(Patient).filter(
            Patient.id == schedule_data.patient_id
        ).first()

        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )

        # Render template if provided
        content = schedule_data.content
        if schedule_data.template_id and schedule_data.template_variables:
            template_key = f"template:v2:{schedule_data.template_id}"
            template_data = await redis_cache.get(template_key)

            if template_data:
                template_dict = json.loads(template_data)
                content = _render_template(
                    template_dict["content"],
                    schedule_data.template_variables
                )

        # Create scheduled message
        schedule_id = f"sched_{uuid4().hex[:12]}"
        schedule_dict = {
            "id": schedule_id,
            "message_id": None,
            "patient_id": schedule_data.patient_id,
            "content": content,
            "type": schedule_data.type.value,
            "scheduled_for": schedule_data.scheduled_for,
            "actual_sent_at": None,
            "template_id": schedule_data.template_id,
            "recurrence": schedule_data.recurrence.model_dump() if schedule_data.recurrence else None,
            "optimization_strategy": schedule_data.optimization_strategy.value,
            "status": "pending",
            "occurrences_sent": 0,
            "next_occurrence": schedule_data.scheduled_for,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        # Store in cache (5 min TTL for scheduled messages)
        cache_key = f"scheduled:v2:{schedule_id}"
        await redis_cache.set(cache_key, json.dumps(schedule_dict, default=str), ex=300)

        # Add to pending queue
        queue_key = f"scheduled:v2:queue:pending"
        await redis_cache.zadd(
            queue_key,
            {schedule_id: schedule_data.scheduled_for.timestamp()}
        )

        logger.info(
            f"Message scheduled: {schedule_id}",
            extra={
                "schedule_id": schedule_id,
                "patient_id": schedule_data.patient_id,
                "scheduled_for": schedule_data.scheduled_for.isoformat(),
                "has_recurrence": schedule_data.recurrence is not None,
                "user_id": current_user.get("id")
            }
        )

        return ScheduledMessageV2Response(**schedule_dict)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scheduling message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to schedule message"
        )


@router.get(
    "/scheduled",
    response_model=ScheduledMessageV2List,
    summary="List scheduled messages",
    description="Get paginated list of scheduled messages"
)
@limiter.limit("100/minute")
async def list_scheduled_messages(
    request: Request,
    pagination = Depends(get_pagination_params),
    patient_id: Optional[str] = Query(None, description="Filter by patient"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    has_recurrence: Optional[bool] = Query(None, description="Filter by recurrence"),
    current_user: dict = Depends(get_current_user_from_session),
    redis_cache = Depends(get_redis_cache)
) -> ScheduledMessageV2List:
    """
    List scheduled messages with filtering.

    Features:
    - Patient filtering
    - Status filtering
    - Recurrence filtering
    - Redis caching (5 min TTL)
    """
    try:
        cursor_data = pagination["cursor_data"]
        limit = pagination["limit"]

        # Get pending scheduled messages from queue
        queue_key = "scheduled:v2:queue:pending"
        schedule_ids = await redis_cache.zrange(queue_key, 0, limit)

        schedules = []
        for schedule_id in schedule_ids:
            cache_key = f"scheduled:v2:{schedule_id}"
            schedule_data = await redis_cache.get(cache_key)
            if schedule_data:
                schedule_dict = json.loads(schedule_data)

                # Apply filters
                if patient_id and schedule_dict.get("patient_id") != patient_id:
                    continue
                if status_filter and schedule_dict.get("status") != status_filter:
                    continue
                if has_recurrence is not None:
                    has_rec = schedule_dict.get("recurrence") is not None
                    if has_rec != has_recurrence:
                        continue

                schedules.append(schedule_dict)

        # Pagination
        has_more = len(schedules) > limit
        if has_more:
            schedules = schedules[:limit]

        next_cursor = create_cursor(len(schedules)) if has_more and schedules else None

        # Count totals
        total_pending = sum(1 for s in schedules if s.get("status") == "pending")
        total_recurring = sum(1 for s in schedules if s.get("recurrence") is not None)

        result = ScheduledMessageV2List(
            data=[ScheduledMessageV2Response(**s) for s in schedules],
            next_cursor=next_cursor,
            has_more=has_more,
            total=len(schedules),
            total_pending=total_pending,
            total_recurring=total_recurring
        )

        logger.info(
            f"Scheduled messages listed: {len(schedules)}",
            extra={"count": len(schedules), "user_id": current_user.get("id")}
        )

        return result

    except Exception as e:
        logger.error(f"Error listing scheduled messages: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list scheduled messages"
        )
