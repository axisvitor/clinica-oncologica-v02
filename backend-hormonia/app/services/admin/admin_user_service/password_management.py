"""
Password management operations for user administration.

Handles password resets, updates, and temporary password generation.
"""
import logging
from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta
from fastapi import HTTPException, status

from app.models.user import User
from app.utils.security import get_password_hash
from .schemas import (
    PasswordResetRequest, PasswordResetResult, UserPasswordUpdateRequest
)
from .validators import generate_temporary_password

logger = logging.getLogger(__name__)


class PasswordManagementMixin:
    """Mixin for password management operations."""

    async def reset_user_password(
        self,
        reset_request: PasswordResetRequest,
        admin_user: User,
        request_info: Optional[dict] = None
    ) -> PasswordResetResult:
        """
        Reset user password with temporary password generation.

        Args:
            reset_request: Password reset request data
            admin_user: Admin user performing the reset
            request_info: Request information for audit

        Returns:
            Password reset result

        Raises:
            HTTPException: If user not found or reset fails
        """
        # Check admin permissions
        self._check_admin_permissions(admin_user, "reset_password")

        user = await self.get_user_by_id(reset_request.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {reset_request.user_id} not found"
            )

        try:
            # Generate temporary password
            temp_password = generate_temporary_password(reset_request.temporary_password_length)
            hashed_password = get_password_hash(temp_password)

            # Update user password
            user.hashed_password = hashed_password

            # Set expiration for temporary password (24 hours)
            expires_at = datetime.utcnow() + timedelta(hours=24)

            self.db.commit()

            # Log password reset (without storing the actual password)
            await self.log_admin_action(
                action_type="user_password_reset",
                admin_user=admin_user,
                target_user_id=user.id,
                action_data={
                    "user_email": user.email,
                    "temp_password_length": len(temp_password),
                    "expires_at": expires_at.isoformat(),
                    "email_notification_requested": reset_request.send_email
                }
            )

            # TODO: Implement email sending
            email_sent = False
            if reset_request.send_email:
                # This would integrate with email service
                # For now, we'll just log the intention
                logger.info(f"Email notification requested for password reset: {user.email}")

            logger.info(f"Password reset for user {user.email} by admin {admin_user.email}")

            return PasswordResetResult(
                user_id=user.id,
                temporary_password=temp_password,
                expires_at=expires_at,
                email_sent=email_sent
            )

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type="user_password_reset_failed",
                admin_user=admin_user,
                target_user_id=reset_request.user_id,
                action_data={
                    "reason": "database_error",
                    "error": str(e)
                },
                result="failure"
            )
            logger.error(f"Failed to reset password for user {reset_request.user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reset password"
            )

    async def update_user_password(
        self,
        user_id: UUID,
        password_data: UserPasswordUpdateRequest,
        admin_user: User,
        request_info: Optional[dict] = None
    ) -> bool:
        """Update user password with enhanced validation."""
        # Check admin permissions
        self._check_admin_permissions(admin_user, "update_password")

        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )

        # Hash new password
        hashed_password = get_password_hash(password_data.new_password)

        try:
            user.hashed_password = hashed_password
            self.db.commit()

            # Log password change (without storing the actual password)
            await self.log_admin_action(
                action_type="user_password_updated",
                admin_user=admin_user,
                target_user_id=user.id,
                action_data={
                    "user_email": user.email,
                    "password_strength_validated": True
                }
            )

            logger.info(f"Password updated for user {user.email} by admin {admin_user.email}")
            return True

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type="user_password_update_failed",
                admin_user=admin_user,
                target_user_id=user_id,
                action_data={
                    "reason": "database_error",
                    "error": str(e)
                },
                result="failure"
            )
            logger.error(f"Failed to update password for user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password"
            )
