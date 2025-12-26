"""
Unit tests for Audit Logger utility.
Verifies structured audit logging functionality.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.utils.audit_logger import AuditLogger, AuditAction


class TestAuditLogger:
    """Test suite for AuditLogger class."""

    @patch("app.utils.audit_logger.logger")
    def test_log_basic_action(self, mock_logger):
        """Test basic audit log entry."""
        AuditLogger.log(
            action=AuditAction.CREATE,
            resource_type="flow_template",
            resource_id="test-123",
            user_id="user-456",
            user_role="admin",
        )

        # Verify logger was called
        assert mock_logger.log.called
        call_args = mock_logger.log.call_args

        # Verify log level is INFO
        assert call_args[0][0] == 20  # logging.INFO

        # Verify audit_data in extra
        assert "audit_data" in call_args[1]["extra"]
        audit_data = call_args[1]["extra"]["audit_data"]

        assert audit_data["action"] == "create"
        assert audit_data["resource_type"] == "flow_template"
        assert audit_data["resource_id"] == "test-123"
        assert audit_data["user_id"] == "user-456"
        assert audit_data["user_role"] == "admin"
        assert audit_data["success"] is True

    @patch("app.utils.audit_logger.logger")
    def test_log_with_details(self, mock_logger):
        """Test audit log with additional details."""
        details = {
            "template_name": "Onboarding Flow",
            "version": 1,
            "changes": ["name", "description"],
        }

        AuditLogger.log(
            action=AuditAction.UPDATE,
            resource_type="flow_template",
            resource_id="test-123",
            user_id="user-456",
            details=details,
        )

        call_args = mock_logger.log.call_args
        audit_data = call_args[1]["extra"]["audit_data"]

        assert audit_data["details"] == details

    @patch("app.utils.audit_logger.logger")
    def test_log_with_ip_address(self, mock_logger):
        """Test audit log with IP address tracking."""
        AuditLogger.log(
            action=AuditAction.DELETE,
            resource_type="quiz_template",
            resource_id="test-789",
            user_id="user-456",
            ip_address="192.168.1.100",
        )

        call_args = mock_logger.log.call_args
        audit_data = call_args[1]["extra"]["audit_data"]

        assert audit_data["ip_address"] == "192.168.1.100"

    @patch("app.utils.audit_logger.logger")
    def test_log_failed_action(self, mock_logger):
        """Test logging failed operations."""
        AuditLogger.log(
            action=AuditAction.UPDATE,
            resource_type="flow_template",
            resource_id="test-123",
            user_id="user-456",
            success=False,
            error_message="Permission denied",
        )

        call_args = mock_logger.log.call_args

        # Verify log level is WARNING for failures
        assert call_args[0][0] == 30  # logging.WARNING

        audit_data = call_args[1]["extra"]["audit_data"]
        assert audit_data["success"] is False
        assert audit_data["error_message"] == "Permission denied"

    @patch("app.utils.audit_logger.logger")
    def test_log_batch_operation(self, mock_logger):
        """Test batch operation logging."""
        resource_ids = ["id-1", "id-2", "id-3"]

        AuditLogger.log_batch(
            action=AuditAction.ARCHIVE,
            resource_type="flow_template",
            resource_ids=resource_ids,
            user_id="user-456",
            user_role="admin",
        )

        assert mock_logger.info.called
        call_args = mock_logger.info.call_args

        audit_data = call_args[1]["extra"]["audit_data"]
        assert audit_data["resource_ids"] == resource_ids
        assert audit_data["resource_count"] == 3

    @patch("app.utils.audit_logger.logger")
    def test_log_access(self, mock_logger):
        """Test access logging for sensitive resources."""
        AuditLogger.log_access(
            resource_type="patient_data",
            resource_id="patient-123",
            user_id="doctor-456",
            user_role="doctor",
            access_type="view",
            ip_address="192.168.1.1",
        )

        call_args = mock_logger.log.call_args
        audit_data = call_args[1]["extra"]["audit_data"]

        assert audit_data["action"] == "read"
        assert audit_data["details"]["access_type"] == "view"

    @patch("app.utils.audit_logger.logger")
    def test_log_security_event(self, mock_logger):
        """Test security event logging."""
        AuditLogger.log_security_event(
            event_type="permission_denied",
            user_id="user-123",
            details={"attempted_action": "delete", "resource": "template-456"},
            ip_address="192.168.1.1",
            severity="high",
        )

        call_args = mock_logger.log.call_args

        # Verify log level is WARNING for high severity
        assert call_args[0][0] == 30  # logging.WARNING

        security_event = call_args[1]["extra"]["security_event"]
        assert security_event["event_type"] == "permission_denied"
        assert security_event["severity"] == "high"

    @patch("app.utils.audit_logger.logger")
    def test_all_audit_actions(self, mock_logger):
        """Test all audit action types."""
        actions = [
            AuditAction.CREATE,
            AuditAction.UPDATE,
            AuditAction.DELETE,
            AuditAction.READ,
            AuditAction.PUBLISH,
            AuditAction.ARCHIVE,
            AuditAction.DUPLICATE,
            AuditAction.ROLLBACK,
            AuditAction.SEARCH,
            AuditAction.VALIDATE,
        ]

        for action in actions:
            AuditLogger.log(
                action=action,
                resource_type="test",
                resource_id="test-id",
                user_id="user-id",
            )

            call_args = mock_logger.log.call_args
            audit_data = call_args[1]["extra"]["audit_data"]
            assert audit_data["action"] == action.value

    @patch("app.utils.audit_logger.logger")
    def test_timestamp_format(self, mock_logger):
        """Test that timestamp is in ISO format."""
        AuditLogger.log(
            action=AuditAction.CREATE,
            resource_type="test",
            resource_id="test-id",
            user_id="user-id",
        )

        call_args = mock_logger.log.call_args
        audit_data = call_args[1]["extra"]["audit_data"]

        # Verify timestamp is present and follows ISO format
        assert "timestamp" in audit_data
        timestamp = audit_data["timestamp"]
        assert "T" in timestamp  # ISO format includes 'T'
        assert timestamp.endswith("Z") or "+" in timestamp  # Timezone info
