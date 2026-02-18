"""
Admin Extensions Dependencies
Shared dependencies and helper functions for admin extension endpoints.
"""

import logging
from typing import Dict, Any, Optional, Union

from app.models.user import User
from app.services.audit import AuditService
from app.utils.request_context import RequestContext
from app.api.v2.routers.admin import dependencies as admin_dependencies

logger = logging.getLogger(__name__)


_is_test_environment = admin_dependencies._is_test_environment
_invoke_dependency = admin_dependencies._invoke_dependency
get_admin_user = admin_dependencies.get_admin_user


async def log_admin_extension_action(
    audit_service: AuditService,
    action: str,
    admin_user: Union[User, Dict[str, Any]],
    context: RequestContext,
    additional_data: Optional[Dict[str, Any]] = None,
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
            **(additional_data or {}),
        }

        audit_service.log_event(
            event_type=f"admin_extension_{action}",
            event_category="admin_extensions",
            severity="info",
            user_id=user_id,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            event_data=event_data,
            result="success",
        )
    except Exception as e:
        logger.error(f"Failed to log admin extension action {action}: {e}")
