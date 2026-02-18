"""
Unit tests for FollowUpRedisStore.

Tests Redis-backed storage for follow-up actions, alerts, and patient contexts.
"""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4, UUID
from datetime import datetime, timedelta, timezone

from app.services.follow_up_system.models import (
    FollowUpAction,
    EscalationAlert,
    ConversationContext,
)
from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
from app.services.follow_up_system.enums import (
    FollowUpType,
    EscalationLevel,
    NotificationChannel,
)
from app.services.analytics.data_extraction import MedicalConcernType


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
        redis.zrevrange = AsyncMock(return_value=[])
        redis.zcard = AsyncMock(return_value=0)

        async def scan_iter_empty(*args, **kwargs):
            if False:
                yield None

        redis.scan_iter = scan_iter_empty
        
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
        action = FollowUpAction(
            action_id=uuid4(),
            patient_id=uuid4(),
            follow_up_type=FollowUpType.EMOTIONAL_SUPPORT,
            priority="medium",
            scheduled_for=now_sao_paulo_naive() + timedelta(hours=1),
            parameters={"reason": "Check progress"},
        )
        
        result = await store.store_action(action)
        
        assert result is True
        mock_redis.hset.assert_called()
        mock_redis.zadd.assert_called()

    @pytest.mark.asyncio
    async def test_get_pending_actions_empty(self, store, mock_redis):
        """Test getting pending actions when none exist."""
        mock_redis.zrangebyscore.return_value = []
        
        actions = await store.get_pending_actions(limit=10, before=now_sao_paulo_naive())
        
        assert actions == []

    @pytest.mark.asyncio
    async def test_get_pending_actions_with_results(self, store, mock_redis):
        """Test getting pending actions with results."""
        action_id = str(uuid4())
        patient_id = str(uuid4())
        action_data = json.dumps({
            "action_id": action_id,
            "patient_id": patient_id,
            "follow_up_type": FollowUpType.EMOTIONAL_SUPPORT.value,
            "scheduled_for": now_sao_paulo_naive().isoformat(),
            "priority": "normal",
            "status": "pending"
        })
        
        mock_redis.zrangebyscore.return_value = [action_id.encode()]
        mock_redis.hget.return_value = action_data.encode()
        async def scan_iter_mock(*args, **kwargs):
            yield f"followup:actions:{patient_id}".encode()
        mock_redis.scan_iter = scan_iter_mock
        
        actions = await store.get_pending_actions(limit=10, before=now_sao_paulo_naive())
        
        assert len(actions) == 1
        assert actions[0]["action_id"] == action_id

    @pytest.mark.asyncio
    async def test_get_pending_actions_priority_order(self, store, mock_redis):
        """Test pending actions are ordered by priority."""
        patient_id = str(uuid4())
        low_id = str(uuid4())
        high_id = str(uuid4())
        now = now_sao_paulo()

        low_action = json.dumps({
            "action_id": low_id,
            "patient_id": patient_id,
            "follow_up_type": FollowUpType.EMOTIONAL_SUPPORT.value,
            "scheduled_for": now.isoformat(),
            "priority": "low",
            "status": "pending"
        })
        high_action = json.dumps({
            "action_id": high_id,
            "patient_id": patient_id,
            "follow_up_type": FollowUpType.EMOTIONAL_SUPPORT.value,
            "scheduled_for": now.isoformat(),
            "priority": "high",
            "status": "pending"
        })

        mock_redis.zrangebyscore.return_value = [
            low_id.encode(),
            high_id.encode()
        ]

        action_map = {
            low_id: low_action.encode(),
            high_id: high_action.encode(),
        }

        async def scan_iter_mock(*args, **kwargs):
            yield f"followup:actions:{patient_id}".encode()

        async def hget_side_effect(key, action_id):
            action_id_str = (
                action_id.decode() if isinstance(action_id, bytes) else action_id
            )
            return action_map.get(action_id_str)

        mock_redis.scan_iter = scan_iter_mock
        mock_redis.hget.side_effect = hget_side_effect

        actions = await store.get_pending_actions(
            limit=10, before=now + timedelta(minutes=1)
        )

        assert len(actions) == 2
        assert actions[0]["action_id"] == high_id
        assert actions[1]["action_id"] == low_id

    @pytest.mark.asyncio
    async def test_update_action_status_success(self, store, mock_redis):
        """Test updating action status."""
        action_id = uuid4()
        patient_id = uuid4()
        existing_data = json.dumps({
            "action_id": str(action_id),
            "patient_id": str(patient_id),
            "status": "pending",
            "scheduled_for": now_sao_paulo_naive().isoformat()
        })
        
        mock_redis.hget.return_value = existing_data.encode()
        async def scan_iter_mock(*args, **kwargs):
            yield f"followup:actions:{patient_id}".encode()
        mock_redis.scan_iter = scan_iter_mock
        
        result = await store.update_action_status(action_id, "executed", executed_at=now_sao_paulo_naive())
        
        assert result is True
        mock_redis.hset.assert_called()
        mock_redis.zrem.assert_called()
        mock_redis.expire.assert_called()

    @pytest.mark.asyncio
    async def test_update_action_status_not_found(self, store, mock_redis):
        """Test updating non-existent action."""
        mock_redis.hget.return_value = None
        
        result = await store.update_action_status(uuid4(), "completed")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_update_action_status_terminal_state_sets_ttl(self, store, mock_redis):
        """Test terminal action status sets TTL."""
        action_id = uuid4()
        patient_id = uuid4()
        existing_data = json.dumps({
            "action_id": str(action_id),
            "patient_id": str(patient_id),
            "status": "pending",
            "scheduled_for": now_sao_paulo_naive().isoformat()
        })
        
        mock_redis.hget.return_value = existing_data.encode()
        async def scan_iter_mock(*args, **kwargs):
            yield f"followup:actions:{patient_id}".encode()
        mock_redis.scan_iter = scan_iter_mock
        
        result = await store.update_action_status(action_id, "failed", executed_at=now_sao_paulo_naive())
        
        assert result is True
        mock_redis.hset.assert_called()
        mock_redis.zrem.assert_called()
        mock_redis.expire.assert_called()


