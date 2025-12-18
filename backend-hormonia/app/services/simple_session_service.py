"""
Simple Synchronous Session Service for Quiz Authentication

Provides basic Redis-backed session management with synchronous operations.
Used by quiz_auth.py for cookie-based authentication.

Features:
- Synchronous Redis operations (compatible with SessionLocal)
- Simple session create/get/delete/refresh
- No Firebase dependency
- Thread-safe with request-scoped sessions
"""

import logging
import secrets
from datetime import timedelta
from typing import Optional, Dict, Any
import redis


logger = logging.getLogger(__name__)


class SimpleSessionService:
    """
    Synchronous session service for quiz authentication.

    Uses Redis for session storage with simple key-value operations.
    Compatible with synchronous database sessions from SessionLocal.
    """

    # Session TTL configuration
    DEFAULT_TTL = int(timedelta(hours=24).total_seconds())  # 24 hours
    REFRESH_TTL = int(timedelta(days=30).total_seconds())  # 30 days for remember_me

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize simple session service.

        Args:
            redis_client: Synchronous Redis client (optional)
        """
        self.redis_client = redis_client
        self._session_prefix = "quiz_session:"

    def _get_session_key(self, session_id: str) -> str:
        """Get Redis key for session."""
        return f"{self._session_prefix}{session_id}"

    def create_session(
        self,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None,
    ) -> str:
        """
        Create new session in Redis.

        Args:
            user_id: User ID to associate with session
            metadata: Optional metadata to store with session
            ttl: Any TTL in seconds (default: 24 hours)

        Returns:
            session_id: Unique session identifier

        Raises:
            RuntimeError: If Redis is not available
        """
        if not self.redis_client:
            logger.warning("Redis not available, returning mock session_id")
            return f"mock_session_{secrets.token_urlsafe(32)}"

        try:
            # Generate secure session ID
            session_id = secrets.token_urlsafe(32)
            session_key = self._get_session_key(session_id)

            # Prepare session data
            session_data = {"user_id": user_id, **(metadata or {})}

            # Store in Redis with TTL
            ttl = ttl or self.DEFAULT_TTL
            self.redis_client.hset(session_key, mapping=session_data)
            self.redis_client.expire(session_key, ttl)

            logger.info(
                f"Created session {session_id} for user {user_id} (TTL: {ttl}s)"
            )
            return session_id

        except Exception as e:
            logger.error(f"Failed to create session: {e}", exc_info=True)
            raise RuntimeError(f"Session creation failed: {e}")

    def get_user_id(self, session_id: str) -> Optional[str]:
        """
        Get user_id from session.

        Args:
            session_id: Any identifier

        Returns:
            user_id if session exists and is valid, None otherwise
        """
        if not self.redis_client:
            logger.warning("Redis not available, cannot validate session")
            return None

        try:
            session_key = self._get_session_key(session_id)
            user_id = self.redis_client.hget(session_key, "user_id")

            if user_id:
                # Decode bytes to string if needed
                if isinstance(user_id, bytes):
                    user_id = user_id.decode("utf-8")
                return user_id

            return None

        except Exception as e:
            logger.error(f"Failed to get user_id from session: {e}")
            return None

    def get_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full session data.

        Args:
            session_id: Any identifier

        Returns:
            Session data dict or None if not found
        """
        if not self.redis_client:
            return None

        try:
            session_key = self._get_session_key(session_id)
            data = self.redis_client.hgetall(session_key)

            if not data:
                return None

            # Decode bytes to strings
            return {
                k.decode("utf-8") if isinstance(k, bytes) else k: v.decode("utf-8")
                if isinstance(v, bytes)
                else v
                for k, v in data.items()
            }

        except Exception as e:
            logger.error(f"Failed to get session data: {e}")
            return None

    def delete_session(self, session_id: str) -> bool:
        """
        Delete session from Redis.

        Args:
            session_id: Any identifier

        Returns:
            True if deleted, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            session_key = self._get_session_key(session_id)
            deleted = self.redis_client.delete(session_key)

            if deleted:
                logger.info(f"Deleted session {session_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return False

    def refresh_session(self, session_id: str, ttl: Optional[int] = None) -> bool:
        """
        Refresh session TTL.

        Args:
            session_id: Any identifier
            ttl: New TTL in seconds (default: 24 hours)

        Returns:
            True if refreshed, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            session_key = self._get_session_key(session_id)

            # Check if session exists
            if not self.redis_client.exists(session_key):
                return False

            # Update TTL
            ttl = ttl or self.DEFAULT_TTL
            refreshed = self.redis_client.expire(session_key, ttl)

            if refreshed:
                logger.debug(f"Refreshed session {session_id} (TTL: {ttl}s)")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to refresh session: {e}")
            return False

    def validate_session(self, session_id: str) -> bool:
        """
        Check if session exists and is valid.

        Args:
            session_id: Any identifier

        Returns:
            True if valid, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            session_key = self._get_session_key(session_id)
            return bool(self.redis_client.exists(session_key))

        except Exception as e:
            logger.error(f"Failed to validate session: {e}")
            return False
