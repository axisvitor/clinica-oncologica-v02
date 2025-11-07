"""
Thread-safe FastAPI dependency injection for Hormonia Backend System.
"""

from fastapi import Depends, HTTPException, status, Path, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
import logging
import httpx
import redis.asyncio as redis

from app.thread_safe_database import get_db, get_database_manager
from app.thread_safe_services import ThreadSafeServiceProvider, get_service_provider
from app.config import settings
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.repositories.user import UserRepository


logger = logging.getLogger(__name__)

# Security scheme for JWT authentication (used to carry Supabase Bearer token)
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    services: ThreadSafeServiceProvider = Depends(get_service_provider)
) -> User:
    """
    Get current authenticated user by validating Supabase Auth token.
    Thread-safe implementation with proper error handling.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Validate token at Supabase and fetch user profile
        supabase_url = settings.SUPABASE_URL.rstrip("/")
        headers_req = {
            "apikey": settings.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {credentials.credentials}",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{supabase_url}/auth/v1/user", headers=headers_req)
        if resp.status_code != 200:
            raise credentials_exception
        data = resp.json()
        email = data.get("email")
        if not email:
            raise credentials_exception

        # Resolve local user by email
        user = services.user_repository.get_by_email(email.strip().lower())
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not provisioned")

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive user"
            )

        return user

    except Exception as e:
        logger.error(f"Error authenticating user: {e}")
        raise credentials_exception


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user (additional validation).
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


async def get_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get current user with admin privileges.
    """
    if current_user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


