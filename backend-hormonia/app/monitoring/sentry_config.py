"""
Sentry configuration for FastAPI backend monitoring.

Provides comprehensive error tracking, performance monitoring, and custom context
for the Clínica Oncológica backend system.
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.httpx import HttpxIntegration
from fastapi import Request
from sqlalchemy.orm import Session

# Environment configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
SENTRY_DSN = os.getenv("SENTRY_DSN")
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
SENTRY_PROFILES_SAMPLE_RATE = float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1"))


class SentryConfig:
    """Centralized Sentry configuration and utilities."""

    @staticmethod
    def init_sentry() -> None:
        """Initialize Sentry SDK with comprehensive monitoring configuration."""
        if not SENTRY_DSN:
            logging.warning("Sentry DSN not configured. Monitoring disabled.")
            return

        # Configure logging integration
        logging_integration = LoggingIntegration(
            level=logging.INFO,  # Capture info and above as breadcrumbs
            event_level=logging.ERROR,  # Send errors as events
        )

        # Initialize Sentry with all integrations
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=ENVIRONMENT,
            traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
            profiles_sample_rate=SENTRY_PROFILES_SAMPLE_RATE,
            # Integrations for comprehensive monitoring
            integrations=[
                FastApiIntegration(
                    auto_enabling_integrations=True,
                    transaction_style="endpoint",
                    failed_request_status_codes=[
                        400,
                        401,
                        403,
                        404,
                        405,
                        500,
                        502,
                        503,
                    ],
                ),
                SqlalchemyIntegration(),
                RedisIntegration(),
                HttpxIntegration(),
                logging_integration,
            ],
            # Performance and error configuration
            send_default_pii=False,  # Don't send PII automatically
            attach_stacktrace=True,
            debug=ENVIRONMENT == "development",
            # Custom error filtering
            before_send=SentryConfig._before_send_filter,
            before_send_transaction=SentryConfig._before_send_transaction_filter,
            # Release tracking
            release=os.getenv("APP_VERSION", "unknown"),
            # Additional options
            max_breadcrumbs=50,
            shutdown_timeout=2,
        )

        logging.info(f"Sentry initialized for environment: {ENVIRONMENT}")

    @staticmethod
    def _before_send_filter(
        event: Dict[str, Any], hint: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Filter and modify events before sending to Sentry."""

        # Skip health check errors
        if "request" in event.get("contexts", {}):
            url = event["contexts"]["request"].get("url", "")
            if any(path in url for path in ["/health", "/metrics", "/favicon.ico"]):
                return None

        # Skip certain exception types in development
        if ENVIRONMENT == "development":
            exception_type = (
                event.get("exception", {}).get("values", [{}])[-1].get("type", "")
            )
            if exception_type in ["KeyboardInterrupt", "ConnectionError"]:
                return None

        # Add custom tags
        event.setdefault("tags", {}).update(
            {"component": "backend-api", "service": "clinica-oncologica"}
        )

        return event

    @staticmethod
    def _before_send_transaction_filter(
        event: Dict[str, Any], hint: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Filter performance transactions before sending."""

        # Skip health check transactions
        transaction_name = event.get("transaction", "")
        if any(path in transaction_name for path in ["/health", "/metrics"]):
            return None

        # Only send slow transactions in production
        if ENVIRONMENT == "production":
            duration = event.get("timestamp", 0) - event.get("start_timestamp", 0)
            if duration < 1.0:  # Skip transactions under 1 second
                return None

        return event

    @staticmethod
    def set_user_context(
        user_id: str, email: Optional[str] = None, role: Optional[str] = None
    ) -> None:
        """Set user context for error tracking."""
        sentry_sdk.set_user(
            {
                "id": user_id,
                "email": email,
                "role": role,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    @staticmethod
    def set_request_context(request: Request, user_id: Optional[str] = None) -> None:
        """Set request context with sanitized data."""
        with sentry_sdk.configure_scope() as scope:
            # Request information
            scope.set_tag("endpoint", f"{request.method} {request.url.path}")
            scope.set_tag("user_agent", request.headers.get("user-agent", ""))
            scope.set_tag(
                "ip_address", request.client.host if request.client else "unknown"
            )

            # User context if available
            if user_id:
                scope.set_tag("user_id", user_id)

            # Custom context
            scope.set_context(
                "request_details",
                {
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": dict(request.query_params),
                    "headers": {
                        key: value
                        for key, value in request.headers.items()
                        if key.lower() not in ["authorization", "cookie", "x-api-key"]
                    },
                },
            )

    @staticmethod
    def set_database_context(db_session: Session, operation: str) -> None:
        """Set database operation context."""
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("db_operation", operation)
            scope.set_context(
                "database",
                {
                    "operation": operation,
                    "session_info": {
                        "is_active": db_session.is_active,
                        "dirty": len(db_session.dirty),
                        "new": len(db_session.new),
                        "deleted": len(db_session.deleted),
                    },
                },
            )

    @staticmethod
    def capture_business_event(event_name: str, data: Dict[str, Any]) -> None:
        """Capture custom business events for analytics."""
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("event_type", "business_event")
            scope.set_tag("event_name", event_name)

            # Add breadcrumb for business events
            sentry_sdk.add_breadcrumb(
                message=f"Business Event: {event_name}",
                category="business",
                level="info",
                data=data,
            )


class SentryMiddleware:
    """FastAPI middleware for automatic Sentry context setup."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Extract request information
            request = Request(scope, receive)

            # Set request context
            SentryConfig.set_request_context(request)

            # Add transaction name
            sentry_sdk.set_tag(
                "transaction_name", f"{request.method} {request.url.path}"
            )

        await self.app(scope, receive, send)


# Utility functions for common monitoring scenarios
def monitor_quiz_session(session_id: str, user_id: str, quiz_type: str) -> None:
    """Monitor quiz session activities."""
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("quiz_session", session_id)
        scope.set_tag("quiz_type", quiz_type)
        scope.set_context(
            "quiz_context",
            {
                "session_id": session_id,
                "user_id": user_id,
                "quiz_type": quiz_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )


def monitor_patient_interaction(
    patient_id: str, interaction_type: str, metadata: Dict[str, Any] = None
) -> None:
    """Monitor patient-related interactions."""
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("patient_interaction", interaction_type)
        scope.set_context(
            "patient_context",
            {
                "patient_id": patient_id,
                "interaction_type": interaction_type,
                "metadata": metadata or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )


def monitor_clinical_data_access(
    data_type: str, access_level: str, user_role: str
) -> None:
    """Monitor access to clinical data."""
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("data_access", data_type)
        scope.set_tag("access_level", access_level)
        scope.set_tag("user_role", user_role)

        sentry_sdk.add_breadcrumb(
            message=f"Clinical data access: {data_type}",
            category="data_access",
            level="info",
            data={
                "data_type": data_type,
                "access_level": access_level,
                "user_role": user_role,
            },
        )


# Performance monitoring decorators
def monitor_performance(operation_name: str):
    """Decorator to monitor function performance."""

    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            with sentry_sdk.start_transaction(
                op="function", name=f"{operation_name}:{func.__name__}"
            ):
                return await func(*args, **kwargs)

        def sync_wrapper(*args, **kwargs):
            with sentry_sdk.start_transaction(
                op="function", name=f"{operation_name}:{func.__name__}"
            ):
                return func(*args, **kwargs)

        return async_wrapper if hasattr(func, "__await__") else sync_wrapper

    return decorator


# Error capturing utilities
def capture_api_error(error: Exception, context: Dict[str, Any] = None) -> str:
    """Capture API errors with additional context."""
    with sentry_sdk.configure_scope() as scope:
        if context:
            scope.set_context("error_context", context)

        scope.set_tag("error_type", "api_error")

        return sentry_sdk.capture_exception(error)


def capture_validation_error(field: str, value: Any, error_message: str) -> str:
    """Capture validation errors."""
    return sentry_sdk.capture_message(
        f"Validation error in field '{field}': {error_message}",
        level="warning",
        extras={"field": field, "value": str(value), "error_message": error_message},
    )


# Health check for monitoring
def get_sentry_health() -> Dict[str, Any]:
    """Get Sentry monitoring health status."""
    return {
        "sentry_enabled": bool(SENTRY_DSN),
        "environment": ENVIRONMENT,
        "traces_sample_rate": SENTRY_TRACES_SAMPLE_RATE,
        "profiles_sample_rate": SENTRY_PROFILES_SAMPLE_RATE,
        "sdk_version": sentry_sdk.VERSION,
    }
