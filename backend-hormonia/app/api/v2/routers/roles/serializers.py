"""
Roles & Permissions Serializers
Response formatting and data serialization for roles.
"""

from typing import Dict, Any
from app.models.user import User


def serialize_user_role_info(user: User) -> Dict[str, Any]:
    """
    Serialize user to UserRoleInfo dict.

    Args:
        user: User model instance

    Returns:
        Dictionary with user role information
    """
    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name or "",
        "current_role": user.role.value if hasattr(user.role, 'value') else str(user.role),
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": getattr(user, 'last_login', None),
    }
