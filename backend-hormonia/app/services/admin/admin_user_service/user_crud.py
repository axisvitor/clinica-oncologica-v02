"""
Core CRUD operations for user administration.

Handles basic user creation, updates, activation, and deactivation.
"""

import logging
from typing import Optional
from uuid import UUID
from sqlalchemy import and_
from fastapi import HTTPException, status

from app.models.user import User, UserRole
from app.utils.security import get_password_hash
from .schemas import UserCreateRequest, UserUpdateRequest, EmailValidationRequest
from .validators import validate_email_advanced

logger = logging.getLogger(__name__)


class UserCRUDMixin:
    """Mixin for basic user CRUD operations."""

    async def create_user(
        self,
        user_data: UserCreateRequest,
        admin_user: User,
        request_info: Optional[dict] = None,
    ) -> User:
        """
        Create a new user with enhanced validation and audit logging.

        Args:
            user_data: User creation data
            admin_user: Admin user creating the user
            request_info: Request information for audit

        Returns:
            Created user

        Raises:
            HTTPException: If email already exists or validation fails
        """
        # Check admin permissions
        self._check_admin_permissions(admin_user, "create_user")

        # Validate email format and check for issues
        email_validation = await validate_email_advanced(
            EmailValidationRequest(email=user_data.email)
        )
        if not email_validation.is_valid:
            await self.log_admin_action(
                action_type="user_creation_failed",
                admin_user=admin_user,
                action_data={
                    "reason": "invalid_email",
                    "email": user_data.email,
                    "email_issues": email_validation.issues,
                },
                result="failure",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid email: {'; '.join(email_validation.issues)}",
            )

        # Check if email already exists
        existing_user = (
            self.db.query(User)
            .filter(User.email == email_validation.normalized_email)
            .first()
        )
        if existing_user:
            await self.log_admin_action(
                action_type="user_creation_failed",
                admin_user=admin_user,
                action_data={
                    "reason": "email_already_exists",
                    "email": email_validation.normalized_email,
                },
                result="failure",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with email {email_validation.normalized_email} already exists",
            )

        # Hash password
        hashed_password = get_password_hash(user_data.password)

        # Create user with normalized email
        new_user = User(
            email=email_validation.normalized_email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            role=user_data.role,
            is_active=user_data.is_active,
        )

        try:
            self.db.add(new_user)
            self.db.commit()
            self.db.refresh(new_user)

            # Log successful creation
            await self.log_admin_action(
                action_type="user_created",
                admin_user=admin_user,
                target_user_id=new_user.id,
                action_data={
                    "user_email": new_user.email,
                    "user_role": new_user.role.value,
                    "is_active": new_user.is_active,
                    "email_normalized": email_validation.normalized_email
                    != user_data.email,
                },
            )

            logger.info(
                f"User created successfully: {new_user.email} by admin {admin_user.email}"
            )
            return new_user

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type="user_creation_failed",
                admin_user=admin_user,
                action_data={
                    "reason": "database_error",
                    "error": str(e),
                    "email": email_validation.normalized_email,
                },
                result="failure",
            )
            logger.error(
                f"Failed to create user {email_validation.normalized_email}: {e}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user",
            )

    async def update_user(
        self,
        user_id: UUID,
        user_data: UserUpdateRequest,
        admin_user: User,
        request_info: Optional[dict] = None,
    ) -> User:
        """Update user information with enhanced validation."""
        # Check admin permissions
        self._check_admin_permissions(admin_user, "update_user")

        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found",
            )

        # Check if new email already exists (if email is being updated)
        if user_data.email and user_data.email != user.email:
            # Validate the new email
            email_validation = await validate_email_advanced(
                EmailValidationRequest(email=user_data.email)
            )
            if not email_validation.is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid email: {'; '.join(email_validation.issues)}",
                )

            existing_user = (
                self.db.query(User)
                .filter(
                    and_(
                        User.email == email_validation.normalized_email,
                        User.id != user_id,
                    )
                )
                .first()
            )
            if existing_user:
                await self.log_admin_action(
                    action_type="user_update_failed",
                    admin_user=admin_user,
                    target_user_id=user_id,
                    action_data={
                        "reason": "email_already_exists",
                        "new_email": email_validation.normalized_email,
                    },
                    result="failure",
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email {email_validation.normalized_email} is already in use",
                )

        # Store original values for audit
        original_values = {
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_active": user.is_active,
        }

        # Update fields
        if user_data.email is not None:
            email_validation = await validate_email_advanced(
                EmailValidationRequest(email=user_data.email)
            )
            user.email = email_validation.normalized_email
        if user_data.full_name is not None:
            user.full_name = user_data.full_name
        if user_data.role is not None:
            user.role = user_data.role
        if user_data.is_active is not None:
            user.is_active = user_data.is_active

        try:
            self.db.commit()
            self.db.refresh(user)

            # Log successful update
            await self.log_admin_action(
                action_type="user_updated",
                admin_user=admin_user,
                target_user_id=user.id,
                action_data={
                    "original_values": original_values,
                    "new_values": {
                        "email": user.email,
                        "full_name": user.full_name,
                        "role": user.role.value,
                        "is_active": user.is_active,
                    },
                },
            )

            logger.info(
                f"User {user.email} updated successfully by admin {admin_user.email}"
            )
            return user

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type="user_update_failed",
                admin_user=admin_user,
                target_user_id=user_id,
                action_data={"reason": "database_error", "error": str(e)},
                result="failure",
            )
            logger.error(f"Failed to update user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user",
            )

    async def activate_user(
        self, user_id: UUID, admin_user: User, request_info: Optional[dict] = None
    ) -> User:
        """Activate a user with permission checks."""
        # Check admin permissions
        self._check_admin_permissions(admin_user, "activate_user")

        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found",
            )

        try:
            user.is_active = True
            self.db.commit()
            self.db.refresh(user)

            # Log user activation
            await self.log_admin_action(
                action_type="user_activated",
                admin_user=admin_user,
                target_user_id=user.id,
                action_data={"user_email": user.email, "user_role": user.role.value},
            )

            logger.info(f"User {user.email} activated by admin {admin_user.email}")
            return user

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type="user_activation_failed",
                admin_user=admin_user,
                target_user_id=user_id,
                action_data={"reason": "database_error", "error": str(e)},
                result="failure",
            )
            logger.error(f"Failed to activate user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to activate user",
            )

    async def deactivate_user(
        self, user_id: UUID, admin_user: User, request_info: Optional[dict] = None
    ) -> User:
        """Deactivate a user with permission checks."""
        # Check admin permissions
        self._check_admin_permissions(admin_user, "deactivate_user")

        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found",
            )

        # Prevent deactivation of the last admin
        if user.role == UserRole.ADMIN:
            admin_count = (
                self.db.query(User)
                .filter(
                    and_(
                        User.role == UserRole.ADMIN, User.is_active, User.id != user_id
                    )
                )
                .count()
            )
            if admin_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot deactivate the last active admin user",
                )

        try:
            user.is_active = False
            self.db.commit()
            self.db.refresh(user)

            # Log user deactivation
            await self.log_admin_action(
                action_type="user_deactivated",
                admin_user=admin_user,
                target_user_id=user.id,
                action_data={"user_email": user.email, "user_role": user.role.value},
            )

            logger.info(f"User {user.email} deactivated by admin {admin_user.email}")
            return user

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type="user_deactivation_failed",
                admin_user=admin_user,
                target_user_id=user_id,
                action_data={"reason": "database_error", "error": str(e)},
                result="failure",
            )
            logger.error(f"Failed to deactivate user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to deactivate user",
            )

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User if found, None otherwise
        """
        return self.db.query(User).filter(User.id == user_id).first()
