"""
Base schemas, dependencies and utilities for physicians module.
"""

from typing import Optional
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.models.patient import Patient
from app.schemas.v2.physicians import WorkloadLevel


def _extract_user_context(current_user) -> tuple[Optional[UserRole | str], Optional[str]]:
    """
    Extract role and user_id from current_user (dict or model).

    Args:
        current_user: User object or dict

    Returns:
        Tuple of (UserRole, user_id string)
    """
    role = None
    user_id = None

    if isinstance(current_user, dict):
        role = current_user.get("role")
        user_id = current_user.get("id")
    else:
        user_id = getattr(current_user, "id", None)
        role = getattr(current_user, "role", None)

    if isinstance(role, UserRole):
        role_token: Optional[UserRole | str] = role
    elif isinstance(role, str):
        try:
            role_token = UserRole(role.lower())
        except ValueError:
            role_token = role.lower()
    else:
        role_token = None

    if user_id is not None:
        user_id = str(user_id)

    return role_token, user_id


def _is_admin(current_user) -> bool:
    """
    Check if current user is admin.

    Args:
        current_user: User object or dict

    Returns:
        True if user is admin
    """
    role_enum, _ = _extract_user_context(current_user)
    return role_enum == UserRole.ADMIN


def _calculate_workload_level(patient_count: int) -> WorkloadLevel:
    """
    Calculate workload level based on patient count.

    Thresholds:
    - LOW: 0-20 patients
    - MEDIUM: 21-50 patients
    - HIGH: 51-100 patients
    - OVERLOADED: 101+ patients

    Args:
        patient_count: Number of assigned patients

    Returns:
        WorkloadLevel enum value
    """
    if patient_count == 0:
        return WorkloadLevel.LOW
    elif patient_count <= 20:
        return WorkloadLevel.LOW
    elif patient_count <= 50:
        return WorkloadLevel.MEDIUM
    elif patient_count <= 100:
        return WorkloadLevel.HIGH
    else:
        return WorkloadLevel.OVERLOADED


async def validate_physician_access(
    physician_id: UUID,
    current_user,
    db: AsyncSession,
    allow_patient_view: bool = True,
) -> User:
    """
    Validate physician exists and check user access permissions.

    RBAC Rules:
    - Admin: Can access any physician
    - Physician: Can access self
    - Patient: Can access assigned physician (if allow_patient_view=True)

    Args:
        physician_id: UUID of physician to validate
        current_user: Current authenticated user
        db: Database session
        allow_patient_view: Allow patients to view their assigned physician

    Returns:
        User: Validated physician object

    Raises:
        HTTPException: If physician not found or access denied
    """
    # Fetch physician
    physician_result = await db.execute(
        select(User).where(
            User.id == physician_id,
            User.role.in_([UserRole.DOCTOR, UserRole.ADMIN]),
        )
    )
    physician = physician_result.scalar_one_or_none()

    if not physician:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Physician with id {physician_id} not found",
        )

    # RBAC: Check access
    role_enum, user_id = _extract_user_context(current_user)

    if role_enum == UserRole.ADMIN:
        return physician

    # Physicians can view themselves
    if str(physician.id) == user_id:
        return physician

    # Patients can view their assigned physician.
    # In this codebase UserRole currently defines only ADMIN/DOCTOR,
    # but some auth contexts may still provide "patient" as a raw string.
    role_value = role_enum.value if isinstance(role_enum, UserRole) else role_enum
    is_patient_role = role_value == "patient"
    if is_patient_role and allow_patient_view and user_id:
        try:
            patient_uuid = UUID(user_id)
        except ValueError:
            patient_uuid = None

        patient_assigned = None
        if patient_uuid:
            patient_result = await db.execute(
                select(Patient).where(
                    Patient.doctor_id == physician_id,
                    Patient.id == patient_uuid,
                    Patient.deleted_at.is_(None),
                )
            )
            patient_assigned = patient_result.scalar_one_or_none()

        if patient_assigned:
            return physician

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to access this physician",
    )


__all__ = [
    "_extract_user_context",
    "_is_admin",
    "_calculate_workload_level",
    "validate_physician_access",
]
