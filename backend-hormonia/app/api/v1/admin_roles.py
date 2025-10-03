"""
Admin Role Management API endpoints.

Provides endpoints for managing user roles including:
- Role assignment and removal
- Role-based access control
- Role validation
- Bulk role operations
"""
import logging
from typing import List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User, UserRole
from app.services.user_admin_service import UserAdminService
from app.middleware.admin_permissions import (
    require_admin, get_admin_user, get_client_info
)

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic models for role management
class RoleAssignmentRequest(BaseModel):
    """Request model for role assignment."""
    role: UserRole

    class Config:
        use_enum_values = True


class BulkRoleAssignmentRequest(BaseModel):
    """Request model for bulk role assignment."""
    user_ids: List[UUID]
    role: UserRole

    class Config:
        use_enum_values = True


class RoleInfo(BaseModel):
    """Information about a role."""
    name: str
    value: str
    description: str
    permissions: List[str]


class UserRoleInfo(BaseModel):
    """User role information."""
    user_id: UUID
    email: str
    full_name: str
    current_role: UserRole
    is_active: bool

    class Config:
        from_attributes = True
        use_enum_values = True


class RoleStatistics(BaseModel):
    """Role distribution statistics."""
    total_users: int
    role_distribution: Dict[str, int]
    active_users_by_role: Dict[str, int]
    inactive_users_by_role: Dict[str, int]


@router.get("/roles", response_model=List[RoleInfo], summary="Get available roles")
async def get_available_roles(
    admin_user: User = Depends(require_admin)
) -> List[RoleInfo]:
    """
    Get list of available user roles with descriptions.

    Returns:
        List of available roles with their information
    """
    # Define role descriptions and permissions
    role_info_map = {
        UserRole.ADMIN: {
            "description": "Full system access with user management capabilities",
            "permissions": [
                "user_management", "role_assignment", "system_configuration",
                "audit_log_access", "patient_management", "report_generation"
            ]
        },
        UserRole.DOCTOR: {
            "description": "Medical professional with patient management access",
            "permissions": [
                "patient_management", "medical_records", "report_generation",
                "quiz_management", "ai_insights"
            ]
        }
    }

    roles = []
    for role in UserRole:
        info = role_info_map.get(role, {"description": "No description", "permissions": []})
        roles.append(RoleInfo(
            name=role.name,
            value=role.value,
            description=info["description"],
            permissions=info["permissions"]
        ))

    return roles


