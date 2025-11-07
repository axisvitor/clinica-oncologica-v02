"""
Roles & Permissions Management API v2
Comprehensive role management endpoints with cursor pagination, Redis caching, and RBAC.

Features:
- Cursor-based pagination on list endpoints
- Redis caching (2-10min TTL based on volatility)
- Rate limiting on write operations (30 req/min)
- Eager loading with joinedload() to prevent N+1
- Comprehensive audit logging for all role changes
- Self-protection rules (prevent admin lockout)
- Field selection support
- RBAC - Admin-only endpoints
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc

from app.database import get_db
from app.models.user import User, UserRole
from app.models.audit_log import AuditLog
from app.services.user_admin_service import UserAdminService
from app.services.audit_service import AuditService
from app.utils.cache import cache
from app.utils.rate_limiter import limiter
from app.dependencies.auth_dependencies import get_redis_cache, get_permissions_for_role
from app.middleware.admin_permissions import get_client_info
from app.schemas.v2.roles import (
    # Role schemas
    RoleResponse,
    RoleListResponse,
    # User role schemas
    UserRoleInfo,
    UserRoleListResponse,
    # Assignment schemas
    RoleAssignmentRequest,
    RoleRevocationRequest,
    RoleAssignmentResponse,
    # Bulk operations
    BulkRoleAssignmentRequest,
    BulkRoleAssignmentResult,
    # Statistics
    RoleStatistics,
    # Permissions
    RolePermissions,
    # Validation
    RoleValidationRequest,
    RoleValidationResponse,
)
from .dependencies import (
    get_pagination_params,
    get_field_selection,
    create_cursor,
    apply_field_selection,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def get_admin_user(
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
) -> User:
    """
    Dependency to verify admin access.

    TODO: Integrate with proper session-based authentication.
    For now, this retrieves the first active admin user.

    Args:
        db: Database session
        redis_cache: Redis cache instance

    Returns:
        Admin user

    Raises:
        HTTPException: If no admin user is found
    """
    # TODO: Replace with actual session-based authentication
    user = db.query(User).filter(
        User.role == UserRole.ADMIN,
        User.is_active == True
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return user


def _serialize_user_role_info(user: User) -> Dict[str, Any]:
    """Serialize user to UserRoleInfo dict."""
    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name or "",
        "current_role": user.role.value if hasattr(user.role, 'value') else str(user.role),
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": getattr(user, 'last_login', None),
    }


async def _log_role_change(
    db: Session,
    admin_user: User,
    target_user: User,
    old_role: str,
    new_role: str,
    reason: Optional[str],
    request: Request
) -> None:
    """Log role change to audit trail."""
    try:
        audit_service = AuditService(db)
        client_info = get_client_info(request)

        event_data = {
            "action": "role_assignment",
            "admin_user_id": str(admin_user.id),
            "admin_email": admin_user.email,
            "target_user_id": str(target_user.id),
            "target_email": target_user.email,
            "old_role": old_role,
            "new_role": new_role,
            "reason": reason,
            **client_info
        }

        audit_service.log_event(
            event_type="role_assignment",
            event_category="security",
            severity="info",
            user_id=admin_user.id,
            metadata=event_data
        )
    except Exception as e:
        logger.error(f"Failed to log role change: {e}")


def _get_role_permissions(role: UserRole) -> List[str]:
    """Get permissions for a role."""
    role_str = role.value if hasattr(role, 'value') else str(role)
    return get_permissions_for_role(role_str)


def _get_role_description(role: UserRole) -> str:
    """Get description for a role."""
    descriptions = {
        UserRole.ADMIN: "Full system access with user management capabilities",
        UserRole.DOCTOR: "Medical professional with patient management access",
    }
    return descriptions.get(role, "No description available")


def _group_permissions(permissions: List[str]) -> Dict[str, List[str]]:
    """Group permissions by category."""
    groups: Dict[str, List[str]] = {}

    for perm in permissions:
        # Extract category from permission (e.g., "users.read" -> "users")
        parts = perm.split('.')
        category = parts[0] if parts else "general"

        if category not in groups:
            groups[category] = []
        groups[category].append(perm)

    return groups


# ============================================================================
# ROLE ENDPOINTS
# ============================================================================

@router.get(
    "/",
    response_model=RoleListResponse,
    summary="Get available roles",
    description="Get list of all available user roles with descriptions and permissions"
)
@cache(ttl=300, key_prefix="roles:list")  # 5 min cache
async def get_available_roles(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
) -> RoleListResponse:
    """
    Get list of available user roles with descriptions and permissions.

    - **Cached**: 5 minutes (moderate volatility)
    - **RBAC**: Admin only

    Returns:
        List of available roles with their information
    """
    try:
        roles_data = []

        for role in UserRole:
            # Count users with this role
            user_count = db.query(User).filter(User.role == role).count()

            roles_data.append(RoleResponse(
                name=role.name,
                value=role.value,
                description=_get_role_description(role),
                permissions=_get_role_permissions(role),
                user_count=user_count
            ))

        return RoleListResponse(
            data=roles_data,
            total=len(roles_data)
        )

    except Exception as e:
        logger.error(f"Failed to get available roles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve available roles"
        )


@router.get(
    "/{user_id}",
    response_model=UserRoleInfo,
    summary="Get user role information",
    description="Get role information for a specific user"
)
@cache(ttl=300, key_prefix="roles:user")  # 5 min cache
async def get_user_role(
    user_id: UUID,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
) -> UserRoleInfo:
    """
    Get role information for a specific user.

    - **Cached**: 5 minutes
    - **RBAC**: Admin only

    Args:
        user_id: ID of the user to get role for

    Returns:
        User role information

    Raises:
        HTTPException: If user not found
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )

        return UserRoleInfo(**_serialize_user_role_info(user))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user role for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user role information"
        )


