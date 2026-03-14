"""Focused contract tests for cookie-only staff session resolution."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request

from app.dependencies.auth_dependencies import get_current_user_from_session


pytestmark = [pytest.mark.api, pytest.mark.auth]


def _build_request() -> Request:
    request = MagicMock(spec=Request)
    request.state = SimpleNamespace()
    return request


def _canonical_session_payload(*, user_id: str | None = None, email: str = "user@example.com") -> dict:
    resolved_user_id = user_id or str(uuid4())
    return {
        "session_id": "cookie-session",
        "user_id": resolved_user_id,
        "email": email,
        "full_name": "Test User",
        "role": "doctor",
        "is_active": True,
        "created_at": "2026-03-14T10:00:00-03:00",
        "updated_at": "2026-03-14T10:30:00-03:00",
        "last_login": None,
    }


def _build_redis_cache(session_payload: dict) -> AsyncMock:
    redis_cache = AsyncMock()
    redis_cache.get_session = AsyncMock(return_value=session_payload)
    redis_cache.update_session_activity = AsyncMock(return_value=None)
    redis_cache.get_user_by_id = AsyncMock(
        side_effect=AssertionError(
            "Embedded canonical session payload should not require user_id cache lookup"
        )
    )
    redis_cache.get_user_by_uid = AsyncMock(
        side_effect=AssertionError(
            "Cookie-only session auth should not require firebase_uid cache lookup"
        )
    )
    redis_cache.cache_user_data = AsyncMock()
    redis_cache.cache_user_data_by_user_id = AsyncMock()
    return redis_cache


@pytest.mark.asyncio
async def test_session_auth_with_cookie_only_sets_canonical_request_state():
    request = _build_request()
    session_payload = _canonical_session_payload()
    redis_cache = _build_redis_cache(session_payload)

    result = await get_current_user_from_session(
        request=request,
        session_cookie_id="cookie-session",
        x_session_id=None,
        authorization=None,
        redis_cache=redis_cache,
    )

    assert result["id"] == session_payload["user_id"]
    assert result["email"] == session_payload["email"]
    assert result["role"] == session_payload["role"]
    assert request.state.session_id == "cookie-session"
    assert request.state.user_id == session_payload["user_id"]
    assert request.state.user_role == session_payload["role"]
    redis_cache.get_session.assert_awaited_once_with("cookie-session")
    redis_cache.get_user_by_id.assert_not_called()
    redis_cache.get_user_by_uid.assert_not_called()


@pytest.mark.asyncio
async def test_session_auth_ignores_header_and_bearer_when_cookie_is_present():
    request = _build_request()
    cookie_payload = _canonical_session_payload(email="cookie@example.com")
    legacy_payload = _canonical_session_payload(email="legacy@example.com")

    redis_cache = _build_redis_cache(cookie_payload)
    redis_cache.get_session = AsyncMock(
        side_effect=lambda session_id: cookie_payload if session_id == "cookie-session" else legacy_payload
    )

    result = await get_current_user_from_session(
        request=request,
        session_cookie_id="cookie-session",
        x_session_id="header-session",
        authorization="Bearer bearer-session",
        redis_cache=redis_cache,
    )

    assert result["email"] == cookie_payload["email"]
    assert request.state.session_id == "cookie-session"
    redis_cache.get_session.assert_awaited_once_with("cookie-session")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("x_session_id", "authorization"),
    [
        ("header-session", None),
        (None, "Bearer bearer-session"),
    ],
)
async def test_session_auth_rejects_legacy_transport_without_cookie(
    x_session_id: str | None,
    authorization: str | None,
):
    request = _build_request()
    redis_cache = AsyncMock()
    redis_cache.get_session = AsyncMock()
    redis_cache.update_session_activity = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_from_session(
            request=request,
            session_cookie_id=None,
            x_session_id=x_session_id,
            authorization=authorization,
            redis_cache=redis_cache,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Session cookie required"
    redis_cache.get_session.assert_not_awaited()
    assert not hasattr(request.state, "session_id")
    assert not hasattr(request.state, "user_id")
    assert not hasattr(request.state, "user_role")
