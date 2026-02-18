"""
Distributed Lock Implementation for Flow State Management.

This module provides Redis-based distributed locking to prevent race conditions
in flow state transitions and message delivery ordering.

Key Features:
- Redis-based distributed locking with automatic timeout
- Lock contention monitoring and metrics
- Automatic lock recovery on timeout
- Context manager for safe lock acquisition/release
- Integration with existing cache infrastructure
"""

import logging
import time
import asyncio
import threading
from typing import Optional, Any, Dict
from uuid import UUID, uuid4

from app.core.redis_manager import get_sync_redis_client as get_sync_redis, get_async_redis_client as get_async_redis

logger = logging.getLogger(__name__)


class LockAcquisitionError(Exception):
    """Raised when lock cannot be acquired."""

    pass


class LockTimeoutError(Exception):
    """Raised when lock operation times out."""

    pass


class DistributedLock:
    """
    Redis-based distributed lock for flow state synchronization.

    This lock ensures that flow state transitions and message delivery
    occur in the correct order, preventing race conditions between
    concurrent operations.

    Features:
    - Automatic lock timeout and cleanup
    - Lock ownership tracking with unique identifiers
    - Metrics collection for lock contention analysis
    - Graceful degradation on Redis failures
    """

    def __init__(
        self,
        lock_name: str,
        timeout: int = 30,
        blocking_timeout: Optional[int] = None,
        namespace: str = "locks",
    ):
        """
        Initialize distributed lock.

        Args:
            lock_name: Unique name for this lock
            timeout: Lock auto-release timeout in seconds (default: 30s)
            blocking_timeout: How long to wait for lock acquisition (None = non-blocking)
            namespace: Redis namespace for lock keys
        """
        self.lock_name = lock_name
        self.timeout = timeout
        self.blocking_timeout = blocking_timeout
        self.namespace = namespace
        self.lock_key = f"{namespace}:{lock_name}"
        self.owner_id = str(uuid4())
        self._redis = None
        self._acquired = False
        self._acquire_time: Optional[float] = None

        # Metrics
        self._contention_count = 0
        self._total_wait_time = 0.0

    def _get_redis(self):
        """Get Redis client with lazy initialization."""
        if self._redis is None:
            self._redis = get_sync_redis()
        return self._redis

    def acquire(self, blocking: bool = True) -> bool:
        """
        Acquire the distributed lock.

        Args:
            blocking: If True, wait for lock. If False, return immediately.

        Returns:
            True if lock acquired, False otherwise

        Raises:
            LockTimeoutError: If blocking timeout exceeded
        """
        redis_client = self._get_redis()
        start_time = time.time()

        # Determine effective timeout
        timeout = self.blocking_timeout if blocking and self.blocking_timeout else 0

        try:
            while True:
                # Try to acquire lock with SET NX EX
                acquired = redis_client.set(
                    self.lock_key,
                    self.owner_id,
                    ex=self.timeout,
                    nx=True,  # Only set if doesn't exist
                )

                if acquired:
                    self._acquired = True
                    self._acquire_time = time.time()
                    wait_time = self._acquire_time - start_time

                    if wait_time > 0.01:  # More than 10ms wait
                        self._contention_count += 1
                        self._total_wait_time += wait_time
                        logger.info(
                            f"Lock '{self.lock_name}' acquired after {wait_time:.3f}s wait "
                            f"(contention count: {self._contention_count})"
                        )

                    return True

                # Lock not available
                if not blocking:
                    return False

                # Check timeout
                elapsed = time.time() - start_time
                if timeout and elapsed >= timeout:
                    raise LockTimeoutError(
                        f"Failed to acquire lock '{self.lock_name}' within {timeout}s"
                    )

                # Wait before retry (exponential backoff with jitter)
                wait_time = min(0.001 * (2**self._contention_count), 0.1)
                threading.Event().wait(wait_time)

        except Exception as e:
            logger.error(f"Error acquiring lock '{self.lock_name}': {e}")
            raise

    def release(self) -> bool:
        """
        Release the distributed lock.

        Only the lock owner can release the lock (verified by owner_id).

        Returns:
            True if lock released, False otherwise
        """
        if not self._acquired:
            logger.warning(f"Attempted to release non-acquired lock '{self.lock_name}'")
            return False

        redis_client = self._get_redis()

        try:
            # Use Lua script to ensure atomic check-and-delete
            # Only delete if the stored value matches our owner_id
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """

            result = redis_client.eval(lua_script, 1, self.lock_key, self.owner_id)

            if result == 1:
                self._acquired = False

                # Log metrics if lock was held for significant time
                if self._acquire_time:
                    hold_time = time.time() - self._acquire_time
                    if hold_time > 1.0:  # More than 1 second
                        logger.info(
                            f"Lock '{self.lock_name}' held for {hold_time:.3f}s"
                        )

                return True
            else:
                logger.warning(
                    f"Lock '{self.lock_name}' was already released or owned by another process"
                )
                return False

        except Exception as e:
            logger.error(f"Error releasing lock '{self.lock_name}': {e}")
            return False

    def extend(self, additional_timeout: int) -> bool:
        """
        Extend the lock timeout.

        Args:
            additional_timeout: Additional seconds to extend lock

        Returns:
            True if extended successfully
        """
        if not self._acquired:
            logger.warning(f"Cannot extend non-acquired lock '{self.lock_name}'")
            return False

        redis_client = self._get_redis()

        try:
            # Use Lua script to verify ownership before extending
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("expire", KEYS[1], ARGV[2])
            else
                return 0
            end
            """

            result = redis_client.eval(
                lua_script, 1, self.lock_key, self.owner_id, additional_timeout
            )

            return result == 1

        except Exception as e:
            logger.error(f"Error extending lock '{self.lock_name}': {e}")
            return False

    def is_locked(self) -> bool:
        """
        Check if lock is currently held by anyone.

        Returns:
            True if lock exists in Redis
        """
        redis_client = self._get_redis()

        try:
            return redis_client.exists(self.lock_key) > 0
        except Exception as e:
            logger.error(f"Error checking lock status '{self.lock_name}': {e}")
            return False

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get lock contention metrics.

        Returns:
            Dictionary with lock performance metrics
        """
        avg_wait_time = (
            self._total_wait_time / self._contention_count
            if self._contention_count > 0
            else 0
        )

        return {
            "lock_name": self.lock_name,
            "contention_count": self._contention_count,
            "total_wait_time": self._total_wait_time,
            "average_wait_time": avg_wait_time,
            "is_acquired": self._acquired,
            "timeout": self.timeout,
        }

    def __enter__(self):
        """Context manager entry - acquire lock."""
        if not self.acquire(blocking=True):
            raise LockAcquisitionError(f"Failed to acquire lock '{self.lock_name}'")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - release lock."""
        self.release()
        return False


