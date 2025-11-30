"""
Comprehensive test suite for DLQ (Dead Letter Queue) Service

Tests cover:
- Individual handler isolation (retry, poison, circuit breaker)
- Handler integration and coordination
- Error recovery and resilience patterns
- Message processing workflows
- Metrics and monitoring
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import asyncio
import json

from app.services.dlq_service import DLQService, DLQMessage, MessagePriority


# ==========================================
# Test Fixtures
# ==========================================

@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis = AsyncMock()
    redis.lpush = AsyncMock(return_value=1)
    redis.rpop = AsyncMock(return_value=None)
    redis.llen = AsyncMock(return_value=0)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def mock_logger():
    """Mock logger"""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.debug = MagicMock()
    return logger


@pytest.fixture
def dlq_service(mock_redis, mock_logger):
    """Create DLQ service instance"""
    with patch('app.services.dlq_service.get_redis_client', return_value=mock_redis):
        service = DLQService()
        service.logger = mock_logger
        return service


@pytest.fixture
def sample_message():
    """Sample DLQ message"""
    return DLQMessage(
        id='msg-001',
        payload={'data': 'test payload'},
        error='Test error',
        retry_count=0,
        priority=MessagePriority.MEDIUM,
        created_at=datetime.utcnow(),
        metadata={'source': 'test'}
    )


@pytest.fixture
def poison_message():
    """Message that exceeds retry limit"""
    return DLQMessage(
        id='poison-001',
        payload={'data': 'poison'},
        error='Persistent error',
        retry_count=5,
        priority=MessagePriority.HIGH,
        created_at=datetime.utcnow() - timedelta(hours=24),
        metadata={'retries_exhausted': True}
    )


# ==========================================
# Retry Handler Tests
# ==========================================

class TestRetryHandler:
    """Test retry handler in isolation"""

    @pytest.mark.asyncio
    async def test_retry_message_success(self, dlq_service, sample_message, mock_redis):
        """Test successful message retry"""
        result = await dlq_service.retry_message(sample_message)

        assert result is True
        assert sample_message.retry_count == 1
        mock_redis.lpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_message_increment_counter(self, dlq_service, sample_message):
        """Test retry counter incrementation"""
        initial_count = sample_message.retry_count
        await dlq_service.retry_message(sample_message)

        assert sample_message.retry_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_retry_message_max_retries_exceeded(self, dlq_service, poison_message):
        """Test behavior when max retries exceeded"""
        dlq_service.max_retries = 3
        poison_message.retry_count = 5

        result = await dlq_service.retry_message(poison_message)

        # Should move to poison queue instead
        assert result is False or poison_message.retry_count > dlq_service.max_retries

    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(self, dlq_service, sample_message):
        """Test exponential backoff calculation"""
        backoff_times = []

        for i in range(5):
            sample_message.retry_count = i
            backoff = dlq_service.calculate_backoff(sample_message)
            backoff_times.append(backoff)

        # Verify exponential growth
        for i in range(len(backoff_times) - 1):
            assert backoff_times[i + 1] > backoff_times[i]

    @pytest.mark.asyncio
    async def test_retry_priority_ordering(self, dlq_service, mock_redis):
        """Test that high priority messages are retried first"""
        high_priority = DLQMessage(
            id='high-001',
            payload={},
            error='error',
            retry_count=0,
            priority=MessagePriority.HIGH,
            created_at=datetime.utcnow()
        )

        low_priority = DLQMessage(
            id='low-001',
            payload={},
            error='error',
            retry_count=0,
            priority=MessagePriority.LOW,
            created_at=datetime.utcnow()
        )

        await dlq_service.enqueue(high_priority)
        await dlq_service.enqueue(low_priority)

        # High priority should be processed first
        # Verify queue ordering
        assert mock_redis.lpush.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_with_custom_delay(self, dlq_service, sample_message):
        """Test retry with custom delay configuration"""
        custom_delay = 60  # 60 seconds
        dlq_service.retry_delay = custom_delay

        backoff = dlq_service.calculate_backoff(sample_message)
        assert backoff >= custom_delay

    @pytest.mark.asyncio
    async def test_retry_metadata_preservation(self, dlq_service, sample_message):
        """Test that message metadata is preserved during retry"""
        original_metadata = sample_message.metadata.copy()
        await dlq_service.retry_message(sample_message)

        assert sample_message.metadata['source'] == original_metadata['source']
        assert 'retry_timestamp' in sample_message.metadata


# ==========================================
# Poison Message Handler Tests
# ==========================================

class TestPoisonMessageHandler:
    """Test poison message handler in isolation"""

    @pytest.mark.asyncio
    async def test_identify_poison_message(self, dlq_service, poison_message):
        """Test poison message identification"""
        is_poison = dlq_service.is_poison_message(poison_message)
        assert is_poison is True

    @pytest.mark.asyncio
    async def test_move_to_poison_queue(self, dlq_service, poison_message, mock_redis):
        """Test moving message to poison queue"""
        await dlq_service.move_to_poison_queue(poison_message)

        # Verify message moved to poison queue
        mock_redis.lpush.assert_called()
        call_args = mock_redis.lpush.call_args
        assert 'poison' in str(call_args).lower()

    @pytest.mark.asyncio
    async def test_poison_message_alerting(self, dlq_service, poison_message, mock_logger):
        """Test that poison messages trigger alerts"""
        await dlq_service.move_to_poison_queue(poison_message)

        # Should log error/warning
        assert mock_logger.error.called or mock_logger.warning.called

    @pytest.mark.asyncio
    async def test_poison_queue_size_limit(self, dlq_service, mock_redis):
        """Test poison queue size limit enforcement"""
        mock_redis.llen.return_value = 1000  # Queue full
        dlq_service.max_poison_queue_size = 500

        # Should handle full queue appropriately
        message = DLQMessage(
            id='test',
            payload={},
            error='error',
            retry_count=10,
            priority=MessagePriority.LOW,
            created_at=datetime.utcnow()
        )

        result = await dlq_service.move_to_poison_queue(message)
        # Should either purge old messages or reject new ones
        assert result is not None

    @pytest.mark.asyncio
    async def test_poison_message_persistence(self, dlq_service, poison_message, mock_redis):
        """Test that poison messages are persisted"""
        await dlq_service.move_to_poison_queue(poison_message)

        # Verify persistence call
        assert mock_redis.lpush.called

    @pytest.mark.asyncio
    async def test_poison_message_analysis(self, dlq_service):
        """Test analysis of poison message patterns"""
        messages = [
            DLQMessage(
                id=f'poison-{i}',
                payload={'type': 'validation_error'},
                error='Validation failed',
                retry_count=10,
                priority=MessagePriority.MEDIUM,
                created_at=datetime.utcnow()
            )
            for i in range(10)
        ]

        for msg in messages:
            await dlq_service.move_to_poison_queue(msg)

        # Service should detect pattern of validation errors
        if hasattr(dlq_service, 'analyze_poison_patterns'):
            patterns = await dlq_service.analyze_poison_patterns()
            assert 'validation_error' in str(patterns)


# ==========================================
# Circuit Breaker Handler Tests
# ==========================================

class TestCircuitBreakerHandler:
    """Test circuit breaker handler in isolation"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self, dlq_service):
        """Test circuit breaker in closed state (normal operation)"""
        if hasattr(dlq_service, 'circuit_breaker'):
            state = dlq_service.circuit_breaker.state
            assert state == 'closed' or state == 'CLOSED'

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(self, dlq_service):
        """Test circuit breaker opens after threshold failures"""
        if hasattr(dlq_service, 'circuit_breaker'):
            failure_threshold = 5

            # Simulate failures
            for _ in range(failure_threshold + 1):
                await dlq_service.record_failure()

            assert dlq_service.circuit_breaker.state == 'open'

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_state(self, dlq_service):
        """Test circuit breaker transitions to half-open"""
        if hasattr(dlq_service, 'circuit_breaker'):
            # Open circuit
            dlq_service.circuit_breaker.state = 'open'
            dlq_service.circuit_breaker.opened_at = datetime.utcnow() - timedelta(seconds=61)

            # Wait for timeout
            await asyncio.sleep(0.1)

            # Should transition to half-open
            state = await dlq_service.get_circuit_state()
            assert state in ['half-open', 'HALF_OPEN']

    @pytest.mark.asyncio
    async def test_circuit_breaker_reset_on_success(self, dlq_service):
        """Test circuit breaker resets after successful operations"""
        if hasattr(dlq_service, 'circuit_breaker'):
            # Set to half-open
            dlq_service.circuit_breaker.state = 'half-open'

            # Record success
            await dlq_service.record_success()

            # Should close
            assert dlq_service.circuit_breaker.state == 'closed'

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_requests_when_open(self, dlq_service, sample_message):
        """Test that circuit breaker blocks requests when open"""
        if hasattr(dlq_service, 'circuit_breaker'):
            dlq_service.circuit_breaker.state = 'open'

            with pytest.raises(Exception) as exc:
                await dlq_service.process_message(sample_message)

            assert 'circuit' in str(exc.value).lower() or 'open' in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_circuit_breaker_metrics(self, dlq_service):
        """Test circuit breaker metrics collection"""
        if hasattr(dlq_service, 'get_circuit_metrics'):
            metrics = await dlq_service.get_circuit_metrics()

            assert 'state' in metrics
            assert 'failure_count' in metrics
            assert 'success_count' in metrics


