"""
Session Management and Caching

Layer 3: Session Management - 24 hours TTL (instant logout control)
Enables instant logout control and activity tracking.
"""

import logging
import asyncio
import json
from typing import Optional, Any, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)


class SessionCache:
    """
    Session management and caching functionality.

    Provides session creation, retrieval, invalidation, and listing.
    """

    def __init__(self, redis_client, session_ttl: int = 86400):
        """
        Initialize session cache.

        Args:
            redis_client: Redis client instance
            session_ttl: Session TTL in seconds (default: 24 hours)
        """
        self.redis = redis_client
        self.session_ttl = session_ttl

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
        self,
        session_id: str,
        extend_ttl: bool = True,
        custom_ttl: Optional[int] = None
    ) -> bool:
        """
        Update session activity timestamp and optionally extend TTL.

        This method explicitly updates the last_activity timestamp and can
        extend the session TTL to keep active users logged in.

        Args:
            session_id: Session identifier
            extend_ttl: Whether to reset the TTL (default: True)
            custom_ttl: Custom TTL in seconds (defaults to self.session_ttl)

        Returns:
            True if session was updated successfully, False otherwise
        """
        key = f"session:{session_id}"

        try:
            # Get current session data
            cached = await asyncio.to_thread(self.redis.get, key)
            if not cached:
                logger.debug(f"❌ Cannot update activity - session not found: {session_id[:16]}...")
                return False

            # Parse and update session data
            session_data = json.loads(cached)
            session_data["last_activity"] = datetime.utcnow().isoformat()

            # Determine TTL
            if extend_ttl:
                ttl_value = custom_ttl or self.session_ttl
                # Write back with new TTL
                await asyncio.to_thread(
                    self.redis.setex,
                    key,
                    ttl_value,
                    json.dumps(session_data)
                )
                logger.debug(f"♻️ Session activity updated + TTL extended ({ttl_value}s): {session_id[:16]}...")
            else:
                # Get remaining TTL to preserve it
                remaining_ttl = await asyncio.to_thread(self.redis.ttl, key)
                if remaining_ttl > 0:
                    await asyncio.to_thread(
                        self.redis.setex,
                        key,
                        remaining_ttl,
                        json.dumps(session_data)
                    )
                    logger.debug(f"♻️ Session activity updated (TTL preserved): {session_id[:16]}...")
                else:
                    logger.warning(f"⚠️ Session TTL expired during update: {session_id[:16]}...")
                    return False

            return True

        except Exception as e:
            logger.error(f"Error updating session activity: {str(e)}")
            return False


# Mixin to add session management to FirebaseRedisCache
class SessionCacheMixin:
    """Mixin to add session management methods to FirebaseRedisCache."""

    async def create_session(self, *args, **kwargs):
        """Create session using SessionCache."""
        session_cache = SessionCache(self.redis, self.session_ttl)
        return await session_cache.create_session(*args, **kwargs)

    async def get_session(self, *args, **kwargs):
        """Get session using SessionCache."""
        session_cache = SessionCache(self.redis, self.session_ttl)
        return await session_cache.get_session(*args, **kwargs)

    async def invalidate_session(self, *args, **kwargs):
        """Invalidate session using SessionCache."""
        session_cache = SessionCache(self.redis, self.session_ttl)
        return await session_cache.invalidate_session(*args, **kwargs)

    async def invalidate_all_user_sessions(self, *args, **kwargs):
        """Invalidate all user sessions using SessionCache."""
        session_cache = SessionCache(self.redis, self.session_ttl)
        return await session_cache.invalidate_all_user_sessions(*args, **kwargs)

    def list_user_sessions(self, *args, **kwargs):
        """List user sessions using SessionCache."""
        session_cache = SessionCache(self.redis, self.session_ttl)
        return session_cache.list_user_sessions(*args, **kwargs)

    async def get_session_ttl(self, *args, **kwargs):
        """Get session TTL using SessionCache."""
        session_cache = SessionCache(self.redis, self.session_ttl)
        return await session_cache.get_session_ttl(*args, **kwargs)

    async def update_session_activity(self, *args, **kwargs):
        """Update session activity using SessionCache."""
        session_cache = SessionCache(self.redis, self.session_ttl)
        return await session_cache.update_session_activity(*args, **kwargs)
