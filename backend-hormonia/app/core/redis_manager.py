"""
Redis Manager - Unified Redis Client Management

Provides both async and sync Redis interfaces with automatic compatibility detection.
Manages connection pooling, error handling, and proper resource cleanup.
"""

import logging
import asyncio
import os
import hashlib
import json
from typing import Optional, Union, Any, Dict, List
import redis.asyncio as redis_async
import redis as redis_sync
from redis.exceptions import ConnectionError, TimeoutError
from contextlib import asynccontextmanager
import threading
import concurrent.futures

from app.config import settings
from datetime import datetime, timedelta
from app.models.user import User  # Import User model for type hints

logger = logging.getLogger(__name__)


# =============================================================================
# FIREBASE REDIS CACHE - 3-LAYER CACHING SYSTEM
# =============================================================================

class FirebaseRedisCache:
    """
    3-Layer Redis cache for Firebase authentication.

    Layer 1: Token Validation Cache - 1 hour TTL (40x faster: 200ms → 5ms)
    Layer 2: User Object Cache - 2 hours TTL (20x faster: 100ms → 5ms)
    Layer 3: Session Management - 24 hours TTL (instant logout control)

    Performance:
    - Cold request: ~250ms (Firebase + DB + cache write)
    - Warm request: ~105ms (token cache hit, DB query)
    - Hot request: ~5ms (full cache hit)
    - Expected hit rate: 95-98% after warm-up
    """

    def __init__(self, redis_client=None):
        """
        Initialize Firebase cache with Redis client.

        Args:
            redis_client: Redis client instance (async or sync). If None, uses default sync client.
        """
        if redis_client is None:
            # Get default Redis client from manager
            redis_manager = get_redis_manager()
            redis_client = redis_manager.get_compatible_client('sync')

        self.redis = redis_client

        # Cache TTL configuration (from settings or defaults)
        self.token_ttl = getattr(settings, 'FIREBASE_TOKEN_CACHE_TTL', 3600)  # 1 hour
        self.user_ttl = getattr(settings, 'FIREBASE_USER_CACHE_TTL', 7200)   # 2 hours
        self.session_ttl = getattr(settings, 'FIREBASE_SESSION_TTL', 86400)  # 24 hours

    # === LAYER 1: TOKEN VALIDATION CACHE ===

    def cache_validated_token(
        self,
        id_token: str,
        user_data: Dict[str, Any],
        ttl_seconds: Optional[int] = None
    ) -> None:
        """
        Cache Firebase validated token (Layer 1).

        Reduces Firebase Admin SDK calls from 200ms to 5ms (40x faster).

        Args:
            id_token: Firebase ID token
            user_data: Validated user data from Firebase
            ttl_seconds: Custom TTL (defaults to self.token_ttl)
        """
        ttl = ttl_seconds or self.token_ttl
        token_hash = hashlib.sha256(id_token.encode()).hexdigest()
        key = f"firebase:token:{token_hash}"

        cache_data = {
            "firebase_uid": user_data["uid"],
            "email": user_data.get("email"),
            "role": user_data.get("role"),
            "validated_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(seconds=ttl)).isoformat()
        }

        self.redis.setex(key, ttl, json.dumps(cache_data))
        logger.debug(f"💾 Token cached: {user_data.get('email')} (TTL: {ttl}s)")

    def get_cached_token(self, id_token: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve validated token from cache (Layer 1).

        Args:
            id_token: Firebase ID token

        Returns:
            Cached token data or None if miss
        """
        token_hash = hashlib.sha256(id_token.encode()).hexdigest()
        key = f"firebase:token:{token_hash}"

        cached = self.redis.get(key)
        if cached:
            logger.debug(f"✅ Token cache HIT: {key[:16]}...")
            return json.loads(cached)

        logger.debug(f"❌ Token cache MISS: {key[:16]}...")
        return None

    def invalidate_token(self, id_token: str) -> None:
        """Invalidate cached token immediately."""
        token_hash = hashlib.sha256(id_token.encode()).hexdigest()
        key = f"firebase:token:{token_hash}"
        self.redis.delete(key)
        logger.debug(f"🗑️ Token cache invalidated: {key[:16]}...")

    # === LAYER 2: USER OBJECT CACHE ===

    def cache_user(
        self,
        firebase_uid: str,
        user_dict: Dict[str, Any],
        ttl_seconds: Optional[int] = None
    ) -> None:
        """
        Cache User object (Layer 2).

        Reduces PostgreSQL queries from 100ms to 5ms (20x faster).

        Args:
            firebase_uid: Firebase user ID
            user_dict: User data dictionary
            ttl_seconds: Custom TTL (defaults to self.user_ttl)
        """
        ttl = ttl_seconds or self.user_ttl
        key = f"user:firebase_uid:{firebase_uid}"

        cache_data = {
            **user_dict,
            "cached_at": datetime.utcnow().isoformat()
        }

        self.redis.setex(key, ttl, json.dumps(cache_data))
        logger.debug(f"💾 User cached: {firebase_uid} (TTL: {ttl}s)")

    def get_cached_user(self, firebase_uid: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve User from cache (Layer 2).

        Args:
            firebase_uid: Firebase user ID

        Returns:
            Cached user data or None if miss
        """
        key = f"user:firebase_uid:{firebase_uid}"

        cached = self.redis.get(key)
        if cached:
            logger.debug(f"✅ User cache HIT: {firebase_uid}")
            return json.loads(cached)

        logger.debug(f"❌ User cache MISS: {firebase_uid}")
        return None

    def invalidate_user_cache(self, firebase_uid: str) -> None:
        """
        Invalidate user cache (call after user update/delete).

        Args:
            firebase_uid: Firebase user ID
        """
        key = f"user:firebase_uid:{firebase_uid}"
        self.redis.delete(key)
        logger.debug(f"🗑️ User cache invalidated: {firebase_uid}")

    # === LAYER 3: SESSION MANAGEMENT ===

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        firebase_uid: str,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None,
        ttl: Optional[int] = None  # Alternative parameter name for compatibility
    ) -> bool:
        """
        Create Redis session (Layer 3) - ASYNC VERSION.

        Enables instant logout control and activity tracking.

        Args:
            session_id: Unique session identifier
            user_id: Database user ID
            firebase_uid: Firebase user ID
            metadata: Additional session data (device, IP, etc.)
            ttl_seconds: Custom TTL (defaults to self.session_ttl)
            ttl: Alternative TTL parameter (for compatibility)

        Returns:
            True if session was created successfully
        """
        ttl_value = ttl or ttl_seconds or self.session_ttl
        key = f"session:{session_id}"

        session_data = {
            "user_id": user_id,
            "firebase_uid": firebase_uid,
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            **(metadata or {})
        }

        try:
            await asyncio.to_thread(
                self.redis.setex,
                key,
                ttl_value,
                json.dumps(session_data)
            )
            logger.info(f"🔐 Session created: {session_id[:16]}... (TTL: {ttl_value}s)")
            return True
        except Exception as e:
            logger.error(f"Failed to create session: {str(e)}")
            return False

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve active session and update last_activity - ASYNC VERSION.

        Args:
            session_id: Session identifier

        Returns:
            Session data or None if expired/invalid
        """
        key = f"session:{session_id}"

        try:
            cached = await asyncio.to_thread(self.redis.get, key)
            if cached:
                # Update last_activity timestamp
                session_data = json.loads(cached)
                session_data["last_activity"] = datetime.utcnow().isoformat()

                # Refresh TTL on activity
                await asyncio.to_thread(
                    self.redis.setex,
                    key,
                    self.session_ttl,
                    json.dumps(session_data)
                )
                logger.debug(f"✅ Session active: {session_id[:16]}...")
                return session_data

            logger.debug(f"❌ Session not found: {session_id[:16]}...")
            return None
        except Exception as e:
            logger.error(f"Error getting session: {str(e)}")
            return None

    async def invalidate_session(self, session_id: str) -> bool:
        """
        Logout - invalidate single session - ASYNC VERSION.

        Args:
            session_id: Session identifier

        Returns:
            True if session existed and was deleted
        """
        key = f"session:{session_id}"

        try:
            deleted = await asyncio.to_thread(self.redis.delete, key)

            if deleted:
                logger.info(f"🚪 Session logged out: {session_id[:16]}...")
                return True
            else:
                logger.debug(f"⚠️ Session already expired: {session_id[:16]}...")
                return False
        except Exception as e:
            logger.error(f"Error invalidating session: {str(e)}")
            return False

    async def invalidate_all_user_sessions(self, firebase_uid: str) -> int:
        """
        Logout global - invalidate ALL sessions for a user - ASYNC VERSION.

        Use case: Password change, account compromise, admin force-logout.

        Args:
            firebase_uid: Firebase user ID

        Returns:
            Number of sessions deleted
        """
        pattern = "session:*"
        deleted = 0

        try:
            # Scan all session keys
            for key in await asyncio.to_thread(list, self.redis.scan_iter(match=pattern)):
                session_data = await asyncio.to_thread(self.redis.get, key)
                if session_data:
                    data = json.loads(session_data)
                    if data.get("firebase_uid") == firebase_uid:
                        await asyncio.to_thread(self.redis.delete, key)
                        deleted += 1

            logger.info(f"🚪 Global logout: {deleted} sessions deleted for {firebase_uid}")
            return deleted
        except Exception as e:
            logger.error(f"Error invalidating user sessions: {str(e)}")
            return 0

    def list_user_sessions(self, firebase_uid: str) -> List[Dict[str, Any]]:
        """
        List all active sessions for a user.

        Args:
            firebase_uid: Firebase user ID

        Returns:
            List of active session data
        """
        pattern = "session:*"
        sessions = []

        for key in self.redis.scan_iter(match=pattern):
            session_data = self.redis.get(key)
            if session_data:
                data = json.loads(session_data)
                if data.get("firebase_uid") == firebase_uid:
                    # Extract session_id from key
                    session_id = key.split(":", 1)[1] if ":" in key else key
                    data["session_id"] = session_id
                    sessions.append(data)

        logger.debug(f"📊 Active sessions for {firebase_uid}: {len(sessions)}")
        return sessions

    # === CACHE METRICS & MONITORING ===

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics and health metrics.

        Returns:
            Dictionary with cache metrics
        """
        stats = {
            "token_cache_ttl": self.token_ttl,
            "user_cache_ttl": self.user_ttl,
            "session_ttl": self.session_ttl,
            "redis_connection": "healthy" if self.redis.ping() else "unhealthy"
        }

        # Count active sessions
        session_count = 0
        for _ in self.redis.scan_iter(match="session:*"):
            session_count += 1
        stats["active_sessions"] = session_count

        return stats

    # === MISSING METHODS FOR CODE COMPATIBILITY ===

    async def get_user_by_uid(self, firebase_uid: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve user data by Firebase UID from cache (async version of get_cached_user).

        Args:
            firebase_uid: Firebase user ID

        Returns:
            Cached user data or None if miss
        """
        key = f"user:firebase_uid:{firebase_uid}"

        # Use asyncio.to_thread for sync Redis operations
        cached = await asyncio.to_thread(self.redis.get, key)
        if cached:
            logger.debug(f"✅ User cache HIT: {firebase_uid}")
            return json.loads(cached)

        logger.debug(f"❌ User cache MISS: {firebase_uid}")
        return None

    async def cache_user_data(
        self,
        firebase_uid: str,
        user_data: Dict[str, Any],
        ttl: int = 900
    ) -> None:
        """
        Cache user data by Firebase UID (async version).

        Args:
            firebase_uid: Firebase user ID
            user_data: User data dictionary
            ttl: Time-to-live in seconds (default: 900 = 15 minutes)
        """
        key = f"user:firebase_uid:{firebase_uid}"

        cache_data = {
            **user_data,
            "cached_at": datetime.utcnow().isoformat()
        }

        await asyncio.to_thread(
            self.redis.setex,
            key,
            ttl,
            json.dumps(cache_data)
        )
        logger.debug(f"💾 User data cached: {firebase_uid} (TTL: {ttl}s)")

    async def get_or_create_user(
        self,
        db,
        firebase_uid: str,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
        photo_url: Optional[str] = None
    ) -> Optional[User]:
        """
        Get user from cache/database or create new user.

        Args:
            db: Database session
            firebase_uid: Firebase user ID
            email: User email
            display_name: User display name
            photo_url: User photo URL

        Returns:
            User object or None if creation fails
        """
        from app.models.user import User, UserRole
        from sqlalchemy import select

        # Try cache first
        cached_user = await self.get_user_by_uid(firebase_uid)
        if cached_user:
            # Convert dict to User object
            user = User(
                id=cached_user.get("id"),
                firebase_uid=cached_user["firebase_uid"],
                email=cached_user["email"],
                full_name=cached_user.get("full_name"),
                role=UserRole[cached_user.get("role", "DOCTOR").upper()],
                is_active=cached_user.get("is_active", True)
            )
            return user

        # Query database
        stmt = select(User).where(User.firebase_uid == firebase_uid)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            # Cache existing user
            user_dict = {
                "id": user.id,
                "firebase_uid": user.firebase_uid,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
                "is_active": user.is_active
            }
            await self.cache_user_data(firebase_uid, user_dict, ttl=self.user_ttl)
            return user

        # Create new user if email provided
        if not email:
            logger.error(f"Cannot create user without email for firebase_uid: {firebase_uid}")
            return None

        try:
            new_user = User(
                firebase_uid=firebase_uid,
                email=email,
                full_name=display_name or email.split("@")[0],
                role=UserRole.DOCTOR,  # Default role
                is_active=True
            )
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)

            # Cache new user
            user_dict = {
                "id": new_user.id,
                "firebase_uid": new_user.firebase_uid,
                "email": new_user.email,
                "full_name": new_user.full_name,
                "role": new_user.role.value if hasattr(new_user.role, 'value') else str(new_user.role),
                "is_active": new_user.is_active
            }
            await self.cache_user_data(firebase_uid, user_dict, ttl=self.user_ttl)

            logger.info(f"✅ Created and cached new user: {email}")
            return new_user

        except Exception as e:
            logger.error(f"Failed to create user: {str(e)}")
            await db.rollback()
            return None

    async def get_session_ttl(self, session_id: str) -> int:
        """
        Get remaining TTL for a session.

        Args:
            session_id: Session identifier

        Returns:
            Remaining TTL in seconds, or -1 if session doesn't exist
        """
        key = f"session:{session_id}"

        try:
            ttl = await asyncio.to_thread(self.redis.ttl, key)
            return ttl if ttl > 0 else -1
        except Exception as e:
            logger.error(f"Error getting session TTL: {str(e)}")
            return -1


class RedisManager:
    """
    Unified Redis manager providing both async and sync interfaces.

    Features:
    - Automatic client type detection
    - Connection pooling for both sync and async
    - Error handling and retry logic
    - Resource cleanup
    - Interface compatibility layer
    """

    def __init__(self, db_number: Optional[int] = None):
        self._async_client: Optional[redis_async.Redis] = None
        self._sync_client: Optional[redis_sync.Redis] = None
        self._async_pool: Optional[redis_async.ConnectionPool] = None
        self._sync_pool: Optional[redis_sync.ConnectionPool] = None
        self._lock = threading.Lock()

        # Connection settings (use Redis Cloud URL from settings)
        self.redis_url = settings.REDIS_URL

        # SSL is now configured manually via connection_kwargs (see _create_*_client methods)
        # This approach works better with Python 3.13's strict SSL validation
        # No need to convert redis:// to rediss:// - we configure SSL parameters directly

        # DB isolation support
        self.db_number = db_number
        if db_number is not None and getattr(settings, 'REDIS_ENABLE_DB_ISOLATION', True):
            # Override DB in URL if isolation is enabled
            base_url = self.redis_url.rsplit('/', 1)[0] if '/' in self.redis_url else self.redis_url
            self.redis_url = f"{base_url}/{db_number}"
            logger.info(f"Redis DB isolation enabled: using DB {db_number}")

        # Connection settings from config - Aumentados para evitar timeouts
        self.decode_responses = getattr(settings, 'REDIS_DECODE_RESPONSES', True)
        self.socket_timeout = getattr(settings, 'REDIS_SOCKET_TIMEOUT', 30.0)  # Aumentado de 10 para 30
        self.socket_connect_timeout = getattr(settings, 'REDIS_SOCKET_CONNECT_TIMEOUT', 30.0)  # Aumentado de 5 para 30
        self.retry_on_timeout = getattr(settings, 'REDIS_RETRY_ON_TIMEOUT', True)
        self.health_check_interval = getattr(settings, 'REDIS_HEALTH_CHECK_INTERVAL', 30)
        self.max_connections = getattr(settings, 'REDIS_MAX_CONNECTIONS', 50)

    async def get_async_client(self) -> redis_async.Redis:
        """
        Get or create async Redis client.

        Returns:
            Async Redis client instance
        """
        if self._async_client is None:
            await self._create_async_client()
        return self._async_client

    def get_sync_client(self) -> redis_sync.Redis:
        """
        Get or create sync Redis client.

        Returns:
            Sync Redis client instance
        """
        if self._sync_client is None:
            with self._lock:
                if self._sync_client is None:
                    self._create_sync_client()
        return self._sync_client

    async def _create_async_client(self):
        """
        Create async Redis client with connection pool.

        SSL is configured using SSLContext for Python 3.13 compatibility.
        This is the correct approach for redis-py 5.x with Python 3.13.
        """
        try:
            import ssl

            # Base connection configuration
            connection_kwargs = {
                'decode_responses': self.decode_responses,
                'socket_timeout': self.socket_timeout,
                'socket_connect_timeout': self.socket_connect_timeout,
                'retry_on_timeout': self.retry_on_timeout,
                'retry_on_error': [ConnectionError, TimeoutError],
                'max_connections': self.max_connections,
                'health_check_interval': self.health_check_interval
            }

            # FIXED: redis-py 6.0+ handles rediss:// URLs automatically
            # We only pass ssl_cert_reqs, ssl_check_hostname (NOT ssl_context or ssl=True)
            # Since .env already defines REDIS_URL with rediss://, no URL rewriting needed
            redis_url = self.redis_url

            if settings.REDIS_SSL:
                import ssl
                ssl_cert_reqs = getattr(settings, 'REDIS_SSL_CERT_REQS', 'required').lower()

                # Configure SSL certificate validation level
                if ssl_cert_reqs == 'none':
                    connection_kwargs['ssl_cert_reqs'] = ssl.CERT_NONE
                    connection_kwargs['ssl_check_hostname'] = False
                    logger.info("Redis async SSL: Certificate verification DISABLED (CERT_NONE)")
                elif ssl_cert_reqs == 'optional':
                    connection_kwargs['ssl_cert_reqs'] = ssl.CERT_OPTIONAL
                    logger.info("Redis async SSL: Certificate verification OPTIONAL")
                else:  # 'required'
                    connection_kwargs['ssl_cert_reqs'] = ssl.CERT_REQUIRED
                    connection_kwargs['ssl_check_hostname'] = True  # SEC-002: Explicit hostname verification

                    # Use CA certificate for validation if provided
                    ssl_ca_certs = getattr(settings, 'REDIS_SSL_CA_CERTS', None)
                    if ssl_ca_certs:
                        import os
                        # Support both absolute and relative paths
                        if os.path.isabs(ssl_ca_certs):
                            ca_path = ssl_ca_certs
                        else:
                            ca_path = os.path.join(settings.BASE_DIR, ssl_ca_certs)

                        if os.path.exists(ca_path):
                            connection_kwargs['ssl_ca_certs'] = ca_path
                            logger.info(f"Redis async SSL: Using CA certificate from {ssl_ca_certs}")
                        else:
                            logger.error(f"Redis CA certificate not found at {ca_path}. Falling back to certifi.")
                            ssl_ca_certs = None  # Trigger fallback below

                    # Fallback to certifi if no custom CA specified
                    if not ssl_ca_certs:
                        try:
                            import certifi
                            connection_kwargs['ssl_ca_certs'] = certifi.where()
                            logger.info(f"Redis async SSL: Using certifi CA bundle: {certifi.where()}")
                        except ImportError:
                            logger.warning("Redis async SSL: certifi not available, using system CA store")

                    logger.info("Redis async SSL: Certificate verification REQUIRED")

                # FIX: Add explicit TLS version support for Redis Cloud compatibility
                # Python 3.13 + OpenSSL 3.x defaults to TLS 1.3, but some Redis Cloud
                # instances require TLS 1.2. Allow configuration via environment variable.
                ssl_min_version = getattr(settings, 'REDIS_SSL_MIN_VERSION', None)
                if ssl_min_version:
                    ssl_min_version = ssl_min_version.upper()
                    if ssl_min_version == 'TLSV1_2':
                        connection_kwargs['ssl_min_version'] = ssl.TLSVersion.TLSv1_2
                        logger.info("Redis async SSL: Enforcing minimum TLS version 1.2")
                    elif ssl_min_version == 'TLSV1_3':
                        connection_kwargs['ssl_min_version'] = ssl.TLSVersion.TLSv1_3
                        logger.info("Redis async SSL: Enforcing minimum TLS version 1.3")
                    else:
                        logger.warning(f"Invalid REDIS_SSL_MIN_VERSION: {ssl_min_version}. Ignoring.")
                else:
                    logger.info("Redis async SSL: Using Python default TLS version negotiation")

                # Validate URL scheme matches SSL config
                if not redis_url.startswith('rediss://'):
                    logger.error(f"REDIS_SSL=true but URL uses {redis_url.split('://')[0]}:// scheme. Fix .env to use rediss://")
            else:
                # Warn if SSL URL used without REDIS_SSL=true
                if redis_url.startswith('rediss://'):
                    logger.warning("URL uses rediss:// but REDIS_SSL=false. Connection may fail.")
                logger.info("Redis async: Using non-SSL connection")

            # Create async connection pool - from_url() handles SSL via rediss:// + ssl_cert_reqs
            self._async_pool = redis_async.ConnectionPool.from_url(
                redis_url,
                **connection_kwargs
            )

            # Create client from pool
            self._async_client = redis_async.Redis(connection_pool=self._async_pool)

            # Test connection
            await self._async_client.ping()
            logger.info("Async Redis client connected successfully")

        except Exception as e:
            logger.error(f"Failed to create async Redis client: {e}")
            raise

    def _create_sync_client(self):
        """
        Create sync Redis client with connection pool.

        SSL is configured using SSLContext for Python 3.13 compatibility.
        This is the correct approach for redis-py 5.x with Python 3.13.
        """
        try:
            import ssl

            # Base connection configuration
            connection_kwargs = {
                'decode_responses': self.decode_responses,
                'socket_timeout': self.socket_timeout,
                'socket_connect_timeout': self.socket_connect_timeout,
                'retry_on_timeout': self.retry_on_timeout,
                'retry_on_error': [ConnectionError, TimeoutError],
                'max_connections': self.max_connections,
                'health_check_interval': self.health_check_interval
            }

            # Configure SSL if enabled
            redis_url = self.redis_url
            if settings.REDIS_SSL:
                # Change redis:// to rediss:// for SSL
                if redis_url.startswith('redis://'):
                    redis_url = 'rediss://' + redis_url[8:]
                logger.info("Redis sync SSL: Enabled with rediss:// scheme")
            else:
                # Ensure using non-SSL scheme
                if redis_url.startswith('rediss://'):
                    redis_url = 'redis://' + redis_url[9:]
                logger.info("Redis sync: Using non-SSL connection")

            # Create sync connection pool
            # NOTE: Do NOT pass ssl_cert_reqs/ssl_check_hostname as kwargs
            # redis-py 6.0+ handles SSL via URL scheme (rediss://) automatically
            self._sync_pool = redis_sync.ConnectionPool.from_url(
                redis_url,
                **connection_kwargs
            )

            # Create client from pool
            self._sync_client = redis_sync.Redis(connection_pool=self._sync_pool)

            # Test connection
            self._sync_client.ping()
            logger.info("Sync Redis client connected successfully")

        except Exception as e:
            logger.error(f"Failed to create sync Redis client: {e}")
            raise

    async def close_async(self):
        """Close async Redis connections."""
        try:
            if self._async_client:
                await self._async_client.aclose()
                self._async_client = None
                logger.debug("Async Redis client closed")

            if self._async_pool:
                await self._async_pool.aclose()
                self._async_pool = None
                logger.debug("Async Redis pool closed")

        except Exception as e:
            logger.error(f"Error closing async Redis connections: {e}")

    def close_sync(self):
        """Close sync Redis connections."""
        try:
            with self._lock:
                if self._sync_client:
                    self._sync_client.close()
                    self._sync_client = None
                    logger.debug("Sync Redis client closed")

                if self._sync_pool:
                    self._sync_pool.disconnect()
                    self._sync_pool = None
                    logger.debug("Sync Redis pool closed")

        except Exception as e:
            logger.error(f"Error closing sync Redis connections: {e}")

    async def close_all(self):
        """Close all Redis connections."""
        await self.close_async()
        self.close_sync()

    def get_compatible_client(self, preferred_type: str = "auto") -> Union[redis_async.Redis, redis_sync.Redis, 'CompatibilityWrapper']:
        """
        Get Redis client with automatic compatibility detection.

        Args:
            preferred_type: "async", "sync", or "auto" (default)

        Returns:
            Redis client or compatibility wrapper
        """
        if preferred_type == "async":
            # Return async client wrapped for sync compatibility if needed
            return AsyncToSyncWrapper(self)
        elif preferred_type == "sync":
            return self.get_sync_client()
        else:
            # Auto-detect based on current context
            try:
                # Check if we're in an async context
                asyncio.get_running_loop()
                return AsyncToSyncWrapper(self)  # Use wrapper for mixed usage
            except RuntimeError:
                # No event loop, use sync client
                return self.get_sync_client()


class AsyncToSyncWrapper:
    """
    Wrapper that provides sync interface for async Redis operations.

    This allows services expecting sync Redis to work with async Redis clients
    without major refactoring.
    """

    def __init__(self, redis_manager: RedisManager):
        self.redis_manager = redis_manager
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    def _run_async(self, coro):
        """Run async coroutine in sync context."""
        try:
            # Try to get current loop
            loop = asyncio.get_running_loop()

            # We're in async context, run in thread to avoid blocking
            future = self._executor.submit(self._run_in_new_loop, coro)
            return future.result(timeout=30)  # 30 second timeout

        except RuntimeError:
            # No running loop, safe to create new one
            try:
                return asyncio.run(coro)
            except Exception as e:
                logger.error(f"Failed to run coroutine with asyncio.run: {e}")
                # Fallback to manual loop management
                return self._run_in_new_loop(coro)
        except concurrent.futures.TimeoutError:
            logger.error("Redis operation timed out after 30 seconds")
            raise TimeoutError("Redis operation timed out")

    def _run_in_new_loop(self, coro):
        """Run coroutine in new event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def get(self, key: str) -> Optional[str]:
        """Sync wrapper for get operation."""
        async def _get():
            client = await self.redis_manager.get_async_client()
            return await client.get(key)

        try:
            return self._run_async(_get())
        except Exception as e:
            logger.error(f"Redis GET error: {e}")
            return None

    def set(self, key: str, value: Any, ex: Optional[int] = None, **kwargs) -> bool:
        """Sync wrapper for set operation."""
        async def _set():
            client = await self.redis_manager.get_async_client()
            return await client.set(key, value, ex=ex, **kwargs)

        try:
            return self._run_async(_set())
        except Exception as e:
            logger.error(f"Redis SET error: {e}")
            return False

    def setex(self, key: str, seconds: int, value: Any) -> bool:
        """Sync wrapper for setex operation."""
        async def _setex():
            client = await self.redis_manager.get_async_client()
            return await client.setex(key, seconds, value)

        try:
            return self._run_async(_setex())
        except Exception as e:
            logger.error(f"Redis SETEX error: {e}")
            return False

    def delete(self, *keys: str) -> int:
        """Sync wrapper for delete operation."""
        async def _delete():
            client = await self.redis_manager.get_async_client()
            return await client.delete(*keys)

        try:
            return self._run_async(_delete())
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")
            return 0

    def exists(self, *keys: str) -> int:
        """Sync wrapper for exists operation."""
        async def _exists():
            client = await self.redis_manager.get_async_client()
            return await client.exists(*keys)

        try:
            return self._run_async(_exists())
        except Exception as e:
            logger.error(f"Redis EXISTS error: {e}")
            return 0

    def expire(self, key: str, seconds: int) -> bool:
        """Sync wrapper for expire operation."""
        async def _expire():
            client = await self.redis_manager.get_async_client()
            return await client.expire(key, seconds)

        try:
            return self._run_async(_expire())
        except Exception as e:
            logger.error(f"Redis EXPIRE error: {e}")
            return False

    def rpush(self, key: str, *values) -> int:
        """Sync wrapper for rpush operation."""
        async def _rpush():
            client = await self.redis_manager.get_async_client()
            return await client.rpush(key, *values)

        try:
            return self._run_async(_rpush())
        except Exception as e:
            logger.error(f"Redis RPUSH error: {e}")
            return 0

    def lpop(self, key: str) -> Optional[str]:
        """Sync wrapper for lpop operation."""
        async def _lpop():
            client = await self.redis_manager.get_async_client()
            return await client.lpop(key)

        try:
            return self._run_async(_lpop())
        except Exception as e:
            logger.error(f"Redis LPOP error: {e}")
            return None

    def ping(self) -> bool:
        """Sync wrapper for ping operation."""
        async def _ping():
            client = await self.redis_manager.get_async_client()
            return await client.ping()

        try:
            result = self._run_async(_ping())
            return bool(result)
        except Exception as e:
            logger.error(f"Redis PING error: {e}")
            return False

    def close(self):
        """Close wrapper resources."""
        self._executor.shutdown(wait=False)


# Global Redis manager instances
_redis_manager: Optional[RedisManager] = None
_redis_cache_manager: Optional[RedisManager] = None
_redis_broker_manager: Optional[RedisManager] = None


def get_redis_manager(db_number: Optional[int] = None) -> RedisManager:
    """
    Get or create global Redis manager instance.

    Args:
        db_number: Optional Redis DB number for isolation (0-15)

    Returns:
        RedisManager instance
    """
    global _redis_manager
    if db_number is None:
        if _redis_manager is None:
            _redis_manager = RedisManager()
        return _redis_manager
    else:
        # Create isolated manager for specific DB
        return RedisManager(db_number=db_number)


def get_cache_redis_manager() -> RedisManager:
    """
    Get Redis manager for cache operations (DB 1 by default).

    Returns:
        RedisManager instance configured for cache
    """
    global _redis_cache_manager
    if _redis_cache_manager is None:
        cache_db = getattr(settings, 'REDIS_CACHE_DB', 1)
        _redis_cache_manager = RedisManager(db_number=cache_db)
    return _redis_cache_manager


def get_broker_redis_manager() -> RedisManager:
    """
    Get Redis manager for Celery broker operations (DB 0 by default).

    Note: Celery manages its own connections via CELERY_BROKER_URL.
    This is for direct broker inspection/management only.

    Returns:
        RedisManager instance configured for broker
    """
    global _redis_broker_manager
    if _redis_broker_manager is None:
        broker_db = getattr(settings, 'REDIS_BROKER_DB', 0)
        _redis_broker_manager = RedisManager(db_number=broker_db)
    return _redis_broker_manager


async def get_async_redis_client() -> redis_async.Redis:
    """
    Get async Redis client from manager.

    Returns:
        Async Redis client
    """
    manager = get_redis_manager()
    return await manager.get_async_client()


def get_sync_redis_client() -> redis_sync.Redis:
    """
    Get sync Redis client from manager.

    Returns:
        Sync Redis client
    """
    manager = get_redis_manager()
    return manager.get_sync_client()


def get_compatible_redis_client(preferred_type: str = "auto"):
    """
    Get Redis client with automatic compatibility.

    Args:
        preferred_type: "async", "sync", or "auto" (default)

    Returns:
        Compatible Redis client
    """
    manager = get_redis_manager()
    return manager.get_compatible_client(preferred_type)


@asynccontextmanager
async def redis_transaction():
    """
    Async context manager for Redis transactions.

    Usage:
        async with redis_transaction() as pipe:
            pipe.set('key', 'value')
            pipe.incr('counter')
            results = await pipe.execute()
    """
    client = await get_async_redis_client()
    pipe = client.pipeline()
    try:
        yield pipe
    finally:
        # Pipeline cleanup is automatic
        pass


async def cleanup_redis_connections():
    """Cleanup all Redis connections (for application shutdown)."""
    global _redis_manager
    if _redis_manager:
        await _redis_manager.close_all()
        _redis_manager = None
        logger.info("All Redis connections cleaned up")


# Health check function
async def redis_health_check() -> dict:
    """
    Perform Redis health check.

    Returns:
        Health check results
    """
    import re

    # SEC-001 FIX: Sanitize Redis URL to hide credentials
    def sanitize_redis_url(url: str) -> str:
        """Remove password from Redis URL for safe logging"""
        if not url:
            return 'not_configured'
        # Replace password in redis://user:password@host:port format
        return re.sub(r'://([^:]*):([^@]*)@', r'://\1:***@', url)

    try:
        manager = get_redis_manager()

        # Test async client
        async_client = await manager.get_async_client()
        async_ping = await async_client.ping()

        # Test sync client
        sync_client = manager.get_sync_client()
        sync_ping = sync_client.ping()

        return {
            "status": "healthy",
            "async_ping": bool(async_ping),
            "sync_ping": bool(sync_ping),
            "redis_url": sanitize_redis_url(settings.REDIS_URL),  # SEC-001: Sanitized URL
            "max_connections": manager.max_connections
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "redis_url": sanitize_redis_url(getattr(settings, 'REDIS_URL', 'not_configured'))  # SEC-001: Sanitized URL
        }
