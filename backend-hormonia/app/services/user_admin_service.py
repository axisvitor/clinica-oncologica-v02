"""
User Administration Service.

Provides comprehensive user management functionality including:
- User CRUD operations
- Role management
- User activation/deactivation
- Batch operations
- User search and filtering
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from fastapi import HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.models.user import User, UserRole
from app.services.audit_service import AuditService
from app.utils.security import get_password_hash, verify_password
from app.middleware.admin_permissions import AdminAuditMixin

logger = logging.getLogger(__name__)


# Pydantic models for user administration
class UserCreateRequest(BaseModel):
    """Request model for creating a new user."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    full_name: Optional[str] = None
    role: UserRole = UserRole.DOCTOR
    is_active: bool = True

    class Config:
        use_enum_values = True


class UserUpdateRequest(BaseModel):
    """Request model for updating a user."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

    class Config:
        use_enum_values = True


class UserPasswordUpdateRequest(BaseModel):
    """Request model for updating user password."""
    new_password: str = Field(..., min_length=8, description="Minimum 8 characters")
    confirm_password: str


class UserSearchFilters(BaseModel):
    """Search filters for user queries."""
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None

    class Config:
        use_enum_values = True


class UserSummary(BaseModel):
    """Summary model for user data."""
    id: UUID
    email: str
    full_name: Optional[str]
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Add computed fields
    total_patients: int = 0
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True
        use_enum_values = True


class PaginatedUsersResponse(BaseModel):
    """Paginated response for user listings."""
    users: List[UserSummary]
    total: int
    page: int
    per_page: int
    total_pages: int


class UserStatistics(BaseModel):
    """User statistics for dashboard."""
    total_users: int
    active_users: int
    inactive_users: int
    users_by_role: Dict[str, int]
    recent_registrations: int
    recent_logins: int


class UserAdminService(AdminAuditMixin):
    """Service for user administration operations."""

    def __init__(self, db: Session):
        super().__init__(db)
        self.logger = logging.getLogger(__name__)

    async def create_user(
        self,
        user_data: UserCreateRequest,
        admin_user: User,
        request_info: Optional[dict] = None
    ) -> User:
        """
        Create a new user.

        Args:
            user_data: User creation data
            admin_user: Admin user creating the user
            request_info: Request information for audit

        Returns:
            Created user

        Raises:
            HTTPException: If email already exists or validation fails
        """
        # Check if email already exists
        existing_user = self.db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            await self.log_admin_action(
                action_type="user_creation_failed",
                admin_user=admin_user,
                action_data={
                    "reason": "email_already_exists",
                    "email": user_data.email
                },
                result="failure"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with email {user_data.email} already exists"
            )

        # Hash password
        hashed_password = get_password_hash(user_data.password)

        # Create user
        new_user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            role=user_data.role,
            is_active=user_data.is_active
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
                    "is_active": new_user.is_active
                }
            )

            self.logger.info(f"User created successfully: {new_user.email} by admin {admin_user.email}")
            return new_user

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type="user_creation_failed",
                admin_user=admin_user,
                action_data={
                    "reason": "database_error",
                    "error": str(e),
                    "email": user_data.email
                },
                result="failure"
            )
            self.logger.error(f"Failed to create user {user_data.email}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
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

    async def get_user_summary(self, user_id: UUID) -> Optional[UserSummary]:
        """
        Get user summary with additional computed fields.

        Args:
            user_id: User ID

        Returns:
            User summary if found, None otherwise
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            return None

        # Get patient count for doctors
        total_patients = 0
        if user.role == UserRole.DOCTOR:
            total_patients = len(user.patients) if user.patients else 0

        # TODO: Get last login from audit logs
        # For now, we'll use None as placeholder
        last_login = None

        return UserSummary(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            total_patients=total_patients,
            last_login=last_login
        )

    async def update_user(
        self,
        user_id: UUID,
        user_data: UserUpdateRequest,
        admin_user: User,
        request_info: Optional[dict] = None
    ) -> User:
        """
        Update user information.

        Args:
            user_id: ID of user to update
            user_data: Updated user data
            admin_user: Admin user performing the update
            request_info: Request information for audit

        Returns:
            Updated user

        Raises:
            HTTPException: If user not found or email already exists
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )

        # Check if new email already exists (if email is being updated)
        if user_data.email and user_data.email != user.email:
            existing_user = self.db.query(User).filter(
                and_(User.email == user_data.email, User.id != user_id)
            ).first()
            if existing_user:
                await self.log_admin_action(
                    action_type="user_update_failed",
                    admin_user=admin_user,
                    target_user_id=user_id,
                    action_data={
                        "reason": "email_already_exists",
                        "new_email": user_data.email
                    },
                    result="failure"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email {user_data.email} is already in use"
                )

        # Store original values for audit
        original_values = {
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_active": user.is_active
        }

        # Update fields
        if user_data.email is not None:
            user.email = user_data.email
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
                        "is_active": user.is_active
                    }
                }
            )

            self.logger.info(f"User {user.email} updated successfully by admin {admin_user.email}")
            return user

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type="user_update_failed",
                admin_user=admin_user,
                target_user_id=user_id,
                action_data={
                    "reason": "database_error",
                    "error": str(e)
                },
                result="failure"
            )
            self.logger.error(f"Failed to update user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user"
            )

    async def update_user_password(
        self,
        user_id: UUID,
        password_data: UserPasswordUpdateRequest,
        admin_user: User,
        request_info: Optional[dict] = None
    ) -> bool:
        """
        Update user password.

        Args:
            user_id: ID of user to update
            password_data: New password data
            admin_user: Admin user performing the update
            request_info: Request information for audit

        Returns:
            True if successful

        Raises:
            HTTPException: If user not found or passwords don't match
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )

        # Validate password confirmation
        if password_data.new_password != password_data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password and confirmation password do not match"
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
                    "user_email": user.email
                }
            )

            self.logger.info(f"Password updated for user {user.email} by admin {admin_user.email}")
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
            self.logger.error(f"Failed to update password for user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password"
            )

    async def delete_user(
        self,
        user_id: UUID,
        admin_user: User,
        request_info: Optional[dict] = None
    ) -> bool:
        """
        Soft delete a user (deactivate).

        Args:
            user_id: ID of user to delete
            admin_user: Admin user performing the deletion
            request_info: Request information for audit

        Returns:
            True if successful

        Raises:
            HTTPException: If user not found or cannot be deleted
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )

        # Prevent deletion of the last admin
        if user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            admin_count = self.db.query(User).filter(
                and_(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]), User.is_active == True, User.id != user_id)
            ).count()
            if admin_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete the last active admin user"
                )

        try:
            # Soft delete - just deactivate the user
            user.is_active = False
            self.db.commit()

            # Log user deletion
            await self.log_admin_action(
                action_type="user_deleted",
                admin_user=admin_user,
                target_user_id=user.id,
                action_data={
                    "user_email": user.email,
                    "user_role": user.role.value,
                    "deletion_type": "soft_delete"
                }
            )

            self.logger.info(f"User {user.email} soft deleted by admin {admin_user.email}")
            return True

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type="user_deletion_failed",
                admin_user=admin_user,
                target_user_id=user_id,
                action_data={
                    "reason": "database_error",
                    "error": str(e)
                },
                result="failure"
            )
            self.logger.error(f"Failed to delete user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete user"
            )

    async def activate_user(
        self,
        user_id: UUID,
        admin_user: User,
        request_info: Optional[dict] = None
    ) -> User:
        """
        Activate a user.

        Args:
            user_id: ID of user to activate
            admin_user: Admin user performing the activation
            request_info: Request information for audit

        Returns:
            Activated user

        Raises:
            HTTPException: If user not found
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
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
                action_data={
                    "user_email": user.email,
                    "user_role": user.role.value
                }
            )

            self.logger.info(f"User {user.email} activated by admin {admin_user.email}")
            return user

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type="user_activation_failed",
                admin_user=admin_user,
                target_user_id=user_id,
                action_data={
                    "reason": "database_error",
                    "error": str(e)
                },
                result="failure"
            )
            self.logger.error(f"Failed to activate user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to activate user"
            )

    async def deactivate_user(
        self,
        user_id: UUID,
        admin_user: User,
        request_info: Optional[dict] = None
    ) -> User:
        """
        Deactivate a user.

        Args:
            user_id: ID of user to deactivate
            admin_user: Admin user performing the deactivation
            request_info: Request information for audit

        Returns:
            Deactivated user

        Raises:
            HTTPException: If user not found or cannot be deactivated
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )

        # Prevent deactivation of the last admin
        if user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            admin_count = self.db.query(User).filter(
                and_(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]), User.is_active == True, User.id != user_id)
            ).count()
            if admin_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot deactivate the last active admin user"
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
                action_data={
                    "user_email": user.email,
                    "user_role": user.role.value
                }
            )

            self.logger.info(f"User {user.email} deactivated by admin {admin_user.email}")
            return user

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type="user_deactivation_failed",
                admin_user=admin_user,
                target_user_id=user_id,
                action_data={
                    "reason": "database_error",
                    "error": str(e)
                },
                result="failure"
            )
            self.logger.error(f"Failed to deactivate user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to deactivate user"
            )

    async def search_users(
        self,
        filters: UserSearchFilters,
        page: int = 1,
        per_page: int = 20
    ) -> PaginatedUsersResponse:
        """
        Search users with filters and pagination.

        Args:
            filters: Search filters
            page: Page number (1-based)
            per_page: Items per page

        Returns:
            Paginated users response
        """
        query = self.db.query(User)

        # Apply filters
        if filters.email:
            query = query.filter(User.email.ilike(f"%{filters.email}%"))
        if filters.full_name:
            query = query.filter(User.full_name.ilike(f"%{filters.full_name}%"))
        if filters.role is not None:
            query = query.filter(User.role == filters.role)
        if filters.is_active is not None:
            query = query.filter(User.is_active == filters.is_active)
        if filters.created_after:
            query = query.filter(User.created_at >= filters.created_after)
        if filters.created_before:
            query = query.filter(User.created_at <= filters.created_before)

        # Get total count
        total = query.count()

        # Apply pagination and ordering
        offset = (page - 1) * per_page
        users = query.order_by(desc(User.created_at)).offset(offset).limit(per_page).all()

        # Convert to user summaries
        user_summaries = []
        for user in users:
            summary = await self.get_user_summary(user.id)
            if summary:
                user_summaries.append(summary)

        total_pages = (total + per_page - 1) // per_page

        return PaginatedUsersResponse(
            users=user_summaries,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )

    async def get_user_statistics(self) -> UserStatistics:
        """
        Get user statistics for admin dashboard.

        Returns:
            User statistics
        """
        # Basic counts
        total_users = self.db.query(User).count()
        active_users = self.db.query(User).filter(User.is_active == True).count()
        inactive_users = total_users - active_users

        # Users by role
        users_by_role = {}
        for role in UserRole:
            count = self.db.query(User).filter(User.role == role).count()
            users_by_role[role.value] = count

        # Recent registrations (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        thirty_days_ago = thirty_days_ago.replace(hour=0, minute=0, second=0, microsecond=0)
        recent_registrations = self.db.query(User).filter(
            User.created_at >= thirty_days_ago
        ).count()

        # TODO: Get recent logins from audit logs
        # For now, we'll use 0 as placeholder
        recent_logins = 0

        return UserStatistics(
            total_users=total_users,
            active_users=active_users,
            inactive_users=inactive_users,
            users_by_role=users_by_role,
            recent_registrations=recent_registrations,
            recent_logins=recent_logins
        )

    async def assign_role(
        self,
        user_id: UUID,
        new_role: UserRole,
        admin_user: User,
        request_info: Optional[dict] = None
    ) -> User:
        """
        Assign a role to a user.

        Args:
            user_id: ID of user to update
            new_role: New role to assign
            admin_user: Admin user performing the role assignment
            request_info: Request information for audit

        Returns:
            Updated user

        Raises:
            HTTPException: If user not found or role assignment not allowed
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )

        # Store original role
        original_role = user.role

        # Check if this would remove the last admin
        if original_role in {UserRole.ADMIN, UserRole.SUPER_ADMIN} and new_role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            admin_count = self.db.query(User).filter(
                and_(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]), User.is_active == True, User.id != user_id)
            ).count()
            if admin_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot remove admin role from the last active admin user"
                )

        try:
            user.role = new_role
            self.db.commit()
            self.db.refresh(user)

            # Log role assignment
            await self.log_admin_action(
                action_type="role_assigned",
                admin_user=admin_user,
                target_user_id=user.id,
                action_data={
                    "user_email": user.email,
                    "original_role": original_role.value,
                    "new_role": new_role.value
                }
            )

            self.logger.info(f"Role {new_role.value} assigned to user {user.email} by admin {admin_user.email}")
            return user

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type="role_assignment_failed",
                admin_user=admin_user,
                target_user_id=user_id,
                action_data={
                    "reason": "database_error",
                    "error": str(e),
                    "attempted_role": new_role.value
                },
                result="failure"
            )
            self.logger.error(f"Failed to assign role to user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to assign role"
            )