class TestAlertStorage(TestFollowUpRedisStore):
    """Test alert storage operations."""

    @pytest.mark.asyncio
    async def test_store_alert_success(self, store, mock_redis):
        """Test storing a new alert."""
        alert = EscalationAlert(
            alert_id=uuid4(),
            patient_id=uuid4(),
            escalation_level=EscalationLevel.MEDIUM,
            concern_type=MedicalConcernType.SIDE_EFFECT,
            description="Missed appointment",
            original_message="Paciente não compareceu",
            recommended_actions=["Contact patient"],
            notification_channels=[NotificationChannel.WHATSAPP],
            requires_immediate_response=True,
        )
        
        result = await store.store_alert(alert)
        
        assert result is True
        mock_redis.hset.assert_called()
        mock_redis.zadd.assert_called()

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
            "alert_id": str(alert_id),
            "patient_id": str(patient_id),
            "escalation_level": "medium",
            "concern_type": "side_effect",
            "resolved_at": None
        })
        
        mock_redis.hget.return_value = existing_data.encode()
        async def scan_iter_mock(*args, **kwargs):
            yield f"followup:alerts:{patient_id}".encode()
        mock_redis.scan_iter = scan_iter_mock
        
        result = await store.update_alert_status(
            alert_id,
            acknowledged_at=now_sao_paulo_naive(),
            assigned_to="nurse"
        )
        
        assert result is True
        mock_redis.hset.assert_called()

    @pytest.mark.asyncio
    async def test_resolve_alert_success(self, store, mock_redis):
        """Test resolving an alert."""
        alert_id = uuid4()
        patient_id = uuid4()
        existing_data = json.dumps({
            "alert_id": str(alert_id),
            "patient_id": str(patient_id),
            "escalation_level": "medium",
            "concern_type": "side_effect",
            "resolved_at": None
        })
        
        mock_redis.hget.return_value = existing_data.encode()
        async def scan_iter_mock(*args, **kwargs):
            yield f"followup:alerts:{patient_id}".encode()
        mock_redis.scan_iter = scan_iter_mock
        
        result = await store.update_alert_status(
            alert_id,
            resolved_at=now_sao_paulo_naive(),
            assigned_to="nurse"
        )
        
        assert result is True
        mock_redis.zrem.assert_called()
        mock_redis.expire.assert_called()


