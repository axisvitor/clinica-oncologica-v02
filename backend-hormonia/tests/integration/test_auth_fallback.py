"""
Integration-style tests for Redis/PostgreSQL fallback and retry behavior.
"""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import Request

from app.dependencies.auth_dependencies import (
    _get_user_from_db_by_user_id_async,
    get_current_user_from_session,
)
from app.models.user import User, UserRole


def _build_request() -> Request:
    request = MagicMock(spec=Request)
    request.state = MagicMock()
    return request


@asynccontextmanager
async def _dummy_async_session():
    yield object()


class _DummySessionFactory:
    def __call__(self):
        return _dummy_async_session()


def _patch_async_session_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy_factory = _DummySessionFactory()
    monkeypatch.setattr(
        "app.database.get_async_session_factory",
        lambda: dummy_factory,
    )


def _build_user(*, user_id: str | None = None, firebase_uid: str) -> User:
    return User(
        id=UUID(user_id) if user_id else uuid4(),
        firebase_uid=firebase_uid,
        email="fallback.user@example.com",
        full_name="Fallback User",
        role=UserRole.DOCTOR,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_redis_timeout_fallback_to_postgresql(monkeypatch):
    """Authentication should succeed via PostgreSQL session fallback when Redis times out."""
    request = _build_request()
    user = _build_user(firebase_uid="a" * 28)

    redis_cache = AsyncMock()
    redis_cache.get_session = AsyncMock(side_effect=asyncio.TimeoutError())
    redis_cache.update_session_activity = AsyncMock()
    redis_cache.get_user_by_id = AsyncMock()
    redis_cache.get_user_by_uid = AsyncMock()
    redis_cache.cache_user_data_by_user_id = AsyncMock()
    redis_cache.cache_user_data = AsyncMock()
    redis_cache.create_session = AsyncMock(return_value=True)

    async def _fake_get_user_by_session(_session_id, _session):
        return user

    monkeypatch.setattr(
        "app.dependencies.auth_dependencies._get_user_from_db_by_session",
        _fake_get_user_by_session,
    )
    _patch_async_session_factory(monkeypatch)

    result = await get_current_user_from_session(
        request=request,
        session_cookie_id="session-timeout",
        x_session_id=None,
        authorization=None,
        redis_cache=redis_cache,
    )

    assert result["id"] == str(user.id)
    assert result["email"] == user.email
    assert "firebase_uid" not in result
    redis_cache.get_user_by_uid.assert_not_called()
    cached_call = redis_cache.cache_user_data_by_user_id.await_args
    assert cached_call.args[0] == str(user.id)
    assert cached_call.kwargs["ttl"] == 900
    assert cached_call.args[1]["id"] == str(user.id)
    assert cached_call.args[1]["email"] == user.email
    assert "permissions" not in cached_call.args[1]
    redis_cache.cache_user_data.assert_not_called()
    redis_cache.create_session.assert_awaited_once()
    create_session_call = redis_cache.create_session.await_args
    assert create_session_call.kwargs["user_id"] == str(user.id)
    assert create_session_call.kwargs["firebase_uid"] is None
    assert "firebase_uid" not in create_session_call.kwargs["metadata"]


@pytest.mark.asyncio
async def test_session_activity_update_failure_non_blocking(monkeypatch):
    """Session activity update failures should not block canonical authentication."""
    request = _build_request()
    canonical_user_id = str(uuid4())
    firebase_uid = "b" * 28

    redis_cache = AsyncMock()
    redis_cache.get_session = AsyncMock(return_value={"user_id": canonical_user_id})
    redis_cache.update_session_activity = AsyncMock(side_effect=asyncio.TimeoutError())
    redis_cache.get_user_by_id = AsyncMock(
        return_value={
            "id": canonical_user_id,
            "firebase_uid": firebase_uid,
            "email": "user@example.com",
            "full_name": "Test User",
            "role": "doctor",
            "is_active": True,
        }
    )
    redis_cache.get_user_by_uid = AsyncMock()

    result = await get_current_user_from_session(
        request=request,
        session_cookie_id="session-activity",
        x_session_id=None,
        authorization=None,
        redis_cache=redis_cache,
    )

    assert result["id"] == canonical_user_id
    assert result["email"] == "user@example.com"
    assert "firebase_uid" not in result
    redis_cache.update_session_activity.assert_awaited_once()
    redis_cache.get_user_by_uid.assert_not_called()


@pytest.mark.asyncio
async def test_db_query_retry_on_timeout():
    """Canonical user_id DB query should retry once after a timeout."""
    user = _build_user(firebase_uid="c" * 28)

    result_proxy = MagicMock()
    result_proxy.scalar_one_or_none.return_value = user

    async_session = AsyncMock()
    async_session.execute = AsyncMock(
        side_effect=[asyncio.TimeoutError(), result_proxy]
    )

    result = await _get_user_from_db_by_user_id_async(str(user.id), async_session)

    assert result == user
    assert async_session.execute.await_count == 2
