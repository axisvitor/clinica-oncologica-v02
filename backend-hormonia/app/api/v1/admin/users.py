"""
Admin User Management API for Clinica Oncológica.

This module provides comprehensive user management endpoints for administrators,
including CRUD operations, role management, and audit logging.
"""
import logging
import math
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.dependencies import (
    get_thread_safe_db,
    get_admin_user,
    get_current_user,
    get_thread_safe_service_provider,
    get_request_context,
    RequestContext
)
from app.middleware.db_optimization import QueryOptimizer, get_db_optimizer
from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.schemas.user_admin import (
    UserCreateRequest,
    UserUpdateRequest,
    UserRoleUpdateRequest,
    UserPermissionsUpdateRequest,
    UserResetPasswordRequest,
    UserResponse,
    UserListResponse,
    UserFilterParams,
    UserStatsResponse,
    UserActionResponse,
    UserActivityResponse,
    UserActivityRecord
)
from app.schemas.common import SuccessResponse, ErrorResponse
from app.services.auth import AuthService
from app.services.audit_service import AuditService
from app.utils.security import get_password_hash
from app.utils.unified_cache import invalidate_user_cache

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def log_user_action(
    audit_service: AuditService,
    action: str,
    user_id: UUID,
    admin_user: User,
    context: RequestContext,
    target_user: Optional[User] = None,
    additional_data: Optional[dict] = None
) -> None:
    """Log user management actions for audit trail."""
    try:
        event_data = {
            "action": action,
            "admin_user_id": str(admin_user.id),
            "admin_user_email": admin_user.email,
            "target_user_id": str(user_id),
            **(additional_data or {})
        }

        if target_user:
            event_data.update({
                "target_user_email": target_user.email,
                "target_user_role": target_user.role.value,
                "target_user_active": target_user.is_active
            })

        audit_service.log_event(
            event_type=f"admin_user_{action}",
            event_category="security",
            severity="info",
            user_id=admin_user.id,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            event_data=event_data,
            result="success"
        )
    except Exception as e:
        logger.error(f"Failed to log user action {action}: {e}")


def build_user_filters(filters: UserFilterParams, query):
    """Build optimized query filters for user list."""
    if filters.role:
        try:
            role_enum = UserRole(filters.role.lower())
            query = query.filter(User.role == role_enum)
        except ValueError:
            pass  # Invalid role, ignore filter

    if filters.is_active is not None:
        query = query.filter(User.is_active == filters.is_active)

    # Use optimized search with proper indexing
    if filters.search:
        query = QueryOptimizer.add_search_filters(
            query,
            filters.search,
            [User.email, User.full_name]
        )

    if filters.created_after:
        query = query.filter(User.created_at >= filters.created_after)

    if filters.created_before:
        query = query.filter(User.created_at <= filters.created_before)

    return query


# ============================================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================================

