"""Database infrastructure package.

Provides:
- Async engine and session factory (async_engine)
- Dual-mode session mixin for sync/async services (dual_session)
"""

from app.core.database.async_engine import (
    AsyncSessionLocal,
    get_async_db,
    get_async_engine,
    get_async_session_factory,
)
from app.core.database.dual_session import DualSessionMixin

__all__ = [
    "get_async_db",
    "get_async_engine",
    "get_async_session_factory",
    "AsyncSessionLocal",
    "DualSessionMixin",
]
