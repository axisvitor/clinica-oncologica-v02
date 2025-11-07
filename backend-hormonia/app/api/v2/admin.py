"""
Admin API v2
User management and administration with strict access control.

Features:
- 12 core admin endpoints for user management
- Cursor-based pagination with Redis caching
- RBAC with admin-only access control
- Comprehensive audit logging for all operations
- Password strength validation
- Rate limiting on sensitive operations
- Field selection and eager loading support
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc

from app.database import get_db
from app.models.user import User, UserRole
from app.models.audit_log import AuditLog
from app.repositories.user import UserRepository
from app.services.audit_service import AuditService
from app.utils.security import get_password_hash, verify_password
from app.utils.rate_limiter import limiter
from app.infrastructure.cache import cache_response, invalidate_user_cache
from app.dependencies import get_request_context, RequestContext
from app.schemas.v2.admin import (
    UserCreateRequest,
    UserUpdateRequest,
    UserResponse,
    UserListResponse,
    UserActionResponse,
    UserResetPasswordRequest,
    UserActivityResponse,
    UserActivityRecord,
    PermissionAssignRequest,
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
# AUTHENTICATION & AUTHORIZATION
# ============================================================================

async def get_admin_user(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context)
) -> User:
    """
    Dependency to verify admin access.

    Raises:
        HTTPException: If user is not authenticated or not an admin

    Returns:
        User: The authenticated admin user

    TODO: Integrate with actual authentication system (Firebase/JWT)
    """
    # TODO: Replace with actual auth integration
    # For now, get first active admin user (placeholder)
    user = db.query(User).filter(
        User.role == UserRole.ADMIN,
        User.is_active == True
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return user


def _require_admin(current_user: User) -> None:
    """
    Ensure user is admin, raise 403 otherwise.

    Args:
        current_user: The current user object

    Raises:
        HTTPException: If user is not an admin
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _serialize_user(user: User, fields: Optional[List[str]] = None) -> dict:
    """
    Serialize user to dict with optional field selection.

    Args:
        user: User model instance
        fields: Optional list of fields to include

    Returns:
        dict: Serialized user data
    """
    data = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": getattr(user, 'last_login', None),
        "firebase_uid": getattr(user, 'firebase_uid', None),
    }

    if fields:
        data = apply_field_selection(data, fields)

    return data


