"""
Admin permissions middleware for user administration endpoints.

This middleware ensures that only users with admin role can access
admin-specific endpoints and provides RBAC functionality.
"""
import logging
from typing import Optional, List, Callable
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.models.user import User, UserRole
# LAZY IMPORTS: To avoid circular import chain:
# admin_permissions -> services.audit -> services.__init__ -> admin_user_service -> admin_permissions


def _get_audit_service():
    """Lazy import of AuditService to avoid circular import."""
    from app.services.audit import AuditService
    return AuditService


def _get_current_user_dependency():
    """Lazy import of get_current_user to avoid circular import."""
    from app.dependencies.auth_dependencies import get_current_user
    return get_current_user

logger = logging.getLogger(__name__)
security = HTTPBearer()


class AdminPermissionError(HTTPException):
    """Custom exception for admin permission errors."""

    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class AdminPermissions:
    """Admin permissions checker class."""

    @staticmethod
    def require_admin() -> Callable:
        """
        Dependency that requires admin role.

        Returns:
            Dependency function that checks for admin role
        """
        async def check_admin_permission(
            current_user: User = Depends(_get_current_user_dependency()),
            db: Session = Depends(get_db),
            request: Request = None
        ) -> User:
            """Check if current user has admin role."""
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            if current_user.role != UserRole.ADMIN:
                # Log unauthorized access attempt
                AuditService = _get_audit_service()
                audit_service = AuditService(db)
                audit_service.log_event(
                    event_type="admin_access_denied",
                    event_category="security",
                    severity="warning",
                    actor_id=current_user.id,
                    ip_address=request.client.host if request and request.client else None,
                    user_agent=request.headers.get('user-agent') if request else None,
                    event_data={
                        "attempted_action": "admin_endpoint_access",
                        "user_role": current_user.role.value,
                        "endpoint": str(request.url) if request else None
                    },
                    result="blocked"
                )

                raise AdminPermissionError(
                    f"Admin role required. Current role: {current_user.role.value}"
                )

            # Log successful admin access
            AuditService = _get_audit_service()
            audit_service = AuditService(db)
            audit_service.log_event(
                event_type="admin_access_granted",
                event_category="access",
                severity="info",
                actor_id=current_user.id,
                ip_address=request.client.host if request and request.client else None,
                user_agent=request.headers.get('user-agent') if request else None,
                event_data={
                    "action": "admin_endpoint_access",
                    "endpoint": str(request.url) if request else None
                },
                result="success"
            )

            return current_user

        return check_admin_permission

    @staticmethod
    def require_admin_or_self(target_user_id: Optional[UUID] = None) -> Callable:
        """
        Dependency that requires admin role OR the user is accessing their own data.

        Args:
            target_user_id: ID of the user being accessed (optional)

        Returns:
            Dependency function that checks permissions
        """
        async def check_admin_or_self_permission(
            current_user: User = Depends(_get_current_user_dependency()),
            db: Session = Depends(get_db),
            request: Request = None
        ) -> User:
            """Check if current user has admin role or is accessing their own data."""
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            # Admin can access everything
            if current_user.role == UserRole.ADMIN:
                return current_user

            # If target_user_id is provided, check if user is accessing their own data
            if target_user_id and str(current_user.id) == str(target_user_id):
                return current_user

            # Otherwise, deny access
            AuditService = _get_audit_service()
            audit_service = AuditService(db)
            audit_service.log_event(
                event_type="unauthorized_user_access",
                event_category="security",
                severity="warning",
                actor_id=current_user.id,
                subject_id=target_user_id,
                ip_address=request.client.host if request and request.client else None,
                user_agent=request.headers.get('user-agent') if request else None,
                event_data={
                    "attempted_action": "user_data_access",
                    "user_role": current_user.role.value,
                    "target_user_id": str(target_user_id) if target_user_id else None
                },
                result="blocked"
            )

            raise AdminPermissionError(
                "Admin role required or user can only access their own data"
            )

        return check_admin_or_self_permission

    @staticmethod
    def require_role(allowed_roles: List[UserRole]) -> Callable:
        """
        Dependency that requires one of the specified roles.

        Args:
            allowed_roles: List of allowed user roles

        Returns:
            Dependency function that checks for required roles
        """
        async def check_role_permission(
            current_user: User = Depends(_get_current_user_dependency()),
            db: Session = Depends(get_db),
            request: Request = None
        ) -> User:
            """Check if current user has one of the required roles."""
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            if current_user.role not in allowed_roles:
                # Log unauthorized access attempt
                AuditService = _get_audit_service()
                audit_service = AuditService(db)
                audit_service.log_event(
                    event_type="role_access_denied",
                    event_category="security",
                    severity="warning",
                    actor_id=current_user.id,
                    ip_address=request.client.host if request and request.client else None,
                    user_agent=request.headers.get('user-agent') if request else None,
                    event_data={
                        "attempted_action": "role_restricted_access",
                        "user_role": current_user.role.value,
                        "required_roles": [role.value for role in allowed_roles],
                        "endpoint": str(request.url) if request else None
                    },
                    result="blocked"
                )

                allowed_role_names = [role.value for role in allowed_roles]
                raise AdminPermissionError(
                    f"Required roles: {allowed_role_names}. Current role: {current_user.role.value}"
                )

            return current_user

        return check_role_permission


