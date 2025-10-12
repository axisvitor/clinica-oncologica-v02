"""
Tests for logging rate limiting and optimization functionality.

This module tests the RateLimitedLogger class and OptimizedRequestLogger
to ensure they properly limit log rates, deduplicate messages, and use
appropriate log levels.
"""
import time
import logging
import pytest
from unittest.mock import Mock, patch, MagicMock
from collections import deque

from app.core.logging_config import (
    RateLimitedLogger,
    OptimizedRequestLogger,
    configure_optimized_logging
)


class TestRateLimitedLogger:
    """Test cases for RateLimitedLogger class."""
    
    def test_rate_limiting_basic(self):
        """Test basic rate limiting functionality."""
        # Create logger with very low rate limit for testing
        logger = RateLimitedLogger(max_logs_per_second=2)
        
        # First two logs should be allowed
        assert logger.should_log("test_key", "test message 1") is True
        assert logger.should_log("test_key", "test message 2") is True
        
        # Third log should be rate limited
        assert logger.should_log("test_key", "test message 3") is False
    
    def test_rate_limiting_time_window(self):
        """Test that rate limiting resets after time window."""
        logger = RateLimitedLogger(max_logs_per_second=1)
        
        # First log should be allowed
        assert logger.should_log("test_key", "test message 1") is True
        
        # Second log should be rate limited (same key, different message to avoid deduplication)
        assert logger.should_log("test_key", "test message 2") is False
        
        # Mock time to simulate passage of time and force cleanup
        future_time = time.time() + 2
        with patch('time.time', return_value=future_time):
            logger._cleanup_old_entries(future_time)
            # After time window, should be allowed again
            assert logger.should_log("test_key", "test message 3") is True
    
    def test_deduplication_basic(self):
        """Test basic message deduplication."""
        logger = RateLimitedLogger(max_logs_per_second=100, enable_deduplication=True)
        
        # First occurrence should be logged
        assert logger.should_log("test_key", "duplicate message") is True
        
        # Subsequent occurrences should be deduplicated
        assert logger.should_log("test_key", "duplicate message") is False
        assert logger.should_log("test_key", "duplicate message") is False
    
    def test_deduplication_every_tenth(self):
        """Test that every 10th duplicate message is logged."""
        logger = RateLimitedLogger(max_logs_per_second=100, enable_deduplication=True)
        
        # First message
        assert logger.should_log("test_key", "duplicate message") is True
        
        # Next 8 should be suppressed
        for i in range(8):
            assert logger.should_log("test_key", "duplicate message") is False
        
        # 10th occurrence should be logged
        assert logger.should_log("test_key", "duplicate message") is True
    
    def test_deduplication_disabled(self):
        """Test that deduplication can be disabled."""
        logger = RateLimitedLogger(max_logs_per_second=100, enable_deduplication=False)
        
        # All messages should be allowed when deduplication is disabled
        assert logger.should_log("test_key", "duplicate message") is True
        assert logger.should_log("test_key", "duplicate message") is True
        assert logger.should_log("test_key", "duplicate message") is True
    
    def test_sampling_for_debug_logs(self):
        """Test sampling for DEBUG level logs."""
        logger = RateLimitedLogger(max_logs_per_second=100, sampling_rate=0.5)
        
        # Track results for multiple calls
        results = []
        for i in range(10):
            result = logger.should_log("debug_key", f"debug message {i}", logging.DEBUG)
            results.append(result)
        
        # Should have some True and some False due to sampling
        assert True in results
        assert False in results
    
    def test_different_keys_independent(self):
        """Test that different log keys are rate limited independently."""
        logger = RateLimitedLogger(max_logs_per_second=1)
        
        # Different keys should be independent (use different messages to avoid deduplication)
        assert logger.should_log("key1", "message1") is True
        assert logger.should_log("key2", "message2") is True
        
        # Same keys should be rate limited (use different messages to avoid deduplication)
        assert logger.should_log("key1", "message3") is False
        assert logger.should_log("key2", "message4") is False
    
    def test_cleanup_old_entries(self):
        """Test that old entries are cleaned up."""
        logger = RateLimitedLogger(max_logs_per_second=1)
        
        # Add some entries
        logger.should_log("test_key", "message")
        
        # Verify entries exist
        assert "test_key" in logger.log_counts
        
        # Mock time to simulate cleanup
        with patch('time.time', return_value=time.time() + 3700):  # 1+ hour later
            logger._cleanup_old_entries(time.time() + 3700)
        
        # Entries should be cleaned up
        assert len(logger.log_counts) == 0
    
    def test_get_stats(self):
        """Test statistics reporting."""
        logger = RateLimitedLogger(max_logs_per_second=10)
        
        # Generate some activity
        logger.should_log("key1", "message1")
        logger.should_log("key2", "message2")
        logger.should_log("key1", "message1")  # duplicate
        
        stats = logger.get_stats()
        
        assert "rate_limited_keys" in stats
        assert "deduplicated_messages" in stats
        assert "suppressed_count" in stats
        assert stats["max_logs_per_second"] == 10


