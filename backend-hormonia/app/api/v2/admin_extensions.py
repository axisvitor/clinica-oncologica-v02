"""
Admin Extensions API v2 - Dead Letter Queue & Audit Management
Comprehensive admin endpoints for system monitoring, troubleshooting, and compliance.

Features:
- Dead Letter Queue (DLQ) management for failed operations
- Comprehensive audit log management for compliance (HIPAA, LGPD)
- Cursor-based pagination on all list endpoints
- Redis caching with SHORT TTLs (critical operations)
- Rate limiting (30-60 req/min)
- Eager loading with joinedload() to prevent N+1
- Field selection (?fields=id,name,email)
- RBAC - Admin-only endpoints (highly sensitive)
- Comprehensive audit trail for all operations

CRITICAL: This module handles sensitive system data and compliance requirements.
All operations must be thoroughly validated and logged.
"""

import logging
import csv
import io
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, asc

from app.database import get_db
from app.models.user import User, UserRole
from app.models.failed_message import FailedMessage, DLQStatus, FailureReason
from app.models.audit_log import AuditLog, AuditEventType
from app.services.dlq_service import DLQService, ErrorCategory
from app.services.audit_service import AuditService
from app.utils.rate_limiter import limiter
from app.infrastructure.cache import cache_response, invalidate_cache
from app.dependencies import get_request_context, RequestContext
from app.schemas.v2.admin_extensions import (
    # DLQ schemas
    DLQItemResponse,
    DLQItemListResponse,
    DLQRetryResponse,
    DLQBulkRetryRequest,
    DLQBulkRetryResponse,
    DLQStatsResponse,
    DLQPurgeRequest,
    DLQPurgeResponse,
    # Audit schemas
    AuditLogResponse,
    AuditLogListResponse,
    AuditLogExportRequest,
    AuditLogExportFormat,
    # Common schemas
    BulkOperationResult,
)
from .dependencies import (
    get_pagination_params,
    get_field_selection,
    create_cursor,
    apply_field_selection,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Cache TTL configurations (SHORT TTLs for critical/time-sensitive data)
CACHE_TTL_DLQ_ITEMS = 120  # 2 minutes for DLQ items
CACHE_TTL_DLQ_STATS = 600  # 10 minutes for DLQ statistics
CACHE_TTL_AUDIT_LOGS = 300  # 5 minutes for audit logs
CACHE_TTL_AUDIT_SINGLE = 900  # 15 minutes for single audit log


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def get_admin_user(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context)
) -> User:
    """
    Dependency to verify admin access.

    Admin Extensions endpoints are HIGHLY SENSITIVE and require admin privileges.

    TODO: Integrate with actual authentication system.
    For now, this is a placeholder that should be replaced.

    Raises:
        HTTPException: If user is not authenticated or not an admin
    """
    # TODO: Get user from session/token
    # This is a placeholder - integrate with your auth system
    user = db.query(User).filter(
        User.role == UserRole.ADMIN,
        User.is_active == True
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for Admin Extensions"
        )

    return user


def _serialize_dlq_item(
    item: FailedMessage,
    fields: Optional[List[str]] = None
) -> dict:
    """
    Serialize DLQ item to dict with optional field selection.

    Args:
        item: FailedMessage instance
        fields: Optional list of fields to include

    Returns:
        Serialized DLQ item dictionary
    """
    data = {
        "id": item.id,
        "patient_id": item.patient_id,
        "phone_number": item.phone_number,
        "message_type": item.message_type,
        "message_content": item.message_content,
        "error_message": item.error_message,
        "error_code": item.error_code,
        "retry_count": item.retry_count,
        "max_retries": item.max_retries,
        "next_retry_at": item.next_retry_at,
        "last_retry_at": item.last_retry_at,
        "status": item.status,
        "resolved_at": item.resolved_at,
        "dlq_metadata": item.dlq_metadata or {},
        "reviewed_by": item.reviewed_by,
        "original_message_id": item.original_message_id,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }

    if fields:
        data = apply_field_selection(data, fields)

    return data


