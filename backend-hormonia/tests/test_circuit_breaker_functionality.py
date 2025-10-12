"""
Tests for circuit breaker functionality under various failure conditions.

This module tests circuit breaker behavior in different scenarios:
- Multiple failure types and recovery patterns
- Fallback mechanism effectiveness
- Performance under load
- State transitions and timing
"""
import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import time

from sqlalchemy.exc import (
    OperationalError,
    DisconnectionError,
    TimeoutError as SQLTimeoutError,
    IntegrityError
)

from app.core.database_circuit_breaker import (
    DatabaseCircuitBreaker,
    DatabaseCircuitBreakerManager,
    protected_read_query,
    protected_write_query,
    protected_analytics_query
)
from app.services.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
    AIServiceCircuitBreaker
)


class TestCircuitBreakerStateTransitions:
    """Test circuit breaker state transitions under various conditions."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker with short timeouts for testing."""
        return CircuitBreaker(
            name="test_circuit",
            failure_threshold=3,
            recovery_timeout=1,  # 1 second for fast testing
            success_threshold=2
        )

    @pytest.mark.asyncio
    async def test_closed_to_open_transition(self, circuit_breaker):
        """Test transition from CLOSED to OPEN state."""
        assert circuit_breaker.state == CircuitState.CLOSED
        
        async def failing_function():
            raise Exception("Test failure")
        
        # Cause failures to reach threshold
        for i in range(3):
            try:
                await circuit_breaker.call(failing_function)
            except Exception:
                pass
        
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.stats.consecutive_failures == 3

    @pytest.mark.asyncio
    async def test_open_to_half_open_transition(self, circuit_breaker):
        """Test transition from OPEN to HALF_OPEN state."""
        # Force circuit to OPEN state
        async def failing_function():
            raise Exception("Test failure")
        
        for _ in range(3):
            try:
                await circuit_breaker.call(failing_function)
            except Exception:
                pass
        
        assert circuit_breaker.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(1.1)
        
        # Next call should transition to HALF_OPEN
        async def success_function():
            return "success"
        
        result = await circuit_breaker.call(success_function)
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        assert result == "success"

    @pytest.mark.asyncio
    async def test_half_open_to_closed_transition(self, circuit_breaker):
        """Test transition from HALF_OPEN to CLOSED state."""
        # Force to HALF_OPEN state
        circuit_breaker.state = CircuitState.HALF_OPEN
        circuit_breaker.stats.consecutive_successes = 1
        
        async def success_function():
            return "success"
        
        # One more success should close the circuit
        result = await circuit_breaker.call(success_function)
        assert circuit_breaker.state == CircuitState.CLOSED
        assert result == "success"

    @pytest.mark.asyncio
    async def test_half_open_to_open_transition(self, circuit_breaker):
        """Test transition from HALF_OPEN back to OPEN on failure."""
        # Force to HALF_OPEN state
        circuit_breaker.state = CircuitState.HALF_OPEN
        
        async def failing_function():
            raise Exception("Test failure during recovery")
        
        try:
            await circuit_breaker.call(failing_function)
        except Exception:
            pass
        
        assert circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_fallback(self, circuit_breaker):
        """Test circuit breaker with fallback mechanism."""
        async def failing_function():
            raise Exception("Primary function failed")
        
        async def fallback_function():
            return "fallback_result"
        
        # Circuit should be closed initially
        result = await circuit_breaker.call(
            failing_function,
            fallback=fallback_function
        )
        assert result == "fallback_result"

    @pytest.mark.asyncio
    async def test_circuit_breaker_statistics(self, circuit_breaker):
        """Test circuit breaker statistics tracking."""
        async def mixed_function(should_fail=False):
            if should_fail:
                raise Exception("Failure")
            return "success"
        
        # Mix of successes and failures
        for i in range(10):
            try:
                await circuit_breaker.call(mixed_function, should_fail=(i % 3 == 0))
            except Exception:
                pass
        
        stats = circuit_breaker.get_stats()
        assert stats["total_requests"] == 10
        assert stats["successful_requests"] > 0
        assert stats["failed_requests"] > 0
        assert "success_rate" in stats


