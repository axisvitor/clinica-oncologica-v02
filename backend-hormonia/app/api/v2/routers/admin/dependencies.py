"""
Admin dependencies module.

Contains authentication and authorization dependencies for admin operations.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

from app.models.user import User, UserRole
from app.dependencies import get_request_context, RequestContext
from app.dependencies.auth_dependencies import get_current_user


# HTTPBearer instance for admin authentication
_admin_bearer = HTTPBearer(auto_error=False)


async def get_admin_user(
    current_user: User = Depends(get_current_user),
    context: RequestContext = Depends(get_request_context),
) -> User:
    """
    Dependency to verify admin access.

    Raises:
        HTTPException: If user is not authenticated or not an admin

    Returns:
        User: The authenticated admin user
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user


def _require_admin(current_user: User) -> None:
    """
    Ensure user is admin, raise 403 otherwise.

    Args:
        current_user: The current user object

    Raises:
        HTTPException: If user is not an admin
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