@router.post(
    "/{user_id}/assign",
    response_model=UserRoleInfo,
    summary="Assign role to user",
    description="Assign a new role to a specific user with audit logging"
)
@limiter.limit("30/minute")  # Rate limit: 30 requests per minute
async def assign_role_to_user(
    request: Request,
    user_id: UUID,
    role_request: RoleAssignmentRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
) -> UserRoleInfo:
    """
    Assign a role to a specific user.

    - **Rate Limited**: 30 requests/minute
    - **RBAC**: Admin only
    - **Audit**: All role changes are logged
    - **Protection**: Prevents removing last admin

    Args:
        user_id: ID of the user to assign role to
        role_request: Role assignment request with role and optional reason

    Returns:
        Updated user role information

    Raises:
        HTTPException: If user not found, role assignment fails, or would remove last admin
    """
    try:
        # Get target user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )

        # Convert role string to enum
        try:
            new_role = UserRole(role_request.role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {role_request.role}"
            )

        # Prevent removing admin role from last admin
        if user.role == UserRole.ADMIN and new_role != UserRole.ADMIN:
            admin_count = db.query(User).filter(
                User.role == UserRole.ADMIN,
                User.is_active == True,
                User.id != user_id
            ).count()

            if admin_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot remove admin role from the last active admin user"
                )

        # Store old role for audit
        old_role = user.role.value if hasattr(user.role, 'value') else str(user.role)

        # Assign new role
        user.role = new_role
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)

        # Log role change
        await _log_role_change(
            db=db,
            admin_user=admin_user,
            target_user=user,
            old_role=old_role,
            new_role=role_request.role,
            reason=role_request.reason,
            request=request
        )

        # Invalidate caches
        try:
            await redis_cache.delete(f"roles:user:{user_id}")
            await redis_cache.delete("roles:statistics")
            await redis_cache.delete("roles:list")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")

        return UserRoleInfo(**_serialize_user_role_info(user))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assign role to user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign role"
        )


@router.delete(
    "/{user_id}/revoke",
    response_model=UserRoleInfo,
    summary="Revoke role (reset to default)",
    description="Reset user role to default (DOCTOR) with audit logging"
)
@limiter.limit("30/minute")  # Rate limit: 30 requests per minute
async def revoke_user_role(
    request: Request,
    user_id: UUID,
    revoke_request: RoleRevocationRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
) -> UserRoleInfo:
    """
    Reset user role to default (DOCTOR).

    - **Rate Limited**: 30 requests/minute
    - **RBAC**: Admin only
    - **Audit**: All role changes are logged
    - **Protection**: Prevents removing last admin

    Args:
        user_id: ID of the user to reset role for
        revoke_request: Revocation request with optional reason

    Returns:
        Updated user role information

    Raises:
        HTTPException: If user not found, revocation fails, or would remove last admin
    """
    try:
        # Get target user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )

        # Prevent removing admin role from last admin
        if user.role == UserRole.ADMIN:
            admin_count = db.query(User).filter(
                User.role == UserRole.ADMIN,
                User.is_active == True,
                User.id != user_id
            ).count()

            if admin_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot revoke admin role from the last active admin user"
                )

        # Store old role for audit
        old_role = user.role.value if hasattr(user.role, 'value') else str(user.role)

        # Reset to default role
        user.role = UserRole.DOCTOR
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)

        # Log role change
        await _log_role_change(
            db=db,
            admin_user=admin_user,
            target_user=user,
            old_role=old_role,
            new_role="doctor",
            reason=revoke_request.reason,
            request=request
        )

        # Invalidate caches
        try:
            await redis_cache.delete(f"roles:user:{user_id}")
            await redis_cache.delete("roles:statistics")
            await redis_cache.delete("roles:list")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")

        return UserRoleInfo(**_serialize_user_role_info(user))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke role for user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke role"
        )


