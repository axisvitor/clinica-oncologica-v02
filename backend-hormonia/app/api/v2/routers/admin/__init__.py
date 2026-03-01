"""
Admin module for user management and administration.

This module provides a combined router for all admin operations including:
- User CRUD operations (users.py)
- User actions: activate, deactivate, reset password, update role (actions.py)
- User activity logs and audit trails (activity.py)
- Role and permission management
- System statistics

The module is decomposed into:
- users.py: User CRUD operations (list, get, create, update, delete)
- actions.py: User action endpoints (activate, deactivate, reset password, update role)
- activity.py: User activity and audit log endpoints
- dependencies.py: Authentication and authorization dependencies
- utils.py: Helper functions for serialization, validation, and logging
"""

from fastapi import APIRouter

# Import dependencies and utilities for use in other modules
from .dependencies import get_admin_user, _require_admin, _admin_bearer
from .utils import (
    _serialize_user,
    _validate_password_strength,
    _log_admin_action,
    _status_count,
)

# Import sub-routers
from . import users, actions, activity, stats, compensation, roles

# Create the combined router
router = APIRouter()

# Include sub-routers with appropriate tags
router.include_router(stats.router, tags=["admin-stats-v2"])
router.include_router(users.router, tags=["admin-users-v2"])
router.include_router(actions.router, tags=["admin-actions-v2"])
router.include_router(activity.router, tags=["admin-activity-v2"])
router.include_router(compensation.router, tags=["admin-compensation-v2"])
router.include_router(roles.router, tags=["admin-roles-v2"])

__all__ = [
    "router",
    "get_admin_user",
    "_require_admin",
    "_admin_bearer",
    "_serialize_user",
    "_validate_password_strength",
    "_log_admin_action",
    "_status_count",
]
