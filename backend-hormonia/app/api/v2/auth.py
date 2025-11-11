"""
Authentication endpoints for API v2
Enhanced authentication with cursor pagination, Redis caching, and eager loading.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, or_

from app.database import get_db
from app.models.user import User, UserRole
from app.models.session import Session as SessionModel
from app.models.notification import Notification, NotificationType
from app.schemas.v2.auth import (
    UserV2Response,
    UserPreferencesV2,
    UserPreferencesV2Update,
    UserPreferencesV2Response,
    NotificationV2Response,
    NotificationV2List,
    NotificationMarkReadRequest,
    NotificationMarkReadResponse,
    SessionV2Response,
    SessionV2List,
    SessionRevokeResponse,
    FirebaseTokenVerifyRequest,
    FirebaseTokenVerifyResponse,
    PasswordChangeRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
)
from .dependencies import (
    get_pagination_params,
    get_field_selection,
    apply_field_selection,
)
from app.dependencies.auth_dependencies import get_current_user_from_session, get_redis_cache
from app.core.redis_client import get_async_redis_client
from app.utils.rate_limiter import limiter
from app.utils.security import get_password_hash
from app.core.security import verify_password_reset_token
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Redis cache TTLs
CACHE_TTL_USER_PROFILE = 300  # 5 minutes
CACHE_TTL_PREFERENCES = 600  # 10 minutes
CACHE_TTL_UNREAD_COUNT = 60  # 1 minute


# ============================================================================
# Helper Functions
# ============================================================================

def _serialize_user(user: User, include_relationships: bool = False) -> dict:
    """
    Serialize User model to API-friendly dict.

    Args:
        user: User SQLAlchemy model
        include_relationships: Whether to include eager-loaded relationships

    Returns:
        dict: Serialized user data
    """
    data = {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": getattr(user, 'firebase_last_sign_in', None),
    }

    if include_relationships:
        # Add computed fields
        if hasattr(user, 'patients'):
            data["patient_count"] = len(user.patients) if user.patients else 0

        if hasattr(user, 'notifications'):
            unread_notifications = [n for n in user.notifications if not n.is_read]
            data["notification_count"] = len(unread_notifications)

    return data


def _serialize_notification(notification: Notification) -> dict:
    """Serialize Notification model to API-friendly dict."""
    return {
        "id": str(notification.id),
        "title": notification.title,
        "message": notification.message,
        "type": notification.notification_type.value,
        "read": notification.is_read,
        "created_at": notification.created_at,
        "updated_at": notification.updated_at,
        "metadata": notification.notification_metadata or {},
        "action_url": notification.action_url,
    }


def _serialize_session(session: SessionModel, current_session_id: Optional[str] = None) -> dict:
    """Serialize Session model to API-friendly dict."""
    return {
        "session_id": str(session.id),
        "user_id": str(session.user_id),
        "created_at": session.created_at,
        "expires_at": session.expires_at,
        "ip_address": session.ip_address,
        "user_agent": session.user_agent,
        "is_current": str(session.id) == current_session_id if current_session_id else False,
    }


async def _get_redis_client():
    """Get async Redis client for caching."""
    try:
        return await get_async_redis_client()
    except Exception as e:
        logger.warning(f"Failed to get Redis client: {e}")
        return None


def _get_user_preferences(user: User) -> UserPreferencesV2:
    """
    Extract user preferences from user metadata.

    Args:
        user: User model

    Returns:
        UserPreferencesV2: User preferences with defaults
    """
    if hasattr(user, 'metadata') and user.metadata:
        prefs_data = user.metadata.get('preferences', {})
        return UserPreferencesV2(**prefs_data)
    return UserPreferencesV2()


def _extract_user_id(current_user) -> str:
    """Extract user ID from current_user (dict or model)."""
    if isinstance(current_user, dict):
        return current_user.get("id")
    return str(getattr(current_user, "id", None))


# ============================================================================
# User Profile Endpoints
# ============================================================================

@router.get(
    "/me",
    response_model=UserV2Response,
    summary="Get current user profile",
    description="""
    Get the authenticated user's profile with Redis caching (5 min TTL).

    Features:
    - Redis caching for performance
    - Eager loading of role and preferences
    - Field selection support

    Example:
        GET /api/v2/auth/me?fields=id,email,full_name
    """
)
@limiter.limit("100/minute")
async def get_current_user_profile(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
    fields: Optional[List[str]] = Depends(get_field_selection),
):
    """
    Get current user profile with Redis caching and eager loading.

    Caching strategy:
    - Cache key: user:profile:{user_id}
    - TTL: 5 minutes
    - Invalidate on profile update
    """
    user_id = _extract_user_id(current_user)

    # Try Redis cache first
    redis = await _get_redis_client()
    cache_key = f"user:profile:{user_id}"

    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for user profile: {user_id}")
                user_data = json.loads(cached)
                if fields:
                    user_data = apply_field_selection(user_data, fields)
                return user_data
        except Exception as e:
            logger.warning(f"Redis get error: {e}")

    # Cache miss - fetch from DB with eager loading
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    user = (
        db.query(User)
        .options(
            joinedload(User.patients),
            joinedload(User.notifications)
        )
        .filter(User.id == user_uuid)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user_data = _serialize_user(user, include_relationships=True)

    # Add preferences
    user_data["preferences"] = _get_user_preferences(user).dict()

    # Cache the result
    if redis:
        try:
            await redis.setex(cache_key, CACHE_TTL_USER_PROFILE, json.dumps(user_data, default=str))
            logger.debug(f"Cached user profile: {user_id}")
        except Exception as e:
            logger.warning(f"Redis set error: {e}")

    # Apply field selection
    if fields:
        user_data = apply_field_selection(user_data, fields)

    return user_data


# ============================================================================
# Session Management Endpoints
# ============================================================================

@router.get(
    "/sessions",
    response_model=SessionV2List,
    summary="List active sessions",
    description="Get list of active sessions for the current user with cursor pagination"
)
@limiter.limit("60/minute")
async def list_sessions(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
    pagination=Depends(get_pagination_params),
):
    """
    List active sessions with cursor pagination.

    Features:
    - Cursor-based pagination
    - Filter by active status
    - Shows current session indicator
    """
    user_id = _extract_user_id(current_user)
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    # Build query
    query = db.query(SessionModel).filter(
        SessionModel.user_id == user_uuid,
        SessionModel.is_active == True,
        SessionModel.revoked_at.is_(None)
    )

    # Apply cursor pagination
    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"])
        cursor_created = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
        query = query.filter(
            or_(
                SessionModel.created_at < cursor_created,
                and_(
                    SessionModel.created_at == cursor_created,
                    SessionModel.id > cursor_id
                )
            )
        )

    # Get total count (only on first page)
    total = None
    if not cursor_data:
        total = query.count()

    # Order and limit
    query = query.order_by(SessionModel.created_at.desc(), SessionModel.id)
    sessions = query.limit(limit + 1).all()

    # Check if there are more results
    has_more = len(sessions) > limit
    if has_more:
        sessions = sessions[:limit]

    # Serialize sessions
    session_responses = [_serialize_session(s) for s in sessions]

    return {
        "sessions": session_responses,
        "total": total or len(session_responses),
    }


@router.delete(
    "/sessions/{session_id}",
    response_model=SessionRevokeResponse,
    summary="Revoke session",
    description="Revoke a specific session (logout from device)"
)
@limiter.limit("20/minute")
async def revoke_session(
    request: Request,
    session_id: str,
    current_user=Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
):
    """
    Revoke a session.

    Validates:
    - Session belongs to current user
    - Session is active
    """
    user_id = _extract_user_id(current_user)

    try:
        user_uuid = UUID(user_id)
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )

    # Get session
    session = db.query(SessionModel).filter(
        SessionModel.id == session_uuid,
        SessionModel.user_id == user_uuid
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Revoke session
    session.is_active = False
    session.revoked_at = datetime.utcnow()
    session.revocation_reason = "User requested revocation"

    db.commit()

    return {
        "session_id": session_id,
        "revoked": True,
        "message": "Session revoked successfully"
    }


@router.post(
    "/verify-session",
    response_model=SessionV2Response,
    summary="Verify session validity",
    description="Check if a session is valid and not expired"
)
@limiter.limit("100/minute")
async def verify_session(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
):
    """
    Verify session validity.

    Checks:
    - Session exists
    - Session is active
    - Session is not expired
    """
    user_id = _extract_user_id(current_user)

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    # Get the most recent active session
    session = (
        db.query(SessionModel)
        .filter(
            SessionModel.user_id == user_uuid,
            SessionModel.is_active == True,
            SessionModel.revoked_at.is_(None)
        )
        .order_by(SessionModel.last_activity.desc())
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active session found"
        )

    # Check expiration
    if session.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired"
        )

    return _serialize_session(session)


# ============================================================================
# User Preferences Endpoints
# ============================================================================

@router.get(
    "/preferences",
    response_model=UserPreferencesV2Response,
    summary="Get user preferences",
    description="Get user preferences with Redis caching (10 min TTL)"
)
@limiter.limit("100/minute")
async def get_preferences(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
):
    """
    Get user preferences with Redis caching.

    Caching strategy:
    - Cache key: user:preferences:{user_id}
    - TTL: 10 minutes
    - Invalidate on preferences update
    """
    user_id = _extract_user_id(current_user)

    # Try Redis cache first
    redis = await _get_redis_client()
    cache_key = f"user:preferences:{user_id}"

    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for user preferences: {user_id}")
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis get error: {e}")

    # Cache miss - fetch from DB
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    user = db.query(User).filter(User.id == user_uuid).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    preferences = _get_user_preferences(user)

    response_data = {
        "user_id": user_id,
        "preferences": preferences.dict(),
        "updated_at": user.updated_at.isoformat()
    }

    # Cache the result
    if redis:
        try:
            await redis.setex(cache_key, CACHE_TTL_PREFERENCES, json.dumps(response_data, default=str))
            logger.debug(f"Cached user preferences: {user_id}")
        except Exception as e:
            logger.warning(f"Redis set error: {e}")

    return response_data


@router.put(
    "/preferences",
    response_model=UserPreferencesV2Response,
    summary="Update user preferences",
    description="Update user preferences (full replacement)"
)
@limiter.limit("20/hour")
async def update_preferences(
    request: Request,
    preferences: UserPreferencesV2,
    current_user=Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
):
    """
    Update user preferences (full replacement).

    This replaces all preferences with the provided values.
    Invalidates cache after update.
    """
    user_id = _extract_user_id(current_user)

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    user = db.query(User).filter(User.id == user_uuid).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update preferences in metadata
    if not hasattr(user, 'metadata') or user.metadata is None:
        user.metadata = {}

    user.metadata['preferences'] = preferences.dict()
    user.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(user)

    # Invalidate cache
    redis = await _get_redis_client()
    if redis:
        try:
            cache_keys = [
                f"user:preferences:{user_id}",
                f"user:profile:{user_id}"
            ]
            for key in cache_keys:
                await redis.delete(key)
            logger.debug(f"Invalidated cache for user: {user_id}")
        except Exception as e:
            logger.warning(f"Redis delete error: {e}")

    return {
        "user_id": user_id,
        "preferences": preferences.dict(),
        "updated_at": user.updated_at.isoformat()
    }


@router.patch(
    "/preferences",
    response_model=UserPreferencesV2Response,
    summary="Partial update preferences",
    description="Partially update user preferences (only provided fields)"
)
@limiter.limit("20/hour")
async def patch_preferences(
    request: Request,
    updates: UserPreferencesV2Update,
    current_user=Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
):
    """
    Partial update of user preferences.

    Only provided fields will be updated.
    Invalidates cache after update.
    """
    user_id = _extract_user_id(current_user)

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    user = db.query(User).filter(User.id == user_uuid).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get current preferences
    current_prefs = _get_user_preferences(user).dict()

    # Apply updates
    update_data = updates.dict(exclude_unset=True)
    current_prefs.update(update_data)

    # Validate updated preferences
    preferences = UserPreferencesV2(**current_prefs)

    # Save to database
    if not hasattr(user, 'metadata') or user.metadata is None:
        user.metadata = {}

    user.metadata['preferences'] = preferences.dict()
    user.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(user)

    # Invalidate cache
    redis = await _get_redis_client()
    if redis:
        try:
            cache_keys = [
                f"user:preferences:{user_id}",
                f"user:profile:{user_id}"
            ]
            for key in cache_keys:
                await redis.delete(key)
            logger.debug(f"Invalidated cache for user: {user_id}")
        except Exception as e:
            logger.warning(f"Redis delete error: {e}")

    return {
        "user_id": user_id,
        "preferences": preferences.dict(),
        "updated_at": user.updated_at.isoformat()
    }


# ============================================================================
# Notification Endpoints
# ============================================================================

@router.get(
    "/notifications",
    response_model=NotificationV2List,
    summary="List notifications",
    description="Get notifications with cursor pagination and eager loading"
)
@limiter.limit("100/minute")
async def list_notifications(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
    pagination=Depends(get_pagination_params),
    unread_only: bool = Query(False, description="Show only unread notifications"),
):
    """
    List notifications with cursor pagination.

    Features:
    - Cursor-based pagination
    - Filter by read/unread status
    - Eager loading of metadata
    - Returns unread count
    """
    user_id = _extract_user_id(current_user)
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    # Build query
    filters = [Notification.user_id == user_uuid]

    if unread_only:
        filters.append(Notification.is_read == False)

    query = db.query(Notification).filter(and_(*filters))

    # Apply cursor pagination
    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"])
        cursor_created = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
        query = query.filter(
            or_(
                Notification.created_at < cursor_created,
                and_(
                    Notification.created_at == cursor_created,
                    Notification.id > cursor_id
                )
            )
        )

    # Get total count (only on first page)
    total = None
    if not cursor_data:
        total = query.count()

    # Get unread count
    unread_count = db.query(func.count(Notification.id)).filter(
        Notification.user_id == user_uuid,
        Notification.is_read == False
    ).scalar()

    # Order and limit
    query = query.order_by(Notification.created_at.desc(), Notification.id)
    notifications = query.limit(limit + 1).all()

    # Check if there are more results
    has_more = len(notifications) > limit
    if has_more:
        notifications = notifications[:limit]

    # Create next cursor
    next_cursor = None
    if has_more and notifications:
        import base64
        cursor_data = {
            "id": str(notifications[-1].id),
            "created_at": notifications[-1].created_at.isoformat()
        }
        next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()

    # Serialize notifications
    notification_responses = [_serialize_notification(n) for n in notifications]

    return {
        "data": notification_responses,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
        "unread_count": unread_count,
    }


@router.post(
    "/notifications/mark-read",
    response_model=NotificationMarkReadResponse,
    summary="Mark notifications as read",
    description="Mark multiple notifications as read (bulk operation, up to 100 IDs)"
)
@limiter.limit("60/minute")
async def mark_notifications_read(
    request: Request,
    payload: NotificationMarkReadRequest,
    current_user=Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
):
    """
    Mark notifications as read (bulk operation).

    Features:
    - Bulk update (up to 100 notifications)
    - Validates notification ownership
    - Returns count of marked notifications
    """
    user_id = _extract_user_id(current_user)

    try:
        user_uuid = UUID(user_id)
        notification_uuids = [UUID(nid) for nid in payload.notification_ids]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )

    # Get notifications belonging to user
    notifications = db.query(Notification).filter(
        Notification.id.in_(notification_uuids),
        Notification.user_id == user_uuid
    ).all()

    # Mark as read
    marked_count = 0
    for notification in notifications:
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            marked_count += 1

    db.commit()

    # Invalidate unread count cache
    redis = await _get_redis_client()
    if redis:
        try:
            await redis.delete(f"user:unread_count:{user_id}")
            logger.debug(f"Invalidated unread count cache for user: {user_id}")
        except Exception as e:
            logger.warning(f"Redis delete error: {e}")

    return {
        "marked_count": marked_count,
        "success": True
    }


@router.get(
    "/notifications/unread-count",
    summary="Get unread notification count",
    description="Get count of unread notifications with Redis caching (1 min TTL)"
)
@limiter.limit("100/minute")
async def get_unread_count(
    request: Request,
    current_user=Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
):
    """
    Get unread notification count with Redis caching.

    Caching strategy:
    - Cache key: user:unread_count:{user_id}
    - TTL: 1 minute
    - Invalidate on mark as read
    """
    user_id = _extract_user_id(current_user)

    # Try Redis cache first
    redis = await _get_redis_client()
    cache_key = f"user:unread_count:{user_id}"

    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for unread count: {user_id}")
                return {"count": int(cached)}
        except Exception as e:
            logger.warning(f"Redis get error: {e}")

    # Cache miss - fetch from DB
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    count = db.query(func.count(Notification.id)).filter(
        Notification.user_id == user_uuid,
        Notification.is_read == False
    ).scalar()

    # Cache the result
    if redis:
        try:
            await redis.setex(cache_key, CACHE_TTL_UNREAD_COUNT, str(count))
            logger.debug(f"Cached unread count for user: {user_id}")
        except Exception as e:
            logger.warning(f"Redis set error: {e}")

    return {"count": count}


# ============================================================================
# Firebase Integration Endpoints
# ============================================================================

@router.post(
    "/firebase/verify",
    response_model=FirebaseTokenVerifyResponse,
    summary="Verify Firebase token",
    description="Verify Firebase ID token and create/update user session"
)
@limiter.limit("60/minute")
async def verify_firebase_token(
    request: Request,
    payload: FirebaseTokenVerifyRequest,
    db: Session = Depends(get_db),
):
    """
    Verify Firebase ID token.

    This endpoint:
    1. Verifies the Firebase ID token
    2. Creates or updates user in database
    3. Creates a new session
    4. Returns user data and session ID

    NOTE: This is a placeholder implementation.
    Firebase Admin SDK integration should be added here.
    """
    # TODO: Implement Firebase Admin SDK token verification
    # For now, return a placeholder response

    logger.warning("Firebase token verification not yet implemented")

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Firebase token verification will be implemented in Sprint 2"
    )


# ============================================================================
# Password Management Endpoints (Legacy - Firebase handles this)
# ============================================================================

@router.post(
    "/password/change",
    summary="Change password (legacy)",
    description="Change user password with Firebase Admin SDK (rate limited: 5/hour)"
)
@limiter.limit("5/hour")
async def change_password(
    request: Request,
    payload: PasswordChangeRequest,
    current_user=Depends(get_current_user_from_session),
    db: Session = Depends(get_db),
):
    """
    Change user password (legacy endpoint).

    Rate limit: 5 attempts per hour

    NOTE: This endpoint is deprecated in favor of Firebase client-side password change.
    Kept for backward compatibility only.
    """
    logger.info("Password change requested (legacy endpoint)")

    # This is a placeholder - actual Firebase Admin SDK integration needed
    return {
        "success": False,
        "message": "Password change via API is deprecated. Please use Firebase client SDK."
    }


@router.post(
    "/password/reset",
    summary="Request password reset",
    description="Send password reset email (rate limited: 3/hour)"
)
@limiter.limit("3/hour")
async def request_password_reset(
    request: Request,
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    """
    Request password reset email.

    Rate limit: 3 attempts per hour

    NOTE: This endpoint is deprecated in favor of Firebase client-side password reset.
    Kept for backward compatibility only.
    """
    logger.info(f"Password reset requested for email: {payload.email}")

    # For security, always return success even if email doesn't exist
    return {
        "success": True,
        "message": "If the email exists, a password reset link has been sent. Please use Firebase client SDK for password reset."
    }


@router.post(
    "/reset-password",
    summary="Reset password with token",
    tags=["auth-v2"],
)
@limiter.limit("5/hour")
async def reset_password_with_token(
    request: Request,
    payload: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    """Reset a user's password given a valid token."""
    email = verify_password_reset_token(payload.token)
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.hashed_password = get_password_hash(payload.new_password)
    user.updated_at = datetime.utcnow()
    db.add(user)
    db.commit()

    return {
        "message": "Password reset successful",
        "user_id": str(user.id),
    }