def _serialize_audit_log(
    log: AuditLog,
    fields: Optional[List[str]] = None,
    redact_sensitive: bool = True
) -> dict:
    """
    Serialize audit log to dict with optional field selection and redaction.

    Args:
        log: AuditLog instance
        fields: Optional list of fields to include
        redact_sensitive: Whether to redact sensitive data (default: True)

    Returns:
        Serialized audit log dictionary
    """
    event_data = log.event_metadata or {}

    # Redact sensitive data if requested
    if redact_sensitive:
        sensitive_keys = ["password", "token", "api_key", "secret", "credential"]
        event_data = {
            k: "[REDACTED]" if any(sk in k.lower() for sk in sensitive_keys) else v
            for k, v in event_data.items()
        }

    data = {
        "id": log.id,
        "event_type": log.event_type.value if hasattr(log.event_type, 'value') else str(log.event_type),
        "event_status": log.event_status,
        "user_id": log.user_id,
        "user_email": log.user_email,
        "firebase_uid": log.firebase_uid,
        "ip_address": str(log.ip_address) if log.ip_address else None,
        "user_agent": log.user_agent,
        "resource": log.resource,
        "action": log.action,
        "event_metadata": event_data,
        "message": log.message,
        "error_details": log.error_details,
        "created_at": log.created_at,
        "updated_at": log.updated_at,
    }

    if fields:
        data = apply_field_selection(data, fields)

    return data