class TestDatabaseCircuitBreakerFailureScenarios:
    """Test database circuit breaker under various failure scenarios."""

    @pytest.fixture
    def db_circuit_breaker(self):
        """Create database circuit breaker for testing."""
        return DatabaseCircuitBreaker(
            name="test_db_circuit",
            failure_threshold=2,
            recovery_timeout=1,
            enable_fallback=True
        )

    @pytest.mark.asyncio
    async def test_operational_error_handling(self, db_circuit_breaker):
        """Test handling of database operational errors."""
        async def failing_query():
            raise OperationalError("Database connection failed", None, None)
        
        # First failure should not open circuit
        with pytest.raises(Exception):
            await db_circuit_breaker.execute_query(
                query_func=failing_query,
                operation_name="test_query"
            )
        
        assert db_circuit_breaker.state == CircuitState.CLOSED
        
        # Second failure should open circuit
        with pytest.raises(Exception):
            await db_circuit_breaker.execute_query(
                query_func=failing_query,
                operation_name="test_query"
            )
        
        assert db_circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_disconnection_error_handling(self, db_circuit_breaker):
        """Test handling of database disconnection errors."""
        async def disconnection_query():
            raise DisconnectionError("Connection lost")
        
        with pytest.raises(Exception):
            await db_circuit_breaker.execute_query(
                query_func=disconnection_query,
                operation_name="test_query"
            )
        
        # Should track the failure
        assert db_circuit_breaker.stats.failed_requests > 0

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self, db_circuit_breaker):
        """Test handling of database timeout errors."""
        async def timeout_query():
            raise SQLTimeoutError("Query timeout", None, None)
        
        with pytest.raises(Exception):
            await db_circuit_breaker.execute_query(
                query_func=timeout_query,
                operation_name="slow_query"
            )

    @pytest.mark.asyncio
    async def test_integrity_error_handling(self, db_circuit_breaker):
        """Test handling of database integrity errors."""
        async def integrity_query():
            raise IntegrityError("Duplicate key", None, None)
        
        with pytest.raises(Exception):
            await db_circuit_breaker.execute_query(
                query_func=integrity_query,
                operation_name="insert_query"
            )

    @pytest.mark.asyncio
    async def test_fallback_data_generation(self, db_circuit_breaker):
        """Test smart fallback data generation."""
        # Test different operation types
        fallback_list = await db_circuit_breaker._generate_smart_fallback("list_users")
        assert fallback_list == []
        
        fallback_count = await db_circuit_breaker._generate_smart_fallback("count_messages")
        assert fallback_count == 0
        
        fallback_exists = await db_circuit_breaker._generate_smart_fallback("user_exists")
        assert fallback_exists is False
        
        fallback_get = await db_circuit_breaker._generate_smart_fallback("get_user")
        assert fallback_get is None
        
        fallback_analytics = await db_circuit_breaker._generate_smart_fallback("analytics_dashboard")
        assert isinstance(fallback_analytics, dict)
        assert "data" in fallback_analytics

    @pytest.mark.asyncio
    async def test_transaction_handling(self, db_circuit_breaker):
        """Test transaction handling with circuit breaker."""
        async def failing_transaction():
            raise OperationalError("Transaction failed", None, None)
        
        with pytest.raises(Exception):
            await db_circuit_breaker.execute_transaction(
                transaction_func=failing_transaction,
                rollback_on_circuit_open=True
            )

    @pytest.mark.asyncio
    async def test_health_check_failure(self, db_circuit_breaker):
        """Test health check failure handling."""
        with patch('app.core.database.get_scoped_session') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.side_effect = Exception("Health check failed")
            
            health = await db_circuit_breaker.health_check()
            assert health is False
            assert db_circuit_breaker.is_healthy() is False


