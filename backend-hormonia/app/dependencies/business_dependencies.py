"""Business Logic Dependencies - Domain Validation & Access Control"""
from fastapi import Depends, HTTPException, status, Path, Query, Request
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from uuid import UUID

from app.models.user import User, UserRole
from app.models.patient import Patient
from app.schemas.common import PaginationParams
from app.dependencies.auth_dependencies import get_current_user, get_optional_user
from app.dependencies.service_dependencies import get_patient_service, get_patient_repository
from app.services import ServiceProvider, get_service_provider

# =============================================================================
# PAGINATION DEPENDENCIES
# =============================================================================

def get_pagination_params(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=200, description="Maximum items to return")
) -> PaginationParams:
    """Get pagination parameters"""
    return PaginationParams(skip=skip, limit=limit)

# =============================================================================
# PATIENT ACCESS CONTROL DEPENDENCIES
# =============================================================================

async def validate_patient_access(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    patient_service = Depends(get_patient_service)
) -> Patient:
    """Validate user has access to patient and return patient object"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        patient = patient_service.get_patient(patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving patient {patient_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving patient information"
        )
    
    # Implement role-based authorization
    if current_user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
        return patient
    elif current_user.role == UserRole.DOCTOR:
        if patient.doctor_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Patient not assigned to current doctor"
            )
        return patient
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Insufficient permissions for patient access"
        )


async def get_validated_patient(
    patient_id: UUID,
    patient_repo = Depends(get_patient_repository)
) -> Patient:
    """Validate that patient exists and return it"""
    from app.exceptions import patient_not_found_exception
    
    patient = patient_repo.get(patient_id)
    if not patient:
        raise patient_not_found_exception(str(patient_id))
    return patient


def verify_patient_access(
    patient_id: UUID = Path(...),
    current_user: User = Depends(get_current_user),
    patient_repo = Depends(get_patient_repository)
) -> Patient:
    """Verify user has access to manage this patient"""
    from app.exceptions import patient_access_denied_exception, patient_not_found_exception
    
    # First validate that patient exists
    patient = patient_repo.get(patient_id)
    if not patient:
        raise patient_not_found_exception(str(patient_id))
    
    # Admin users can access all patients
    if current_user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
        return patient
    
    # Doctors can only access their assigned patients
    if current_user.role == UserRole.DOCTOR:
        if hasattr(patient, 'doctor_id') and patient.doctor_id == current_user.id:
            return patient
    
    # If no access rules match, deny access
    raise patient_access_denied_exception(str(patient.id))

# =============================================================================
# MONTHLY QUIZ VALIDATION DEPENDENCIES
# =============================================================================

async def verify_monthly_quiz_token(
    token: str,
    services: ServiceProvider = Depends(get_service_provider)
) -> Dict[str, Any]:
    """Verify monthly quiz token for public access"""
    from app.exceptions import ValidationError

    try:
        payload = services.monthly_quiz_service._verify_token(token)
        return payload
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid quiz token: {str(e)}"
        )

# =============================================================================
# REQUEST CONTEXT DEPENDENCIES (For audit logging)
# =============================================================================

class RequestContext:
    """Container for request context information used in audit logging"""
    def __init__(
        self,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        user_id: Optional[UUID] = None,
        session_id: Optional[str] = None
    ):
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.user_id = user_id
        self.session_id = session_id


async def get_request_context(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
) -> RequestContext:
    """Extract request context for audit logging"""
    # Extract IP address with X-Forwarded-For support
    ip_address = None
    if "x-forwarded-for" in request.headers:
        ip_address = request.headers["x-forwarded-for"].split(",")[0].strip()
    elif "x-real-ip" in request.headers:
        ip_address = request.headers["x-real-ip"]
    else:
        ip_address = request.client.host if request.client else "unknown"

    # Extract user agent
    user_agent = request.headers.get("user-agent", "unknown")

    # Extract user ID if authenticated
    user_id = current_user.id if current_user else None

    # Extract session ID from request state or generate one
    session_id = getattr(request.state, "session_id", None)

    return RequestContext(
        ip_address=ip_address,
        user_agent=user_agent,
        user_id=user_id,
        session_id=session_id
    )
