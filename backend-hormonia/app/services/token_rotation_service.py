"""
JWT Token Rotation Service for Enhanced Security
Implements token rotation, blacklisting, and session management
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from uuid import uuid4
import redis
import json
from jose import jwt, JWTError
from app.config import get_settings
from app.core.redis_manager import get_redis_manager

logger = logging.getLogger(__name__)

class TokenRotationService:
    """
    Service for managing JWT token rotation and security.
    Implements:
    - Automatic token rotation
    - Token blacklisting
    - Session management
    - Concurrent session control
    """

    def __init__(self):
        self.settings = get_settings()
        self.redis_manager = get_redis_manager()
        self.algorithm = self.settings.ALGORITHM
        self.secret_key = self.settings.SECRET_KEY

        # Token expiration settings
        self.access_token_expire = timedelta(minutes=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        self.refresh_token_expire = timedelta(days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS)

        # Rotation settings
        self.rotation_enabled = self.settings.TOKEN_ROTATION_ENABLED
        self.blacklist_enabled = self.settings.TOKEN_BLACKLIST_ENABLED
        self.max_concurrent_sessions = getattr(self.settings, 'MAX_CONCURRENT_SESSIONS', 3)

    def create_access_token(self, data: dict, user_id: str) -> str:
        """
        Create a new access token with rotation tracking.

        Args:
            data: Token payload data
            user_id: User identifier

        Returns:
            JWT access token
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + self.access_token_expire

        # Add token metadata
        token_id = str(uuid4())
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": token_id,  # JWT ID for tracking
            "type": "access",
            "rotation_count": 0
        })

        # Track active token
        if self.rotation_enabled:
            self._track_token(user_id, token_id, "access", expire)

        # Encode token
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

        return encoded_jwt

    def create_refresh_token(self, user_id: str) -> str:
        """
        Create a new refresh token.

        Args:
            user_id: User identifier

        Returns:
            JWT refresh token
        """
        expire = datetime.utcnow() + self.refresh_token_expire
        token_id = str(uuid4())

        to_encode = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": token_id,
            "type": "refresh"
        }

        # Track refresh token
        if self.rotation_enabled:
            self._track_token(user_id, token_id, "refresh", expire)

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

        return encoded_jwt

    def rotate_token(self, current_token: str) -> Optional[Dict[str, str]]:
        """
        Rotate an existing token to a new one.

        Args:
            current_token: Current JWT token

        Returns:
            Dictionary with new access and refresh tokens
        """
        try:
            # Decode current token
            payload = jwt.decode(current_token, self.secret_key, algorithms=[self.algorithm])

            # Check if token is blacklisted
            if self._is_blacklisted(payload.get("jti")):
                logger.warning(f"Attempted to rotate blacklisted token: {payload.get('jti')}")
                return None

            # Get user info
            user_id = payload.get("sub")
            if not user_id:
                return None

            # Blacklist old token
            if self.blacklist_enabled:
                self._blacklist_token(payload.get("jti"), payload.get("exp"))

            # Create new tokens
            new_access_data = {
                "sub": user_id,
                "rotation_count": payload.get("rotation_count", 0) + 1,
                "previous_jti": payload.get("jti")
            }

            new_access_token = self.create_access_token(new_access_data, user_id)
            new_refresh_token = self.create_refresh_token(user_id)

            # Log rotation
            logger.info(f"Token rotated for user {user_id}, rotation count: {new_access_data['rotation_count']}")

            return {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "token_type": "bearer"
            }

        except JWTError as e:
            logger.error(f"Token rotation failed: {e}")
            return None

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify a token and check blacklist.

        Args:
            token: JWT token to verify

        Returns:
            Token payload if valid, None otherwise
        """
        try:
            # Decode token
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Check blacklist
            if self.blacklist_enabled and self._is_blacklisted(payload.get("jti")):
                logger.warning(f"Blacklisted token used: {payload.get('jti')}")
                return None

            # Check if token needs rotation
            if self._should_rotate(payload):
                logger.info(f"Token {payload.get('jti')} marked for rotation")
                payload["should_rotate"] = True

            return payload

        except JWTError as e:
            logger.error(f"Token verification failed: {e}")
            return None

    def revoke_token(self, token: str) -> bool:
        """
        Revoke a token by adding to blacklist.

        Args:
            token: JWT token to revoke

        Returns:
            Success status
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            token_id = payload.get("jti")
            expire = payload.get("exp")

            if token_id:
                self._blacklist_token(token_id, expire)
                logger.info(f"Token {token_id} revoked")
                return True

            return False

        except JWTError:
            return False

    def revoke_all_user_tokens(self, user_id: str) -> int:
        """
        Revoke all tokens for a specific user.

        Args:
            user_id: User identifier

        Returns:
            Number of tokens revoked
        """
        try:
            # Get sync Redis client from manager
            redis_client = self.redis_manager.get_sync_client()

            # Get all user tokens
            pattern = f"token:active:{user_id}:*"
            tokens = redis_client.keys(pattern)

            revoked_count = 0
            for token_key in tokens:
                token_data = redis_client.get(token_key)
                if token_data:
                    token_info = json.loads(token_data)
                    self._blacklist_token(token_info["jti"], token_info["exp"])
                    redis_client.delete(token_key)
                    revoked_count += 1

            logger.info(f"Revoked {revoked_count} tokens for user {user_id}")
            return revoked_count

        except Exception as e:
            logger.error(f"Failed to revoke user tokens: {e}")
            return 0

    def get_active_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all active sessions for a user.

        Args:
            user_id: User identifier

        Returns:
            List of active sessions
        """
        try:
            # Get sync Redis client from manager
            redis_client = self.redis_manager.get_sync_client()

            pattern = f"token:active:{user_id}:*"
            tokens = redis_client.keys(pattern)

            sessions = []
            for token_key in tokens:
                token_data = redis_client.get(token_key)
                if token_data:
                    sessions.append(json.loads(token_data))

            return sessions

        except Exception as e:
            logger.error(f"Failed to get active sessions: {e}")
            return []

    def enforce_session_limit(self, user_id: str) -> int:
        """
        Enforce maximum concurrent sessions per user.

        Args:
            user_id: User identifier

        Returns:
            Number of sessions revoked
        """
        sessions = self.get_active_sessions(user_id)

        if len(sessions) <= self.max_concurrent_sessions:
            return 0

        # Sort by creation time (oldest first)
        sessions.sort(key=lambda x: x.get("iat", 0))

        # Revoke oldest sessions
        sessions_to_revoke = len(sessions) - self.max_concurrent_sessions
        revoked_count = 0

        # Get sync Redis client from manager
        redis_client = self.redis_manager.get_sync_client()

        for session in sessions[:sessions_to_revoke]:
            if self._blacklist_token(session["jti"], session["exp"]):
                revoked_count += 1
                # Remove from active tokens
                key = f"token:active:{user_id}:{session['jti']}"
                redis_client.delete(key)

        if revoked_count > 0:
            logger.info(f"Enforced session limit for user {user_id}, revoked {revoked_count} sessions")

        return revoked_count

    def _track_token(self, user_id: str, token_id: str, token_type: str, expire: datetime):
        """Track an active token in Redis."""
        try:
            # Get sync Redis client from manager
            redis_client = self.redis_manager.get_sync_client()

            key = f"token:active:{user_id}:{token_id}"
            value = {
                "jti": token_id,
                "type": token_type,
                "iat": datetime.utcnow().isoformat(),
                "exp": expire.isoformat(),
                "user_id": user_id
            }

            # Calculate TTL
            ttl = int((expire - datetime.utcnow()).total_seconds())

            # Store in Redis with TTL
            redis_client.setex(
                key,
                ttl,
                json.dumps(value)
            )

        except Exception as e:
            logger.error(f"Failed to track token: {e}")

    def _blacklist_token(self, token_id: str, expire: Any) -> bool:
        """Add token to blacklist."""
        if not self.blacklist_enabled:
            return False

        try:
            # Get sync Redis client from manager
            redis_client = self.redis_manager.get_sync_client()

            key = f"token:blacklist:{token_id}"

            # Calculate TTL (keep blacklisted until original expiration)
            if isinstance(expire, (int, float)):
                expire_dt = datetime.fromtimestamp(expire)
            else:
                expire_dt = expire

            ttl = int((expire_dt - datetime.utcnow()).total_seconds())

            if ttl > 0:
                redis_client.setex(key, ttl, "1")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")
            return False

    def _is_blacklisted(self, token_id: str) -> bool:
        """Check if token is blacklisted."""
        if not self.blacklist_enabled or not token_id:
            return False

        try:
            # Get sync Redis client from manager
            redis_client = self.redis_manager.get_sync_client()

            key = f"token:blacklist:{token_id}"
            return redis_client.exists(key) > 0

        except Exception as e:
            logger.error(f"Failed to check blacklist: {e}")
            return False

    def _should_rotate(self, payload: Dict[str, Any]) -> bool:
        """
        Determine if token should be rotated.

        Rotation criteria:
        - Token age > 50% of lifetime
        - High rotation count
        - Security event detected
        """
        if not self.rotation_enabled:
            return False

        # Check token age
        iat = payload.get("iat")
        exp = payload.get("exp")

        if iat and exp:
            now = datetime.utcnow().timestamp()
            token_lifetime = exp - iat
            token_age = now - iat

            # Rotate if token is more than 50% through its lifetime
            if token_age > (token_lifetime * 0.5):
                return True

        # Check rotation count
        rotation_count = payload.get("rotation_count", 0)
        if rotation_count > 10:
            return True

        return False

    def cleanup_expired_blacklist(self) -> int:
        """
        Clean up expired entries from blacklist.
        Redis handles this automatically with TTL, but this is for manual cleanup.

        Returns:
            Number of entries cleaned
        """
        try:
            # Get sync Redis client from manager
            redis_client = self.redis_manager.get_sync_client()

            pattern = "token:blacklist:*"
            keys = redis_client.keys(pattern)

            cleaned = 0
            for key in keys:
                # Check if key has no TTL (shouldn't happen)
                ttl = redis_client.ttl(key)
                if ttl == -1:  # No TTL set
                    redis_client.delete(key)
                    cleaned += 1

            if cleaned > 0:
                logger.info(f"Cleaned {cleaned} expired blacklist entries")

            return cleaned

        except Exception as e:
            logger.error(f"Failed to cleanup blacklist: {e}")
            return 0


# Singleton instance
_token_rotation_service: Optional[TokenRotationService] = None

def get_token_rotation_service() -> TokenRotationService:
    """Get or create the token rotation service instance."""
    global _token_rotation_service
    if _token_rotation_service is None:
        _token_rotation_service = TokenRotationService()
    return _token_rotation_service