async def get_doctor_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get current user with doctor privileges.
    """
    if current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    request: Request = None
) -> Optional[User]:
    """
    Get current user if authenticated, otherwise return None.
    Thread-safe implementation with minimal overhead.
    """
    if credentials is None:
        return None
    try:
        services = get_service_provider(request)
        return await get_current_user(credentials, services)
    except HTTPException:
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_optional_user: {e}")
        return None


# Database dependency (thread-safe)
get_database = get_db


# Redis dependency (thread-safe)
async def get_redis(request: Request) -> Optional[redis.Redis]:
    """Get Redis client instance from app state."""
    return getattr(request.app.state, 'redis_client', None)


# WebSocket user authentication dependency (Supabase-only)
async def get_current_user_websocket(
    websocket,
    services: ThreadSafeServiceProvider = Depends(get_service_provider)
) -> Optional[User]:
    """
    Get current user from WebSocket connection validating Supabase token.
    Thread-safe implementation.
    """
    try:
        # Get token from query parameters or headers
        token = None
        if hasattr(websocket, 'query_params') and 'token' in websocket.query_params:
            token = websocket.query_params['token']
        elif hasattr(websocket, 'headers'):
            auth_header = None
            try:
                auth_header = websocket.headers.get('authorization')
            except Exception:
                if 'authorization' in getattr(websocket, 'headers', {}):
                    auth_header = websocket.headers['authorization']
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]

        if not token:
            return None

        # Validate token at Supabase and fetch user profile
        supabase_url = settings.SUPABASE_URL.rstrip("/")
        headers_req = {
            "apikey": settings.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {token}",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{supabase_url}/auth/v1/user", headers=headers_req)
        if resp.status_code != 200:
            return None
        data = resp.json()
        email = data.get("email")
        if not email:
            return None

        user = services.user_repository.get_by_email(email.strip().lower())
        if user is None or not user.is_active:
            return None

        return user

    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        return None


def get_patient_service(services: ThreadSafeServiceProvider = Depends(get_service_provider)) -> 'PatientService':
    """Get PatientService instance (thread-safe)."""
    return services.patient_service


def get_quiz_service(services: ThreadSafeServiceProvider = Depends(get_service_provider)) -> 'QuizService':
    """Get QuizService instance (thread-safe)."""
    return services.quiz_service


def get_quiz_template_service(services: ThreadSafeServiceProvider = Depends(get_service_provider)) -> 'QuizTemplateService':
    """Get QuizTemplateService instance (thread-safe)."""
    return services.quiz_service.template_service


def get_quiz_response_service(services: ThreadSafeServiceProvider = Depends(get_service_provider)) -> 'QuizResponseService':
    """Get QuizResponseService instance (thread-safe)."""
    return services.quiz_service.response_service


def get_quiz_session_service(services: ThreadSafeServiceProvider = Depends(get_service_provider)) -> 'QuizSessionService':
    """Get QuizSessionService instance (thread-safe)."""
    return services.quiz_service.session_service


def get_quiz_analytics_service(services: ThreadSafeServiceProvider = Depends(get_service_provider)) -> 'QuizAnalyticsService':
    """Get QuizAnalyticsService instance (thread-safe)."""
    return services.quiz_service.analytics_service


def get_flow_service(services: ThreadSafeServiceProvider = Depends(get_service_provider)) -> 'FlowEngineIntegrationService':
    """Get FlowEngineIntegrationService instance (thread-safe)."""
    return services.flow_service


def get_analytics_service(services: ThreadSafeServiceProvider = Depends(get_service_provider)) -> 'AnalyticsService':
    """Get AnalyticsService instance (thread-safe)."""
    return services.analytics_service


def get_message_service(services: ThreadSafeServiceProvider = Depends(get_service_provider)) -> 'MessageService':
    """Get MessageService instance (thread-safe)."""
    return services.message_service


def get_report_service(services: ThreadSafeServiceProvider = Depends(get_service_provider)) -> 'ReportService':
    """Get ReportService instance (thread-safe)."""
    return services.report_service


def get_auth_service(services: ThreadSafeServiceProvider = Depends(get_service_provider)) -> 'AuthService':
    """Get AuthService instance (thread-safe)."""
    return services.auth_service


def get_notification_service(services: ThreadSafeServiceProvider = Depends(get_service_provider)) -> 'NotificationService':
    """Get NotificationService instance (thread-safe)."""
    return services.notification_service


def get_file_service(services: ThreadSafeServiceProvider = Depends(get_service_provider)) -> 'FileService':
    """Get FileService instance (thread-safe)."""
    return services.file_service


def get_monthly_quiz_service(services: ThreadSafeServiceProvider = Depends(get_service_provider)) -> 'MonthlyQuizService':
    """Get MonthlyQuizService instance (thread-safe)."""
    return services.monthly_quiz_service


def get_metrics_collector_service(services: ThreadSafeServiceProvider = Depends(get_service_provider)) -> 'MetricsCollectorService':
    """Get MetricsCollectorService instance (thread-safe)."""
    return services.metrics_collector_service


def get_metrics_redis_storage(services: ThreadSafeServiceProvider = Depends(get_service_provider)) -> 'MetricsRedisStorage':
    """Get MetricsRedisStorage instance (thread-safe)."""
    return services.metrics_redis_storage


# Pagination dependency (unchanged)
from app.schemas.common import PaginationParams
from fastapi import Query
from app.services.unified_cache import UnifiedCacheService


def get_pagination_params(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=200, description="Maximum items to return")
) -> PaginationParams:
    """Get pagination parameters."""
    return PaginationParams(skip=skip, limit=limit)


async def validate_patient_access(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    patient_service = Depends(get_patient_service)
) -> Patient:
    """
    Validate user has access to patient and return patient object.
    Thread-safe implementation with proper error handling.
    """
    try:
        patient = patient_service.get_patient(patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error retrieving patient {patient_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving patient information"
        )

    # Implement role-based authorization
    if current_user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
        # Admins can access all patients
        return patient
    elif current_user.role == UserRole.DOCTOR:
        # Doctors can only access their assigned patients
        if hasattr(patient, 'doctor_id') and patient.doctor_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Patient not assigned to current doctor"
            )
        return patient
    else:
        # Other roles have no patient access by default
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Insufficient permissions for patient access"
        )

    return patient


# Thread-safe repository dependencies
def get_flow_state_repository(db: Session = Depends(get_db)) -> 'FlowStateRepository':
    """Get flow state repository instance (thread-safe)."""
    from app.repositories.flow import FlowStateRepository
    return FlowStateRepository(db)


def get_patient_repository(db: Session = Depends(get_db)) -> 'PatientRepository':
    """Get patient repository instance (thread-safe)."""
    from app.repositories.patient import PatientRepository
    return PatientRepository(db)


def get_user_repository(db: Session = Depends(get_db)) -> 'UserRepository':
    """Get user repository instance (thread-safe)."""
    return UserRepository(db)


async def get_websocket_manager() -> 'WebSocketManager':
    """Get WebSocket manager instance (thread-safe)."""
    from app.services.websocket_manager import WebSocketManager
    return WebSocketManager.get_instance()


def get_flow_management_service(
    flow_repo = Depends(get_flow_state_repository),
    flow_engine = Depends(get_flow_service)
) -> 'FlowManagementService':
    """Get flow management service instance (thread-safe)."""
    from app.services.flow_management import FlowManagementService
    return FlowManagementService(flow_repo, flow_engine)


async def get_validated_patient(
    patient_id: UUID,
    patient_repo = Depends(get_patient_repository)
) -> Patient:
    """
    Validate that patient exists and return it (thread-safe).
    """
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
    """
    Verify user has access to manage this patient (thread-safe).
    """
    from app.exceptions import patient_access_denied_exception, patient_not_found_exception
    from app.models.user import UserRole

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


# Enhanced service dependencies for caching and performance (thread-safe)
async def get_cache_service() -> 'CacheService':
    """Get cache service instance (thread-safe)."""
    
    return CacheService()


async def verify_monthly_quiz_token(
    token: str,
    services: ThreadSafeServiceProvider = Depends(get_service_provider)
) -> Dict[str, Any]:
    """
    Verify monthly quiz token for public access (thread-safe).
    """
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


class RequestContext:
    """
    Container for request context information used in audit logging.
    Thread-safe implementation.
    """
    def __init__(
        self,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        user_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
        thread_id: Optional[int] = None
    ):
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.user_id = user_id
        self.session_id = session_id
        self.thread_id = thread_id


async def get_request_context(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user)
) -> RequestContext:
    """
    Extract request context for audit logging (thread-safe).
    """
    import threading

    # Extract IP address with X-Forwarded-For support
    ip_address = None
    if "x-forwarded-for" in request.headers:
        # Get first IP from X-Forwarded-For chain
        ip_address = request.headers["x-forwarded-for"].split(",")[0].strip()
    elif "x-real-ip" in request.headers:
        ip_address = request.headers["x-real-ip"]
    else:
        # Fallback to client host
        ip_address = request.client.host if request.client else "unknown"

    # Extract user agent
    user_agent = request.headers.get("user-agent", "unknown")

    # Extract user ID if authenticated
    user_id = current_user.id if current_user else None

    # Extract session ID from request state or generate one
    session_id = getattr(request.state, "session_id", None)

    # Add thread ID for debugging
    thread_id = threading.get_ident()

    return RequestContext(
        ip_address=ip_address,
        user_agent=user_agent,
        user_id=user_id,
        session_id=session_id,
        thread_id=thread_id
    )


# Database health check dependency (thread-safe)
async def get_database_health() -> Dict[str, Any]:
    """
    Get database health status and metrics (thread-safe).
    """
    try:
        db_manager = get_database_manager()
        health_status = db_manager.health_check()
        pool_metrics = db_manager.get_pool_status()

        return {
            "status": "healthy" if health_status else "unhealthy",
            "metrics": pool_metrics,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Database health check error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# Service provider health check dependency
async def get_service_provider_health(
    request: Request
) -> Dict[str, Any]:
    """
    Get service provider health status and metrics (thread-safe).
    """
    import threading

    try:
        services = get_service_provider(request)
        thread_id = threading.get_ident()

        # Get service cache metrics
        service_cache_size = len(services._service_cache)
        repository_cache_size = len(services._repository_cache)

        # Get total instances across all threads
        total_instances = len(ThreadSafeServiceProvider._instances)

        return {
            "status": "healthy",
            "thread_id": thread_id,
            "service_cache_size": service_cache_size,
            "repository_cache_size": repository_cache_size,
            "total_instances": total_instances,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Service provider health check error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# Export all dependencies for easy import
__all__ = [
    # Authentication
    'get_current_user',
    'get_current_active_user',
    'get_admin_user',
    'get_doctor_user',
    'get_optional_user',
    'get_current_user_websocket',

    # Database
    'get_database',
    'get_redis',

    # Services
    'get_auth_service',
    'get_patient_service',
    'get_quiz_service',
    'get_quiz_template_service',
    'get_quiz_response_service',
    'get_quiz_session_service',
    'get_quiz_analytics_service',
    'get_flow_service',
    'get_analytics_service',
    'get_message_service',
    'get_report_service',
    'get_notification_service',
    'get_file_service',
    'get_monthly_quiz_service',
    'get_metrics_collector_service',
    'get_metrics_redis_storage',

    # Repositories
    'get_flow_state_repository',
    'get_patient_repository',
    'get_user_repository',

    # Utilities
    'get_pagination_params',
    'validate_patient_access',
    'verify_patient_access',
    'get_validated_patient',
    'get_websocket_manager',
    'get_flow_management_service',
    'get_cache_service',
    'verify_monthly_quiz_token',
    'get_request_context',
    'get_database_health',
    'get_service_provider_health',

    # Classes
    'RequestContext',
    'security'
]