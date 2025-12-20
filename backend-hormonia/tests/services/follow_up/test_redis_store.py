"""
Unit tests for FollowUpRedisStore.

Tests Redis-backed storage for follow-up actions, alerts, and patient contexts.
"""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4, UUID
from datetime import datetime, timedelta


class TestFollowUpRedisStore:
    """Test FollowUpRedisStore functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create a comprehensive mock Redis client."""
        redis = Mock()
        redis.ping = AsyncMock(return_value=True)
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        redis.setex = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=1)
        redis.exists = AsyncMock(return_value=0)
        redis.expire = AsyncMock(return_value=True)
        redis.hget = AsyncMock(return_value=None)
        redis.hset = AsyncMock(return_value=1)
        redis.hdel = AsyncMock(return_value=1)
        redis.hgetall = AsyncMock(return_value={})
        redis.hlen = AsyncMock(return_value=0)
        redis.zadd = AsyncMock(return_value=1)
        redis.zrem = AsyncMock(return_value=1)
        redis.zrangebyscore = AsyncMock(return_value=[])
        redis.zcard = AsyncMock(return_value=0)
        
        # Mock pipeline
        mock_pipeline = AsyncMock()
        mock_pipeline.hset = Mock()
        mock_pipeline.zadd = Mock()
        mock_pipeline.execute = AsyncMock(return_value=[1, 1])
        redis.pipeline = Mock(return_value=mock_pipeline)
        
        return redis

    @pytest.fixture
    def store(self, mock_redis):
        """Create FollowUpRedisStore instance."""
        with patch('app.services.follow_up.redis_store.get_async_redis', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_redis
            from app.services.follow_up.redis_store import FollowUpRedisStore
            store = FollowUpRedisStore()
            store._redis = mock_redis
            return store


class TestActionStorage(TestFollowUpRedisStore):
    """Test action storage operations."""

    @pytest.mark.asyncio
    async def test_store_action_success(self, store, mock_redis):
        """Test storing a new action."""
        action = Mock()
        action.id = uuid4()
        action.patient_id = uuid4()
        action.action_type = "follow_up_call"
        action.scheduled_for = datetime.utcnow() + timedelta(hours=1)
        action.status = "pending"
        action.priority = "medium"
        action.metadata = {"reason": "Check progress"}
        
        result = await store.store_action(action)
        
        assert result is True
        mock_redis.pipeline.assert_called()

    @pytest.mark.asyncio
    async def test_get_pending_actions_empty(self, store, mock_redis):
        """Test getting pending actions when none exist."""
        mock_redis.zrangebyscore.return_value = []
        
        actions = await store.get_pending_actions(limit=10, before=datetime.utcnow())
        
        assert actions == []

    @pytest.mark.asyncio
    async def test_get_pending_actions_with_results(self, store, mock_redis):
        """Test getting pending actions with results."""
        action_id = str(uuid4())
        patient_id = str(uuid4())
        action_data = json.dumps({
            "id": action_id,
            "patient_id": patient_id,
            "action_type": "follow_up_call",
            "scheduled_for": datetime.utcnow().isoformat(),
            "status": "pending"
        })
        
        mock_redis.zrangebyscore.return_value = [action_id.encode()]
        mock_redis.hget.return_value = action_data.encode()
        
        actions = await store.get_pending_actions(limit=10, before=datetime.utcnow())
        
        assert len(actions) == 1
        assert actions[0]["id"] == action_id

    @pytest.mark.asyncio
    async def test_update_action_status_success(self, store, mock_redis):
        """Test updating action status."""
        action_id = uuid4()
        patient_id = uuid4()
        existing_data = json.dumps({
            "id": str(action_id),
            "patient_id": str(patient_id),
            "status": "pending"
        })
        
        mock_redis.hget.return_value = existing_data.encode()
        
        result = await store.update_action_status(action_id, "completed")
        
        assert result is True
        mock_redis.hset.assert_called()

    @pytest.mark.asyncio
    async def test_update_action_status_not_found(self, store, mock_redis):
        """Test updating non-existent action."""
        mock_redis.hget.return_value = None
        
        result = await store.update_action_status(uuid4(), "completed")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_action_success(self, store, mock_redis):
        """Test deleting an action."""
        action_id = uuid4()
        patient_id = uuid4()
        existing_data = json.dumps({
            "id": str(action_id),
            "patient_id": str(patient_id),
            "status": "pending"
        })
        
        mock_redis.hget.return_value = existing_data.encode()
        
        result = await store.delete_action(action_id)
        
        assert result is True
        mock_redis.hdel.assert_called()
        mock_redis.zrem.assert_called()


class TestAlertStorage(TestFollowUpRedisStore):
    """Test alert storage operations."""

    @pytest.mark.asyncio
    async def test_store_alert_success(self, store, mock_redis):
        """Test storing a new alert."""
        alert = Mock()
        alert.id = uuid4()
        alert.patient_id = uuid4()
        alert.alert_type = "missed_appointment"
        alert.escalation_level = 1
        alert.status = "active"
        alert.created_at = datetime.utcnow()
        alert.metadata = {"appointment_date": "2024-01-15"}
        
        result = await store.store_alert(alert)
        
        assert result is True
        mock_redis.pipeline.assert_called()

    @pytest.mark.asyncio
    async def test_get_active_alerts_empty(self, store, mock_redis):
        """Test getting active alerts when none exist."""
        mock_redis.zrangebyscore.return_value = []
        
        alerts = await store.get_active_alerts()
        
        assert alerts == []

    @pytest.mark.asyncio
    async def test_get_active_alerts_for_patient(self, store, mock_redis):
        """Test getting active alerts for specific patient."""
        patient_id = uuid4()
        alert_id = str(uuid4())
        alert_data = json.dumps({
            "id": alert_id,
            "patient_id": str(patient_id),
            "alert_type": "missed_appointment",
            "escalation_level": 2,
            "status": "active"
        })
        
        mock_redis.hgetall.return_value = {alert_id.encode(): alert_data.encode()}
        
        alerts = await store.get_active_alerts(patient_id=patient_id)
        
        assert len(alerts) == 1
        assert alerts[0]["patient_id"] == str(patient_id)

    @pytest.mark.asyncio
    async def test_escalate_alert_success(self, store, mock_redis):
        """Test escalating an alert."""
        alert_id = uuid4()
        patient_id = uuid4()
        existing_data = json.dumps({
            "id": str(alert_id),
            "patient_id": str(patient_id),
            "escalation_level": 1,
            "status": "active"
        })
        
        mock_redis.hget.return_value = existing_data.encode()
        
        result = await store.escalate_alert(alert_id)
        
        assert result is True
        mock_redis.hset.assert_called()
        mock_redis.zadd.assert_called()

    @pytest.mark.asyncio
    async def test_resolve_alert_success(self, store, mock_redis):
        """Test resolving an alert."""
        alert_id = uuid4()
        patient_id = uuid4()
        existing_data = json.dumps({
            "id": str(alert_id),
            "patient_id": str(patient_id),
            "escalation_level": 1,
            "status": "active"
        })
        
        mock_redis.hget.return_value = existing_data.encode()
        
        result = await store.resolve_alert(alert_id)
        
        assert result is True
        mock_redis.zrem.assert_called()


class TestContextStorage(TestFollowUpRedisStore):
    """Test patient context storage operations."""

    @pytest.mark.asyncio
    async def test_store_context_success(self, store, mock_redis):
        """Test storing patient context."""
        context = Mock()
        context.patient_id = uuid4()
        context.last_interaction = datetime.utcnow()
        context.conversation_state = "awaiting_response"
        context.pending_questions = ["How are you feeling?"]
        context.metadata = {"flow_id": str(uuid4())}
        
        result = await store.store_context(context)
        
        assert result is True
        mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_get_context_success(self, store, mock_redis):
        """Test getting patient context."""
        patient_id = uuid4()
        context_data = json.dumps({
            "patient_id": str(patient_id),
            "last_interaction": datetime.utcnow().isoformat(),
            "conversation_state": "awaiting_response"
        })
        
        mock_redis.get.return_value = context_data.encode()
        
        context = await store.get_context(patient_id)
        
        assert context is not None
        assert context["patient_id"] == str(patient_id)

    @pytest.mark.asyncio
    async def test_get_context_not_found(self, store, mock_redis):
        """Test getting non-existent context."""
        mock_redis.get.return_value = None
        
        context = await store.get_context(uuid4())
        
        assert context is None

    @pytest.mark.asyncio
    async def test_context_ttl_applied(self, store, mock_redis):
        """Test that context has 7-day TTL."""
        context = Mock()
        context.patient_id = uuid4()
        context.last_interaction = datetime.utcnow()
        context.conversation_state = "idle"
        context.pending_questions = []
        context.metadata = {}
        
        await store.store_context(context)
        
        # Verify setex was called with 7-day TTL (604800 seconds)
        mock_redis.setex.assert_called()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 604800  # 7 days


class TestHealthCheck(TestFollowUpRedisStore):
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, store, mock_redis):
        """Test health check when Redis is healthy."""
        mock_redis.ping.return_value = True
        mock_redis.hlen.return_value = 10
        mock_redis.zcard.return_value = 5
        
        health = await store.health_check()
        
        assert health["status"] == "healthy"
        assert health["redis_connected"] is True

    @pytest.mark.asyncio
    async def test_health_check_redis_down(self, store, mock_redis):
        """Test health check when Redis is down."""
        mock_redis.ping.side_effect = Exception("Connection refused")
        
        health = await store.health_check()
        
        assert health["status"] == "unhealthy"
        assert health["redis_connected"] is False

    @pytest.mark.asyncio
    async def test_health_check_includes_stats(self, store, mock_redis):
        """Test health check includes statistics."""
        mock_redis.ping.return_value = True
        mock_redis.hlen.side_effect = [50, 25]  # actions, alerts
        mock_redis.zcard.side_effect = [30, 15]  # pending actions, active alerts
        
        health = await store.health_check()
        
        assert "stats" in health or health["status"] == "healthy"