class AsyncDistributedLock:
    """
    Async version of DistributedLock for async contexts.

    Provides the same functionality as DistributedLock but with
    async/await support for use in async functions and coroutines.
    """

    def __init__(
        self,
        lock_name: str,
        timeout: int = 30,
        blocking_timeout: Optional[int] = None,
        namespace: str = "locks",
    ):
        """Initialize async distributed lock."""
        self.lock_name = lock_name
        self.timeout = timeout
        self.blocking_timeout = blocking_timeout
        self.namespace = namespace
        self.lock_key = f"{namespace}:{lock_name}"
        self.owner_id = str(uuid4())
        self._redis = None
        self._acquired = False
        self._acquire_time: Optional[float] = None
        self._contention_count = 0
        self._total_wait_time = 0.0

    async def _get_redis(self):
        """Get async Redis client with lazy initialization."""
        if self._redis is None:
            self._redis = await get_async_redis()
        return self._redis

    async def acquire(self, blocking: bool = True) -> bool:
        """
        Acquire the distributed lock (async).

        Args:
            blocking: If True, wait for lock. If False, return immediately.

        Returns:
            True if lock acquired, False otherwise

        Raises:
            LockTimeoutError: If blocking timeout exceeded
        """
        redis_client = await self._get_redis()
        start_time = time.time()

        timeout = self.blocking_timeout if blocking and self.blocking_timeout else 0

        try:
            while True:
                acquired = await redis_client.set(
                    self.lock_key, self.owner_id, ex=self.timeout, nx=True
                )

                if acquired:
                    self._acquired = True
                    self._acquire_time = time.time()
                    wait_time = self._acquire_time - start_time

                    if wait_time > 0.01:
                        self._contention_count += 1
                        self._total_wait_time += wait_time
                        logger.info(
                            f"Async lock '{self.lock_name}' acquired after {wait_time:.3f}s wait"
                        )

                    return True

                if not blocking:
                    return False

                elapsed = time.time() - start_time
                if timeout and elapsed >= timeout:
                    raise LockTimeoutError(
                        f"Failed to acquire async lock '{self.lock_name}' within {timeout}s"
                    )

                wait_time = min(0.001 * (2**self._contention_count), 0.1)
                await asyncio.sleep(wait_time)

        except Exception as e:
            logger.error(f"Error acquiring async lock '{self.lock_name}': {e}")
            raise

    async def release(self) -> bool:
        """Release the distributed lock (async)."""
        if not self._acquired:
            logger.warning(
                f"Attempted to release non-acquired async lock '{self.lock_name}'"
            )
            return False

        redis_client = await self._get_redis()

        try:
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """

            result = await redis_client.eval(
                lua_script, 1, self.lock_key, self.owner_id
            )

            if result == 1:
                self._acquired = False

                if self._acquire_time:
                    hold_time = time.time() - self._acquire_time
                    if hold_time > 1.0:
                        logger.info(
                            f"Async lock '{self.lock_name}' held for {hold_time:.3f}s"
                        )

                return True
            else:
                logger.warning(
                    f"Async lock '{self.lock_name}' was already released or owned by another process"
                )
                return False

        except Exception as e:
            logger.error(f"Error releasing async lock '{self.lock_name}': {e}")
            return False

    async def extend(self, additional_timeout: int) -> bool:
        """Extend the lock timeout (async)."""
        if not self._acquired:
            logger.warning(f"Cannot extend non-acquired async lock '{self.lock_name}'")
            return False

        redis_client = await self._get_redis()

        try:
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("expire", KEYS[1], ARGV[2])
            else
                return 0
            end
            """

            result = await redis_client.eval(
                lua_script, 1, self.lock_key, self.owner_id, additional_timeout
            )

            return result == 1

        except Exception as e:
            logger.error(f"Error extending async lock '{self.lock_name}': {e}")
            return False

    async def is_locked(self) -> bool:
        """Check if lock is currently held by anyone (async)."""
        redis_client = await self._get_redis()

        try:
            return await redis_client.exists(self.lock_key) > 0
        except Exception as e:
            logger.error(f"Error checking async lock status '{self.lock_name}': {e}")
            return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get lock contention metrics."""
        avg_wait_time = (
            self._total_wait_time / self._contention_count
            if self._contention_count > 0
            else 0
        )

        return {
            "lock_name": self.lock_name,
            "contention_count": self._contention_count,
            "total_wait_time": self._total_wait_time,
            "average_wait_time": avg_wait_time,
            "is_acquired": self._acquired,
            "timeout": self.timeout,
        }

    async def __aenter__(self):
        """Async context manager entry - acquire lock."""
        if not await self.acquire(blocking=True):
            raise LockAcquisitionError(
                f"Failed to acquire async lock '{self.lock_name}'"
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - release lock."""
        await self.release()
        return False


