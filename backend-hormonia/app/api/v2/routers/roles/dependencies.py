"""
Roles & Permissions Dependencies
Shared dependencies for roles endpoints including admin authentication.
"""

import logging
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.async_engine import get_async_db
from app.models.user import User
from app.dependencies.auth_dependencies import get_current_user_from_session

logger = logging.getLogger(__name__)


async def get_admin_user(
    current_user: dict = Depends(get_current_user_from_session),
    db: AsyncSession = Depends(get_async_db),
) -> User:
    """
    Dependency to verify admin access using session-based authentication.

    Validates that the current authenticated user has ADMIN role.
    This replaces the insecure placeholder that returned any admin user.

    Args:
        current_user: Current authenticated user from session (dict with role, email, etc.)
        db: Database session

    Returns:
        Admin User object from database

    Raises:
        HTTPException 401: If not authenticated
        HTTPException 403: If user is not an admin or inactive
        HTTPException 404: If user not found in database
    """
    # Verify admin role from session data
    role = current_user.get("role", "").upper()
    if role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )

    # Get full User object from database for operations that need it
    firebase_uid = current_user.get("firebase_uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session data"
        )

    result = await db.execute(
        select(User).where(User.firebase_uid == firebase_uid, User.is_active)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin user not found or inactive",
        )

    return user
