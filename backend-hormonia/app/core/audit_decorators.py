"""
HIPAA Audit Decorators - Phase 3 Sprint 1

Decorators for automatic audit logging of functions and API endpoints:
- @audit_event: Log any function call as an audit event
- @audit_phi_access: Log PHI data access
- @audit_data_modification: Log data changes with before/after states

HIPAA Compliance:
- § 164.312(b) - Audit Controls

Usage:
    from app.core.audit_decorators import audit_event, audit_phi_access

    @audit_event(event_type=AuditEventType.USER_CREATED, event_category="ADMIN")
    async def create_user(user_data: dict):
        # Function implementation
        pass

    @audit_phi_access(resource_type="PATIENT")
    async def get_patient(patient_id: UUID):
        # Function implementation
        return patient
"""

import functools
import inspect
import time
from typing import Callable, Optional

from app.models.audit_log import AuditEventType
from app.services.audit import AuditService, AuditEventContext


def audit_event(
    event_type: AuditEventType,
    event_category: str,
    resource_type: Optional[str] = None,
    extract_resource_id: Optional[str] = None,
    capture_result: bool = False,
):
    """
    Decorator to automatically log audit events for function calls.

    Args:
        event_type: Type of audit event
        event_category: Event category (AUTHENTICATION, PHI_ACCESS, etc.)
        resource_type: Type of resource being accessed (PATIENT, MEDICATION, etc.)
        extract_resource_id: Name of parameter containing resource ID
        capture_result: Whether to capture function result in metadata

    Example:
        @audit_event(
            event_type=AuditEventType.USER_CREATED,
            event_category="ADMIN",
            extract_resource_id="user_id"
        )
        async def create_user(db: AsyncSession, user_id: UUID, user_data: dict):
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            status = "SUCCESS"
            error_message = None
            result = None

            try:
                # Execute function
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "ERROR"
                error_message = str(e)
                raise
            finally:
                # Extract context
                duration_ms = int((time.time() - start_time) * 1000)

                # Try to get database session from args/kwargs
                db = None
                if args and hasattr(
                    args[0], "execute"
                ):  # First arg might be AsyncSession
                    db = args[0]
                elif "db" in kwargs:
                    db = kwargs["db"]

                # Extract resource ID if specified
                resource_id = None
                if extract_resource_id:
                    if extract_resource_id in kwargs:
                        resource_id = kwargs[extract_resource_id]
                    else:
                        # Try to find in args using parameter names
                        sig = inspect.signature(func)
                        param_names = list(sig.parameters.keys())
                        for i, param_name in enumerate(param_names):
                            if param_name == extract_resource_id and i < len(args):
                                resource_id = args[i]
                                break

                # Build metadata
                metadata = {
                    "function": func.__name__,
                    "module": func.__module__,
                }

                if capture_result and result is not None:
                    metadata["result"] = str(result)

                # Build context
                context = AuditEventContext(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    status=status,
                    error_message=error_message,
                    duration_ms=duration_ms,
                    description=f"Function call: {func.__name__}",
                    metadata=metadata,
                )

                # Log event if we have a database session
                if db:
                    try:
                        audit_service = AuditService(db)
                        await audit_service.log_event(
                            event_type=event_type,
                            event_category=event_category,
                            context=context,
                        )
                    except Exception as audit_error:
                        # Don't fail the function if audit logging fails
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.error(
                            "Audit logging failed in decorator",
                            extra={
                                "error": str(audit_error),
                                "function": func.__name__,
                                "event_type": event_type.value
                                if hasattr(event_type, "value")
                                else str(event_type),
                                "event_category": event_category,
                            },
                        )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we can't easily log async
            # Consider using a background task queue
            return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def audit_phi_access(
    resource_type: str,
    extract_resource_id: str = "id",
    event_type: Optional[AuditEventType] = None,
):
    """
    Decorator to automatically log PHI data access.

    Args:
        resource_type: Type of PHI resource (PATIENT, MEDICATION, etc.)
        extract_resource_id: Parameter name containing resource ID
        event_type: Specific event type (auto-detected if not provided)

    Example:
        @audit_phi_access(resource_type="PATIENT", extract_resource_id="patient_id")
        async def get_patient(db: AsyncSession, patient_id: UUID):
            return await db.get(Patient, patient_id)
    """
    # Auto-detect event type based on resource type (placeholder)
    if not event_type:
        event_type = AuditEventType.SUSPICIOUS_ACTIVITY  # Will be enhanced in Sprint 2

    return audit_event(
        event_type=event_type,
        event_category="PHI_ACCESS",
        resource_type=resource_type,
        extract_resource_id=extract_resource_id,
    )


def audit_data_modification(
    resource_type: str,
    operation: str,  # CREATE, UPDATE, DELETE
    extract_resource_id: str = "id",
    extract_before_state: Optional[str] = None,
    extract_after_state: Optional[str] = None,
    event_type: Optional[AuditEventType] = None,
):
    """
    Decorator to automatically log data modifications with before/after states.

    Args:
        resource_type: Type of resource being modified
        operation: Type of operation (CREATE, UPDATE, DELETE)
        extract_resource_id: Parameter name containing resource ID
        extract_before_state: Parameter name containing before state
        extract_after_state: Parameter name containing after state
        event_type: Specific event type (auto-detected if not provided)

    Example:
        @audit_data_modification(
            resource_type="PATIENT",
            operation="UPDATE",
            extract_resource_id="patient_id",
            extract_before_state="original_patient",
            extract_after_state="updated_patient"
        )
        async def update_patient(
            db: AsyncSession,
            patient_id: UUID,
            original_patient: dict,
            updated_patient: dict
        ):
            pass
    """
    # Auto-detect event type based on operation (placeholder)
    if not event_type:
        event_type = AuditEventType.SUSPICIOUS_ACTIVITY  # Will be enhanced in Sprint 2

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            status = "SUCCESS"
            error_message = None
            result = None

            try:
                # Execute function
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "ERROR"
                error_message = str(e)
                raise
            finally:
                # Extract context
                duration_ms = int((time.time() - start_time) * 1000)

                # Try to get database session
                db = None
                if args and hasattr(args[0], "execute"):
                    db = args[0]
                elif "db" in kwargs:
                    db = kwargs["db"]

                # Extract resource ID
                resource_id = None
                if extract_resource_id in kwargs:
                    resource_id = kwargs[extract_resource_id]

                # Extract before/after states
                changes_before = None
                changes_after = None

                if extract_before_state and extract_before_state in kwargs:
                    changes_before = kwargs[extract_before_state]
                    if hasattr(changes_before, "__dict__"):
                        changes_before = changes_before.__dict__

                if extract_after_state and extract_after_state in kwargs:
                    changes_after = kwargs[extract_after_state]
                    if hasattr(changes_after, "__dict__"):
                        changes_after = changes_after.__dict__

                # Build context
                context = AuditEventContext(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    operation=operation,
                    changes_before=changes_before,
                    changes_after=changes_after,
                    status=status,
                    error_message=error_message,
                    duration_ms=duration_ms,
                    description=f"{operation} {resource_type}: {func.__name__}",
                    metadata={
                        "function": func.__name__,
                        "module": func.__module__,
                    },
                )

                # Log event
                if db:
                    try:
                        audit_service = AuditService(db)
                        await audit_service.log_event(
                            event_type=event_type,
                            event_category="DATA_MODIFICATION",
                            context=context,
                        )
                    except Exception as audit_error:
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.error(
                            "Audit logging failed in data modification decorator",
                            extra={
                                "error": str(audit_error),
                                "function": func.__name__,
                                "resource_type": resource_type,
                                "operation": operation,
                            },
                        )

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return func  # Sync functions not supported yet

    return decorator


# Convenience decorators for common operations
def audit_create(resource_type: str, **kwargs):
    """Convenience decorator for CREATE operations."""
    return audit_data_modification(
        resource_type=resource_type, operation="CREATE", **kwargs
    )


def audit_update(resource_type: str, **kwargs):
    """Convenience decorator for UPDATE operations."""
    return audit_data_modification(
        resource_type=resource_type, operation="UPDATE", **kwargs
    )


def audit_delete(resource_type: str, **kwargs):
    """Convenience decorator for DELETE operations."""
    return audit_data_modification(
        resource_type=resource_type, operation="DELETE", **kwargs
    )