class TestOptimizedRequestLogger:
    """Test cases for OptimizedRequestLogger class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.rate_limiter = RateLimitedLogger(max_logs_per_second=100)
        self.logger = OptimizedRequestLogger(self.rate_limiter)
    
    def test_log_request_start_debug_paths(self):
        """Test that debug paths are logged at DEBUG level."""
        with patch.object(self.logger, 'logger') as mock_logger:
            # Test debug path
            self.logger.log_request_start("GET", "/health", "127.0.0.1", "test-id")
            
            # Should call debug method
            mock_logger.debug.assert_called_once()
            mock_logger.info.assert_not_called()
    
    def test_log_request_start_regular_paths(self):
        """Test that regular paths are logged at INFO level."""
        with patch.object(self.logger, 'logger') as mock_logger:
            # Test regular path
            self.logger.log_request_start("GET", "/api/v1/patients", "127.0.0.1", "test-id")
            
            # Should call info method
            mock_logger.info.assert_called_once()
            mock_logger.debug.assert_not_called()
    
    def test_log_request_start_quiet_paths(self):
        """Test that quiet paths are not logged."""
        with patch.object(self.logger, 'logger') as mock_logger:
            # Test quiet path
            self.logger.log_request_start("GET", "/api/v1/health", "127.0.0.1", "test-id")
            
            # Should not call any logging methods
            mock_logger.debug.assert_not_called()
            mock_logger.info.assert_not_called()
    
    def test_log_request_complete_status_codes(self):
        """Test appropriate log levels for different status codes."""
        with patch.object(self.logger, 'logger') as mock_logger:
            # Test 500 error
            self.logger.log_request_complete("GET", "/api/v1/test", 500, 0.1, "test-id")
            mock_logger.error.assert_called_once()
            
            # Reset mock
            mock_logger.reset_mock()
            
            # Test 400 error
            self.logger.log_request_complete("GET", "/api/v1/test", 400, 0.1, "test-id")
            mock_logger.warning.assert_called_once()
            
            # Reset mock
            mock_logger.reset_mock()
            
            # Test 200 success
            self.logger.log_request_complete("GET", "/api/v1/test", 200, 0.1, "test-id")
            mock_logger.info.assert_called_once()
    
    def test_log_request_error_with_stacktrace(self):
        """Test error logging with appropriate stack trace handling."""
        with patch.object(self.logger, 'logger') as mock_logger:
            # Test unexpected error (should include stack trace)
            error = RuntimeError("Unexpected error")
            self.logger.log_request_error("GET", "/api/v1/test", error, 0.1, "test-id")
            
            # Should call error with exc_info=True
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert call_args[1]['exc_info'] is True
    
    def test_log_request_error_without_stacktrace(self):
        """Test error logging without stack trace for expected errors."""
        with patch.object(self.logger, 'logger') as mock_logger:
            # Create a mock HTTPException
            error = Mock()
            error.__class__.__name__ = "HTTPException"
            error.status_code = 400
            
            self.logger.log_request_error("GET", "/api/v1/test", error, 0.1, "test-id")
            
            # Should call warning without exc_info
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert call_args[1]['exc_info'] is False
    
    def test_rate_limiting_integration(self):
        """Test that rate limiting is properly integrated."""
        # Create logger with very low rate limit
        rate_limiter = RateLimitedLogger(max_logs_per_second=1)
        logger = OptimizedRequestLogger(rate_limiter)
        
        with patch.object(logger, 'logger') as mock_logger:
            # First request should be logged
            logger.log_request_start("GET", "/api/v1/test", "127.0.0.1", "test-id-1")
            assert mock_logger.info.call_count == 1
            
            # Second request should be rate limited (use different message to avoid deduplication)
            logger.log_request_start("GET", "/api/v1/test2", "127.0.0.1", "test-id-2")
            assert mock_logger.info.call_count == 1  # Still 1, not 2


class TestConfigureOptimizedLogging:
    """Test cases for configure_optimized_logging function."""
    
    def test_configure_with_rate_limiting(self):
        """Test configuration with rate limiting enabled."""
        with patch('app.core.logging_config.logging') as mock_logging:
            mock_root_logger = Mock()
            mock_root_logger.handlers = []
            mock_logging.getLogger.return_value = mock_root_logger
            mock_logging.INFO = logging.INFO
            mock_logging.StreamHandler = logging.StreamHandler
            mock_logging.Formatter = logging.Formatter
            
            rate_limiter = configure_optimized_logging(
                log_level="DEBUG",
                max_logs_per_second=50,
                enable_rate_limiting=True
            )
            
            assert rate_limiter is not None
            assert isinstance(rate_limiter, RateLimitedLogger)
            assert rate_limiter.max_logs_per_second == 50
    
    def test_configure_without_rate_limiting(self):
        """Test configuration with rate limiting disabled."""
        with patch('app.core.logging_config.logging') as mock_logging:
            mock_root_logger = Mock()
            mock_root_logger.handlers = []
            mock_logging.getLogger.return_value = mock_root_logger
            mock_logging.INFO = logging.INFO
            mock_logging.StreamHandler = logging.StreamHandler
            mock_logging.Formatter = logging.Formatter
            
            rate_limiter = configure_optimized_logging(
                enable_rate_limiting=False
            )
            
            assert rate_limiter is None
    
    def test_third_party_logger_levels(self):
        """Test that third-party loggers are set to appropriate levels."""
        with patch('app.core.logging_config.logging') as mock_logging:
            mock_loggers = {}
            
            def get_logger_side_effect(name=None):
                if name is None:
                    name = 'root'
                if name not in mock_loggers:
                    mock_loggers[name] = Mock()
                    mock_loggers[name].handlers = []
                return mock_loggers[name]
            
            mock_logging.getLogger.side_effect = get_logger_side_effect
            mock_logging.INFO = logging.INFO
            mock_logging.WARNING = logging.WARNING
            mock_logging.StreamHandler = logging.StreamHandler
            mock_logging.Formatter = logging.Formatter
            
            configure_optimized_logging()
            
            # Check that third-party loggers were configured
            assert 'uvicorn.access' in mock_loggers
            assert 'uvicorn.error' in mock_loggers
            assert 'fastapi' in mock_loggers
            assert 'sqlalchemy.engine' in mock_loggers


class TestMiddlewareLoggingPerformance:
    """Test cases for middleware logging performance under load."""
    
    def test_rate_limiter_performance(self):
        """Test rate limiter performance with many requests."""
        logger = RateLimitedLogger(max_logs_per_second=100)
        
        start_time = time.time()
        
        # Simulate 1000 log checks
        for i in range(1000):
            logger.should_log(f"key_{i % 10}", f"message_{i}")
        
        end_time = time.time()
        
        # Should complete quickly (less than 1 second for 1000 operations)
        assert end_time - start_time < 1.0
    
    def test_deduplication_performance(self):
        """Test deduplication performance with many duplicate messages."""
        logger = RateLimitedLogger(
            max_logs_per_second=1000,
            enable_deduplication=True
        )
        
        start_time = time.time()
        
        # Simulate many duplicate messages
        for i in range(1000):
            logger.should_log("test_key", "duplicate message")
        
        end_time = time.time()
        
        # Should complete quickly despite deduplication
        assert end_time - start_time < 1.0
        
        # Should have suppressed most messages (allow some tolerance)
        stats = logger.get_stats()
        assert stats['suppressed_count'] > 890
    
    def test_memory_cleanup_prevents_leaks(self):
        """Test that memory cleanup prevents memory leaks."""
        logger = RateLimitedLogger(max_logs_per_second=100)
        
        # Generate many different keys
        for i in range(1000):
            logger.should_log(f"unique_key_{i}", f"message_{i}")
        
        initial_key_count = len(logger.log_counts)
        
        # Simulate time passage and cleanup
        with patch('time.time', return_value=time.time() + 3700):
            logger._cleanup_old_entries(time.time() + 3700)
        
        final_key_count = len(logger.log_counts)
        
        # Should have cleaned up old entries
        assert final_key_count < initial_key_count


@pytest.fixture
def mock_request():
    """Create a mock request for testing."""
    request = Mock()
    request.method = "GET"
    request.url.path = "/api/v1/test"
    request.client.host = "127.0.0.1"
    return request


@pytest.fixture
def mock_response():
    """Create a mock response for testing."""
    response = Mock()
    response.status_code = 200
    response.headers = {"content-length": "100"}
    return response


class TestMiddlewareIntegration:
    """Integration tests for middleware logging optimization."""
    
    def test_request_logging_middleware_with_rate_limiting(self, mock_request, mock_response):
        """Test RequestLoggingMiddleware with rate limiting enabled."""
        # Mock the settings to avoid validation errors
        with patch('app.middleware.enhanced_middleware.settings') as mock_settings:
            mock_settings.SECRET_KEY = "test_secret"
            mock_settings.DATABASE_URL = "test_db_url"
            
            from app.middleware.enhanced_middleware import RequestLoggingMiddleware
            
            # Create middleware with rate limiting
            middleware = RequestLoggingMiddleware(
                app=Mock(),
                enable_rate_limiting=True,
                max_logs_per_second=2
            )
            
            assert middleware.rate_limiter is not None
            assert middleware.optimized_logger is not None
            assert middleware.rate_limiter.max_logs_per_second == 2
    
    def test_request_logging_middleware_without_rate_limiting(self, mock_request, mock_response):
        """Test RequestLoggingMiddleware with rate limiting disabled."""
        # Mock the settings to avoid validation errors
        with patch('app.middleware.enhanced_middleware.settings') as mock_settings:
            mock_settings.SECRET_KEY = "test_secret"
            mock_settings.DATABASE_URL = "test_db_url"
            
            from app.middleware.enhanced_middleware import RequestLoggingMiddleware
            
            # Create middleware without rate limiting
            middleware = RequestLoggingMiddleware(
                app=Mock(),
                enable_rate_limiting=False
            )
            
            assert middleware.rate_limiter is None
            assert middleware.optimized_logger is None