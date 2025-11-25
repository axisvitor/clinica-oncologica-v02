"""
Utility functions for Redis Manager

Provides global manager instances and utility functions.
"""

import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Global Redis manager instances
_redis_manager: Optional['RedisManager'] = None
_redis_cache_manager: Optional['RedisManager'] = None
_redis_broker_manager: Optional['RedisManager'] = None


def get_redis_manager(db_number: Optional[int] = None) -> 'RedisManager':
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
            from .manager import RedisManager
            _redis_manager = RedisManager()
        return _redis_manager
    else:
        # Create isolated manager for specific DB
        from .manager import RedisManager
        return RedisManager(db_number=db_number)


def get_cache_redis_manager() -> 'RedisManager':
    """
    Get Redis manager for cache operations (DB 1 by default).

    Returns:
        RedisManager instance configured for cache
    """
    global _redis_cache_manager
    if _redis_cache_manager is None:
        cache_db = getattr(settings, 'REDIS_CACHE_DB', 1)
        from .manager import RedisManager
        _redis_cache_manager = RedisManager(db_number=cache_db)
    return _redis_cache_manager


def get_broker_redis_manager() -> 'RedisManager':
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
        from .manager import RedisManager
        _redis_broker_manager = RedisManager(db_number=broker_db)
    return _redis_broker_manager


async def _cleanup_managers():
    """Internal function to cleanup all global managers."""
    global _redis_manager, _redis_cache_manager, _redis_broker_manager

    if _redis_manager:
        await _redis_manager.close_all()
        _redis_manager = None

    if _redis_cache_manager:
        await _redis_cache_manager.close_all()
        _redis_cache_manager = None

    if _redis_broker_manager:
        await _redis_broker_manager.close_all()
        _redis_broker_manager = None
