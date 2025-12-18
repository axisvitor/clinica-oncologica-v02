"""
Common utilities and dependencies for debug endpoints.

Shared functions:
- Authentication/authorization
- Audit logging
- Security checks
- Data sanitization
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any
from uuid import uuid4

from fastapi import Depends, HTTPException, status, Request
from typing import Union

from app.database import get_db
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.v2.debug import DebugSeverity
from app.dependencies.auth_dependencies import get_current_active_admin

logger = logging.getLogger(__name__)

# Environment flag - MUST be explicitly enabled
DEBUG_ENDPOINTS_ENABLED = os.getenv("ENABLE_DEBUG_ENDPOINTS", "false").lower() == "true"

# Safe environment variables (whitelist only)
SAFE_ENV_VARS = {
    "ENVIRONMENT",
    "DEBUG",
    "PYTHON_VERSION",
    "PYTHONPATH",
    "TZ",
    "LANG",
    "LC_ALL",
    "PORT",
    "HOST",
    # Database (masked values)
    "DATABASE_URL",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    # Redis (masked values)
    "REDIS_URL",
    "REDIS_HOST",
    "REDIS_PORT",
    # App config
    "API_VERSION",
    "APP_NAME",
    "LOG_LEVEL",
}

# Sensitive claims to mask in tokens
SENSITIVE_CLAIMS = {"password", "secret", "token", "key", "private"}


# ============================================================================
# Helper Functions
# ============================================================================


def check_debug_enabled():
    """Check if debug endpoints are enabled, raise 404 if not."""
    if not DEBUG_ENDPOINTS_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def get_admin_user(
    admin_data: Dict[str, Any] = Depends(get_current_active_admin), db=Depends(get_db)
) -> Union[User, Dict[str, Any]]:
    """
    Verify ADMIN-ONLY access using session-based authentication.

    Uses the secure get_current_active_admin dependency which:
    1. Validates session from Redis cache (~2-5ms)
    2. Verifies user is active
    3. Confirms ADMIN role

    Returns:
        User model if found in DB, otherwise the admin dict from session

    Raises:
        HTTPException 401: If not authenticated
        HTTPException 403: If not admin
    """
    # admin_data is already validated by get_current_active_admin
    # Try to get full User model from DB for audit logging
    user_id = admin_data.get("id")
    if user_id:
        admin = db.query(User).filter(User.id == user_id).first()
        if admin:
            return admin

    # Fallback: return session data as dict (still authenticated admin)
    return admin_data


async def log_debug_operation(
    db,
    admin_user: Union[User, Dict[str, Any]],
    endpoint: str,
    parameters: Dict[str, Any],
    result_summary: str,
    request: Request,
    severity: DebugSeverity = DebugSeverity.INFO,
):
    """
    Log debug operation to audit trail.

    Args:
        db: Database session
        admin_user: Admin user performing operation (User model or dict)
        endpoint: Debug endpoint called
        parameters: Operation parameters (sanitized)
        result_summary: Brief result summary (sanitized)
        request: FastAPI request object
        severity: Operation severity level
    """
    try:
        # Handle both User model and dict from session
        if isinstance(admin_user, dict):
            user_id = admin_user.get("id")
            user_email = admin_user.get("email", "unknown")
        else:
            user_id = admin_user.id
            user_email = admin_user.email

        audit_log = AuditLog(
            id=uuid4(),
            user_id=user_id,
            action=f"debug:{endpoint}",
            resource_type="debug",
            resource_id=None,
            changes={
                "endpoint": endpoint,
                "parameters": parameters,
                "result": result_summary,
                "severity": severity.value,
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            created_at=datetime.utcnow(),
        )
        db.add(audit_log)
        db.commit()
        logger.info(
            f"Debug operation logged: {endpoint} by {user_email} "
            f"(severity: {severity.value})"
        )
    except Exception as e:
        logger.error(f"Failed to log debug operation: {e}")
        # Don't fail the request if audit logging fails


def mask_sensitive_value(key: str, value: str) -> tuple[str, bool]:
    """
    Mask sensitive environment variables.

    Args:
        key: Environment variable key
        value: Environment variable value

    Returns:
        Tuple of (masked_value, is_masked)
    """
    sensitive_keywords = {
        "password",
        "secret",
        "key",
        "token",
        "credential",
        "private",
        "api_key",
        "auth",
        "jwt",
    }

    key_lower = key.lower()
    is_sensitive = any(kw in key_lower for kw in sensitive_keywords)

    if is_sensitive:
        # Show format but mask actual value
        if "://" in value:
            # URL format: show scheme and host, mask credentials
            parts = value.split("://", 1)
            if len(parts) == 2:
                scheme, rest = parts
                if "@" in rest:
                    # Has credentials
                    return f"{scheme}://***:***@{rest.split('@')[-1]}", True
                return f"{scheme}://***", True
        # Generic masking
        if len(value) > 8:
            return f"{value[:3]}***{value[-3:]}", True
        return "***", True

    return value, False


def sanitize_sql_query(query: str, max_length: int = 100) -> str:
    """
    Sanitize SQL query for safe logging.

    Args:
        query: SQL query string
        max_length: Maximum length to display

    Returns:
        Sanitized query string
    """
    # Truncate long queries
    if len(query) > max_length:
        return query[:max_length] + "..."
    return query
