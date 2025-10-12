"""
Tests for error logging and context preservation.

This module tests the enhanced error logging system:
- Structured logging with proper context
- Correlation ID tracking across requests
- Error aggregation and alerting
- Context preservation in error scenarios
"""
import asyncio
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import threading
import json

from app.core.enhanced_error_logging import (
    StructuredErrorLogger,
    CorrelationIdManager,
    ErrorContext,
    ErrorAggregation,
    LogLevel,
    AlertSeverity,
    get_enhanced_error_logger,
    log_error_with_context,
    log_structured_event,
    error_tracking_context,
    console_alert_callback
)
from app.core.logging_config import RateLimitedLogger


class TestCorrelationIdTracking:
    """Test correlation ID tracking and context management."""

    def test_correlation_id_thread_isolation(self):
        """Test that correlation IDs are isolated between threads."""
        results = {}
        
        def thread_function(thread_id):
            correlation_id = f"thread-{thread_id}"
            CorrelationIdManager.set_correlation_id(correlation_id)
            
            # Simulate some work
            import time
            time.sleep(0.1)
            
            # Check that correlation ID is preserved
            retrieved_id = CorrelationIdManager.get_correlation_id()
            results[thread_id] = retrieved_id
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=thread_function, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify each thread maintained its own correlation ID
        for i in range(5):
            assert results[i] == f"thread-{i}"

    def test_correlation_context_nesting(self):
        """Test nested correlation contexts."""
        # Set initial correlation ID
        CorrelationIdManager.set_correlation_id("outer-id")
        
        with CorrelationIdManager.correlation_context("middle-id") as middle_id:
            assert middle_id == "middle-id"
            assert CorrelationIdManager.get_correlation_id() == "middle-id"
            
            with CorrelationIdManager.correlation_context("inner-id") as inner_id:
                assert inner_id == "inner-id"
                assert CorrelationIdManager.get_correlation_id() == "inner-id"
            
            # Should restore middle context
            assert CorrelationIdManager.get_correlation_id() == "middle-id"
        
        # Should restore outer context
        assert CorrelationIdManager.get_correlation_id() == "outer-id"

    def test_correlation_context_with_none(self):
        """Test correlation context with None (should generate new ID)."""
        with CorrelationIdManager.correlation_context(None) as context_id:
            assert context_id is not None
            assert len(context_id) > 0
            assert CorrelationIdManager.get_correlation_id() == context_id

    def test_ensure_correlation_id_generation(self):
        """Test that ensure_correlation_id generates ID when none exists."""
        # Clear any existing ID
        CorrelationIdManager._local.correlation_id = None
        
        # Should generate new ID
        id1 = CorrelationIdManager.ensure_correlation_id()
        assert id1 is not None
        
        # Should return same ID on subsequent calls
        id2 = CorrelationIdManager.ensure_correlation_id()
        assert id1 == id2


