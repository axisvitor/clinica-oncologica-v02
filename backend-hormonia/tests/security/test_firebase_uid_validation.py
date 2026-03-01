"""
Security tests for Firebase UID validation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException, Request

from app.core.redis_manager import FirebaseRedisCache
from app.dependencies.auth_dependencies import (
    get_current_user_from_session,
    _validate_firebase_uid,
)

pytestmark = [pytest.mark.security, pytest.mark.asyncio]

INVALID_UID_MESSAGE = "Invalid Firebase UID format (audit_id: firebase_uid_format)"


def _build_request() -> Request:
    request = MagicMock(spec=Request)
    request.state = MagicMock()
    return request


def _build_redis_cache(firebase_uid: str, user_data=None) -> AsyncMock:
    mock_redis_cache = AsyncMock(spec=FirebaseRedisCache)
    mock_redis_cache.get_session = AsyncMock(
        return_value={"firebase_uid": firebase_uid, "user_id": "user-123"}
    )
    mock_redis_cache.update_session_activity = AsyncMock(return_value=None)
    mock_redis_cache.get_user_by_uid = AsyncMock(return_value=user_data)
    mock_redis_cache.cache_user_data = AsyncMock()
    return mock_redis_cache


async def _call_get_current_user_from_session(mock_redis_cache, mock_request):
    return await get_current_user_from_session(
        request=mock_request,
        session_cookie_id="test_session_id",
        x_session_id=None,
        authorization=None,
        redis_cache=mock_redis_cache,
    )


class TestFirebaseUIDValidation:
    """Testes de seguranca para validacao de Firebase UID."""

    async def test_invalid_uid_rejected_before_cache(self, monkeypatch):
        firebase_uid = "invalid-uid-123"
        mock_redis_cache = _build_redis_cache(firebase_uid)
        mock_request = _build_request()

        mocked_db_query = AsyncMock()
        monkeypatch.setattr(
            "app.dependencies.auth_dependencies._get_user_from_db_async",
            mocked_db_query,
        )

        with pytest.raises(HTTPException) as exc_info:
            await _call_get_current_user_from_session(mock_redis_cache, mock_request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == INVALID_UID_MESSAGE
        mock_redis_cache.get_user_by_uid.assert_not_called()
        mocked_db_query.assert_not_called()

    @pytest.mark.parametrize(
        "firebase_uid",
        [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "../../etc/passwd",
        ],
    )
    async def test_sql_injection_blocked(self, monkeypatch, firebase_uid):
        mock_redis_cache = _build_redis_cache(firebase_uid)
        mock_request = _build_request()

        mocked_db_query = AsyncMock()
        monkeypatch.setattr(
            "app.dependencies.auth_dependencies._get_user_from_db_async",
            mocked_db_query,
        )

        with pytest.raises(HTTPException) as exc_info:
            await _call_get_current_user_from_session(mock_redis_cache, mock_request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == INVALID_UID_MESSAGE
        mock_redis_cache.get_user_by_uid.assert_not_called()
        mocked_db_query.assert_not_called()

    async def test_session_hijacking_prevented(self, monkeypatch):
        firebase_uid = "MALFORMED_UID_HERE"
        mock_redis_cache = _build_redis_cache(firebase_uid)
        mock_request = _build_request()

        mocked_db_query = AsyncMock()
        monkeypatch.setattr(
            "app.dependencies.auth_dependencies._get_user_from_db_async",
            mocked_db_query,
        )

        with pytest.raises(HTTPException) as exc_info:
            await _call_get_current_user_from_session(mock_redis_cache, mock_request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == INVALID_UID_MESSAGE
        mock_redis_cache.get_user_by_uid.assert_not_called()
        mocked_db_query.assert_not_called()

    @pytest.mark.parametrize(
        "firebase_uid",
        [
            "<script>alert('xss')</script>",
            "uid@#$%^&*()",
            "uid\n\r\t",
            "uid with spaces",
        ],
    )
    async def test_special_characters_rejected(self, monkeypatch, firebase_uid):
        mock_redis_cache = _build_redis_cache(firebase_uid)
        mock_request = _build_request()

        mocked_db_query = AsyncMock()
        monkeypatch.setattr(
            "app.dependencies.auth_dependencies._get_user_from_db_async",
            mocked_db_query,
        )

        with pytest.raises(HTTPException) as exc_info:
            await _call_get_current_user_from_session(mock_redis_cache, mock_request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == INVALID_UID_MESSAGE
        mock_redis_cache.get_user_by_uid.assert_not_called()
        mocked_db_query.assert_not_called()

    @pytest.mark.parametrize(
        "firebase_uid",
        [
            "short",
            "a" * 129,
        ],
    )
    async def test_uid_length_limits_rejected(self, monkeypatch, firebase_uid):
        mock_redis_cache = _build_redis_cache(firebase_uid)
        mock_request = _build_request()

        mocked_db_query = AsyncMock()
        monkeypatch.setattr(
            "app.dependencies.auth_dependencies._get_user_from_db_async",
            mocked_db_query,
        )

        with pytest.raises(HTTPException) as exc_info:
            await _call_get_current_user_from_session(mock_redis_cache, mock_request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == INVALID_UID_MESSAGE
        mock_redis_cache.get_user_by_uid.assert_not_called()
        mocked_db_query.assert_not_called()

    @pytest.mark.parametrize(
        "firebase_uid",
        [
            "a" * 28,
            "b" * 28,
        ],
    )
    async def test_valid_uid_passes_validation(self, monkeypatch, firebase_uid):
        _validate_firebase_uid(firebase_uid)

        user_data = {
            "id": "user-123",
            "firebase_uid": firebase_uid,
            "email": "user@example.com",
            "full_name": "Test User",
            "role": "doctor",
            "is_active": True,
        }

        mock_redis_cache = _build_redis_cache(firebase_uid, user_data=user_data)
        mock_request = _build_request()

        mocked_db_query = AsyncMock()
        monkeypatch.setattr(
            "app.dependencies.auth_dependencies._get_user_from_db_async",
            mocked_db_query,
        )

        result = await _call_get_current_user_from_session(mock_redis_cache, mock_request)

        assert result["firebase_uid"] == firebase_uid
        assert result["is_active"] is True
        assert "permissions" in result
        mock_redis_cache.get_user_by_uid.assert_awaited_once_with(firebase_uid)
        mocked_db_query.assert_not_called()
