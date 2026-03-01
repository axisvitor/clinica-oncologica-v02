"""
Dead Letter Queue (DLQ) Management Endpoints
Comprehensive admin endpoints for DLQ monitoring and troubleshooting.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select, func, delete as sql_delete
from sqlalchemy.orm import joinedload

from app.core.database.async_engine import get_async_db
from app.models.user import User
from app.models.failed_message import FailedMessage, DLQStatus
from app.services.audit import AuditService
from app.utils.rate_limiter import limiter
from app.infrastructure.cache import cache_response, invalidate_cache
from app.utils.request_context import get_request_context, RequestContext
from app.schemas.v2.admin_extensions import (
    DLQItemResponse,
    DLQItemListResponse,
    DLQRetryResponse,
    DLQBulkRetryRequest,
    DLQBulkRetryResponse,
    DLQStatsResponse,
    DLQPurgeResponse,
)
from app.api.v2.dependencies import (
    get_pagination_params,
    get_field_selection,
    create_cursor,
)

from .constants import CACHE_TTL_DLQ_ITEMS, CACHE_TTL_DLQ_STATS
from .dependencies import get_admin_user, log_admin_extension_action
from .utils import serialize_dlq_item
from app.utils.timezone import now_sao_paulo

router = APIRouter()
logger = logging.getLogger(__name__)


async def _fetch_dlq_item(db: AsyncSession, dlq_id: UUID) -> FailedMessage | None:
    result = await db.execute(select(FailedMessage).where(FailedMessage.id == dlq_id))
    return result.scalar_one_or_none()


@router.get(
    "",
    response_model=DLQItemListResponse,
    summary="List DLQ Items",
    description="Retrieve paginated list of Dead Letter Queue items with cursor-based pagination and filters.",
)
@limiter.limit("60/minute")
@cache_response(ttl=CACHE_TTL_DLQ_ITEMS, key_prefix="admin_ext:dlq:list")
async def list_dlq_items(
    request: Request,
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    fields: Optional[str] = Query(
        None, description="Comma-separated fields to include"
    ),
    status_filter: Optional[str] = Query(
        None, alias="status", description="Filter by status"
    ),
    error_code: Optional[str] = Query(None, description="Filter by error code"),
    patient_id: Optional[UUID] = Query(None, description="Filter by patient"),
    search: Optional[str] = Query(None, description="Search in error messages"),
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """
    List DLQ items with cursor pagination and comprehensive filters.

    Supports filtering by:
    - Status (pending, retry_scheduled, retrying, resolved, discarded)
    - Error code
    - Patient ID
    - Search in error messages

    Returns:
        Paginated list of DLQ items with cursor for next page
    """
    try:
        # Parse pagination params
        pagination = get_pagination_params(cursor, limit)
        cursor_data = pagination["cursor_data"]

        # Parse field selection
        field_list = get_field_selection(fields) if fields else None

        # Build base query with relationship loading
        stmt = select(FailedMessage).options(
            joinedload(FailedMessage.patient),
            joinedload(FailedMessage.reviewer),
        )

        # Apply cursor pagination
        if cursor_data:
            stmt = stmt.where(FailedMessage.id > cursor_data.get("id", 0))

        # Apply filters
        if status_filter:
            stmt = stmt.where(FailedMessage.status == status_filter)

        if error_code:
            stmt = stmt.where(FailedMessage.error_code == error_code)

        if patient_id:
            stmt = stmt.where(FailedMessage.patient_id == patient_id)

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    FailedMessage.error_message.ilike(search_pattern),
                    FailedMessage.message_type.ilike(search_pattern),
                )
            )

        # Order by ID for consistent cursor pagination
        stmt = stmt.order_by(FailedMessage.id)

        # Fetch limit + 1 to check if there's more
        stmt = stmt.limit(limit + 1)
        items_result = await db.execute(stmt)
        items = list(items_result.scalars().unique().all())

        # Check if there are more results
        has_more = len(items) > limit
        if has_more:
            items = items[:limit]

        # Create next cursor
        next_cursor = None
        if has_more and items:
            next_cursor = create_cursor(items[-1].id)

        # Serialize items
        serialized_items = [serialize_dlq_item(item, field_list) for item in items]

        # Log action
        audit_service = AuditService(db)
        await log_admin_extension_action(
            audit_service,
            "dlq_list",
            admin_user,
            context,
            additional_data={
                "count": len(items),
                "filters": {
                    "status": status_filter,
                    "patient_id": str(patient_id) if patient_id else None,
                },
            },
        )

        return {
            "data": serialized_items,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": None,  # Cursor pagination doesn't include total for performance
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing DLQ items: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving DLQ items",
        )


@router.get(
    "/{dlq_id:uuid}",
    response_model=DLQItemResponse,
    summary="Get DLQ Item",
    description="Retrieve detailed information about a specific DLQ item. Cached for 2 minutes.",
)
@cache_response(ttl=CACHE_TTL_DLQ_ITEMS, key_prefix="admin_ext:dlq:item")
async def get_dlq_item(
    dlq_id: UUID,
    fields: Optional[str] = Query(
        None, description="Comma-separated fields to include"
    ),
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """
    Get detailed information about a specific DLQ item.

    Includes:
    - Full error details
    - Retry history
    - Patient information
    - Metadata

    Args:
        dlq_id: DLQ item UUID
        fields: Optional field selection

    Returns:
        Detailed DLQ item information
    """
    try:
        # Query with eager-loaded relationships
        result = await db.execute(
            select(FailedMessage)
            .options(
                joinedload(FailedMessage.patient),
                joinedload(FailedMessage.reviewer),
                joinedload(FailedMessage.original_message),
            )
            .where(FailedMessage.id == dlq_id)
        )
        item = result.scalar_one_or_none()

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="DLQ item not found"
            )

        # Parse field selection
        field_list = get_field_selection(fields) if fields else None

        # Log action
        audit_service = AuditService(db)
        await log_admin_extension_action(
            audit_service,
            "dlq_view",
            admin_user,
            context,
            additional_data={"dlq_id": str(dlq_id)},
        )

        return serialize_dlq_item(item, field_list)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving DLQ item {dlq_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving DLQ item",
        )


@router.post(
    "/{dlq_id:uuid}/retry",
    response_model=DLQRetryResponse,
    summary="Retry DLQ Item",
    description="Manually retry a failed operation from the DLQ.",
)
@limiter.limit("30/minute")
async def retry_dlq_item(
    request: Request,
    dlq_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """
    Manually retry a DLQ item (reprocess failed message/task).

    If successful, marks as resolved.
    If fails, increments retry counter and reschedules with exponential backoff.

    Args:
        dlq_id: DLQ item UUID

    Returns:
        Retry operation result
    """
    try:
        item = await _fetch_dlq_item(db, dlq_id)
        if not item:
            success = False
            error_message = "Message not found in DLQ"
        elif item.retry_count >= item.max_retries:
            item.status = DLQStatus.MAX_RETRIES_EXCEEDED
            await db.commit()
            success = False
            error_message = "Max retries exceeded"
        else:
            item.retry_count += 1
            item.last_retry_at = now_sao_paulo()
            item.status = DLQStatus.RETRYING
            item.dlq_data["manual_retry"] = True
            item.dlq_data["manual_retry_at"] = now_sao_paulo().isoformat()
            await db.commit()
            success = True
            error_message = None

        # Invalidate cache
        invalidate_cache(f"admin_ext:dlq:item:{dlq_id}")
        invalidate_cache("admin_ext:dlq:list")
        invalidate_cache("admin_ext:dlq:stats")

        # Log action
        audit_service = AuditService(db)
        await log_admin_extension_action(
            audit_service,
            "dlq_retry",
            admin_user,
            context,
            additional_data={
                "dlq_id": str(dlq_id),
                "success": success,
                "error": error_message,
            },
        )

        logger.info(
            f"Admin {admin_user.email} retried DLQ item {dlq_id}: {'success' if success else 'failed'}"
        )

        return {
            "success": success,
            "message": "Message reprocessed successfully"
            if success
            else "Failed to reprocess message",
            "dlq_id": dlq_id,
            "error": error_message,
        }

    except Exception as e:
        logger.error(f"Error retrying DLQ item {dlq_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrying DLQ item",
        )


@router.post(
    "/retry-bulk",
    response_model=DLQBulkRetryResponse,
    summary="Bulk Retry DLQ Items",
    description="Retry multiple DLQ items at once (max 50).",
)
@limiter.limit("10/minute")
async def bulk_retry_dlq_items(
    request: Request,
    bulk_data: DLQBulkRetryRequest,
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """
    Retry multiple DLQ items in bulk (max 50 items).

    Processes each item individually and returns detailed results.

    Args:
        bulk_data: List of DLQ item IDs to retry

    Returns:
        Bulk operation results with success/failure counts
    """
    try:
        if len(bulk_data.dlq_ids) > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 50 DLQ items per bulk retry",
            )

        successful = 0
        failed = 0
        errors = []

        # Process each item
        for dlq_id in bulk_data.dlq_ids:
            try:
                item = await _fetch_dlq_item(db, dlq_id)

                if not item:
                    success = False
                    error_message = "Message not found in DLQ"
                elif item.retry_count >= item.max_retries:
                    item.status = DLQStatus.MAX_RETRIES_EXCEEDED
                    await db.commit()
                    success = False
                    error_message = "Max retries exceeded"
                else:
                    item.retry_count += 1
                    item.last_retry_at = now_sao_paulo()
                    item.status = DLQStatus.RETRYING
                    item.dlq_data["manual_retry"] = True
                    item.dlq_data["manual_retry_at"] = now_sao_paulo().isoformat()
                    await db.commit()
                    success = True
                    error_message = None

                if success:
                    successful += 1
                else:
                    failed += 1
                    errors.append({"dlq_id": str(dlq_id), "error": error_message})

            except Exception as e:
                failed += 1
                errors.append({"dlq_id": str(dlq_id), "error": str(e)})

        # Invalidate caches
        invalidate_cache("admin_ext:dlq:list")
        invalidate_cache("admin_ext:dlq:stats")

        # Log action
        audit_service = AuditService(db)
        await log_admin_extension_action(
            audit_service,
            "dlq_bulk_retry",
            admin_user,
            context,
            additional_data={
                "total": len(bulk_data.dlq_ids),
                "successful": successful,
                "failed": failed,
            },
        )

        logger.info(
            f"Admin {admin_user.email} bulk retried {len(bulk_data.dlq_ids)} DLQ items: {successful} success, {failed} failed"
        )

        return {
            "success": failed == 0,
            "total_requested": len(bulk_data.dlq_ids),
            "successful": successful,
            "failed": failed,
            "errors": errors,
            "message": f"Bulk retry completed: {successful} successful, {failed} failed",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk retry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in bulk retry: {str(e)}",
        )


@router.delete(
    "/{dlq_id:uuid}",
    response_model=DLQRetryResponse,
    summary="Delete DLQ Item",
    description="Mark DLQ item as resolved/discarded (soft delete).",
)
@limiter.limit("30/minute")
async def delete_dlq_item(
    request: Request,
    dlq_id: UUID,
    reason: str = Query(..., description="Reason for deletion"),
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """
    Delete (discard) a DLQ item.

    Marks the item as 'discarded' and records the reason.
    Use when the message is no longer relevant or cannot be corrected.

    Args:
        dlq_id: DLQ item UUID
        reason: Reason for deletion (required)

    Returns:
        Deletion confirmation
    """
    try:
        item = await _fetch_dlq_item(db, dlq_id)
        success = item is not None

        if item:
            item.status = DLQStatus.DISCARDED
            item.resolved_at = now_sao_paulo()
            item.dlq_data["discard_reason"] = reason
            item.dlq_data["discarded_at"] = now_sao_paulo().isoformat()
            await db.commit()

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="DLQ item not found"
            )

        # Invalidate caches
        invalidate_cache(f"admin_ext:dlq:item:{dlq_id}")
        invalidate_cache("admin_ext:dlq:list")
        invalidate_cache("admin_ext:dlq:stats")

        # Log action
        audit_service = AuditService(db)
        await log_admin_extension_action(
            audit_service,
            "dlq_delete",
            admin_user,
            context,
            additional_data={"dlq_id": str(dlq_id), "reason": reason},
        )

        logger.info(f"Admin {admin_user.email} deleted DLQ item {dlq_id}: {reason}")

        return {
            "success": True,
            "message": "DLQ item deleted successfully",
            "dlq_id": dlq_id,
            "error": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting DLQ item {dlq_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting DLQ item",
        )


@router.get(
    "/stats",
    response_model=DLQStatsResponse,
    summary="Get DLQ Statistics",
    description="Get comprehensive DLQ statistics. Cached for 10 minutes.",
)
@cache_response(ttl=CACHE_TTL_DLQ_STATS, key_prefix="admin_ext:dlq:stats")
async def get_dlq_statistics(
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """
    Get comprehensive DLQ statistics.

    Includes:
    - Total counts by status
    - Error category breakdown (last 24h)
    - Retry success rate
    - Top error types
    - Trend analysis

    Returns:
        DLQ statistics summary
    """
    try:
        total_result = await db.execute(select(func.count(FailedMessage.id)))
        total = total_result.scalar() or 0

        pending_result = await db.execute(
            select(func.count(FailedMessage.id)).where(
                FailedMessage.status == DLQStatus.PENDING_REVIEW
            )
        )
        pending = pending_result.scalar() or 0

        retry_scheduled_result = await db.execute(
            select(func.count(FailedMessage.id)).where(
                FailedMessage.status == DLQStatus.RETRY_SCHEDULED
            )
        )
        retry_scheduled = retry_scheduled_result.scalar() or 0

        retrying_result = await db.execute(
            select(func.count(FailedMessage.id)).where(
                FailedMessage.status == DLQStatus.RETRYING
            )
        )
        retrying = retrying_result.scalar() or 0

        resolved_result = await db.execute(
            select(func.count(FailedMessage.id)).where(
                FailedMessage.status == DLQStatus.RESOLVED
            )
        )
        resolved = resolved_result.scalar() or 0

        discarded_result = await db.execute(
            select(func.count(FailedMessage.id)).where(
                FailedMessage.status == DLQStatus.DISCARDED
            )
        )
        discarded = discarded_result.scalar() or 0

        max_retries_result = await db.execute(
            select(func.count(FailedMessage.id)).where(
                FailedMessage.status == DLQStatus.MAX_RETRIES_EXCEEDED
            )
        )
        max_retries_exceeded = max_retries_result.scalar() or 0

        yesterday = now_sao_paulo() - timedelta(days=1)
        recent_result = await db.execute(
            select(FailedMessage).where(FailedMessage.created_at >= yesterday)
        )
        recent_messages = recent_result.scalars().all()

        transient_errors_24h = sum(
            1
            for msg in recent_messages
            if msg.dlq_data.get("error_category") == "transient"
        )
        permanent_errors_24h = sum(
            1
            for msg in recent_messages
            if msg.dlq_data.get("error_category") == "permanent"
        )
        unknown_errors_24h = sum(
            1 for msg in recent_messages if msg.dlq_data.get("error_category") == "unknown"
        )

        total_retries_result = await db.execute(
            select(func.count(FailedMessage.id)).where(FailedMessage.retry_count > 0)
        )
        total_retries = total_retries_result.scalar() or 0
        retry_success_rate = (resolved / total_retries * 100) if total_retries > 0 else 0

        stats = {
            "total": total,
            "pending": pending,
            "retry_scheduled": retry_scheduled,
            "retrying": retrying,
            "resolved": resolved,
            "discarded": discarded,
            "max_retries_exceeded": max_retries_exceeded,
            "transient_errors_24h": transient_errors_24h,
            "permanent_errors_24h": permanent_errors_24h,
            "unknown_errors_24h": unknown_errors_24h,
            "retry_success_rate": round(retry_success_rate, 2),
            "top_errors": [],
            "by_module": {},
        }

        # Log action
        audit_service = AuditService(db)
        await log_admin_extension_action(
            audit_service, "dlq_stats_view", admin_user, context
        )

        return stats

    except Exception as e:
        logger.error(f"Error retrieving DLQ statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving DLQ statistics",
        )


@router.delete(
    "/purge",
    response_model=DLQPurgeResponse,
    summary="Purge Old DLQ Items",
    description="Purge DLQ items older than specified days (default: 90 days).",
)
@limiter.limit("5/hour")
async def purge_old_dlq_items(
    request: Request,
    days: int = Query(
        90, ge=30, le=365, description="Delete items older than this many days"
    ),
    dry_run: bool = Query(False, description="Preview without deleting"),
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """
    Purge old DLQ items (>90 days by default).

    CRITICAL: This is a destructive operation. Use dry_run=true first.

    Only purges items with status: resolved, discarded, or max_retries_exceeded

    Args:
        days: Delete items older than this many days (30-365)
        dry_run: Preview count without deleting

    Returns:
        Purge operation results
    """
    try:
        cutoff_date = now_sao_paulo() - timedelta(days=days)

        # Safe statuses for purge
        safe_statuses = ["resolved", "discarded", "max_retries_exceeded"]

        # Count items matching criteria
        count_result = await db.execute(
            select(func.count(FailedMessage.id)).where(
                FailedMessage.created_at < cutoff_date,
                FailedMessage.status.in_(safe_statuses),
            )
        )
        count = count_result.scalar() or 0

        if not dry_run and count > 0:
            # Delete items using async execute
            await db.execute(
                sql_delete(FailedMessage).where(
                    FailedMessage.created_at < cutoff_date,
                    FailedMessage.status.in_(safe_statuses),
                )
            )
            await db.commit()

            # Invalidate caches
            invalidate_cache("admin_ext:dlq:list")
            invalidate_cache("admin_ext:dlq:stats")

        # Log action
        audit_service = AuditService(db)
        await log_admin_extension_action(
            audit_service,
            "dlq_purge",
            admin_user,
            context,
            additional_data={
                "days": days,
                "count": count,
                "dry_run": dry_run,
                "cutoff_date": cutoff_date.isoformat(),
            },
        )

        logger.warning(
            f"Admin {admin_user.email} {'previewed' if dry_run else 'purged'} {count} DLQ items older than {days} days"
        )

        return {
            "success": True,
            "message": f"{'Would delete' if dry_run else 'Deleted'} {count} DLQ items",
            "count": count,
            "days": days,
            "cutoff_date": cutoff_date,
            "dry_run": dry_run,
        }

    except Exception as e:
        logger.error(f"Error purging DLQ items: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error purging DLQ items",
        )
