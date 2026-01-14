"""
Tests for database timeout handling in authentication.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth_dependencies import (
    get_current_user_from_session,
    _get_user_from_db_async,
)
@pytest.mark.asyncio
async def test_get_user_from_db_async_timeout():
    """Test that database query timeout raises HTTPException 504 after retry."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(
        side_effect=[asyncio.TimeoutError(), asyncio.TimeoutError()]
    )

    with pytest.raises(HTTPException) as exc_info:
        await _get_user_from_db_async("test_firebase_uid", mock_session)

    assert exc_info.value.status_code == 504
    assert mock_session.execute.await_count == 2


@pytest.mark.asyncio
async def test_get_current_user_from_session_db_timeout_returns_504(
    monkeypatch, test_user
):
    """Test that database timeout in get_current_user_from_session returns 504."""
    from app.core.redis_manager import FirebaseRedisCache
    from fastapi import Request

    # Arrange: Mock Redis cache with valid session but slow DB query
    firebase_uid = "testfirebaseuid1234567890123"
    mock_redis_cache = AsyncMock(spec=FirebaseRedisCache)
    mock_redis_cache.get_session.return_value = {"firebase_uid": firebase_uid}
    mock_redis_cache.update_session_activity.return_value = None
    mock_redis_cache.get_user_by_uid.return_value = None  # Force DB query

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
        "app.core.database.get_async_session_factory",
        fake_get_async_session_factory,
    )

    mock_request = MagicMock(spec=Request)
    mock_request.state = MagicMock()

    # Act & Assert: Should raise HTTPException 504
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


@pytest.mark.asyncio
async def test_get_current_user_from_session_db_timeout_logs_error(
    monkeypatch, caplog, test_user
):
    """Test that database timeout logs error with firebase_uid."""
    from app.core.redis_manager import FirebaseRedisCache
    from fastapi import Request
    import logging

    caplog.set_level(logging.ERROR)

    # Arrange: Mock Redis cache with valid session but slow DB query
    firebase_uid = "testfirebaseuid1234567890123"
    firebase_uid_prefix = firebase_uid[:8]
    mock_redis_cache = AsyncMock(spec=FirebaseRedisCache)
    mock_redis_cache.get_session.return_value = {"firebase_uid": firebase_uid}
    mock_redis_cache.update_session_activity.return_value = None
    mock_redis_cache.get_user_by_uid.return_value = None

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
        "app.core.database.get_async_session_factory",
        fake_get_async_session_factory,
    )

    mock_request = MagicMock(spec=Request)
    mock_request.state = MagicMock()

    # Act
    with pytest.raises(HTTPException):
        await get_current_user_from_session(
            request=mock_request,
            session_cookie_id="test_session_id",
            x_session_id=None,
            authorization=None,
            redis_cache=mock_redis_cache,
        )

    # Assert: Check log contains firebase_uid
    assert any(firebase_uid_prefix in record.message for record in caplog.records)
    assert any("timeout" in record.message.lower() for record in caplog.records)


@pytest.mark.asyncio
async def test_cancelled_error_handling():
    """Test that CancelledError is properly handled."""
    # Arrange: Mock AsyncSession
    mock_session = AsyncMock(spec=AsyncSession)

    async def cancelled_execute(*args, **kwargs):
        raise asyncio.CancelledError()

    mock_session.execute = cancelled_execute

    # Act & Assert: Should raise CancelledError
    with pytest.raises(asyncio.CancelledError):
        await _get_user_from_db_async("test_firebase_uid", mock_session)
