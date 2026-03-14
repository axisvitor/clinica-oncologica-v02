import json
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from app.core.redis_manager.session_cache import SessionCache
from app.utils.timezone import now_sao_paulo


@pytest.fixture
def mock_redis_client():
    return MagicMock()


@pytest.fixture
def session_cache(mock_redis_client):
    return SessionCache(
        redis_client=mock_redis_client,
        session_ttl=3600,
        max_session_age=604800,
    )


@pytest.fixture
def sample_session_data():
    now = now_sao_paulo()
    return {
        "user_id": "user123",
        "created_at": now.isoformat(),
        "last_activity": now.isoformat(),
        "max_age_seconds": 604800,
        "device": "test-device",
    }


@pytest.mark.asyncio
async def test_create_session_requires_only_canonical_user_id(session_cache, mock_redis_client):
    session_id = "test-session-id"
    user_id = "user123"

    result = await session_cache.create_session(session_id, user_id)

    assert result is True
    mock_redis_client.setex.assert_called_once()
    key, ttl, value_json = mock_redis_client.setex.call_args[0]
    assert key == f"session:{session_id}"
    assert ttl == 3600

    data = json.loads(value_json)
    assert data["user_id"] == user_id
    assert "firebase_uid" not in data
    assert "created_at" in data
    assert "last_activity" in data
    assert data["max_age_seconds"] == 604800


@pytest.mark.asyncio
async def test_create_session_does_not_inject_firebase_uid_from_compat_arg(session_cache, mock_redis_client):
    await session_cache.create_session(
        "compat-arg-session",
        "user-123",
        firebase_uid="legacy-firebase-uid",
    )

    stored = json.loads(mock_redis_client.setex.call_args[0][2])
    assert stored["user_id"] == "user-123"
    assert "firebase_uid" not in stored


@pytest.mark.asyncio
async def test_get_session_valid_within_max_age(session_cache, mock_redis_client, sample_session_data):
    session_id = "test-session-id"
    created_at = now_sao_paulo() - timedelta(days=1)
    sample_session_data["created_at"] = created_at.isoformat()

    mock_redis_client.get.return_value = json.dumps(sample_session_data)

    result = await session_cache.get_session(session_id)

    assert result is not None
    assert result["user_id"] == sample_session_data["user_id"]
    mock_redis_client.setex.assert_called_once()
    assert mock_redis_client.setex.call_args[0][1] == 3600


@pytest.mark.asyncio
async def test_session_expires_after_max_age(session_cache, mock_redis_client, sample_session_data):
    session_id = "test-session-id"
    created_at = now_sao_paulo() - timedelta(days=8)
    sample_session_data["created_at"] = created_at.isoformat()
    mock_redis_client.get.return_value = json.dumps(sample_session_data)
    mock_redis_client.delete.return_value = 1

    result = await session_cache.get_session(session_id)

    assert result is None
    mock_redis_client.delete.assert_called_with(f"session:{session_id}")
    mock_redis_client.setex.assert_not_called()


@pytest.mark.asyncio
async def test_invalidate_all_user_sessions_matches_canonical_user_id_only(session_cache, mock_redis_client):
    target_user_id = "target-user"
    keys = ["session:1", "session:2", "session:3"]
    mock_redis_client.scan_iter.return_value = iter(keys)

    payloads = {
        "session:1": {"user_id": target_user_id, "firebase_uid": "legacy-a"},
        "session:2": {"user_id": "other-user", "firebase_uid": target_user_id},
        "session:3": {"id": target_user_id, "firebase_uid": "legacy-b"},
    }
    mock_redis_client.get.side_effect = lambda key: json.dumps(payloads[key])

    pipeline = MagicMock()
    mock_redis_client.pipeline.return_value = pipeline
    pipeline.execute.return_value = [1, 1]

    count = await session_cache.invalidate_all_user_sessions(target_user_id)

    assert count == 2
    mock_redis_client.scan_iter.assert_called_with(match="session:*", count=100)
    assert [call.args[0] for call in pipeline.delete.call_args_list] == [
        "session:1",
        "session:3",
    ]
    pipeline.execute.assert_called_once()


def test_list_user_sessions_matches_canonical_user_id_only(session_cache, mock_redis_client):
    target_user_id = "target-user"
    keys = ["session:1", "session:2", "session:3"]
    mock_redis_client.scan_iter.return_value = iter(keys)

    payloads = {
        "session:1": {"user_id": target_user_id, "firebase_uid": "legacy-a"},
        "session:2": {"user_id": "other-user", "firebase_uid": target_user_id},
        "session:3": {"id": target_user_id, "firebase_uid": "legacy-b"},
    }
    mock_redis_client.get.side_effect = lambda key: json.dumps(payloads[key])

    sessions = session_cache.list_user_sessions(target_user_id)

    assert [session["session_id"] for session in sessions] == ["1", "3"]
    assert all(session.get("firebase_uid") in {"legacy-a", "legacy-b"} for session in sessions)


@pytest.mark.asyncio
async def test_update_session_activity_max_age_check(session_cache, mock_redis_client, sample_session_data):
    session_id = "test-session-id"
    created_at = now_sao_paulo() - timedelta(days=8)
    sample_session_data["created_at"] = created_at.isoformat()

    mock_redis_client.get.return_value = json.dumps(sample_session_data)
    mock_redis_client.delete.return_value = 1

    result = await session_cache.update_session_activity(session_id)

    assert result is False
    mock_redis_client.delete.assert_called_with(f"session:{session_id}")
    mock_redis_client.setex.assert_not_called()
