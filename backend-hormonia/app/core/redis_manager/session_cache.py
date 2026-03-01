"""
Session Management and Caching

Layer 3: Session Management - 24 hours TTL (instant logout control)
Enables instant logout control and activity tracking.
"""

import logging
import asyncio
import inspect
import json
from typing import Optional, Any, Dict, List
from datetime import datetime, timezone
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class SessionCache:
    """
    Session management and caching functionality.

    Provides session creation, retrieval, invalidation, and listing.
    """

    def __init__(
        self, redis_client, session_ttl: int = 86400, max_session_age: int = 604800
    ):
        """
        Initialize session cache.

        Args:
            redis_client: Redis client instance
            session_ttl: Session TTL in seconds (default: 24 hours - inactivity timeout)
            max_session_age: Absolute max session age in seconds (default: 7 days)
        """
        self.redis = redis_client
        self.session_ttl = session_ttl
        self.max_session_age = max_session_age

    async def _redis_call(self, method_name: str, *args, **kwargs):
        """Call Redis methods supporting both sync and async clients."""
        method = getattr(self.redis, method_name)
        if inspect.iscoroutinefunction(method):
            return await method(*args, **kwargs)
        return await asyncio.to_thread(method, *args, **kwargs)

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        firebase_uid: str,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None,
        ttl: Optional[int] = None,  # Alternative parameter name for compatibility
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
            "created_at": now_sao_paulo().isoformat(),
            "last_activity": now_sao_paulo().isoformat(),
            "max_age_seconds": self.max_session_age,
            **(metadata or {}),
        }

        try:
            await self._redis_call("setex", key, ttl_value, json.dumps(session_data))
            logger.info(f"🔐 Session created: {session_id[:16]}... (TTL: {ttl_value}s)")
            return True
        except Exception as e:
            logger.error(f"Failed to create session: {str(e)}")
            return False

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve active session and update last_activity - ASYNC VERSION.

        Implements Dual-TTL:
        1. Inactivity TTL (session_ttl): Reset on every access
        2. Absolute Max Age (max_session_age): Session hard expires after this time

        Args:
            session_id: Session identifier

        Returns:
            Session data or None if expired/invalid
        """
        key = f"session:{session_id}"

        try:
            cached = await self._redis_call("get", key)
            if cached:
                session_data = json.loads(cached)
                now = now_sao_paulo()

                # --- 1. Max Age Validation ---
                created_at_str = session_data.get("created_at")
                max_age = session_data.get("max_age_seconds", self.max_session_age)

                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                        age = (now - created_at).total_seconds()

                        if age > max_age:
                            logger.warning(
                                f"🚫 Session expired (Max Age): {session_id[:16]}... Age: {age:.0f}s > {max_age}s"
                            )
                            await self.invalidate_session(session_id)
                            return None
                    except ValueError:
                        # Malformed created_at, treat as new/valid but reset created_at below
                        session_data["created_at"] = now.isoformat()
                        logger.warning(f"🔧 Normalized malformed created_at: {session_id[:16]}...")
                else:
                    # Legacy session compatibility: Set created_at = now
                    logger.info(
                        f"⚠️ Legacy session found: {session_id[:16]}... Adding created_at."
                    )
                    session_data["created_at"] = now.isoformat()
                    # Don't return yet, need to save this update

                if "max_age_seconds" not in session_data:
                    session_data["max_age_seconds"] = self.max_session_age

                # --- 2. Update Activity & Reset Inactivity TTL ---
                session_data["last_activity"] = now.isoformat()

                # Refresh TTL for inactivity
                await self._redis_call(
                    "setex", key, self.session_ttl, json.dumps(session_data)
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
            deleted = await self._redis_call("delete", key)

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

        OPTIMIZED: Uses Redis pipeline to delete sessions in batch.

        Use case: Password change, account compromise, admin force-logout.

        Args:
            firebase_uid: Firebase user ID

        Returns:
            Number of sessions deleted
        """
        pattern = "session:*"

        try:
            # 1. Collect keys to delete (scan is lightweight)
            keys_to_delete = []
            
            # Using scan_iter in a thread to avoid blocking loop on large datasets
            # Although scan_iter itself is a generator, iterating it involves network calls
            def scan_and_filter():
                found_keys = []
                for key in self.redis.scan_iter(match=pattern, count=100):
                    session_data = self.redis.get(key)
                    if session_data:
                        try:
                            data = json.loads(session_data)
                            if data.get("firebase_uid") == firebase_uid:
                                found_keys.append(key)
                        except json.JSONDecodeError:
                            continue
                return found_keys
            
            keys_to_delete = await asyncio.to_thread(scan_and_filter)

            if not keys_to_delete:
                return 0

            # 2. Batch delete using pipeline
            def batch_delete(keys):
                pipe = self.redis.pipeline(transaction=False)
                for key in keys:
                    pipe.delete(key)
                results = pipe.execute()
                return sum(results) # Count successful deletes

            deleted_count = await asyncio.to_thread(batch_delete, keys_to_delete)

            logger.info(
                f"🚪 Global logout: {deleted_count} sessions deleted for {firebase_uid}"
            )
            return deleted_count
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

        try:
            for key in self.redis.scan_iter(match=pattern):
                session_data = self.redis.get(key)
                if session_data:
                    try:
                        data = json.loads(session_data)
                        if data.get("firebase_uid") == firebase_uid:
                            # Extract session_id from key
                            session_id = key.split(":", 1)[1] if ":" in key else key
                            data["session_id"] = session_id
                            sessions.append(data)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Error listing user sessions: {str(e)}")
            return []

        logger.debug(f"📊 Active sessions for {firebase_uid}: {len(sessions)}")
        return sessions

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

    async def update_session_activity(
        self, session_id: str, extend_ttl: bool = True, custom_ttl: Optional[int] = None
    ) -> bool:
        """
        Update session activity timestamp and optionally extend TTL.

        This method explicitly updates the last_activity timestamp and can
        extend the session TTL to keep active users logged in.
        
        Note: Checks for Max Age validity implicitly via get_session, or we can check here explicitly.
        Currently this method just updates activity. It's better to fetch via get_session first 
        to ensure validity, but that might be expensive? 
        
        To ensure consistency, we should check max age here too, but this method is often called 
        after get_session. Let's keep it simple: update activity. If session is expired by Max Age,
        get_session would have killed it or it will be killed next get_session. 
        However, if we extend TTL here for an "old" session, we might keep it alive longer.
        
        Logic update: check max_age here too to prevent zombies.
        """
        key = f"session:{session_id}"

        try:
            # Get current session data
            cached = await asyncio.to_thread(self.redis.get, key)
            if not cached:
                logger.debug(
                    f"❌ Cannot update activity - session not found: {session_id[:16]}..."
                )
                return False

            # Parse and update session data
            session_data = json.loads(cached)
            now = now_sao_paulo()
            
            # --- Max Age Check ---
            created_at_str = session_data.get("created_at")
            max_age = session_data.get("max_age_seconds", self.max_session_age)
            
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str)
                    age = (now - created_at).total_seconds()
                    if age > max_age:
                        logger.warning(
                            f"🚫 Session expired during update (Max Age): {session_id[:16]}..."
                        )
                        await self.invalidate_session(session_id)
                        return False
                except ValueError:
                    session_data["created_at"] = now.isoformat()
                    logger.warning(f"🔧 Normalized malformed created_at: {session_id[:16]}...")
            else:
                 # Legacy fixup on update
                 session_data["created_at"] = now.isoformat()

            session_data["last_activity"] = now.isoformat()

            # Determine TTL
            if extend_ttl:
                ttl_value = custom_ttl or self.session_ttl
                # Write back with new TTL
                await asyncio.to_thread(
                    self.redis.setex, key, ttl_value, json.dumps(session_data)
                )
                logger.debug(
                    f"♻️ Session activity updated + TTL extended ({ttl_value}s): {session_id[:16]}..."
                )
            else:
                # Get remaining TTL to preserve it
                remaining_ttl = await asyncio.to_thread(self.redis.ttl, key)
                if remaining_ttl > 0:
                    await asyncio.to_thread(
                        self.redis.setex, key, remaining_ttl, json.dumps(session_data)
                    )
                    logger.debug(
                        f"♻️ Session activity updated (TTL preserved): {session_id[:16]}..."
                    )
                else:
                    logger.warning(
                        f"⚠️ Session TTL expired during update: {session_id[:16]}..."
                    )
                    return False

            return True

        except Exception as e:
            logger.error(f"Error updating session activity: {str(e)}")
            return False


