"""Dependencies package for FastAPI dependency injection."""

from .auth_dependencies import (
    get_current_user,
    get_current_active_user,
    get_optional_user,
    get_admin_user,
    get_doctor_user,
    get_current_user_websocket,
)

from .business_dependencies import (
    get_pagination_params,
    validate_patient_access,
    get_validated_patient,
    verify_patient_access,
    verify_monthly_quiz_token,
    get_request_context,
    RequestContext,
)

from .service_dependencies import (
    get_patient_service,
    get_patient_repository,
    get_flow_service,
    get_flow_state_repository,
    get_flow_analytics_service,
    get_quiz_service,
    get_quiz_template_service,
    get_quiz_response_service,
    get_quiz_session_service,
    get_quiz_analytics_service,
    get_auth_service,
    get_flow_management_service,
    get_redis,
    get_database,
    # get_supabase_client - REMOVED (migrated to AWS RDS PostgreSQL)
    get_message_service,
    get_analytics_service,
    get_report_service,
    get_notification_service,
    get_file_service,
    get_monthly_quiz_service,
    get_metrics_collector_service,
    get_metrics_redis_storage,
    get_cache_service,
    get_websocket_manager,
)

# Import get_db directly from database module
from app.database import get_db

# Import from database for backward compatibility
from app.database import get_db as get_thread_safe_db

# Thread-safe service provider implementation
# Moved from app/dependencies.py to avoid package/module shadowing conflict
from typing import Generator
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

from app.exceptions import HormoniaException


def get_thread_safe_service_provider() -> Generator:
    """
    Get thread-safe ServiceProvider instance using the new session management.

    This dependency provides request-scoped ServiceProvider instances
    with their own database sessions, ensuring thread safety.

    Yields:
        ServiceProvider: Thread-safe service provider for this request
    """
    provider = None
    try:
        # Lazy imports to avoid circular dependencies
        from app.services import ServiceProvider  # noqa: F401 - imported for type context
        from app.core.session_manager import get_request_factory

        logger.debug("Starting thread-safe service provider creation")

        # Validate session manager is initialized
        try:
            request_factory = get_request_factory()
        except RuntimeError as factory_error:
            logger.error(f"Request factory not initialized: {factory_error}")
            raise HTTPException(
                status_code=500, detail="Session management system not initialized"
            ) from factory_error

        get_provider = request_factory.create_service_provider_dependency()

        # Yield from the factory dependency with enhanced error handling
        for provider in get_provider():
            logger.debug(
                f"Yielding ServiceProvider: {hex(id(provider))} with session: {hex(id(provider.db))}"
            )

            # Validate session before yielding
            try:
                provider.validate_session()
                logger.debug(
                    f"ServiceProvider session validation passed for provider: {hex(id(provider))}"
                )
            except RuntimeError as validation_error:
                logger.error(
                    f"ServiceProvider session validation failed: {validation_error}"
                )
                raise HTTPException(
                    status_code=500,
                    detail="Database session validation failed - check database connectivity",
                ) from validation_error

            yield provider

        logger.debug("Thread-safe service provider context ended")

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except HormoniaException:
        # Allow domain exceptions to bubble up so route handlers can translate appropriately
        raise
    except ImportError as import_error:
        logger.error(f"Import error in service provider creation: {import_error}")
        raise HTTPException(
            status_code=500, detail="Service provider dependencies not available"
        ) from import_error
    except ConnectionError as conn_error:
        logger.error(f"Database connection error in service provider: {conn_error}")
        raise HTTPException(
            status_code=500, detail="Database connection failed"
        ) from conn_error
    except Exception as e:
        logger.error(f"Unexpected error in get_thread_safe_service_provider: {e}")
        logger.error(f"Error type: {type(e).__name__}")

        if provider:
            try:
                logger.error(
                    f"Provider state - ID: {hex(id(provider))}, Session active: {provider.is_session_active}"
                )
            except Exception as state_error:
                logger.error(f"Could not get provider state: {state_error}")

        raise HTTPException(
            status_code=500,
            detail=f"Service provider initialization failed: {type(e).__name__}",
        ) from e


__all__ = [
    # Auth dependencies
    "get_current_user",
    "get_current_active_user",
    "get_optional_user",
    "get_admin_user",
    "get_doctor_user",
    "get_current_user_websocket",
    # Business dependencies
    "get_pagination_params",
    "validate_patient_access",
    "get_validated_patient",
    "verify_patient_access",
    "verify_monthly_quiz_token",
    "get_request_context",
    "RequestContext",
    # Service dependencies
    "get_patient_service",
    "get_patient_repository",
    "get_flow_service",
    "get_flow_state_repository",
    "get_quiz_service",
    "get_quiz_template_service",
    "get_quiz_response_service",
    "get_quiz_session_service",
    "get_quiz_analytics_service",
    "get_auth_service",
    "get_flow_management_service",
    "get_redis",
    "get_database",
    # "get_supabase_client", - REMOVED (migrated to AWS RDS PostgreSQL)
    "get_thread_safe_db",
    "get_thread_safe_service_provider",
    "get_message_service",
    "get_analytics_service",
    "get_report_service",
    "get_notification_service",
    "get_file_service",
    "get_monthly_quiz_service",
    "get_metrics_collector_service",
    "get_metrics_redis_storage",
    "get_cache_service",
    "get_websocket_manager",
    # Database dependencies
    "get_db",
    "get_flow_analytics_service",
]
