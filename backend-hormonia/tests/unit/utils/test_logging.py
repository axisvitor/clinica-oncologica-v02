"""
Comprehensive tests for logging utilities.
"""
import pytest
import logging
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.utils.logging import (
    StructuredFormatter, HealthCheckFilter, SensitiveDataFilter,
    LoggerAdapter, get_logger, log_function_call, log_database_operation,
    log_external_api_call, log_business_event, log_security_event,
    log_performance_metric, setup_logging
)


class TestStructuredFormatter:
    """Test StructuredFormatter functionality."""

    def test_add_fields_basic(self):
        """Test basic field addition."""
        formatter = StructuredFormatter()
        log_record = {}
        record = Mock(spec=logging.LogRecord)
        record.levelname = "INFO"
        record.name = "test.logger"
        record.thread = 12345
        record.process = 6789
        record.exc_info = None

        formatter.add_fields(log_record, record, {})

        assert log_record["service"] == "hormonia-backend"
        assert log_record["level"] == "INFO"
        assert log_record["logger"] == "test.logger"
        assert log_record["thread_id"] == 12345
        assert log_record["process_id"] == 6789
        assert "timestamp" in log_record

    def test_add_fields_with_request_context(self):
        """Test field addition with request context."""
        formatter = StructuredFormatter()
        log_record = {}
        record = Mock(spec=logging.LogRecord)
        record.levelname = "INFO"
        record.name = "test.logger"
        record.thread = 12345
        record.process = 6789
        record.exc_info = None
        record.request_id = "req-123"
        record.user_id = "user-456"
        record.patient_id = "patient-789"
        record.correlation_id = "corr-abc"

        formatter.add_fields(log_record, record, {})

        assert log_record["request_id"] == "req-123"
        assert log_record["user_id"] == "user-456"
        assert log_record["patient_id"] == "patient-789"
        assert log_record["correlation_id"] == "corr-abc"

    def test_add_fields_with_exception(self):
        """Test field addition with exception information."""
        formatter = StructuredFormatter()
        log_record = {}
        record = Mock(spec=logging.LogRecord)
        record.levelname = "ERROR"
        record.name = "test.logger"
        record.thread = 12345
        record.process = 6789

        # Mock exception info
        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys
            record.exc_info = sys.exc_info()

        formatter.add_fields(log_record, record, {})

        assert "exception" in log_record
        assert log_record["exception"]["type"] == "ValueError"
        assert "Test exception" in log_record["exception"]["message"]
        assert isinstance(log_record["exception"]["traceback"], list)


class TestHealthCheckFilter:
    """Test HealthCheckFilter functionality."""

    def test_filter_health_check_in_message(self):
        """Test filtering health check requests."""
        filter_instance = HealthCheckFilter()
        record = Mock(spec=logging.LogRecord)
        record.getMessage.return_value = "GET /health - 200"

        result = filter_instance.filter(record)
        assert result is False

    def test_filter_health_check_keyword(self):
        """Test filtering health check keyword."""
        filter_instance = HealthCheckFilter()
        record = Mock(spec=logging.LogRecord)
        record.getMessage.return_value = "health_check completed successfully"

        result = filter_instance.filter(record)
        assert result is False

    def test_filter_normal_message(self):
        """Test filtering normal messages."""
        filter_instance = HealthCheckFilter()
        record = Mock(spec=logging.LogRecord)
        record.getMessage.return_value = "User authenticated successfully"

        result = filter_instance.filter(record)
        assert result is True

    def test_filter_message_error(self):
        """Test filter with getMessage error."""
        filter_instance = HealthCheckFilter()
        record = Mock(spec=logging.LogRecord)
        record.getMessage.side_effect = ValueError("Format error")

        result = filter_instance.filter(record)
        assert result is True  # Should allow through on error


