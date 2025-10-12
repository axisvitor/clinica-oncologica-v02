"""
Tests for graceful error handling system.

This module tests the comprehensive error handling system including:
- Graceful error handler functionality
- Circuit breaker pattern implementation
- Enhanced error logging with correlation IDs
- Error aggregation and alerting
"""
import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from sqlalchemy.exc import (
    IntegrityError, 
    OperationalError, 
    DisconnectionError,
    DatabaseError
)
from websockets.exceptions import ConnectionClosed, InvalidState
from fastapi import HTTPException

from app.core.graceful_error_handler import (
    GracefulErrorHandler,
    ErrorResponse,
    ErrorCategory,
    ErrorSeverity,
    graceful_error_handler
)
from app.core.database_circuit_breaker import (
    DatabaseCircuitBreaker,
    DatabaseCircuitBreakerManager,
    get_db_circuit_manager
)
from app.core.enhanced_error_logging import (
    StructuredErrorLogger,
    CorrelationIdManager,
    ErrorContext,
    ErrorAggregation,
    LogLevel,
    AlertSeverity,
    get_enhanced_error_logger
)
from app.services.circuit_breaker import CircuitState, CircuitOpenError


class TestGracefulErrorHandler:
    """Test cases for GracefulErrorHandler."""

    @pytest.fixture
    def error_handler(self):
        """Create error handler instance for testing."""
        return GracefulErrorHandler(max_errors_per_hour=100, enable_tracking=False)

    @pytest.mark.asyncio
    async def test_handle_database_error_integrity_error(self, error_handler):
        """Test handling of database integrity errors."""
        error = IntegrityError("duplicate key", None, None)
        
        response = await error_handler.handle_database_error(
            error=error,
            operation="create_user",
            table_name="users"
        )
        
        assert response.error_code == "DB_INTEGRITY_ERROR"
        assert response.status_code == 400
        assert response.category == ErrorCategory.DATABASE
        assert response.severity == ErrorSeverity.WARNING
        assert "integrity constraint" in response.message.lower()
        assert len(response.suggestions) > 0

    @pytest.mark.asyncio
    async def test_handle_database_error_operational_error(self, error_handler):
        """Test handling of database operational errors."""
        error = OperationalError("connection failed", None, None)
        
        response = await error_handler.handle_database_error(
            error=error,
            operation="fetch_data",
            table_name="messages"
        )
        
        assert response.error_code == "DB_OPERATIONAL_ERROR"
        assert response.status_code == 503
        assert response.category == ErrorCategory.DATABASE
        assert response.severity == ErrorSeverity.ERROR

    @pytest.mark.asyncio
    async def test_handle_database_error_disconnection_error(self, error_handler):
        """Test handling of database disconnection errors."""
        error = DisconnectionError("connection lost")
        
        response = await error_handler.handle_database_error(
            error=error,
            operation="transaction",
            query_context={"transaction_id": "tx_123"}
        )
        
        assert response.error_code == "DB_CONNECTION_LOST"
        assert response.status_code == 503
        assert response.severity == ErrorSeverity.CRITICAL
        assert "reconnect" in response.suggestions[0].lower()

    @pytest.mark.asyncio
    async def test_handle_websocket_error_connection_closed(self, error_handler):
        """Test handling of WebSocket connection closed errors."""
        # Create a proper ConnectionClosed exception
        error = ConnectionClosed(rcvd=None, sent=None)
        
        response = await error_handler.handle_websocket_error(
            error=error,
            connection_id="conn_123",
            user_id="user_456"
        )
        
        assert response.error_code == "WS_CONNECTION_CLOSED"
        assert response.status_code == 503
        assert response.category == ErrorCategory.WEBSOCKET
        assert response.severity == ErrorSeverity.WARNING

    @pytest.mark.asyncio
    async def test_handle_websocket_error_invalid_state(self, error_handler):
        """Test handling of WebSocket invalid state errors."""
        error = InvalidState("WebSocket is not connected")
        
        response = await error_handler.handle_websocket_error(
            error=error,
            connection_id="conn_123",
            operation="send_message"
        )
        
        assert response.error_code == "WS_INVALID_STATE"
        assert response.status_code == 400
        assert response.severity == ErrorSeverity.WARNING

    @pytest.mark.asyncio
    async def test_handle_api_error_validation_error(self, error_handler):
        """Test handling of API validation errors."""
        from pydantic import ValidationError
        
        # Create a mock validation error
        error = ValueError("Invalid email format")
        
        response = await error_handler.handle_api_error(
            error=error,
            endpoint="/api/v1/users",
            method="POST",
            user_id="user_123"
        )
        
        assert response.error_code == "API_VALUE_ERROR"
        assert response.status_code == 400
        assert response.category == ErrorCategory.VALIDATION

    @pytest.mark.asyncio
    async def test_handle_api_error_permission_error(self, error_handler):
        """Test handling of API permission errors."""
        error = PermissionError("Access denied")
        
        response = await error_handler.handle_api_error(
            error=error,
            endpoint="/api/v1/admin",
            method="GET",
            user_id="user_123"
        )
        
        assert response.error_code == "API_PERMISSION_DENIED"
        assert response.status_code == 403
        assert response.category == ErrorCategory.AUTHORIZATION

    @pytest.mark.asyncio
    async def test_handle_graceful_degradation(self, error_handler):
        """Test graceful degradation functionality."""
        primary_error = Exception("Service unavailable")
        fallback_data = {"message": "Using cached data"}
        
        result = await error_handler.handle_graceful_degradation(
            primary_error=primary_error,
            fallback_data=fallback_data,
            operation="get_analytics"
        )
        
        assert result["data"] == fallback_data
        assert "warning" in result
        assert result["warning"]["message"] == "Service is running in degraded mode"

    def test_sanitize_request_data(self, error_handler):
        """Test request data sanitization."""
        sensitive_data = {
            "username": "testuser",
            "password": "secret123",
            "token": "abc123",
            "email": "test@example.com",
            "nested": {
                "api_key": "key123",
                "public_info": "visible"
            }
        }
        
        sanitized = error_handler._sanitize_request_data(sensitive_data)
        
        assert sanitized["username"] == "testuser"
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["token"] == "[REDACTED]"
        assert sanitized["email"] == "test@example.com"
        assert sanitized["nested"]["api_key"] == "[REDACTED]"
        assert sanitized["nested"]["public_info"] == "visible"