@router.post("/users/{user_id}/role", response_model=UserRoleInfo, summary="Assign role to user")
async def assign_role_to_user(
    user_id: UUID,
    role_request: RoleAssignmentRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> UserRoleInfo:
    """
    Assign a role to a specific user.

    Args:
        user_id: ID of the user to assign role to
        role_request: Role assignment request
        request: HTTP request for audit logging
        admin_user: Admin user performing the assignment
        db: Database session

    Returns:
        Updated user role information

    Raises:
        HTTPException: If user not found or role assignment fails
    """
    user_service = UserAdminService(db)
    client_info = get_client_info(request)

    try:
        updated_user = await user_service.assign_role(
            user_id=user_id,
            new_role=role_request.role,
            admin_user=admin_user,
            request_info=client_info
        )

        return UserRoleInfo(
            user_id=updated_user.id,
            email=updated_user.email,
            full_name=updated_user.full_name or "",
            current_role=updated_user.role,
            is_active=updated_user.is_active
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assign role {role_request.role} to user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign role"
        )


@router.delete("/users/{user_id}/role", response_model=UserRoleInfo, summary="Reset user role to default")
async def reset_user_role(
    user_id: UUID,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> UserRoleInfo:
    """
    Reset user role to default (DOCTOR).

    Args:
        user_id: ID of the user to reset role for
        request: HTTP request for audit logging
        admin_user: Admin user performing the reset
        db: Database session

    Returns:
        Updated user role information

    Raises:
        HTTPException: If user not found or role reset fails
    """
    user_service = UserAdminService(db)
    client_info = get_client_info(request)

    try:
        updated_user = await user_service.assign_role(
            user_id=user_id,
            new_role=UserRole.DOCTOR,  # Default role
            admin_user=admin_user,
            request_info=client_info
        )

        return UserRoleInfo(
            user_id=updated_user.id,
            email=updated_user.email,
            full_name=updated_user.full_name or "",
            current_role=updated_user.role,
            is_active=updated_user.is_active
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset role for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset role"
        )


@router.get("/users/{user_id}/role", response_model=UserRoleInfo, summary="Get user role information")
async def get_user_role(
    user_id: UUID,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> UserRoleInfo:
    """
    Get role information for a specific user.

    Args:
        user_id: ID of the user to get role for
        admin_user: Admin user requesting the information
        db: Database session

    Returns:
        User role information

    Raises:
        HTTPException: If user not found
    """
    user_service = UserAdminService(db)

    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )

    return UserRoleInfo(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name or "",
        current_role=user.role,
        is_active=user.is_active
    )


@router.post("/roles/bulk-assign", response_model=List[UserRoleInfo], summary="Bulk assign roles")
async def bulk_assign_roles(
    bulk_request: BulkRoleAssignmentRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> List[UserRoleInfo]:
    """
    Assign the same role to multiple users.

    Args:
        bulk_request: Bulk role assignment request
        request: HTTP request for audit logging
        admin_user: Admin user performing the bulk assignment
        db: Database session

    Returns:
        List of updated user role information

    Raises:
        HTTPException: If any user not found or assignment fails
    """
    user_service = UserAdminService(db)
    client_info = get_client_info(request)

    updated_users = []
    failed_users = []

    for user_id in bulk_request.user_ids:
        try:
            updated_user = await user_service.assign_role(
                user_id=user_id,
                new_role=bulk_request.role,
                admin_user=admin_user,
                request_info=client_info
            )

            updated_users.append(UserRoleInfo(
                user_id=updated_user.id,
                email=updated_user.email,
                full_name=updated_user.full_name or "",
                current_role=updated_user.role,
                is_active=updated_user.is_active
            ))

        except Exception as e:
            failed_users.append({"user_id": str(user_id), "error": str(e)})
            logger.error(f"Failed to assign role {bulk_request.role} to user {user_id}: {e}")

    # If some assignments failed, log the details but return successful ones
    if failed_users:
        logger.warning(f"Bulk role assignment partially failed. Failed users: {failed_users}")
        # You might want to return this information in the response
        # For now, we'll continue with successful assignments

    if not updated_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No roles were successfully assigned"
        )

    return updated_users


@router.get("/roles/statistics", response_model=RoleStatistics, summary="Get role distribution statistics")
async def get_role_statistics(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> RoleStatistics:
    """
    Get statistics about role distribution across users.

    Args:
        admin_user: Admin user requesting the statistics
        db: Database session

    Returns:
        Role distribution statistics
    """
    user_service = UserAdminService(db)

    try:
        # Get overall user statistics
        stats = await user_service.get_user_statistics()

        # Calculate active/inactive breakdown by role
        active_users_by_role = {}
        inactive_users_by_role = {}

        for role in UserRole:
            # Count active users for this role
            active_count = db.query(User).filter(
                User.role == role,
                User.is_active == True
            ).count()

            # Count inactive users for this role
            inactive_count = db.query(User).filter(
                User.role == role,
                User.is_active == False
            ).count()

            active_users_by_role[role.value] = active_count
            inactive_users_by_role[role.value] = inactive_count

        return RoleStatistics(
            total_users=stats.total_users,
            role_distribution=stats.users_by_role,
            active_users_by_role=active_users_by_role,
            inactive_users_by_role=inactive_users_by_role
        )

    except Exception as e:
        logger.error(f"Failed to get role statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get role statistics"
        )


@router.get("/roles/{role}/users", response_model=List[UserRoleInfo], summary="Get users by role")
async def get_users_by_role(
    role: UserRole,
    include_inactive: bool = False,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> List[UserRoleInfo]:
    """
    Get all users with a specific role.

    Args:
        role: Role to filter by
        include_inactive: Whether to include inactive users
        admin_user: Admin user requesting the information
        db: Database session

    Returns:
        List of users with the specified role
    """
    try:
        query = db.query(User).filter(User.role == role)

        if not include_inactive:
            query = query.filter(User.is_active == True)

        users = query.order_by(User.created_at.desc()).all()

        return [
            UserRoleInfo(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name or "",
                current_role=user.role,
                is_active=user.is_active
            )
            for user in users
        ]

    except Exception as e:
        logger.error(f"Failed to get users by role {role}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users by role"
        )


@router.post("/roles/validate", summary="Validate role assignment")
async def validate_role_assignment(
    user_id: UUID,
    target_role: UserRole,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Validate if a role can be assigned to a user.

    Args:
        user_id: ID of the user to check
        target_role: Role to validate
        admin_user: Admin user performing the validation
        db: Database session

    Returns:
        Validation result with details
    """
    user_service = UserAdminService(db)

    try:
        user = await user_service.get_user_by_id(user_id)
        if not user:
            return {
                "valid": False,
                "reason": "user_not_found",
                "message": f"User with ID {user_id} not found"
            }

        # Check if this would remove the last admin
        if user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN} and target_role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            admin_count = db.query(User).filter(
                User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]),
                User.is_active == True,
                User.id != user_id
            ).count()

            if admin_count == 0:
                return {
                    "valid": False,
                    "reason": "last_admin_protection",
                    "message": "Cannot remove admin role from the last active admin user"
                }

        # Check if user is currently inactive and target role is admin
        if not user.is_active and target_role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            return {
                "valid": False,
                "reason": "inactive_user_admin",
                "message": "Cannot assign admin role to inactive user"
            }

        return {
            "valid": True,
            "current_role": user.role.value,
            "target_role": target_role.value,
            "message": "Role assignment is valid"
        }

    except Exception as e:
        logger.error(f"Failed to validate role assignment for user {user_id}: {e}")
        return {
            "valid": False,
            "reason": "validation_error",
            "message": "Failed to validate role assignment"
        }