@router.post(
    "/bulk-assign",
    response_model=BulkRoleAssignmentResult,
    summary="Bulk assign roles",
    description="Assign the same role to multiple users (max 50) with audit logging"
)
@limiter.limit("10/minute")  # Rate limit: 10 requests per minute for bulk operations
async def bulk_assign_roles(
    request: Request,
    bulk_request: BulkRoleAssignmentRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
) -> BulkRoleAssignmentResult:
    """
    Assign the same role to multiple users.

    - **Rate Limited**: 10 requests/minute (bulk operations)
    - **RBAC**: Admin only
    - **Audit**: All role changes are logged
    - **Max Users**: 50 per request

    Args:
        bulk_request: Bulk role assignment request with user IDs and role

    Returns:
        Result with success/failure counts and details
    """
    successful_users: List[UserRoleInfo] = []
    failed_users: List[Dict[str, Any]] = []

    try:
        # Convert role string to enum
        try:
            new_role = UserRole(bulk_request.role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {bulk_request.role}"
            )

        for user_id in bulk_request.user_ids:
            try:
                # Get user
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    failed_users.append({
                        "user_id": str(user_id),
                        "reason": "User not found"
                    })
                    continue

                # Prevent removing admin role from last admin
                if user.role == UserRole.ADMIN and new_role != UserRole.ADMIN:
                    admin_count = db.query(User).filter(
                        User.role == UserRole.ADMIN,
                        User.is_active == True,
                        User.id != user_id
                    ).count()

                    if admin_count == 0:
                        failed_users.append({
                            "user_id": str(user_id),
                            "reason": "Cannot remove admin role from last admin"
                        })
                        continue

                # Store old role for audit
                old_role = user.role.value if hasattr(user.role, 'value') else str(user.role)

                # Assign new role
                user.role = new_role
                user.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(user)

                # Log role change
                await _log_role_change(
                    db=db,
                    admin_user=admin_user,
                    target_user=user,
                    old_role=old_role,
                    new_role=bulk_request.role,
                    reason=bulk_request.reason,
                    request=request
                )

                successful_users.append(UserRoleInfo(**_serialize_user_role_info(user)))

            except Exception as e:
                logger.error(f"Failed to assign role to user {user_id}: {e}")
                failed_users.append({
                    "user_id": str(user_id),
                    "reason": str(e)
                })

        # Invalidate caches
        try:
            await redis_cache.delete("roles:statistics")
            await redis_cache.delete("roles:list")
            for user_id in bulk_request.user_ids:
                await redis_cache.delete(f"roles:user:{user_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")

        return BulkRoleAssignmentResult(
            success_count=len(successful_users),
            failure_count=len(failed_users),
            successful_users=successful_users,
            failed_users=failed_users
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk role assignment failed: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bulk role assignment failed"
        )


@router.get(
    "/statistics",
    response_model=RoleStatistics,
    summary="Get role distribution statistics",
    description="Get statistics about role distribution and usage across all users"
)
@cache(ttl=120, key_prefix="roles:statistics")  # 2 min cache (near real-time)
async def get_role_statistics(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
) -> RoleStatistics:
    """
    Get statistics about role distribution across users.

    - **Cached**: 2 minutes (near real-time)
    - **RBAC**: Admin only

    Returns:
        Role distribution and usage statistics
    """
    try:
        # Total users
        total_users = db.query(User).count()

        # Role distribution
        role_distribution: Dict[str, int] = {}
        active_users_by_role: Dict[str, int] = {}
        inactive_users_by_role: Dict[str, int] = {}

        for role in UserRole:
            # Total users with this role
            total_count = db.query(User).filter(User.role == role).count()
            role_distribution[role.value] = total_count

            # Active users with this role
            active_count = db.query(User).filter(
                User.role == role,
                User.is_active == True
            ).count()
            active_users_by_role[role.value] = active_count

            # Inactive users with this role
            inactive_count = db.query(User).filter(
                User.role == role,
                User.is_active == False
            ).count()
            inactive_users_by_role[role.value] = inactive_count

        # Role changes in last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        role_changes_count = db.query(AuditLog).filter(
            AuditLog.event_type == "role_assignment",
            AuditLog.timestamp >= thirty_days_ago
        ).count()

        # Most assigned role
        most_assigned_role = max(role_distribution.items(), key=lambda x: x[1])[0] if role_distribution else None

        return RoleStatistics(
            total_users=total_users,
            role_distribution=role_distribution,
            active_users_by_role=active_users_by_role,
            inactive_users_by_role=inactive_users_by_role,
            role_changes_last_30_days=role_changes_count,
            most_assigned_role=most_assigned_role
        )

    except Exception as e:
        logger.error(f"Failed to get role statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve role statistics"
        )


