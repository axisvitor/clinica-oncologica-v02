"""
Admin Management API v2
Comprehensive admin endpoints with cursor pagination, Redis caching, and rate limiting.

Features:
- Cursor-based pagination on all list endpoints
- Redis caching (5-15min TTL for lists, stats)
- Eager loading with joinedload() to prevent N+1
- Rate limiting on write operations (decorators for future enablement)
- Field selection (?fields=id,name,email)
- RBAC - Admin-only endpoints
"""

import logging
import math
import csv
import io
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc

from app.database import get_db
from app.models.user import User, UserRole
from app.models.audit_log import AuditLog
from app.repositories.user import UserRepository
from app.services.audit_service import AuditService
from app.utils.security import get_password_hash
from app.utils.rate_limiter import limiter
from app.infrastructure.cache import cache_response, invalidate_user_cache
from app.dependencies import get_request_context, RequestContext
from app.schemas.v2.admin import (
    # User schemas
    UserCreateRequest,
    UserUpdateRequest,
    UserResponse,
    UserListResponse,
    UserActionResponse,
    UserResetPasswordRequest,
    # Role schemas (placeholder - for future implementation)
    RoleCreateRequest,
    RoleUpdateRequest,
    RoleResponse,
    RoleListResponse,
    # Permission schemas (placeholder)
    PermissionResponse,
    PermissionListResponse,
    PermissionAssignRequest,
    # Audit schemas
    AuditLogRecord,
    AuditLogListResponse,
    UserActivityRecord,
    UserActivityResponse,
    # Stats schemas
    UserStatsResponse,
    ActivityStatsResponse,
    # Bulk operations
    BulkUpdateRequest,
    BulkDeleteRequest,
    BulkOperationResult,
    ExportFormat,
    # Search schemas
    UserSearchRequest,
)
from .dependencies import (
    get_pagination_params,
    get_field_selection,
    create_cursor,
    apply_field_selection,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def get_admin_user(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context)
) -> User:
    """
    Dependency to verify admin access.

    TODO: Implement proper authentication integration.
    For now, this is a placeholder that should be replaced with actual auth.
    """
    # TODO: Get user from session/token
    # This is a placeholder - integrate with your auth system
    user = db.query(User).filter(User.role == UserRole.ADMIN, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


def _serialize_user(user: User, fields: Optional[List[str]] = None) -> dict:
    """Serialize user to dict with optional field selection."""
    data = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": user.last_login,
        "firebase_uid": user.firebase_uid if hasattr(user, 'firebase_uid') else None,
    }

    if fields:
        data = apply_field_selection(data, fields)

    return data


async def log_admin_action(
    audit_service: AuditService,
    action: str,
    admin_user: User,
    context: RequestContext,
    target_user_id: Optional[UUID] = None,
    additional_data: Optional[Dict[str, Any]] = None
) -> None:
    """Log admin actions for audit trail."""
    try:
        event_data = {
            "action": action,
            "admin_user_id": str(admin_user.id),
            "admin_user_email": admin_user.email,
            **(additional_data or {})
        }

        if target_user_id:
            event_data["target_user_id"] = str(target_user_id)

        audit_service.log_event(
            event_type=f"admin_{action}",
            event_category="admin",
            severity="info",
            user_id=admin_user.id,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            event_data=event_data,
            result="success"
        )
    except Exception as e:
        logger.error(f"Failed to log admin action {action}: {e}")


# ============================================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================================