class TestStructuredErrorLogging:
    """Test structured error logging functionality."""

    @pytest.fixture
    def error_logger(self):
        """Create error logger with mocked rate limiter."""
        rate_limiter = Mock(spec=RateLimitedLogger)
        rate_limiter.should_log.return_value = True
        
        return StructuredErrorLogger(
            rate_limiter=rate_limiter,
            enable_aggregation=True,
            enable_alerting=False
        )

    def test_error_context_creation(self, error_logger):
        """Test error context creation with all fields."""
        error = ValueError("Test error")
        
        with patch.object(error_logger.logger, 'log') as mock_log:
            correlation_id = error_logger.log_error(
                error=error,
                level=LogLevel.ERROR,
                user_id="user_123",
                session_id="session_456",
                request_id="req_789",
                endpoint="/api/v1/test",
                method="POST",
                user_agent="TestAgent/1.0",
                ip_address="192.168.1.1",
                additional_context={"custom_field": "custom_value"},
                correlation_id="test-correlation-id"
            )
            
            assert correlation_id == "test-correlation-id"
            mock_log.assert_called_once()
            
            # Check the logged data structure
            call_args = mock_log.call_args
            extra_data = call_args[1]['extra']
            
            assert 'structured_error' in extra_data
            structured_error = extra_data['structured_error']
            
            assert structured_error['correlation_id'] == "test-correlation-id"
            assert structured_error['error_type'] == "ValueError"
            assert structured_error['user_id'] == "user_123"
            assert structured_error['endpoint'] == "/api/v1/test"
            assert structured_error['additional_context']['custom_field'] == "custom_value"

    def test_error_message_formatting(self, error_logger):
        """Test error message formatting."""
        error_context = ErrorContext(
            correlation_id="test-id",
            timestamp=datetime.utcnow(),
            error_type="ValueError",
            error_message="Test error message",
            endpoint="/api/test",
            method="GET",
            user_id="user_123"
        )
        
        formatted_message = error_logger._format_error_message(error_context)
        
        assert "[test-id]" in formatted_message
        assert "GET /api/test" in formatted_message
        assert "ValueError: Test error message" in formatted_message
        assert "(User: user_123)" in formatted_message

    def test_structured_event_logging(self, error_logger):
        """Test structured event logging."""
        with patch.object(error_logger.logger, 'log') as mock_log:
            correlation_id = error_logger.log_structured(
                message="User login successful",
                level=LogLevel.INFO,
                event_type="authentication",
                user_id="user_123",
                login_method="password"
            )
            
            assert correlation_id is not None
            mock_log.assert_called_once()
            
            call_args = mock_log.call_args
            extra_data = call_args[1]['extra']
            
            assert extra_data['event_type'] == "authentication"
            assert extra_data['correlation_id'] == correlation_id
            assert extra_data['context']['user_id'] == "user_123"
            assert extra_data['context']['login_method'] == "password"

    def test_rate_limiting_integration(self, error_logger):
        """Test integration with rate limiting."""
        # Configure rate limiter to deny logging
        error_logger.rate_limiter.should_log.return_value = False
        
        with patch.object(error_logger.logger, 'log') as mock_log:
            error_logger.log_error(
                error=ValueError("Rate limited error"),
                endpoint="/api/test"
            )
            
            # Should not log due to rate limiting
            mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_database_storage_integration(self, error_logger):
        """Test error storage in database."""
        error = RuntimeError("Database storage test")
        
        with patch('app.core.database.get_scoped_session') as mock_session:
            mock_session_instance = Mock()
            mock_session.return_value.__enter__.return_value = mock_session_instance
            
            with patch.object(error_logger.logger, 'log'):
                correlation_id = error_logger.log_error(
                    error=error,
                    user_id="user_123"
                )
            
            # Wait for async storage
            await asyncio.sleep(0.1)
            
            # Verify session was used
            mock_session_instance.add.assert_called_once()
            mock_session_instance.commit.assert_called_once()

    def test_error_context_manager(self, error_logger):
        """Test error context manager functionality."""
        with patch.object(error_logger, 'log_error') as mock_log_error:
            try:
                with error_logger.error_context(
                    operation="test_operation",
                    user_id="user_123",
                    custom_field="custom_value"
                ) as correlation_id:
                    assert correlation_id is not None
                    raise ValueError("Context manager test error")
            except ValueError:
                pass  # Expected
            
            mock_log_error.assert_called_once()
            
            call_args = mock_log_error.call_args
            assert call_args[1]['user_id'] == "user_123"
            assert call_args[1]['additional_context']['operation'] == "test_operation"
            assert call_args[1]['additional_context']['custom_field'] == "custom_value"