class TestDatabaseCircuitBreakerManager:
    """Test database circuit breaker manager functionality."""

    @pytest.fixture
    def manager(self):
        """Create circuit breaker manager for testing."""
        return DatabaseCircuitBreakerManager()

    @pytest.mark.asyncio
    async def test_read_operation_with_fallback(self, manager):
        """Test read operation with fallback data."""
        async def failing_read():
            raise OperationalError("Read failed", None, None)
        
        fallback_data = [{"id": 1, "name": "fallback"}]
        
        # Mock the graceful error handler to return fallback
        with patch('app.core.graceful_error_handler.graceful_error_handler') as mock_handler:
            mock_handler.handle_graceful_degradation.return_value = {
                "data": fallback_data,
                "warning": {"message": "degraded mode"}
            }
            
            # Force circuit to open
            breaker = manager.get_breaker("read_operations")
            breaker.state = CircuitState.OPEN
            
            result = await manager.execute_read_operation(
                query_func=failing_read,
                fallback_data=fallback_data
            )
            
            # Should get graceful degradation response
            assert "data" in result or result == fallback_data

    @pytest.mark.asyncio
    async def test_write_operation_no_fallback(self, manager):
        """Test write operation without fallback (should fail)."""
        async def failing_write():
            raise IntegrityError("Write failed", None, None)
        
        with pytest.raises(Exception):
            await manager.execute_write_operation(
                query_func=failing_write
            )

    @pytest.mark.asyncio
    async def test_analytics_query_with_default_fallback(self, manager):
        """Test analytics query with default fallback."""
        async def failing_analytics():
            raise OperationalError("Analytics failed", None, None)
        
        # Mock the graceful error handler
        with patch('app.core.graceful_error_handler.graceful_error_handler') as mock_handler:
            mock_handler.handle_graceful_degradation.return_value = {
                "data": {"data": [], "total": 0},
                "warning": {"message": "degraded mode"}
            }
            
            # Force circuit to open
            breaker = manager.get_breaker("analytics_queries")
            breaker.state = CircuitState.OPEN
            
            result = await manager.execute_analytics_query(
                query_func=failing_analytics
            )
            
            # Should get some form of response
            assert result is not None

    @pytest.mark.asyncio
    async def test_protected_operation_context_manager(self, manager):
        """Test protected operation context manager."""
        async def successful_operation():
            return "success"
        
        async with manager.protected_operation("read_operations") as context:
            # Context manager should allow operation to proceed
            pass
        
        # Should not raise exception for successful operation

    @pytest.mark.asyncio
    async def test_protected_operation_with_failure(self, manager):
        """Test protected operation context manager with failure."""
        with pytest.raises(Exception):
            async with manager.protected_operation("read_operations"):
                raise OperationalError("Operation failed", None, None)

    def test_reset_specific_breaker(self, manager):
        """Test resetting specific circuit breaker."""
        # Get a breaker and modify its state
        breaker = manager.get_breaker("read_operations")
        breaker.stats.failed_requests = 5
        
        # Reset it
        manager.reset_breaker("read_operations")
        
        # Should be reset
        assert breaker.stats.failed_requests == 0
        assert breaker.state == CircuitState.CLOSED

    def test_reset_all_breakers(self, manager):
        """Test resetting all circuit breakers."""
        # Modify some breakers
        for operation_type in ["read_operations", "write_operations"]:
            breaker = manager.get_breaker(operation_type)
            breaker.stats.failed_requests = 10
        
        # Reset all
        manager.reset_all()
        
        # All should be reset
        for operation_type in ["read_operations", "write_operations"]:
            breaker = manager.get_breaker(operation_type)
            assert breaker.stats.failed_requests == 0


