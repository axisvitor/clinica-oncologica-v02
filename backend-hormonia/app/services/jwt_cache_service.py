import hashlib
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import json

from app.core.redis_manager import get_redis_manager
from app.config import settings
from app.services.firebase_auth_service import get_firebase_auth_service

logger = logging.getLogger(__name__)


class JWTCacheService:
    """
    Redis-based JWT validation cache with token blacklist.

    Features:
    - Cache Firebase JWT validation results
    - Dynamic TTL based on token expiration
    - Token blacklist for logout
    - Graceful fallback if Redis unavailable
    """

    def __init__(self):
        """Initialize JWT cache service with Redis manager."""
        self.redis_manager = get_redis_manager()
        self._redis_available = False
        self._firebase_service = None

    async def _ensure_redis_connection(self) -> bool:
        """
        Ensure Redis connection is available.

        Returns:
            True if Redis is available, False otherwise
        """
        if self._redis_available:
            return True

        try:
            redis_client = await self.redis_manager.get_async_client()
            await redis_client.ping()
            self._redis_available = True
            logger.info("Redis connection established for JWT caching")
            return True
        except Exception as e:
            logger.warning(f"Redis unavailable for JWT caching: {e}")
            self._redis_available = False
            return False

    def _hash_token(self, token: str) -> str:
        """
        Create SHA256 hash of token for Redis key.

        Args:
            token: JWT token string

        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(token.encode()).hexdigest()

    def _calculate_ttl(self, claims: dict) -> int:
        """
        Calculate TTL based on JWT exp claim.

        Args:
            claims: JWT claims including 'exp' timestamp

        Returns:
            TTL in seconds (minimum 60, maximum 3600)
        """
        try:
            exp = claims.get('exp')
            if not exp:
                return 1800  # Default 30 minutes

            now = datetime.now(timezone.utc).timestamp()
            ttl = int(exp - now)

            # Clamp TTL between 60 seconds and 1 hour
            return max(60, min(ttl, 3600))
        except Exception as e:
            logger.warning(f"Error calculating TTL: {e}")
            return 1800  # Default 30 minutes

    async def validate_token_cached(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate JWT token with Redis caching.

        Process:
        1. Check if token is blacklisted
        2. Check cache for validation result
        3. If cache miss, validate with Firebase
        4. Cache the validation result

        Args:
            token: JWT token string

        Returns:
            Firebase user claims dict if valid, None otherwise
        """
        if not token:
            return None

        # Normalize token
        token = token.strip()
        if token.startswith('Bearer '):
            token = token[7:]

        token_hash = self._hash_token(token)

        # Check if token is blacklisted
        if await self.is_blacklisted(token_hash):
            logger.info("Token is blacklisted (logged out)")
            return None

        # Check cache first
        redis_available = await self._ensure_redis_connection()
        if redis_available:
            cached_data = await self._get_cached_validation(token_hash)
            if cached_data:
                logger.debug(f"JWT validation cache HIT for token hash: {token_hash[:16]}...")
                return cached_data
            logger.debug(f"JWT validation cache MISS for token hash: {token_hash[:16]}...")

        # Cache miss or Redis unavailable - validate via Firebase
        firebase_data = await self._validate_with_firebase(token)
        if not firebase_data:
            return None

        # Cache the validation result
        if redis_available:
            ttl = self._calculate_ttl(firebase_data)
            await self.cache_validation(token_hash, firebase_data, ttl)

        return firebase_data

    async def _get_cached_validation(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get cached validation result from Redis.

        Args:
            token_hash: SHA256 hash of token

        Returns:
            Cached user data dict or None
        """
        try:
            redis_client = await self.redis_manager.get_async_client()
            cache_key = f"jwt:validation:{token_hash}"

            cached_json = await redis_client.get(cache_key)
            if cached_json:
                return json.loads(cached_json)
            return None
        except Exception as e:
            logger.error(f"Error retrieving cached validation: {e}")
            return None

    def _get_firebase_service(self):
        """Lazily initialize and cache Firebase auth service."""
        if self._firebase_service is None:
            if not all([
                settings.FIREBASE_ADMIN_PROJECT_ID,
                settings.FIREBASE_ADMIN_PRIVATE_KEY,
                settings.FIREBASE_ADMIN_CLIENT_EMAIL
            ]):
                raise RuntimeError("Firebase credentials not configured for JWT validation")

            self._firebase_service = get_firebase_auth_service(
                project_id=settings.FIREBASE_ADMIN_PROJECT_ID,
                private_key=settings.FIREBASE_ADMIN_PRIVATE_KEY.replace("\\n", "\n"),
                client_email=settings.FIREBASE_ADMIN_CLIENT_EMAIL
            )
        return self._firebase_service

    async def _validate_with_firebase(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate JWT token using Firebase Admin SDK.

        Args:
            token: Firebase ID token string

        Returns:
            Firebase user claims dict or None
        """
        try:
            firebase_service = self._get_firebase_service()
            claims = await firebase_service.verify_token(token)
            logger.debug(f"Token validated via Firebase for email: {claims.get('email')}")
            return claims
        except Exception as exc:
            logger.error(f"Error validating token with Firebase: {exc}")
            return None

    async def cache_validation(
        self,
        token_hash: str,
        claims: Dict[str, Any],
        ttl: int
    ) -> bool:
        """
        Cache JWT validation result in Redis.

        Args:
            token_hash: SHA256 hash of token
            claims: Firebase user claims to cache
            ttl: Time-to-live in seconds

        Returns:
            True if cached successfully, False otherwise
        """
        try:
            redis_client = await self.redis_manager.get_async_client()
            cache_key = f"jwt:validation:{token_hash}"

            # Serialize claims to JSON
            claims_json = json.dumps(claims)

            # Set with TTL
            await redis_client.setex(cache_key, ttl, claims_json)
            logger.debug(f"Cached JWT validation for {ttl}s: {token_hash[:16]}...")
            return True

        except Exception as e:
            logger.error(f"Error caching validation: {e}")
            return False

    async def invalidate_token(self, token: str) -> bool:
        """
        Invalidate token by adding to blacklist (for logout).

        Args:
            token: JWT token string to blacklist

        Returns:
            True if blacklisted successfully, False otherwise
        """
        if not token:
            return False

        # Normalize token
        token = token.strip()
        if token.startswith('Bearer '):
            token = token[7:]

        token_hash = self._hash_token(token)

        redis_available = await self._ensure_redis_connection()
        if not redis_available:
            logger.warning("Cannot blacklist token: Redis unavailable")
            return False

        try:
            redis_client = await self.redis_manager.get_async_client()
            blacklist_key = f"jwt:blacklist:{token_hash}"

            # Blacklist for 24 hours (covers most JWT expiration times)
            await redis_client.setex(blacklist_key, 86400, "1")

            # Also invalidate cached validation
            cache_key = f"jwt:validation:{token_hash}"
            await redis_client.delete(cache_key)

            logger.info(f"Token blacklisted (logout): {token_hash[:16]}...")
            return True

        except Exception as e:
            logger.error(f"Error blacklisting token: {e}")
            return False

    async def is_blacklisted(self, token_or_hash: str) -> bool:
        """
        Check if token is blacklisted.

        Args:
            token_or_hash: JWT token string or pre-computed hash

        Returns:
            True if blacklisted, False otherwise
        """
        redis_available = await self._ensure_redis_connection()
        if not redis_available:
            # If Redis unavailable, cannot check blacklist
            return False

        try:
            # Determine if input is token or hash
            if len(token_or_hash) == 64 and all(c in '0123456789abcdef' for c in token_or_hash):
                token_hash = token_or_hash  # Already a hash
            else:
                # Normalize token
                token = token_or_hash.strip()
                if token.startswith('Bearer '):
                    token = token[7:]
                token_hash = self._hash_token(token)

            redis_client = await self.redis_manager.get_async_client()
            blacklist_key = f"jwt:blacklist:{token_hash}"

            exists = await redis_client.exists(blacklist_key)
            return bool(exists)

        except Exception as e:
            logger.error(f"Error checking blacklist: {e}")
            return False


# Global service instance
_jwt_cache_service: Optional[JWTCacheService] = None


def get_jwt_cache_service() -> JWTCacheService:
    """
    Get or create global JWT cache service instance.

    Returns:
        JWTCacheService instance
    """
    global _jwt_cache_service
    if _jwt_cache_service is None:
        _jwt_cache_service = JWTCacheService()
    return _jwt_cache_service
