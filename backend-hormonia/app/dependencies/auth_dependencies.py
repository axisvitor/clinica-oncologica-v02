"""Authentication Dependencies - Firebase Authentication Only

Firebase-only authentication system.
All Supabase fallback code has been removed.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import logging

from app.models.user import User, UserRole
from app.services import ServiceProvider
from app.config import settings

logger = logging.getLogger(__name__)
security = HTTPBearer()

# Initialize Firebase Auth Service if configured
_firebase_service = None
try:
    from app.services.firebase_auth_service import get_firebase_auth_service

    # Check if Firebase credentials are configured
    firebase_project_id = getattr(settings, 'FIREBASE_ADMIN_PROJECT_ID', None)
    firebase_private_key = getattr(settings, 'FIREBASE_ADMIN_PRIVATE_KEY', None)
    firebase_client_email = getattr(settings, 'FIREBASE_ADMIN_CLIENT_EMAIL', None)

    if firebase_project_id and firebase_private_key and firebase_client_email:
        _firebase_service = get_firebase_auth_service(
            project_id=firebase_project_id,
            private_key=firebase_private_key,
            client_email=firebase_client_email
        )
        logger.info("Firebase Authentication enabled")
    else:
        logger.error("Firebase credentials not configured - authentication will not work")
        _firebase_service = None
except Exception as e:
    logger.error(f"Failed to initialize Firebase Auth: {str(e)}")
    _firebase_service = None

# =============================================================================
# CORE AUTHENTICATION DEPENDENCIES
# =============================================================================

def _get_service_provider():
    """Lazy loader for ServiceProvider to avoid circular imports."""
    from app.dependencies import get_thread_safe_service_provider
    # Yield from the actual generator function
    yield from get_thread_safe_service_provider()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    services: ServiceProvider = Depends(_get_service_provider)
) -> User:
    """
    Get current authenticated user by validating Firebase Auth token.

    Authentication flow:
    1. Validate Firebase is configured
    2. Verify Firebase JWT token
    3. Sync Firebase user to local database
    4. Return authenticated user

    No fallback authentication - Firebase only.
    """
    # Check if Firebase is configured
    if _firebase_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase authentication is not configured"
        )

    try:
        # Verify Firebase token
        user_data = await _firebase_service.verify_token(credentials.credentials)
        firebase_uid = user_data.get("uid")
        email = user_data.get("email")

        logger.debug(f"Firebase token validated for user: {email}")

        # Fast path: Check if user already exists in database (< 100ms)
        from app.models.user import User
        from sqlalchemy import select

        stmt = select(User).where(User.firebase_uid == firebase_uid)
        result = await services.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            # User exists - return immediately without blocking
            logger.debug(f"User found in database: {email}")

            # Check if user is active
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive"
                )

            return user

        # Slow path: User doesn't exist - sync in background (non-blocking)
        # For now, create minimal user record to unblock authentication
        # Full sync will happen in background task
        logger.info(f"User not found in database, creating minimal record for: {email}")

        from app.services.firebase_user_sync_service import FirebaseUserSyncService
        from app.models.user import UserRole
        sync_service = FirebaseUserSyncService(services.db, _firebase_service)

        # Create minimal user record (fast - no external calls)
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            full_name=user_data.get("name", email.split("@")[0]),
            is_active=True,
            role=UserRole.PATIENT  # Default, can be updated by sync
        )
        services.db.add(user)
        await services.db.commit()
        await services.db.refresh(user)

        logger.info(f"Minimal user created: {email}. Full sync will run in background.")

        # TODO: Schedule background task for full sync
        # asyncio.create_task(sync_service.sync_firebase_user(...))

        return user

    except HTTPException:
        # Re-raise HTTP exceptions (inactive user, etc.)
        raise
    except Exception as e:
        # Firebase authentication failed
        logger.error(f"Firebase authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Firebase authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user (additional validation)"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    services: ServiceProvider = Depends(_get_service_provider)
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None"""
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials, services)
    except HTTPException:
        return None

# =============================================================================
# ROLE-BASED DEPENDENCIES
# =============================================================================

async def get_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current user with admin privileges"""
    if current_user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


async def get_doctor_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current user with doctor privileges"""
    if current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

# =============================================================================
# WEBSOCKET AUTHENTICATION
# =============================================================================

async def get_current_user_websocket(
    websocket,
    services: ServiceProvider = Depends(_get_service_provider)
) -> Optional[User]:
    """Get current user from WebSocket connection validating Firebase token only"""
    try:
        # Check if Firebase is configured
        if _firebase_service is None:
            logger.error("Firebase authentication not configured for WebSocket")
            return None

        # Get token from query parameters or headers
        token = None
        if hasattr(websocket, 'query_params') and 'token' in websocket.query_params:
            token = websocket.query_params['token']
        elif hasattr(websocket, 'headers'):
            auth_header = None
            try:
                auth_header = websocket.headers.get('authorization')
            except Exception:
                if 'authorization' in getattr(websocket, 'headers', {}):
                    auth_header = websocket.headers['authorization']
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]

        if not token:
            return None

        # Verify Firebase token
        user_data = await _firebase_service.verify_token(token)
        email = user_data.get("email")

        if not email:
            return None

        # Get user from database
        user = services.user_repository.get_by_email(email.strip().lower())
        if user is None or not user.is_active:
            return None

        return user

    except Exception as e:
        logger.error(f"WebSocket authentication failed: {str(e)}")
        return None
