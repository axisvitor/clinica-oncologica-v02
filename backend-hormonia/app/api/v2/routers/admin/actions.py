"""
Admin Actions API v2
User action endpoints: activate, deactivate, reset password, update role.

Features:
- User activation/deactivation with cache invalidation
- Password reset with strength validation
- Role management with self-protection
- Comprehensive audit logging
- Rate limiting on sensitive operations
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.utils.security import get_password_hash
from app.utils.rate_limiter import limiter
from app.infrastructure.cache import invalidate_user_cache
from app.dependencies import get_request_context, RequestContext
from app.schemas.v2.admin import (
    UserActionResponse,
    UserResetPasswordRequest,
)

from .dependencies import get_admin_user
from .utils import _log_admin_action, _validate_password_strength

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# ENDPOINT 1: ACTIVATE USER
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
    db = Depends(get_db),
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
# ENDPOINT 2: DEACTIVATE USER
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
    db = Depends(get_db),
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
# ENDPOINT 3: RESET PASSWORD
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
    db = Depends(get_db),
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

        # Set force change password flag if requested
        if password_data.force_change:
            update_data["force_change_password"] = True

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
# ENDPOINT 4: UPDATE ROLE
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
    db = Depends(get_db),
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