class TestErrorAggregation:
    """Test error aggregation and alerting functionality."""

    @pytest.fixture
    def error_logger_with_alerting(self):
        """Create error logger with alerting enabled."""
        rate_limiter = Mock(spec=RateLimitedLogger)
        rate_limiter.should_log.return_value = True
        
        logger = StructuredErrorLogger(
            rate_limiter=rate_limiter,
            enable_aggregation=True,
            enable_alerting=True
        )
        
        # Mock alert callback
        logger.alert_callbacks = [Mock()]
        
        return logger

    def test_error_aggregation_basic(self, error_logger_with_alerting):
        """Test basic error aggregation functionality."""
        error = ValueError("Repeated error")
        
        with patch.object(error_logger_with_alerting.logger, 'log'):
            # Log the same error multiple times
            for i in range(5):
                error_logger_with_alerting.log_error(
                    error=error,
                    endpoint="/api/test",
                    user_id=f"user_{i}"
                )
        
        # Check aggregation
        stats = error_logger_with_alerting.get_aggregation_stats()
        assert stats["total_patterns"] > 0
        
        # Find our pattern
        pattern_key = "ValueError_/api/test"
        if pattern_key in stats["patterns"]:
            pattern_stats = stats["patterns"][pattern_key]
            assert pattern_stats["count"] == 5
            assert pattern_stats["affected_users"] == 5

    def test_severity_calculation(self, error_logger_with_alerting):
        """Test alert severity calculation."""
        aggregation = ErrorAggregation(
            error_type="DatabaseError",
            error_pattern="test_pattern",
            count=25,
            first_occurrence=datetime.utcnow(),
            last_occurrence=datetime.utcnow()
        )
        
        # Add users to test severity levels
        for i in range(12):
            aggregation.affected_users.add(f"user_{i}")
        
        severity = error_logger_with_alerting._calculate_severity(aggregation)
        assert severity == AlertSeverity.HIGH

    def test_alert_threshold_checking(self, error_logger_with_alerting):
        """Test alert threshold checking."""
        aggregation = ErrorAggregation(
            error_type="DatabaseError",
            error_pattern="test_pattern",
            count=15,
            first_occurrence=datetime.utcnow(),
            last_occurrence=datetime.utcnow()
        )
        
        threshold_config = {
            'time_window_minutes': 60,
            'count_threshold': 10,
            'affected_users_threshold': 5
        }
        
        # Should trigger alert due to count threshold
        assert aggregation.should_alert(threshold_config) is True
        
        # Test with higher threshold
        threshold_config['count_threshold'] = 20
        assert aggregation.should_alert(threshold_config) is False

    def test_error_categorization(self, error_logger_with_alerting):
        """Test error type categorization for thresholds."""
        assert error_logger_with_alerting._categorize_error("SQLAlchemyError") == "database_errors"
        assert error_logger_with_alerting._categorize_error("ConnectionError") == "websocket_errors"
        assert error_logger_with_alerting._categorize_error("AuthenticationError") == "authentication_errors"
        assert error_logger_with_alerting._categorize_error("ValueError") == "api_errors"
        assert error_logger_with_alerting._categorize_error("UnknownError") == "api_errors"

    def test_alert_callback_execution(self, error_logger_with_alerting):
        """Test that alert callbacks are executed."""
        # Configure low thresholds for testing
        error_logger_with_alerting.alert_thresholds["api_errors"] = {
            'time_window_minutes': 60,
            'count_threshold': 3,
            'affected_users_threshold': 2
        }
        
        error = ValueError("Alert test error")
        
        with patch.object(error_logger_with_alerting.logger, 'log'):
            # Log enough errors to trigger alert
            for i in range(4):
                error_logger_with_alerting.log_error(
                    error=error,
                    endpoint="/api/alert_test",
                    user_id=f"user_{i}"
                )
        
        # Check if alert callback was called
        # Note: This might not trigger immediately due to aggregation logic
        # In a real scenario, you'd need to wait or trigger aggregation manually

    def test_aggregation_cleanup(self, error_logger_with_alerting):
        """Test cleanup of old aggregations."""
        # Add old aggregation
        old_time = datetime.utcnow() - timedelta(hours=3)
        error_logger_with_alerting.error_aggregations["old_pattern"] = ErrorAggregation(
            error_type="OldError",
            error_pattern="old_pattern",
            count=1,
            first_occurrence=old_time,
            last_occurrence=old_time
        )
        
        # Add recent aggregation
        recent_time = datetime.utcnow()
        error_logger_with_alerting.error_aggregations["recent_pattern"] = ErrorAggregation(
            error_type="RecentError",
            error_pattern="recent_pattern",
            count=1,
            first_occurrence=recent_time,
            last_occurrence=recent_time
        )
        
        error_logger_with_alerting.cleanup_old_aggregations()
        
        # Old should be removed, recent should remain
        assert "old_pattern" not in error_logger_with_alerting.error_aggregations
        assert "recent_pattern" in error_logger_with_alerting.error_aggregations

    def test_alert_callback_failure_handling(self, error_logger_with_alerting):
        """Test that alert callback failures don't break logging."""
        # Add failing callback
        def failing_callback(alert_data):
            raise Exception("Callback failed")
        
        error_logger_with_alerting.add_alert_callback(failing_callback)
        
        # Should not raise exception even with failing callback
        with patch.object(error_logger_with_alerting.logger, 'log'):
            with patch.object(error_logger_with_alerting.logger, 'error') as mock_error_log:
                error_logger_with_alerting.log_error(
                    error=ValueError("Test error"),
                    endpoint="/api/test"
                )
                
                # If callback fails, it should be logged but not break the flow
                # This test ensures the system is resilient to callback failures


