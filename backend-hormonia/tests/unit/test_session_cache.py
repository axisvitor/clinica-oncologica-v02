import pytest
import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, call
from app.core.redis_manager.session_cache import SessionCache

# Mock Redis Client
@pytest.fixture
def mock_redis_client():
    client = MagicMock()
    # Mock async methods if they were awaited directly (but here they are run in to_thread)
    # Since existing code uses asyncio.to_thread(self.redis.method, ...), 
    # the redis client methods themselves should be synchronous/standard mocks unless the client is async.
    # The current implementation assumes sync redis client wrapped in asyncio.to_thread
    return client

@pytest.fixture
def session_cache(mock_redis_client):
    cache = SessionCache(
        redis_client=mock_redis_client,
        session_ttl=3600,   # 1 hour
        max_session_age=604800  # 7 days
    )
    return cache

@pytest.fixture
def sample_session_data():
    now = datetime.now(timezone.utc)
    return {
        "user_id": "user123",
        "firebase_uid": "firebase123",
        "created_at": now.isoformat(),
        "last_activity": now.isoformat(),
        "max_age_seconds": 604800,
        "device": "test-device"
    }

@pytest.mark.asyncio
async def test_create_session(session_cache, mock_redis_client):
    """Test session creation stores correct data structure including max_age_seconds"""
    session_id = "test-session-id"
    user_id = "user123"
    firebase_uid = "firebase123"
    
    result = await session_cache.create_session(session_id, user_id, firebase_uid)
    
    assert result is True
    mock_redis_client.setex.assert_called_once()
    
    # Verify stored data
    call_args = mock_redis_client.setex.call_args
    key, ttl, value_json = call_args[0]
    
    assert key == f"session:{session_id}"
    assert ttl == 3600
    
    data = json.loads(value_json)
    assert data["user_id"] == user_id
    assert data["firebase_uid"] == firebase_uid
    assert "created_at" in data
    assert "last_activity" in data
    assert data["max_age_seconds"] == 604800

@pytest.mark.asyncio
async def test_get_session_valid_within_max_age(session_cache, mock_redis_client, sample_session_data):
    """Test valid session within max age returns data and extends TTL"""
    session_id = "test-session-id"
    key = f"session:{session_id}"
    
    # Session created 1 day ago (well within 7 days max age)
    created_at = datetime.now(timezone.utc) - timedelta(days=1)
    sample_session_data["created_at"] = created_at.isoformat()
    
    mock_redis_client.get.return_value = json.dumps(sample_session_data)
    
    result = await session_cache.get_session(session_id)
    
    assert result is not None
    assert result["user_id"] == sample_session_data["user_id"]
    
    # Verify TTL extension (inactivity reset)
    mock_redis_client.setex.assert_called_once()
    assert mock_redis_client.setex.call_args[0][1] == 3600 # session_ttl reset

@pytest.mark.asyncio
async def test_session_expires_after_max_age(session_cache, mock_redis_client, sample_session_data):
    """Test session expires if it exceeds max age, even if recently active"""
    session_id = "test-session-id"
    key = f"session:{session_id}"
    
    # Session created 8 days ago (exceeds 7 days max age)
    created_at = datetime.now(timezone.utc) - timedelta(days=8)
    sample_session_data["created_at"] = created_at.isoformat()
    mock_redis_client.get.return_value = json.dumps(sample_session_data)
    mock_redis_client.delete.return_value = 1
    
    result = await session_cache.get_session(session_id)
    
    assert result is None
    
    # Verify session was invalidated
    mock_redis_client.delete.assert_called_with(key)
    # verify we did NOT extend TTL
    mock_redis_client.setex.assert_not_called()

@pytest.mark.asyncio
async def test_session_without_created_at_assumes_now(session_cache, mock_redis_client, sample_session_data):
    """Test legacy session without created_at gets updated with current time"""
    session_id = "legacy-session-id"
    key = f"session:{session_id}"
    
    # Remove created_at to simulate legacy session
    del sample_session_data["created_at"]
    mock_redis_client.get.return_value = json.dumps(sample_session_data)
    
    result = await session_cache.get_session(session_id)
    
    assert result is not None
    assert "created_at" in result
    
    # Verify it updated the session in Redis with the new created_at
    mock_redis_client.setex.assert_called_once()
    stored_data = json.loads(mock_redis_client.setex.call_args[0][2])
    assert "created_at" in stored_data

@pytest.mark.asyncio
async def test_invalidate_all_user_sessions_uses_pipeline(session_cache, mock_redis_client):
    """Test bulk invalidation uses Redis pipeline and scan_iter"""
    firebase_uid = "user123"
    
    # Mock scan_iter to return list of keys
    keys = [b"session:1", b"session:2", b"session:3"] # Redis often returns bytes
    # But our code assumes scan_iter returns something capable of being used.
    # Mock redis client scan_iter to return generator
    mock_redis_client.scan_iter.return_value = iter(keys)
    
    # Mock get returns for these keys
    def get_side_effect(key):
        return json.dumps({"firebase_uid": firebase_uid, "user_id": "u1"})
    
    mock_redis_client.get.side_effect = get_side_effect
    
    # Mock pipeline
    pipeline = MagicMock()
    mock_redis_client.pipeline.return_value = pipeline
    pipeline.execute.return_value = [1, 1, 1] # 3 successful deletes
    
    count = await session_cache.invalidate_all_user_sessions(firebase_uid)
    
    assert count == 3
    # Verify scan_iter Called
    mock_redis_client.scan_iter.assert_called_with(match="session:*", count=100)
    # Verify pipeline used for deletes
    assert pipeline.delete.call_count == 3
    pipeline.execute.assert_called_once()

@pytest.mark.asyncio
async def test_update_session_activity_max_age_check(session_cache, mock_redis_client, sample_session_data):
    """Test update_session_activity also respects max age"""
    session_id = "test-session-id"
    created_at = datetime.now(timezone.utc) - timedelta(days=8) # Expired
    sample_session_data["created_at"] = created_at.isoformat()
    
    mock_redis_client.get.return_value = json.dumps(sample_session_data)
    mock_redis_client.delete.return_value = 1
    
    result = await session_cache.update_session_activity(session_id)
    
    assert result is False
    mock_redis_client.delete.assert_called_with(f"session:{session_id}")
    mock_redis_client.setex.assert_not_called()

@pytest.mark.asyncio
async def test_invalidate_all_user_sessions_filters_correctly(session_cache, mock_redis_client):
    """Test bulk invalidation only deletes sessions for specific user"""
    target_uid = "target-user"
    other_uid = "other-user"
    
    keys = [b"session:1", b"session:2"]
    mock_redis_client.scan_iter.return_value = iter(keys)
    
    # distinct session data
    s1 = {"firebase_uid": target_uid}
    s2 = {"firebase_uid": other_uid}
    
    mock_redis_client.get.side_effect = [json.dumps(s1), json.dumps(s2)]
    
    pipeline = MagicMock()
    mock_redis_client.pipeline.return_value = pipeline
    pipeline.execute.return_value = [1]
    
    count = await session_cache.invalidate_all_user_sessions(target_uid)
    
    assert count == 1
    # Should only delete key 1
    pipeline.delete.assert_called_once_with(b"session:1")
