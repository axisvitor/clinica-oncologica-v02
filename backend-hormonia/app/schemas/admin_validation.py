"""Shared validators for admin user schemas."""

from typing import Optional

ALLOWED_ADMIN_ROLES = ("admin", "doctor")


def validate_admin_role(
    role: Optional[str], *, allow_none: bool = False, normalize: bool = False
) -> Optional[str]:
    """Validate admin role values with optional normalization."""
    if role is None:
        if allow_none:
            return None
        raise ValueError(f"Role must be one of {list(ALLOWED_ADMIN_ROLES)}")

    candidate = role.lower() if normalize else role
    if candidate not in ALLOWED_ADMIN_ROLES:
        raise ValueError(f"Role must be one of {list(ALLOWED_ADMIN_ROLES)}")
    return candidate


def validate_password_strength(password: str) -> str:
    """Validate minimum password complexity used in admin APIs."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not any(char.isupper() for char in password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(char.islower() for char in password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not any(char.isdigit() for char in password):
        raise ValueError("Password must contain at least one digit")
    return password