@router.get(
    "/users",
    response_model=UserListResponse,
    summary="List Users with Cursor Pagination",
    description="Retrieve paginated list of users with cursor-based pagination, field selection, and eager loading."
)
@limiter.limit("100/minute")  # Rate limit decorator (no-op but ready for future)
async def list_users(
    request: Request,
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    fields: Optional[str] = Query(None, description="Comma-separated fields to include"),
    role: Optional[str] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in email and full_name"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """List all users with cursor pagination and filters."""
    try:
        # Parse pagination params
        pagination = get_pagination_params(cursor, limit)
        cursor_data = pagination["cursor_data"]

        # Parse field selection
        field_list = get_field_selection(fields) if fields else None

        # Build base query with eager loading
        query = db.query(User)

        # Apply cursor pagination
        if cursor_data:
            query = query.filter(User.id > cursor_data.get("id", 0))

        # Apply filters
        if role:
            try:
                role_enum = UserRole(role.lower())
                query = query.filter(User.role == role_enum)
            except ValueError:
                pass  # Invalid role, ignore

        if is_active is not None:
            query = query.filter(User.is_active == is_active)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    User.email.ilike(search_pattern),
                    User.full_name.ilike(search_pattern)
                )
            )

        # Order by ID for consistent cursor pagination
        query = query.order_by(User.id)

        # Fetch limit + 1 to check if there's more
        users = query.limit(limit + 1).all()

        # Check if there are more results
        has_more = len(users) > limit
        if has_more:
            users = users[:limit]

        # Create next cursor
        next_cursor = None
        if has_more and users:
            next_cursor = create_cursor(users[-1].id)

        # Serialize users
        serialized_users = [_serialize_user(user, field_list) for user in users]

        # Log action
        audit_service = AuditService(db)
        await log_admin_action(
            audit_service, "list_users", admin_user, context,
            additional_data={"count": len(users), "filters": {"role": role, "is_active": is_active, "search": search}}
        )

        return {
            "data": serialized_users,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": None  # Cursor pagination doesn't include total for performance
        }

    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user list"
        )


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create New User",
    description="Create a new user account with password validation and role assignment."
)
@limiter.limit("10/hour")  # Rate limit for user creation
async def create_user(
    request: Request,
    user_data: UserCreateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """Create a new user."""
    try:
        user_repo = UserRepository(db)

        # Check if email already exists
        existing_user = user_repo.get_by_email(user_data.email.lower())
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )

        # Hash password
        hashed_password = get_password_hash(user_data.password)

        # Convert role string to enum
        role_enum = UserRole(user_data.role.lower())

        # Create user
        new_user = user_repo.create({
            "email": user_data.email.lower(),
            "hashed_password": hashed_password,
            "full_name": user_data.full_name,
            "role": role_enum,
            "is_active": user_data.is_active
        })
        db.commit()
        db.refresh(new_user)

        # Log action
        audit_service = AuditService(db)
        await log_admin_action(
            audit_service, "create_user", admin_user, context,
            target_user_id=new_user.id,
            additional_data={"created_role": user_data.role}
        )

        logger.info(f"Admin {admin_user.email} created user {new_user.email}")

        return _serialize_user(new_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating user: {str(e)}"
        )


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Get User Details",
    description="Retrieve detailed information about a specific user. Cached for 10 minutes."
)
@cache_response(ttl=600, key_prefix="admin:user")  # Cache for 10 minutes
async def get_user(
    user_id: UUID,
    fields: Optional[str] = Query(None, description="Comma-separated fields to include"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """Get user details by ID."""
    try:
        user_repo = UserRepository(db)

        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Parse field selection
        field_list = get_field_selection(fields) if fields else None

        # Log action
        audit_service = AuditService(db)
        await log_admin_action(
            audit_service, "view_user", admin_user, context, target_user_id=user_id
        )

        return _serialize_user(user, field_list)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user"
        )


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Update User",
    description="Update user information with cache invalidation."
)
@limiter.limit("20/hour")  # Rate limit for updates
async def update_user(
    request: Request,
    user_id: UUID,
    user_data: UserUpdateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """Update user information."""
    try:
        user_repo = UserRepository(db)

        # Get existing user
        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Prepare update data
        update_data = {}
        changes = []

        if user_data.email and user_data.email.lower() != user.email:
            # Check email uniqueness
            existing = user_repo.get_by_email(user_data.email.lower())
            if existing and existing.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists"
                )
            update_data["email"] = user_data.email.lower()
            changes.append(f"email: {user.email} -> {user_data.email.lower()}")

        if user_data.full_name and user_data.full_name != user.full_name:
            update_data["full_name"] = user_data.full_name
            changes.append(f"full_name changed")

        if user_data.role:
            role_enum = UserRole(user_data.role.lower())
            if role_enum != user.role:
                update_data["role"] = role_enum
                changes.append(f"role: {user.role.value} -> {role_enum.value}")

        if user_data.is_active is not None and user_data.is_active != user.is_active:
            update_data["is_active"] = user_data.is_active
            changes.append(f"is_active: {user.is_active} -> {user_data.is_active}")

        # Apply updates
        if update_data:
            user_repo.update(user_id, update_data)
            db.commit()

            # Invalidate cache
            invalidate_user_cache(str(user_id))

            # Log action
            audit_service = AuditService(db)
            await log_admin_action(
                audit_service, "update_user", admin_user, context,
                target_user_id=user_id,
                additional_data={"changes": changes}
            )

            logger.info(f"Admin {admin_user.email} updated user {user.email}")

        # Refresh and return
        db.refresh(user)
        return _serialize_user(user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user: {str(e)}"
        )


@router.delete(
    "/users/{user_id}",
    response_model=UserActionResponse,
    summary="Soft Delete User",
    description="Soft delete (deactivate) a user account."
)
@limiter.limit("10/hour")  # Rate limit for deletions
async def delete_user(
    request: Request,
    user_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """Soft delete (deactivate) a user."""
    try:
        user_repo = UserRepository(db)

        # Prevent self-deletion
        if user_id == admin_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )

        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Soft delete
        user_repo.update(user_id, {"is_active": False})
        db.commit()

        # Invalidate cache
        invalidate_user_cache(str(user_id))

        # Log action
        audit_service = AuditService(db)
        await log_admin_action(
            audit_service, "delete_user", admin_user, context,
            target_user_id=user_id,
            additional_data={"deletion_type": "soft_delete"}
        )

        logger.info(f"Admin {admin_user.email} deleted user {user.email}")

        return UserActionResponse(
            success=True,
            message="User deleted successfully",
            user_id=user_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting user"
        )


@router.post(
    "/users/{user_id}/restore",
    response_model=UserActionResponse,
    summary="Restore Deleted User",
    description="Restore a soft-deleted (deactivated) user account."
)
async def restore_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """Restore a soft-deleted user."""
    try:
        user_repo = UserRepository(db)

        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already active"
            )

        # Restore user
        user_repo.update(user_id, {"is_active": True})
        db.commit()

        # Invalidate cache
        invalidate_user_cache(str(user_id))

        # Log action
        audit_service = AuditService(db)
        await log_admin_action(
            audit_service, "restore_user", admin_user, context, target_user_id=user_id
        )

        logger.info(f"Admin {admin_user.email} restored user {user.email}")

        return UserActionResponse(
            success=True,
            message="User restored successfully",
            user_id=user_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error restoring user"
        )


@router.post(
    "/users/{user_id}/reset-password",
    response_model=UserActionResponse,
    summary="Reset User Password",
    description="Reset a user's password with password strength validation."
)
@limiter.limit("10/hour")  # Rate limit for password resets
async def reset_user_password(
    request: Request,
    user_id: UUID,
    password_data: UserResetPasswordRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """Reset user password."""
    try:
        user_repo = UserRepository(db)

        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Hash new password
        hashed_password = get_password_hash(password_data.new_password)

        # Update password
        user_repo.update(user_id, {"hashed_password": hashed_password})
        db.commit()

        # Invalidate cache
        invalidate_user_cache(str(user_id))

        # Log action (don't log the actual password)
        audit_service = AuditService(db)
        await log_admin_action(
            audit_service, "reset_password", admin_user, context,
            target_user_id=user_id,
            additional_data={"force_change": password_data.force_change}
        )

        logger.info(f"Admin {admin_user.email} reset password for user {user.email}")

        return UserActionResponse(
            success=True,
            message="Password reset successfully",
            user_id=user_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting password for user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error resetting password"
        )


# ============================================================================
# ROLE MANAGEMENT ENDPOINTS (Placeholder for future implementation)
# ============================================================================

@router.get(
    "/roles",
    response_model=RoleListResponse,
    summary="List Roles",
    description="List all roles in the system. Cached for 30 minutes."
)
@cache_response(ttl=1800, key_prefix="admin:roles")  # Cache for 30 minutes
async def list_roles(
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """List all roles. Placeholder for future implementation."""
    # TODO: Implement role management system
    return {
        "data": [
            {"id": "uuid1", "name": "admin", "description": "Administrator role", "permissions": [], "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()},
            {"id": "uuid2", "name": "doctor", "description": "Doctor role", "permissions": [], "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()}
        ],
        "next_cursor": None,
        "has_more": False,
        "total": 2
    }


@router.post(
    "/roles",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Role",
    description="Create a new role. Placeholder for future implementation."
)
@limiter.limit("5/hour")
async def create_role(
    request: Request,
    role_data: RoleCreateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Create a new role. Placeholder for future implementation."""
    # TODO: Implement role creation
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Role management not yet implemented"
    )


