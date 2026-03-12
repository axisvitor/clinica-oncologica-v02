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
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.database.async_engine import get_async_db
from app.database import get_db
from app.models.user import User, UserRole
from app.services.password_reset_service import PasswordResetFailure, PasswordResetService
from app.utils.security import get_password_hash
from app.utils.rate_limiter import limiter
from app.infrastructure.cache import invalidate_user_cache
from app.utils.request_context import get_request_context, RequestContext
from app.schemas.v2.admin import (
    UserActionResponse,
    UserPasswordResetResponse,
    UserResetPasswordRequest,
)

from .dependencies import get_admin_user
from .utils import (
    _log_admin_action,
    _password_reset_failure_response,
    _validate_password_strength,
)

router = APIRouter()
logger = logging.getLogger(__name__)


async def _get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


# ============================================================================
# ENDPOINT 1: ACTIVATE USER
# ============================================================================


@router.post(
    "/users/{user_id}/activate",
    response_model=UserActionResponse,
    summary="Activate User",
    description="Activate a user account (set is_active to True).",
)
@limiter.limit("20/hour")
async def activate_user(
    request: Request,
    user_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """
    Activate a user account.

    Features:
    - Sets is_active to True
    - Cache invalidation
    - Audit logging
    """
    try:
        user = await _get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        if bool(getattr(user, "is_active", False)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="User is already active"
            )

        # Activate user
        setattr(user, "is_active", True)
        await db.commit()

        # Invalidate cache
        invalidate_user_cache(str(user_id))

        # Log action
        await _log_admin_action(
            db,
            "activate_user",
            admin_user,
            context,
            target_user_id=user_id,
            additional_data={"user_email": user.email},
        )

        logger.info(f"Admin {admin_user.email} activated user {user.email}")

        return UserActionResponse(
            success=True, message="User activated successfully", user_id=user_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating user {user_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error activating user",
        )


# ============================================================================
# ENDPOINT 2: DEACTIVATE USER
# ============================================================================


@router.post(
    "/users/{user_id}/deactivate",
    response_model=UserActionResponse,
    summary="Deactivate User",
    description="Deactivate a user account (set is_active to False).",
)
@limiter.limit("20/hour")
async def deactivate_user(
    request: Request,
    user_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
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
        # Prevent self-deactivation
        if user_id == admin_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate your own account",
            )

        user = await _get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        if not bool(getattr(user, "is_active", False)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already inactive",
            )

        # Deactivate user
        setattr(user, "is_active", False)
        await db.commit()

        # Invalidate cache
        invalidate_user_cache(str(user_id))

        # Log action
        await _log_admin_action(
            db,
            "deactivate_user",
            admin_user,
            context,
            target_user_id=user_id,
            additional_data={"user_email": user.email},
        )

        logger.info(f"Admin {admin_user.email} deactivated user {user.email}")

        return UserActionResponse(
            success=True, message="User deactivated successfully", user_id=user_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating user {user_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deactivating user",
        )


# ============================================================================
# ENDPOINT 2.5: RESTORE USER
# ============================================================================


@router.post(
    "/users/{user_id}/restore",
    response_model=UserActionResponse,
    summary="Restore User",
    description="Restore (reactivate) a previously deactivated user account.",
)
@limiter.limit("20/hour")
async def restore_user(
    request: Request,
    user_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """Restore a deactivated user account."""
    try:
        user = await _get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        if bool(getattr(user, "is_active", False)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already active",
            )

        setattr(user, "is_active", True)
        await db.commit()

        invalidate_user_cache(str(user_id))

        await _log_admin_action(
            db,
            "restore_user",
            admin_user,
            context,
            target_user_id=user_id,
            additional_data={"user_email": user.email},
        )

        return UserActionResponse(
            success=True, message="User restored successfully", user_id=user_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring user {user_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error restoring user",
        )


# ============================================================================
# ENDPOINT 3: RESET PASSWORD
# ============================================================================


@router.post(
    "/users/{user_id}/reset-password",
    response_model=UserPasswordResetResponse,
    summary="Reset User Password",
    description="Reset a user's password through the shared email recovery contract or a legacy compatibility fallback.",
)
@limiter.limit("10/hour")  # Strict rate limit for password resets
async def reset_password(
    request: Request,
    user_id: UUID,
    password_data: UserResetPasswordRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    """
    Reset user password.

    Features:
    - Canonical email-backed recovery using the shared password reset service
    - Explicit legacy compatibility fallback for direct password assignment until S03
    - Cache invalidation
    - Audit logging without leaking token or password material
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        if password_data.send_email:
            reset_service = PasswordResetService(db)
            try:
                delivery_result = await reset_service.request_password_reset_for_user(user)
            except PasswordResetFailure as exc:
                db.rollback()
                await _log_admin_action(
                    db,
                    "reset_password_recovery_failed",
                    admin_user,
                    context,
                    target_user_id=user_id,
                    additional_data={
                        "user_email": user.email,
                        "error": exc.error_code,
                    },
                )
                return _password_reset_failure_response(request, exc)

            await _log_admin_action(
                db,
                "reset_password_recovery",
                admin_user,
                context,
                target_user_id=user_id,
                additional_data={
                    "user_email": user.email,
                    "delivery_channel": delivery_result.channel,
                    "delivery_status": delivery_result.status,
                    "first_access": delivery_result.first_access,
                },
            )

            logger.info(
                "Admin triggered email-backed password recovery",
                extra={
                    "admin_email": admin_user.email,
                    "target_user_id": str(user_id),
                    "delivery_channel": delivery_result.channel,
                    "first_access": delivery_result.first_access,
                },
            )

            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content=UserPasswordResetResponse(
                    success=True,
                    message="Recovery email queued successfully",
                    user_id=user_id,
                    delivery={
                        "channel": delivery_result.channel,
                        "status": delivery_result.status,
                        "message_id": delivery_result.message_id,
                    },
                ).model_dump(mode="json"),
            )

        # Explicit compatibility boundary for the pre-S03 admin SPA.
        _validate_password_strength(password_data.new_password)
        user.hashed_password = get_password_hash(password_data.new_password)
        user.force_change_password = bool(password_data.force_change)
        db.add(user)
        db.commit()

        invalidate_user_cache(str(user_id))

        await _log_admin_action(
            db,
            "reset_password_legacy_direct",
            admin_user,
            context,
            target_user_id=user_id,
            additional_data={
                "user_email": user.email,
                "force_change": password_data.force_change,
                "compatibility_mode": "legacy_direct_password",
            },
        )

        logger.info(
            "Admin performed legacy direct password reset",
            extra={
                "admin_email": admin_user.email,
                "target_user_id": str(user_id),
                "compatibility_mode": "legacy_direct_password",
            },
        )

        return UserPasswordResetResponse(
            success=True,
            message="Password reset successfully",
            user_id=user_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting password for user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error resetting password",
        )


# ============================================================================
# ENDPOINT 4: UPDATE ROLE
# ============================================================================


@router.put(
    "/users/{user_id}/role",
    response_model=UserActionResponse,
    summary="Update User Role",
    description="Update a user's role with audit logging.",
)
@limiter.limit("20/hour")
async def update_role(
    request: Request,
    user_id: UUID,
    role: str = Query(..., description="New role (admin or doctor)"),
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
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
        user = await _get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Validate role
        try:
            new_role = UserRole(role.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {role}. Valid roles: admin, doctor",
            )

        # Prevent self-demotion from admin
        if user_id == admin_user.id and new_role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote your own admin role",
            )

        old_role = user.role
        old_role_value = old_role.value if hasattr(old_role, "value") else str(old_role)

        # Update role
        setattr(user, "role", new_role)
        await db.commit()

        # Invalidate cache
        invalidate_user_cache(str(user_id))

        # Log action
        await _log_admin_action(
            db,
            "update_role",
            admin_user,
            context,
            target_user_id=user_id,
            additional_data={
                "user_email": user.email,
                "old_role": old_role_value,
                "new_role": new_role.value,
            },
        )

        logger.info(
            f"Admin {admin_user.email} updated role for user {user.email}: {old_role_value} -> {new_role.value}"
        )

        return UserActionResponse(
            success=True,
            message=f"User role updated to {new_role.value}",
            user_id=user_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating role for user {user_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating user role",
        )
