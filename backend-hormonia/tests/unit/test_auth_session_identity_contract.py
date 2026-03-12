"""Unit contract tests for session-backed local auth identity resolution."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import Request

from app.config import settings
from app.dependencies import auth_dependencies


pytestmark = [pytest.mark.unit, pytest.mark.auth]


def _build_request(session_id: str = "local-session-cookie") -> Request:
    request = MagicMock(spec=Request)
    request.cookies = {settings.SESSION_COOKIE_NAME: session_id}
    request.headers = {}
    request.state = SimpleNamespace()
    return request


def _canonical_session_payload(*, user_id: str | None = None) -> dict:
    resolved_user_id = user_id or str(uuid4())
    return {
        "session_id": "local-session-cookie",
        "user_id": resolved_user_id,
        "email": "local.contract@example.com",
        "full_name": "Dra. Contract",
        "role": "doctor",
        "is_active": True,
        "created_at": "2026-03-11T12:00:00-03:00",
        "updated_at": "2026-03-11T12:00:00-03:00",
        "last_login": None,
        # Intentionally omitted: firebase_uid should be optional on the happy path.
    }


@pytest.mark.asyncio
async def test_get_current_user_from_session_accepts_user_id_centric_redis_payload():
    request = _build_request()
    session_payload = _canonical_session_payload()

    redis_cache = AsyncMock()
    redis_cache.get_session = AsyncMock(return_value=session_payload)
    redis_cache.update_session_activity = AsyncMock(return_value=True)
    redis_cache.get_user_by_uid = AsyncMock(
        side_effect=AssertionError(
            "Session-backed local auth should not require firebase_uid cache lookup"
        )
    )

    result = await auth_dependencies.get_current_user_from_session(
        request=request,
        session_cookie_id="local-session-cookie",
        x_session_id=None,
        authorization=None,
        redis_cache=redis_cache,
    )

    assert result["id"] == session_payload["user_id"]
    assert result["email"] == session_payload["email"]
    assert result["full_name"] == session_payload["full_name"]
    assert result["role"] == session_payload["role"]
    assert request.state.user_id == session_payload["user_id"]
    assert request.state.user_role == session_payload["role"]
    redis_cache.get_user_by_uid.assert_not_called()


@pytest.mark.asyncio
async def test_get_current_user_from_session_prefers_session_identity_over_bearer_token():
    request = _build_request()
    session_payload = _canonical_session_payload()

    redis_cache = AsyncMock()
    redis_cache.get_session = AsyncMock(return_value=session_payload)
    redis_cache.update_session_activity = AsyncMock(return_value=True)
    redis_cache.get_user_by_uid = AsyncMock(
        side_effect=AssertionError(
            "Bearer fallback should not be needed when session cookie already resolves identity"
        )
    )

    result = await auth_dependencies.get_current_user_from_session(
        request=request,
        session_cookie_id="local-session-cookie",
        x_session_id=None,
        authorization="Bearer firebase-token-that-should-not-win",
        redis_cache=redis_cache,
    )

    assert result["id"] == session_payload["user_id"]
    redis_cache.get_session.assert_awaited_once_with("local-session-cookie")
    redis_cache.get_user_by_uid.assert_not_called()


@pytest.mark.asyncio
async def test_get_current_user_prefers_session_backed_identity_when_session_cookie_exists(monkeypatch):
    request = _build_request()
    session_payload = _canonical_session_payload()

    async def _fake_get_current_user_from_session(*args, **kwargs):
        _ = args, kwargs
        return session_payload

    monkeypatch.setattr(
        auth_dependencies,
        "get_current_user_from_session",
        _fake_get_current_user_from_session,
    )

    services = SimpleNamespace(db=MagicMock())

    result = await auth_dependencies.get_current_user(
        request=request,
        credentials=None,
        services=services,
    )

    assert str(result.id) == session_payload["user_id"]
    assert result.email == session_payload["email"]
    assert result.full_name == session_payload["full_name"]
    assert request.state.user_id == session_payload["user_id"]
    assert request.state.user_role == session_payload["role"]