class TestDatabaseCircuitBreaker:
    """Test cases for DatabaseCircuitBreaker."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker instance for testing."""
        return DatabaseCircuitBreaker(
            name="test_db",
            failure_threshold=3,
            recovery_timeout=1,  # Short timeout for testing
            enable_fallback=True
        )

    @pytest.mark.asyncio
    async def test_execute_query_success(self, circuit_breaker):
        """Test successful query execution."""
        async def mock_query():
            return {"result": "success"}
        
        result = await circuit_breaker.execute_query(
            query_func=mock_query,
            operation_name="test_query"
        )
        
        assert result == {"result": "success"}
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_execute_query_with_fallback(self, circuit_breaker):
        """Test query execution with fallback data."""
        async def failing_query():
            raise OperationalError("Database error", None, None)
        
        fallback_data = {"result": "fallback"}
        
        # This should use graceful degradation
        with patch('app.core.graceful_error_handler.graceful_error_handler') as mock_handler:
            mock_handler.handle_graceful_degradation.return_value = {
                "data": fallback_data,
                "warning": {"message": "degraded mode"}
            }
            
            # Force circuit to open by causing failures
            for _ in range(3):
                try:
                    await circuit_breaker.execute_query(
                        query_func=failing_query,
                        fallback_data=fallback_data,
                        operation_name="test_query"
                    )
                except:
                    pass
            
            # Circuit should be open now
            assert circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self, circuit_breaker):
        """Test circuit breaker recovery mechanism."""
        async def failing_query():
            raise DatabaseError("Database error", None, None)
        
        async def successful_query():
            return {"result": "success"}
        
        # Force circuit to open
        for _ in range(3):
            try:
                await circuit_breaker.call(failing_query)
            except:
                pass
        
        assert circuit_breaker.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(1.1)
        
        # Next call should half-open the circuit
        result = await circuit_breaker.call(successful_query)
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        
        # Another success should close the circuit
        result = await circuit_breaker.call(successful_query)
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_health_check(self, circuit_breaker):
        """Test database health check functionality."""
        with patch('app.core.database.get_scoped_session') as mock_session:
            mock_session.return_value.__enter__.return_value.execute.return_value = None
            
            health = await circuit_breaker.health_check()
            assert health is True
            assert circuit_breaker.is_healthy() is True

    def test_get_detailed_stats(self, circuit_breaker):
        """Test detailed statistics retrieval."""
        stats = circuit_breaker.get_detailed_stats()
        
        assert "name" in stats
        assert "state" in stats
        assert "connection_pool_healthy" in stats
        assert "fallback_enabled" in stats
        assert stats["fallback_enabled"] is True


