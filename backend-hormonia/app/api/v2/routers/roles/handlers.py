"""
Roles & Permissions Handlers
Business logic for role management operations.
"""

import logging
from datetime import datetime
from typing import Optional
from fastapi import Request
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.audit import AuditService
from app.middleware.admin_permissions import get_client_info

logger = logging.getLogger(__name__)


async def log_role_change(
    db: Session,
    admin_user: User,
    target_user: User,
    old_role: str,
    new_role: str,
    reason: Optional[str],
    request: Request
) -> None:
    """
    Log role change to audit trail.

    Args:
        db: Database session
        admin_user: User making the change
        target_user: User whose role is being changed
        old_role: Previous role
        new_role: New role
        reason: Optional reason for the change
        request: FastAPI request object for client info
    """
    try:
        audit_service = AuditService(db)
        client_info = get_client_info(request)

        event_data = {
            "action": "role_assignment",
            "admin_user_id": str(admin_user.id),
            "admin_email": admin_user.email,
            "target_user_id": str(target_user.id),
            "target_email": target_user.email,
            "old_role": old_role,
            "new_role": new_role,
            "reason": reason,
            **client_info
        }

        audit_service.log_event(
            event_type="role_assignment",
            event_category="security",
            severity="info",
            user_id=admin_user.id,
            metadata=event_data
        )
    except Exception as e:
        logger.error(f"Failed to log role change: {e}")
