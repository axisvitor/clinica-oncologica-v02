"""
API v2 Utilities Package.

Provides shared utilities for API v2 routers including:
- auth_helpers: User context extraction, admin checks, UUID utilities
"""

from app.api.v2.utils.auth_helpers import (
    extract_user_context,
    is_admin,
    ensure_uuid,
)

__all__ = [
    "extract_user_context",
    "is_admin",
    "ensure_uuid",
]