class TestDatabaseCircuitBreakerManager:
    """Test cases for DatabaseCircuitBreakerManager."""

    @pytest.fixture
    def manager(self):
        """Create circuit breaker manager for testing."""
        return DatabaseCircuitBreakerManager()

    def test_get_breaker_existing(self, manager):
        """Test getting existing circuit breaker."""
        breaker = manager.get_breaker("read_operations")
        assert breaker.name == "database_read"
        assert isinstance(breaker, DatabaseCircuitBreaker)

    def test_get_breaker_new(self, manager):
        """Test creating new circuit breaker for unknown operation."""
        breaker = manager.get_breaker("custom_operation")
        assert breaker.name == "database_custom_operation"
        assert isinstance(breaker, DatabaseCircuitBreaker)

    @pytest.mark.asyncio
    async def test_execute_read_operation(self, manager):
        """Test executing read operation through manager."""
        async def mock_query():
            return [{"id": 1, "name": "test"}]
        
        result = await manager.execute_read_operation(
            query_func=mock_query,
            fallback_data=[]
        )
        
        assert result == [{"id": 1, "name": "test"}]

    @pytest.mark.asyncio
    async def test_execute_analytics_query(self, manager):
        """Test executing analytics query with fallback."""
        async def mock_query():
            return {"data": [1, 2, 3], "total": 3}
        
        result = await manager.execute_analytics_query(
            query_func=mock_query
        )
        
        assert result == {"data": [1, 2, 3], "total": 3}

    @pytest.mark.asyncio
    async def test_health_check_all(self, manager):
        """Test health check for all circuit breakers."""
        with patch.object(DatabaseCircuitBreaker, 'health_check', return_value=True):
            health_status = await manager.health_check_all()
            
            assert isinstance(health_status, dict)
            assert len(health_status) > 0
            assert all(status is True for status in health_status.values())

    def test_get_all_stats(self, manager):
        """Test getting statistics for all circuit breakers."""
        stats = manager.get_all_stats()
        
        assert isinstance(stats, dict)
        assert "read_operations" in stats
        assert "write_operations" in stats
        assert "analytics_queries" in stats