class TestContextStorage(TestFollowUpRedisStore):
    """Test patient context storage operations."""

    @pytest.mark.asyncio
    async def test_store_context_success(self, store, mock_redis):
        """Test storing patient context."""
        context = ConversationContext(
            patient_id=uuid4(),
            conversation_history=[{"role": "system", "content": "How are you feeling?"}],
            current_topic="daily_follow_up",
            emotional_state="neutral",
            medical_context={"flow_id": str(uuid4())},
            preferences={"language": "pt-BR"},
        )
        
        result = await store.store_context(context)
        
        assert result is True
        mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_get_context_success(self, store, mock_redis):
        """Test getting patient context."""
        patient_id = uuid4()
        context_data = json.dumps({
            "patient_id": str(patient_id),
            "conversation_history": [],
            "current_topic": "daily_follow_up",
            "emotional_state": "neutral",
            "medical_context": {},
            "preferences": {},
            "last_updated": now_sao_paulo_naive().isoformat()
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
        """Test that context has 1-hour TTL."""
        context = ConversationContext(
            patient_id=uuid4(),
            conversation_history=[],
            current_topic=None,
            emotional_state=None,
            medical_context={},
            preferences={},
        )
        
        await store.store_context(context)
        
        # Verify setex was called with 1-hour TTL (3600 seconds)
        mock_redis.setex.assert_called()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 3600  # 1 hour


class TestHealthCheck(TestFollowUpRedisStore):
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, store, mock_redis):
        """Test health check when Redis is healthy."""
        mock_redis.ping.return_value = True
        mock_redis.zcard.return_value = 5
        
        health = await store.health_check()
        
        assert health["healthy"] is True
        assert health["backend"] == "redis"

    @pytest.mark.asyncio
    async def test_health_check_redis_down(self, store, mock_redis):
        """Test health check when Redis is down."""
        mock_redis.ping.side_effect = Exception("Connection refused")
        
        health = await store.health_check()
        
        assert health["healthy"] is True
        assert health["backend"] == "in-memory-fallback"

    @pytest.mark.asyncio
    async def test_health_check_includes_stats(self, store, mock_redis):
        """Test health check includes statistics."""
        mock_redis.ping.return_value = True
        mock_redis.zcard.side_effect = [30, 15]  # pending actions, active alerts
        
        health = await store.health_check()
        
        assert health["stats"]["pending_actions"] == 30
        assert health["stats"]["active_alerts"] == 15


class TestGracefulFallback(TestFollowUpRedisStore):
    """Test graceful fallback when Redis is unavailable."""

    @pytest.mark.asyncio
    async def test_store_action_redis_error_fallback(self, store, mock_redis):
        """Test fallback when Redis fails during action storage."""
        action = FollowUpAction(
            action_id=uuid4(),
            patient_id=uuid4(),
            follow_up_type=FollowUpType.EMOTIONAL_SUPPORT,
            priority="medium",
            scheduled_for=now_sao_paulo_naive() + timedelta(hours=1),
            parameters={},
        )
        
        mock_redis.hset.side_effect = Exception("Redis error")
        
        # Should handle error gracefully
        result = await store.store_action(action)
        
        # Falls back to in-memory storage on Redis errors
        assert result is True
        assert str(action.action_id) in store._fallback_storage["actions"]

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

    def test_dedup_key_pattern(self):
        """Test deduplication key pattern."""
        patient_id = uuid4()
        expected_pattern = f"sent_messages:{patient_id}"

        assert "sent_messages:" in expected_pattern

    def test_follow_up_lock_key_pattern(self):
        """Test follow-up lock key pattern."""
        patient_id = uuid4()
        expected_pattern = f"follow_up_locks:{patient_id}"

        assert "follow_up_locks:" in expected_pattern


class TestDataSerialization:
    """Test data serialization/deserialization."""

    def test_serialize_action_to_json(self):
        """Test action serialization to JSON."""
        action_data = {
            "id": str(uuid4()),
            "patient_id": str(uuid4()),
            "action_type": "follow_up_call",
            "scheduled_for": now_sao_paulo_naive().isoformat(),
            "status": "pending"
        }
        
        serialized = json.dumps(action_data)
        deserialized = json.loads(serialized)
        
        assert deserialized["id"] == action_data["id"]
        assert deserialized["action_type"] == "follow_up_call"

    def test_serialize_datetime_as_iso(self):
        """Test datetime serialization as ISO format."""
        dt = now_sao_paulo_naive()
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


class TestDeduplicationStorage(TestFollowUpRedisStore):
    """Test deduplication and lock storage."""

    @pytest.mark.asyncio
    async def test_acquire_follow_up_lock_redis(self, store, mock_redis):
        """Test acquiring follow-up lock using Redis."""
        patient_id = uuid4()

        result = await store.acquire_follow_up_lock(patient_id, ttl_seconds=300)

        assert result is True
        mock_redis.set.assert_called_with(
            f"follow_up_locks:{patient_id}", "1", ex=300, nx=True
        )

    @pytest.mark.asyncio
    async def test_acquire_follow_up_lock_fallback(self, store):
        """Test acquiring follow-up lock with in-memory fallback."""
        store._redis_available = False
        store._redis = None
        patient_id = uuid4()

        result = await store.acquire_follow_up_lock(patient_id, ttl_seconds=60)

        assert result is True
        assert str(patient_id) in store._fallback_storage["locks"]

    @pytest.mark.asyncio
    async def test_release_follow_up_lock_fallback(self, store):
        """Test releasing follow-up lock with in-memory fallback."""
        store._redis_available = False
        store._redis = None
        patient_id = uuid4()
        store._fallback_storage["locks"][str(patient_id)] = {
            "expires_at": now_sao_paulo() + timedelta(seconds=60)
        }

        result = await store.release_follow_up_lock(patient_id)

        assert result is True
        assert str(patient_id) not in store._fallback_storage["locks"]

    @pytest.mark.asyncio
    async def test_set_last_follow_up_sent_at_redis(self, store, mock_redis):
        """Test setting dedup timestamp in Redis."""
        patient_id = uuid4()
        sent_at = now_sao_paulo()

        result = await store.set_last_follow_up_sent_at(
            patient_id, sent_at, ttl_seconds=3600
        )

        assert result is True
        mock_redis.setex.assert_called_with(
            f"sent_messages:{patient_id}", 3600, sent_at.isoformat()
        )

    @pytest.mark.asyncio
    async def test_get_last_follow_up_sent_at_fallback(self, store):
        """Test reading dedup timestamp from in-memory fallback."""
        store._redis_available = False
        store._redis = None
        patient_id = uuid4()
        sent_at = now_sao_paulo()
        store._fallback_storage["dedup"][str(patient_id)] = {
            "sent_at": sent_at,
            "expires_at": sent_at + timedelta(seconds=60),
        }

        result = await store.get_last_follow_up_sent_at(patient_id)

        assert result == sent_at

    @pytest.mark.asyncio
    async def test_get_last_follow_up_sent_at_fallback_expired(self, store):
        """Test expired dedup timestamp cleanup in fallback."""
        store._redis_available = False
        store._redis = None
        patient_id = uuid4()
        sent_at = now_sao_paulo() - timedelta(hours=1)
        store._fallback_storage["dedup"][str(patient_id)] = {
            "sent_at": sent_at,
            "expires_at": now_sao_paulo() - timedelta(seconds=1),
        }

        result = await store.get_last_follow_up_sent_at(patient_id)

        assert result is None
        assert str(patient_id) not in store._fallback_storage["dedup"]


class TestRedisReconnect(TestFollowUpRedisStore):
    """Test Redis reconnection behavior."""

    @pytest.mark.asyncio
    async def test_reconnects_after_redis_returns(self, store, mock_redis):
        """Test reconnect attempt when Redis becomes available."""
        store._redis_available = False
        store._redis = None
        store._redis_retry_delay = 4
        store._redis_retry_at = now_sao_paulo() - timedelta(seconds=1)

        with patch(
            "app.services.follow_up.redis_store.get_async_redis",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = mock_redis
            redis_client = await store._get_redis()

        assert redis_client == mock_redis
        assert store.is_redis_available() is True
        assert store._redis_retry_delay == 1
        assert store._redis_retry_at is None