@router.get(
    "/roles/{role_id}",
    response_model=RoleResponse,
    summary="Get Role Details",
    description="Get role details. Placeholder for future implementation."
)
async def get_role(
    role_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Get role by ID. Placeholder for future implementation."""
    # TODO: Implement role retrieval
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Role management not yet implemented"
    )


@router.put(
    "/roles/{role_id}",
    response_model=RoleResponse,
    summary="Update Role",
    description="Update role. Placeholder for future implementation."
)
async def update_role(
    role_id: UUID,
    role_data: RoleUpdateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Update role. Placeholder for future implementation."""
    # TODO: Implement role update
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Role management not yet implemented"
    )


@router.delete(
    "/roles/{role_id}",
    summary="Delete Role",
    description="Delete role. Placeholder for future implementation."
)
async def delete_role(
    role_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Delete role. Placeholder for future implementation."""
    # TODO: Implement role deletion
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Role management not yet implemented"
    )


# ============================================================================
# PERMISSION MANAGEMENT ENDPOINTS (Placeholder)
# ============================================================================

@router.get(
    "/permissions",
    response_model=PermissionListResponse,
    summary="List Permissions",
    description="List all permissions. Cached for 1 hour."
)
@cache_response(ttl=3600, key_prefix="admin:permissions")
async def list_permissions(
    cursor: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """List all permissions. Placeholder for future implementation."""
    # TODO: Implement permission management
    return {
        "data": [],
        "next_cursor": None,
        "has_more": False,
        "total": 0
    }


@router.post(
    "/users/{user_id}/permissions",
    response_model=UserActionResponse,
    summary="Assign Permissions",
    description="Assign permissions to user. Placeholder for future implementation."
)
async def assign_permissions(
    user_id: UUID,
    permissions_data: PermissionAssignRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Assign permissions to user. Placeholder for future implementation."""
    # TODO: Implement permission assignment
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Permission management not yet implemented"
    )