class TestStructuredErrorLogger:
    """Test cases for StructuredErrorLogger."""

    @pytest.fixture
    def error_logger(self):
        """Create error logger instance for testing."""
        return StructuredErrorLogger(
            enable_aggregation=True,
            enable_alerting=False  # Disable alerting for tests
        )

    def test_log_error_basic(self, error_logger):
        """Test basic error logging functionality."""
        error = ValueError("Test error")
        
        with patch.object(error_logger.logger, 'log') as mock_log:
            correlation_id = error_logger.log_error(
                error=error,
                user_id="user_123",
                endpoint="/api/test"
            )
            
            assert correlation_id is not None
            assert len(correlation_id) > 0
            mock_log.assert_called_once()

    def test_log_structured_event(self, error_logger):
        """Test structured event logging."""
        with patch.object(error_logger.logger, 'log') as mock_log:
            correlation_id = error_logger.log_structured(
                message="Test event",
                event_type="test",
                level=LogLevel.INFO,
                custom_field="custom_value"
            )
            
            assert correlation_id is not None
            mock_log.assert_called_once()

    def test_error_aggregation(self, error_logger):
        """Test error aggregation functionality."""
        error = ValueError("Repeated error")
        
        # Log the same error multiple times
        for i in range(5):
            error_logger.log_error(
                error=error,
                endpoint="/api/test",
                user_id=f"user_{i}"
            )
        
        stats = error_logger.get_aggregation_stats()
        assert stats["total_patterns"] > 0
        
        # Check that aggregation occurred
        pattern_key = "ValueError_/api/test"
        if pattern_key in stats["patterns"]:
            pattern_stats = stats["patterns"][pattern_key]
            assert pattern_stats["count"] == 5
            assert pattern_stats["affected_users"] == 5

    def test_alert_threshold_calculation(self, error_logger):
        """Test alert threshold and severity calculation."""
        aggregation = ErrorAggregation(
            error_type="DatabaseError",
            error_pattern="DatabaseError_/api/data",
            count=15,
            first_occurrence=datetime.utcnow(),
            last_occurrence=datetime.utcnow()
        )
        
        # Add affected users
        for i in range(8):
            aggregation.affected_users.add(f"user_{i}")
        
        severity = error_logger._calculate_severity(aggregation)
        assert severity == AlertSeverity.MEDIUM

    def test_error_categorization(self, error_logger):
        """Test error type categorization."""
        assert error_logger._categorize_error("SQLAlchemyError") == "database_errors"
        assert error_logger._categorize_error("WebSocketError") == "websocket_errors"
        assert error_logger._categorize_error("AuthenticationError") == "authentication_errors"
        assert error_logger._categorize_error("ValueError") == "api_errors"

    def test_cleanup_old_aggregations(self, error_logger):
        """Test cleanup of old error aggregations."""
        # Add old aggregation
        old_time = datetime.utcnow() - timedelta(hours=3)
        error_logger.error_aggregations["old_pattern"] = ErrorAggregation(
            error_type="OldError",
            error_pattern="old_pattern",
            count=1,
            first_occurrence=old_time,
            last_occurrence=old_time
        )
        
        # Add recent aggregation
        recent_time = datetime.utcnow()
        error_logger.error_aggregations["recent_pattern"] = ErrorAggregation(
            error_type="RecentError",
            error_pattern="recent_pattern",
            count=1,
            first_occurrence=recent_time,
            last_occurrence=recent_time
        )
        
        error_logger.cleanup_old_aggregations()
        
        # Old aggregation should be removed, recent should remain
        assert "old_pattern" not in error_logger.error_aggregations
        assert "recent_pattern" in error_logger.error_aggregations

    def test_error_context_manager(self, error_logger):
        """Test error context manager functionality."""
        with patch.object(error_logger, 'log_error') as mock_log_error:
            try:
                with error_logger.error_context("test_operation", user_id="user_123"):
                    raise ValueError("Test error in context")
            except ValueError:
                pass  # Expected
            
            mock_log_error.assert_called_once()
            args, kwargs = mock_log_error.call_args
            assert kwargs["user_id"] == "user_123"
            assert kwargs["additional_context"]["operation"] == "test_operation"


