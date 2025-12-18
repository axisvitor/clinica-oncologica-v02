from typing import Optional, Dict, Any, Set
from datetime import datetime, timedelta
import logging
from collections import defaultdict


from app.models.user import User
from app.repositories.user import UserRepository
from app.utils.security import (
    get_password_hash,
    create_access_token,
    create_refresh_token,
)
from app.schemas.auth import TokenData

# Redis client will be passed as generic object for compatibility
from app.infrastructure.cache import cache, cache_user_data

logger = logging.getLogger(__name__)


class AuthService:
    """Service layer for authentication with enhanced security features"""

    def __init__(self, db: Any, user_repository: UserRepository, redis_client=None):
        self.db = db
        self.repository = user_repository
        self.redis = redis_client  # Compatible with sync/async/wrapper clients

        # Rate limiting configuration
        self.max_attempts = 5  # Max failed attempts per email
        self.max_ip_attempts = 10  # Max failed attempts per IP
        self.lockout_window = 300  # 5 minutes in seconds

        # In-memory fallback when Redis is unavailable (disabled per config)
        self._fallback_enabled = False
        self._blacklisted_tokens: Set[str] = set()
        self._failed_attempts: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "last_attempt": None, "ip_attempts": defaultdict(int)}
        )

    def create_access_token(
        self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT access token using utility function.

        Args:
            data: Payload data to encode in the token
            expires_delta: Custom expiration time, defaults to settings value

        Returns:
            Encoded JWT token string

        Raises:
            ValueError: If data is empty or invalid
        """
        if not data:
            raise ValueError("Token data cannot be empty")

        return create_access_token(data, expires_delta)

    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """
        Create JWT refresh token using utility function.

        Args:
            data: Payload data to encode in the token

        Returns:
            Encoded JWT refresh token string

        Raises:
            ValueError: If data is empty or invalid
        """
        if not data:
            raise ValueError("Token data cannot be empty")

        return create_refresh_token(data)

    def verify_token(
        self, token: str, token_type: str = "access"
    ) -> Optional[TokenData]:
        """
        Verify JWT token and return token data.

        Args:
            token: JWT token string to verify
            token_type: Expected token type ("access" or "refresh")

        Returns:
            TokenData if token is valid, None otherwise
        """
        if not token or not isinstance(token, str) or len(token.strip()) == 0:
            logger.warning("Empty or invalid token provided")
            return None

        # Remove 'Bearer ' prefix if present
        token = token.replace("Bearer ", "").strip()

        # Enforce blacklist (logout)
        if token in self._blacklisted_tokens:
            logger.warning("Blacklisted token used")
            return None

        try:
            # Use the utility function for consistency
            from app.utils.security import verify_token as verify_jwt_token

            token_data = verify_jwt_token(token, token_type)
            if token_data is None:
                logger.warning(f"Token verification failed for type: {token_type}")
                return None

            logger.debug(f"Token verified successfully for user: {token_data.email}")
            return token_data

        except Exception as e:
            logger.error(f"Unexpected error verifying token: {str(e)}")
            return None

    def blacklist_token(self, token: str, exp_timestamp: Optional[int] = None) -> None:
        """Blacklist a JWT token (in-memory minimal implementation)."""
        if not token:
            return
        token = token.replace("Bearer ", "").strip()
        self._blacklisted_tokens.add(token)
        logger.debug("Token added to in-memory blacklist")

    @cache(ttl=1800, key_prefix="user_profile")
    def _get_user_from_token_data(self, token_data: TokenData) -> Optional[User]:
        """
        Get user from validated token data with caching (30 min TTL).

        Args:
            token_data: Validated token data containing user email

        Returns:
            User object if found and active, None otherwise
        """
        logger.debug(f"Fetching user profile from database: {token_data.email}")
        user = self.repository.get_by_email(token_data.email)
        if user is None:
            logger.warning(f"User not found for email: {token_data.email}")
            return None
        if not user.is_active:
            logger.warning(f"Inactive user attempted access: {token_data.email}")
            return None
        return user

    def get_current_user(self, token: str) -> Optional[User]:
        """
        Get current user from JWT token.

        Args:
            token: JWT token string

        Returns:
            User object if token is valid and user exists, None otherwise
        """
        token_data = self.verify_token(token)
        if token_data is None:
            return None
        return self._get_user_from_token_data(token_data)

    def create_user(
        self, email: str, password: str, full_name: str, role: str = "doctor"
    ) -> User:
        """
        Create a new user.

        Args:
            email: User email address
            password: Plain text password
            full_name: User's full name
            role: User role, defaults to "doctor"

        Returns:
            Created User object

        Raises:
            ValueError: If required fields are empty or invalid
        """
        if not email or not email.strip():
            raise ValueError("Email cannot be empty")
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not full_name or not full_name.strip():
            raise ValueError("Full name cannot be empty")

        # Check if user already exists
        existing_user = self.repository.get_by_email(email.strip().lower())
        if existing_user:
            raise ValueError("User with this email already exists")

        hashed_password = get_password_hash(password)
        user_data = {
            "email": email.strip().lower(),
            "hashed_password": hashed_password,
            "full_name": full_name.strip(),
            "role": role,
        }

        logger.info(f"Creating new user with email: {email}")
        user = self.repository.create(user_data)

        # Cache the new user profile
        cache_user_data(str(user.id), user, ttl=1800)
        logger.debug(f"Cached new user profile: {user.id}")

        return user

    async def _is_rate_limited(
        self, email: str, client_ip: Optional[str] = None
    ) -> bool:
        """
        Check if authentication attempts are rate limited using Redis.

        Uses Redis for distributed rate limiting with automatic TTL cleanup.
        Falls back to in-memory storage if Redis is unavailable.

        Configuration:
        - Max 5 failed attempts per email within 5 minutes
        - Max 10 failed attempts per IP address
        - Automatic cleanup via Redis EXPIRE

        Args:
            email: User email address
            client_ip: Client IP address

        Returns:
            True if rate limited, False otherwise
        """
        # Require Redis for distributed rate limiting; if unavailable, skip rate-limit check
        if self.redis and await self._redis_is_connected():
            try:
                return await self._is_rate_limited_redis(email, client_ip)
            except Exception as e:
                logger.error(f"Redis rate limit check error: {e}")
                return False

        # Redis not available: do not fallback to memory
        logger.warning("Rate limit check skipped: Redis not available")
        return False

    async def _is_rate_limited_redis(
        self, email: str, client_ip: Optional[str] = None
    ) -> bool:
        """
        Redis-based rate limiting with distributed counter.
        Args:
            email: User email address
            client_ip: Client IP address

        Returns:
            True if rate limited, False otherwise
        """
        try:
            # Check email-based rate limiting
            email_key = f"rate_limit:email:{email}"
            email_attempts = await self.redis.get(email_key)

            if email_attempts and int(email_attempts) >= self.max_attempts:
                logger.warning(f"Rate limit exceeded for email: {email}")
                return True

            # Check IP-based rate limiting if provided
            if client_ip:
                ip_key = f"rate_limit:ip:{client_ip}"
                ip_attempts = await self.redis.get(ip_key)

                if ip_attempts and int(ip_attempts) >= self.max_ip_attempts:
                    logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Redis rate limit check error: {e}")
            # Fallback to in-memory on error
            if self._fallback_enabled:
                return self._is_rate_limited_memory(email, client_ip)
            return False

    def _is_rate_limited_memory(
        self, email: str, client_ip: Optional[str] = None
    ) -> bool:
        """
        In-memory fallback rate limiting.

        Args:
            email: User email address
            client_ip: Client IP address

        Returns:
            True if rate limited, False otherwise
        """
        now = datetime.utcnow()
        attempts = self._failed_attempts[email]

        # Check if we're within the lockout period
        if attempts["last_attempt"]:
            time_since_last = (now - attempts["last_attempt"]).total_seconds()
            if time_since_last >= self.lockout_window:
                attempts["count"] = 0
                attempts["ip_attempts"].clear()
            elif attempts["count"] >= self.max_attempts:
                return True

        # Check IP-based rate limiting if provided
        if client_ip:
            ip_attempts = attempts["ip_attempts"][client_ip]
            if ip_attempts >= self.max_ip_attempts:
                return True

        return False

    async def _record_failed_attempt(
        self, email: str, client_ip: Optional[str] = None
    ) -> None:
        """
        Record a failed authentication attempt using Redis.

        Args:
            email: User email address
            client_ip: Client IP address
        """
        # Use Redis when available; otherwise do not track in-memory
        if self.redis and await self._redis_is_connected():
            await self._record_failed_attempt_redis(email, client_ip)
        else:
            logger.warning("Failed attempt tracking skipped: Redis not available")

    async def _record_failed_attempt_redis(
        self, email: str, client_ip: Optional[str] = None
    ) -> None:
        """
        Record failed attempt in Redis with automatic TTL.

        Args:
            email: User email address
            client_ip: Client IP address
        """
        try:
            # Increment email-based counter with TTL
            email_key = f"rate_limit:email:{email}"
            current_count = await self.redis.incr(email_key)

            # Set TTL on first attempt
            if current_count == 1:
                await self.redis.expire(email_key, self.lockout_window)

            # Increment IP-based counter with TTL
            if client_ip:
                ip_key = f"rate_limit:ip:{client_ip}"
                ip_count = await self.redis.incr(ip_key)

                if ip_count == 1:
                    await self.redis.expire(ip_key, self.lockout_window)

            logger.warning(
                f"Failed attempt recorded for {email} (count: {current_count})"
            )

        except Exception as e:
            logger.error(f"Redis failed attempt recording error: {e}")

    def _record_failed_attempt_memory(
        self, email: str, client_ip: Optional[str] = None
    ) -> None:
        """
        In-memory fallback for recording failed attempts.

        Args:
            email: User email address
            client_ip: Client IP address
        """
        now = datetime.utcnow()
        attempts = self._failed_attempts[email]

        # Check if lockout window has passed - reset if so
        if attempts["last_attempt"]:
            time_since_last = (now - attempts["last_attempt"]).total_seconds()
            if time_since_last >= self.lockout_window:
                attempts["count"] = 0
                attempts["ip_attempts"].clear()

        attempts["count"] += 1
        attempts["last_attempt"] = now

        if client_ip:
            attempts["ip_attempts"][client_ip] += 1

        logger.warning(
            f"Failed attempt recorded for {email} (count: {attempts['count']})"
        )

    async def _redis_is_connected(self) -> bool:
        """Check if Redis client is connected and available."""
        try:
            if hasattr(self.redis, "ping"):
                # Test async Redis connection
                result = await self.redis.ping()
                return bool(result)
            elif hasattr(self.redis, "get"):
                # Try a simple get operation with async
                await self.redis.get("__connection_test__")
                return True
            else:
                return False
        except Exception as e:
            logger.debug(f"Redis connection check failed: {e}")
            return False

    async def _clear_failed_attempts(self, email: str) -> None:
        """
        Clear failed authentication attempts for a user.

        Args:
            email: User email address
        """
        # Clear from Redis if available
        if self.redis and await self._redis_is_connected():
            try:
                email_key = f"rate_limit:email:{email}"
                await self.redis.delete(email_key)
                logger.debug(f"Cleared Redis failed attempts for {email}")
            except Exception as e:
                logger.error(f"Error clearing Redis failed attempts: {e}")

        # Clear from in-memory fallback
        if email in self._failed_attempts:
            del self._failed_attempts[email]
            logger.debug(f"Cleared in-memory failed attempts for {email}")