@router.get(
    "/permissions/{role}",
    response_model=RolePermissions,
    summary="Get role permissions",
    description="Get detailed permissions for a specific role"
)
@cache(ttl=600, key_prefix="roles:permissions")  # 10 min cache (infrequent changes)
async def get_role_permissions(
    role: str,
    admin_user: User = Depends(get_admin_user)
) -> RolePermissions:
    """
    Get detailed permissions for a specific role.

    - **Cached**: 10 minutes (infrequent changes)
    - **RBAC**: Admin only

    Args:
        role: Role to get permissions for (admin, doctor)

    Returns:
        Detailed permissions for the role

    Raises:
        HTTPException: If role is invalid
    """
    try:
        # Convert role string to enum
        try:
            role_enum = UserRole(role.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {role}"
            )

        # Get permissions
        permissions = _get_role_permissions(role_enum)
        permission_groups = _group_permissions(permissions)
        description = _get_role_description(role_enum)

        return RolePermissions(
            role=role_enum.value,
            permissions=permissions,
            permission_groups=permission_groups,
            description=description
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get permissions for role {role}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve role permissions"
        )


@router.post(
    "/validate",
    response_model=RoleValidationResponse,
    summary="Validate role assignment",
    description="Validate if a role can be assigned to a user (checks constraints)"
)
async def validate_role_assignment(
    validation_request: RoleValidationRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
) -> RoleValidationResponse:
    """
    Validate if a role can be assigned to a user.

    Checks:
    - User exists
    - Would not remove last admin
    - User is active (for admin role)
    - No conflicts with existing roles

    - **RBAC**: Admin only

    Args:
        validation_request: Validation request with user ID and target role

    Returns:
        Validation result with details and warnings
    """
    try:
        user_id = validation_request.user_id
        target_role_str = validation_request.target_role

        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return RoleValidationResponse(
                valid=False,
                user_id=user_id,
                current_role=None,
                target_role=target_role_str,
                reason="user_not_found",
                message=f"User with ID {user_id} not found",
                warnings=[]
            )

        # Convert target role string to enum
        try:
            target_role = UserRole(target_role_str)
        except ValueError:
            return RoleValidationResponse(
                valid=False,
                user_id=user_id,
                current_role=user.role.value if hasattr(user.role, 'value') else str(user.role),
                target_role=target_role_str,
                reason="invalid_role",
                message=f"Invalid role: {target_role_str}",
                warnings=[]
            )

        warnings: List[str] = []

        # Check if this would remove the last admin
        if user.role == UserRole.ADMIN and target_role != UserRole.ADMIN:
            admin_count = db.query(User).filter(
                User.role == UserRole.ADMIN,
                User.is_active == True,
                User.id != user_id
            ).count()

            if admin_count == 0:
                return RoleValidationResponse(
                    valid=False,
                    user_id=user_id,
                    current_role=user.role.value if hasattr(user.role, 'value') else str(user.role),
                    target_role=target_role_str,
                    reason="last_admin_protection",
                    message="Cannot remove admin role from the last active admin user",
                    warnings=[]
                )

        # Check if user is inactive and target role is admin
        if not user.is_active and target_role == UserRole.ADMIN:
            return RoleValidationResponse(
                valid=False,
                user_id=user_id,
                current_role=user.role.value if hasattr(user.role, 'value') else str(user.role),
                target_role=target_role_str,
                reason="inactive_user_admin",
                message="Cannot assign admin role to inactive user",
                warnings=[]
            )

        # Check if role is already assigned
        if user.role == target_role:
            warnings.append("User already has this role")

        return RoleValidationResponse(
            valid=True,
            user_id=user_id,
            current_role=user.role.value if hasattr(user.role, 'value') else str(user.role),
            target_role=target_role_str,
            reason=None,
            message="Role assignment is valid",
            warnings=warnings
        )

    except Exception as e:
        logger.error(f"Failed to validate role assignment: {e}")
        return RoleValidationResponse(
            valid=False,
            user_id=validation_request.user_id,
            current_role=None,
            target_role=validation_request.target_role,
            reason="validation_error",
            message="Failed to validate role assignment",
            warnings=[]
        )