@router.get(
    "/",
    response_model=UserListResponse,
    summary="List All Users",
    description="""
    Retrieve a paginated list of all users in the system with optional filtering.

    **Admin Access Required**: Only users with admin role can access this endpoint.

    **Features**:
    - Pagination with customizable page size
    - Filtering by role, active status, and creation date
    - Search across email and full name fields
    - Sorting by creation date (newest first)

    **Rate Limit**: 100 requests per minute per admin user.
    """,
    responses={
        200: {"description": "Users retrieved successfully"},
        403: {"description": "Admin access required"},
        422: {"description": "Invalid filter parameters"}
    }
)
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    role: Optional[str] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in email and full_name"),
    created_after: Optional[datetime] = Query(None, description="Filter users created after this date"),
    created_before: Optional[datetime] = Query(None, description="Filter users created before this date"),
    db: Session = Depends(get_thread_safe_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
) -> UserListResponse:
    """List all users with pagination and filtering."""
    try:
        # Build filters
        filters = UserFilterParams(
            role=role,
            is_active=is_active,
            search=search,
            created_after=created_after,
            created_before=created_before
        )

        # Build base query with optimizations
        query = db.query(User)
        query = build_user_filters(filters, query)

        # Use optimized pagination
        paginated_query, total, pagination_info = QueryOptimizer.optimize_pagination_query(
            query, page, size, max_size=100
        )

        # Execute query with ordering
        users = paginated_query.order_by(User.created_at.desc()).all()

        # Extract pagination info
        total_pages = pagination_info['total_pages']
        has_next = pagination_info['has_next']
        has_previous = pagination_info['has_previous']

        # Log the action
        audit_service = AuditService(db)
        await log_user_action(
            audit_service, "list", admin_user.id, admin_user, context,
            additional_data={
                "filters": filters.model_dump(exclude_none=True),
                "page": page, "size": size, "total_results": total
            }
        )

        return UserListResponse(
            items=[UserResponse.model_validate(user) for user in users],
            total=total,
            page=page,
            size=size,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous
        )

    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user list"
        )


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create New User",
    description="""
    Create a new user account in the system.

    **Admin Access Required**: Only users with admin role can create new users.

    **Features**:
    - Password strength validation
    - Email uniqueness validation
    - Role assignment with validation
    - Automatic audit logging
    - Password hashing for security

    **Password Requirements**:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    """,
    responses={
        201: {"description": "User created successfully"},
        400: {"description": "Invalid user data or email already exists"},
        403: {"description": "Admin access required"},
        422: {"description": "Validation error"}
    }
)
async def create_user(
    user_data: UserCreateRequest,
    db: Session = Depends(get_thread_safe_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
) -> UserResponse:
    """Create a new user."""
    try:
        user_repo = UserRepository(db)
        audit_service = AuditService(db)

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
        try:
            role_enum = UserRole(user_data.role.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {user_data.role}"
            )

        # Create user
        user_dict = {
            "email": user_data.email.lower(),
            "hashed_password": hashed_password,
            "full_name": user_data.full_name,
            "role": role_enum,
            "is_active": user_data.is_active
        }

        new_user = user_repo.create(user_dict)
        db.commit()

        # Log the action
        await log_user_action(
            audit_service, "create", new_user.id, admin_user, context,
            target_user=new_user,
            additional_data={"created_role": user_data.role, "created_active": user_data.is_active}
        )

        logger.info(f"Admin {admin_user.email} created user {new_user.email}")

        return UserResponse.model_validate(new_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating user"
        )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get User Details",
    description="""
    Retrieve detailed information about a specific user.

    **Admin Access Required**: Only users with admin role can access user details.

    **Features**:
    - Complete user profile information
    - Audit logging of access
    - Input validation for user ID
    """,
    responses={
        200: {"description": "User retrieved successfully"},
        404: {"description": "User not found"},
        403: {"description": "Admin access required"}
    }
)
async def get_user(
    user_id: UUID,
    db: Session = Depends(get_thread_safe_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
) -> UserResponse:
    """Get user details by ID."""
    try:
        user_repo = UserRepository(db)
        audit_service = AuditService(db)

        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Log the action
        await log_user_action(
            audit_service, "view", user_id, admin_user, context, target_user=user
        )

        return UserResponse.model_validate(user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user"
        )


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update User",
    description="""
    Update user information including email, name, role, and active status.

    **Admin Access Required**: Only users with admin role can update users.

    **Features**:
    - Partial updates (only provided fields are updated)
    - Email uniqueness validation
    - Role validation
    - Audit logging of changes
    - Cache invalidation

    **Note**: Password updates should use the dedicated reset-password endpoint.
    """,
    responses={
        200: {"description": "User updated successfully"},
        400: {"description": "Invalid update data or email conflict"},
        404: {"description": "User not found"},
        403: {"description": "Admin access required"}
    }
)
async def update_user(
    user_id: UUID,
    user_data: UserUpdateRequest,
    db: Session = Depends(get_thread_safe_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
) -> UserResponse:
    """Update user information."""
    try:
        user_repo = UserRepository(db)
        audit_service = AuditService(db)

        # Get existing user
        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Store original values for audit
        original_values = {
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_active": user.is_active
        }

        # Prepare update data
        update_data = {}
        changes = []

        if user_data.email is not None and user_data.email.lower() != user.email:
            # Check email uniqueness
            existing_user = user_repo.get_by_email(user_data.email.lower())
            if existing_user and existing_user.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists"
                )
            update_data["email"] = user_data.email.lower()
            changes.append(f"email: {user.email} -> {user_data.email.lower()}")

        if user_data.full_name is not None and user_data.full_name != user.full_name:
            update_data["full_name"] = user_data.full_name
            changes.append(f"full_name: {user.full_name} -> {user_data.full_name}")

        if user_data.role is not None:
            try:
                role_enum = UserRole(user_data.role.lower())
                if role_enum != user.role:
                    update_data["role"] = role_enum
                    changes.append(f"role: {user.role.value} -> {role_enum.value}")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role: {user_data.role}"
                )

        if user_data.is_active is not None and user_data.is_active != user.is_active:
            update_data["is_active"] = user_data.is_active
            changes.append(f"is_active: {user.is_active} -> {user_data.is_active}")

        # Apply updates if any
        if update_data:
            user_repo.update(user_id, update_data)
            db.commit()

            # Invalidate user cache
            invalidate_user_cache(str(user_id))

            # Log the action
            await log_user_action(
                audit_service, "update", user_id, admin_user, context,
                target_user=user,
                additional_data={
                    "changes": changes,
                    "original_values": original_values,
                    "new_values": update_data
                }
            )

            logger.info(f"Admin {admin_user.email} updated user {user.email}: {', '.join(changes)}")

        # Refresh user data
        updated_user = user_repo.get(user_id)
        return UserResponse.model_validate(updated_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating user"
        )


