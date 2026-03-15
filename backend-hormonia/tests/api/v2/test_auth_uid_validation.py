"""
Security tests for canonical session identity rejection order.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, Request

from app.dependencies.auth_dependencies import get_current_user_from_session


@pytest.mark.asyncio
async def test_invalid_firebase_uid_only_session_payload_rejected_before_cache(monkeypatch):
    """Malformed firebase_uid-only session payloads should fail before any identity lookup."""
    from app.core.redis_manager import FirebaseRedisCache

    mock_redis_cache = AsyncMock(spec=FirebaseRedisCache)
    mock_redis_cache.get_session.return_value = {"firebase_uid": "invalid_uid!!"}
    mock_redis_cache.update_session_activity.return_value = None
    mock_redis_cache.get_user_by_id = AsyncMock()
    mock_redis_cache.get_user_by_uid = AsyncMock()

    mocked_db_query = AsyncMock()
    monkeypatch.setattr(
        "app.dependencies.auth_dependencies._get_user_from_db_by_user_id_async",
        mocked_db_query,
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

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid session data"
    mock_redis_cache.get_user_by_id.assert_not_called()
    mock_redis_cache.get_user_by_uid.assert_not_called()
    mocked_db_query.assert_not_called()


@pytest.mark.asyncio
async def test_sql_injection_like_firebase_uid_only_session_payload_blocked(monkeypatch):
    """SQL injection-like firebase_uid strings should fail closed as malformed session payloads."""
    from app.core.redis_manager import FirebaseRedisCache

    mock_redis_cache = AsyncMock(spec=FirebaseRedisCache)
    mock_redis_cache.get_session.return_value = {
        "firebase_uid": "uid12345DROPtableusers--9999"
    }
    mock_redis_cache.update_session_activity.return_value = None
    mock_redis_cache.get_user_by_id = AsyncMock()
    mock_redis_cache.get_user_by_uid = AsyncMock()

    mocked_db_query = AsyncMock()
    monkeypatch.setattr(
        "app.dependencies.auth_dependencies._get_user_from_db_by_user_id_async",
        mocked_db_query,
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

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid session data"
    mock_redis_cache.get_user_by_id.assert_not_called()
    mock_redis_cache.get_user_by_uid.assert_not_called()
    mocked_db_query.assert_not_called()