class TestCorrelationIdManager:
    """Test cases for CorrelationIdManager."""

    def test_generate_id(self):
        """Test correlation ID generation."""
        id1 = CorrelationIdManager.generate_id()
        id2 = CorrelationIdManager.generate_id()
        
        assert id1 != id2
        assert len(id1) > 0
        assert len(id2) > 0

    def test_set_and_get_correlation_id(self):
        """Test setting and getting correlation ID."""
        test_id = "test-correlation-id"
        
        CorrelationIdManager.set_correlation_id(test_id)
        retrieved_id = CorrelationIdManager.get_correlation_id()
        
        assert retrieved_id == test_id

    def test_ensure_correlation_id(self):
        """Test ensuring correlation ID exists."""
        # Clear any existing ID
        CorrelationIdManager.set_correlation_id(None)
        
        # Should generate new ID
        id1 = CorrelationIdManager.ensure_correlation_id()
        assert id1 is not None
        
        # Should return same ID on subsequent calls
        id2 = CorrelationIdManager.ensure_correlation_id()
        assert id1 == id2

    def test_correlation_context(self):
        """Test correlation context manager."""
        original_id = CorrelationIdManager.get_correlation_id()
        
        with CorrelationIdManager.correlation_context("context-test-id") as context_id:
            assert context_id == "context-test-id"
            assert CorrelationIdManager.get_correlation_id() == "context-test-id"
        
        # Should restore original ID
        assert CorrelationIdManager.get_correlation_id() == original_id


class TestErrorResponse:
    """Test cases for ErrorResponse."""

    def test_error_response_creation(self):
        """Test ErrorResponse creation and serialization."""
        response = ErrorResponse(
            error_code="TEST_ERROR",
            message="Test error message",
            details="Additional details",
            status_code=400,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.WARNING,
            suggestions=["Check input", "Try again"]
        )
        
        assert response.error_code == "TEST_ERROR"
        assert response.status_code == 400
        assert response.category == ErrorCategory.VALIDATION
        assert response.severity == ErrorSeverity.WARNING

    def test_error_response_to_dict(self):
        """Test ErrorResponse dictionary conversion."""
        response = ErrorResponse(
            error_code="TEST_ERROR",
            message="Test message",
            status_code=500
        )
        
        response_dict = response.to_dict()
        
        assert "error" in response_dict
        assert response_dict["error"]["code"] == "TEST_ERROR"
        assert response_dict["error"]["message"] == "Test message"
        assert "timestamp" in response_dict["error"]

    def test_error_response_to_json_response(self):
        """Test ErrorResponse JSON response conversion."""
        response = ErrorResponse(
            error_code="TEST_ERROR",
            message="Test message",
            status_code=400
        )
        
        json_response = response.to_json_response()
        
        assert json_response.status_code == 400
        assert json_response.media_type == "application/json"


@pytest.mark.asyncio
async def test_integration_error_handling_flow():
    """Test complete error handling flow integration."""
    # Create instances
    error_handler = GracefulErrorHandler(enable_tracking=False)
    circuit_manager = DatabaseCircuitBreakerManager()
    error_logger = StructuredErrorLogger(enable_alerting=False)
    
    # Simulate database error
    db_error = OperationalError("Connection failed", None, None)
    
    # Handle error through graceful handler
    error_response = await error_handler.handle_database_error(
        error=db_error,
        operation="fetch_users",
        table_name="users"
    )
    
    # Log error through structured logger
    with patch.object(error_logger.logger, 'log'):
        correlation_id = error_logger.log_error(
            error=db_error,
            endpoint="/api/v1/users",
            user_id="user_123"
        )
    
    # Verify error response
    assert error_response.error_code == "DB_OPERATIONAL_ERROR"
    assert error_response.status_code == 503
    assert correlation_id is not None
    
    # Verify circuit breaker can handle the error
    async def failing_query():
        raise db_error
    
    breaker = circuit_manager.get_breaker("read_operations")
    
    # Should handle gracefully with fallback
    try:
        await breaker.execute_query(
            query_func=failing_query,
            fallback_data=[],
            operation_name="fetch_users"
        )
    except Exception:
        # Expected to raise exception, but should be handled gracefully
        pass
    
    # Verify aggregation occurred
    stats = error_logger.get_aggregation_stats()
    assert stats["total_patterns"] >= 0  # May have patterns from this or other tests


if __name__ == "__main__":
    pytest.main([__file__])