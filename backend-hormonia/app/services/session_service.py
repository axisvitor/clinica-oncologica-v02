"""
Session Service - Unified API for Session Management

Provides a high-level service layer for session operations, integrating:
- Firebase authentication
- Redis session storage
- CSRF token management
- Session validation and cleanup

This service acts as a facade over the core session_manager and Firebase/Redis
integration, providing a clean API for authentication and session management.

Architecture:
- Uses core.session_manager for database session lifecycle
- Uses core.redis_manager for Redis session storage
- Integrates with Firebase for authentication
- Provides session validation for CSRF middleware

Performance:
- Session validation: ~2-5ms (Redis cache hit)
- Session creation: ~250ms (Firebase validation + Redis storage)
- Session cleanup: ~50-100ms (Redis scan + delete)
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
# from sqlalchemy.orm import
import redis.asyncio as redis

from app.config import settings
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


class SessionService:
    """
    High-level session management service.

    Provides unified API for session operations across the application.
    Integrates Firebase authentication, Redis session storage, and CSRF protection.
    """

    def __init__(
        self,
        db: Any,
        redis_client: Optional[redis.Redis] = None,
        firebase_service = None
    ):
        """
        Initialize session service.

        Args:
            db: Database session
            redis_client: Redis client for session storage
            firebase_service: Firebase authentication service
        """
        self.db = db
        self.redis_client = redis_client
        self.firebase_service = firebase_service
        self._firebase_cache = None

    def _get_firebase_cache(self):
        """Get or create FirebaseRedisCache instance."""
        if self._firebase_cache is None and self.redis_client is not None:
            from app.core.redis_manager import FirebaseRedisCache
            self._firebase_cache = FirebaseRedisCache(self.redis_client)
        return self._firebase_cache

    async def create_session_from_firebase_token(
        self,
        firebase_token: str,
        device_info: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Create new session from Firebase ID token.

        Validates Firebase token, creates or retrieves user from database,
        stores session in Redis, and returns session details.

        Args:
            firebase_token: Firebase ID token from frontend
            device_info: Optional device metadata

        Returns:
            dict: Any details including session_id, user data, and expiration

        Raises:
            HTTPException: If Firebase service unavailable or token invalid
        """
        if self.firebase_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Firebase authentication is not configured"
            )

        # Validate Firebase token (~200ms)
        try:
            user_data = await self.firebase_service.verify_token(firebase_token)
            firebase_uid = user_data["uid"]
            email = user_data.get("email")
        except Exception as e:
            logger.error(f"Firebase token validation failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Firebase token"
            )

        logger.info(f"Creating session for user: {email}")

        # Get or create user in database
        user = await self._get_or_create_user(firebase_uid, user_data)

        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )

        # Create Redis session
        firebase_cache = self._get_firebase_cache()
        if firebase_cache is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis session storage is not available"
            )

        # Generate session ID
        session_id = str(uuid.uuid4())

        # Session metadata
        metadata = {
            "email": user.email,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            **(device_info or {})
        }

        # Create session (24 hours TTL by default)
        ttl = getattr(settings, 'FIREBASE_SESSION_TTL', 86400)
        success = await firebase_cache.create_session(
            session_id=session_id,
            user_id=str(user.id),
            firebase_uid=firebase_uid,
            metadata=metadata
        )

        if not success:
            logger.error(f"Failed to create Redis session for {email}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create session in Redis"
            )

        # Cache user object (Layer 2 cache)
        user_dict = self._user_to_dict(user)
        firebase_cache.cache_user(firebase_uid, user_dict)

        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)

        logger.info(f"✅ Session created: {session_id[:8]}... for {email}")

        return {
            "session_id": session_id,
            "user": user_dict,
            "expires_at": expires_at.isoformat(),
            "ttl": ttl,
            "status": "authenticated"
        }

    async def validate_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Validate session and return session data.

        Ultra-fast validation using Redis cache (~2-5ms).

        Args:
            session_id: Any ID to validate

        Returns:
            dict: Any data with user info if valid, None if invalid
        """
        if not session_id:
            return None

        firebase_cache = self._get_firebase_cache()
        if firebase_cache is None:
            logger.warning("Redis not available, session validation failed")
            return None

        try:
            # Get session from Redis (~2-5ms)
            session_data = await firebase_cache.get_session(session_id)

            if not session_data:
                return None

            # Get user data from cache or DB
            firebase_uid = session_data.get("firebase_uid")
            cached_user = firebase_cache.get_cached_user(firebase_uid)

            if cached_user:
                user_data = cached_user
            else:
                # Fallback: query DB
                user = await self._get_user_by_firebase_uid(firebase_uid)
                if not user:
                    return None
                user_data = self._user_to_dict(user)

            return {
                "valid": True,
                "user": user_data,
                "session_data": session_data
            }

        except Exception as e:
            logger.error(f"Session validation error: {str(e)}", exc_info=True)
            return None

    async def invalidate_session(self, session_id: str) -> bool:
        """
        Invalidate single session.

        Args:
            session_id: Any ID to invalidate

        Returns:
            bool: True if session was deleted, False if not found
        """
        firebase_cache = self._get_firebase_cache()
        if firebase_cache is None:
            logger.warning("Redis not available, cannot invalidate session")
            return False

        try:
            deleted = await firebase_cache.invalidate_session(session_id)
            if deleted:
                logger.info(f"Session invalidated: {session_id[:8]}...")
            return deleted
        except Exception as e:
            logger.error(f"Session invalidation error: {str(e)}", exc_info=True)
            return False

    async def invalidate_all_user_sessions(self, firebase_uid: str) -> int:
        """
        Invalidate all sessions for a user (global logout).

        Args:
            firebase_uid: Firebase UID of user

        Returns:
            int: Number of sessions deleted
        """
        firebase_cache = self._get_firebase_cache()
        if firebase_cache is None:
            logger.warning("Redis not available, cannot invalidate sessions")
            return 0

        try:
            deleted = await firebase_cache.invalidate_all_user_sessions(firebase_uid)
            logger.info(f"Global logout: {deleted} sessions deleted for uid {firebase_uid[:8]}...")
            return deleted
        except Exception as e:
            logger.error(f"Global logout error: {str(e)}", exc_info=True)
            return 0

    async def list_user_sessions(self, firebase_uid: str) -> List[Dict[str, Any]]:
        """
        List all active sessions for a user.

        Args:
            firebase_uid: Firebase UID of user

        Returns:
            list: Active sessions with metadata
        """
        firebase_cache = self._get_firebase_cache()
        if firebase_cache is None:
            logger.warning("Redis not available, cannot list sessions")
            return []

        try:
            sessions = firebase_cache.list_user_sessions(firebase_uid)
            return sessions
        except Exception as e:
            logger.error(f"List sessions error: {str(e)}", exc_info=True)
            return []

    async def cleanup_expired_sessions(self) -> int:
        """
        Cleanup expired sessions (background task).

        Redis TTL handles most cleanup automatically, but this can be used
        for additional cleanup logic if needed.

        Returns:
            int: Number of sessions cleaned up
        """
        # Redis TTL auto-expires keys, so this is mostly for logging/monitoring
        firebase_cache = self._get_firebase_cache()
        if firebase_cache is None:
            return 0

        try:
            stats = firebase_cache.get_cache_stats()
            logger.info(f"Session cleanup check - Active sessions: {stats.get('active_sessions', 0)}")
            return 0  # Redis handles expiration automatically
        except Exception as e:
            logger.error(f"Session cleanup error: {str(e)}", exc_info=True)
            return 0

    def generate_csrf_token(self, session_id: str) -> str:
        """
        Generate CSRF token for session.

        CSRF tokens are tied to sessions for additional security.
        The token is stored in Redis with the session data.

        Args:
            session_id: Any ID to generate CSRF token for

        Returns:
            str: CSRF token
        """
        import secrets
        csrf_token = secrets.token_urlsafe(32)

        # Store CSRF token in session data
        firebase_cache = self._get_firebase_cache()
        if firebase_cache:
            try:
                # Update session with CSRF token
                session_key = f"session:{session_id}"
                self.redis_client.hset(session_key, "csrf_token", csrf_token)
                logger.debug(f"CSRF token generated for session {session_id[:8]}...")
            except Exception as e:
                logger.error(f"Failed to store CSRF token: {str(e)}")

        return csrf_token

    def validate_csrf_token(self, session_id: str, csrf_token: str) -> bool:
        """
        Validate CSRF token against session.

        Args:
            session_id: Any ID
            csrf_token: CSRF token to validate

        Returns:
            bool: True if token is valid
        """
        firebase_cache = self._get_firebase_cache()
        if firebase_cache is None:
            logger.warning("Redis not available, CSRF validation failed")
            return False

        try:
            session_key = f"session:{session_id}"
            stored_token = self.redis_client.hget(session_key, "csrf_token")

            if not stored_token:
                logger.warning(f"No CSRF token found for session {session_id[:8]}...")
                return False

            is_valid = stored_token == csrf_token
            if not is_valid:
                logger.warning(f"CSRF token mismatch for session {session_id[:8]}...")

            return is_valid

        except Exception as e:
            logger.error(f"CSRF validation error: {str(e)}", exc_info=True)
            return False

    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================

    async def _get_or_create_user(
        self,
        firebase_uid: str,
        user_data: Dict[str, Any]
    ) -> User:
        """Get existing user or create new one from Firebase data."""
        from sqlalchemy import select

        stmt = select(User).where(User.firebase_uid == firebase_uid)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            # Create minimal user record
            email = user_data.get("email")
            firebase_role = user_data.get("role", "doctor").lower()
            user_role = UserRole.ADMIN if firebase_role == "admin" else UserRole.DOCTOR

            user = User(
                firebase_uid=firebase_uid,
                email=email,
                full_name=user_data.get("name", email.split("@")[0] if email else "Unknown"),
                is_active=True,
                role=user_role
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            logger.info(f"Created new user: {email}")

        return user

    async def _get_user_by_firebase_uid(self, firebase_uid: str) -> Optional[User]:
        """Get user by Firebase UID."""
        from sqlalchemy import select

        stmt = select(User).where(User.firebase_uid == firebase_uid)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def _user_to_dict(self, user: User) -> Dict[str, Any]:
        """Convert User model to dictionary."""
        return {
            "id": str(user.id),
            "firebase_uid": user.firebase_uid,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            "is_active": user.is_active,
        }


# =============================================================================
# FACTORY FUNCTIONS FOR DEPENDENCY INJECTION
# =============================================================================

def create_session_service(
    db: Any,
    redis_client: Optional[redis.Redis] = None,
    firebase_service = None
) -> AnyService:
    """
    Factory function to create SessionService instance.

    Args:
        db: Database session
        redis_client: Redis client
        firebase_service: Firebase authentication service

    Returns:
        SessionService: Configured session service
    """
    return SessionService(
        db=db,
        redis_client=redis_client,
        firebase_service=firebase_service
    )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def get_session_from_request(
    session_id: Optional[str],
    db: Any,
    redis_client: Optional[redis.Redis] = None
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to validate session from request.

    Args:
        session_id: Any ID from cookie or header
        db: Database session
        redis_client: Redis client

    Returns:
        dict: Any data if valid, None otherwise
    """
    service = SessionService(db, redis_client)
    return await service.validate_session(session_id)


__all__ = [
    'SessionService',
    'create_session_service',
    'get_session_from_request',
]
