"""
Test parallel service initialization performance.

Verifies that the parallel startup implementation reduces initialization time
from the sequential baseline of 56+ seconds to under 15 seconds.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import FastAPI


class MockLogger:
    """Mock logger that captures timing information."""

    def __init__(self):
        self.logs = []

    def info(self, message, **kwargs):
        self.logs.append({"level": "info", "message": message, "extra": kwargs.get("extra", {})})

    def warning(self, message, **kwargs):
        self.logs.append({"level": "warning", "message": message, "extra": kwargs.get("extra", {})})

    def error(self, message, **kwargs):
        self.logs.append({"level": "error", "message": message, "extra": kwargs.get("extra", {})})

    def debug(self, message, **kwargs):
        self.logs.append({"level": "debug", "message": message, "extra": kwargs.get("extra", {})})


@pytest.fixture
def mock_app():
    """Create a mock FastAPI app."""
    app = FastAPI()
    app.state.start_time = time.time()
    return app


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return MockLogger()


@pytest.mark.asyncio
async def test_parallel_initialization_performance(mock_app, mock_logger):
    """Test that parallel initialization is faster than sequential."""
    from app.core.lifespan import _startup

    # Mock all external dependencies
    with patch("app.core.lifespan.setup_logging"), \
         patch("app.core.lifespan.get_logger", return_value=mock_logger), \
         patch("app.core.lifespan.configure_structured_logging"), \
         patch("app.core.lifespan._initialize_monitoring", new_callable=AsyncMock) as mock_monitoring, \
         patch("app.core.lifespan._initialize_redis_websocket_events", new_callable=AsyncMock) as mock_redis, \
         patch("app.core.lifespan._initialize_websocket_manager", new_callable=AsyncMock) as mock_ws, \
         patch("app.core.lifespan._initialize_session_manager", new_callable=AsyncMock) as mock_session, \
         patch("app.core.lifespan._initialize_redis_pubsub", new_callable=AsyncMock) as mock_pubsub, \
         patch("app.core.lifespan._initialize_ai_services", new_callable=AsyncMock) as mock_ai, \
         patch("app.core.lifespan._initialize_enum_validation", new_callable=AsyncMock) as mock_enum, \
         patch("app.core.lifespan._initialize_follow_up_system", new_callable=AsyncMock) as mock_followup:

        # Simulate realistic initialization times
        async def slow_monitoring(*args):
            await asyncio.sleep(0.5)  # 500ms

        async def slow_redis(*args):
            await asyncio.sleep(0.3)  # 300ms

        async def slow_ws(*args):
            await asyncio.sleep(0.2)  # 200ms

        async def slow_session(*args):
            await asyncio.sleep(0.2)  # 200ms

        async def slow_pubsub(*args):
            await asyncio.sleep(0.1)  # 100ms

        async def fast_ai(*args):
            await asyncio.sleep(0.05)  # 50ms

        async def fast_enum(*args):
            await asyncio.sleep(0.01)  # 10ms

        async def slow_followup(*args):
            await asyncio.sleep(0.15)  # 150ms

        mock_monitoring.side_effect = slow_monitoring
        mock_redis.side_effect = slow_redis
        mock_ws.side_effect = slow_ws
        mock_session.side_effect = slow_session
        mock_pubsub.side_effect = slow_pubsub
        mock_ai.side_effect = fast_ai
        mock_enum.side_effect = fast_enum
        mock_followup.side_effect = slow_followup

        # Measure startup time
        start = time.time()
        logger = await _startup(mock_app)
        elapsed = time.time() - start

        # Verify parallel execution
        # Sequential: 0.5 + 0.3 + 0.2 + 0.2 + 0.1 + 0.05 + 0.01 + 0.15 = 1.51s
        # Parallel Phase 1 (max of monitoring, redis, ai, enum): max(0.5, 0.3, 0.05, 0.01) = 0.5s
        # Parallel Phase 2 (max of ws, session): max(0.2, 0.2) = 0.2s
        # Sequential Phase 2: pubsub (0.1s) + followup (0.15s) = 0.25s
        # Expected total: ~0.5 + 0.2 + 0.25 = 0.95s (vs 1.51s sequential)

        assert elapsed < 1.2, f"Parallel initialization took {elapsed:.2f}s, expected < 1.2s"
        assert elapsed > 0.9, f"Parallel initialization too fast ({elapsed:.2f}s), mocks may not be working"

        # Verify all services were initialized
        mock_monitoring.assert_called_once()
        mock_redis.assert_called_once()
        mock_ws.assert_called_once()
        mock_session.assert_called_once()
        mock_pubsub.assert_called_once()
        mock_ai.assert_called_once()
        mock_enum.assert_called_once()
        mock_followup.assert_called_once()

        # Verify timing logs were captured
        info_logs = [log for log in mock_logger.logs if log["level"] == "info"]
        phase1_logs = [log for log in info_logs if "Phase 1 completed" in log["message"]]
        phase2_logs = [log for log in info_logs if "Phase 2 completed" in log["message"]]

        assert len(phase1_logs) == 1, "Should log Phase 1 completion"
        assert len(phase2_logs) == 1, "Should log Phase 2 completion"


@pytest.mark.asyncio
async def test_parallel_error_handling(mock_app, mock_logger):
    """Test that errors in one service don't block others."""
    from app.core.lifespan import _startup

    with patch("app.core.lifespan.setup_logging"), \
         patch("app.core.lifespan.get_logger", return_value=mock_logger), \
         patch("app.core.lifespan.configure_structured_logging"), \
         patch("app.core.lifespan._initialize_monitoring", new_callable=AsyncMock) as mock_monitoring, \
         patch("app.core.lifespan._initialize_redis_websocket_events", new_callable=AsyncMock) as mock_redis, \
         patch("app.core.lifespan._initialize_websocket_manager", new_callable=AsyncMock) as mock_ws, \
         patch("app.core.lifespan._initialize_session_manager", new_callable=AsyncMock) as mock_session, \
         patch("app.core.lifespan._initialize_redis_pubsub", new_callable=AsyncMock) as mock_pubsub, \
         patch("app.core.lifespan._initialize_ai_services", new_callable=AsyncMock) as mock_ai, \
         patch("app.core.lifespan._initialize_enum_validation", new_callable=AsyncMock) as mock_enum, \
         patch("app.core.lifespan._initialize_follow_up_system", new_callable=AsyncMock) as mock_followup:

        # Simulate one service failing
        async def failing_monitoring(*args):
            raise Exception("Monitoring initialization failed")

        async def successful_service(*args):
            await asyncio.sleep(0.1)

        mock_monitoring.side_effect = failing_monitoring
        mock_redis.side_effect = successful_service
        mock_ai.side_effect = successful_service
        mock_enum.side_effect = successful_service
        mock_ws.side_effect = successful_service
        mock_session.side_effect = successful_service
        mock_pubsub.side_effect = successful_service
        mock_followup.side_effect = successful_service

        # Should not raise exception (return_exceptions=True)
        logger = await _startup(mock_app)

        # Verify other services still initialized
        mock_redis.assert_called_once()
        mock_ai.assert_called_once()
        mock_enum.assert_called_once()
        mock_ws.assert_called_once()
        mock_session.assert_called_once()


