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
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import desc

from app.database import get_db
from app.models.user import User
from app.models.audit_log import AuditLog
from app.repositories.user import UserRepository
from app.utils.rate_limiter import limiter
from app.infrastructure.cache import cache_response, invalidate_user_cache
from app.dependencies import get_request_context, RequestContext
from app.schemas.v2.admin import (
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

        # Parse pagination
        pagination = get_pagination_params(cursor, limit)
        cursor_data = pagination["cursor_data"]

        # Build query
        query = db.query(AuditLog).filter(AuditLog.user_id == user_id)

        # Apply cursor
        if cursor_data:
            query = query.filter(AuditLog.id > cursor_data.get("id", 0))

        # Apply action filter
        if action:
            query = query.filter(AuditLog.event_type.like(f"%{action}%"))

        # Order and fetch
        query = query.order_by(desc(AuditLog.timestamp))
        logs = query.limit(limit + 1).all()

        # Check for more
        has_more = len(logs) > limit
        if has_more:
            logs = logs[:limit]

        # Create cursor
        next_cursor = create_cursor(logs[-1].id) if has_more and logs else None

        # Serialize
        activity_records = []
        for log in logs:
            action_name = (
                log.event_type.split("_")[-1]
                if "_" in log.event_type
                else log.event_type
            )
            activity_records.append(
                {
                    "id": str(log.id),
                    "user_id": str(user_id),
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

        # Log action
        await _log_admin_action(
            db,
            "view_user_activity",
            admin_user,
            context,
            target_user_id=user_id,
            additional_data={"count": len(activity_records)},
        )

        return {
            "data": activity_records,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user activity",
        )


# ============================================================================
# ENDPOINT 2: UPDATE PERMISSIONS
# ============================================================================

# Valid permission identifiers that can be assigned
VALID_PERMISSIONS = {
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
    context: RequestContext = Depends(get_request_context),
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
        user_repo = UserRepository(db)
        user = user_repo.get(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Validate permissions
        invalid_permissions = [
            p for p in permissions_data.permissions if p not in VALID_PERMISSIONS
        ]
        if invalid_permissions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid permissions: {', '.join(invalid_permissions)}",
            )

        # Store old permissions for audit
        old_permissions = list(user.permissions) if user.permissions else []

        # Update permissions
        user.permissions = permissions_data.permissions
        db.commit()
        db.refresh(user)

        # Invalidate cache
        await invalidate_user_cache(str(user_id))

        # Log action
        await _log_admin_action(
            db,
            "update_permissions",
            admin_user,
            context,
            target_user_id=user_id,
            additional_data={
                "old_permissions": old_permissions,
                "new_permissions": permissions_data.permissions,
                "changes": {
                    "added": [
                        p
                        for p in permissions_data.permissions
                        if p not in old_permissions
                    ],
                    "removed": [
                        p
                        for p in old_permissions
                        if p not in permissions_data.permissions
                    ],
                },
            },
        )

        logger.info(f"Permissions updated for user {user_id} by admin {admin_user.id}")

        return {
            "success": True,
            "message": f"Permissions updated successfully. {len(permissions_data.permissions)} permissions assigned.",
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
        invalidate_user_cache(str(user_id))

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
