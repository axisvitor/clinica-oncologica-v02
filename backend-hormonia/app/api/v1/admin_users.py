"""
Admin Users API endpoints.

Provides comprehensive user management functionality for admin users including:
- User CRUD operations
- Role management
- User activation/deactivation
- User search and filtering
- User statistics
- Password management
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.services.user_admin_service import (
    UserAdminService,
    UserCreateRequest,
    UserUpdateRequest,
    UserPasswordUpdateRequest,
    UserSearchFilters,
    UserSummary,
    PaginatedUsersResponse,
    UserStatistics
)
from app.dependencies.auth_dependencies import get_admin_user as get_current_admin_user
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def get_user_admin_service(db: Session = Depends(get_db)) -> UserAdminService:
    """Get UserAdminService instance."""
    return UserAdminService(db)


@router.post("/", response_model=UserSummary, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreateRequest,
    admin_user: User = Depends(get_current_admin_user),
    service: UserAdminService = Depends(get_user_admin_service)
):
    """
    Create a new user.

    Only admins can create new users. The created user will have the specified role
    and can be activated or deactivated based on the is_active flag.

    Args:
        user_data: User creation data including email, password, role, etc.
        admin_user: Current authenticated admin user
        service: User admin service instance

    Returns:
        Created user summary

    Raises:
        HTTPException: If email already exists or validation fails
    """
    logger.info(f"Admin {admin_user.email} creating new user with email {user_data.email}")

    new_user = await service.create_user(user_data, admin_user)
    user_summary = await service.get_user_summary(new_user.id)

    if not user_summary:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve created user"
        )

    return user_summary


@router.get("/", response_model=PaginatedUsersResponse)
async def list_users(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    email: Optional[str] = Query(None, description="Filter by email (partial match)"),
    full_name: Optional[str] = Query(None, description="Filter by full name (partial match)"),
    role: Optional[UserRole] = Query(None, description="Filter by user role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    admin_user: User = Depends(get_current_admin_user),
    service: UserAdminService = Depends(get_user_admin_service)
):
    """
    List users with optional filtering and pagination.

    Supports filtering by email, full name, role, and active status.
    Results are paginated and ordered by creation date (newest first).

    Args:
        page: Page number (1-based)
        per_page: Number of items per page (max 100)
        email: Filter by email (partial match)
        full_name: Filter by full name (partial match)
        role: Filter by user role
        is_active: Filter by active status
        admin_user: Current authenticated admin user
        service: User admin service instance

    Returns:
        Paginated list of users with metadata
    """
    logger.info(f"Admin {admin_user.email} listing users (page {page}, per_page {per_page})")

    filters = UserSearchFilters(
        email=email,
        full_name=full_name,
        role=role,
        is_active=is_active
    )

    return await service.search_users(filters, page, per_page)


@router.get("/statistics", response_model=UserStatistics)
async def get_user_statistics(
    admin_user: User = Depends(get_current_admin_user),
    service: UserAdminService = Depends(get_user_admin_service)
):
    """
    Get user statistics for admin dashboard.

    Provides comprehensive statistics including total users, active/inactive counts,
    users by role, recent registrations, and recent logins.

    Args:
        admin_user: Current authenticated admin user
        service: User admin service instance

    Returns:
        User statistics
    """
    logger.info(f"Admin {admin_user.email} requesting user statistics")

    return await service.get_user_statistics()


@router.get("/{user_id}", response_model=UserSummary)
async def get_user(
    user_id: UUID,
    admin_user: User = Depends(get_current_admin_user),
    service: UserAdminService = Depends(get_user_admin_service)
):
    """
    Get user details by ID.

    Returns detailed user information including computed fields like
    patient count and last login time.

    Args:
        user_id: ID of the user to retrieve
        admin_user: Current authenticated admin user
        service: User admin service instance

    Returns:
        User summary with details

    Raises:
        HTTPException: If user not found
    """
    logger.info(f"Admin {admin_user.email} requesting user details for {user_id}")

    user_summary = await service.get_user_summary(user_id)
    if not user_summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )

    return user_summary


@router.put("/{user_id}", response_model=UserSummary)
async def update_user(
    user_id: UUID,
    user_data: UserUpdateRequest,
    admin_user: User = Depends(get_current_admin_user),
    service: UserAdminService = Depends(get_user_admin_service)
):
    """
    Update user information.

    Allows updating email, full name, role, and active status.
    All changes are logged for audit purposes.

    Args:
        user_id: ID of the user to update
        user_data: Updated user data
        admin_user: Current authenticated admin user
        service: User admin service instance

    Returns:
        Updated user summary

    Raises:
        HTTPException: If user not found or email already exists
    """
    logger.info(f"Admin {admin_user.email} updating user {user_id}")

    updated_user = await service.update_user(user_id, user_data, admin_user)
    user_summary = await service.get_user_summary(updated_user.id)

    if not user_summary:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve updated user"
        )

    return user_summary


@router.put("/{user_id}/password")
async def update_user_password(
    user_id: UUID,
    password_data: UserPasswordUpdateRequest,
    admin_user: User = Depends(get_current_admin_user),
    service: UserAdminService = Depends(get_user_admin_service)
):
    """
    Update user password.

    Allows admin to reset a user's password. The new password must be confirmed
    and meet minimum security requirements.

    Args:
        user_id: ID of the user to update
        password_data: New password and confirmation
        admin_user: Current authenticated admin user
        service: User admin service instance

    Returns:
        Success message

    Raises:
        HTTPException: If user not found or passwords don't match
    """
    logger.info(f"Admin {admin_user.email} updating password for user {user_id}")

    await service.update_user_password(user_id, password_data, admin_user)

    return {"message": "Password updated successfully"}


@router.post("/{user_id}/activate", response_model=UserSummary)
async def activate_user(
    user_id: UUID,
    admin_user: User = Depends(get_current_admin_user),
    service: UserAdminService = Depends(get_user_admin_service)
):
    """
    Activate a user account.

    Sets the user's is_active flag to True, allowing them to log in
    and use the system.

    Args:
        user_id: ID of the user to activate
        admin_user: Current authenticated admin user
        service: User admin service instance

    Returns:
        Activated user summary

    Raises:
        HTTPException: If user not found
    """
    logger.info(f"Admin {admin_user.email} activating user {user_id}")

    activated_user = await service.activate_user(user_id, admin_user)
    user_summary = await service.get_user_summary(activated_user.id)

    if not user_summary:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve activated user"
        )

    return user_summary


@router.post("/{user_id}/deactivate", response_model=UserSummary)
async def deactivate_user(
    user_id: UUID,
    admin_user: User = Depends(get_current_admin_user),
    service: UserAdminService = Depends(get_user_admin_service)
):
    """
    Deactivate a user account.

    Sets the user's is_active flag to False, preventing them from logging in.
    Cannot deactivate the last active admin user.

    Args:
        user_id: ID of the user to deactivate
        admin_user: Current authenticated admin user
        service: User admin service instance

    Returns:
        Deactivated user summary

    Raises:
        HTTPException: If user not found or cannot be deactivated
    """
    logger.info(f"Admin {admin_user.email} deactivating user {user_id}")

    deactivated_user = await service.deactivate_user(user_id, admin_user)
    user_summary = await service.get_user_summary(deactivated_user.id)

    if not user_summary:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve deactivated user"
        )

    return user_summary


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    admin_user: User = Depends(get_current_admin_user),
    service: UserAdminService = Depends(get_user_admin_service)
):
    """
    Delete a user account (soft delete).

    Performs a soft delete by deactivating the user. Cannot delete
    the last active admin user.

    Args:
        user_id: ID of the user to delete
        admin_user: Current authenticated admin user
        service: User admin service instance

    Returns:
        Success message

    Raises:
        HTTPException: If user not found or cannot be deleted
    """
    logger.info(f"Admin {admin_user.email} deleting user {user_id}")

    await service.delete_user(user_id, admin_user)

    return {"message": "User deleted successfully"}


@router.put("/{user_id}/role", response_model=UserSummary)
async def assign_role(
    user_id: UUID,
    new_role: UserRole,
    admin_user: User = Depends(get_current_admin_user),
    service: UserAdminService = Depends(get_user_admin_service)
):
    """
    Assign a role to a user.

    Changes the user's role. Cannot remove admin role from the last
    active admin user.

    Args:
        user_id: ID of the user to update
        new_role: New role to assign
        admin_user: Current authenticated admin user
        service: User admin service instance

    Returns:
        Updated user summary

    Raises:
        HTTPException: If user not found or role assignment not allowed
    """
    logger.info(f"Admin {admin_user.email} assigning role {new_role.value} to user {user_id}")

    updated_user = await service.assign_role(user_id, new_role, admin_user)
    user_summary = await service.get_user_summary(updated_user.id)

    if not user_summary:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve updated user"
        )

    return user_summary