"""Business Logic Dependencies - Domain Validation & Access Control"""

from fastapi import Depends, HTTPException, status, Path, Query
from typing import Dict, Any, TYPE_CHECKING
from uuid import UUID

from app.models.user import User, UserRole
from app.models.patient import Patient
from app.schemas.common import PaginationParams
from app.dependencies.auth_dependencies import get_current_user_object_from_session
from app.dependencies.service_dependencies import (
    get_patient_service,
    get_patient_repository,
)
if TYPE_CHECKING:
    from app.services import ServiceProvider
from app.utils.auth_helpers import extract_user_context, ensure_uuid
from typing import Generator


# CRITICAL: Lazy import to avoid circular dependency
class _ThreadSafeProviderDependency:
    """Callable class for lazy importing to prevent circular import"""

    def __call__(self) -> Generator:
        from app.dependencies import get_thread_safe_service_provider

        yield from get_thread_safe_service_provider()


_get_provider_dep = _ThreadSafeProviderDependency()

# =============================================================================
# PAGINATION DEPENDENCIES
# =============================================================================


def get_pagination_params(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=200, description="Maximum items to return"),
) -> PaginationParams:
    """Get pagination parameters"""
    return PaginationParams(skip=skip, limit=limit)


# =============================================================================
# PATIENT ACCESS CONTROL DEPENDENCIES
# =============================================================================


async def validate_patient_access(
    patient_id: UUID,
    current_user: Any = Depends(get_current_user_object_from_session),
    patient_service=Depends(get_patient_service),
) -> Patient:
    """Validate user has access to patient and return patient object"""
    import logging

    logger = logging.getLogger(__name__)

    try:
        patient = patient_service.get_patient(patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving patient {patient_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving patient information",
        )

    # Implement role-based authorization (supports dict or User)
    role_enum, user_id = extract_user_context(current_user)

    if role_enum == UserRole.ADMIN:
        return patient

    if role_enum == UserRole.DOCTOR:
        user_uuid = ensure_uuid(user_id)
        if not user_uuid or patient.doctor_id != user_uuid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Patient not assigned to current doctor",
            )
        return patient

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied: Insufficient permissions for patient access",
    )


async def get_validated_patient(
    patient_id: UUID, patient_repo=Depends(get_patient_repository)
) -> Patient:
    """Validate that patient exists and return it"""
    from app.exceptions import patient_not_found_exception

    patient = patient_repo.get(patient_id)
    if not patient:
        raise patient_not_found_exception(str(patient_id))
    return patient


def verify_patient_access(
    patient_id: UUID = Path(...),
    current_user: User = Depends(get_current_user_object_from_session),
    patient_repo=Depends(get_patient_repository),
) -> Patient:
    """Verify user has access to manage this patient"""
    from app.exceptions import (
        patient_access_denied_exception,
        patient_not_found_exception,
    )

    # First validate that patient exists
    patient = patient_repo.get(patient_id)
    if not patient:
        raise patient_not_found_exception(str(patient_id))

    # Admin users can access all patients
    if current_user.role == UserRole.ADMIN:
        return patient

    # Doctors can only access their assigned patients
    if current_user.role == UserRole.DOCTOR:
        if hasattr(patient, "doctor_id") and patient.doctor_id == current_user.id:
            return patient

    # If no access rules match, deny access
    raise patient_access_denied_exception(str(patient.id))


# =============================================================================
# MONTHLY QUIZ VALIDATION DEPENDENCIES
# =============================================================================


async def verify_monthly_quiz_token(
    token: str, services: "ServiceProvider" = Depends(_get_provider_dep)
) -> Dict[str, Any]:
    """
    Verify monthly quiz token for public access.

    Thread-safety: Uses per-request ServiceProvider with isolated session.
    """
    from app.exceptions import ValidationError

    try:
        payload = services.monthly_quiz_service._verify_token(token)
        return payload
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid quiz token")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired quiz token",
        )