# Convenience functions for common locking patterns


def flow_state_lock(patient_id: UUID, timeout: int = 30) -> DistributedLock:
    """
    Create a distributed lock for flow state transitions.

    Args:
        patient_id: Patient UUID
        timeout: Lock timeout in seconds

    Returns:
        DistributedLock instance for flow state

    Usage:
        with flow_state_lock(patient_id) as lock:
            # Perform flow state transition
            flow_state.current_step = next_step
            db.commit()
    """
    return DistributedLock(
        lock_name=f"flow_state:{patient_id}", timeout=timeout, namespace="flow_locks"
    )


def async_flow_state_lock(patient_id: UUID, timeout: int = 30) -> AsyncDistributedLock:
    """
    Create an async distributed lock for flow state transitions.

    Args:
        patient_id: Patient UUID
        timeout: Lock timeout in seconds

    Returns:
        AsyncDistributedLock instance for flow state

    Usage:
        async with async_flow_state_lock(patient_id) as lock:
            # Perform async flow state transition
            flow_state.current_step = next_step
            await db.commit()
    """
    return AsyncDistributedLock(
        lock_name=f"flow_state:{patient_id}", timeout=timeout, namespace="flow_locks"
    )


def message_delivery_lock(patient_id: UUID, timeout: int = 10) -> DistributedLock:
    """
    Create a distributed lock for message delivery ordering.

    Args:
        patient_id: Patient UUID
        timeout: Lock timeout in seconds

    Returns:
        DistributedLock instance for message delivery

    Usage:
        with message_delivery_lock(patient_id) as lock:
            # Schedule message in correct order
            scheduler.schedule_message(patient_id, message)
    """
    return DistributedLock(
        lock_name=f"message_delivery:{patient_id}",
        timeout=timeout,
        namespace="message_locks",
    )


def async_message_delivery_lock(
    patient_id: UUID, timeout: int = 10
) -> AsyncDistributedLock:
    """
    Create an async distributed lock for message delivery ordering.

    Args:
        patient_id: Patient UUID
        timeout: Lock timeout in seconds

    Returns:
        AsyncDistributedLock instance for message delivery

    Usage:
        async with async_message_delivery_lock(patient_id) as lock:
            # Schedule message in correct order
            await scheduler.schedule_message(patient_id, message)
    """
    return AsyncDistributedLock(
        lock_name=f"message_delivery:{patient_id}",
        timeout=timeout,
        namespace="message_locks",
    )
