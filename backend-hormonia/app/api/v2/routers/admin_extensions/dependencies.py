"""
Admin Extensions Dependencies
Shared dependencies and helper functions for admin extension endpoints.
"""

import logging
from typing import Dict, Any, Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.services.audit import AuditService
from app.dependencies import get_request_context, RequestContext

logger = logging.getLogger(__name__)


async def get_admin_user(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context)
) -> User:
    """
    Dependency to verify admin access.

    Admin Extensions endpoints are HIGHLY SENSITIVE and require admin privileges.

    TODO: Integrate with actual authentication system.
    For now, this is a placeholder that should be replaced.

    Raises:
        HTTPException: If user is not authenticated or not an admin
    """
    # TODO: Get user from session/token
    # This is a placeholder - integrate with your auth system
    user = db.query(User).filter(
        User.role == UserRole.ADMIN,
        User.is_active == True
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for Admin Extensions"
        )

    return user


async def log_admin_extension_action(
    audit_service: AuditService,
    action: str,
    admin_user: User,
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
        event_data = {
            "action": action,
            "admin_user_id": str(admin_user.id),
            "admin_user_email": admin_user.email,
            **(additional_data or {})
        }

        audit_service.log_event(
            event_type=f"admin_extension_{action}",
            event_category="admin_extensions",
            severity="info",
            user_id=admin_user.id,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            event_data=event_data,
            result="success"
        )
    except Exception as e:
        logger.error(f"Failed to log admin extension action {action}: {e}")