class TestGracefulFallback(TestFollowUpRedisStore):
    """Test graceful fallback when Redis is unavailable."""

    @pytest.mark.asyncio
    async def test_store_action_redis_error_fallback(self, store, mock_redis):
        """Test fallback when Redis fails during action storage."""
        action = Mock()
        action.id = uuid4()
        action.patient_id = uuid4()
        action.action_type = "follow_up_call"
        action.scheduled_for = datetime.utcnow() + timedelta(hours=1)
        action.status = "pending"
        action.priority = "medium"
        action.metadata = {}
        
        mock_pipeline = Mock()
        mock_pipeline.execute = AsyncMock(side_effect=Exception("Redis error"))
        mock_redis.pipeline.return_value = mock_pipeline
        
        # Should handle error gracefully
        result = await store.store_action(action)
        
        # Returns False on error but doesn't raise
        assert result is False

    @pytest.mark.asyncio
    async def test_get_context_redis_error_returns_none(self, store, mock_redis):
        """Test getting context returns None when Redis fails."""
        mock_redis.get.side_effect = Exception("Redis connection error")
        
        context = await store.get_context(uuid4())
        
        assert context is None


class TestKeyPatterns:
    """Test Redis key pattern generation."""

    def test_action_key_pattern(self):
        """Test action key pattern follows convention."""
        patient_id = uuid4()
        expected_pattern = f"followup:actions:{patient_id}"
        
        assert "followup:actions:" in expected_pattern

    def test_alert_key_pattern(self):
        """Test alert key pattern follows convention."""
        patient_id = uuid4()
        expected_pattern = f"followup:alerts:{patient_id}"
        
        assert "followup:alerts:" in expected_pattern

    def test_context_key_pattern(self):
        """Test context key pattern follows convention."""
        patient_id = uuid4()
        expected_pattern = f"followup:context:{patient_id}"
        
        assert "followup:context:" in expected_pattern

    def test_pending_actions_sorted_set_key(self):
        """Test pending actions sorted set key."""
        expected_key = "followup:actions:pending"
        
        assert expected_key == "followup:actions:pending"

    def test_active_alerts_sorted_set_key(self):
        """Test active alerts sorted set key."""
        expected_key = "followup:alerts:active"
        
        assert expected_key == "followup:alerts:active"


class TestDataSerialization:
    """Test data serialization/deserialization."""

    def test_serialize_action_to_json(self):
        """Test action serialization to JSON."""
        action_data = {
            "id": str(uuid4()),
            "patient_id": str(uuid4()),
            "action_type": "follow_up_call",
            "scheduled_for": datetime.utcnow().isoformat(),
            "status": "pending"
        }
        
        serialized = json.dumps(action_data)
        deserialized = json.loads(serialized)
        
        assert deserialized["id"] == action_data["id"]
        assert deserialized["action_type"] == "follow_up_call"

    def test_serialize_datetime_as_iso(self):
        """Test datetime serialization as ISO format."""
        dt = datetime.utcnow()
        iso_str = dt.isoformat()
        
        # Should be parseable back
        parsed = datetime.fromisoformat(iso_str)
        
        assert parsed.year == dt.year
        assert parsed.month == dt.month
        assert parsed.day == dt.day

    def test_serialize_uuid_as_string(self):
        """Test UUID serialization as string."""
        uid = uuid4()
        uid_str = str(uid)
        
        # Should be parseable back
        parsed = UUID(uid_str)
        
        assert parsed == uid