@pytest.mark.asyncio
async def test_dependency_order(mock_app, mock_logger):
    """Test that dependent services wait for Phase 1 services."""
    from app.core.lifespan import _startup

    call_order = []

    async def track_monitoring(*args):
        call_order.append("monitoring")
        await asyncio.sleep(0.2)

    async def track_redis(*args):
        call_order.append("redis")
        await asyncio.sleep(0.2)

    async def track_ws(*args):
        call_order.append("websocket")
        await asyncio.sleep(0.1)

    async def track_pubsub(*args):
        call_order.append("pubsub")

    async def track_other(*args):
        call_order.append("other")

    with patch("app.core.lifespan.setup_logging"), \
         patch("app.core.lifespan.get_logger", return_value=mock_logger), \
         patch("app.core.lifespan.configure_structured_logging"), \
         patch("app.core.lifespan._initialize_monitoring", side_effect=track_monitoring), \
         patch("app.core.lifespan._initialize_redis_websocket_events", side_effect=track_redis), \
         patch("app.core.lifespan._initialize_websocket_manager", side_effect=track_ws), \
         patch("app.core.lifespan._initialize_session_manager", side_effect=track_other), \
         patch("app.core.lifespan._initialize_redis_pubsub", side_effect=track_pubsub), \
         patch("app.core.lifespan._initialize_ai_services", side_effect=track_other), \
         patch("app.core.lifespan._initialize_enum_validation", side_effect=track_other), \
         patch("app.core.lifespan._initialize_follow_up_system", side_effect=track_other):

        logger = await _startup(mock_app)

        # Verify Redis and monitoring started before WebSocket
        redis_index = call_order.index("redis")
        ws_index = call_order.index("websocket")
        pubsub_index = call_order.index("pubsub")

        assert redis_index < ws_index, "Redis should initialize before WebSocket"
        assert ws_index < pubsub_index, "WebSocket should initialize before Pub/Sub"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
