"""
Authentication endpoints for Hormonia Backend System.
"""
from datetime import timedelta, datetime
from typing import Annotated, List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query, File, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.dependencies import get_thread_safe_db as get_db, get_current_user, get_auth_service
from app.services.auth import AuthService
from app.schemas.auth import LoginResponse, RefreshTokenRequest, UserResponse, LoginRequest
from app.schemas.common import SuccessResponse
from app.models.user import User
from app.config import settings
from app.utils.logging import get_logger
from app.utils.user_cache import (
    get_cached_profile, set_cached_profile, invalidate_user_cache,
    get_cached_preferences, set_cached_preferences,
    check_password_change_rate_limit
)
from app.utils.rate_limiter import limiter

logger = get_logger(__name__)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")
security = HTTPBearer()


# User Preferences Models
class UserPreferences(BaseModel):
    """User preferences schema."""
    notification_email: bool = True
    notification_sms: bool = True
    notification_whatsapp: bool = True
    language: str = "pt-BR"
    timezone: str = "America/Sao_Paulo"
    theme: str = "light"
    dashboard_widgets: Optional[Dict[str, Any]] = None
    email_digest_frequency: str = "daily"  # daily, weekly, monthly, never
    data_sharing_consent: bool = True
    marketing_consent: bool = False


class UserPreferencesResponse(BaseModel):
    """User preferences response."""
    user_id: str
    preferences: UserPreferences
    updated_at: datetime


# Notification Models
class NotificationResponse(BaseModel):
    """Notification response schema."""
    id: str
    title: str
    message: str
    type: str  # info, warning, error, success
    read: bool
    created_at: datetime
    metadata: Optional[dict] = None


class NotificationListResponse(BaseModel):
    """Notification list response."""
    notifications: List[NotificationResponse]
    total: int
    unread_count: int


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="[DEPRECATED] Local Login Disabled",
    description="""
    Local authentication is disabled. Use Firebase Auth on the client and send the Firebase ID token to this API.
    """,
)
@limiter.limit("5/minute")  # Rate limit: 5 attempts per minute per IP
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth_service: AuthService = Depends(get_auth_service)
) -> LoginResponse:
    """Disabled: Firebase-only authentication enforced."""
    raise HTTPException(status_code=status.HTTP_410_GONE, detail="Local login is disabled: Firebase-only authentication")


@router.post(
    "/login-json",
    response_model=LoginResponse,
    summary="[DEPRECATED] Local Login Disabled",
    description="Local authentication is disabled. Use Firebase Auth on the client.",
)
@limiter.limit("5/minute")  # Rate limit: 5 attempts per minute per IP
async def login_json(
    request: Request,
    login_data: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> LoginResponse:
    """Disabled: Firebase-only authentication enforced."""
    raise HTTPException(status_code=status.HTTP_410_GONE, detail="Local login is disabled: Firebase-only authentication")


@router.post(
    "/refresh",
    response_model=None,
    summary="[DEPRECATED] Local Refresh Disabled",
    description="Token refresh is handled by Firebase automatically on the client.",
)
@limiter.limit("20/minute")  # Rate limit: 20 refreshes per minute per IP
async def refresh_token(
    request: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> dict[str, str]:
    """Disabled: Firebase handles refresh automatically on the client."""
    raise HTTPException(status_code=status.HTTP_410_GONE, detail="Local refresh is disabled: Firebase handles refresh client-side")





@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get Current User Profile",
    description="""
    Retrieve the profile information of the currently authenticated user.

    This endpoint returns detailed information about the authenticated user,
    including their role, permissions, and account status.

    **Authentication Required**:
    - Session cookie (httpOnly) - PREFERRED (secure, XSS-safe)
    - X-Session-ID header - Fallback for backward compatibility
    - Bearer token in Authorization header - Legacy support

    **Rate Limit**: 100 requests per minute per IP
    """,
    responses={
        200: {
            "description": "User profile retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "email": "doctor@example.com",
                        "full_name": "Dr. Jane Smith",
                        "role": "doctor",
                        "is_active": True,
                        "created_at": "2024-01-01T00:00:00Z"
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Could not validate credentials"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "too_many_requests",
                        "message": "Muitas tentativas. Tente novamente mais tarde."
                    }
                }
            }
        }
    }
)
@limiter.limit("100/minute")  # Rate limit: 100 profile fetches per minute per IP
async def get_current_user_profile(request: Request, current_user: User = Depends(get_current_user)) -> UserResponse:
    """
    Get current user profile.

    SECURITY: Accepts session authentication via:
    1. httpOnly cookie (most secure)
    2. X-Session-ID header (backward compatible)
    3. Bearer token (legacy)
    """
    return UserResponse.from_orm(current_user)