class AdminAuditMixin:
    """Mixin class for admin action auditing."""

    def __init__(self, db: Session):
        self.db = db
        AuditService = _get_audit_service()
        self.audit_service = AuditService(db)

    async def log_admin_action(
        self,
        action_type: str,
        admin_user: User,
        target_user_id: Optional[UUID] = None,
        action_data: Optional[dict] = None,
        request: Optional[Request] = None,
        result: str = "success"
    ) -> None:
        """
        Log admin action for audit trail.

        Args:
            action_type: Type of admin action performed
            admin_user: User who performed the action
            target_user_id: ID of user affected by the action
            action_data: Additional data about the action
            request: HTTP request object for IP/user agent
            result: Result of the action (success, failure, etc.)
        """
        self.audit_service.log_event(
            event_type=f"admin_{action_type}",
            event_category="data_change",
            severity="info" if result == "success" else "warning",
            actor_id=admin_user.id,
            subject_id=target_user_id,
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get('user-agent') if request else None,
            event_data={
                "admin_action": action_type,
                "admin_role": admin_user.role.value,
                **(action_data or {})
            },
            result=result,
            data_subject_id=target_user_id,
            legal_basis="legitimate_interest"
        )


# Lazy convenience dependencies to avoid circular import
# These are now functions that return the dependency on first call
_cached_require_admin = None
_cached_require_admin_or_doctor = None
_cached_require_any_role = None


def require_admin():
    """Get admin requirement dependency (lazy initialization)."""
    global _cached_require_admin
    if _cached_require_admin is None:
        _cached_require_admin = AdminPermissions.require_admin()
    return _cached_require_admin


def require_admin_or_doctor():
    """Get admin or doctor requirement dependency (lazy initialization)."""
    global _cached_require_admin_or_doctor
    if _cached_require_admin_or_doctor is None:
        _cached_require_admin_or_doctor = AdminPermissions.require_role([UserRole.ADMIN, UserRole.DOCTOR])
    return _cached_require_admin_or_doctor


def require_any_role():
    """Get any role requirement dependency (lazy initialization)."""
    global _cached_require_any_role
    if _cached_require_any_role is None:
        _cached_require_any_role = AdminPermissions.require_role([UserRole.ADMIN, UserRole.DOCTOR])
    return _cached_require_any_role


def _get_admin_dependency():
    """Helper to get the admin dependency lazily."""
    return require_admin()


async def get_admin_user(
    current_user: User = Depends(_get_admin_dependency)
) -> User:
    """
    Convenience function to get current admin user.

    Args:
        current_user: Current authenticated user (must be admin)

    Returns:
        Admin user
    """
    return current_user


async def validate_user_modification_permission(
    target_user_id: UUID,
    admin_user: User,
    db: Session
) -> User:
    """
    Validate that admin can modify the target user.

    Args:
        target_user_id: ID of user to be modified
        admin_user: Admin user performing the action
        db: Database session

    Returns:
        Target user if modification is allowed

    Raises:
        HTTPException: If target user not found or modification not allowed
    """
    # Get target user
    target_user = db.query(User).filter(User.id == target_user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {target_user_id} not found"
        )

    # Prevent admin from modifying themselves for certain actions
    if str(target_user.id) == str(admin_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot perform this action on your own account"
        )

    return target_user


def get_client_info(request: Request) -> dict:
    """
    Extract client information from request for audit logging.

    Args:
        request: HTTP request object

    Returns:
        Dictionary with client IP, port, and user agent
    """
    client = request.client if request else None
    return {
        "ip_address": client.host if client else None,
        "port": client.port if client else None,
        "user_agent": request.headers.get('user-agent') if request else None
    }