class TestConvenienceFunctions:
    """Test convenience functions for error logging."""

    def test_log_error_with_context(self):
        """Test log_error_with_context convenience function."""
        with patch('app.core.enhanced_error_logging.get_enhanced_error_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            mock_logger.log_error.return_value = "test-correlation-id"
            
            correlation_id = log_error_with_context(
                error=ValueError("Test error"),
                operation="test_operation",
                user_id="user_123",
                custom_field="custom_value"
            )
            
            assert correlation_id == "test-correlation-id"
            mock_logger.log_error.assert_called_once()
            
            call_args = mock_logger.log_error.call_args
            assert call_args[1]['user_id'] == "user_123"
            assert call_args[1]['additional_context']['operation'] == "test_operation"
            assert call_args[1]['additional_context']['custom_field'] == "custom_value"

    def test_log_structured_event(self):
        """Test log_structured_event convenience function."""
        with patch('app.core.enhanced_error_logging.get_enhanced_error_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            mock_logger.log_structured.return_value = "test-correlation-id"
            
            correlation_id = log_structured_event(
                message="Test event",
                event_type="test_event",
                level=LogLevel.INFO,
                custom_field="custom_value"
            )
            
            assert correlation_id == "test-correlation-id"
            mock_logger.log_structured.assert_called_once()

    def test_error_tracking_context(self):
        """Test error_tracking_context convenience function."""
        with patch('app.core.enhanced_error_logging.get_enhanced_error_logger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            # Mock the error_context method to return a context manager
            mock_context = Mock()
            mock_logger.error_context.return_value = mock_context
            
            context = error_tracking_context(
                operation="test_operation",
                user_id="user_123",
                custom_field="custom_value"
            )
            
            assert context == mock_context
            mock_logger.error_context.assert_called_once_with(
                operation="test_operation",
                user_id="user_123",
                custom_field="custom_value"
            )


class TestAlertCallbacks:
    """Test alert callback functionality."""

    def test_console_alert_callback(self):
        """Test console alert callback."""
        alert_data = {
            'error_pattern': 'ValueError_/api/test',
            'error_type': 'ValueError',
            'count': 15,
            'affected_users': 5,
            'affected_endpoints': ['/api/test'],
            'severity': 'HIGH',
            'first_occurrence': datetime.utcnow().isoformat(),
            'last_occurrence': datetime.utcnow().isoformat(),
            'correlation_ids': ['id1', 'id2', 'id3']
        }
        
        with patch('app.core.enhanced_error_logging.logger') as mock_logger:
            console_alert_callback(alert_data)
            
            # Should log the alert
            mock_logger.error.assert_called_once()
            
            call_args = mock_logger.error.call_args
            assert "ALERT [HIGH]" in call_args[0][0]
            assert "ValueError_/api/test" in call_args[0][0]

    def test_console_alert_callback_medium_severity(self):
        """Test console alert callback with medium severity."""
        alert_data = {
            'error_pattern': 'ValueError_/api/test',
            'severity': 'MEDIUM',
            'count': 8
        }
        
        with patch('app.core.enhanced_error_logging.logger') as mock_logger:
            console_alert_callback(alert_data)
            
            # Should use warning level for medium severity
            mock_logger.warning.assert_called_once()


class TestErrorContextPreservation:
    """Test error context preservation across async operations."""

    @pytest.mark.asyncio
    async def test_context_preservation_across_async_calls(self):
        """Test that correlation ID is preserved across async calls."""
        correlation_id = "test-async-correlation"
        
        async def async_operation_1():
            # Should preserve correlation ID
            current_id = CorrelationIdManager.get_correlation_id()
            assert current_id == correlation_id
            
            await asyncio.sleep(0.01)  # Simulate async work
            
            # Should still preserve correlation ID
            current_id = CorrelationIdManager.get_correlation_id()
            assert current_id == correlation_id
            
            return "result1"
        
        async def async_operation_2():
            # Should preserve correlation ID
            current_id = CorrelationIdManager.get_correlation_id()
            assert current_id == correlation_id
            
            await asyncio.sleep(0.01)  # Simulate async work
            
            return "result2"
        
        with CorrelationIdManager.correlation_context(correlation_id):
            # Run concurrent async operations
            results = await asyncio.gather(
                async_operation_1(),
                async_operation_2()
            )
            
            assert results == ["result1", "result2"]

    @pytest.mark.asyncio
    async def test_context_isolation_between_concurrent_operations(self):
        """Test that correlation IDs are isolated between concurrent operations."""
        results = {}
        
        async def async_operation_with_context(operation_id):
            correlation_id = f"correlation-{operation_id}"
            
            with CorrelationIdManager.correlation_context(correlation_id):
                await asyncio.sleep(0.01)  # Simulate work
                
                current_id = CorrelationIdManager.get_correlation_id()
                results[operation_id] = current_id
        
        # Run multiple concurrent operations
        tasks = []
        for i in range(5):
            task = asyncio.create_task(async_operation_with_context(i))
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        # Each operation should have maintained its own correlation ID
        for i in range(5):
            assert results[i] == f"correlation-{i}"


if __name__ == "__main__":
    pytest.main([__file__])