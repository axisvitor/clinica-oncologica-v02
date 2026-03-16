"""
Tests for timeout handling in canonical session authentication.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth_dependencies import (
    _get_user_from_db_by_user_id_async,
    get_current_user_from_session,
)


@pytest.mark.asyncio
async def test_get_user_from_db_by_user_id_async_timeout():
    """Canonical user_id DB lookups should raise HTTPException 504 after retry."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(
        side_effect=[asyncio.TimeoutError(), asyncio.TimeoutError()]
    )

    with pytest.raises(HTTPException) as exc_info:
        await _get_user_from_db_by_user_id_async(str(uuid4()), mock_session)

    assert exc_info.value.status_code == 504
    assert mock_session.execute.await_count == 2


@pytest.mark.asyncio
async def test_get_current_user_from_session_db_timeout_returns_504(monkeypatch):
    """Canonical user_id DB timeout in get_current_user_from_session should return 504."""
    from app.core.redis_manager import FirebaseRedisCache
    from fastapi import Request

    canonical_user_id = str(uuid4())
    mock_redis_cache = AsyncMock(spec=FirebaseRedisCache)
    mock_redis_cache.get_session.return_value = {"user_id": canonical_user_id}
    mock_redis_cache.update_session_activity.return_value = None
    mock_redis_cache.get_user_by_id.return_value = None
    mock_redis_cache.get_user_by_uid = AsyncMock()

    async_session = AsyncMock(spec=AsyncSession)
    async_session.execute = AsyncMock(
        side_effect=[asyncio.TimeoutError(), asyncio.TimeoutError()]
    )

    class DummySessionContext:
        async def __aenter__(self):
            return async_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def fake_get_async_session_factory():
        def factory():
            return DummySessionContext()

        return factory

    monkeypatch.setattr(
        "app.database.get_async_session_factory",
        fake_get_async_session_factory,
    )

    mock_request = MagicMock(spec=Request)
    mock_request.state = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_from_session(
            request=mock_request,
            session_cookie_id="test_session_id",
            x_session_id=None,
            authorization=None,
            redis_cache=mock_redis_cache,
        )

    assert exc_info.value.status_code == 504
    assert "timeout" in exc_info.value.detail.lower()
    mock_redis_cache.get_user_by_uid.assert_not_called()


@pytest.mark.asyncio
async def test_get_current_user_from_session_db_timeout_logs_error(monkeypatch, caplog):
    """Canonical user_id timeout logs should include the canonical identity prefix."""
    from app.core.redis_manager import FirebaseRedisCache
    from fastapi import Request
    import logging

    # When the Postgres harness runs, alembic/env.py calls
    # fileConfig(alembic.ini) with disable_existing_loggers=True (the default).
    # Because this test file imports app.dependencies.auth_dependencies at
    # module level, the logger already exists when fileConfig fires, so it gets
    # its `disabled` flag set to True.  A disabled logger silently drops all
    # records — caplog never sees them.  Reset the flag here so caplog works
    # under both SQLite and Postgres harnesses.
    target_logger = logging.getLogger("app.dependencies.auth_dependencies")
    _orig_disabled = target_logger.disabled
    _orig_propagate = target_logger.propagate
    target_logger.disabled = False
    target_logger.propagate = True

    caplog.set_level(logging.ERROR, logger="app.dependencies.auth_dependencies")

    canonical_user_id = str(uuid4())
    canonical_user_prefix = canonical_user_id[:8]
    mock_redis_cache = AsyncMock(spec=FirebaseRedisCache)
    mock_redis_cache.get_session.return_value = {"user_id": canonical_user_id}
    mock_redis_cache.update_session_activity.return_value = None
    mock_redis_cache.get_user_by_id.return_value = None
    mock_redis_cache.get_user_by_uid = AsyncMock()

    async_session = AsyncMock(spec=AsyncSession)
    async_session.execute = AsyncMock(
        side_effect=[asyncio.TimeoutError(), asyncio.TimeoutError()]
    )

    class DummySessionContext:
        async def __aenter__(self):
            return async_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def fake_get_async_session_factory():
        def factory():
            return DummySessionContext()

        return factory

    monkeypatch.setattr(
        "app.database.get_async_session_factory",
        fake_get_async_session_factory,
    )

    mock_request = MagicMock(spec=Request)
    mock_request.state = MagicMock()

    try:
        with pytest.raises(HTTPException):
            await get_current_user_from_session(
                request=mock_request,
                session_cookie_id="test_session_id",
                x_session_id=None,
                authorization=None,
                redis_cache=mock_redis_cache,
            )

        logged_messages = [
            record.getMessage()
            for record in caplog.records
            if record.name == "app.dependencies.auth_dependencies"
        ]
        assert any(canonical_user_prefix in message for message in logged_messages)
        assert any("timeout" in message.lower() for message in logged_messages)
    finally:
        target_logger.disabled = _orig_disabled
        target_logger.propagate = _orig_propagate


@pytest.mark.asyncio
async def test_cancelled_error_handling():
    """CancelledError from canonical user_id DB lookups should propagate."""
    mock_session = AsyncMock(spec=AsyncSession)

    async def cancelled_execute(*args, **kwargs):
        raise asyncio.CancelledError()

    mock_session.execute = cancelled_execute

    with pytest.raises(asyncio.CancelledError):
        await _get_user_from_db_by_user_id_async(str(uuid4()), mock_session)
