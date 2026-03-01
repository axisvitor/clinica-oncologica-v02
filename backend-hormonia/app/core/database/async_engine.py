"""Async database engine, session factory, and FastAPI dependency.

Canonical location for all async database infrastructure.
Separated from sync config (app/database.py) per Phase 21 architecture decision.

Usage:
    from app.core.database import get_async_db
    # or
    from app.core.database.async_engine import get_async_db
"""

import asyncio
import logging
import ssl as ssl_module
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

logger = logging.getLogger(__name__)

_async_engine = None
_async_session_factory = None


class _AsyncSessionFactoryProxy:
    """Lazy proxy that defers async session factory initialization."""

    def __call__(self, *args, **kwargs):
        return get_async_session_factory()(*args, **kwargs)


def get_async_engine():
    """Get or create an AsyncEngine for async database operations."""
    global _async_engine

    if _async_engine is None:
        sync_url = settings.DATABASE_URL
        async_url = sync_url.replace(
            "postgresql+psycopg://", "postgresql+asyncpg://"
        ).replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://"
        ).replace(
            "postgresql://", "postgresql+asyncpg://"
        )

        connect_args: dict = {}
        if "sslmode=require" in async_url or "sslmode=verify" in async_url:
            async_url = (
                async_url.replace("?sslmode=require", "")
                .replace("&sslmode=require", "")
                .replace("?sslmode=verify-ca", "")
                .replace("?sslmode=verify-full", "")
            )
            ssl_context = ssl_module.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl_module.CERT_NONE
            connect_args["ssl"] = ssl_context

        logger.info(
            "Initializing AsyncEngine (SSL=%s)",
            "enabled" if connect_args.get("ssl") else "disabled",
        )

        _async_engine = create_async_engine(
            async_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=1800,
            echo=settings.APP_ENABLE_DEBUG,
            connect_args=connect_args,
        )

    return _async_engine


def get_async_session_factory():
    """Get or create an async session factory."""
    global _async_session_factory

    if _async_session_factory is None:
        engine = get_async_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    return _async_session_factory


AsyncSessionLocal = _AsyncSessionFactoryProxy()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get async database session."""
    try:
        asyncio.get_running_loop()
    except RuntimeError as exc:
        raise RuntimeError(
            "get_async_db() must be called from an async context. "
            "Celery tasks should use get_db() or get_scoped_session() instead."
        ) from exc

    async_session_factory = get_async_session_factory()
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Async database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()
