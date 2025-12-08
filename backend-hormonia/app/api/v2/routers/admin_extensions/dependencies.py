"""
Admin Extensions Dependencies
Shared dependencies and helper functions for admin extension endpoints.
"""

import logging
from typing import Dict, Any, Optional, Union

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.services.audit import AuditService
from app.dependencies import get_request_context, RequestContext
from app.dependencies.auth_dependencies import get_current_active_admin

logger = logging.getLogger(__name__)


async def get_admin_user(
    admin_data: Dict[str, Any] = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
) -> Union[User, Dict[str, Any]]:
    """
    Dependency to verify admin access using session-based authentication.

    Admin Extensions endpoints are HIGHLY SENSITIVE and require admin privileges.

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
    # Try to get full User model from DB for operations that need it
    user_id = admin_data.get("id")
    if user_id:
        admin = db.query(User).filter(User.id == user_id).first()
        if admin:
            return admin

    # Fallback: return session data as dict (still authenticated admin)
    return admin_data


async def log_admin_extension_action(
    audit_service: AuditService,
    action: str,
    admin_user: Union[User, Dict[str, Any]],
    context: RequestContext,
    additional_data: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log admin extension actions for audit trail.

    Args:
        audit_service: AuditService instance
        action: Action name (e.g., 'dlq_retry', 'audit_export')
        admin_user: Admin user performing action
        context: Request context
        additional_data: Additional data to log
    """
    try:
        # Handle both User model and dict from session
        if isinstance(admin_user, dict):
            user_id = admin_user.get("id")
            user_email = admin_user.get("email", "unknown")
        else:
            user_id = admin_user.id
            user_email = admin_user.email

        event_data = {
            "action": action,
            "admin_user_id": str(user_id) if user_id else "unknown",
            "admin_user_email": user_email,
            **(additional_data or {})
        }

        audit_service.log_event(
            event_type=f"admin_extension_{action}",
            event_category="admin_extensions",
            severity="info",
            user_id=user_id,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            event_data=event_data,
            result="success"
        )
    except Exception as e:
        logger.error(f"Failed to log admin extension action {action}: {e}")