class TestSensitiveDataFilter:
    """Test SensitiveDataFilter functionality."""

    def test_filter_dict_in_args(self):
        """Test filtering dictionary in args."""
        filter_instance = SensitiveDataFilter()
        record = Mock(spec=logging.LogRecord)
        record.args = ({"password": "secret123", "username": "user"},)
        record.msg = "Login attempt: %s"

        filter_instance.filter(record)

        filtered_dict = record.args[0]
        assert filtered_dict["password"] == "[REDACTED]"
        assert filtered_dict["username"] == "user"

    def test_filter_string_in_args(self):
        """Test filtering string in args."""
        filter_instance = SensitiveDataFilter()
        record = Mock(spec=logging.LogRecord)
        record.args = ("Bearer jwt.token.here",)
        record.msg = "Token: %s"

        filter_instance.filter(record)

        filtered_string = record.args[0]
        assert "Bearer [REDACTED]" in filtered_string

    def test_filter_message(self):
        """Test filtering message content."""
        filter_instance = SensitiveDataFilter()
        record = Mock(spec=logging.LogRecord)
        record.args = ()
        record.msg = "API key: sk-1234567890 used for request"

        filter_instance.filter(record)

        assert "api_key: [REDACTED]" in record.msg

    def test_filter_nested_dict(self):
        """Test filtering nested dictionary."""
        filter_instance = SensitiveDataFilter()
        data = {
            "config": {
                "token": "secret123",
                "normal": "value"
            },
            "list": [
                {"password": "hidden", "name": "test"}
            ]
        }

        result = filter_instance._filter_dict(data)

        assert result["config"]["token"] == "[REDACTED]"
        assert result["config"]["normal"] == "value"
        assert result["list"][0]["password"] == "[REDACTED]"
        assert result["list"][0]["name"] == "test"

    def test_filter_jwt_token_string(self):
        """Test filtering JWT tokens from strings."""
        filter_instance = SensitiveDataFilter()
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature"

        result = filter_instance._filter_string(text)

        assert "Bearer [REDACTED]" in result
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result

    def test_filter_password_string(self):
        """Test filtering passwords from strings."""
        filter_instance = SensitiveDataFilter()
        text = "Login with password: mysecret123"

        result = filter_instance._filter_string(text)

        assert "password: [REDACTED]" in result
        assert "mysecret123" not in result

    def test_filter_error_handling(self):
        """Test filter error handling."""
        filter_instance = SensitiveDataFilter()
        record = Mock(spec=logging.LogRecord)
        record.args = None  # This might cause an error
        record.msg = None

        # Should not raise exception
        result = filter_instance.filter(record)
        assert result is True


class TestLoggerAdapter:
    """Test LoggerAdapter functionality."""

    def test_init_with_extra(self):
        """Test adapter initialization with extra context."""
        logger = Mock(spec=logging.Logger)
        extra = {"user_id": "123", "request_id": "req-456"}

        adapter = LoggerAdapter(logger, extra)

        assert adapter.logger == logger
        assert adapter.extra == extra

    def test_init_without_extra(self):
        """Test adapter initialization without extra context."""
        logger = Mock(spec=logging.Logger)

        adapter = LoggerAdapter(logger)

        assert adapter.logger == logger
        assert adapter.extra == {}

    def test_process_message(self):
        """Test message processing with context."""
        logger = Mock(spec=logging.Logger)
        extra = {"user_id": "123"}
        adapter = LoggerAdapter(logger, extra)

        msg, kwargs = adapter.process("Test message", {})

        assert msg == "Test message"
        assert kwargs["extra"]["user_id"] == "123"

    def test_process_message_with_existing_extra(self):
        """Test message processing with existing extra in kwargs."""
        logger = Mock(spec=logging.Logger)
        extra = {"user_id": "123"}
        adapter = LoggerAdapter(logger, extra)

        msg, kwargs = adapter.process("Test message", {"extra": {"request_id": "req-456"}})

        assert msg == "Test message"
        assert kwargs["extra"]["user_id"] == "123"
        assert kwargs["extra"]["request_id"] == "req-456"

    def test_with_context(self):
        """Test creating adapter with additional context."""
        logger = Mock(spec=logging.Logger)
        extra = {"user_id": "123"}
        adapter = LoggerAdapter(logger, extra)

        new_adapter = adapter.with_context(request_id="req-456", session_id="sess-789")

        assert new_adapter.extra["user_id"] == "123"
        assert new_adapter.extra["request_id"] == "req-456"
        assert new_adapter.extra["session_id"] == "sess-789"
        assert new_adapter.logger == logger


class TestGetLogger:
    """Test get_logger function."""

    @patch('app.utils.logging.logging.getLogger')
    def test_get_logger_basic(self, mock_get_logger):
        """Test basic logger creation."""
        mock_logger = Mock(spec=logging.Logger)
        mock_get_logger.return_value = mock_logger

        result = get_logger("test.module")

        assert isinstance(result, LoggerAdapter)
        assert result.logger == mock_logger
        mock_get_logger.assert_called_once_with("test.module")

    @patch('app.utils.logging.logging.getLogger')
    def test_get_logger_with_context(self, mock_get_logger):
        """Test logger creation with context."""
        mock_logger = Mock(spec=logging.Logger)
        mock_get_logger.return_value = mock_logger

        result = get_logger("test.module", user_id="123", request_id="req-456")

        assert isinstance(result, LoggerAdapter)
        assert result.extra["user_id"] == "123"
        assert result.extra["request_id"] == "req-456"


