"""
Unit tests for centralized error handling functionality.

Tests the CriticalErrorHandler class and its various error handling methods,
including fallback mechanisms, rate limiting, and error tracking.
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.core.error_handler import (
    CriticalErrorHandler,
    error_handler,
    handle_di_error,
    handle_role_error,
    handle_schema_error,
    handle_validation_error
)
from app.models.error_tracking import ErrorLog


class TestCriticalErrorHandler:
    """Test cases for the CriticalErrorHandler class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.handler = CriticalErrorHandler(max_errors_per_hour=5, enable_tracking=True)

    def test_error_key_creation(self):
        """Test error key creation for deduplication."""
        error_type = "TEST_ERROR"
        error_message = "This is a test error"
        
        key1 = self.handler._create_error_key(error_type, error_message)
        key2 = self.handler._create_error_key(error_type, error_message)
        key3 = self.handler._create_error_key(error_type, "Different message")
        
        # Same error should produce same key
        assert key1 == key2
        # Different message should produce different key
        assert key1 != key3
        # Key should contain error type
        assert error_type in key1

    def test_rate_limiting_functionality(self):
        """Test that error rate limiting works correctly."""
        error_key = "test_error_key"
        
        # First 5 errors should be allowed
        for i in range(5):
            assert self.handler._should_log_error(error_key) is True
        
        # 6th error should be rate limited
        assert self.handler._should_log_error(error_key) is False
        
        # Different error key should not be affected
        assert self.handler._should_log_error("different_key") is True

    def test_rate_limiting_time_window(self):
        """Test that rate limiting respects time windows."""
        error_key = "time_test_key"
        
        # Fill up the rate limit
        for i in range(5):
            assert self.handler._should_log_error(error_key) is True
        
        # Should be rate limited now
        assert self.handler._should_log_error(error_key) is False
        
        # Simulate time passing (mock the timestamps)
        old_time = time.time() - 3700  # More than 1 hour ago
        self.handler.error_counts[error_key] = [old_time] * 5
        
        # Should be allowed again after time window
        assert self.handler._should_log_error(error_key) is True

    @pytest.mark.asyncio
    async def test_dependency_injection_error_handling(self):
        """Test handling of dependency injection errors."""
        test_error = AttributeError("'generator' object has no attribute 'monthly_quiz_service'")
        context = {"endpoint": "/api/v1/test", "method": "GET"}
        
        with patch.object(self.handler, '_track_error_in_db', new_callable=AsyncMock) as mock_track:
            with pytest.raises(HTTPException) as exc_info:
                await self.handler.handle_dependency_injection_error(test_error, context)
            
            # Should raise 500 error with secure message
            assert exc_info.value.status_code == 500
            assert "Service temporarily unavailable" in exc_info.value.detail
            assert "generator" not in exc_info.value.detail  # Should not expose internal details
            
            # Should track error in database
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert call_args[1]['error_type'] == "DI_GENERATOR_ERROR"
            assert call_args[1]['severity'] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_role_enum_error_handling(self):
        """Test handling of role enum errors."""
        test_error = AttributeError("'UserRole' has no attribute 'SUPER_ADMIN'")
        user_role = "invalid_role"
        endpoint = "/api/v1/analytics"
        
        with patch.object(self.handler, '_track_error_in_db', new_callable=AsyncMock) as mock_track:
            with pytest.raises(HTTPException) as exc_info:
                await self.handler.handle_role_enum_error(test_error, user_role, endpoint)
            
            # Should raise 403 error with secure message
            assert exc_info.value.status_code == 403
            assert "Access denied" in exc_info.value.detail
            assert "SUPER_ADMIN" not in exc_info.value.detail  # Should not expose internal details
            
            # Should track error in database
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert call_args[1]['error_type'] == "ROLE_ENUM_ERROR"
            assert call_args[1]['context']['user_role'] == user_role
            assert call_args[1]['context']['endpoint'] == endpoint

    @pytest.mark.asyncio
    async def test_schema_mismatch_error_handling(self):
        """Test handling of database schema mismatch errors."""
        test_error = SQLAlchemyError("column 'alert_type' does not exist")
        table_name = "alerts"
        operation = "SELECT"
        
        with patch.object(self.handler, '_track_error_in_db', new_callable=AsyncMock) as mock_track:
            with pytest.raises(HTTPException) as exc_info:
                await self.handler.handle_schema_mismatch_error(test_error, table_name, operation)
            
            # Should raise 500 error with helpful message
            assert exc_info.value.status_code == 500
            assert "Database schema mismatch" in exc_info.value.detail
            assert "contact support" in exc_info.value.detail
            
            # Should track error in database
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert call_args[1]['error_type'] == "SCHEMA_MISMATCH_ERROR"
            assert call_args[1]['context']['table_name'] == table_name
            assert call_args[1]['context']['operation'] == operation

    @pytest.mark.asyncio
    async def test_validation_error_handling(self):
        """Test handling of validation errors."""
        test_error = ValueError("Invalid date format: not-a-date")
        field_name = "start_date"
        input_value = "not-a-date"
        
        with patch.object(self.handler, '_track_error_in_db', new_callable=AsyncMock) as mock_track:
            with pytest.raises(HTTPException) as exc_info:
                await self.handler.handle_validation_error(test_error, field_name, input_value)
            
            # Should raise 400 error with helpful message
            assert exc_info.value.status_code == 400
            assert field_name in exc_info.value.detail
            assert "Invalid value" in exc_info.value.detail
            
            # Should track error in database with WARNING severity
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert call_args[1]['error_type'] == "VALIDATION_ERROR"
            assert call_args[1]['severity'] == "WARNING"
            assert call_args[1]['context']['field_name'] == field_name

    @pytest.mark.asyncio
    async def test_generic_error_handling(self):
        """Test handling of generic errors."""
        test_error = RuntimeError("Unexpected runtime error")
        error_type = "RUNTIME_ERROR"
        context = {"operation": "data_processing"}
        
        with patch.object(self.handler, '_track_error_in_db', new_callable=AsyncMock) as mock_track:
            with pytest.raises(HTTPException) as exc_info:
                await self.handler.handle_generic_error(
                    test_error,
                    error_type=error_type,
                    context=context,
                    status_code=503,
                    user_message="Service temporarily unavailable"
                )
            
            # Should raise specified status code with custom message
            assert exc_info.value.status_code == 503
            assert exc_info.value.detail == "Service temporarily unavailable"
            
            # Should track error in database
            mock_track.assert_called_once()
            call_args = mock_track.call_args
            assert call_args[1]['error_type'] == error_type
            assert call_args[1]['context']['operation'] == "data_processing"

    def test_error_context_manager(self):
        """Test the error context manager functionality."""
        operation = "test_operation"
        context_data = {"user_id": "123", "action": "test"}
        
        # Test successful operation
        with self.handler.error_context(operation, **context_data):
            pass  # Should not raise any errors
        
        # Test AttributeError with UserRole (should convert to HTTPException)
        with pytest.raises(HTTPException) as exc_info:
            with self.handler.error_context(operation, **context_data):
                raise AttributeError("'UserRole' has no attribute 'SUPER_ADMIN'")
        
        assert exc_info.value.status_code == 403
        assert "Access denied" in exc_info.value.detail
        
        # Test SQLAlchemyError (should convert to HTTPException)
        with pytest.raises(HTTPException) as exc_info:
            with self.handler.error_context(operation, **context_data):
                raise SQLAlchemyError("Database error")
        
        assert exc_info.value.status_code == 500
        assert "Database schema mismatch" in exc_info.value.detail
        
        # Test generic error (should convert to HTTPException)
        with pytest.raises(HTTPException) as exc_info:
            with self.handler.error_context(operation, **context_data):
                raise RuntimeError("Generic error")
        
        assert exc_info.value.status_code == 500
        assert "unexpected error" in exc_info.value.detail
        
        # Test HTTPException passthrough
        with pytest.raises(HTTPException) as exc_info:
            with self.handler.error_context(operation, **context_data):
                raise HTTPException(status_code=400, detail="Original error")
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Original error"

    @pytest.mark.asyncio
    async def test_error_tracking_database_operations(self):
        """Test error tracking database operations with mocked session."""
        error_type = "TEST_ERROR"
        error_message = "Test error message"
        context = {"test": "data"}
        stack_trace = "Test stack trace"
        
        # Mock the database session and ErrorLog
        mock_session = Mock()
        mock_error_log = Mock(spec=ErrorLog)
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        with patch('app.core.error_handler.get_scoped_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session
            
            # Test creating new error log
            result = await self.handler._track_error_in_db(
                error_type, error_message, context, stack_trace
            )
            
            # Should add new error log to session
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_tracking_deduplication(self):
        """Test error deduplication in database tracking."""
        error_type = "TEST_ERROR"
        error_message = "Test error message"
        context = {"test": "data"}
        
        # Mock existing error log
        mock_session = Mock()
        mock_existing_error = Mock(spec=ErrorLog)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_existing_error
        
        with patch('app.core.error_handler.get_scoped_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_session
            
            # Test updating existing error log
            result = await self.handler._track_error_in_db(
                error_type, error_message, context
            )
            
            # Should increment count on existing error
            mock_existing_error.increment_count.assert_called_once()
            # Should not add new error log
            mock_session.add.assert_not_called()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_tracking_database_failure(self):
        """Test error tracking handles database failures gracefully."""
        error_type = "TEST_ERROR"
        error_message = "Test error message"
        context = {"test": "data"}
        
        # Mock database failure
        with patch('app.core.error_handler.get_scoped_session') as mock_get_session:
            mock_get_session.side_effect = Exception("Database connection failed")
            
            # Should not raise exception, just return None
            result = await self.handler._track_error_in_db(
                error_type, error_message, context
            )
            
            assert result is None

    def test_error_statistics(self):
        """Test error statistics functionality."""
        # Add some errors to the handler
        self.handler._should_log_error("error_type_1")
        self.handler._should_log_error("error_type_1")
        self.handler._should_log_error("error_type_2")
        
        stats = self.handler.get_error_stats()
        
        assert "error_types" in stats
        assert "total_error_types" in stats
        assert "rate_limit_threshold" in stats
        
        assert stats["total_error_types"] == 2
        assert stats["rate_limit_threshold"] == 5
        
        # Check individual error type stats
        error_types = stats["error_types"]
        assert "error_type_1" in error_types
        assert "error_type_2" in error_types
        assert error_types["error_type_1"]["count_last_hour"] == 2
        assert error_types["error_type_2"]["count_last_hour"] == 1

    def test_disabled_tracking(self):
        """Test handler with tracking disabled."""
        handler_no_tracking = CriticalErrorHandler(enable_tracking=False)
        
        # Should still handle rate limiting
        assert handler_no_tracking._should_log_error("test_key") is True
        
        # But tracking should be disabled
        assert handler_no_tracking.enable_tracking is False


class TestConvenienceFunctions:
    """Test the convenience functions for common error types."""

    @pytest.mark.asyncio
    async def test_handle_di_error_convenience(self):
        """Test the handle_di_error convenience function."""
        test_error = AttributeError("DI error")
        context = {"test": "context"}
        
        with patch.object(error_handler, 'handle_dependency_injection_error', new_callable=AsyncMock) as mock_handle:
            await handle_di_error(test_error, context)
            mock_handle.assert_called_once_with(test_error, context)

    @pytest.mark.asyncio
    async def test_handle_role_error_convenience(self):
        """Test the handle_role_error convenience function."""
        test_error = AttributeError("Role error")
        user_role = "invalid"
        endpoint = "/test"
        
        with patch.object(error_handler, 'handle_role_enum_error', new_callable=AsyncMock) as mock_handle:
            await handle_role_error(test_error, user_role, endpoint)
            mock_handle.assert_called_once_with(test_error, user_role, endpoint)

    @pytest.mark.asyncio
    async def test_handle_schema_error_convenience(self):
        """Test the handle_schema_error convenience function."""
        test_error = SQLAlchemyError("Schema error")
        table_name = "test_table"
        operation = "SELECT"
        
        with patch.object(error_handler, 'handle_schema_mismatch_error', new_callable=AsyncMock) as mock_handle:
            await handle_schema_error(test_error, table_name, operation)
            mock_handle.assert_called_once_with(test_error, table_name, operation)

    @pytest.mark.asyncio
    async def test_handle_validation_error_convenience(self):
        """Test the handle_validation_error convenience function."""
        test_error = ValueError("Validation error")
        field_name = "test_field"
        input_value = "invalid"
        
        with patch.object(error_handler, 'handle_validation_error', new_callable=AsyncMock) as mock_handle:
            await handle_validation_error(test_error, field_name, input_value)
            mock_handle.assert_called_once_with(test_error, field_name, input_value)


class TestSecurityAspects:
    """Test security aspects of error handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.handler = CriticalErrorHandler()

    @pytest.mark.asyncio
    async def test_secure_error_messages(self):
        """Test that error messages don't expose internal details."""
        # Test DI error doesn't expose generator details
        di_error = AttributeError("'generator' object has no attribute 'monthly_quiz_service'")
        with pytest.raises(HTTPException) as exc_info:
            await self.handler.handle_dependency_injection_error(di_error, {})
        
        assert "generator" not in exc_info.value.detail
        assert "monthly_quiz_service" not in exc_info.value.detail
        
        # Test role error doesn't expose enum details
        role_error = AttributeError("'UserRole' has no attribute 'SUPER_ADMIN'")
        with pytest.raises(HTTPException) as exc_info:
            await self.handler.handle_role_enum_error(role_error)
        
        assert "UserRole" not in exc_info.value.detail
        assert "SUPER_ADMIN" not in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_secure_fallback_behavior(self):
        """Test that fallbacks default to secure behavior (deny access)."""
        # Role errors should deny access (403)
        role_error = AttributeError("Role error")
        with pytest.raises(HTTPException) as exc_info:
            await self.handler.handle_role_enum_error(role_error)
        
        assert exc_info.value.status_code == 403
        
        # DI errors should return service unavailable (500)
        di_error = AttributeError("DI error")
        with pytest.raises(HTTPException) as exc_info:
            await self.handler.handle_dependency_injection_error(di_error, {})
        
        assert exc_info.value.status_code == 500

    def test_context_data_sanitization(self):
        """Test that sensitive data is not logged in context."""
        # This is a placeholder for future context sanitization
        # Currently, the handler logs context as-is, but in production
        # we might want to sanitize sensitive fields like passwords, tokens, etc.
        pass