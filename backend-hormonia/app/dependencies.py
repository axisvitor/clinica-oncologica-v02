"""
FastAPI dependency injection for Hormonia Backend System.

Updated to use thread-safe session management with request-scoped
database sessions and service providers.
"""
import logging
import httpx
from fastapi import Depends, HTTPException, status, Path, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, Generator
from jose import jwt, JWTError
from datetime import datetime
from uuid import UUID

from app.database import get_db, get_supabase
from app.services.flow_analytics import FlowAnalyticsService
from app.config import settings
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.repositories.user import UserRepository
import redis.asyncio as redis
from typing import Optional as OptionalType

# Import directly from the services.py file (not the services package)
# to avoid circular imports with app/services/__init__.py
import importlib.util
import sys
import os

# Import ServiceProvider directly - circular import resolved by lazy loading
# This is safer than complex importlib logic in production
try:
    from app.services import ServiceProvider
    # Legacy function - will be imported when available
    _legacy_get_service_provider = None
    try:
        from app.services import get_service_provider as _legacy_get_service_provider
    except ImportError:
        pass  # Legacy function may not be available
except ImportError as e:
    logger.error(f"Failed to import ServiceProvider: {e}")
    raise ImportError(f"ServiceProvider not available: {e}") from e
from app.core.session_manager import get_session_manager, get_request_factory

logger = logging.getLogger(__name__)

# Security scheme for JWT authentication
security = HTTPBearer()


# ==============================================================================
# THREAD-SAFE SESSION AND SERVICE DEPENDENCIES
# ==============================================================================

def get_thread_safe_db() -> Generator[Session, None, None]:
    """
    Get thread-safe database session using the new session manager.

    This dependency provides request-scoped database sessions that are
    automatically closed after the request completes.

    Yields:
        Session: SQLAlchemy database session for this request
    """
    try:
        session_manager = get_session_manager()
        with session_manager.get_session() as session:
            yield session
    except Exception as e:
        logger.error(f"Error in get_thread_safe_db: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection error"
        )


def get_thread_safe_service_provider() -> Generator[ServiceProvider, None, None]:
    """
    Get thread-safe ServiceProvider instance using the new session management.

    This dependency provides request-scoped ServiceProvider instances
    with their own database sessions, ensuring thread safety.

    Yields:
        ServiceProvider: Thread-safe service provider for this request
    """
    try:
        logger.debug("Starting thread-safe service provider creation")

        # Get session manager and create session directly
        session_manager = get_session_manager()

        # Create session using context manager for automatic cleanup
        with session_manager.get_session() as session:
            # Create ServiceProvider with the session
            provider = ServiceProvider(session)

            logger.debug(f"Created ServiceProvider: {hex(id(provider))} with session: {hex(id(session))}")

            # Validate session before yielding
            try:
                provider.validate_session()
                logger.debug(f"ServiceProvider session validation passed")
            except RuntimeError as validation_error:
                logger.error(f"ServiceProvider session validation failed: {validation_error}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database session validation failed - check database connectivity"
                ) from validation_error

            # Yield the provider to the request
            yield provider

        logger.debug("Thread-safe service provider context ended")

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ImportError as import_error:
        logger.error(f"Import error in service provider creation: {import_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Service provider dependencies not available"
        ) from import_error
    except ConnectionError as conn_error:
        logger.error(f"Database connection error in service provider: {conn_error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection failed"
        ) from conn_error
    except Exception as e:
        logger.error(f"Unexpected error in get_thread_safe_service_provider: {e}")
        logger.error(f"Error type: {type(e).__name__}")

        # Log provider state for debugging
        if provider:
            try:
                logger.error(f"Provider state - ID: {hex(id(provider))}, Session active: {provider.is_session_active}")
            except Exception as state_error:
                logger.error(f"Could not get provider state: {state_error}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Service provider initialization failed: {type(e).__name__}"
        ) from e


