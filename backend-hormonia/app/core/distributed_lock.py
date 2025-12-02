"""
Distributed Locking - Redis-based locks for race condition prevention

Implements the SET NX EX pattern for distributed mutex locks with:
- Automatic lock expiration (TTL) to prevent deadlocks
- Lock owner validation to prevent accidental release by other processes
- Both async and sync context managers
- Retry with exponential backoff

Usage:
    # Async context
    async with distributed_lock.acquire("saga:patient:123") as lock_id:
        # Critical section
        await process_patient(patient_id)

    # Sync context
    with distributed_lock.acquire_sync("saga:patient:123") as lock_id:
        # Critical section
        process_patient(patient_id)

    # Non-blocking acquire
    lock_id = await distributed_lock.try_acquire("saga:patient:123")
    if lock_id:
        try:
            await process_patient(patient_id)
        finally:
            await distributed_lock.release("saga:patient:123", lock_id)
"""

import asyncio
import logging
import uuid
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Optional, AsyncGenerator, Generator
from functools import wraps

logger = logging.getLogger(__name__)


class LockAcquisitionError(Exception):
    """Raised when lock cannot be acquired within timeout."""

    def __init__(self, key: str, timeout: float, message: Optional[str] = None):
        self.key = key
        self.timeout = timeout
        self.message = message or f"Could not acquire lock '{key}' within {timeout}s"
        super().__init__(self.message)


class LockReleaseError(Exception):
    """Raised when lock release fails (e.g., already expired)."""

    def __init__(self, key: str, lock_id: str, message: Optional[str] = None):
        self.key = key
        self.lock_id = lock_id
        self.message = message or f"Failed to release lock '{key}' (lock_id={lock_id})"
        super().__init__(self.message)