# User Preferences Endpoints
@router.get(
    "/users/preferences",
    response_model=UserPreferencesResponse,
    summary="Get User Preferences",
    description="Get preferences for the current authenticated user. **Rate Limit**: 100 requests/minute per IP"
)
@limiter.limit("100/minute")  # Rate limit: 100 preference fetches per minute per IP
async def get_user_preferences(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserPreferencesResponse:
    """
    Get user preferences for the current user.
    """
    try:
        logger.info(f"Fetching preferences for user {current_user.id}")

        # Default preferences (would normally be fetched from database)
        user_prefs = UserPreferences()

        # If user has stored preferences in metadata, use them
        if hasattr(current_user, 'metadata') and current_user.metadata:
            if 'preferences' in current_user.metadata:
                stored_prefs = current_user.metadata.get('preferences', {})
                user_prefs = UserPreferences(**stored_prefs)

        return UserPreferencesResponse(
            user_id=str(current_user.id),
            preferences=user_prefs,
            updated_at=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error fetching user preferences: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch user preferences"
        )


@router.put(
    "/users/preferences",
    response_model=UserPreferencesResponse,
    summary="Update User Preferences",
    description="Update preferences for the current authenticated user. **Rate Limit**: 20 requests/hour per IP"
)
@limiter.limit("20/hour")  # Rate limit: 20 preference updates per hour per IP
async def update_user_preferences(
    request: Request,
    preferences: UserPreferences,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserPreferencesResponse:
    """
    Update user preferences for the current user.
    """
    try:
        logger.info(f"Updating preferences for user {current_user.id}")

        # Update user metadata with preferences
        if not hasattr(current_user, 'metadata') or current_user.metadata is None:
            current_user.metadata = {}

        current_user.metadata['preferences'] = preferences.dict()

        # Commit changes
        db.commit()
        db.refresh(current_user)

        return UserPreferencesResponse(
            user_id=str(current_user.id),
            preferences=preferences,
            updated_at=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error updating user preferences: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to update user preferences"
        )


@router.patch(
    "/users/preferences",
    response_model=UserPreferencesResponse,
    summary="Partially Update User Preferences",
    description="Partially update preferences for the current authenticated user. **Rate Limit**: 20 requests/hour per IP"
)
@limiter.limit("20/hour")  # Rate limit: 20 preference patches per hour per IP
async def patch_user_preferences(
    request: Request,
    updates: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserPreferencesResponse:
    """
    Partially update user preferences for the current user.
    """
    try:
        logger.info(f"Patching preferences for user {current_user.id}")

        # Get current preferences
        if hasattr(current_user, 'metadata') and current_user.metadata:
            current_prefs = current_user.metadata.get('preferences', {})
        else:
            current_prefs = {}

        # Apply updates
        current_prefs.update(updates)

        # Validate updated preferences
        user_prefs = UserPreferences(**current_prefs)

        # Save to database
        if not hasattr(current_user, 'metadata') or current_user.metadata is None:
            current_user.metadata = {}

        current_user.metadata['preferences'] = user_prefs.dict()

        db.commit()
        db.refresh(current_user)

        return UserPreferencesResponse(
            user_id=str(current_user.id),
            preferences=user_prefs,
            updated_at=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error patching user preferences: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to patch user preferences"
        )


@router.post(
    "/users/preferences/reset",
    response_model=SuccessResponse,
    summary="Reset User Preferences",
    description="Reset user preferences to defaults. **Rate Limit**: 10 requests/hour per IP"
)
@limiter.limit("10/hour")  # Rate limit: 10 preference resets per hour per IP
async def reset_user_preferences(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SuccessResponse:
    """
    Reset user preferences to defaults.
    """
    try:
        logger.info(f"Resetting preferences for user {current_user.id}")

        # Reset to default preferences
        default_prefs = UserPreferences()

        if not hasattr(current_user, 'metadata') or current_user.metadata is None:
            current_user.metadata = {}

        current_user.metadata['preferences'] = default_prefs.dict()

        db.commit()

        return SuccessResponse(
            success=True,
            message="User preferences reset to defaults"
        )

    except Exception as e:
        logger.error(f"Error resetting user preferences: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to reset user preferences"
        )


# Notification Endpoints
@router.get(
    "/notifications",
    response_model=NotificationListResponse,
    summary="Get User Notifications",
    description="Get notifications for the current authenticated user. **Rate Limit**: 100 requests/minute per IP"
)
@limiter.limit("100/minute")  # Rate limit: 100 notification fetches per minute per IP
async def get_notifications(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = Query(default=False)
) -> NotificationListResponse:
    """
    Get notifications for the current user.
    """
    try:
        # For now, return empty notifications (will be implemented with actual notification system)
        # This fixes the 404 error and provides a proper endpoint structure

        notifications = []
        total = 0
        unread_count = 0

        # Example notification structure (to be replaced with actual database query)
        # This would normally query a notifications table

        logger.info(f"Fetching notifications for user {current_user.id}")

        return NotificationListResponse(
            notifications=notifications,
            total=total,
            unread_count=unread_count
        )

    except Exception as e:
        logger.error(f"Error fetching notifications: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch notifications"
        )


@router.post(
    "/notifications/{notification_id}/read",
    response_model=SuccessResponse,
    summary="Mark Notification as Read",
    description="Mark a specific notification as read. **Rate Limit**: 100 requests/minute per IP"
)
@limiter.limit("100/minute")  # Rate limit: 100 notification marks per minute per IP
async def mark_notification_as_read(
    request: Request,
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SuccessResponse:
    """
    Mark a notification as read.
    """
    try:
        # Implementation would mark the notification as read in the database
        logger.info(f"Marking notification {notification_id} as read for user {current_user.id}")

        return SuccessResponse(
            success=True,
            message="Notification marked as read"
        )

    except Exception as e:
        logger.error(f"Error marking notification as read: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to mark notification as read"
        )


@router.post(
    "/notifications/mark-all-read",
    response_model=SuccessResponse,
    summary="Mark All Notifications as Read",
    description="Mark all notifications as read for the current user. **Rate Limit**: 20 requests/hour per IP"
)
@limiter.limit("20/hour")  # Rate limit: 20 mark-all operations per hour per IP
async def mark_all_notifications_as_read(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SuccessResponse:
    """
    Mark all notifications as read for the current user.
    """
    try:
        # Implementation would mark all user's notifications as read
        logger.info(f"Marking all notifications as read for user {current_user.id}")

        return SuccessResponse(
            success=True,
            message="All notifications marked as read"
        )

    except Exception as e:
        logger.error(f"Error marking all notifications as read: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to mark all notifications as read"
        )


@router.delete(
    "/notifications/{notification_id}",
    response_model=SuccessResponse,
    summary="Delete Notification",
    description="Delete a specific notification. **Rate Limit**: 100 requests/minute per IP"
)
@limiter.limit("100/minute")  # Rate limit: 100 notification deletes per minute per IP
async def delete_notification(
    request: Request,
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SuccessResponse:
    """
    Delete a notification.
    """
    try:
        # Implementation would delete the notification from the database
        logger.info(f"Deleting notification {notification_id} for user {current_user.id}")

        return SuccessResponse(
            success=True,
            message="Notification deleted successfully"
        )

    except Exception as e:
        logger.error(f"Error deleting notification: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete notification"
        )


# New Settings Endpoints

class ProfileUpdateRequest(BaseModel):
    """Profile update request schema."""
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    specialty: Optional[str] = None


class ProfileUpdateResponse(BaseModel):
    """Profile update response schema."""
    id: str
    email: str
    full_name: str
    phone: Optional[str] = None
    specialty: Optional[str] = None
    updated_at: datetime


class PasswordChangeRequest(BaseModel):
    """Password change request schema."""
    current_password: str = Field(..., min_length=8, description="Current password for verification")
    new_password: str = Field(..., min_length=8, description="New password")


@router.put(
    "/profile",
    response_model=ProfileUpdateResponse,
    summary="Update User Profile",
    description="Update profile information for the current authenticated user"
)
@limiter.limit("20/hour")  # Rate limit: 20 profile updates per hour per IP
async def update_profile(
    request: Request,
    profile_data: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> ProfileUpdateResponse:
    """
    Update user profile with cache invalidation.
    """
    try:
        logger.info(f"Updating profile for user {current_user.id}")

        # Update user fields
        if profile_data.full_name is not None:
            current_user.full_name = profile_data.full_name

        if profile_data.email is not None:
            # Check if email already exists for another user
            from app.repositories.user import UserRepository
            user_repo = UserRepository(db)
            existing = user_repo.get_by_email(profile_data.email.strip().lower())
            if existing and existing.id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use"
                )
            current_user.email = profile_data.email.strip().lower()

        # Store phone and specialty in metadata if not in model
        if not hasattr(current_user, 'metadata') or current_user.metadata is None:
            current_user.metadata = {}

        if profile_data.phone is not None:
            current_user.metadata['phone'] = profile_data.phone

        if profile_data.specialty is not None:
            current_user.metadata['specialty'] = profile_data.specialty

        current_user.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(current_user)

        # Invalidate cache
        firebase_uid = current_user.metadata.get('firebase_uid', str(current_user.id))
        invalidate_user_cache(firebase_uid, str(current_user.id))

        return ProfileUpdateResponse(
            id=str(current_user.id),
            email=current_user.email,
            full_name=current_user.full_name,
            phone=current_user.metadata.get('phone'),
            specialty=current_user.metadata.get('specialty'),
            updated_at=current_user.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to update profile"
        )


@router.post(
    "/avatar",
    summary="Upload User Avatar (DISABLED)",
    description="Avatar upload temporarily disabled during migration to AWS S3",
    deprecated=True
)
@limiter.limit("10/hour")
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Avatar upload temporarily disabled.

    NOTE: This feature is being migrated from Supabase Storage to AWS S3.
    Will be re-enabled once migration is complete.
    """
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Avatar upload temporarily disabled during storage migration to AWS S3. This feature will be available soon."
    )


@router.put(
    "/password",
    response_model=SuccessResponse,
    summary="Change User Password",
    description="Change password for the current authenticated user (with rate limiting)"
)
@limiter.limit("3/hour")  # Rate limit: 3 password changes per hour per IP
async def change_password(
    request: Request,
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> SuccessResponse:
    """
    Change user password with Firebase Admin SDK and rate limiting.

    Requires current password verification for re-authentication security.
    """
    try:
        logger.info(f"Password change requested for user {current_user.id}")

        # Get Firebase UID
        firebase_uid = current_user.metadata.get('firebase_uid') if hasattr(current_user, 'metadata') and current_user.metadata else None

        if not firebase_uid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Firebase UID not found for user"
            )

        # Check rate limit
        if not check_password_change_rate_limit(firebase_uid, max_attempts=3, window_seconds=3600):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many password change attempts. Please try again later."
            )

        # Verify current password with Firebase Admin SDK
        import firebase_admin
        from firebase_admin import auth as firebase_auth

        try:
            # For Firebase Admin SDK, we need to verify the current password
            # Since Firebase Admin doesn't directly support password verification,
            # we use Firebase Auth REST API to verify the current password

            # Verify current password using Firebase Auth REST API
            import requests

            auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={settings.FIREBASE_WEB_API_KEY}"
            auth_payload = {
                "email": current_user.email,
                "password": password_data.current_password,
                "returnSecureToken": True
            }

            auth_response = requests.post(auth_url, json=auth_payload)

            if auth_response.status_code != 200:
                logger.warning(f"Current password verification failed for user {current_user.id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is incorrect"
                )

            auth_data = auth_response.json()
            if auth_data.get('localId') != firebase_uid:
                logger.warning(f"Firebase UID mismatch during password verification for user {current_user.id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is incorrect"
                )

        except requests.RequestException as e:
            logger.error(f"Error verifying current password for user {current_user.id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password verification failed"
            )
        except firebase_admin.exceptions.FirebaseError as e:
            logger.error(f"Firebase error during password verification for user {current_user.id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password verification failed"
            )

        # Update password via Firebase Admin SDK
        from app.services.firebase_auth_service import get_firebase_auth_service

        firebase_service = get_firebase_auth_service(
            project_id=settings.FIREBASE_ADMIN_PROJECT_ID,
            private_key=settings.FIREBASE_ADMIN_PRIVATE_KEY,
            client_email=settings.FIREBASE_ADMIN_CLIENT_EMAIL
        )

        # Update password
        firebase_auth.update_user(
            firebase_uid,
            password=password_data.new_password
        )

        logger.info(f"Password updated successfully for user {current_user.id}")

        return SuccessResponse(
            success=True,
            message="Password updated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to change password: {str(e)}"
        )