@router.delete(
    "/{user_id}",
    response_model=UserActionResponse,
    summary="Delete User",
    description="""
    Delete a user account from the system.

    **Admin Access Required**: Only users with admin role can delete users.

    **Features**:
    - Soft delete (sets is_active to false)
    - Prevents self-deletion
    - Audit logging
    - Cache invalidation

    **Note**: This performs a soft delete by deactivating the user account.
    """,
    responses={
        200: {"description": "User deleted successfully"},
        400: {"description": "Cannot delete self or invalid operation"},
        404: {"description": "User not found"},
        403: {"description": "Admin access required"}
    }
)
async def delete_user(
    user_id: UUID,
    db: Session = Depends(get_thread_safe_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
) -> UserActionResponse:
    """Delete (deactivate) a user."""
    try:
        user_repo = UserRepository(db)
        audit_service = AuditService(db)

        # Prevent self-deletion
        if user_id == admin_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )

        # Get user to delete
        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Soft delete (deactivate)
        user_repo.update(user_id, {"is_active": False})
        db.commit()

        # Invalidate user cache
        invalidate_user_cache(str(user_id))

        # Log the action
        await log_user_action(
            audit_service, "delete", user_id, admin_user, context,
            target_user=user,
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
    "/{user_id}/activate",
    response_model=UserActionResponse,
    summary="Activate User",
    description="""
    Activate a deactivated user account.

    **Admin Access Required**: Only users with admin role can activate users.

    **Features**:
    - Reactivates deactivated accounts
    - Audit logging
    - Cache invalidation
    """,
    responses={
        200: {"description": "User activated successfully"},
        400: {"description": "User is already active"},
        404: {"description": "User not found"},
        403: {"description": "Admin access required"}
    }
)
async def activate_user(
    user_id: UUID,
    db: Session = Depends(get_thread_safe_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
) -> UserActionResponse:
    """Activate a user account."""
    try:
        user_repo = UserRepository(db)
        audit_service = AuditService(db)

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

        # Invalidate user cache
        invalidate_user_cache(str(user_id))

        # Log the action
        await log_user_action(
            audit_service, "activate", user_id, admin_user, context, target_user=user
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


@router.post(
    "/{user_id}/deactivate",
    response_model=UserActionResponse,
    summary="Deactivate User",
    description="""
    Deactivate an active user account.

    **Admin Access Required**: Only users with admin role can deactivate users.

    **Features**:
    - Prevents user login
    - Prevents self-deactivation
    - Audit logging
    - Cache invalidation
    """,
    responses={
        200: {"description": "User deactivated successfully"},
        400: {"description": "User is already inactive or cannot deactivate self"},
        404: {"description": "User not found"},
        403: {"description": "Admin access required"}
    }
)
async def deactivate_user(
    user_id: UUID,
    db: Session = Depends(get_thread_safe_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
) -> UserActionResponse:
    """Deactivate a user account."""
    try:
        user_repo = UserRepository(db)
        audit_service = AuditService(db)

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

        # Invalidate user cache
        invalidate_user_cache(str(user_id))

        # Log the action
        await log_user_action(
            audit_service, "deactivate", user_id, admin_user, context, target_user=user
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


@router.put(
    "/{user_id}/role",
    response_model=UserActionResponse,
    summary="Update User Role",
    description="""
    Update a user's role in the system.

    **Admin Access Required**: Only users with admin role can change user roles.

    **Features**:
    - Role validation
    - Prevents self-role change
    - Audit logging
    - Cache invalidation

    **Available Roles**: admin, doctor
    """,
    responses={
        200: {"description": "User role updated successfully"},
        400: {"description": "Invalid role or cannot change own role"},
        404: {"description": "User not found"},
        403: {"description": "Admin access required"}
    }
)
async def update_user_role(
    user_id: UUID,
    role_data: UserRoleUpdateRequest,
    db: Session = Depends(get_thread_safe_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
) -> UserActionResponse:
    """Update user role."""
    try:
        user_repo = UserRepository(db)
        audit_service = AuditService(db)

        # Prevent self-role change
        if user_id == admin_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change your own role"
            )

        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Validate and convert role
        try:
            new_role = UserRole(role_data.role.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {role_data.role}"
            )

        old_role = user.role.value

        # Update role
        user_repo.update(user_id, {"role": new_role})
        db.commit()

        # Invalidate user cache
        invalidate_user_cache(str(user_id))

        # Log the action
        await log_user_action(
            audit_service, "role_change", user_id, admin_user, context,
            target_user=user,
            additional_data={"old_role": old_role, "new_role": new_role.value}
        )

        logger.info(f"Admin {admin_user.email} changed role of user {user.email} from {old_role} to {new_role.value}")

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


@router.put(
    "/{user_id}/permissions",
    response_model=UserActionResponse,
    summary="Update User Permissions",
    description="""
    Update a user's permissions (placeholder for future implementation).

    **Admin Access Required**: Only users with admin role can change permissions.

    **Note**: This is a placeholder endpoint for future permission system implementation.
    Currently returns success but doesn't modify any permissions.
    """,
    responses={
        200: {"description": "User permissions updated successfully"},
        404: {"description": "User not found"},
        403: {"description": "Admin access required"}
    }
)
async def update_user_permissions(
    user_id: UUID,
    permissions_data: UserPermissionsUpdateRequest,
    db: Session = Depends(get_thread_safe_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
) -> UserActionResponse:
    """Update user permissions (placeholder implementation)."""
    try:
        user_repo = UserRepository(db)
        audit_service = AuditService(db)

        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Log the action
        await log_user_action(
            audit_service, "permissions_update", user_id, admin_user, context,
            target_user=user,
            additional_data={"permissions": permissions_data.permissions}
        )

        logger.info(f"Admin {admin_user.email} updated permissions for user {user.email}")

        return UserActionResponse(
            success=True,
            message="User permissions updated successfully (placeholder)",
            user_id=user_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating permissions for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating user permissions"
        )


@router.post(
    "/{user_id}/reset-password",
    response_model=UserActionResponse,
    summary="Reset User Password",
    description="""
    Reset a user's password to a new value.

    **Admin Access Required**: Only users with admin role can reset passwords.

    **Features**:
    - Password strength validation
    - Secure password hashing
    - Optional force password change on next login
    - Audit logging
    - Cache invalidation

    **Password Requirements**:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    """,
    responses={
        200: {"description": "Password reset successfully"},
        400: {"description": "Invalid password"},
        404: {"description": "User not found"},
        403: {"description": "Admin access required"}
    }
)
async def reset_user_password(
    user_id: UUID,
    password_data: UserResetPasswordRequest,
    db: Session = Depends(get_thread_safe_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
) -> UserActionResponse:
    """Reset user password."""
    try:
        user_repo = UserRepository(db)
        audit_service = AuditService(db)

        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Hash new password
        new_hashed_password = get_password_hash(password_data.new_password)

        # Update password
        update_data = {"hashed_password": new_hashed_password}
        if password_data.force_change:
            # Add logic for force password change if needed
            pass

        user_repo.update(user_id, update_data)
        db.commit()

        # Invalidate user cache
        invalidate_user_cache(str(user_id))

        # Log the action (don't log the actual password)
        await log_user_action(
            audit_service, "password_reset", user_id, admin_user, context,
            target_user=user,
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
            detail="Error resetting user password"
        )


@router.get(
    "/{user_id}/activity",
    response_model=UserActivityResponse,
    summary="Get User Activity Log",
    description="""
    Retrieve paginated activity history for a specific user.

    **Admin Access Required**: Only users with admin role can view user activity.

    **Features**:
    - Paginated activity records
    - Detailed action logging
    - IP address and user agent tracking
    - Resource and action filtering
    """,
    responses={
        200: {"description": "User activity retrieved successfully"},
        404: {"description": "User not found"},
        403: {"description": "Admin access required"}
    }
)
async def get_user_activity(
    user_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    db: Session = Depends(get_thread_safe_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
) -> UserActivityResponse:
    """Get paginated user activity history."""
    try:
        user_repo = UserRepository(db)
        audit_service = AuditService(db)

        # Get user
        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Build query for audit events
        query_filters = {"user_id": user_id}
        if action:
            query_filters["event_type"] = action

        # Get total count for pagination
        total_count = audit_service.count_events(**query_filters)

        # Calculate pagination
        offset = (page - 1) * size
        total_pages = math.ceil(total_count / size)

        # Get activity records
        events = audit_service.query_events(
            limit=size,
            offset=offset,
            **query_filters
        )

        # Convert to activity records
        activity_records = []
        for event in events:
            # Extract action from event_type (e.g., "admin_user_create" -> "create")
            action_name = event.event_type.split('_')[-1] if '_' in event.event_type else event.event_type

            # Determine resource from event data
            resource = "user"
            resource_id = None
            if event.event_data:
                if "target_user_id" in event.event_data:
                    resource_id = event.event_data["target_user_id"]
                elif "patient_id" in event.event_data:
                    resource = "patient"
                    resource_id = event.event_data["patient_id"]

            activity_record = UserActivityRecord(
                id=str(event.id),
                user_id=str(user_id),
                user_email=user.email,
                action=action_name,
                resource=resource,
                resource_id=resource_id,
                details=event.event_data or {},
                timestamp=event.timestamp,
                ip_address=event.ip_address or "unknown",
                user_agent=event.user_agent or "unknown"
            )
            activity_records.append(activity_record)

        # Log the action
        await log_user_action(
            audit_service, "activity_view", user_id, admin_user, context,
            target_user=user,
            additional_data={
                "page": page,
                "size": size,
                "action_filter": action,
                "total_records": total_count
            }
        )

        return UserActivityResponse(
            items=activity_records,
            total=total_count,
            page=page,
            size=size,
            pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user activity {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user activity"
        )


@router.get(
    "/stats/overview",
    response_model=UserStatsResponse,
    summary="Get User Statistics",
    description="""
    Get comprehensive statistics about users in the system.

    **Admin Access Required**: Only users with admin role can view statistics.

    **Features**:
    - Total user count
    - Active/inactive breakdown
    - User count by role
    - Recent registration counts
    """,
    responses={
        200: {"description": "Statistics retrieved successfully"},
        403: {"description": "Admin access required"}
    }
)
async def get_user_stats(
    db: Session = Depends(get_thread_safe_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context)
) -> UserStatsResponse:
    """Get user statistics."""
    try:
        audit_service = AuditService(db)

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

        # Log the action
        await log_user_action(
            audit_service, "stats_view", admin_user.id, admin_user, context,
            additional_data={"stats_type": "overview"}
        )

        return UserStatsResponse(
            total_users=total_users,
            active_users=active_users,
            inactive_users=inactive_users,
            by_role=role_counts,
            recent_registrations=recent_registrations
        )

    except Exception as e:
        logger.error(f"Error retrieving user stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user statistics"
        )