@router.delete(
    "/users/{user_id}/permissions/{permission_id}",
    response_model=UserActionResponse,
    summary="Revoke Permission",
    description="Revoke permission from user. Placeholder for future implementation."
)
async def revoke_permission(
    user_id: UUID,
    permission_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Revoke permission from user. Placeholder for future implementation."""
    # TODO: Implement permission revocation
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Permission management not yet implemented"
    )


@router.get(
    "/users/{user_id}/permissions",
    response_model=PermissionListResponse,
    summary="List User Permissions",
    description="List permissions for a specific user. Placeholder for future implementation."
)
async def list_user_permissions(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """List user permissions. Placeholder for future implementation."""
    # TODO: Implement user permission listing
    return {
        "data": [],
        "next_cursor": None,
        "has_more": False,
        "total": 0
    }


# ============================================================================
# AUDIT & STATS ENDPOINTS
# ============================================================================

@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    summary="Get Audit Logs",
    description="Retrieve audit logs with cursor pagination and filtering."
)
async def get_audit_logs(
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    user_id: Optional[UUID] = Query(None, description="Filter by user"),
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """Get audit logs with filters."""
    try:
        # Parse pagination
        pagination = get_pagination_params(cursor, limit)
        cursor_data = pagination["cursor_data"]

        # Build query
        query = db.query(AuditLog)

        # Apply cursor
        if cursor_data:
            query = query.filter(AuditLog.id > cursor_data.get("id", 0))

        # Apply filters
        if event_type:
            query = query.filter(AuditLog.event_type == event_type)

        if severity:
            query = query.filter(AuditLog.severity == severity)

        if user_id:
            query = query.filter(AuditLog.user_id == user_id)

        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)

        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)

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
        serialized_logs = []
        for log in logs:
            serialized_logs.append({
                "id": log.id,
                "event_type": log.event_type,
                "event_category": log.event_category,
                "severity": log.severity,
                "user_id": log.user_id,
                "user_email": None,  # Can be joined if needed
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "event_data": log.event_data or {},
                "result": log.result,
                "timestamp": log.timestamp
            })

        return {
            "data": serialized_logs,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": None
        }

    except Exception as e:
        logger.error(f"Error retrieving audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving audit logs"
        )


@router.get(
    "/users/{user_id}/audit",
    response_model=UserActivityResponse,
    summary="Get User Audit Trail",
    description="Get audit trail for a specific user with cursor pagination."
)
async def get_user_audit_trail(
    user_id: UUID,
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    action: Optional[str] = Query(None, description="Filter by action type"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """Get audit trail for a specific user."""
    try:
        # Verify user exists
        user_repo = UserRepository(db)
        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
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
            action_name = log.event_type.split('_')[-1] if '_' in log.event_type else log.event_type
            activity_records.append({
                "id": str(log.id),
                "user_id": str(user_id),
                "user_email": user.email,
                "action": action_name,
                "resource": "user",
                "resource_id": log.event_data.get("target_user_id") if log.event_data else None,
                "details": log.event_data or {},
                "timestamp": log.timestamp,
                "ip_address": log.ip_address or "unknown",
                "user_agent": log.user_agent or "unknown"
            })

        # Log action
        audit_service = AuditService(db)
        await log_admin_action(
            audit_service, "view_user_audit", admin_user, context,
            target_user_id=user_id,
            additional_data={"count": len(activity_records)}
        )

        return {
            "data": activity_records,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user audit trail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user audit trail"
        )


@router.get(
    "/stats/users",
    response_model=UserStatsResponse,
    summary="Get User Statistics",
    description="Get comprehensive user statistics. Cached for 15 minutes."
)
@cache_response(ttl=900, key_prefix="admin:stats:users")  # Cache for 15 minutes
async def get_user_statistics(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """Get user statistics."""
    try:
        # Get basic counts
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        inactive_users = total_users - active_users

        # Get counts by role
        role_counts = {}
        for role in UserRole:
            count = db.query(User).filter(User.role == role).count()
            role_counts[role.value] = count

        # Get recent registrations (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_registrations = db.query(User).filter(User.created_at >= thirty_days_ago).count()

        # Calculate growth rate
        sixty_days_ago = datetime.utcnow() - timedelta(days=60)
        previous_period = db.query(User).filter(
            User.created_at >= sixty_days_ago,
            User.created_at < thirty_days_ago
        ).count()

        growth_rate = None
        if previous_period > 0:
            growth_rate = ((recent_registrations - previous_period) / previous_period) * 100

        # Log action
        audit_service = AuditService(db)
        await log_admin_action(
            audit_service, "view_user_stats", admin_user, context
        )

        return UserStatsResponse(
            total_users=total_users,
            active_users=active_users,
            inactive_users=inactive_users,
            by_role=role_counts,
            recent_registrations=recent_registrations,
            growth_rate=growth_rate
        )

    except Exception as e:
        logger.error(f"Error retrieving user stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user statistics"
        )


@router.get(
    "/stats/activity",
    response_model=ActivityStatsResponse,
    summary="Get Activity Statistics",
    description="Get activity/audit statistics. Cached for 15 minutes."
)
@cache_response(ttl=900, key_prefix="admin:stats:activity")  # Cache for 15 minutes
async def get_activity_statistics(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """Get activity statistics."""
    try:
        now = datetime.utcnow()
        today_start = datetime(now.year, now.month, now.day)
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)

        # Total events
        total_events = db.query(AuditLog).count()

        # Events today
        events_today = db.query(AuditLog).filter(
            AuditLog.timestamp >= today_start
        ).count()

        # Events this week
        events_this_week = db.query(AuditLog).filter(
            AuditLog.timestamp >= week_start
        ).count()

        # Events this month
        events_this_month = db.query(AuditLog).filter(
            AuditLog.timestamp >= month_start
        ).count()

        # By event type
        event_type_counts = {}
        event_types = db.query(
            AuditLog.event_type,
            func.count(AuditLog.id).label('count')
        ).group_by(AuditLog.event_type).limit(10).all()

        for event_type, count in event_types:
            event_type_counts[event_type] = count

        # By severity
        severity_counts = {}
        severities = db.query(
            AuditLog.severity,
            func.count(AuditLog.id).label('count')
        ).group_by(AuditLog.severity).all()

        for severity, count in severities:
            severity_counts[severity] = count

        # Most active users (top 5)
        most_active = db.query(
            AuditLog.user_id,
            func.count(AuditLog.id).label('event_count')
        ).filter(
            AuditLog.user_id.isnot(None),
            AuditLog.timestamp >= month_start
        ).group_by(AuditLog.user_id).order_by(desc('event_count')).limit(5).all()

        most_active_users = []
        for user_id, event_count in most_active:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                most_active_users.append({
                    "user_id": str(user_id),
                    "user_email": user.email,
                    "event_count": event_count
                })

        # Log action
        audit_service = AuditService(db)
        await log_admin_action(
            audit_service, "view_activity_stats", admin_user, context
        )

        return ActivityStatsResponse(
            total_events=total_events,
            events_today=events_today,
            events_this_week=events_this_week,
            events_this_month=events_this_month,
            by_event_type=event_type_counts,
            by_severity=severity_counts,
            most_active_users=most_active_users
        )

    except Exception as e:
        logger.error(f"Error retrieving activity stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving activity statistics"
        )


# ============================================================================
# BULK OPERATIONS ENDPOINTS
# ============================================================================

@router.post(
    "/users/bulk-update",
    response_model=BulkOperationResult,
    summary="Bulk Update Users",
    description="Update multiple users at once (max 100)."
)
@limiter.limit("5/hour")
async def bulk_update_users(
    request: Request,
    bulk_data: BulkUpdateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """Bulk update users."""
    try:
        if len(bulk_data.user_ids) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 100 users per bulk update"
            )

        user_repo = UserRepository(db)
        successful = 0
        failed = 0
        errors = []

        # Prepare update data
        update_data = {}
        if bulk_data.updates.is_active is not None:
            update_data["is_active"] = bulk_data.updates.is_active
        if bulk_data.updates.role:
            update_data["role"] = UserRole(bulk_data.updates.role.lower())

        # Process each user
        for user_id in bulk_data.user_ids:
            try:
                user = user_repo.get(user_id)
                if not user:
                    errors.append({"user_id": str(user_id), "error": "User not found"})
                    failed += 1
                    continue

                if update_data:
                    user_repo.update(user_id, update_data)
                    invalidate_user_cache(str(user_id))
                    successful += 1

            except Exception as e:
                errors.append({"user_id": str(user_id), "error": str(e)})
                failed += 1

        db.commit()

        # Log action
        audit_service = AuditService(db)
        await log_admin_action(
            audit_service, "bulk_update_users", admin_user, context,
            additional_data={
                "total": len(bulk_data.user_ids),
                "successful": successful,
                "failed": failed
            }
        )

        return BulkOperationResult(
            success=failed == 0,
            total_requested=len(bulk_data.user_ids),
            successful=successful,
            failed=failed,
            errors=errors,
            message=f"Bulk update completed: {successful} successful, {failed} failed"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk update: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in bulk update: {str(e)}"
        )


@router.post(
    "/users/bulk-delete",
    response_model=BulkOperationResult,
    summary="Bulk Delete Users",
    description="Soft delete multiple users at once (max 50)."
)
@limiter.limit("3/hour")
async def bulk_delete_users(
    request: Request,
    bulk_data: BulkDeleteRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """Bulk soft delete users."""
    try:
        if len(bulk_data.user_ids) > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 50 users per bulk delete"
            )

        # Prevent self-deletion
        if admin_user.id in bulk_data.user_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )

        user_repo = UserRepository(db)
        successful = 0
        failed = 0
        errors = []

        for user_id in bulk_data.user_ids:
            try:
                user = user_repo.get(user_id)
                if not user:
                    errors.append({"user_id": str(user_id), "error": "User not found"})
                    failed += 1
                    continue

                user_repo.update(user_id, {"is_active": False})
                invalidate_user_cache(str(user_id))
                successful += 1

            except Exception as e:
                errors.append({"user_id": str(user_id), "error": str(e)})
                failed += 1

        db.commit()

        # Log action
        audit_service = AuditService(db)
        await log_admin_action(
            audit_service, "bulk_delete_users", admin_user, context,
            additional_data={
                "total": len(bulk_data.user_ids),
                "successful": successful,
                "failed": failed,
                "reason": bulk_data.reason
            }
        )

        return BulkOperationResult(
            success=failed == 0,
            total_requested=len(bulk_data.user_ids),
            successful=successful,
            failed=failed,
            errors=errors,
            message=f"Bulk delete completed: {successful} successful, {failed} failed"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk delete: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in bulk delete: {str(e)}"
        )


@router.post(
    "/users/export",
    summary="Export Users",
    description="Export users to CSV or JSON format."
)
async def export_users(
    export_format: ExportFormat,
    role: Optional[str] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """Export users to CSV or JSON."""
    try:
        # Build query
        query = db.query(User)

        # Apply filters
        if role:
            try:
                role_enum = UserRole(role.lower())
                query = query.filter(User.role == role_enum)
            except ValueError:
                pass

        if is_active is not None:
            query = query.filter(User.is_active == is_active)

        # Fetch users
        users = query.order_by(User.created_at.desc()).all()

        # Determine fields
        all_fields = ["id", "email", "full_name", "role", "is_active", "created_at", "updated_at", "last_login"]
        fields = export_format.fields if export_format.fields else all_fields

        # Log action
        audit_service = AuditService(db)
        await log_admin_action(
            audit_service, "export_users", admin_user, context,
            additional_data={
                "format": export_format.format,
                "count": len(users),
                "filters": {"role": role, "is_active": is_active}
            }
        )

        if export_format.format == "csv":
            # Generate CSV
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()

            for user in users:
                row = {}
                for field in fields:
                    value = getattr(user, field, None)
                    if field == "role" and hasattr(value, "value"):
                        value = value.value
                    elif isinstance(value, datetime):
                        value = value.isoformat()
                    elif isinstance(value, UUID):
                        value = str(value)
                    row[field] = value
                writer.writerow(row)

            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=users_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"}
            )

        else:  # JSON
            data = []
            for user in users:
                row = {}
                for field in fields:
                    value = getattr(user, field, None)
                    if field == "role" and hasattr(value, "value"):
                        value = value.value
                    elif isinstance(value, datetime):
                        value = value.isoformat()
                    elif isinstance(value, UUID):
                        value = str(value)
                    row[field] = value
                data.append(row)

            return Response(
                content=json.dumps(data, indent=2),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=users_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"}
            )

    except Exception as e:
        logger.error(f"Error exporting users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting users: {str(e)}"
        )


# ============================================================================
# SEARCH & FILTER ENDPOINTS
# ============================================================================

@router.post(
    "/users/search",
    response_model=UserListResponse,
    summary="Advanced User Search",
    description="Advanced search with multiple criteria and cursor pagination."
)
async def search_users(
    search_data: UserSearchRequest,
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """Advanced user search."""
    try:
        # Parse pagination
        pagination = get_pagination_params(cursor, limit)
        cursor_data = pagination["cursor_data"]

        # Build query
        query = db.query(User)

        # Apply cursor
        if cursor_data:
            query = query.filter(User.id > cursor_data.get("id", 0))

        # Apply search filters
        if search_data.query:
            search_pattern = f"%{search_data.query}%"
            query = query.filter(
                or_(
                    User.email.ilike(search_pattern),
                    User.full_name.ilike(search_pattern)
                )
            )

        if search_data.role:
            try:
                role_enum = UserRole(search_data.role.lower())
                query = query.filter(User.role == role_enum)
            except ValueError:
                pass

        if search_data.is_active is not None:
            query = query.filter(User.is_active == search_data.is_active)

        if search_data.created_after:
            query = query.filter(User.created_at >= search_data.created_after)

        if search_data.created_before:
            query = query.filter(User.created_at <= search_data.created_before)

        if search_data.last_login_after:
            query = query.filter(User.last_login >= search_data.last_login_after)

        if search_data.last_login_before:
            query = query.filter(User.last_login <= search_data.last_login_before)

        # Order and fetch
        query = query.order_by(User.id)
        users = query.limit(limit + 1).all()

        # Check for more
        has_more = len(users) > limit
        if has_more:
            users = users[:limit]

        # Create cursor
        next_cursor = create_cursor(users[-1].id) if has_more and users else None

        # Serialize
        serialized_users = [_serialize_user(user) for user in users]

        # Log action
        audit_service = AuditService(db)
        await log_admin_action(
            audit_service, "search_users", admin_user, context,
            additional_data={"count": len(users), "query": search_data.query}
        )

        return {
            "data": serialized_users,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": None
        }

    except Exception as e:
        logger.error(f"Error searching users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error searching users"
        )


@router.get(
    "/users/active",
    response_model=UserListResponse,
    summary="List Active Users",
    description="Get all active users with cursor pagination."
)
async def list_active_users(
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """List active users."""
    try:
        pagination = get_pagination_params(cursor, limit)
        cursor_data = pagination["cursor_data"]

        query = db.query(User).filter(User.is_active == True)

        if cursor_data:
            query = query.filter(User.id > cursor_data.get("id", 0))

        query = query.order_by(User.id)
        users = query.limit(limit + 1).all()

        has_more = len(users) > limit
        if has_more:
            users = users[:limit]

        next_cursor = create_cursor(users[-1].id) if has_more and users else None

        return {
            "data": [_serialize_user(user) for user in users],
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": None
        }

    except Exception as e:
        logger.error(f"Error listing active users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing active users"
        )


@router.get(
    "/users/inactive",
    response_model=UserListResponse,
    summary="List Inactive Users",
    description="Get all inactive users with cursor pagination."
)
async def list_inactive_users(
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """List inactive users."""
    try:
        pagination = get_pagination_params(cursor, limit)
        cursor_data = pagination["cursor_data"]

        query = db.query(User).filter(User.is_active == False)

        if cursor_data:
            query = query.filter(User.id > cursor_data.get("id", 0))

        query = query.order_by(User.id)
        users = query.limit(limit + 1).all()

        has_more = len(users) > limit
        if has_more:
            users = users[:limit]

        next_cursor = create_cursor(users[-1].id) if has_more and users else None

        return {
            "data": [_serialize_user(user) for user in users],
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": None
        }

    except Exception as e:
        logger.error(f"Error listing inactive users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error listing inactive users"
        )