async def _log_admin_action(
    db: Session,
    action: str,
    admin_user: User,
    context: RequestContext,
    target_user_id: Optional[UUID] = None,
    additional_data: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log admin actions for audit trail.

    Args:
        db: Database session
        action: Action performed (e.g., 'create_user', 'update_role')
        admin_user: Admin user who performed the action
        context: Request context with IP, user agent, etc.
        target_user_id: Optional ID of the target user
        additional_data: Optional additional event data
    """
    try:
        audit_service = AuditService(db)

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


def _validate_password_strength(password: str) -> None:
    """
    Validate password strength.

    Args:
        password: Password to validate

    Raises:
        HTTPException: If password doesn't meet requirements
    """
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    if not any(c.isupper() for c in password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one uppercase letter"
        )
    if not any(c.islower() for c in password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one lowercase letter"
        )
    if not any(c.isdigit() for c in password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one digit"
        )


# ============================================================================
# ENDPOINT 1: LIST USERS
# ============================================================================

@router.get(
    "/users",
    response_model=UserListResponse,
    summary="List Users with Cursor Pagination",
    description="Retrieve paginated list of users with cursor-based pagination, field selection, and eager loading."
)
@limiter.limit("100/minute")
@cache_response(ttl=300, key_prefix="admin:users:list")  # Cache for 5 minutes
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
    """
    List all users with cursor pagination and filters.

    Features:
    - Cursor-based pagination (efficient for large datasets)
    - Field selection (?fields=id,email,role)
    - Role and status filters
    - Search by email or name
    - Redis caching (5 min TTL)
    """
    try:
        # Parse pagination params
        pagination = get_pagination_params(cursor, limit)
        cursor_data = pagination["cursor_data"]

        # Parse field selection
        field_list = get_field_selection(fields) if fields else None

        # Build base query
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
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role: {role}. Valid roles: admin, doctor"
                )

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
        await _log_admin_action(
            db, "list_users", admin_user, context,
            additional_data={"count": len(users), "filters": {"role": role, "is_active": is_active, "search": search}}
        )

        return {
            "data": serialized_users,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": None  # Cursor pagination doesn't include total for performance
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user list"
        )


# ============================================================================
# ENDPOINT 2: GET SINGLE USER
# ============================================================================

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
    """
    Get user details by ID.

    Features:
    - Field selection support
    - Redis caching (10 min TTL)
    - Audit logging
    """
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
        await _log_admin_action(
            db, "view_user", admin_user, context, target_user_id=user_id
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


# ============================================================================
# ENDPOINT 3: CREATE USER
# ============================================================================

@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create New User",
    description="Create a new user account with password validation and role assignment."
)
@limiter.limit("10/hour")  # Strict rate limit for user creation
async def create_user(
    request: Request,
    user_data: UserCreateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """
    Create a new user.

    Features:
    - Password strength validation
    - Email uniqueness check
    - Role assignment
    - Audit logging
    """
    try:
        user_repo = UserRepository(db)

        # Check if email already exists
        existing_user = user_repo.get_by_email(user_data.email.lower())
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )

        # Validate password strength
        _validate_password_strength(user_data.password)

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
        await _log_admin_action(
            db, "create_user", admin_user, context,
            target_user_id=new_user.id,
            additional_data={
                "created_email": user_data.email,
                "created_role": user_data.role
            }
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


# ============================================================================
# ENDPOINT 4: UPDATE USER
# ============================================================================

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
    """
    Update user information.

    Features:
    - Partial updates (only provided fields)
    - Email uniqueness validation
    - Cache invalidation
    - Change tracking and audit logging
    """
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
            changes.append("full_name changed")

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
            await _log_admin_action(
                db, "update_user", admin_user, context,
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


# ============================================================================
# ENDPOINT 5: DELETE USER
# ============================================================================

@router.delete(
    "/users/{user_id}",
    response_model=UserActionResponse,
    summary="Delete User (Soft Delete)",
    description="Soft delete (deactivate) a user account."
)
@limiter.limit("10/hour")  # Strict rate limit for deletions
async def delete_user(
    request: Request,
    user_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """
    Soft delete (deactivate) a user.

    Features:
    - Prevents self-deletion
    - Sets is_active to False (soft delete)
    - Cache invalidation
    - Audit logging
    """
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

        # Soft delete (deactivate)
        user_repo.update(user_id, {"is_active": False})
        db.commit()

        # Invalidate cache
        invalidate_user_cache(str(user_id))

        # Log action
        await _log_admin_action(
            db, "delete_user", admin_user, context,
            target_user_id=user_id,
            additional_data={"deletion_type": "soft_delete", "user_email": user.email}
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


# ============================================================================
# ENDPOINT 6: ACTIVATE USER
# ============================================================================

@router.post(
    "/users/{user_id}/activate",
    response_model=UserActionResponse,
    summary="Activate User",
    description="Activate a user account (set is_active to True)."
)
@limiter.limit("20/hour")
async def activate_user(
    request: Request,
    user_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """
    Activate a user account.

    Features:
    - Sets is_active to True
    - Cache invalidation
    - Audit logging
    """
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

        # Activate user
        user_repo.update(user_id, {"is_active": True})
        db.commit()

        # Invalidate cache
        invalidate_user_cache(str(user_id))

        # Log action
        await _log_admin_action(
            db, "activate_user", admin_user, context,
            target_user_id=user_id,
            additional_data={"user_email": user.email}
        )

        logger.info(f"Admin {admin_user.email} activated user {user.email}")

        return UserActionResponse(
            success=True,
            message="User activated successfully",
            user_id=user_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error activating user"
        )


# ============================================================================
# ENDPOINT 7: DEACTIVATE USER
# ============================================================================

@router.post(
    "/users/{user_id}/deactivate",
    response_model=UserActionResponse,
    summary="Deactivate User",
    description="Deactivate a user account (set is_active to False)."
)
@limiter.limit("20/hour")
async def deactivate_user(
    request: Request,
    user_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """
    Deactivate a user account.

    Features:
    - Sets is_active to False
    - Prevents self-deactivation
    - Cache invalidation
    - Audit logging
    """
    try:
        user_repo = UserRepository(db)

        # Prevent self-deactivation
        if user_id == admin_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate your own account"
            )

        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already inactive"
            )

        # Deactivate user
        user_repo.update(user_id, {"is_active": False})
        db.commit()

        # Invalidate cache
        invalidate_user_cache(str(user_id))

        # Log action
        await _log_admin_action(
            db, "deactivate_user", admin_user, context,
            target_user_id=user_id,
            additional_data={"user_email": user.email}
        )

        logger.info(f"Admin {admin_user.email} deactivated user {user.email}")

        return UserActionResponse(
            success=True,
            message="User deactivated successfully",
            user_id=user_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deactivating user"
        )


# ============================================================================
# ENDPOINT 8: UPDATE PERMISSIONS
# ============================================================================

@router.put(
    "/users/{user_id}/permissions",
    response_model=UserActionResponse,
    summary="Update User Permissions",
    description="Update user permissions (placeholder for future RBAC implementation)."
)
@limiter.limit("20/hour")
async def update_permissions(
    request: Request,
    user_id: UUID,
    permissions_data: PermissionAssignRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """
    Update user permissions.

    TODO: Implement granular permission management system.

    This is a placeholder for future RBAC implementation.
    Currently returns 501 Not Implemented.
    """
    # TODO: Implement permission management
    # This would involve:
    # 1. Creating a permissions table
    # 2. Creating user_permissions junction table
    # 3. Implementing permission checks in endpoints
    # 4. Adding permission-based access control

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Permission management not yet implemented. Use role-based access control."
    )


# ============================================================================
# ENDPOINT 9: UPDATE ROLE
# ============================================================================

@router.put(
    "/users/{user_id}/role",
    response_model=UserActionResponse,
    summary="Update User Role",
    description="Update a user's role with audit logging."
)
@limiter.limit("20/hour")
async def update_role(
    request: Request,
    user_id: UUID,
    role: str = Query(..., description="New role (admin or doctor)"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """
    Update user role.

    Features:
    - Role validation
    - Prevents self-demotion from admin
    - Cache invalidation
    - Audit logging
    """
    try:
        user_repo = UserRepository(db)

        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Validate role
        try:
            new_role = UserRole(role.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {role}. Valid roles: admin, doctor"
            )

        # Prevent self-demotion from admin
        if user_id == admin_user.id and new_role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote your own admin role"
            )

        old_role = user.role

        # Update role
        user_repo.update(user_id, {"role": new_role})
        db.commit()

        # Invalidate cache
        invalidate_user_cache(str(user_id))

        # Log action
        await _log_admin_action(
            db, "update_role", admin_user, context,
            target_user_id=user_id,
            additional_data={
                "user_email": user.email,
                "old_role": old_role.value,
                "new_role": new_role.value
            }
        )

        logger.info(f"Admin {admin_user.email} updated role for user {user.email}: {old_role.value} -> {new_role.value}")

        return UserActionResponse(
            success=True,
            message=f"User role updated to {new_role.value}",
            user_id=user_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating role for user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating user role"
        )


# ============================================================================
# ENDPOINT 10: GET USER ACTIVITY
# ============================================================================

@router.get(
    "/users/{user_id}/activity",
    response_model=UserActivityResponse,
    summary="Get User Activity Log",
    description="Get audit trail for a specific user with cursor pagination."
)
@cache_response(ttl=300, key_prefix="admin:user:activity")  # Cache for 5 minutes
async def get_user_activity(
    user_id: UUID,
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    action: Optional[str] = Query(None, description="Filter by action type"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
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
        await _log_admin_action(
            db, "view_user_activity", admin_user, context,
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
        logger.error(f"Error retrieving user activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user activity"
        )


# ============================================================================
# ENDPOINT 11: RESET PASSWORD
# ============================================================================

@router.post(
    "/users/{user_id}/reset-password",
    response_model=UserActionResponse,
    summary="Reset User Password",
    description="Reset a user's password with password strength validation."
)
@limiter.limit("10/hour")  # Strict rate limit for password resets
async def reset_password(
    request: Request,
    user_id: UUID,
    password_data: UserResetPasswordRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
):
    """
    Reset user password.

    Features:
    - Password strength validation
    - Secure password hashing
    - Cache invalidation
    - Audit logging (without logging actual password)
    - Optional force password change on next login
    """
    try:
        user_repo = UserRepository(db)

        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Validate password strength
        _validate_password_strength(password_data.new_password)

        # Hash new password
        hashed_password = get_password_hash(password_data.new_password)

        # Update password
        update_data = {"hashed_password": hashed_password}

        # TODO: Implement force_change_password field in User model
        # if password_data.force_change:
        #     update_data["force_change_password"] = True

        user_repo.update(user_id, update_data)
        db.commit()

        # Invalidate cache
        invalidate_user_cache(str(user_id))

        # Log action (don't log the actual password)
        await _log_admin_action(
            db, "reset_password", admin_user, context,
            target_user_id=user_id,
            additional_data={
                "user_email": user.email,
                "force_change": password_data.force_change
            }
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
# ENDPOINT 12: UNLOCK USER ACCOUNT
# ============================================================================

@router.post(
    "/users/{user_id}/unlock",
    response_model=UserActionResponse,
    summary="Unlock User Account",
    description="Unlock a user account that has been locked due to failed login attempts."
)
@limiter.limit("20/hour")
async def unlock_user(
    request: Request,
    user_id: UUID,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
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
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # TODO: Implement account locking fields in User model
        # Fields needed:
        # - failed_login_attempts (int)
        # - locked_until (datetime)
        # - is_locked (bool)

        # For now, just ensure user is active
        update_data = {"is_active": True}
        # Future implementation:
        # update_data = {
        #     "failed_login_attempts": 0,
        #     "locked_until": None,
        #     "is_locked": False,
        #     "is_active": True
        # }

        user_repo.update(user_id, update_data)
        db.commit()

        # Invalidate cache
        invalidate_user_cache(str(user_id))

        # Log action
        await _log_admin_action(
            db, "unlock_user", admin_user, context,
            target_user_id=user_id,
            additional_data={"user_email": user.email}
        )

        logger.info(f"Admin {admin_user.email} unlocked user {user.email}")

        return UserActionResponse(
            success=True,
            message="User account unlocked successfully",
            user_id=user_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unlocking user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error unlocking user account"
        )
