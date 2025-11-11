"""
Compatibility layer for patient-related utilities.

The full patient CRUD endpoints were migrated to ``patients_crud.py``, but
other modules (appointments, medications) still import ``_get_current_user_simple``
from ``app.api.v2.patients``. This module re-exports the router and keeps the
helper available to avoid breaking those dependencies.
"""

from typing import Optional, Dict, Any
from uuid import UUID
import logging

from fastapi import (
    APIRouter,
    Cookie,
    Header,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.api.v2.patients_crud import router as patients_router
from app.database import get_db
from app.dependencies.auth_dependencies import get_redis_cache
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

# Re-export router so legacy imports keep working
router = patients_router


async def _get_current_user_simple(
    session_id: Optional[str] = Cookie(None, alias="session_id"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    db: Session = Depends(get_db),
    redis_cache=Depends(get_redis_cache),
) -> Dict[str, Any]:
    """
    Minimal session validation helper used by other endpoints.

    Returns a dict with user information or raises HTTP 401/403 accordingly.
    """
    final_session_id = session_id or x_session_id
    if not final_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID not provided",
        )

    session_data = await redis_cache.get_session(final_session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    firebase_uid = session_data.get("firebase_uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session data",
        )

    user_data = await redis_cache.get_user_by_uid(firebase_uid)
    if not user_data:
        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        user_data = {
            "id": str(user.id),
            "firebase_uid": user.firebase_uid,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if isinstance(user.role, UserRole) else str(user.role),
            "is_active": user.is_active,
        }
        await redis_cache.cache_user_data(firebase_uid, user_data, ttl=900)

    if not user_data.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user_data


__all__ = ["router", "_get_current_user_simple"]
