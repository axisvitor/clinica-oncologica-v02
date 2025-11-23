"""
Tests for BaseOrchestrator.

Tests database session management, logging, health checks, and metrics tracking.
Target: 90%+ code coverage.
"""

import pytest
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.orchestration.base.base_orchestrator import BaseOrchestrator


# ===============================
# Test Implementation
# ===============================


class TestOrchestrator(BaseOrchestrator):
    """Concrete implementation for testing."""

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute test logic."""
        return {"success": True, "context": context}

    def validate(self, context: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate test context."""
        if not context.get("required_field"):
            return False, "Missing required_field"
        return True, None


# ===============================
# Fixtures
# ===============================


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    db.execute = Mock(return_value=None)
    return db


@pytest.fixture
def orchestrator(mock_db):
    """Create test orchestrator instance."""
    return TestOrchestrator(db=mock_db, service_name="TestOrchestrator")


# ===============================
# Initialization Tests
# ===============================


def test_base_orchestrator_initialization(mock_db):
    """Test orchestrator initialization with default parameters."""
    orchestrator = TestOrchestrator(db=mock_db)

    assert orchestrator.db is mock_db
    assert orchestrator.service_name == "TestOrchestrator"
    assert orchestrator.logger is not None
    assert orchestrator.enable_health_checks is True
    assert orchestrator._execution_count == 0
    assert orchestrator._error_count == 0


def test_base_orchestrator_custom_service_name(mock_db):
    """Test orchestrator initialization with custom service name."""
    orchestrator = TestOrchestrator(
        db=mock_db,
        service_name="CustomService",
        enable_health_checks=False
    )

    assert orchestrator.service_name == "CustomService"
    assert orchestrator.enable_health_checks is False


# ===============================
# Abstract Method Tests
# ===============================


def test_abstract_methods_must_be_implemented():
    """Test that abstract methods raise NotImplementedError if not implemented."""

    class IncompleteOrchestrator(BaseOrchestrator):
        """Orchestrator missing abstract method implementations."""
        pass

    # Should not be able to instantiate without implementing abstract methods
    with pytest.raises(TypeError):
        IncompleteOrchestrator(db=Mock())


@pytest.mark.asyncio
async def test_execute_method(orchestrator):
    """Test execute method implementation."""
    context = {"required_field": "value"}
    result = await orchestrator.execute(context)

    assert result["success"] is True
    assert result["context"] == context


def test_validate_method(orchestrator):
    """Test validate method implementation."""
    # Valid context
    is_valid, error = orchestrator.validate({"required_field": "value"})
    assert is_valid is True
    assert error is None

    # Invalid context
    is_valid, error = orchestrator.validate({})
    assert is_valid is False
    assert error == "Missing required_field"


# ===============================
# Logging Tests
# ===============================


def test_log_info(orchestrator):
    """Test log_info method."""
    with patch.object(orchestrator.logger, "info") as mock_info:
        orchestrator.log_info("Test message", extra={"key": "value"})

        mock_info.assert_called_once()
        args, kwargs = mock_info.call_args
        assert "Test message" in args
        assert "service" in kwargs["extra"]
        assert "key" in kwargs["extra"]


def test_log_warning(orchestrator):
    """Test log_warning method."""
    with patch.object(orchestrator.logger, "warning") as mock_warning:
        orchestrator.log_warning("Warning message", extra={"level": "high"})

        mock_warning.assert_called_once()
        args, kwargs = mock_warning.call_args
        assert "Warning message" in args
        assert "service" in kwargs["extra"]


def test_log_error(orchestrator):
    """Test log_error method."""
    test_error = ValueError("Test error")

    with patch.object(orchestrator.logger, "error") as mock_error:
        orchestrator.log_error("Error occurred", test_error, extra={"context": "test"})

        mock_error.assert_called_once()
        args, kwargs = mock_error.call_args
        assert "Error occurred" in args
        assert kwargs["exc_info"] is True
        assert "error_type" in kwargs["extra"]
        assert kwargs["extra"]["error_type"] == "ValueError"


def test_log_error_tracks_error_count(orchestrator):
    """Test that log_error increments error count."""
    initial_count = orchestrator._error_count
    test_error = RuntimeError("Test")

    with patch.object(orchestrator.logger, "error"):
        orchestrator.log_error("Error", test_error)

    assert orchestrator._error_count == initial_count + 1