class TestAIServiceCircuitBreaker:
    """Test AI service circuit breaker functionality."""

    @pytest.fixture
    def ai_circuit_breaker(self):
        """Create AI service circuit breaker for testing."""
        return AIServiceCircuitBreaker()

    @pytest.mark.asyncio
    async def test_gemini_call_with_fallback(self, ai_circuit_breaker):
        """Test Gemini call with fallback response."""
        async def failing_gemini(prompt):
            raise Exception("Gemini API failed")
        
        result = await ai_circuit_breaker.call_gemini(
            func=failing_gemini,
            prompt="Test prompt",
            fallback_response="Fallback response"
        )
        
        assert result == "Fallback response"

    @pytest.mark.asyncio
    async def test_sentiment_analysis_with_fallback(self, ai_circuit_breaker):
        """Test sentiment analysis with rule-based fallback."""
        async def failing_sentiment(message, context):
            raise Exception("Sentiment API failed")
        
        result = await ai_circuit_breaker.call_sentiment_analysis(
            func=failing_sentiment,
            message="Estou me sentindo bem hoje",
            context={}
        )
        
        assert result["sentiment"] == "positive"
        assert result["fallback"] is True

    @pytest.mark.asyncio
    async def test_quiz_interpretation_with_fallback(self, ai_circuit_breaker):
        """Test quiz interpretation with matching fallback."""
        async def failing_quiz(question, response):
            raise Exception("Quiz API failed")
        
        question = {
            "options": [
                {"text": "Sim", "value": "yes"},
                {"text": "Não", "value": "no"}
            ]
        }
        
        result = await ai_circuit_breaker.call_quiz_interpretation(
            func=failing_quiz,
            question=question,
            response="Sim"
        )
        
        assert result["matched_option"] == "yes"
        assert result["fallback"] is True

    def test_get_all_stats(self, ai_circuit_breaker):
        """Test getting statistics for all AI circuit breakers."""
        stats = ai_circuit_breaker.get_all_stats()
        
        assert "gemini" in stats
        assert "sentiment" in stats
        assert "quiz" in stats
        
        for breaker_stats in stats.values():
            assert "name" in breaker_stats
            assert "state" in breaker_stats
            assert "total_requests" in breaker_stats

    def test_reset_all_ai_breakers(self, ai_circuit_breaker):
        """Test resetting all AI circuit breakers."""
        # Modify some stats
        ai_circuit_breaker.breakers["gemini"].stats.failed_requests = 5
        
        # Reset all
        ai_circuit_breaker.reset_all()
        
        # Should be reset
        assert ai_circuit_breaker.breakers["gemini"].stats.failed_requests == 0


class TestCircuitBreakerPerformance:
    """Test circuit breaker performance under load."""

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test circuit breaker with concurrent requests."""
        circuit_breaker = CircuitBreaker(
            name="concurrent_test",
            failure_threshold=5,
            recovery_timeout=1
        )
        
        async def fast_function(delay=0.01):
            await asyncio.sleep(delay)
            return "success"
        
        # Run many concurrent requests
        tasks = []
        for _ in range(100):
            task = asyncio.create_task(circuit_breaker.call(fast_function))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Most should succeed
        successes = [r for r in results if r == "success"]
        assert len(successes) > 90  # Allow for some timing variations

    @pytest.mark.asyncio
    async def test_rapid_state_changes(self):
        """Test circuit breaker with rapid state changes."""
        circuit_breaker = CircuitBreaker(
            name="rapid_test",
            failure_threshold=2,
            recovery_timeout=0.1  # Very short timeout
        )
        
        async def alternating_function(should_fail):
            if should_fail:
                raise Exception("Failure")
            return "success"
        
        # Rapid alternation between success and failure
        for i in range(20):
            try:
                await circuit_breaker.call(alternating_function, should_fail=(i % 3 == 0))
            except Exception:
                pass
            
            # Small delay to allow state transitions
            await asyncio.sleep(0.05)
        
        # Circuit should handle rapid changes gracefully
        stats = circuit_breaker.get_stats()
        assert stats["total_requests"] == 20

    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self):
        """Test that circuit breaker doesn't leak memory under load."""
        circuit_breaker = CircuitBreaker(
            name="memory_test",
            failure_threshold=10,
            recovery_timeout=1
        )
        
        async def simple_function():
            return "success"
        
        # Run many requests to test memory usage
        for _ in range(1000):
            await circuit_breaker.call(simple_function)
        
        # Check that stats are reasonable (not growing unbounded)
        stats = circuit_breaker.get_stats()
        assert stats["total_requests"] == 1000
        assert len(circuit_breaker.stats.state_changes) < 100  # Should not grow unbounded


@pytest.mark.asyncio
async def test_convenience_functions():
    """Test convenience functions for protected queries."""
    async def mock_query():
        return {"result": "success"}
    
    # Test protected read query
    result = await protected_read_query(mock_query, fallback_data=[])
    assert result == {"result": "success"}
    
    # Test protected write query
    result = await protected_write_query(mock_query)
    assert result == {"result": "success"}
    
    # Test protected analytics query
    result = await protected_analytics_query(mock_query)
    assert result == {"result": "success"}


if __name__ == "__main__":
    pytest.main([__file__])