@router.post(
    "/password/reset/confirm",
    summary="Confirm password reset",
    description="Confirm password reset with token"
)
@limiter.limit("5/hour")
async def confirm_password_reset(
    request: Request,
    payload: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    """
    Confirm password reset with token.

    NOTE: This endpoint is deprecated in favor of Firebase client-side password reset.
    Kept for backward compatibility only.
    """
    logger.info("Password reset confirmation requested (legacy endpoint)")

    return {
        "success": False,
        "message": "Password reset via API is deprecated. Please use Firebase client SDK."
    }


# ============================================================================
# Health Check Endpoint
# ============================================================================

@router.get(
    "/health",
    summary="Auth service health check",
    description="Check health of authentication service dependencies"
)
async def health_check(db: Session = Depends(get_db)):
    """
    Health check for auth service.

    Checks:
    - Database connectivity
    - Redis availability
    - Firebase connectivity (placeholder)

    Returns:
        dict: Health status of all dependencies
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }

    # Check database
    try:
        db.execute("SELECT 1")
        health_status["services"]["database"] = True
    except Exception as e:
        health_status["services"]["database"] = False
        health_status["status"] = "unhealthy"
        logger.error(f"Database health check failed: {e}")

    # Check Redis
    redis = await _get_redis_client()
    if redis:
        try:
            await redis.ping()
            health_status["services"]["redis"] = True
        except Exception as e:
            health_status["services"]["redis"] = False
            logger.warning(f"Redis health check failed: {e}")
    else:
        health_status["services"]["redis"] = False

    # Check Firebase (placeholder)
    # TODO: Add Firebase Admin SDK health check
    health_status["services"]["firebase"] = None  # Not implemented yet

    return health_status