class TestLoggingHelpers:
    """Test logging helper functions."""

    @patch('app.utils.logging.logging.getLogger')
    def test_log_function_call(self, mock_get_logger):
        """Test function call logging."""
        mock_logger = Mock(spec=logging.Logger)
        mock_get_logger.return_value = mock_logger

        log_function_call("test_function", args=("arg1", "arg2"), kwargs={"key": "value"})

        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args
        assert "Function call: test_function" in call_args[0][0]
        assert call_args[1]["extra"]["function"] == "test_function"

    def test_log_function_call_with_logger(self):
        """Test function call logging with provided logger."""
        mock_logger = Mock(spec=logging.Logger)

        log_function_call("test_function", logger=mock_logger)

        mock_logger.debug.assert_called_once()

    @patch('app.utils.logging.SensitiveDataFilter')
    def test_log_function_call_sensitive_data(self, mock_filter_class):
        """Test function call logging with sensitive data filtering."""
        mock_filter = Mock()
        mock_filter._filter_dict.return_value = {"password": "[REDACTED]", "user": "test"}
        mock_filter_class.return_value = mock_filter

        mock_logger = Mock(spec=logging.Logger)

        log_function_call("test_function", kwargs={"password": "secret", "user": "test"}, logger=mock_logger)

        mock_filter._filter_dict.assert_called_once_with({"password": "secret", "user": "test"})

    @patch('app.utils.logging.logging.getLogger')
    def test_log_database_operation(self, mock_get_logger):
        """Test database operation logging."""
        mock_logger = Mock(spec=logging.Logger)
        mock_get_logger.return_value = mock_logger

        log_database_operation("INSERT", "users", record_id="123", duration=0.05)

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "Database INSERT: users" in call_args[0][0]
        assert call_args[1]["extra"]["operation"] == "INSERT"
        assert call_args[1]["extra"]["table"] == "users"
        assert call_args[1]["extra"]["record_id"] == "123"
        assert call_args[1]["extra"]["duration_ms"] == 50.0

    @patch('app.utils.logging.logging.getLogger')
    def test_log_external_api_call(self, mock_get_logger):
        """Test external API call logging."""
        mock_logger = Mock(spec=logging.Logger)
        mock_get_logger.return_value = mock_logger

        log_external_api_call("firebase", "/auth/verify", "POST", status_code=200, duration=0.1)

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "External API call: firebase POST /auth/verify" in call_args[0][0]
        assert call_args[1]["extra"]["service"] == "firebase"
        assert call_args[1]["extra"]["status_code"] == 200

    @patch('app.utils.logging.logging.getLogger')
    def test_log_business_event(self, mock_get_logger):
        """Test business event logging."""
        mock_logger = Mock(spec=logging.Logger)
        mock_get_logger.return_value = mock_logger

        log_business_event("user_registered", "New user created account",
                          entity_id="user-123", user_id="123",
                          metadata={"source": "web"})

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "Business event: user_registered" in call_args[0][0]
        assert call_args[1]["extra"]["business_event_type"] == "user_registered"
        assert call_args[1]["extra"]["metadata"]["source"] == "web"

    @patch('app.utils.logging.logging.getLogger')
    def test_log_security_event(self, mock_get_logger):
        """Test security event logging."""
        mock_logger = Mock(spec=logging.Logger)
        mock_get_logger.return_value = mock_logger

        log_security_event("login_failed", "Invalid credentials provided",
                          user_id="123", ip_address="192.168.1.1",
                          user_agent="Mozilla/5.0", severity="WARNING")

        mock_logger.log.assert_called_once()
        call_args = mock_logger.log.call_args
        assert call_args[0][0] == logging.WARNING  # Log level
        assert "Security event: login_failed" in call_args[0][1]
        assert call_args[0][2]["extra"]["security_event_type"] == "login_failed"
        assert call_args[0][2]["extra"]["ip_address"] == "192.168.1.1"

    @patch('app.utils.logging.logging.getLogger')
    def test_log_performance_metric(self, mock_get_logger):
        """Test performance metric logging."""
        mock_logger = Mock(spec=logging.Logger)
        mock_get_logger.return_value = mock_logger

        log_performance_metric("api_response_time", 150.5, unit="ms",
                              tags={"endpoint": "/api/users", "method": "GET"})

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "Performance metric: api_response_time = 150.5ms" in call_args[0][0]
        assert call_args[1]["extra"]["metric_name"] == "api_response_time"
        assert call_args[1]["extra"]["value"] == 150.5
        assert call_args[1]["extra"]["tags"]["endpoint"] == "/api/users"


class TestSetupLogging:
    """Test setup_logging function."""

    @patch('app.utils.logging.logging.basicConfig')
    @patch('app.utils.logging.logging.getLogger')
    def test_setup_logging(self, mock_get_logger, mock_basic_config):
        """Test logging setup."""
        mock_loggers = {}

        def mock_logger_factory(name):
            if name not in mock_loggers:
                mock_loggers[name] = Mock(spec=logging.Logger)
            return mock_loggers[name]

        mock_get_logger.side_effect = mock_logger_factory

        setup_logging()

        # Check basic config was called
        mock_basic_config.assert_called_once()
        call_args = mock_basic_config.call_args
        assert call_args[1]["level"] == logging.INFO

        # Check specific loggers were configured
        assert "uvicorn" in mock_loggers
        assert "sqlalchemy.engine" in mock_loggers
        assert "celery" in mock_loggers