# ===============================
# Health Check Tests
# ===============================


@pytest.mark.asyncio
async def test_health_check_success(orchestrator):
    """Test health check with healthy database."""
    health = await orchestrator.health_check()

    assert health["service"] == "TestOrchestrator"
    assert health["overall_healthy"] is True
    assert "database" in health["components"]
    assert health["components"]["database"]["healthy"] is True
    assert "metrics" in health
    assert "timestamp" in health


@pytest.mark.asyncio
async def test_health_check_database_failure(orchestrator, mock_db):
    """Test health check with database failure."""
    mock_db.execute.side_effect = Exception("Database connection failed")

    health = await orchestrator.health_check()

    assert health["overall_healthy"] is False
    assert health["components"]["database"]["healthy"] is False
    assert "error" in health["components"]["database"]


@pytest.mark.asyncio
async def test_health_check_disabled(mock_db):
    """Test health check when disabled."""
    orchestrator = TestOrchestrator(db=mock_db, enable_health_checks=False)

    health = await orchestrator.health_check()

    assert health["healthy"] is True
    assert health["message"] == "Health checks disabled"


@pytest.mark.asyncio
async def test_health_check_includes_metrics(orchestrator):
    """Test that health check includes metrics."""
    orchestrator.track_execution()
    orchestrator.track_error()

    health = await orchestrator.health_check()

    assert health["metrics"]["execution_count"] == 1
    assert health["metrics"]["error_count"] == 1
    assert health["metrics"]["last_execution"] is not None


# ===============================
# Metrics Tracking Tests
# ===============================


def test_track_execution(orchestrator):
    """Test execution tracking."""
    initial_count = orchestrator._execution_count
    initial_time = orchestrator._last_execution_time

    orchestrator.track_execution()

    assert orchestrator._execution_count == initial_count + 1
    assert orchestrator._last_execution_time is not None
    assert orchestrator._last_execution_time != initial_time


def test_track_error(orchestrator):
    """Test error tracking."""
    initial_count = orchestrator._error_count
    initial_time = orchestrator._last_error_time

    orchestrator.track_error()

    assert orchestrator._error_count == initial_count + 1
    assert orchestrator._last_error_time is not None
    assert orchestrator._last_error_time != initial_time


def test_get_metrics(orchestrator):
    """Test get_metrics method."""
    orchestrator.track_execution()
    orchestrator.track_execution()
    orchestrator.track_error()

    metrics = orchestrator.get_metrics()

    assert metrics["service"] == "TestOrchestrator"
    assert metrics["execution_count"] == 2
    assert metrics["error_count"] == 1
    assert metrics["error_rate"] == 0.5


def test_get_metrics_zero_executions(orchestrator):
    """Test get_metrics with zero executions."""
    metrics = orchestrator.get_metrics()

    assert metrics["execution_count"] == 0
    assert metrics["error_count"] == 0
    assert metrics["error_rate"] == 0


def test_reset_metrics(orchestrator):
    """Test metrics reset."""
    orchestrator.track_execution()
    orchestrator.track_error()

    with patch.object(orchestrator, "log_info") as mock_log:
        orchestrator.reset_metrics()

        assert orchestrator._execution_count == 0
        assert orchestrator._error_count == 0
        assert orchestrator._last_execution_time is None
        assert orchestrator._last_error_time is None
        mock_log.assert_called_once_with("Metrics reset")


# ===============================
# Integration Tests
# ===============================


@pytest.mark.asyncio
async def test_full_execution_workflow(orchestrator):
    """Test full execution workflow with metrics tracking."""
    context = {"required_field": "test_value"}

    # Validate
    is_valid, error = orchestrator.validate(context)
    assert is_valid is True

    # Execute
    result = await orchestrator.execute(context)
    assert result["success"] is True

    # Track
    orchestrator.track_execution()

    # Verify metrics
    metrics = orchestrator.get_metrics()
    assert metrics["execution_count"] == 1
    assert metrics["error_rate"] == 0


@pytest.mark.asyncio
async def test_error_handling_workflow(orchestrator):
    """Test error handling workflow."""
    test_error = RuntimeError("Test error")

    with patch.object(orchestrator.logger, "error"):
        orchestrator.log_error("Operation failed", test_error)

    # Check error was tracked
    assert orchestrator._error_count == 1

    # Check health reflects error
    health = await orchestrator.health_check()
    assert health["metrics"]["error_count"] == 1