class DistributedLock:
    """
    Redis-based distributed lock with SET NX EX pattern.

    Features:
    - Atomic lock acquisition with expiration
    - Owner validation on release (Lua script for atomicity)
    - Configurable TTL and retry behavior
    - Both async and sync interfaces
    - Metrics for observability
    """

    # Lua script for atomic release (check owner before deleting)
    # This prevents accidentally releasing a lock acquired by another process
    # after our lock expired
    RELEASE_SCRIPT = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """

    # Lua script for atomic extend (only if we still own the lock)
    EXTEND_SCRIPT = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("expire", KEYS[1], ARGV[2])
    else
        return 0
    end
    """

    # Lock key prefix for namespacing
    KEY_PREFIX = "lock:"

    # Default settings
    DEFAULT_TTL = 30  # seconds
    DEFAULT_ACQUIRE_TIMEOUT = 10  # seconds
    DEFAULT_RETRY_DELAY = 0.1  # seconds (initial delay, exponential backoff)
    MAX_RETRY_DELAY = 2.0  # seconds (cap on backoff)

    def __init__(
        self,
        ttl: int = DEFAULT_TTL,
        acquire_timeout: float = DEFAULT_ACQUIRE_TIMEOUT,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        auto_extend: bool = True
    ):
        """
        Initialize distributed lock.

        Args:
            ttl: Lock expiration time in seconds (prevents deadlocks)
            acquire_timeout: Max time to wait for lock acquisition
            retry_delay: Initial delay between acquisition retries
            auto_extend: Whether to automatically extend lock while held
        """
        self.ttl = ttl
        self.acquire_timeout = acquire_timeout
        self.retry_delay = retry_delay
        self.auto_extend = auto_extend

        # Lazy-loaded Redis clients
        self._async_redis = None
        self._sync_redis = None

        # Registered Lua scripts (for performance)
        self._release_sha = None
        self._extend_sha = None

        # Metrics
        self._locks_acquired = 0
        self._locks_released = 0
        self._locks_failed = 0
        self._locks_extended = 0

    async def _get_async_redis(self):
        """Get async Redis client (lazy initialization)."""
        if self._async_redis is None:
            from app.core.redis_unified import get_async_redis
            self._async_redis = await get_async_redis()
            # Register Lua scripts for performance
            self._release_sha = await self._async_redis.script_load(self.RELEASE_SCRIPT)
            self._extend_sha = await self._async_redis.script_load(self.EXTEND_SCRIPT)
        return self._async_redis

    def _get_sync_redis(self):
        """Get sync Redis client (lazy initialization)."""
        if self._sync_redis is None:
            from app.core.redis_unified import get_sync_redis
            self._sync_redis = get_sync_redis()
            # Register Lua scripts for sync client
            self._release_sha_sync = self._sync_redis.script_load(self.RELEASE_SCRIPT)
            self._extend_sha_sync = self._sync_redis.script_load(self.EXTEND_SCRIPT)
        return self._sync_redis

    def _make_key(self, key: str) -> str:
        """Create namespaced Redis key."""
        if key.startswith(self.KEY_PREFIX):
            return key
        return f"{self.KEY_PREFIX}{key}"

    def _generate_lock_id(self) -> str:
        """Generate unique lock identifier."""
        return str(uuid.uuid4())

    async def try_acquire(
        self,
        key: str,
        ttl: Optional[int] = None,
        lock_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Try to acquire lock without waiting (non-blocking).

        Args:
            key: Lock identifier
            ttl: Optional custom TTL (uses default if not specified)
            lock_id: Optional custom lock ID (generates if not specified)

        Returns:
            Lock ID if acquired, None if lock is held by another
        """
        redis = await self._get_async_redis()
        lock_key = self._make_key(key)
        lock_id = lock_id or self._generate_lock_id()
        ttl = ttl or self.ttl

        # SET NX EX - atomic set-if-not-exists with expiration
        acquired = await redis.set(lock_key, lock_id, ex=ttl, nx=True)

        if acquired:
            self._locks_acquired += 1
            logger.debug(f"Lock acquired: {key} (lock_id={lock_id[:8]}..., ttl={ttl}s)")
            return lock_id

        return None

    def try_acquire_sync(
        self,
        key: str,
        ttl: Optional[int] = None,
        lock_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Try to acquire lock without waiting (sync, non-blocking).

        Args:
            key: Lock identifier
            ttl: Optional custom TTL
            lock_id: Optional custom lock ID

        Returns:
            Lock ID if acquired, None if lock is held by another
        """
        redis = self._get_sync_redis()
        lock_key = self._make_key(key)
        lock_id = lock_id or self._generate_lock_id()
        ttl = ttl or self.ttl

        acquired = redis.set(lock_key, lock_id, ex=ttl, nx=True)

        if acquired:
            self._locks_acquired += 1
            logger.debug(f"Lock acquired (sync): {key} (lock_id={lock_id[:8]}..., ttl={ttl}s)")
            return lock_id

        return None

    async def acquire_with_retry(
        self,
        key: str,
        timeout: Optional[float] = None,
        ttl: Optional[int] = None
    ) -> str:
        """
        Acquire lock with retry and exponential backoff.

        Args:
            key: Lock identifier
            timeout: Max time to wait (uses default if not specified)
            ttl: Lock TTL (uses default if not specified)

        Returns:
            Lock ID on success

        Raises:
            LockAcquisitionError: If lock cannot be acquired within timeout
        """
        timeout = timeout or self.acquire_timeout
        ttl = ttl or self.ttl
        lock_id = self._generate_lock_id()

        start_time = time.monotonic()
        delay = self.retry_delay
        attempts = 0

        while True:
            attempts += 1

            # Try to acquire
            acquired_id = await self.try_acquire(key, ttl=ttl, lock_id=lock_id)
            if acquired_id:
                if attempts > 1:
                    logger.info(f"Lock acquired after {attempts} attempts: {key}")
                return acquired_id

            # Check timeout
            elapsed = time.monotonic() - start_time
            if elapsed >= timeout:
                self._locks_failed += 1
                logger.warning(f"Lock acquisition timeout: {key} (attempts={attempts}, elapsed={elapsed:.2f}s)")
                raise LockAcquisitionError(key, timeout)

            # Exponential backoff with jitter
            jitter = delay * 0.1 * (uuid.uuid4().int % 100) / 100
            sleep_time = min(delay + jitter, self.MAX_RETRY_DELAY)
            await asyncio.sleep(sleep_time)

            # Increase delay for next iteration (exponential backoff)
            delay = min(delay * 2, self.MAX_RETRY_DELAY)

    def acquire_with_retry_sync(
        self,
        key: str,
        timeout: Optional[float] = None,
        ttl: Optional[int] = None
    ) -> str:
        """
        Acquire lock with retry and exponential backoff (sync version).

        Args:
            key: Lock identifier
            timeout: Max time to wait
            ttl: Lock TTL

        Returns:
            Lock ID on success

        Raises:
            LockAcquisitionError: If lock cannot be acquired within timeout
        """
        timeout = timeout or self.acquire_timeout
        ttl = ttl or self.ttl
        lock_id = self._generate_lock_id()

        start_time = time.monotonic()
        delay = self.retry_delay
        attempts = 0

        while True:
            attempts += 1

            acquired_id = self.try_acquire_sync(key, ttl=ttl, lock_id=lock_id)
            if acquired_id:
                if attempts > 1:
                    logger.info(f"Lock acquired (sync) after {attempts} attempts: {key}")
                return acquired_id

            elapsed = time.monotonic() - start_time
            if elapsed >= timeout:
                self._locks_failed += 1
                logger.warning(f"Lock acquisition timeout (sync): {key} (attempts={attempts})")
                raise LockAcquisitionError(key, timeout)

            jitter = delay * 0.1 * (uuid.uuid4().int % 100) / 100
            sleep_time = min(delay + jitter, self.MAX_RETRY_DELAY)
            time.sleep(sleep_time)

            delay = min(delay * 2, self.MAX_RETRY_DELAY)

    async def release(self, key: str, lock_id: str) -> bool:
        """
        Release lock atomically (only if we still own it).

        Uses Lua script to ensure atomic check-and-delete.
        This prevents releasing a lock that was already expired and
        re-acquired by another process.

        Args:
            key: Lock identifier
            lock_id: Lock ID returned from acquire

        Returns:
            True if released, False if lock was already released/expired
        """
        redis = await self._get_async_redis()
        lock_key = self._make_key(key)

        try:
            # Use registered Lua script for atomic release
            result = await redis.evalsha(self._release_sha, 1, lock_key, lock_id)

            if result == 1:
                self._locks_released += 1
                logger.debug(f"Lock released: {key}")
                return True
            else:
                logger.warning(f"Lock release failed (not owner or expired): {key}")
                return False
        except Exception as e:
            # Fallback to inline script if SHA not found
            logger.debug(f"Evalsha failed, using inline script: {e}")
            result = await redis.eval(self.RELEASE_SCRIPT, 1, lock_key, lock_id)
            return result == 1

    def release_sync(self, key: str, lock_id: str) -> bool:
        """
        Release lock atomically (sync version).

        Args:
            key: Lock identifier
            lock_id: Lock ID returned from acquire

        Returns:
            True if released, False if lock was already released/expired
        """
        redis = self._get_sync_redis()
        lock_key = self._make_key(key)

        try:
            result = redis.evalsha(self._release_sha_sync, 1, lock_key, lock_id)

            if result == 1:
                self._locks_released += 1
                logger.debug(f"Lock released (sync): {key}")
                return True
            else:
                logger.warning(f"Lock release failed (sync, not owner or expired): {key}")
                return False
        except Exception as e:
            logger.debug(f"Evalsha failed (sync), using inline script: {e}")
            result = redis.eval(self.RELEASE_SCRIPT, 1, lock_key, lock_id)
            return result == 1

    async def extend(self, key: str, lock_id: str, ttl: Optional[int] = None) -> bool:
        """
        Extend lock TTL (only if we still own it).

        Useful for long-running operations that may exceed initial TTL.

        Args:
            key: Lock identifier
            lock_id: Lock ID returned from acquire
            ttl: New TTL in seconds (uses default if not specified)

        Returns:
            True if extended, False if lock was already released/expired
        """
        redis = await self._get_async_redis()
        lock_key = self._make_key(key)
        ttl = ttl or self.ttl

        try:
            result = await redis.evalsha(self._extend_sha, 1, lock_key, lock_id, ttl)

            if result == 1:
                self._locks_extended += 1
                logger.debug(f"Lock extended: {key} (new_ttl={ttl}s)")
                return True
            else:
                logger.warning(f"Lock extend failed (not owner or expired): {key}")
                return False
        except Exception as e:
            logger.debug(f"Evalsha failed, using inline script: {e}")
            result = await redis.eval(self.EXTEND_SCRIPT, 1, lock_key, lock_id, ttl)
            return result == 1

    @asynccontextmanager
    async def acquire(
        self,
        key: str,
        timeout: Optional[float] = None,
        ttl: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        Async context manager for acquiring/releasing locks.

        Usage:
            async with lock.acquire("saga:patient:123") as lock_id:
                await process_patient(patient_id)

        Args:
            key: Lock identifier
            timeout: Max time to wait for acquisition
            ttl: Lock TTL

        Yields:
            Lock ID

        Raises:
            LockAcquisitionError: If lock cannot be acquired
        """
        lock_id = await self.acquire_with_retry(key, timeout=timeout, ttl=ttl)
        try:
            yield lock_id
        finally:
            await self.release(key, lock_id)

    @contextmanager
    def acquire_sync(
        self,
        key: str,
        timeout: Optional[float] = None,
        ttl: Optional[int] = None
    ) -> Generator[str, None, None]:
        """
        Sync context manager for acquiring/releasing locks.

        Usage:
            with lock.acquire_sync("saga:patient:123") as lock_id:
                process_patient(patient_id)

        Args:
            key: Lock identifier
            timeout: Max time to wait for acquisition
            ttl: Lock TTL

        Yields:
            Lock ID

        Raises:
            LockAcquisitionError: If lock cannot be acquired
        """
        lock_id = self.acquire_with_retry_sync(key, timeout=timeout, ttl=ttl)
        try:
            yield lock_id
        finally:
            self.release_sync(key, lock_id)

    async def is_locked(self, key: str) -> bool:
        """
        Check if a key is currently locked.

        Args:
            key: Lock identifier

        Returns:
            True if locked, False otherwise
        """
        redis = await self._get_async_redis()
        lock_key = self._make_key(key)
        return await redis.exists(lock_key) > 0

    async def get_lock_owner(self, key: str) -> Optional[str]:
        """
        Get the current lock owner (lock_id).

        Args:
            key: Lock identifier

        Returns:
            Lock ID if locked, None otherwise
        """
        redis = await self._get_async_redis()
        lock_key = self._make_key(key)
        return await redis.get(lock_key)

    async def force_release(self, key: str) -> bool:
        """
        Force release a lock regardless of owner.

        WARNING: Use only in exceptional circumstances (e.g., stuck locks).
        This can cause race conditions if the lock owner is still active.

        Args:
            key: Lock identifier

        Returns:
            True if deleted, False if not found
        """
        redis = await self._get_async_redis()
        lock_key = self._make_key(key)
        result = await redis.delete(lock_key)
        if result:
            logger.warning(f"Lock force-released: {key}")
        return result > 0

    def get_metrics(self) -> dict:
        """Get lock metrics for observability."""
        return {
            "locks_acquired": self._locks_acquired,
            "locks_released": self._locks_released,
            "locks_failed": self._locks_failed,
            "locks_extended": self._locks_extended,
            "default_ttl": self.ttl,
            "acquire_timeout": self.acquire_timeout
        }


# ============================================================================
# Module-level singleton and convenience functions
# ============================================================================

_default_lock: Optional[DistributedLock] = None


def get_distributed_lock() -> DistributedLock:
    """
    Get the default distributed lock instance (singleton).

    Returns:
        DistributedLock instance
    """
    global _default_lock
    if _default_lock is None:
        _default_lock = DistributedLock()
    return _default_lock


@asynccontextmanager
async def acquire_lock(
    key: str,
    timeout: float = DistributedLock.DEFAULT_ACQUIRE_TIMEOUT,
    ttl: int = DistributedLock.DEFAULT_TTL
) -> AsyncGenerator[str, None]:
    """
    Convenience function for async lock acquisition.

    Usage:
        async with acquire_lock("saga:patient:123") as lock_id:
            await process_patient(patient_id)

    Args:
        key: Lock identifier
        timeout: Max time to wait
        ttl: Lock TTL

    Yields:
        Lock ID
    """
    lock = get_distributed_lock()
    async with lock.acquire(key, timeout=timeout, ttl=ttl) as lock_id:
        yield lock_id


@contextmanager
def acquire_lock_sync(
    key: str,
    timeout: float = DistributedLock.DEFAULT_ACQUIRE_TIMEOUT,
    ttl: int = DistributedLock.DEFAULT_TTL
) -> Generator[str, None, None]:
    """
    Convenience function for sync lock acquisition.

    Usage:
        with acquire_lock_sync("saga:patient:123") as lock_id:
            process_patient(patient_id)

    Args:
        key: Lock identifier
        timeout: Max time to wait
        ttl: Lock TTL

    Yields:
        Lock ID
    """
    lock = get_distributed_lock()
    with lock.acquire_sync(key, timeout=timeout, ttl=ttl) as lock_id:
        yield lock_id


def with_lock(key_template: str, timeout: float = 10.0, ttl: int = 30):
    """
    Decorator for protecting async functions with distributed lock.

    Usage:
        @with_lock("saga:patient:{patient_id}")
        async def process_patient(patient_id: str):
            # Critical section
            pass

    Args:
        key_template: Lock key template (uses format() with function kwargs)
        timeout: Max time to wait for lock
        ttl: Lock TTL
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build key from template using kwargs
            key = key_template.format(**kwargs)
            async with acquire_lock(key, timeout=timeout, ttl=ttl):
                return await func(*args, **kwargs)
        return wrapper
    return decorator


def with_lock_sync(key_template: str, timeout: float = 10.0, ttl: int = 30):
    """
    Decorator for protecting sync functions with distributed lock.

    Usage:
        @with_lock_sync("saga:patient:{patient_id}")
        def process_patient(patient_id: str):
            # Critical section
            pass

    Args:
        key_template: Lock key template
        timeout: Max time to wait for lock
        ttl: Lock TTL
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = key_template.format(**kwargs)
            with acquire_lock_sync(key, timeout=timeout, ttl=ttl):
                return func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================================
# Lock key patterns for the application
# ============================================================================

class LockKeys:
    """
    Standard lock key patterns for the application.

    Usage:
        async with acquire_lock(LockKeys.saga(patient_id)):
            await process_saga(patient_id)
    """

    @staticmethod
    def saga(patient_id: str) -> str:
        """Lock for saga orchestration per patient."""
        return f"saga:patient:{patient_id}"

    @staticmethod
    def message_processing(patient_id: str) -> str:
        """Lock for message processing per patient."""
        return f"message:processing:{patient_id}"

    @staticmethod
    def quiz_session(patient_id: str) -> str:
        """Lock for quiz session operations per patient."""
        return f"quiz:session:{patient_id}"

    @staticmethod
    def patient_onboarding(patient_id: str) -> str:
        """Lock for patient onboarding per patient."""
        return f"patient:onboarding:{patient_id}"

    @staticmethod
    def webhook_processing(webhook_id: str) -> str:
        """Lock for webhook idempotency."""
        return f"webhook:{webhook_id}"

    @staticmethod
    def retry(message_id: str) -> str:
        """Lock for message retry operations."""
        return f"retry:message:{message_id}"

    @staticmethod
    def flow_advance(patient_id: str) -> str:
        """Lock for flow advancement operations."""
        return f"flow:advance:{patient_id}"
