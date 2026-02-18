from datetime import datetime, timezone
from uuid import UUID
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, or_

from app.database import get_db
from app.models.notification import Notification
from app.api.v2.dependencies import get_pagination_params_async
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.utils.rate_limiter import limiter

# Using auth schemas for now as they are defined there
from app.schemas.v2.auth import (
    NotificationV2List,
    NotificationMarkReadRequest,
    NotificationMarkReadResponse,
)
from app.utils.auth_helpers import extract_user_id as _extract_user_id
from app.utils.timezone import now_sao_paulo
from app.api.v2.routers import users as users_router_module

router = APIRouter()
logger = logging.getLogger(__name__)

CACHE_TTL_UNREAD_COUNT = 60  # 1 minute


async def _get_redis_client():
    try:
        # Reuse users router provider so auth tests can patch one shared path.
        return await users_router_module._get_redis_client()
    except Exception as e:
        logger.warning(f"Failed to get Redis client: {e}")
        return None


def _serialize_notification(notification: Notification) -> dict:
    """Serialize Notification model to API-friendly dict."""
    return {
        "id": str(notification.id),
        "title": notification.title,
        "message": notification.message,
        "type": notification.notification_type.value,
        "read": notification.is_read,
        "created_at": notification.created_at,
        "updated_at": notification.updated_at,
        "metadata": notification.notification_metadata or {},
        "action_url": notification.action_url,
    }


@router.get(
    "",
    response_model=NotificationV2List,
    summary="List notifications",
    description="Get notifications with cursor pagination and eager loading",
)
@limiter.limit("100/minute")
async def list_notifications(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
    pagination=Depends(get_pagination_params_async),
    unread_only: bool = Query(False, description="Show only unread notifications"),
):
    user_id = _extract_user_id(current_user)
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    # Build query
    filters = [Notification.user_id == user_uuid]

    if unread_only:
        filters.append(Notification.is_read.is_(False))

    query = db.query(Notification).filter(and_(*filters))

    # Apply cursor pagination
    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"])
        cursor_created = datetime.fromisoformat(
            cursor_data["created_at"]
        )
        query = query.filter(
            or_(
                Notification.created_at < cursor_created,
                and_(
                    Notification.created_at == cursor_created,
                    Notification.id > cursor_id,
                ),
            )
        )

    # Get total count (only on first page)
    total = None
    if not cursor_data:
        total = query.count()

    # Get unread count
    unread_count = (
        db.query(func.count(Notification.id))
        .filter(Notification.user_id == user_uuid, Notification.is_read.is_(False))
        .scalar()
    )

    # Order and limit
    query = query.order_by(Notification.created_at.desc(), Notification.id)
    notifications = query.limit(limit + 1).all()

    # Check if there are more results
    has_more = len(notifications) > limit
    if has_more:
        notifications = notifications[:limit]

    # Create next cursor
    next_cursor = None
    if has_more and notifications:
        import base64

        cursor_data = {
            "id": str(notifications[-1].id),
            "created_at": notifications[-1].created_at.isoformat(),
        }
        next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()

    # Serialize notifications
    notification_responses = [_serialize_notification(n) for n in notifications]

    return {
        "data": notification_responses,
        "items": notification_responses,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
        "unread_count": unread_count,
    }


@router.post(
    "/mark-read",
    response_model=NotificationMarkReadResponse,
    summary="Mark notifications as read",
)
@limiter.limit("60/minute")
async def mark_notifications_read(
    request: Request,
    payload: NotificationMarkReadRequest,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
):
    user_id = _extract_user_id(current_user)

    try:
        user_uuid = UUID(user_id)
        notification_uuids = [UUID(nid) for nid in payload.notification_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    # Get notifications belonging to user
    notifications = (
        db.query(Notification)
        .filter(
            Notification.id.in_(notification_uuids), Notification.user_id == user_uuid
        )
        .all()
    )

    # Mark as read
    marked_count = 0
    for notification in notifications:
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = now_sao_paulo()
            marked_count += 1

    db.commit()

    # Invalidate unread count cache
    redis = await _get_redis_client()
    if redis:
        try:
            await redis.delete(f"user:unread_count:{user_id}")
        except Exception as e:
            logger.warning(f"Redis delete error: {e}")

    return {"marked_count": marked_count, "success": True}


@router.get("/unread-count", summary="Get unread notification count")
@limiter.limit("100/minute")
async def get_unread_count(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db=Depends(get_db),
):
    user_id = _extract_user_id(current_user)

    # Try Redis cache first
    redis = await _get_redis_client()
    cache_key = f"user:unread_count:{user_id}"

    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                return {"count": int(cached)}
        except Exception as e:
            logger.warning(f"Redis get error: {e}")

    # Cache miss - fetch from DB
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    count = (
        db.query(func.count(Notification.id))
        .filter(Notification.user_id == user_uuid, Notification.is_read.is_(False))
        .scalar()
    )

    # Cache the result
    if redis:
        try:
            await redis.setex(cache_key, CACHE_TTL_UNREAD_COUNT, str(count))
        except Exception as e:
            logger.warning(f"Redis set error: {e}")

    return {"count": count}
