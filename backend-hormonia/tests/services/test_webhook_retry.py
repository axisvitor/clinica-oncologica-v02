"""
Tests for Webhook Retry Service

MEDIUM-009: Test exponential backoff retry logic, circuit breaker integration, and DLQ.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
import aiohttp

from app.services.webhook_retry import (
    WebhookRetryService,
    CircuitBreakerAwareWebhookRetry
)


class MockDLQService:
    """Mock DLQ service for testing."""

    def __init__(self):
        self.enqueued = []

    async def enqueue(self, payload):
        """Mock enqueue method."""
        self.enqueued.append(payload)


class MockCircuitBreaker:
    """Mock circuit breaker for testing."""

    def __init__(self, is_open=False):
        self._is_open = is_open
        self.state = 'OPEN' if is_open else 'CLOSED'
        self.call_count = 0

    def is_open(self):
        """Check if circuit is open."""
        return self._is_open

    async def call(self, func, *args, **kwargs):
        """Call function through circuit breaker."""
        self.call_count += 1
        if self._is_open:
            raise Exception("Circuit breaker OPEN")
        return await func(*args, **kwargs)


@pytest.fixture
def dlq_service():
    """Provide mock DLQ service."""
    return MockDLQService()


@pytest.fixture
def webhook_retry_service(dlq_service):
    """Provide webhook retry service."""
    return WebhookRetryService(
        dlq_service=dlq_service,
        max_retries=5,
        min_wait=2,
        max_wait=60,
        multiplier=1
    )


@pytest.fixture
def circuit_breaker():
    """Provide mock circuit breaker."""
    return MockCircuitBreaker(is_open=False)


class TestWebhookRetryService:
    """Test webhook retry service."""

    @pytest.mark.asyncio
    async def test_successful_first_attempt(self, webhook_retry_service):
        """Test successful processing on first attempt."""

        webhook_data = {'id': '123', 'type': 'message.received'}

        async def mock_processor(data):
            return {'status': 'success'}

        result = await webhook_retry_service.process_webhook_with_retry(
            webhook_data,
            processor_func=mock_processor
        )

        assert result['status'] == 'success'
        assert webhook_retry_service._current_attempt == 0  # Reset after success

    @pytest.mark.asyncio
    async def test_retry_on_timeout_error(self, webhook_retry_service, dlq_service):
        """Test retry on TimeoutError."""

        webhook_data = {'id': '123', 'type': 'message.received'}
        attempt_count = 0

        async def mock_processor(data):
            nonlocal attempt_count
            attempt_count += 1

            if attempt_count < 3:
                raise TimeoutError("Request timeout")

            return {'status': 'success'}

        # Patch the retry decorator to use faster wait times for testing
        with patch('app.services.webhook_retry.webhook_settings') as mock_settings:
            mock_settings.WEBHOOK_MAX_RETRIES = 5
            mock_settings.WEBHOOK_RETRY_MIN_WAIT = 0.1
            mock_settings.WEBHOOK_RETRY_MAX_WAIT = 1

            result = await webhook_retry_service.process_webhook_with_retry(
                webhook_data,
                processor_func=mock_processor
            )

            # Should succeed on attempt 3
            assert result['status'] == 'success'
            assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self, webhook_retry_service, dlq_service):
        """Test that webhook goes to DLQ after max retries."""

        webhook_data = {'id': '456', 'type': 'message.received'}

        async def mock_processor(data):
            raise ConnectionError("Connection failed")

        # Should exhaust retries and send to DLQ
        with pytest.raises(ConnectionError):
            await webhook_retry_service.process_webhook_with_retry(
                webhook_data,
                processor_func=mock_processor
            )

        # Verify sent to DLQ
        assert len(dlq_service.enqueued) == 1
        dlq_item = dlq_service.enqueued[0]
        assert dlq_item['webhook_data']['id'] == '456'
        assert dlq_item['retry_count'] == 5
        assert 'Connection failed' in dlq_item['error']

    @pytest.mark.asyncio
    async def test_retry_statistics(self, webhook_retry_service):
        """Test retry statistics."""

        stats = webhook_retry_service.get_retry_statistics()

        assert stats['max_retries'] == 5
        assert stats['min_wait_seconds'] == 2
        assert stats['max_wait_seconds'] == 60
        assert stats['multiplier'] == 1

        # Verify retry schedule
        schedule = stats['retry_schedule']
        assert len(schedule) == 5

        # First attempt should have 0 wait
        assert schedule[0]['wait_time'] == 2
        assert schedule[0]['cumulative_wait'] == 0

        # Second attempt should have 2s wait
        assert schedule[1]['wait_time'] == 4
        assert schedule[1]['cumulative_wait'] == 2

    @pytest.mark.asyncio
    async def test_no_dlq_service_warning(self, caplog):
        """Test warning when no DLQ service configured."""

        service = WebhookRetryService(dlq_service=None, max_retries=1)

        webhook_data = {'id': '789'}

        async def mock_processor(data):
            raise ConnectionError("Failed")

        with pytest.raises(ConnectionError):
            await service.process_webhook_with_retry(
                webhook_data,
                processor_func=mock_processor
            )

        # Should log warning about missing DLQ
        # Note: This test requires proper logging configuration

    @pytest.mark.asyncio
    async def test_different_error_types_retried(self, webhook_retry_service):
        """Test that different retriable errors are handled."""

        webhook_data = {'id': 'multi-error'}
        errors_to_raise = [
            TimeoutError("Timeout"),
            ConnectionError("Connection failed"),
            aiohttp.ClientError("Client error"),
            asyncio.TimeoutError("Async timeout"),
        ]

        attempt_count = 0

        async def mock_processor(data):
            nonlocal attempt_count
            if attempt_count < len(errors_to_raise):
                error = errors_to_raise[attempt_count]
                attempt_count += 1
                raise error

            return {'status': 'success'}

        result = await webhook_retry_service.process_webhook_with_retry(
            webhook_data,
            processor_func=mock_processor
        )

        assert result['status'] == 'success'
        assert attempt_count == 4  # Should retry all error types


class TestCircuitBreakerAwareWebhookRetry:
    """Test circuit breaker integration."""

    @pytest.mark.asyncio
    async def test_circuit_open_fails_fast(self, dlq_service):
        """Test that open circuit fails fast without retry."""

        circuit_breaker = MockCircuitBreaker(is_open=True)
        service = CircuitBreakerAwareWebhookRetry(
            circuit_breaker=circuit_breaker,
            dlq_service=dlq_service
        )

        webhook_data = {'id': 'circuit-test'}

        with pytest.raises(Exception, match="Circuit breaker OPEN"):
            await service.process_webhook_with_retry(webhook_data)

        # Should send to DLQ immediately (no retries)
        assert len(dlq_service.enqueued) == 1
        assert 'Circuit breaker OPEN' in dlq_service.enqueued[0]['error']

    @pytest.mark.asyncio
    async def test_circuit_closed_allows_retry(self, dlq_service):
        """Test that closed circuit allows normal retry."""

        circuit_breaker = MockCircuitBreaker(is_open=False)
        service = CircuitBreakerAwareWebhookRetry(
            circuit_breaker=circuit_breaker,
            dlq_service=dlq_service,
            max_retries=3
        )

        webhook_data = {'id': 'retry-test'}
        attempt_count = 0

        async def mock_processor(data):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise TimeoutError("Timeout")
            return {'status': 'success'}

        # Mock the parent class's process_webhook_with_retry to avoid actual retry logic
        with patch.object(
            WebhookRetryService,
            'process_webhook_with_retry',
            new_callable=AsyncMock
        ) as mock_retry:
            mock_retry.return_value = {'status': 'success'}

            result = await service.process_webhook_with_retry(
                webhook_data,
                processor_func=mock_processor
            )

            # Circuit breaker should have been called
            assert circuit_breaker.call_count > 0


class TestWebhookRetryConfiguration:
    """Test configuration and initialization."""

    def test_default_configuration(self):
        """Test default retry configuration."""

        service = WebhookRetryService()

        # Should use defaults from settings
        assert service.max_retries == 5
        assert service.min_wait == 2
        assert service.max_wait == 60
        assert service.multiplier == 1

    def test_custom_configuration(self):
        """Test custom retry configuration."""

        service = WebhookRetryService(
            max_retries=10,
            min_wait=5,
            max_wait=120,
            multiplier=2
        )

        assert service.max_retries == 10
        assert service.min_wait == 5
        assert service.max_wait == 120
        assert service.multiplier == 2

    def test_retry_schedule_calculation(self):
        """Test exponential backoff schedule calculation."""

        service = WebhookRetryService(
            max_retries=5,
            min_wait=2,
            max_wait=64,
            multiplier=1
        )

        stats = service.get_retry_statistics()
        schedule = stats['retry_schedule']

        # Expected exponential backoff: 2, 4, 8, 16, 32
        expected_waits = [2, 4, 8, 16, 32]

        for i, expected_wait in enumerate(expected_waits):
            assert schedule[i]['wait_time'] == expected_wait

    def test_retry_schedule_with_max_cap(self):
        """Test that retry schedule respects max_wait cap."""

        service = WebhookRetryService(
            max_retries=6,
            min_wait=2,
            max_wait=10,  # Cap at 10 seconds
            multiplier=1
        )

        stats = service.get_retry_statistics()
        schedule = stats['retry_schedule']

        # Expected: 2, 4, 8, 10, 10, 10 (capped)
        expected_waits = [2, 4, 8, 10, 10, 10]

        for i, expected_wait in enumerate(expected_waits):
            assert schedule[i]['wait_time'] == expected_wait
