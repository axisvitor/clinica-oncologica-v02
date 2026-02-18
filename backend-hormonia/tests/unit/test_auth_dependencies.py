"""
Unit tests for authentication dependencies.
"""

from unittest.mock import AsyncMock, MagicMock, call
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request

from app.config import settings
from app.core.permissions import Permission, PermissionChecker
from app.dependencies.auth_dependencies import (
    GenericRedisCache,
    _get_user_from_db_by_session,
    _validate_firebase_uid,
    get_current_user_from_session,
)
from app.models.user import UserRole


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
    return redis_cache


def test_validate_firebase_uid_valid():
    """Valid 28-char UID should not raise."""
    uid = "a" * 28
    _validate_firebase_uid(uid)


def test_validate_firebase_uid_invalid_length():
    """Invalid UID length should raise 401."""
    with pytest.raises(HTTPException) as exc:
        _validate_firebase_uid("abc123")
    assert exc.value.status_code == 401


def test_validate_firebase_uid_sql_injection():
    """UID with SQL injection should raise 401."""
    with pytest.raises(HTTPException) as exc:
        _validate_firebase_uid("'; DROP TABLE users; --")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_session_id_priority_cookie_first(monkeypatch):
    """Cookie should take priority over header and bearer."""
    monkeypatch.setattr(settings, "ENABLE_COOKIE_PRIORITY", True)

    request = _build_request()
    firebase_uid = "b" * 28
    redis_cache = _build_redis_cache(firebase_uid)

    await get_current_user_from_session(
        request=request,
        session_cookie_id="cookie-session",
        x_session_id="header-session",
        authorization="Bearer bearer-session",
        redis_cache=redis_cache,
    )

    redis_cache.get_session.assert_awaited_once_with("cookie-session")


@pytest.mark.asyncio
async def test_session_id_priority_header_second(monkeypatch):
    """Header should be used when cookie is missing."""
    monkeypatch.setattr(settings, "ENABLE_COOKIE_PRIORITY", True)

    request = _build_request()
    firebase_uid = "c" * 28
    redis_cache = _build_redis_cache(firebase_uid)

    await get_current_user_from_session(
        request=request,
        session_cookie_id=None,
        x_session_id="header-session",
        authorization="Bearer bearer-session",
        redis_cache=redis_cache,
    )

    redis_cache.get_session.assert_awaited_once_with("header-session")


@pytest.mark.asyncio
async def test_session_id_priority_bearer_fallback(monkeypatch):
    """Bearer should be used only as fallback."""
    monkeypatch.setattr(settings, "ENABLE_COOKIE_PRIORITY", True)

    request = _build_request()
    firebase_uid = "d" * 28
    redis_cache = _build_redis_cache(firebase_uid)

    await get_current_user_from_session(
        request=request,
        session_cookie_id=None,
        x_session_id=None,
        authorization="Bearer bearer-session",
        redis_cache=redis_cache,
    )

    redis_cache.get_session.assert_awaited_once_with("bearer-session")


def test_has_permission_admin():
    """Admin should have all permissions."""
    assert PermissionChecker.has_permission(UserRole.ADMIN, Permission.USER_DELETE)


def test_has_permission_doctor():
    """Doctor should not have admin permissions."""
    assert not PermissionChecker.has_permission(UserRole.DOCTOR, Permission.USER_DELETE)
    assert PermissionChecker.has_permission(UserRole.DOCTOR, Permission.PATIENT_READ)


@pytest.mark.asyncio
async def test_generic_redis_cache_delete_pattern_uses_scan_iter():
    """delete_pattern should scan with pattern/count and delete matching keys."""
    redis_client = MagicMock()
    redis_client.scan_iter.return_value = iter(["cache:1", "cache:2"])
    cache = GenericRedisCache(redis_client)

    result = await cache.delete_pattern("cache:*")

    assert result is True
    redis_client.scan_iter.assert_called_once_with(match="cache:*", count=100)
    redis_client.delete.assert_called_once_with("cache:1", "cache:2")


@pytest.mark.asyncio
async def test_generic_redis_cache_delete_pattern_batches_large_keyspace():
    """delete_pattern should delete scanned keys in bounded batches."""
    redis_client = MagicMock()
    scanned_keys = [f"cache:{index}" for index in range(205)]
    redis_client.scan_iter.return_value = iter(scanned_keys)
    cache = GenericRedisCache(redis_client)

    result = await cache.delete_pattern("cache:*")

    assert result is True
    redis_client.scan_iter.assert_called_once_with(match="cache:*", count=100)
    assert redis_client.delete.call_count == 3
    assert redis_client.delete.call_args_list == [
        call(*scanned_keys[0:100]),
        call(*scanned_keys[100:200]),
        call(*scanned_keys[200:205]),
    ]


@pytest.mark.asyncio
async def test_generic_redis_cache_delete_pattern_preserves_false_on_error():
    """delete_pattern should keep fail-closed return contract."""
    redis_client = MagicMock()
    redis_client.scan_iter.side_effect = RuntimeError("redis unavailable")
    cache = GenericRedisCache(redis_client)

    result = await cache.delete_pattern("cache:*")

    assert result is False
    redis_client.delete.assert_not_called()


@pytest.mark.asyncio
async def test_get_user_from_db_by_session_enforces_revoked_filter():
    """Fallback DB lookup must exclude revoked sessions."""
    async_session = AsyncMock()
    result_proxy = MagicMock()
    result_proxy.scalar_one_or_none.return_value = None
    async_session.execute.return_value = result_proxy

    await _get_user_from_db_by_session(str(uuid4()), async_session)

    stmt = async_session.execute.call_args.args[0]
    rendered = str(stmt)
    assert "sessions.revoked_at IS NULL" in rendered
    assert "sessions.id =" in rendered


@pytest.mark.asyncio
async def test_get_user_from_db_by_session_supports_legacy_session_token():
    """Fallback DB lookup should support legacy token identifiers."""
    async_session = AsyncMock()
    result_proxy = MagicMock()
    result_proxy.scalar_one_or_none.return_value = None
    async_session.execute.return_value = result_proxy

    await _get_user_from_db_by_session("legacy-session-token", async_session)

    stmt = async_session.execute.call_args.args[0]
    rendered = str(stmt)
    assert "sessions.session_token =" in rendered
    assert "sessions.revoked_at IS NULL" in rendered