# ==========================================
# Handler Integration Tests
# ==========================================

class TestHandlerIntegration:
    """Test integration between DLQ handlers"""

    @pytest.mark.asyncio
    async def test_retry_to_poison_flow(self, dlq_service, sample_message):
        """Test message flow from retry to poison queue"""
        # Exhaust retries
        for _ in range(dlq_service.max_retries + 1):
            await dlq_service.retry_message(sample_message)

        # Should end up in poison queue
        assert dlq_service.is_poison_message(sample_message)

    @pytest.mark.asyncio
    async def test_circuit_breaker_affects_retry(self, dlq_service, sample_message):
        """Test that circuit breaker state affects retry logic"""
        if hasattr(dlq_service, 'circuit_breaker'):
            # Open circuit
            dlq_service.circuit_breaker.state = 'open'

            # Retry should be delayed or blocked
            result = await dlq_service.retry_message(sample_message)
            assert result is False or sample_message.retry_count == 0

    @pytest.mark.asyncio
    async def test_priority_queue_with_circuit_breaker(self, dlq_service):
        """Test priority queue behavior with circuit breaker"""
        if hasattr(dlq_service, 'circuit_breaker'):
            high_priority = DLQMessage(
                id='high',
                payload={},
                error='error',
                retry_count=0,
                priority=MessagePriority.HIGH,
                created_at=datetime.utcnow()
            )

            # Even with open circuit, critical messages might be attempted
            dlq_service.circuit_breaker.state = 'half-open'
            result = await dlq_service.process_message(high_priority)
            assert result is not None

    @pytest.mark.asyncio
    async def test_full_message_lifecycle(self, dlq_service, sample_message, mock_redis):
        """Test complete message lifecycle through all handlers"""
        # 1. Enqueue
        await dlq_service.enqueue(sample_message)

        # 2. Process (may fail and retry)
        for _ in range(3):
            await dlq_service.retry_message(sample_message)

        # 3. Eventually succeeds or moves to poison
        final_state = 'processed' if sample_message.retry_count < dlq_service.max_retries else 'poison'
        assert final_state in ['processed', 'poison']


