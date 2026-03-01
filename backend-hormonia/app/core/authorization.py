"""
Role-Based Access Control (RBAC) decorators and utilities.

This module provides decorators and functions for implementing fine-grained
authorization in API endpoints following backend API best practices.
"""

from functools import wraps
from typing import Callable, Optional
from uuid import UUID
import logging

from fastapi import HTTPException, status

from app.models.user import UserRole
from app.core.permissions import Permission, PermissionChecker

logger = logging.getLogger(__name__)


def _extract_user_from_kwargs(**kwargs) -> Optional[dict]:
    """
    Extract current_user from endpoint kwargs.

    Args:
        **kwargs: Endpoint function kwargs

    Returns:
        User dict or None
    """
    current_user = kwargs.get("current_user")

    if current_user is None:
        return None

    # Handle both dict and model objects
    if isinstance(current_user, dict):
        return current_user

    # Convert model to dict
    return {
        "id": str(getattr(current_user, "id", "")),
        "email": getattr(current_user, "email", ""),
        "role": getattr(current_user, "role", "").value
        if hasattr(getattr(current_user, "role", ""), "value")
        else str(getattr(current_user, "role", "")),
        "is_active": getattr(current_user, "is_active", False),
    }


def _get_user_role(current_user: dict) -> str:
    """
    Extract role from user dict.

    Args:
        current_user: User dictionary

    Returns:
        User role as string
    """
    role = current_user.get("role", "")

    # Handle enum values
    if hasattr(role, "value"):
        return role.value

    return str(role).lower()


def require_permission(*permissions: Permission):
    """
    Decorator to require specific permission(s) for an endpoint.

    Validates that the authenticated user has at least one of the specified
    permissions. Raises HTTP 401 if not authenticated, HTTP 403 if lacking permission.

    Args:
        *permissions: One or more Permission enums required

    Returns:
        Decorator function

    Example:
        @router.get("/patients/{patient_id}")
        @require_permission(Permission.PATIENT_READ)
        async def get_patient(patient_id: str, current_user = Depends(get_current_user)):
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = _extract_user_from_kwargs(**kwargs)

            if not current_user:
                logger.warning(
                    f"Permission check failed: No authenticated user for {func.__name__}"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            user_role = _get_user_role(current_user)
            try:
                user_role_enum = UserRole(user_role)
            except ValueError:
                user_role_enum = None

            # Check if user has any of the required permissions
            has_permission = bool(user_role_enum) and any(
                PermissionChecker.has_permission(user_role_enum, perm) for perm in permissions
            )

            if not has_permission:
                permission_names = [p.value for p in permissions]
                logger.warning(
                    f"Permission denied: User {current_user.get('email')} "
                    f"(role: {user_role}) lacks permissions: {permission_names}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied. Required: {', '.join(permission_names)}",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_role(*roles: UserRole):
    """
    Decorator to require specific role(s) for an endpoint.

    Simpler alternative to require_permission when role-level checks are sufficient.

    Args:
        *roles: One or more UserRole enums required

    Returns:
        Decorator function

    Example:
        @router.post("/patients")
        @require_role(UserRole.ADMIN, UserRole.DOCTOR)
        async def create_patient(patient_data: PatientCreate, current_user = Depends(get_current_user)):
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = _extract_user_from_kwargs(**kwargs)

            if not current_user:
                logger.warning(
                    f"Role check failed: No authenticated user for {func.__name__}"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            user_role = _get_user_role(current_user)

            # Check if user has required role
            allowed_roles = [r.value for r in roles]

            if user_role not in allowed_roles:
                logger.warning(
                    f"Role denied: User {current_user.get('email')} "
                    f"(role: {user_role}) not in allowed roles: {allowed_roles}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required role: {', '.join(allowed_roles)}",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def check_patient_access(current_user: dict, patient_doctor_id: UUID) -> bool:
    """
    Check if user can access a specific patient.

    Admins can access all patients.
    Doctors can only access their own patients.

    Args:
        current_user: User dictionary
        patient_doctor_id: UUID of the patient's assigned doctor

    Returns:
        True if access allowed, False otherwise
    """
    if not current_user:
        return False

    user_role = _get_user_role(current_user)

    # Admins can access all patients
    if user_role == UserRole.ADMIN.value:
        return True

    # Doctors can only access their own patients
    if user_role == UserRole.DOCTOR.value:
        user_id = current_user.get("id")
        if not user_id:
            return False

        try:
            user_uuid = UUID(user_id)
            return user_uuid == patient_doctor_id
        except (ValueError, TypeError):
            return False

    return False


def ensure_patient_access(current_user: dict, patient_doctor_id: UUID):
    """
    Ensure user can access a specific patient, raise HTTPException if not.

    Args:
        current_user: User dictionary
        patient_doctor_id: UUID of the patient's assigned doctor

    Raises:
        HTTPException: 403 if access denied
    """
    if not check_patient_access(current_user, patient_doctor_id):
        user_email = current_user.get("email", "unknown") if current_user else "unknown"
        user_role = _get_user_role(current_user) if current_user else "none"

        logger.warning(
            f"Patient access denied: User {user_email} (role: {user_role}) "
            f"attempted to access patient with doctor_id {patient_doctor_id}"
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this patient",
        )


def require_admin():
    """
    Decorator shorthand for admin-only endpoints.

    Returns:
        Decorator function

    Example:
        @router.delete("/patients/{patient_id}")
        @require_admin()
        async def delete_patient(patient_id: str, current_user = Depends(get_current_user)):
            ...
    """
    return require_role(UserRole.ADMIN)


def require_doctor_or_admin():
    """
    Decorator shorthand for endpoints accessible by doctors and admins.

    Returns:
        Decorator function

    Example:
        @router.post("/patients")
        @require_doctor_or_admin()
        async def create_patient(patient_data: PatientCreate, current_user = Depends(get_current_user)):
            ...
    """
    return require_role(UserRole.ADMIN, UserRole.DOCTOR)


__all__ = [
    "require_permission",
    "require_role",
    "require_admin",
    "require_doctor_or_admin",
    "check_patient_access",
    "ensure_patient_access",
]