async def log_admin_extension_action(
    audit_service: AuditService,
    action: str,
    admin_user: User,
    context: RequestContext,
    additional_data: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log admin extension actions for audit trail.

    Args:
        audit_service: AuditService instance
        action: Action name (e.g., 'dlq_retry', 'audit_export')
        admin_user: Admin user performing action
        context: Request context
        additional_data: Additional data to log
    """
    try:
        event_data = {
            "action": action,
            "admin_user_id": str(admin_user.id),
            "admin_user_email": admin_user.email,
            **(additional_data or {})
        }

        audit_service.log_event(
            event_type=f"admin_extension_{action}",
            event_category="admin_extensions",
            severity="info",
            user_id=admin_user.id,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            event_data=event_data,
            result="success"
        )
    except Exception as e:
        logger.error(f"Failed to log admin extension action {action}: {e}")


# ============================================================================
# DLQ (DEAD LETTER QUEUE) ENDPOINTS
# ============================================================================

@router.get(
    "/dlq",
    response_model=DLQItemListResponse,
    summary="List DLQ Items",
    description="Retrieve paginated list of Dead Letter Queue items with cursor-based pagination and filters."
)
@limiter.limit("60/minute")
@cache_response(ttl=CACHE_TTL_DLQ_ITEMS, key_prefix="admin_ext:dlq:list")
async def list_dlq_items(
    request: Request,
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    fields: Optional[str] = Query(None, description="Comma-separated fields to include"),
    status: Optional[str] = Query(None, description="Filter by status"),
    error_code: Optional[str] = Query(None, description="Filter by error code"),
    patient_id: Optional[UUID] = Query(None, description="Filter by patient"),
    search: Optional[str] = Query(None, description="Search in error messages"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
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

        # Build base query with eager loading
        query = db.query(FailedMessage).options(
            joinedload(FailedMessage.patient),
            joinedload(FailedMessage.reviewer)
        )

        # Apply cursor pagination
        if cursor_data:
            query = query.filter(FailedMessage.id > cursor_data.get("id", 0))

        # Apply filters
        if status:
            query = query.filter(FailedMessage.status == status)

        if error_code:
            query = query.filter(FailedMessage.error_code == error_code)

        if patient_id:
            query = query.filter(FailedMessage.patient_id == patient_id)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    FailedMessage.error_message.ilike(search_pattern),
                    FailedMessage.message_type.ilike(search_pattern)
                )
            )

        # Order by ID for consistent cursor pagination
        query = query.order_by(FailedMessage.id)

        # Fetch limit + 1 to check if there's more
        items = query.limit(limit + 1).all()

        # Check if there are more results
        has_more = len(items) > limit
        if has_more:
            items = items[:limit]

        # Create next cursor
        next_cursor = None
        if has_more and items:
            next_cursor = create_cursor(items[-1].id)

        # Serialize items
        serialized_items = [_serialize_dlq_item(item, field_list) for item in items]

        # Log action
        audit_service = AuditService(db)
        await log_admin_extension_action(
            audit_service, "dlq_list", admin_user, context,
            additional_data={"count": len(items), "filters": {"status": status, "patient_id": str(patient_id) if patient_id else None}}
        )

        return {
            "data": serialized_items,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": None  # Cursor pagination doesn't include total for performance
        }

    except Exception as e:
        logger.error(f"Error listing DLQ items: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving DLQ items"
        )


@router.get(
    "/dlq/{dlq_id}",
    response_model=DLQItemResponse,
    summary="Get DLQ Item",
    description="Retrieve detailed information about a specific DLQ item. Cached for 2 minutes."
)
@cache_response(ttl=CACHE_TTL_DLQ_ITEMS, key_prefix="admin_ext:dlq:item")
async def get_dlq_item(
    dlq_id: UUID,
    fields: Optional[str] = Query(None, description="Comma-separated fields to include"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """
    Get detailed information about a specific DLQ item.

    Includes:
    - Full error details
    - Retry history
    - Patient information (via eager loading)
    - Metadata

    Args:
        dlq_id: DLQ item UUID
        fields: Optional field selection

    Returns:
        Detailed DLQ item information
    """
    try:
        # Query with eager loading
        item = db.query(FailedMessage).options(
            joinedload(FailedMessage.patient),
            joinedload(FailedMessage.reviewer),
            joinedload(FailedMessage.original_message)
        ).filter(FailedMessage.id == dlq_id).first()

        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DLQ item not found"
            )

        # Parse field selection
        field_list = get_field_selection(fields) if fields else None

        # Log action
        audit_service = AuditService(db)
        await log_admin_extension_action(
            audit_service, "dlq_view", admin_user, context,
            additional_data={"dlq_id": str(dlq_id)}
        )

        return _serialize_dlq_item(item, field_list)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving DLQ item {dlq_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving DLQ item"
        )


@router.post(
    "/dlq/{dlq_id}/retry",
    response_model=DLQRetryResponse,
    summary="Retry DLQ Item",
    description="Manually retry a failed operation from the DLQ."
)
@limiter.limit("30/minute")
async def retry_dlq_item(
    request: Request,
    dlq_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
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
        dlq_service = DLQService(db)

        # Attempt retry
        success, error_message = dlq_service.retry_message(dlq_id, manual=True)

        # Invalidate cache
        invalidate_cache(f"admin_ext:dlq:item:{dlq_id}")
        invalidate_cache("admin_ext:dlq:list")
        invalidate_cache("admin_ext:dlq:stats")

        # Log action
        audit_service = AuditService(db)
        await log_admin_extension_action(
            audit_service, "dlq_retry", admin_user, context,
            additional_data={
                "dlq_id": str(dlq_id),
                "success": success,
                "error": error_message
            }
        )

        logger.info(f"Admin {admin_user.email} retried DLQ item {dlq_id}: {'success' if success else 'failed'}")

        return {
            "success": success,
            "message": "Message reprocessed successfully" if success else "Failed to reprocess message",
            "dlq_id": dlq_id,
            "error": error_message
        }

    except Exception as e:
        logger.error(f"Error retrying DLQ item {dlq_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrying DLQ item"
        )


@router.post(
    "/dlq/retry-bulk",
    response_model=DLQBulkRetryResponse,
    summary="Bulk Retry DLQ Items",
    description="Retry multiple DLQ items at once (max 50)."
)
@limiter.limit("10/minute")
async def bulk_retry_dlq_items(
    request: Request,
    bulk_data: DLQBulkRetryRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
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
                detail="Maximum 50 DLQ items per bulk retry"
            )

        dlq_service = DLQService(db)
        successful = 0
        failed = 0
        errors = []

        # Process each item
        for dlq_id in bulk_data.dlq_ids:
            try:
                success, error_message = dlq_service.retry_message(dlq_id, manual=True)

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
            audit_service, "dlq_bulk_retry", admin_user, context,
            additional_data={
                "total": len(bulk_data.dlq_ids),
                "successful": successful,
                "failed": failed
            }
        )

        logger.info(f"Admin {admin_user.email} bulk retried {len(bulk_data.dlq_ids)} DLQ items: {successful} success, {failed} failed")

        return {
            "success": failed == 0,
            "total_requested": len(bulk_data.dlq_ids),
            "successful": successful,
            "failed": failed,
            "errors": errors,
            "message": f"Bulk retry completed: {successful} successful, {failed} failed"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk retry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in bulk retry: {str(e)}"
        )


@router.delete(
    "/dlq/{dlq_id}",
    response_model=DLQRetryResponse,
    summary="Delete DLQ Item",
    description="Mark DLQ item as resolved/discarded (soft delete)."
)
@limiter.limit("30/minute")
async def delete_dlq_item(
    request: Request,
    dlq_id: UUID,
    reason: str = Query(..., description="Reason for deletion"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
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
        dlq_service = DLQService(db)

        # Discard message
        success = dlq_service.discard_message(dlq_id, reason)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DLQ item not found"
            )

        # Invalidate caches
        invalidate_cache(f"admin_ext:dlq:item:{dlq_id}")
        invalidate_cache("admin_ext:dlq:list")
        invalidate_cache("admin_ext:dlq:stats")

        # Log action
        audit_service = AuditService(db)
        await log_admin_extension_action(
            audit_service, "dlq_delete", admin_user, context,
            additional_data={"dlq_id": str(dlq_id), "reason": reason}
        )

        logger.info(f"Admin {admin_user.email} deleted DLQ item {dlq_id}: {reason}")

        return {
            "success": True,
            "message": "DLQ item deleted successfully",
            "dlq_id": dlq_id,
            "error": None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting DLQ item {dlq_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting DLQ item"
        )


@router.get(
    "/dlq/stats",
    response_model=DLQStatsResponse,
    summary="Get DLQ Statistics",
    description="Get comprehensive DLQ statistics. Cached for 10 minutes."
)
@cache_response(ttl=CACHE_TTL_DLQ_STATS, key_prefix="admin_ext:dlq:stats")
async def get_dlq_statistics(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
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
        dlq_service = DLQService(db)
        stats = dlq_service.get_stats()

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
            detail="Error retrieving DLQ statistics"
        )


@router.delete(
    "/dlq/purge",
    response_model=DLQPurgeResponse,
    summary="Purge Old DLQ Items",
    description="Purge DLQ items older than specified days (default: 90 days)."
)
@limiter.limit("5/hour")
async def purge_old_dlq_items(
    request: Request,
    days: int = Query(90, ge=30, le=365, description="Delete items older than this many days"),
    dry_run: bool = Query(False, description="Preview without deleting"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
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
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Query old items (only safe statuses)
        safe_statuses = ['resolved', 'discarded', 'max_retries_exceeded']
        query = db.query(FailedMessage).filter(
            FailedMessage.created_at < cutoff_date,
            FailedMessage.status.in_(safe_statuses)
        )

        count = query.count()

        if not dry_run and count > 0:
            # Delete items
            query.delete(synchronize_session=False)
            db.commit()

            # Invalidate caches
            invalidate_cache("admin_ext:dlq:list")
            invalidate_cache("admin_ext:dlq:stats")

        # Log action
        audit_service = AuditService(db)
        await log_admin_extension_action(
            audit_service, "dlq_purge", admin_user, context,
            additional_data={
                "days": days,
                "count": count,
                "dry_run": dry_run,
                "cutoff_date": cutoff_date.isoformat()
            }
        )

        logger.warning(f"Admin {admin_user.email} {'previewed' if dry_run else 'purged'} {count} DLQ items older than {days} days")

        return {
            "success": True,
            "message": f"{'Would delete' if dry_run else 'Deleted'} {count} DLQ items",
            "count": count,
            "days": days,
            "cutoff_date": cutoff_date,
            "dry_run": dry_run
        }

    except Exception as e:
        logger.error(f"Error purging DLQ items: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error purging DLQ items"
        )


# ============================================================================
# AUDIT LOG MANAGEMENT ENDPOINTS
# ============================================================================

@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    summary="List Audit Logs",
    description="Retrieve paginated list of audit logs with cursor-based pagination and comprehensive filters."
)
@limiter.limit("60/minute")
@cache_response(ttl=CACHE_TTL_AUDIT_LOGS, key_prefix="admin_ext:audit:list")
async def list_audit_logs(
    request: Request,
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    fields: Optional[str] = Query(None, description="Comma-separated fields to include"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    event_status: Optional[str] = Query(None, description="Filter by status (success/failure)"),
    user_id: Optional[UUID] = Query(None, description="Filter by user"),
    user_email: Optional[str] = Query(None, description="Filter by user email"),
    ip_address: Optional[str] = Query(None, description="Filter by IP address"),
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    search: Optional[str] = Query(None, description="Search in messages"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """
    List audit logs with cursor pagination and comprehensive filters.

    Supports filtering by:
    - Event type (login, logout, access_denied, etc.)
    - Event status (success, failure, error)
    - User ID or email
    - IP address
    - Date range
    - Search in messages

    Returns:
        Paginated list of audit logs with cursor for next page
    """
    try:
        # Parse pagination params
        pagination = get_pagination_params(cursor, limit)
        cursor_data = pagination["cursor_data"]

        # Parse field selection
        field_list = get_field_selection(fields) if fields else None

        # Build base query
        query = db.query(AuditLog)

        # Apply cursor pagination
        if cursor_data:
            query = query.filter(AuditLog.id > cursor_data.get("id", 0))

        # Apply filters
        if event_type:
            query = query.filter(AuditLog.event_type == event_type)

        if event_status:
            query = query.filter(AuditLog.event_status == event_status)

        if user_id:
            query = query.filter(AuditLog.user_id == str(user_id))

        if user_email:
            query = query.filter(AuditLog.user_email.ilike(f"%{user_email}%"))

        if ip_address:
            query = query.filter(AuditLog.ip_address == ip_address)

        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)

        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    AuditLog.message.ilike(search_pattern),
                    AuditLog.action.ilike(search_pattern),
                    AuditLog.resource.ilike(search_pattern)
                )
            )

        # Order by created_at DESC (most recent first)
        query = query.order_by(desc(AuditLog.created_at))

        # Fetch limit + 1 to check if there's more
        logs = query.limit(limit + 1).all()

        # Check if there are more results
        has_more = len(logs) > limit
        if has_more:
            logs = logs[:limit]

        # Create next cursor
        next_cursor = None
        if has_more and logs:
            next_cursor = create_cursor(logs[-1].id)

        # Serialize logs
        serialized_logs = [_serialize_audit_log(log, field_list) for log in logs]

        # Log action
        audit_service = AuditService(db)
        await log_admin_extension_action(
            audit_service, "audit_list", admin_user, context,
            additional_data={"count": len(logs), "filters": {
                "event_type": event_type,
                "user_email": user_email,
                "ip_address": ip_address
            }}
        )

        return {
            "data": serialized_logs,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": None  # Cursor pagination doesn't include total for performance
        }

    except Exception as e:
        logger.error(f"Error listing audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving audit logs"
        )


@router.get(
    "/audit-logs/{log_id}",
    response_model=AuditLogResponse,
    summary="Get Audit Log",
    description="Retrieve detailed information about a specific audit log. Cached for 15 minutes."
)
@cache_response(ttl=CACHE_TTL_AUDIT_SINGLE, key_prefix="admin_ext:audit:item")
async def get_audit_log(
    log_id: UUID,
    fields: Optional[str] = Query(None, description="Comma-separated fields to include"),
    redact_sensitive: bool = Query(True, description="Redact sensitive data"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """
    Get detailed information about a specific audit log.

    Includes:
    - Full event details
    - User information
    - Network information (IP, user agent)
    - Event metadata
    - Sensitive data redaction (configurable)

    Args:
        log_id: Audit log UUID
        fields: Optional field selection
        redact_sensitive: Whether to redact sensitive data (default: True)

    Returns:
        Detailed audit log information
    """
    try:
        log = db.query(AuditLog).filter(AuditLog.id == log_id).first()

        if not log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit log not found"
            )

        # Parse field selection
        field_list = get_field_selection(fields) if fields else None

        # Log action
        audit_service = AuditService(db)
        await log_admin_extension_action(
            audit_service, "audit_view", admin_user, context,
            additional_data={"log_id": str(log_id)}
        )

        return _serialize_audit_log(log, field_list, redact_sensitive)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving audit log {log_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving audit log"
        )


@router.post(
    "/audit-logs/export",
    summary="Export Audit Logs",
    description="Export audit logs to CSV or JSON format with filters."
)
@limiter.limit("10/hour")
async def export_audit_logs(
    request: Request,
    export_request: AuditLogExportRequest,
    event_type: Optional[str] = Query(None),
    event_status: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """
    Export audit logs to CSV or JSON format.

    CRITICAL: This exports sensitive compliance data. All exports are logged.

    Supports:
    - CSV or JSON format
    - Field selection
    - Comprehensive filters
    - Automatic sensitive data redaction
    - HIPAA/LGPD compliance

    Args:
        export_request: Export configuration (format, fields)
        event_type: Filter by event type
        event_status: Filter by status
        user_email: Filter by user email
        start_date: Filter from date
        end_date: Filter to date

    Returns:
        Streaming response with exported data
    """
    try:
        # Build query with filters
        query = db.query(AuditLog)

        if event_type:
            query = query.filter(AuditLog.event_type == event_type)

        if event_status:
            query = query.filter(AuditLog.event_status == event_status)

        if user_email:
            query = query.filter(AuditLog.user_email.ilike(f"%{user_email}%"))

        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)

        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        # Order by created_at
        query = query.order_by(desc(AuditLog.created_at))

        # Fetch logs (limit to 10000 for safety)
        logs = query.limit(10000).all()

        # Determine fields
        all_fields = [
            "id", "event_type", "event_status", "user_id", "user_email",
            "firebase_uid", "ip_address", "user_agent", "resource", "action",
            "event_metadata", "message", "error_details", "created_at"
        ]
        fields_to_export = export_request.fields if export_request.fields else all_fields

        # Log action
        audit_service = AuditService(db)
        await log_admin_extension_action(
            audit_service, "audit_export", admin_user, context,
            additional_data={
                "format": export_request.format,
                "count": len(logs),
                "fields": fields_to_export,
                "filters": {
                    "event_type": event_type,
                    "user_email": user_email,
                    "date_range": f"{start_date} to {end_date}" if start_date or end_date else None
                }
            }
        )

        logger.warning(f"Admin {admin_user.email} exported {len(logs)} audit logs in {export_request.format} format")

        if export_request.format == AuditLogExportFormat.CSV:
            # Generate CSV
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=fields_to_export)
            writer.writeheader()

            for log in logs:
                row_data = _serialize_audit_log(log, redact_sensitive=export_request.redact_sensitive)
                row = {}
                for field in fields_to_export:
                    value = row_data.get(field)
                    if isinstance(value, (datetime)):
                        value = value.isoformat()
                    elif isinstance(value, (dict, list)):
                        value = json.dumps(value)
                    elif isinstance(value, UUID):
                        value = str(value)
                    row[field] = value
                writer.writerow(row)

            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=audit_logs_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
                }
            )

        else:  # JSON
            data = []
            for log in logs:
                row_data = _serialize_audit_log(log, redact_sensitive=export_request.redact_sensitive)
                # Filter fields
                filtered_data = {k: v for k, v in row_data.items() if k in fields_to_export}
                # Convert datetime to ISO format
                for k, v in filtered_data.items():
                    if isinstance(v, datetime):
                        filtered_data[k] = v.isoformat()
                    elif isinstance(v, UUID):
                        filtered_data[k] = str(v)
                data.append(filtered_data)

            return Response(
                content=json.dumps(data, indent=2),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename=audit_logs_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
                }
            )

    except Exception as e:
        logger.error(f"Error exporting audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting audit logs: {str(e)}"
        )