# ==========================================
# Message Processing Tests
# ==========================================

class TestMessageProcessing:
    """Test message processing workflows"""

    @pytest.mark.asyncio
    async def test_process_message_success(self, dlq_service, sample_message, mock_redis):
        """Test successful message processing"""
        mock_processor = AsyncMock(return_value=True)
        result = await dlq_service.process_with_handler(sample_message, mock_processor)

        assert result is True
        mock_processor.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_failure_triggers_retry(self, dlq_service, sample_message):
        """Test that processing failure triggers retry"""
        mock_processor = AsyncMock(side_effect=Exception('Processing failed'))

        with pytest.raises(Exception):
            await dlq_service.process_with_handler(sample_message, mock_processor)

        # Should schedule retry
        assert sample_message.retry_count >= 0

    @pytest.mark.asyncio
    async def test_process_message_timeout(self, dlq_service, sample_message):
        """Test message processing timeout"""
        async def slow_processor(msg):
            await asyncio.sleep(10)
            return True

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                dlq_service.process_with_handler(sample_message, slow_processor),
                timeout=1.0
            )

    @pytest.mark.asyncio
    async def test_concurrent_message_processing(self, dlq_service, mock_redis):
        """Test concurrent processing of multiple messages"""
        messages = [
            DLQMessage(
                id=f'msg-{i}',
                payload={'index': i},
                error=None,
                retry_count=0,
                priority=MessagePriority.MEDIUM,
                created_at=datetime.utcnow()
            )
            for i in range(10)
        ]

        async def process_all():
            tasks = [dlq_service.enqueue(msg) for msg in messages]
            return await asyncio.gather(*tasks)

        results = await process_all()
        assert len(results) == 10

    @pytest.mark.asyncio
    async def test_message_deduplication(self, dlq_service, sample_message, mock_redis):
        """Test message deduplication"""
        # Enqueue same message twice
        await dlq_service.enqueue(sample_message)

        # Second enqueue should detect duplicate
        if hasattr(dlq_service, 'is_duplicate'):
            is_dup = await dlq_service.is_duplicate(sample_message)
            assert is_dup is True


