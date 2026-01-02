"""
Admin API v2 - User Management Routes
User CRUD operations with strict access control.

Features:
- 5 core user management endpoints (list, get, create, update, delete)
- Cursor-based pagination with Redis caching
- RBAC with admin-only access control
- Comprehensive audit logging for all operations
- Password strength validation
- Rate limiting on sensitive operations
- Field selection and eager loading support
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import or_

from app.database import get_db
from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.utils.security import get_password_hash
from app.utils.rate_limiter import limiter
from app.infrastructure.cache import (
    cache_response,
    invalidate_user_cache,
)
from app.dependencies import get_request_context, RequestContext
from app.schemas.v2.admin import (
    UserCreateRequest,
    UserUpdateRequest,
    UserResponse,
    UserListResponse,
    UserActionResponse,
)

# Relative imports for dependencies and utils
from .dependencies import get_admin_user
from .utils import (
    _serialize_user,
    _log_admin_action,
    _validate_password_strength,
)
from app.api.v2.dependencies import (
    get_pagination_params,
    get_field_selection,
    create_cursor,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# ENDPOINT 1: LIST USERS
# ============================================================================


@router.get(
    "/users",
    response_model=UserListResponse,
    summary="List Users with Pagination",
    description="Retrieve paginated list of users with cursor-based or offset-based pagination, field selection, and eager loading.",
)
@limiter.limit("100/minute")
async def list_users(
    request: Request,
    # Cursor-based pagination
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (used with cursor)"),
    # Offset-based pagination (for backwards compatibility)
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    # Filters
    fields: Optional[str] = Query(None, description="Comma-separated fields to include"),
    role: Optional[str] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in email and full_name"),
    db=Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """
    List all users with pagination and filters.

    Features:
    - Cursor-based pagination (efficient for large datasets)
    - Offset-based pagination (page/size) for backwards compatibility
    - Field selection (?fields=id,email,role)
    - Role and status filters
    - Search by email or name
    """
    try:
        # Determine pagination mode
        use_cursor = cursor is not None
        effective_limit = limit if use_cursor else size

        # Parse field selection
        field_list = get_field_selection(fields) if fields else None

        # Build base query
        query = db.query(User)

        # Apply cursor pagination if using cursor mode
        if use_cursor:
            pagination = get_pagination_params(cursor, effective_limit)
            cursor_data = pagination.get("cursor_data")
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
                    detail=f"Invalid role: {role}. Valid roles: admin, doctor",
                )

        if is_active is not None:
            query = query.filter(User.is_active == is_active)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    User.email.ilike(search_pattern),
                    User.full_name.ilike(search_pattern),
                )
            )

        # Order by ID for consistent pagination
        query = query.order_by(User.id)

        # Get total count for offset-based pagination
        total = None
        if not use_cursor:
            total = query.count()
            # Apply offset
            offset = (page - 1) * size
            query = query.offset(offset)

        # Fetch limit + 1 to check if there's more
        users = query.limit(effective_limit + 1).all()

        # Check if there are more results
        has_more = len(users) > effective_limit
        if has_more:
            users = users[:effective_limit]

        # Create next cursor (only for cursor-based pagination)
        next_cursor = None
        if use_cursor and has_more and users:
            next_cursor = create_cursor(users[-1].id)

        # Serialize users
        serialized_users = [_serialize_user(user, field_list) for user in users]

        try:
            # Log action
            await _log_admin_action(
                db,
                "list_users",
                admin_user,
                context,
                additional_data={
                    "count": len(users),
                    "filters": {"role": role, "is_active": is_active, "search": search},
                },
            )
        except Exception as e:
            logger.error(f"FAILED TO LOG ACTION: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Don't fail the request just because logging failed
            pass

        return {
            "data": serialized_users,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": total,
        }

    except HTTPException:
        raise


    except Exception as e:
        import traceback
        logger.error(f"Error listing users: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user list: {str(e)}",
        )


# ============================================================================
# ENDPOINT 2: GET SINGLE USER
# ============================================================================


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Get User Details",
    description="Retrieve detailed information about a specific user. Cached for 10 minutes.",
)
@cache_response(ttl=600, key_prefix="admin:user")  # Cache for 10 minutes
async def get_user(
    user_id: UUID,
    fields: Optional[str] = Query(
        None, description="Comma-separated fields to include"
    ),
    db=Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
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
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
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
            detail="Error retrieving user",
        )


# ============================================================================
# ENDPOINT 3: CREATE USER
# ============================================================================


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create New User",
    description="Create a new user account with password validation and role assignment.",
)
@limiter.limit("10/hour")  # Strict rate limit for user creation
async def create_user(
    request: Request,
    user_data: UserCreateRequest,
    db=Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
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
                detail="User with this email already exists",
            )

        # Validate password strength
        _validate_password_strength(user_data.password)

        # Hash password
        hashed_password = get_password_hash(user_data.password)

        # Convert role string to enum
        role_enum = UserRole(user_data.role.lower())

        # Create user
        new_user = user_repo.create(
            {
                "email": user_data.email.lower(),
                "hashed_password": hashed_password,
                "full_name": user_data.full_name,
                "role": role_enum,
                "is_active": user_data.is_active,
            }
        )
        db.commit()
        db.refresh(new_user)

        # Log action
        await _log_admin_action(
            db,
            "create_user",
            admin_user,
            context,
            target_user_id=new_user.id,
            additional_data={
                "created_email": user_data.email,
                "created_role": user_data.role,
            },
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
            detail=f"Error creating user: {str(e)}",
        )


# ============================================================================
# ENDPOINT 4: UPDATE USER
# ============================================================================


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Update User",
    description="Update user information with cache invalidation.",
)
@limiter.limit("20/hour")  # Rate limit for updates
async def update_user(
    request: Request,
    user_id: UUID,
    user_data: UserUpdateRequest,
    db=Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
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
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
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
                    detail="Email already exists",
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
                db,
                "update_user",
                admin_user,
                context,
                target_user_id=user_id,
                additional_data={"changes": changes},
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
            detail=f"Error updating user: {str(e)}",
        )


# ============================================================================
# ENDPOINT 5: DELETE USER
# ============================================================================


@router.delete(
    "/users/{user_id}",
    response_model=UserActionResponse,
    summary="Delete User (Soft Delete)",
    description="Soft delete (deactivate) a user account.",
)
@limiter.limit("10/hour")  # Strict rate limit for deletions
async def delete_user(
    request: Request,
    user_id: UUID,
    db=Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
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
                detail="Cannot delete your own account",
            )

        user = user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Soft delete (deactivate)
        user_repo.update(user_id, {"is_active": False})
        db.commit()

        # Invalidate cache
        invalidate_user_cache(str(user_id))

        # Log action
        await _log_admin_action(
            db,
            "delete_user",
            admin_user,
            context,
            target_user_id=user_id,
            additional_data={"deletion_type": "soft_delete", "user_email": user.email},
        )

        logger.info(f"Admin {admin_user.email} deleted user {user.email}")

        return UserActionResponse(
            success=True, message="User deleted successfully", user_id=user_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting user",
        )