# Mixin to add session management to FirebaseRedisCache
class SessionCacheMixin:
    """Mixin to add session management methods to FirebaseRedisCache."""
    
    # These parameters should come from config or be passed during init of the main class
    # For mixin, we rely on self.session_ttl being available, but map max_session_age possibly from accessing settings
    # or just using default. Better: The calling class should configure these.
    # Assuming the main class initializes session_ttl. We need to fetch max_session_age from settings if possible,
    # or default it. Since we can't easily injection dependency here without changing init of main class,
    # we'll look for attribute or use default.
    
    @property
    def _max_session_age(self):
        return getattr(self, "max_session_age", 604800)

    async def create_session(self, *args, **kwargs):
        """Create session using SessionCache."""
        session_cache = SessionCache(self.redis, self.session_ttl, self._max_session_age)
        return await session_cache.create_session(*args, **kwargs)

    async def get_session(self, *args, **kwargs):
        """Get session using SessionCache."""
        session_cache = SessionCache(self.redis, self.session_ttl, self._max_session_age)
        return await session_cache.get_session(*args, **kwargs)

    async def invalidate_session(self, *args, **kwargs):
        """Invalidate session using SessionCache."""
        session_cache = SessionCache(self.redis, self.session_ttl, self._max_session_age)
        return await session_cache.invalidate_session(*args, **kwargs)

    async def invalidate_all_user_sessions(self, *args, **kwargs):
        """Invalidate all user sessions using SessionCache."""
        session_cache = SessionCache(self.redis, self.session_ttl, self._max_session_age)
        return await session_cache.invalidate_all_user_sessions(*args, **kwargs)

    def list_user_sessions(self, *args, **kwargs):
        """List user sessions using SessionCache."""
        session_cache = SessionCache(self.redis, self.session_ttl, self._max_session_age)
        return session_cache.list_user_sessions(*args, **kwargs)

    async def get_session_ttl(self, *args, **kwargs):
        """Get session TTL using SessionCache."""
        session_cache = SessionCache(self.redis, self.session_ttl, self._max_session_age)
        return await session_cache.get_session_ttl(*args, **kwargs)

    async def update_session_activity(self, *args, **kwargs):
        """Update session activity using SessionCache."""
        session_cache = SessionCache(self.redis, self.session_ttl, self._max_session_age)
        return await session_cache.update_session_activity(*args, **kwargs)