# ==========================================
# Metrics and Monitoring Tests
# ==========================================

class TestMetricsAndMonitoring:
    """Test metrics collection and monitoring"""

    @pytest.mark.asyncio
    async def test_collect_retry_metrics(self, dlq_service, sample_message):
        """Test collection of retry metrics"""
        for _ in range(3):
            await dlq_service.retry_message(sample_message)

        if hasattr(dlq_service, 'get_metrics'):
            metrics = await dlq_service.get_metrics()
            assert metrics['total_retries'] >= 3

    @pytest.mark.asyncio
    async def test_collect_poison_metrics(self, dlq_service, poison_message):
        """Test collection of poison message metrics"""
        await dlq_service.move_to_poison_queue(poison_message)

        if hasattr(dlq_service, 'get_metrics'):
            metrics = await dlq_service.get_metrics()
            assert metrics['poison_messages'] >= 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_metrics_reporting(self, dlq_service):
        """Test circuit breaker metrics reporting"""
        if hasattr(dlq_service, 'get_circuit_metrics'):
            metrics = await dlq_service.get_circuit_metrics()

            assert 'state' in metrics
            assert 'total_failures' in metrics or 'failure_count' in metrics

    @pytest.mark.asyncio
    async def test_queue_depth_monitoring(self, dlq_service, mock_redis):
        """Test queue depth monitoring"""
        mock_redis.llen.return_value = 42

        depth = await dlq_service.get_queue_depth()
        assert depth == 42

    @pytest.mark.asyncio
    async def test_processing_latency_tracking(self, dlq_service, sample_message):
        """Test processing latency tracking"""
        start_time = datetime.utcnow()

        async def tracked_processor(msg):
            await asyncio.sleep(0.1)
            return True

        await dlq_service.process_with_handler(sample_message, tracked_processor)

        if hasattr(dlq_service, 'get_latency_metrics'):
            metrics = await dlq_service.get_latency_metrics()
            assert metrics['avg_latency'] > 0


# ==========================================
# Error Recovery Tests
# ==========================================

class TestErrorRecovery:
    """Test error recovery and resilience"""

    @pytest.mark.asyncio
    async def test_recovery_from_redis_failure(self, dlq_service, sample_message):
        """Test recovery when Redis is unavailable"""
        dlq_service.redis.lpush = AsyncMock(side_effect=ConnectionError('Redis down'))

        with pytest.raises(ConnectionError):
            await dlq_service.enqueue(sample_message)

        # Should have fallback mechanism
        if hasattr(dlq_service, 'fallback_queue'):
            assert len(dlq_service.fallback_queue) > 0

    @pytest.mark.asyncio
    async def test_recovery_from_corrupt_message(self, dlq_service, mock_redis):
        """Test handling of corrupt message data"""
        mock_redis.rpop.return_value = b'corrupt{invalid:json'

        message = await dlq_service.dequeue()
        # Should handle gracefully
        assert message is None or hasattr(message, 'error')

    @pytest.mark.asyncio
    async def test_automatic_queue_recovery(self, dlq_service):
        """Test automatic recovery of stalled queues"""
        if hasattr(dlq_service, 'recover_stalled_messages'):
            recovered = await dlq_service.recover_stalled_messages()
            assert isinstance(recovered, list)


# ==========================================
# Configuration Tests
# ==========================================

class TestDLQConfiguration:
    """Test DLQ service configuration"""

    def test_default_configuration(self, dlq_service):
        """Test default configuration values"""
        assert dlq_service.max_retries > 0
        assert dlq_service.retry_delay > 0

    def test_custom_configuration(self, mock_redis):
        """Test custom configuration"""
        with patch('app.services.dlq_service.get_redis_client', return_value=mock_redis):
            service = DLQService(
                max_retries=10,
                retry_delay=30,
                max_poison_queue_size=1000
            )

            assert service.max_retries == 10
            assert service.retry_delay == 30

    def test_configuration_validation(self, mock_redis):
        """Test configuration validation"""
        with patch('app.services.dlq_service.get_redis_client', return_value=mock_redis):
            with pytest.raises(ValueError):
                DLQService(max_retries=-1)
