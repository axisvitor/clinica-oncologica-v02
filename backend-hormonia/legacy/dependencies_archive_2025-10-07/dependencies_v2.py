"""
Thread-safe FastAPI dependencies using ServiceContainer pattern.
Replaces the problematic shared ServiceProvider with request-scoped services.
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
import redis.asyncio as redis

from app.database import get_db
from app.services.container import ServiceContainer, get_service_container
from app.models.user import User, UserRole
from app.models.patient import Patient

# Security scheme
security = HTTPBearer()

# Thread-safe Redis dependency
async def get_redis_client(request: Request) -> Optional[redis.Redis]:
    """Get Redis client from app state (shared, but Redis is thread-safe)."""
    return getattr(request.app.state, 'redis_client', None)


# Core dependency: Request-scoped service container
async def get_container(
    db: Session = Depends(get_db),
    redis_client: Optional[redis.Redis] = Depends(get_redis_client)
) -> ServiceContainer:
    """
    Get request-scoped service container.

    Key improvements over ServiceProvider:
    1. Fresh database session per request (thread-safe)
    2. Request-scoped service instances
    3. Proper resource cleanup
    4. No shared state between requests
    """
    container = get_service_container(db=db, redis_client=redis_client)
    try:
        yield container
    finally:
        # Cleanup resources
        container.cleanup()


# Authentication dependencies (now thread-safe)
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    container: ServiceContainer = Depends(get_container)
) -> User:
    """Get current authenticated user from JWT token (thread-safe)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Use request-scoped auth service
    auth_service = container.get_auth_service()
    token_data = auth_service.verify_token(credentials.credentials, token_type="access")

    if token_data is None:
        raise credentials_exception

    user = auth_service._get_user_from_token_data(token_data)

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user"
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user (additional validation)."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


async def get_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current user with admin privileges."""
    if current_user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


async def get_doctor_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current user with doctor privileges."""
    if current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


# Service dependencies (now thread-safe)
def get_auth_service(container: ServiceContainer = Depends(get_container)):
    """Get thread-safe AuthService instance."""
    return container.get_auth_service()


def get_patient_service(container: ServiceContainer = Depends(get_container)):
    """Get thread-safe PatientService instance."""
    return container.get_patient_service()


def get_flow_service(container: ServiceContainer = Depends(get_container)):
    """Get thread-safe FlowIntegrationService instance."""
    return container.get_flow_integration_service()


def get_quiz_service(container: ServiceContainer = Depends(get_container)):
    """Get thread-safe QuizService instance."""
    return container.get_quiz_service()


def get_message_service(container: ServiceContainer = Depends(get_container)):
    """Get thread-safe MessageService instance."""
    return container.get_message_service()


def get_monthly_quiz_service(container: ServiceContainer = Depends(get_container)):
    """Get thread-safe MonthlyQuizService instance."""
    return container.get_monthly_quiz_service()


# Patient access validation (now thread-safe)
async def validate_patient_access(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container)
) -> Patient:
    """
    Validate user has access to patient and return patient object (thread-safe).
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        patient_service = container.get_patient_service()
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

    # Role-based authorization
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


# Repository dependencies (now thread-safe)
def get_patient_repository(container: ServiceContainer = Depends(get_container)):
    """Get thread-safe PatientRepository instance."""
    return container.get_patient_repository()


def get_user_repository(container: ServiceContainer = Depends(get_container)):
    """Get thread-safe UserRepository instance."""
    return container.get_user_repository()


# Request context for audit logging (thread-safe)
class RequestContext:
    """Container for request context information."""
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
    current_user: Optional[User] = Depends(get_current_user)
) -> RequestContext:
    """Extract request context for audit logging (thread-safe)."""
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

    # Extract session ID from request state
    session_id = getattr(request.state, "session_id", None)

    return RequestContext(
        ip_address=ip_address,
        user_agent=user_agent,
        user_id=user_id,
        session_id=session_id
    )


# Monthly quiz token validation (thread-safe)
async def verify_monthly_quiz_token(
    token: str,
    container: ServiceContainer = Depends(get_container)
) -> dict:
    """Verify monthly quiz token for public access (thread-safe)."""
    from app.exceptions import ValidationError

    try:
        monthly_quiz_service = container.get_monthly_quiz_service()
        payload = monthly_quiz_service._verify_token(token)
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