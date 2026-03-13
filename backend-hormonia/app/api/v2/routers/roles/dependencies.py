"""
Roles & Permissions Dependencies
Shared dependencies for roles endpoints including admin authentication.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.async_engine import get_async_db
from app.dependencies import auth_role_dependencies
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.models.user import User


async def get_admin_user(
    current_user: dict = Depends(get_current_user_from_session),
    db: AsyncSession = Depends(get_async_db),
) -> User:
    """Verify admin access using session-based authentication."""
    return await auth_role_dependencies.get_active_admin_user_from_session(
        current_user=current_user,
        db=db,
    )
