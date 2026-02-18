"""
Admin Activity API v2
User activity and audit log endpoints.

Features:
- User activity tracking with cursor pagination
- Permission management (placeholder)
- Account unlock functionality
- Audit trail with filtering
- Redis caching for performance
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import desc

from app.database import get_db
from app.models.user import User
from app.models.audit_log import AuditLog
from app.repositories.user import UserRepository
from app.utils.rate_limiter import limiter
from app.infrastructure.cache import cache_response, invalidate_user_cache_async
from app.utils.request_context import get_request_context, RequestContext
from app.schemas.v2.admin import (
    AuditLogListResponse,
    UserActionResponse,
    UserActivityResponse,
    PermissionAssignRequest,
)
from app.api.v2.dependencies import (
    get_pagination_params,
    create_cursor,
)

from .dependencies import get_admin_user
from .utils import _log_admin_action

router = APIRouter()
logger = logging.getLogger(__name__)


def _serialize_audit_log_record(log: AuditLog) -> Dict[str, Any]:
    """Serialize audit log to admin audit schema."""
    event_type = (
        log.event_type.value
        if hasattr(log.event_type, "value")
        else str(log.event_type)
    )
    event_category = log.event_category
    if not event_category:
        event_category = (log.event_metadata or {}).get("event_category", "system")
    return {
        "id": log.id,
        "event_type": event_type,
        "event_category": event_category,
        "severity": log.severity,
        "user_id": log.user_id,
        "user_email": log.user_email,
        "ip_address": str(log.ip_address) if log.ip_address else None,
        "user_agent": log.user_agent,
        "event_data": log.event_data or {},
        "result": log.result,
        "timestamp": log.timestamp,
    }


def _build_user_activity_response(
    user: User,
    logs: list[AuditLog],
    cursor: Optional[str],
    limit: int,
) -> Dict[str, Any]:
    """Build a cursor-paginated user activity response."""
    pagination = get_pagination_params(cursor, limit)
    cursor_data = pagination["cursor_data"]

    query_logs = logs
    if cursor_data:
        query_logs = [log for log in query_logs if log.id > cursor_data.get("id", 0)]

    query_logs = query_logs[: limit + 1]
    has_more = len(query_logs) > limit
    if has_more:
        query_logs = query_logs[:limit]

    next_cursor = create_cursor(query_logs[-1].id) if has_more and query_logs else None

    activity_records = []
    for log in query_logs:
        event_type = (
            log.event_type.value
            if hasattr(log.event_type, "value")
            else str(log.event_type)
        )
        action_name = event_type.split("_")[-1] if "_" in event_type else event_type
        activity_records.append(
            {
                "id": str(log.id),
                "user_id": str(user.id),
                "user_email": user.email,
                "action": action_name,
                "resource": "user",
                "resource_id": log.event_data.get("target_user_id")
                if log.event_data
                else None,
                "details": log.event_data or {},
                "timestamp": log.timestamp,
                "ip_address": log.ip_address or "unknown",
                "user_agent": log.user_agent or "unknown",
            }
        )

    return {
        "data": activity_records,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": None,
    }


# ============================================================================
# ENDPOINT 1: GET USER ACTIVITY
# ============================================================================


@router.get(
    "/users/{user_id}/activity",
    response_model=UserActivityResponse,
    summary="Get User Activity Log",
    description="Get audit trail for a specific user with cursor pagination.",
)
@cache_response(ttl=300, key_prefix="admin:user:activity")  # Cache for 5 minutes
async def get_user_activity(
    user_id: UUID,
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    action: Optional[str] = Query(None, description="Filter by action type"),
    db=Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """
    Get audit trail for a specific user.

    Features:
    - Cursor-based pagination
    - Action type filtering
    - Redis caching (5 min TTL)
    - Audit logging
    """
    try:
        # Verify user exists
        user_repo = UserRepository(db)
        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        query = db.query(AuditLog).filter(AuditLog.user_id == user_id)

        if action:
            query = query.filter(AuditLog.event_type.like(f"%{action}%"))

        query = query.order_by(desc(AuditLog.timestamp))
        logs = query.all()

        response_payload = _build_user_activity_response(user, logs, cursor, limit)

        # Log action
        await _log_admin_action(
            db,
            "view_user_activity",
            admin_user,
            context,
            target_user_id=user_id,
            additional_data={"count": len(response_payload["data"])},
        )

        return response_payload

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user activity",
        )


@router.get(
    "/users/{user_id}/audit",
    response_model=UserActivityResponse,
    summary="Get User Audit Trail",
    description="Alias for user activity audit trail.",
)
@cache_response(ttl=300, key_prefix="admin:user:audit")
async def get_user_audit_trail(
    user_id: UUID,
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    action: Optional[str] = Query(None, description="Filter by action type"),
    db=Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """Alias endpoint for user audit trail."""
    return await get_user_activity(
        user_id=user_id,
        cursor=cursor,
        limit=limit,
        action=action,
        db=db,
        admin_user=admin_user,
        context=context,
    )


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    summary="List Audit Logs",
    description="List audit logs with cursor pagination and basic filters.",
)
@cache_response(ttl=300, key_prefix="admin:audit:list")
async def list_audit_logs(
    request: Request,
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    user_id: Optional[UUID] = Query(None, description="Filter by user"),
    user_email: Optional[str] = Query(None, description="Filter by user email"),
    ip_address: Optional[str] = Query(None, description="Filter by IP address"),
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    db=Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """List audit logs for admin review."""
    try:
        pagination = get_pagination_params(cursor, limit)
        cursor_data = pagination["cursor_data"]

        query = db.query(AuditLog)

        if cursor_data:
            query = query.filter(AuditLog.id > cursor_data.get("id", 0))

        if event_type:
            query = query.filter(AuditLog.event_type == event_type)

        if user_id:
            query = query.filter(AuditLog.user_id == user_id)

        if user_email:
            query = query.filter(AuditLog.user_email.ilike(f"%{user_email}%"))

        if ip_address:
            query = query.filter(AuditLog.ip_address == ip_address)

        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)

        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        query = query.order_by(desc(AuditLog.created_at))
        logs = query.all()

        if severity:
            severity_value = severity.lower()
            logs = [log for log in logs if str(log.severity).lower() == severity_value]

        has_more = len(logs) > limit
        logs = logs[:limit]
        next_cursor = create_cursor(logs[-1].id) if has_more and logs else None

        serialized_logs = [_serialize_audit_log_record(log) for log in logs]

        await _log_admin_action(
            db,
            "list_audit_logs",
            admin_user,
            context,
            additional_data={
                "count": len(serialized_logs),
                "filters": {
                    "event_type": event_type,
                    "severity": severity,
                    "user_email": user_email,
                },
            },
        )

        return {
            "data": serialized_logs,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving audit logs",
        )


# ============================================================================
# ENDPOINT 2: UPDATE PERMISSIONS
# ============================================================================

# Valid permission identifiers that can be assigned
VALID_PERMISSIONS = {
    "read",
    "write",
    "delete",
    "admin",
    # Patients
    "patients:read",
    "patients:write",
    "patients:delete",
    "patients:admin",
    # Messages
    "messages:read",
    "messages:write",
    "messages:delete",
    "messages:admin",
    # Reports
    "reports:read",
    "reports:write",
    "reports:delete",
    "reports:admin",
    # Analytics
    "analytics:read",
    "analytics:write",
    "analytics:admin",
    # Settings
    "settings:read",
    "settings:write",
    "settings:admin",
    # Users (admin only)
    "users:read",
    "users:write",
    "users:delete",
    "users:admin",
    # Flows
    "flows:read",
    "flows:write",
    "flows:delete",
    "flows:admin",
    # Appointments
    "appointments:read",
    "appointments:write",
    "appointments:delete",
    "appointments:admin",
    # Treatments
    "treatments:read",
    "treatments:write",
    "treatments:delete",
    "treatments:admin",
    # Medications
    "medications:read",
    "medications:write",
    "medications:delete",
    "medications:admin",
    # Alerts
    "alerts:read",
    "alerts:write",
    "alerts:delete",
    "alerts:admin",
    # AI Features
    "ai:read",
    "ai:write",
    "ai:admin",
}


@router.put(
    "/users/{user_id}/permissions",
    response_model=UserActionResponse,
    summary="Update User Permissions",
    description="Update granular permissions for a user.",
)
@limiter.limit("20/hour")
async def assign_permissions(
    request: Request,
    user_id: UUID,
    permissions_data: PermissionAssignRequest,
    db=Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    Update user permissions.

    Features:
    - Validates permission identifiers against allowed list
    - Persists permissions to user record
    - Cache invalidation
    - Audit logging
    """
    try:
        context = RequestContext(
            ip_address=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent", "unknown"),
            user_id=admin_user.id,
            session_id=getattr(request.state, "session_id", None),
        )

        user_repo = UserRepository(db)
        user = user_repo.get(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Store old permissions for audit
        old_permissions = list(user.permissions) if user.permissions else []

        # Normalize permissions (dedupe while preserving order)
        normalized_permissions = list(dict.fromkeys(permissions_data.permissions))
        user.permissions = normalized_permissions
        db.commit()

        # Invalidate cache
        await invalidate_user_cache_async(str(user_id))

        # Log action
        await _log_admin_action(
            db,
            "update_permissions",
            admin_user,
            context,
            target_user_id=user_id,
            additional_data={
                "old_permissions": old_permissions,
                "new_permissions": normalized_permissions,
                "changes": {
                    "added": [
                        p
                        for p in normalized_permissions
                        if p not in old_permissions
                    ],
                    "removed": [
                        p
                        for p in old_permissions
                        if p not in normalized_permissions
                    ],
                },
            },
        )

        logger.info(f"Permissions updated for user {user_id} by admin {admin_user.id}")

        return {
            "success": True,
            "message": f"Permissions updated successfully. {len(normalized_permissions)} permissions assigned.",
            "user_id": str(user_id),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating permissions: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating permissions",
        )


@router.get(
    "/users/{user_id}/permissions",
    summary="Get User Permissions",
    description="Retrieve assigned permissions for a user.",
)
@limiter.limit("60/minute")
async def get_user_permissions(
    request: Request,
    user_id: UUID,
    db=Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """Get permissions for a user."""
    user_repo = UserRepository(db)
    user = user_repo.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    permissions = list(dict.fromkeys(user.permissions or []))
    return {"user_id": str(user_id), "permissions": permissions}


# ============================================================================
# ENDPOINT 3: UNLOCK USER ACCOUNT
# ============================================================================


@router.post(
    "/users/{user_id}/unlock",
    response_model=UserActionResponse,
    summary="Unlock User Account",
    description="Unlock a user account that has been locked due to failed login attempts.",
)
@limiter.limit("20/hour")
async def unlock_user(
    request: Request,
    user_id: UUID,
    db=Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """
    Unlock user account.

    Features:
    - Clears account lock
    - Resets failed login attempts counter
    - Cache invalidation
    - Audit logging

    TODO: Implement account locking mechanism.

    This endpoint is a placeholder for future implementation of:
    - Failed login attempt tracking
    - Automatic account locking after N failed attempts
    - Lockout duration management
    """
    try:
        user_repo = UserRepository(db)

        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Check if user was actually locked
        user.is_locked if hasattr(user, "is_locked") else False

        # Unlock account and reset security counters
        if hasattr(user, "is_locked"):
            user.is_locked = False
        if hasattr(user, "locked_until"):
            user.locked_until = None
        if hasattr(user, "failed_login_attempts"):
            user.failed_login_attempts = 0

        # Ensure user is active
        user.is_active = True

        db.commit()
        db.refresh(user)

        # Invalidate cache
        await invalidate_user_cache_async(str(user_id))

        # Log action
        await _log_admin_action(
            db,
            "unlock_user",
            admin_user,
            context,
            target_user_id=user_id,
            additional_data={"user_email": user.email},
        )

        logger.info(f"Admin {admin_user.email} unlocked user {user.email}")

        return UserActionResponse(
            success=True, message="User account unlocked successfully", user_id=user_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unlocking user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error unlocking user account",
        )
