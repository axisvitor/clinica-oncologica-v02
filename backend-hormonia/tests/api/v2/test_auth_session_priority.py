"""
Integration tests for session ID priority and Firebase UID validation order.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, Request

from app.config import settings
from app.dependencies.auth_dependencies import get_current_user_from_session


def _build_request() -> Request:
    request = MagicMock(spec=Request)
    request.state = MagicMock()
    return request


def _build_redis_cache(firebase_uid: str) -> AsyncMock:
    redis_cache = AsyncMock()
    redis_cache.get_session = AsyncMock(return_value={"firebase_uid": firebase_uid})
    redis_cache.update_session_activity = AsyncMock(return_value=None)
    redis_cache.get_user_by_uid = AsyncMock(
        return_value={
            "id": "user-123",
            "firebase_uid": firebase_uid,
            "email": "user@example.com",
            "full_name": "Test User",
            "role": "doctor",
            "is_active": True,
        }
    )
    redis_cache.cache_user_data = AsyncMock()
    return redis_cache


@pytest.mark.asyncio
async def test_session_auth_with_cookie_only(monkeypatch):
    """Authenticate using cookie only."""
    monkeypatch.setattr(settings, "ENABLE_COOKIE_PRIORITY", True)

    request = _build_request()
    firebase_uid = "e" * 28
    redis_cache = _build_redis_cache(firebase_uid)

    result = await get_current_user_from_session(
        request=request,
        session_cookie_id="cookie-session",
        x_session_id=None,
        authorization=None,
        redis_cache=redis_cache,
    )

    assert result["firebase_uid"] == firebase_uid
    redis_cache.get_session.assert_awaited_once_with("cookie-session")


@pytest.mark.asyncio
async def test_session_auth_with_header_only(monkeypatch):
    """Authenticate using X-Session-ID header only."""
    monkeypatch.setattr(settings, "ENABLE_COOKIE_PRIORITY", True)

    request = _build_request()
    firebase_uid = "f" * 28
    redis_cache = _build_redis_cache(firebase_uid)

    result = await get_current_user_from_session(
        request=request,
        session_cookie_id=None,
        x_session_id="header-session",
        authorization=None,
        redis_cache=redis_cache,
    )

    assert result["firebase_uid"] == firebase_uid
    redis_cache.get_session.assert_awaited_once_with("header-session")


@pytest.mark.asyncio
async def test_session_auth_priority_cookie_over_header(monkeypatch):
    """Cookie should win when both cookie and header are present."""
    monkeypatch.setattr(settings, "ENABLE_COOKIE_PRIORITY", True)

    request = _build_request()
    cookie_uid = "g" * 28
    header_uid = "h" * 28

    redis_cache = AsyncMock()
    redis_cache.update_session_activity = AsyncMock(return_value=None)
    redis_cache.cache_user_data = AsyncMock()
    redis_cache.get_session = AsyncMock(
        side_effect=lambda session_id: {
            "firebase_uid": cookie_uid if session_id == "cookie-session" else header_uid
        }
    )
    redis_cache.get_user_by_uid = AsyncMock(
        side_effect=lambda firebase_uid: {
            "id": "user-123",
            "firebase_uid": firebase_uid,
            "email": "user@example.com",
            "full_name": "Test User",
            "role": "doctor",
            "is_active": True,
        }
    )

    result = await get_current_user_from_session(
        request=request,
        session_cookie_id="cookie-session",
        x_session_id="header-session",
        authorization=None,
        redis_cache=redis_cache,
    )

    assert result["firebase_uid"] == cookie_uid
    redis_cache.get_session.assert_awaited_once_with("cookie-session")


@pytest.mark.asyncio
async def test_firebase_uid_validation_before_query(monkeypatch):
    """Invalid UID should be rejected before cache/DB lookup."""
    monkeypatch.setattr(settings, "ENABLE_COOKIE_PRIORITY", True)

    request = _build_request()
    redis_cache = AsyncMock()
    redis_cache.get_session = AsyncMock(return_value={"firebase_uid": "invalid_uid!!"})
    redis_cache.update_session_activity = AsyncMock(return_value=None)
    redis_cache.get_user_by_uid = AsyncMock()

    mocked_db_query = AsyncMock()
    monkeypatch.setattr(
        "app.dependencies.auth_dependencies._get_user_from_db_async",
        mocked_db_query,
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_from_session(
            request=request,
            session_cookie_id="cookie-session",
            x_session_id=None,
            authorization=None,
            redis_cache=redis_cache,
        )

    assert exc_info.value.status_code == 401
    redis_cache.get_user_by_uid.assert_not_called()
    mocked_db_query.assert_not_called()
