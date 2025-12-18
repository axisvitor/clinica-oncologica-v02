"""
Roles & Permissions Validators
Validation logic for role assignments and permissions.
"""

import logging
from typing import List, Dict
from app.models.user import UserRole
from app.dependencies.auth_dependencies import get_permissions_for_role

logger = logging.getLogger(__name__)


def get_role_permissions(role: UserRole) -> List[str]:
    """
    Get permissions for a role.

    Args:
        role: UserRole enum value

    Returns:
        List of permission strings
    """
    role_str = role.value if hasattr(role, "value") else str(role)
    return get_permissions_for_role(role_str)


def get_role_description(role: UserRole) -> str:
    """
    Get description for a role.

    Args:
        role: UserRole enum value

    Returns:
        Human-readable role description
    """
    descriptions = {
        UserRole.ADMIN: "Full system access with user management capabilities",
        UserRole.DOCTOR: "Medical professional with patient management access",
    }
    return descriptions.get(role, "No description available")


def group_permissions(permissions: List[str]) -> Dict[str, List[str]]:
    """
    Group permissions by category.

    Args:
        permissions: List of permission strings (e.g., "users.read", "patients.write")

    Returns:
        Dictionary with permissions grouped by category
    """
    groups: Dict[str, List[str]] = {}

    for perm in permissions:
        # Extract category from permission (e.g., "users.read" -> "users")
        parts = perm.split(".")
        category = parts[0] if parts else "general"

        if category not in groups:
            groups[category] = []
        groups[category].append(perm)

    return groups
