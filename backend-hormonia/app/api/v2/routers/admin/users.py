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

import csv
import io
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.core.database.async_engine import get_async_db
from app.database import get_db
from app.models.user import AuthProvider, User, UserRole
from app.services.password_reset_service import PasswordResetFailure, PasswordResetService
from app.utils.security import get_password_hash
from app.utils.rate_limiter import limiter
from app.infrastructure.cache import (
    cache_response,
    invalidate_user_cache,
)
from app.utils.request_context import get_request_context, RequestContext
from app.schemas.v2.admin import (
    UserCreateRequest,
    UserUpdateRequest,
    UserResponse,
    UserProvisioningResponse,
    UserListResponse,
    UserActionResponse,
)

# Relative imports for dependencies and utils
from .dependencies import get_admin_user
from .utils import (
    _serialize_user,
    _log_admin_action,
    _password_reset_failure_response,
    _validate_password_strength,
)
from app.api.v2.dependencies import (
    get_pagination_params,
    get_field_selection,
    create_cursor,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class BulkUserUpdateRequest(BaseModel):
    """Schema for bulk updating users."""

    user_ids: List[UUID] = Field(..., min_length=1)
    updates: Dict[str, Any] = Field(default_factory=dict)


class BulkUserDeleteRequest(BaseModel):
    """Schema for bulk deleting (deactivating) users."""

    user_ids: List[UUID] = Field(..., min_length=1)
    reason: Optional[str] = None


class ExportUsersRequest(BaseModel):
    """Schema for exporting users."""

    format: str = Field(..., description="Export format: csv or json")
    fields: Optional[List[str]] = None


class UserSearchRequest(BaseModel):
    """Schema for searching users."""

    query: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None


def _normalize_bulk_updates(updates: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(updates)

    if "email" in normalized and isinstance(normalized["email"], str):
        normalized["email"] = normalized["email"].lower()

    if "role" in normalized and isinstance(normalized["role"], str):
        try:
            normalized["role"] = UserRole(normalized["role"].lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role. Valid roles: admin, doctor",
            )

    return normalized


def _apply_user_filters(
    stmt,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
):
    """Apply common user filters to a query."""
    if role:
        try:
            role_enum = UserRole(role.lower())
            stmt = stmt.where(User.role == role_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {role}. Valid roles: admin, doctor",
            )

    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))

    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                User.email.ilike(search_pattern),
                User.full_name.ilike(search_pattern),
            )
        )

    if created_after:
        stmt = stmt.where(User.created_at >= created_after)

    if created_before:
        stmt = stmt.where(User.created_at <= created_before)

    return stmt


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
    db: AsyncSession = Depends(get_async_db),
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
        limit_provided = "limit" in request.query_params
        effective_limit = limit if use_cursor or limit_provided else size

        # Parse field selection
        field_list = get_field_selection(fields) if fields else None

        # Build base query
        query = select(User)

        # Apply cursor pagination if using cursor mode
        if use_cursor:
            pagination = get_pagination_params(cursor, effective_limit)
            cursor_data = pagination.get("cursor_data")
            if cursor_data:
                query = query.where(User.id > cursor_data.get("id", 0))

        query = _apply_user_filters(query, role=role, is_active=is_active, search=search)

        # Order by ID for consistent pagination
        query = query.order_by(User.id)

        # Get total count for offset-based pagination
        total = None
        total_pages = None
        has_next = None
        has_previous = None
        page_value = None
        size_value = None
        if not use_cursor:
            total_query = _apply_user_filters(
                select(func.count(User.id)), role=role, is_active=is_active, search=search
            )
            total_result = await db.execute(total_query)
            total = total_result.scalar() or 0
            # Apply offset
            offset = (page - 1) * effective_limit
            query = query.offset(offset)
            page_value = page
            size_value = effective_limit
            total_pages = (
                int((total + effective_limit - 1) / effective_limit)
                if effective_limit
                else 0
            )
            has_next = page_value < total_pages if total_pages is not None else None
            has_previous = page_value > 1 if page_value is not None else None

        # Fetch limit + 1 to check if there's more
        users_result = await db.execute(query.limit(effective_limit + 1))
        users = users_result.scalars().all()

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
            "items": serialized_users,
            "users": serialized_users,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total": total,
            "page": page_value,
            "size": size_value,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_previous": has_previous,
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
    "/users/{user_id:uuid}",
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
    db: AsyncSession = Depends(get_async_db),
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
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
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
    response_model=UserProvisioningResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create New User",
    description="Create a new user account either with an immediate password or via first-access recovery email.",
)
@limiter.limit("10/hour")  # Strict rate limit for user creation
async def create_user(
    request: Request,
    user_data: UserCreateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """
    Create a new user.

    Features:
    - Legacy password-based provisioning compatibility
    - First-access recovery email provisioning without plaintext passwords
    - Email uniqueness check
    - Role assignment
    - Audit logging
    """
    try:
        normalized_email = user_data.email.lower()

        # Check if email already exists
        existing_user = db.query(User).filter(User.email == normalized_email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

        # Convert role string to enum
        role_enum = UserRole(user_data.role.lower())

        is_first_access = bool(user_data.send_activation_email)
        hashed_password = None
        if not is_first_access:
            _validate_password_strength(user_data.password)
            hashed_password = get_password_hash(user_data.password)

        new_user = User(
            email=normalized_email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            role=role_enum,
            is_active=user_data.is_active,
            auth_provider=AuthProvider.LOCAL,
            force_change_password=is_first_access,
            failed_login_attempts=0,
            is_locked=False,
            locked_until=None,
            last_password_change=None,
        )
        db.add(new_user)
        db.flush()

        delivery_result = None
        if is_first_access:
            reset_service = PasswordResetService(db)
            try:
                delivery_result = await reset_service.request_password_reset_for_user(new_user)
            except PasswordResetFailure as exc:
                db.rollback()
                await _log_admin_action(
                    db,
                    "create_user_first_access_failed",
                    admin_user,
                    context,
                    additional_data={
                        "created_email": normalized_email,
                        "created_role": user_data.role,
                        "error": exc.error_code,
                    },
                )
                return _password_reset_failure_response(request, exc)

        db.commit()
        db.refresh(new_user)

        # Log action
        await _log_admin_action(
            db,
            "create_user_first_access" if is_first_access else "create_user",
            admin_user,
            context,
            target_user_id=new_user.id,
            additional_data={
                "created_email": normalized_email,
                "created_role": user_data.role,
                "provisioning_mode": "first_access_email" if is_first_access else "direct_password",
                "delivery_status": getattr(delivery_result, "status", None),
            },
        )

        logger.info(
            "Admin provisioned user",
            extra={
                "admin_email": admin_user.email,
                "created_email": new_user.email,
                "provisioning_mode": "first_access_email" if is_first_access else "direct_password",
            },
        )

        response_payload = _serialize_user(new_user)
        if is_first_access and delivery_result is not None:
            response_payload["first_access"] = {
                "required": True,
                "delivery": delivery_result.status,
                "channel": delivery_result.channel,
                "ready_for_login": False,
                "message_id": delivery_result.message_id,
            }

        return response_payload

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
    "/users/{user_id:uuid}",
    response_model=UserResponse,
    summary="Update User",
    description="Update user information with cache invalidation.",
)
@limiter.limit("20/hour")  # Rate limit for updates
async def update_user(
    request: Request,
    user_id: UUID,
    user_data: UserUpdateRequest,
    db: AsyncSession = Depends(get_async_db),
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
        # Get existing user
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Prepare update data
        update_data = {}
        changes = []

        if user_data.email and user_data.email.lower() != user.email:
            # Check email uniqueness
            existing_result = await db.execute(
                select(User).where(User.email == user_data.email.lower())
            )
            existing = existing_result.scalar_one_or_none()
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
            for key, value in update_data.items():
                setattr(user, key, value)
            await db.commit()

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
        await db.refresh(user)
        return _serialize_user(user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user: {str(e)}",
        )


# ============================================================================
# ENDPOINT 5: DELETE USER
# ============================================================================


@router.delete(
    "/users/{user_id:uuid}",
    response_model=UserActionResponse,
    summary="Delete User (Soft Delete)",
    description="Soft delete (deactivate) a user account.",
)
@limiter.limit("10/hour")  # Strict rate limit for deletions
async def delete_user(
    request: Request,
    user_id: UUID,
    db: AsyncSession = Depends(get_async_db),
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
        # Prevent self-deletion
        if user_id == admin_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account",
            )

        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Soft delete (deactivate)
        user.is_active = False
        await db.commit()

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
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting user",
        )


# ============================================================================
# ENDPOINT 6: BULK UPDATE USERS
# ============================================================================


@router.post(
    "/users/bulk-update",
    summary="Bulk update users",
    description="Update multiple users in a single request.",
)
@limiter.limit("10/hour")
async def bulk_update_users(
    request: Request,
    bulk_data: BulkUserUpdateRequest,
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """Bulk update users with basic validation."""
    if len(bulk_data.user_ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bulk update limit exceeded (max 100 users)",
        )

    errors = []
    success_count = 0
    normalized_updates = _normalize_bulk_updates(bulk_data.updates)

    try:
        for user_id in bulk_data.user_ids:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                errors.append({"user_id": str(user_id), "error": "User not found"})
                continue
            for key, value in normalized_updates.items():
                setattr(user, key, value)
            success_count += 1

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    for user_id in bulk_data.user_ids:
        invalidate_user_cache(str(user_id))

    await _log_admin_action(
        db,
        "bulk_update_users",
        admin_user,
        context,
        additional_data={"successful": success_count, "failed": len(errors)},
    )

    return {
        "success": len(errors) == 0,
        "successful": success_count,
        "failed": len(errors),
        "errors": errors,
    }


# ============================================================================
# ENDPOINT 7: BULK DELETE USERS
# ============================================================================


@router.post(
    "/users/bulk-delete",
    summary="Bulk delete users",
    description="Soft delete (deactivate) multiple users.",
)
@limiter.limit("10/hour")
async def bulk_delete_users(
    request: Request,
    bulk_data: BulkUserDeleteRequest,
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """Bulk deactivate users with safety checks."""
    if len(bulk_data.user_ids) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bulk delete limit exceeded (max 50 users)",
        )

    if admin_user.id in bulk_data.user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    errors = []
    success_count = 0

    try:
        for user_id in bulk_data.user_ids:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                errors.append({"user_id": str(user_id), "error": "User not found"})
                continue
            user.is_active = False
            success_count += 1

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    for user_id in bulk_data.user_ids:
        invalidate_user_cache(str(user_id))

    await _log_admin_action(
        db,
        "bulk_delete_users",
        admin_user,
        context,
        additional_data={"successful": success_count, "failed": len(errors)},
    )

    return {
        "success": len(errors) == 0,
        "successful": success_count,
        "failed": len(errors),
        "errors": errors,
    }


# ============================================================================
# ENDPOINT 8: EXPORT USERS
# ============================================================================


@router.post(
    "/users/export",
    summary="Export users",
    description="Export users in CSV or JSON format.",
)
@limiter.limit("5/minute")
async def export_users(
    request: Request,
    export_request: ExportUsersRequest,
    role: Optional[str] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """Export users with optional filters."""
    query = _apply_user_filters(select(User), role=role, is_active=is_active, search=search)
    users_result = await db.execute(query.order_by(User.id))
    users = users_result.scalars().all()

    fields = export_request.fields or [
        "id",
        "email",
        "full_name",
        "role",
        "is_active",
    ]

    def _normalize_value(value):
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, UUID):
            return str(value)
        return value

    rows = []
    for user in users:
        data = _serialize_user(user)
        row = {field: _normalize_value(data.get(field)) for field in fields}
        rows.append(row)

    await _log_admin_action(
        db,
        "export_users",
        admin_user,
        context,
        additional_data={
            "format": export_request.format,
            "count": len(rows),
            "filters": {"role": role, "is_active": is_active, "search": search},
        },
    )

    export_format = export_request.format.lower()
    if export_format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        return Response(content=output.getvalue(), media_type="text/csv")

    if export_format == "json":
        return JSONResponse(content=rows, media_type="application/json")

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported export format",
    )


# ============================================================================
# ENDPOINT 9: SEARCH USERS
# ============================================================================


@router.post(
    "/users/search",
    response_model=UserListResponse,
    summary="Search users",
    description="Search users with filters and date ranges.",
)
@limiter.limit("30/minute")
async def search_users(
    request: Request,
    search_data: UserSearchRequest,
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """Search users with flexible filters."""
    query = _apply_user_filters(
        select(User),
        role=search_data.role,
        is_active=search_data.is_active,
        search=search_data.query,
        created_after=search_data.created_after,
        created_before=search_data.created_before,
    )

    users_result = await db.execute(query.order_by(User.id))
    users = users_result.scalars().all()
    serialized_users = [_serialize_user(user) for user in users]

    await _log_admin_action(
        db,
        "search_users",
        admin_user,
        context,
        additional_data={"count": len(serialized_users)},
    )

    return {
        "data": serialized_users,
        "items": serialized_users,
        "users": serialized_users,
        "next_cursor": None,
        "has_more": False,
        "total": len(serialized_users),
    }


# ============================================================================
# ENDPOINT 10: LIST ACTIVE USERS
# ============================================================================


@router.get(
    "/users/active",
    response_model=UserListResponse,
    summary="List active users",
    description="List all active users.",
)
@limiter.limit("30/minute")
async def list_active_users(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """List active users."""
    users_result = await db.execute(
        select(User).where(User.is_active.is_(True)).order_by(User.id)
    )
    users = users_result.scalars().all()
    serialized_users = [_serialize_user(user) for user in users]

    return {
        "data": serialized_users,
        "items": serialized_users,
        "users": serialized_users,
        "next_cursor": None,
        "has_more": False,
        "total": len(serialized_users),
    }


# ============================================================================
# ENDPOINT 11: LIST INACTIVE USERS
# ============================================================================


@router.get(
    "/users/inactive",
    response_model=UserListResponse,
    summary="List inactive users",
    description="List all inactive users.",
)
@limiter.limit("30/minute")
async def list_inactive_users(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """List inactive users."""
    users_result = await db.execute(
        select(User).where(User.is_active.is_(False)).order_by(User.id)
    )
    users = users_result.scalars().all()
    serialized_users = [_serialize_user(user) for user in users]

    return {
        "data": serialized_users,
        "items": serialized_users,
        "users": serialized_users,
        "next_cursor": None,
        "has_more": False,
        "total": len(serialized_users),
    }