# Legacy database dependency (for backward compatibility)
# New code should use get_thread_safe_db instead
get_database = get_db


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    services: ServiceProvider = Depends(get_thread_safe_service_provider)
) -> User:
    """
    Get current authenticated user by validating Firebase Auth token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        services.validate_session()

        # Validate token with Firebase Admin SDK
        from app.services.firebase_auth_service import get_firebase_auth_service

        try:
            firebase_service = get_firebase_auth_service(
                project_id=settings.FIREBASE_ADMIN_PROJECT_ID,
                private_key=settings.FIREBASE_ADMIN_PRIVATE_KEY,
                client_email=settings.FIREBASE_ADMIN_CLIENT_EMAIL
            )
            user_info = await firebase_service.verify_token(credentials.credentials)
            email = user_info.get("email")
            if not email:
                raise credentials_exception
        except Exception as firebase_error:
            logger.error(f"Firebase authentication failed: {firebase_error}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Firebase authentication failed: {str(firebase_error)}",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Resolve local user by email
        user = services.user_repository.get_by_email(email.strip().lower())
        if user is None:
            # Auto-provision if enabled
            if getattr(settings, 'AUTO_PROVISION_SUPABASE_USERS', False):
                try:
                    from app.utils.security import get_password_hash
                    import secrets
                    full_name = None
                    if isinstance(data, dict):
                        meta = data.get('user_metadata') or {}
                        full_name = meta.get('full_name') or email
                    random_password = secrets.token_urlsafe(32)
                    hashed_password = get_password_hash(random_password)
                    # IMPORTANT: Only ADMIN and DOCTOR can access the system
                    # Patients interact only via WhatsApp and Quiz links
                    email_lower = email.strip().lower()
                    email_domain = email_lower.split('@')[-1] if '@' in email_lower else ''

                    # Check if email domain is authorized for auto-provisioning (from environment)
                    authorized_domains_str = getattr(settings, 'FIREBASE_ALLOWED_DOMAINS', '')
                    authorized_domains = [d.strip() for d in authorized_domains_str.split(',') if d.strip()] if authorized_domains_str else []

                    # Block public email domains if configured
                    block_public = getattr(settings, 'FIREBASE_BLOCK_PUBLIC_DOMAINS', False)
                    public_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'live.com', 'icloud.com']

                    if block_public and email_domain in public_domains:
                        logger.warning(f"Public domain blocked: {email_lower} from {email_domain}")
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Public email domains are not allowed. Use your institutional email."
                        )

                    if authorized_domains and email_domain not in authorized_domains:
                        logger.warning(f"Unauthorized domain attempt: {email_lower} from {email_domain}")
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Access denied. Only authorized medical professionals can access this system."
                        )

                    # Check Supabase metadata for role hint (optional)
                    assigned_role = UserRole.DOCTOR  # Default for medical professionals
                    if isinstance(data, dict):
                        meta = data.get('user_metadata') or {}
                        supabase_role = meta.get('role', '').lower()

                        # Admin role CANNOT be auto-provisioned - must be created manually
                        if supabase_role == 'admin':
                            logger.warning(f"Admin role requested for {email_lower} - denied (manual creation required)")
                            assigned_role = UserRole.DOCTOR  # Always downgrade to doctor

                        # Explicitly reject patient role attempts
                        if supabase_role == 'patient':
                            logger.error(f"Patient role attempt for {email_lower} - patients don't have system access")
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="Patients access the system via WhatsApp and Quiz links only."
                            )

                    # Log auto-provisioning for audit
                    logger.info(f"Auto-provisioning DOCTOR: {email_lower} from authorized domain {email_domain}")

                    user_data = {
                        "email": email_lower,
                        "hashed_password": hashed_password,
                        "full_name": full_name or email,
                        "role": assigned_role,
                        "is_active": True,
                        "auto_provisioned": True,  # Track auto-provisioned users
                        "specialization": "Oncologia"  # Default specialization for doctors
                    }
                    user = services.user_repository.create(user_data)
                except Exception as e:
                    logger.error(f"Auto-provisioning failed for {email}: {e}")
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not provisioned")
            else:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not provisioned")

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive user"
            )

        return user

    except RuntimeError as e:
        logger.error(f"Session validation failed in get_current_user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service unavailable"
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_current_user: {e}")
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
    services: ServiceProvider = Depends(get_thread_safe_service_provider)
) -> Optional[User]:
    """
    Get current user if authenticated, otherwise return None.
    Useful for endpoints that work with or without authentication.
    Uses thread-safe session management.
    """
    if credentials is None:
        return None

    try:
        # Use the thread-safe get_current_user directly
        return await get_current_user(credentials, services)
    except HTTPException:
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_optional_user: {e}")
        return None


# Database dependency (already defined in database.py but imported here for convenience)
get_database = get_db

# Supabase client dependency
get_supabase_client = get_supabase


# WebSocket user authentication dependency
async def get_current_user_websocket(
    websocket,
    services: ServiceProvider = Depends(get_thread_safe_service_provider)
) -> Optional[User]:
    """
    Get current user from WebSocket connection with Firebase ID token.
    Uses thread-safe session management.
    """
    try:
        # Validate that the service provider session is active
        services.validate_session()

        # Get token from query parameters or headers
        token = None
        if hasattr(websocket, 'query_params') and 'token' in websocket.query_params:
            token = websocket.query_params['token']
        elif hasattr(websocket, 'headers'):
            # Headers in Starlette are case-insensitive but accessed in lowercase
            auth_header = None
            try:
                auth_header = websocket.headers.get('authorization')
            except Exception:
                # Some websocket implementations expose headers as dict
                if 'authorization' in getattr(websocket, 'headers', {}):
                    auth_header = websocket.headers['authorization']
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]

        if not token:
            return None

        # Validate token with Firebase Admin SDK
        from app.services.firebase_auth_service import get_firebase_auth_service

        try:
            firebase_service = get_firebase_auth_service(
                project_id=settings.FIREBASE_ADMIN_PROJECT_ID,
                private_key=settings.FIREBASE_ADMIN_PRIVATE_KEY,
                client_email=settings.FIREBASE_ADMIN_CLIENT_EMAIL
            )
            user_info = await firebase_service.verify_token(token)
            email = user_info.get("email")
            if not email:
                logger.warning("[WebSocket] No email in Firebase token")
                return None
        except Exception as firebase_error:
            logger.error(f"[WebSocket] Firebase authentication failed: {firebase_error}")
            return None

        # Resolve local user by email
        user = services.user_repository.get_by_email(email.strip().lower())
        if user is None or not user.is_active:
            logger.warning(f"[WebSocket] User not found or inactive: {email}")
            return None

        return user

    except Exception as e:
        logger.error(f"Error in get_current_user_websocket: {e}")
        return None


# Redis dependency
async def get_redis(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> OptionalType[redis.Redis]:
    """Get Redis client instance using unified Redis client."""
    # Try to get from service provider first (legacy support)
    if hasattr(services, 'redis_client') and services.redis_client:
        return services.redis_client

    # Use unified Redis client for async
    try:
        from app.core.redis_unified import get_async_redis
        return await get_async_redis()
    except Exception as e:
        logger.error(f"Failed to get Redis client: {e}")
        return None


# ==============================================================================
# THREAD-SAFE SERVICE DEPENDENCIES
# ==============================================================================

def get_quiz_template_service(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'QuizTemplateService':
    """Get QuizTemplateService using thread-safe session management."""
    services.validate_session()
    return services.quiz_service.template_service

def get_quiz_response_service(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'QuizResponseService':
    """Get QuizResponseService using thread-safe session management."""
    services.validate_session()
    return services.quiz_service.response_service

def get_quiz_session_service(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'QuizSessionService':
    """Get QuizSessionService using thread-safe session management."""
    services.validate_session()
    return services.quiz_service.session_service

def get_quiz_analytics_service(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'QuizAnalyticsService':
    """Get QuizAnalyticsService using thread-safe session management."""
    services.validate_session()
    return services.quiz_service.analytics_service

def get_patient_service(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'PatientService':
    """Get PatientService using thread-safe session management."""
    services.validate_session()
    return services.patient_service

def get_flow_service(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'FlowEngineIntegrationService':
    """Get FlowEngineIntegrationService using thread-safe session management."""
    services.validate_session()
    return services.flow_service

def get_auth_service(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'AuthService':
    """Get AuthService using thread-safe session management."""
    services.validate_session()
    return services.auth_service

def get_analytics_service(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'AnalyticsService':
    """Get AnalyticsService using thread-safe session management."""
    services.validate_session()
    return services.analytics_service

def get_message_service(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'MessageService':
    """Get MessageService using thread-safe session management."""
    services.validate_session()
    return services.message_service


def get_flow_analytics_service(db: Session = Depends(get_db)) -> FlowAnalyticsService:
    """Get FlowAnalyticsService using standard DB dependency (non-thread-factory)."""
    return FlowAnalyticsService(db)

def get_quiz_service(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'QuizService':
    """Get QuizService using thread-safe session management."""
    services.validate_session()
    return services.quiz_service

def get_report_service(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'ReportService':
    """Get ReportService using thread-safe session management."""
    services.validate_session()
    return services.report_service

def get_notification_service(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'NotificationService':
    """Get NotificationService using thread-safe session management."""
    services.validate_session()
    return services.notification_service

def get_file_service(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'FileService':
    """Get FileService using thread-safe session management."""
    services.validate_session()
    return services.file_service

def get_monthly_quiz_service(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'MonthlyQuizService':
    """Get MonthlyQuizService using thread-safe session management."""
    services.validate_session()
    return services.monthly_quiz_service

def get_metrics_collector_service(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'MetricsCollectorService':
    """Get MetricsCollectorService using thread-safe session management."""
    services.validate_session()
    return services.metrics_collector_service

def get_metrics_redis_storage(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'MetricsRedisStorage':
    """Get MetricsRedisStorage using thread-safe session management."""
    services.validate_session()
    return services.metrics_redis_storage


# ==============================================================================
# LEGACY SERVICE DEPENDENCIES (for backward compatibility)
# ==============================================================================
# These functions are kept for backward compatibility during migration.
# New code should use the thread-safe versions above.

def get_legacy_quiz_template_service(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'QuizTemplateService':
    """DEPRECATED: Use get_quiz_template_service instead."""
    return services.quiz_service.template_service

def get_legacy_patient_service(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'PatientService':
    """DEPRECATED: Use get_patient_service instead."""
    return services.patient_service

def get_legacy_auth_service(services: ServiceProvider = Depends(get_thread_safe_service_provider)) -> 'AuthService':
    """DEPRECATED: Use get_auth_service instead."""
    return services.auth_service


# Pagination dependency
from app.schemas.common import PaginationParams
from fastapi import Query
from uuid import UUID


def get_pagination_params(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=200, description="Maximum items to return")
) -> PaginationParams:
    """Get pagination parameters."""
    return PaginationParams(skip=skip, limit=limit)


async def validate_patient_access(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    patient_service: 'PatientService' = Depends(get_patient_service)
) -> Patient:
    """
    Validate user has access to patient and return patient object.
    """
    import logging
    from app.models.user import UserRole
    
    logger = logging.getLogger(__name__)
    
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
        if patient.doctor_id != current_user.id:
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


# Flow-related dependencies (thread-safe)
def get_flow_state_repository(db: Session = Depends(get_thread_safe_db)) -> 'FlowStateRepository':
    """Get flow state repository instance using thread-safe session management."""
    from app.repositories.flow import FlowStateRepository
    return FlowStateRepository(db)


def get_patient_repository(db: Session = Depends(get_thread_safe_db)) -> 'PatientRepository':
    """Get patient repository instance using thread-safe session management."""
    from app.repositories.patient import PatientRepository
    return PatientRepository(db)

# Legacy versions (for backward compatibility)
def get_legacy_flow_state_repository(db: Session = Depends(get_db)) -> 'FlowStateRepository':
    """DEPRECATED: Get flow state repository instance. Use get_flow_state_repository instead."""
    from app.repositories.flow import FlowStateRepository
    return FlowStateRepository(db)

def get_legacy_patient_repository(db: Session = Depends(get_db)) -> 'PatientRepository':
    """DEPRECATED: Get patient repository instance. Use get_patient_repository instead."""
    from app.repositories.patient import PatientRepository
    return PatientRepository(db)


async def get_websocket_manager() -> 'WebSocketManager':
    """Get WebSocket manager instance."""
    from app.services.websocket_manager import WebSocketManager
    return WebSocketManager.get_instance()


def get_flow_management_service(
    flow_repo: 'FlowStateRepository' = Depends(get_flow_state_repository),
    flow_engine: 'FlowEngineIntegrationService' = Depends(get_flow_service)
) -> 'FlowManagementService':
    """Get flow management service instance."""
    from app.services.flow_management import FlowManagementService
    return FlowManagementService(flow_repo, flow_engine)


async def get_validated_patient(
    patient_id: UUID,
    patient_repo: 'PatientRepository' = Depends(get_patient_repository)
) -> Patient:
    """
    Validate that patient exists and return it.
    """
    from app.exceptions import patient_not_found_exception
    
    patient = patient_repo.get(patient_id)
    if not patient:
        raise patient_not_found_exception(str(patient_id))
    return patient


def verify_patient_access(
    patient_id: UUID = Path(...),
    current_user: User = Depends(get_current_user),
    patient_repo: 'PatientRepository' = Depends(get_patient_repository)
) -> Patient:
    """
    Verify user has access to manage this patient.
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


# Enhanced service dependencies for caching and performance
async def get_cache_service() -> 'CacheService':
    """Get cache service instance."""
    from app.services.cache import CacheService
    return CacheService()


async def verify_monthly_quiz_token(
    token: str,
    services: ServiceProvider = Depends(get_thread_safe_service_provider)
) -> Dict[str, Any]:
    """
    Verify monthly quiz token for public access.
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
    """
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
    """
    Extract request context for audit logging.
    """
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

    return RequestContext(
        ip_address=ip_address,
        user_agent=user_agent,
        user_id=user_id,
        session_id=session_id
    )
