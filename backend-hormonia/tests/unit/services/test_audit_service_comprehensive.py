"""
Comprehensive unit tests for AuditService (audit_service.py).

Tests all methods in audit_service.py to achieve 100% code coverage including:
- log_event() with all parameters and edge cases
- All specific logging methods (monthly quiz, AI, LGPD compliance)
- Query and reporting methods
- Error handling and edge cases
- Database operations and transactions
- Metadata sanitization and security
- Performance edge cases

Coverage target: 100% of audit_service.py
"""

import pytest
import hashlib
import json
import logging
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, call, PropertyMock
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4

# Import the service under test and dependencies
from app.services.audit_service import AuditService
from app.models.audit_log import AuditLog
from app.utils.security import mask_sensitive_url, mask_dict_secrets


class TestAuditServiceInit:
    """Test AuditService initialization."""

    def test_init_basic(self):
        """Test basic initialization."""
        mock_db = Mock(spec=Session)
        service = AuditService(mock_db)

        assert service.db is mock_db
        assert service.logger is not None
        assert isinstance(service.logger, logging.Logger)

    def test_init_logger_name(self):
        """Test logger has correct name."""
        mock_db = Mock(spec=Session)
        service = AuditService(mock_db)

        assert service.logger.name == "app.services.audit_service"


class TestLogEventMethod:
    """Test the core log_event method comprehensively."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session = Mock(spec=Session)
        session.add = Mock()
        session.commit = Mock()
        return session

    @pytest.fixture
    def audit_service(self, mock_db_session):
        """AuditService instance with mocked database."""
        return AuditService(mock_db_session)

    @pytest.fixture
    def sample_uuid(self):
        """Sample UUID for testing."""
        return uuid4()

    def test_log_event_minimal_params(self, audit_service, mock_db_session):
        """Test log_event with minimal parameters."""
        with patch('app.services.audit_service.datetime') as mock_datetime, \
             patch('app.services.audit_service.mask_dict_secrets') as mock_mask:

            fixed_now = datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.utcnow.return_value = fixed_now
            mock_mask.return_value = {}

            result = audit_service.log_event(
                event_type="test_event",
                event_category="test"
            )

            # Verify database operations
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()

            # Verify audit log object creation
            added_audit_log = mock_db_session.add.call_args[0][0]
            assert isinstance(added_audit_log, AuditLog)
            assert added_audit_log.event_type == "test_event"
            assert added_audit_log.event_category == "test"
            assert added_audit_log.severity == "info"  # default
            assert added_audit_log.result == "success"  # default
            assert added_audit_log.retention_until == fixed_now + timedelta(days=365)

    def test_log_event_all_params(self, audit_service, mock_db_session, sample_uuid):
        """Test log_event with all parameters provided."""
        with patch('app.services.audit_service.datetime') as mock_datetime, \
             patch('app.services.audit_service.mask_dict_secrets') as mock_mask:

            fixed_now = datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.utcnow.return_value = fixed_now
            mock_mask.return_value = {"sanitized": "data"}

            event_data = {"key": "value", "password": "secret"}
            actor_id = sample_uuid
            subject_id = uuid4()
            session_id = uuid4()
            data_subject_id = uuid4()

            result = audit_service.log_event(
                event_type="comprehensive_test",
                event_category="access",
                severity="warning",
                actor_id=actor_id,
                subject_id=subject_id,
                session_id=session_id,
                ip_address="192.168.1.100",
                user_agent="Mozilla/5.0 Test Browser",
                event_data=event_data,
                result="failure",
                data_subject_id=data_subject_id,
                legal_basis="consent",
                retention_days=90
            )

            # Verify mask_dict_secrets was called
            mock_mask.assert_called_once_with(event_data)

            # Verify audit log object
            added_audit_log = mock_db_session.add.call_args[0][0]
            assert added_audit_log.event_type == "comprehensive_test"
            assert added_audit_log.event_category == "access"
            assert added_audit_log.severity == "warning"
            assert added_audit_log.actor_id == str(actor_id)
            assert added_audit_log.subject_id == str(subject_id)
            assert added_audit_log.session_id == str(session_id)
            assert added_audit_log.ip_address == "192.168.1.100"
            assert added_audit_log.user_agent == "Mozilla/5.0 Test Browser"
            assert added_audit_log.event_data == {"sanitized": "data"}
            assert added_audit_log.result == "failure"
            assert added_audit_log.data_subject_id == str(data_subject_id)
            assert added_audit_log.legal_basis == "consent"
            assert added_audit_log.retention_until == fixed_now + timedelta(days=90)

    def test_log_event_backward_compatibility(self, audit_service, mock_db_session):
        """Test backward compatibility with legacy user_id and patient_id parameters."""
        with patch('app.services.audit_service.datetime') as mock_datetime, \
             patch('app.services.audit_service.mask_dict_secrets') as mock_mask:

            mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 12, 0, 0)
            mock_mask.return_value = {}

            user_id = uuid4()
            patient_id = uuid4()

            result = audit_service.log_event(
                event_type="legacy_test",
                event_category="test",
                user_id=user_id,
                patient_id=patient_id
            )

            added_audit_log = mock_db_session.add.call_args[0][0]
            # Legacy parameters should map to new ones
            assert added_audit_log.actor_id == str(user_id)
            assert added_audit_log.subject_id == str(patient_id)
            # Legacy fields should also be set
            assert added_audit_log.user_id == str(user_id)
            assert added_audit_log.patient_id == str(patient_id)

    def test_log_event_backward_compatibility_precedence(self, audit_service, mock_db_session):
        """Test that new parameters take precedence over legacy ones."""
        with patch('app.services.audit_service.datetime') as mock_datetime, \
             patch('app.services.audit_service.mask_dict_secrets') as mock_mask:

            mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 12, 0, 0)
            mock_mask.return_value = {}

            new_actor_id = uuid4()
            new_subject_id = uuid4()
            legacy_user_id = uuid4()
            legacy_patient_id = uuid4()

            result = audit_service.log_event(
                event_type="precedence_test",
                event_category="test",
                actor_id=new_actor_id,
                subject_id=new_subject_id,
                user_id=legacy_user_id,
                patient_id=legacy_patient_id
            )

            added_audit_log = mock_db_session.add.call_args[0][0]
            # New parameters should take precedence
            assert added_audit_log.actor_id == str(new_actor_id)
            assert added_audit_log.subject_id == str(new_subject_id)
            # Legacy fields should still be set from legacy parameters
            assert added_audit_log.user_id == str(legacy_user_id)
            assert added_audit_log.patient_id == str(legacy_patient_id)

    def test_log_event_user_agent_truncation(self, audit_service, mock_db_session):
        """Test user agent string truncation at 500 characters."""
        with patch('app.services.audit_service.datetime') as mock_datetime, \
             patch('app.services.audit_service.mask_dict_secrets') as mock_mask:

            mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 12, 0, 0)
            mock_mask.return_value = {}

            long_user_agent = "A" * 600  # Longer than 500 chars

            result = audit_service.log_event(
                event_type="truncation_test",
                event_category="test",
                user_agent=long_user_agent
            )

            added_audit_log = mock_db_session.add.call_args[0][0]
            assert len(added_audit_log.user_agent) == 500
            assert added_audit_log.user_agent == "A" * 500

    def test_log_event_user_agent_none(self, audit_service, mock_db_session):
        """Test user agent None handling."""
        with patch('app.services.audit_service.datetime') as mock_datetime, \
             patch('app.services.audit_service.mask_dict_secrets') as mock_mask:

            mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 12, 0, 0)
            mock_mask.return_value = {}

            result = audit_service.log_event(
                event_type="none_user_agent_test",
                event_category="test",
                user_agent=None
            )

            added_audit_log = mock_db_session.add.call_args[0][0]
            assert added_audit_log.user_agent is None

    def test_log_event_empty_event_data(self, audit_service, mock_db_session):
        """Test handling of None and empty event_data."""
        with patch('app.services.audit_service.datetime') as mock_datetime, \
             patch('app.services.audit_service.mask_dict_secrets') as mock_mask:

            mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 12, 0, 0)
            mock_mask.return_value = {}

            # Test with None event_data
            result = audit_service.log_event(
                event_type="none_data_test",
                event_category="test",
                event_data=None
            )

            mock_mask.assert_called_once_with({})  # Should pass empty dict

            added_audit_log = mock_db_session.add.call_args[0][0]
            assert added_audit_log.event_data == {}

    def test_log_event_uuid_string_conversion(self, audit_service, mock_db_session):
        """Test UUID to string conversion for all UUID fields."""
        with patch('app.services.audit_service.datetime') as mock_datetime, \
             patch('app.services.audit_service.mask_dict_secrets') as mock_mask:

            mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 12, 0, 0)
            mock_mask.return_value = {}

            actor_id = uuid4()
            subject_id = uuid4()
            session_id = uuid4()
            data_subject_id = uuid4()
            user_id = uuid4()
            patient_id = uuid4()

            result = audit_service.log_event(
                event_type="uuid_conversion_test",
                event_category="test",
                actor_id=actor_id,
                subject_id=subject_id,
                session_id=session_id,
                data_subject_id=data_subject_id,
                user_id=user_id,
                patient_id=patient_id
            )

            added_audit_log = mock_db_session.add.call_args[0][0]
            assert added_audit_log.actor_id == str(actor_id)
            assert added_audit_log.subject_id == str(subject_id)
            assert added_audit_log.session_id == str(session_id)
            assert added_audit_log.data_subject_id == str(data_subject_id)
            assert added_audit_log.user_id == str(user_id)
            assert added_audit_log.patient_id == str(patient_id)

    def test_log_event_none_uuids(self, audit_service, mock_db_session):
        """Test None UUID handling."""
        with patch('app.services.audit_service.datetime') as mock_datetime, \
             patch('app.services.audit_service.mask_dict_secrets') as mock_mask:

            mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 12, 0, 0)
            mock_mask.return_value = {}

            result = audit_service.log_event(
                event_type="none_uuids_test",
                event_category="test",
                actor_id=None,
                subject_id=None,
                session_id=None,
                data_subject_id=None
            )

            added_audit_log = mock_db_session.add.call_args[0][0]
            assert added_audit_log.actor_id is None
            assert added_audit_log.subject_id is None
            assert added_audit_log.session_id is None
            assert added_audit_log.data_subject_id is None

    def test_log_event_logger_call(self, audit_service, mock_db_session):
        """Test that application logger is called with correct information."""
        with patch('app.services.audit_service.datetime') as mock_datetime, \
             patch('app.services.audit_service.mask_dict_secrets') as mock_mask, \
             patch.object(audit_service, 'logger') as mock_logger:

            mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 12, 0, 0)
            mock_mask.return_value = {}

            # Mock the AuditLog to have an id attribute after creation
            mock_audit_log = Mock(spec=AuditLog)
            mock_audit_log.id = uuid4()

            with patch('app.services.audit_service.AuditLog', return_value=mock_audit_log):
                actor_id = uuid4()
                subject_id = uuid4()

                result = audit_service.log_event(
                    event_type="logger_test",
                    event_category="access",
                    severity="warning",
                    actor_id=actor_id,
                    subject_id=subject_id,
                    result="blocked"
                )

                # Verify logger.info was called with correct parameters
                mock_logger.info.assert_called_once_with(
                    "Audit: logger_test",
                    extra={
                        'audit_id': mock_audit_log.id,
                        'category': 'access',
                        'severity': 'warning',
                        'result': 'blocked',
                        'actor_id': str(actor_id),
                        'subject_id': str(subject_id)
                    }
                )


class TestSpecificLoggingMethods:
    """Test all specific logging methods (monthly quiz related)."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session = Mock(spec=Session)
        session.add = Mock()
        session.commit = Mock()
        return session

    @pytest.fixture
    def audit_service(self, mock_db_session):
        """AuditService instance with mocked database."""
        return AuditService(mock_db_session)

    @pytest.fixture
    def sample_uuids(self):
        """Sample UUIDs for testing."""
        return {
            'actor_id': uuid4(),
            'patient_id': uuid4(),
            'session_id': uuid4(),
            'response_id': uuid4()
        }

    def test_log_link_created(self, audit_service, mock_db_session, sample_uuids):
        """Test log_link_created method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            expires_at = datetime.utcnow() + timedelta(hours=24)

            result = audit_service.log_link_created(
                actor_id=sample_uuids['actor_id'],
                patient_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                delivery_method="email",
                expires_at=expires_at,
                ip_address="192.168.1.1",
                user_agent="Test Browser"
            )

            mock_log_event.assert_called_once_with(
                event_type="monthly_quiz_link_created",
                event_category="access",
                severity="info",
                actor_id=sample_uuids['actor_id'],
                subject_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                ip_address="192.168.1.1",
                user_agent="Test Browser",
                event_data={
                    "delivery_method": "email",
                    "expires_at": expires_at.isoformat()
                },
                result="success",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="legitimate_interest"
            )

    def test_log_link_accessed(self, audit_service, mock_db_session, sample_uuids):
        """Test log_link_accessed method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_link_accessed(
                patient_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                ip_address="10.0.0.1",
                user_agent="Mobile Browser",
                token_prefix="abc123"
            )

            mock_log_event.assert_called_once_with(
                event_type="monthly_quiz_link_accessed",
                event_category="access",
                severity="info",
                subject_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                ip_address="10.0.0.1",
                user_agent="Mobile Browser",
                event_data={
                    "token_prefix": "abc123"
                },
                result="success",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="consent"
            )

    def test_log_response_submitted(self, audit_service, mock_db_session, sample_uuids):
        """Test log_response_submitted method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_response_submitted(
                patient_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                question_id="q_001",
                response_id=sample_uuids['response_id'],
                ip_address="172.16.0.1",
                user_agent="Chrome"
            )

            mock_log_event.assert_called_once_with(
                event_type="monthly_quiz_response_submitted",
                event_category="data_change",
                severity="info",
                subject_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                ip_address="172.16.0.1",
                user_agent="Chrome",
                event_data={
                    "question_id": "q_001",
                    "response_id": str(sample_uuids['response_id'])
                },
                result="success",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="consent"
            )

    def test_log_invalid_access_attempt(self, audit_service, mock_db_session):
        """Test log_invalid_access_attempt method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_invalid_access_attempt(
                ip_address="192.168.1.100",
                user_agent="Suspicious Bot",
                reason="Invalid token signature",
                token_prefix="xyz789"
            )

            mock_log_event.assert_called_once_with(
                event_type="monthly_quiz_invalid_access",
                event_category="security",
                severity="warning",
                ip_address="192.168.1.100",
                user_agent="Suspicious Bot",
                event_data={
                    "reason": "Invalid token signature",
                    "token_prefix": "xyz789"
                },
                result="blocked"
            )

    def test_log_invalid_access_attempt_no_token_prefix(self, audit_service, mock_db_session):
        """Test log_invalid_access_attempt with no token prefix."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_invalid_access_attempt(
                ip_address="192.168.1.100",
                user_agent="Suspicious Bot",
                reason="No token provided"
            )

            expected_event_data = {
                "reason": "No token provided",
                "token_prefix": None
            }

            mock_log_event.assert_called_once_with(
                event_type="monthly_quiz_invalid_access",
                event_category="security",
                severity="warning",
                ip_address="192.168.1.100",
                user_agent="Suspicious Bot",
                event_data=expected_event_data,
                result="blocked"
            )

    def test_log_token_expired(self, audit_service, mock_db_session, sample_uuids):
        """Test log_token_expired method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_token_expired(
                patient_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id']
            )

            mock_log_event.assert_called_once_with(
                event_type="monthly_quiz_token_expired",
                event_category="security",
                severity="info",
                subject_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                result="expired"
            )

    def test_log_link_resent(self, audit_service, mock_db_session, sample_uuids):
        """Test log_link_resent method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_link_resent(
                actor_id=sample_uuids['actor_id'],
                patient_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                delivery_method="sms",
                ip_address="10.0.0.2",
                user_agent="Admin Panel"
            )

            mock_log_event.assert_called_once_with(
                event_type="monthly_quiz_link_resent",
                event_category="access",
                severity="info",
                actor_id=sample_uuids['actor_id'],
                subject_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                ip_address="10.0.0.2",
                user_agent="Admin Panel",
                event_data={
                    "delivery_method": "sms"
                },
                result="success",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="legitimate_interest"
            )

    def test_log_link_regenerated(self, audit_service, mock_db_session, sample_uuids):
        """Test log_link_regenerated method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_link_regenerated(
                actor_id=sample_uuids['actor_id'],
                patient_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                regeneration_count=3,
                ip_address="192.168.1.50"
            )

            mock_log_event.assert_called_once_with(
                event_type="monthly_quiz_link_regenerated",
                event_category="security",
                severity="info",
                actor_id=sample_uuids['actor_id'],
                subject_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                ip_address="192.168.1.50",
                user_agent=None,
                event_data={
                    "regeneration_count": 3
                },
                result="success",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="legitimate_interest"
            )

    def test_log_link_cancelled(self, audit_service, mock_db_session, sample_uuids):
        """Test log_link_cancelled method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_link_cancelled(
                actor_id=sample_uuids['actor_id'],
                patient_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id']
            )

            mock_log_event.assert_called_once_with(
                event_type="monthly_quiz_link_cancelled",
                event_category="access",
                severity="info",
                actor_id=sample_uuids['actor_id'],
                subject_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                ip_address=None,
                user_agent=None,
                event_data={},
                result="success",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="legitimate_interest"
            )

    def test_log_link_expired_no_fallback(self, audit_service, mock_db_session, sample_uuids):
        """Test log_link_expired without fallback."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_link_expired(
                patient_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id']
            )

            mock_log_event.assert_called_once_with(
                event_type="monthly_quiz_link_expired",
                event_category="security",
                severity="warning",  # Should be warning when fallback not activated
                subject_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                event_data={
                    "fallback_activated": False
                },
                result="expired",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="legitimate_interest"
            )

    def test_log_link_expired_with_fallback(self, audit_service, mock_db_session, sample_uuids):
        """Test log_link_expired with fallback activated."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_link_expired(
                patient_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                fallback_activated=True
            )

            mock_log_event.assert_called_once_with(
                event_type="monthly_quiz_link_expired",
                event_category="security",
                severity="info",  # Should be info when fallback activated
                subject_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                event_data={
                    "fallback_activated": True
                },
                result="expired",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="legitimate_interest"
            )

    def test_log_fallback_activated(self, audit_service, mock_db_session, sample_uuids):
        """Test log_fallback_activated method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_fallback_activated(
                patient_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                fallback_reason="link_expired",
                fallback_method="whatsapp_conversational"
            )

            mock_log_event.assert_called_once_with(
                event_type="monthly_quiz_fallback_activated",
                event_category="access",
                severity="warning",
                subject_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                event_data={
                    "fallback_reason": "link_expired",
                    "fallback_method": "whatsapp_conversational"
                },
                result="fallback",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="legitimate_interest"
            )

    def test_log_fallback_activated_default_method(self, audit_service, mock_db_session, sample_uuids):
        """Test log_fallback_activated with default fallback method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_fallback_activated(
                patient_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                fallback_reason="user_request"
            )

            expected_event_data = {
                "fallback_reason": "user_request",
                "fallback_method": "whatsapp_conversational"  # default
            }

            mock_log_event.assert_called_once()
            call_args = mock_log_event.call_args[1]  # Get keyword arguments
            assert call_args['event_data'] == expected_event_data

    def test_log_reminder_sent(self, audit_service, mock_db_session, sample_uuids):
        """Test log_reminder_sent method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_reminder_sent(
                patient_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                delivery_channel="email",
                is_retry=True,
                retry_count=2
            )

            mock_log_event.assert_called_once_with(
                event_type="monthly_quiz_reminder_sent",
                event_category="access",
                severity="info",
                subject_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                event_data={
                    "delivery_channel": "email",
                    "is_retry": True,
                    "retry_count": 2
                },
                result="success",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="legitimate_interest"
            )

    def test_log_reminder_sent_defaults(self, audit_service, mock_db_session, sample_uuids):
        """Test log_reminder_sent with default parameters."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_reminder_sent(
                patient_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                delivery_channel="sms"
            )

            expected_event_data = {
                "delivery_channel": "sms",
                "is_retry": False,  # default
                "retry_count": 0   # default
            }

            call_args = mock_log_event.call_args[1]
            assert call_args['event_data'] == expected_event_data

    def test_log_reminder_failed(self, audit_service, mock_db_session, sample_uuids):
        """Test log_reminder_failed method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_reminder_failed(
                patient_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                delivery_channel="sms",
                failure_reason="Invalid phone number",
                retry_count=1
            )

            mock_log_event.assert_called_once_with(
                event_type="monthly_quiz_reminder_failed",
                event_category="access",
                severity="error",
                subject_id=sample_uuids['patient_id'],
                session_id=sample_uuids['session_id'],
                event_data={
                    "delivery_channel": "sms",
                    "failure_reason": "Invalid phone number",
                    "retry_count": 1
                },
                result="failure",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="legitimate_interest"
            )


class TestLGPDComplianceMethods:
    """Test LGPD compliance logging methods."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session = Mock(spec=Session)
        session.add = Mock()
        session.commit = Mock()
        return session

    @pytest.fixture
    def audit_service(self, mock_db_session):
        """AuditService instance with mocked database."""
        return AuditService(mock_db_session)

    @pytest.fixture
    def sample_uuids(self):
        """Sample UUIDs for testing."""
        return {
            'patient_id': uuid4(),
            'user_id': uuid4()
        }

    def test_log_consent_given(self, audit_service, mock_db_session, sample_uuids):
        """Test log_consent_given method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_consent_given(
                patient_id=sample_uuids['patient_id'],
                consent_type="data_processing",
                ip_address="192.168.1.1"
            )

            mock_log_event.assert_called_once_with(
                event_type="lgpd_consent_given",
                event_category="consent",
                severity="info",
                patient_id=sample_uuids['patient_id'],
                ip_address="192.168.1.1",
                event_data={
                    "consent_type": "data_processing"
                },
                result="success",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="consent",
                retention_days=2555  # 7 years for LGPD compliance
            )

    def test_log_consent_given_no_ip(self, audit_service, mock_db_session, sample_uuids):
        """Test log_consent_given without IP address."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_consent_given(
                patient_id=sample_uuids['patient_id'],
                consent_type="marketing"
            )

            call_args = mock_log_event.call_args[1]
            assert call_args['ip_address'] is None

    def test_log_data_deletion(self, audit_service, mock_db_session, sample_uuids):
        """Test log_data_deletion method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_data_deletion(
                patient_id=sample_uuids['patient_id'],
                user_id=sample_uuids['user_id'],
                deletion_scope="all_data",
                reason="user_request"
            )

            mock_log_event.assert_called_once_with(
                event_type="lgpd_data_deleted",
                event_category="data_change",
                severity="warning",
                actor_id=sample_uuids['user_id'],
                subject_id=sample_uuids['patient_id'],
                event_data={
                    "deletion_scope": "all_data",
                    "reason": "user_request"
                },
                result="success",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="legal_obligation",
                retention_days=2555  # 7 years retention
            )


class TestAIAuditMethods:
    """Test AI-specific audit methods."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session = Mock(spec=Session)
        session.add = Mock()
        session.commit = Mock()
        return session

    @pytest.fixture
    def audit_service(self, mock_db_session):
        """AuditService instance with mocked database."""
        return AuditService(mock_db_session)

    @pytest.fixture
    def sample_uuids(self):
        """Sample UUIDs for testing."""
        return {
            'user_id': uuid4(),
            'patient_id': uuid4()
        }

    def test_log_ai_chat_request(self, audit_service, mock_db_session, sample_uuids):
        """Test log_ai_chat_request method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event, \
             patch('app.services.audit_service.hashlib.sha256') as mock_sha256:

            # Mock hashlib.sha256
            mock_hash = Mock()
            mock_hash.hexdigest.return_value = "abcdef1234567890123456789"
            mock_sha256.return_value = mock_hash

            message = "Patient is experiencing headaches"
            response = "I recommend scheduling an appointment with a neurologist"

            result = audit_service.log_ai_chat_request(
                user_id=sample_uuids['user_id'],
                user_role="doctor",
                patient_id=sample_uuids['patient_id'],
                message=message,
                response=response,
                response_time_ms=150.5,
                cache_hit=True,
                ip_address="192.168.1.1",
                user_agent="Doctor App v1.0"
            )

            # Verify hash was called correctly
            mock_sha256.assert_called_once_with(message.encode())

            expected_event_data = {
                "user_role": "doctor",
                "message_hash": "abcdef1234567890",  # First 16 chars
                "message_length": len(message),
                "response_summary": response,  # Response is short enough
                "response_length": len(response),
                "response_time_ms": 150.5,
                "cache_hit": True,
                "has_patient_context": True
            }

            mock_log_event.assert_called_once_with(
                event_type="ai_chat_request",
                event_category="access",
                severity="info",
                actor_id=sample_uuids['user_id'],
                subject_id=sample_uuids['patient_id'],
                ip_address="192.168.1.1",
                user_agent="Doctor App v1.0",
                event_data=expected_event_data,
                result="success",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="legitimate_interest",
                retention_days=90  # HIPAA: 90 days for access logs
            )

    def test_log_ai_chat_request_long_response(self, audit_service, mock_db_session, sample_uuids):
        """Test log_ai_chat_request with long response truncation."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event, \
             patch('app.services.audit_service.hashlib.sha256') as mock_sha256:

            mock_hash = Mock()
            mock_hash.hexdigest.return_value = "abcdef1234567890123456789"
            mock_sha256.return_value = mock_hash

            message = "Short message"
            long_response = "A" * 150  # Longer than 100 chars

            result = audit_service.log_ai_chat_request(
                user_id=sample_uuids['user_id'],
                user_role="nurse",
                patient_id=sample_uuids['patient_id'],
                message=message,
                response=long_response,
                response_time_ms=200.0
            )

            call_args = mock_log_event.call_args[1]
            event_data = call_args['event_data']

            # Response should be truncated to 100 chars + "..."
            assert event_data['response_summary'] == "A" * 100 + "..."
            assert event_data['response_length'] == 150

    def test_log_ai_chat_request_no_patient_context(self, audit_service, mock_db_session, sample_uuids):
        """Test log_ai_chat_request without patient context."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event, \
             patch('app.services.audit_service.hashlib.sha256') as mock_sha256:

            mock_hash = Mock()
            mock_hash.hexdigest.return_value = "abcdef1234567890123456789"
            mock_sha256.return_value = mock_hash

            result = audit_service.log_ai_chat_request(
                user_id=sample_uuids['user_id'],
                user_role="admin",
                patient_id=None,  # No patient context
                message="General medical question",
                response="General medical advice",
                response_time_ms=100.0
            )

            call_args = mock_log_event.call_args[1]
            event_data = call_args['event_data']

            assert event_data['has_patient_context'] is False
            assert call_args['subject_id'] is None
            assert call_args['data_subject_id'] is None

    def test_log_ai_chat_error(self, audit_service, mock_db_session, sample_uuids):
        """Test log_ai_chat_error method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_ai_chat_error(
                user_id=sample_uuids['user_id'],
                user_role="doctor",
                patient_id=sample_uuids['patient_id'],
                error_type="api_timeout",
                error_message="OpenAI API request timed out after 30 seconds",
                ip_address="10.0.0.1",
                user_agent="Medical App"
            )

            expected_event_data = {
                "user_role": "doctor",
                "error_type": "api_timeout",
                "error_message": "OpenAI API request timed out after 30 seconds"[:200]  # Truncated
            }

            mock_log_event.assert_called_once_with(
                event_type="ai_chat_error",
                event_category="security",
                severity="error",
                actor_id=sample_uuids['user_id'],
                subject_id=sample_uuids['patient_id'],
                ip_address="10.0.0.1",
                user_agent="Medical App",
                event_data=expected_event_data,
                result="failure",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="legitimate_interest",
                retention_days=90
            )

    def test_log_ai_insights_generation(self, audit_service, mock_db_session, sample_uuids):
        """Test log_ai_insights_generation method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_ai_insights_generation(
                user_id=sample_uuids['user_id'],
                user_role="physician",
                patient_id=sample_uuids['patient_id'],
                timeframe_days=30,
                insights_count=5,
                risk_level="medium",
                response_time_ms=250.0,
                cache_hit=False,
                ip_address="172.16.0.1"
            )

            expected_event_data = {
                "user_role": "physician",
                "timeframe_days": 30,
                "insights_count": 5,
                "risk_level": "medium",
                "response_time_ms": 250.0,
                "cache_hit": False
            }

            mock_log_event.assert_called_once_with(
                event_type="ai_insights_generated",
                event_category="access",
                severity="info",
                actor_id=sample_uuids['user_id'],
                subject_id=sample_uuids['patient_id'],
                ip_address="172.16.0.1",
                user_agent=None,
                event_data=expected_event_data,
                result="success",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="legitimate_interest",
                retention_days=90
            )

    def test_log_ai_recommendations_generation(self, audit_service, mock_db_session, sample_uuids):
        """Test log_ai_recommendations_generation method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_ai_recommendations_generation(
                user_id=sample_uuids['user_id'],
                user_role="specialist",
                patient_id=sample_uuids['patient_id'],
                recommendations_count=3,
                action_items_count=2,
                confidence_level=0.85,
                response_time_ms=180.5
            )

            expected_event_data = {
                "user_role": "specialist",
                "recommendations_count": 3,
                "action_items_count": 2,
                "confidence_level": 0.85,
                "response_time_ms": 180.5,
                "cache_hit": False  # default
            }

            call_args = mock_log_event.call_args[1]
            assert call_args['event_data'] == expected_event_data

    def test_log_ai_analysis_request(self, audit_service, mock_db_session, sample_uuids):
        """Test log_ai_analysis_request method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_ai_analysis_request(
                user_id=sample_uuids['user_id'],
                user_role="researcher",
                patient_id=sample_uuids['patient_id'],
                analysis_type="trend_analysis",
                date_range_days=90,
                include_messages=True,
                include_medical_history=False,
                response_time_ms=500.0,
                ip_address="10.1.1.1",
                user_agent="Research Portal"
            )

            expected_event_data = {
                "user_role": "researcher",
                "analysis_type": "trend_analysis",
                "date_range_days": 90,
                "include_messages": True,
                "include_medical_history": False,
                "response_time_ms": 500.0
            }

            mock_log_event.assert_called_once_with(
                event_type="ai_analysis_request",
                event_category="access",
                severity="info",
                actor_id=sample_uuids['user_id'],
                subject_id=sample_uuids['patient_id'],
                ip_address="10.1.1.1",
                user_agent="Research Portal",
                event_data=expected_event_data,
                result="success",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="legitimate_interest",
                retention_days=90
            )

    def test_log_ai_sentiment_analysis(self, audit_service, mock_db_session, sample_uuids):
        """Test log_ai_sentiment_analysis method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event, \
             patch('app.services.audit_service.hashlib.sha256') as mock_sha256:

            mock_hash = Mock()
            mock_hash.hexdigest.return_value = "fedcba9876543210abcdef"
            mock_sha256.return_value = mock_hash

            message = "I'm feeling very anxious about the upcoming surgery"

            result = audit_service.log_ai_sentiment_analysis(
                user_id=sample_uuids['user_id'],
                user_role="therapist",
                patient_id=sample_uuids['patient_id'],
                message=message,
                sentiment="negative",
                concern_level="high",
                confidence=0.92,
                response_time_ms=95.0,
                ip_address="192.168.2.1",
                user_agent="Therapy App"
            )

            mock_sha256.assert_called_once_with(message.encode())

            expected_event_data = {
                "user_role": "therapist",
                "message_hash": "fedcba9876543210",  # First 16 chars
                "message_length": len(message),
                "sentiment": "negative",
                "concern_level": "high",
                "confidence": 0.92,
                "response_time_ms": 95.0
            }

            mock_log_event.assert_called_once_with(
                event_type="ai_sentiment_analysis",
                event_category="access",
                severity="info",
                actor_id=sample_uuids['user_id'],
                subject_id=sample_uuids['patient_id'],
                ip_address="192.168.2.1",
                user_agent="Therapy App",
                event_data=expected_event_data,
                result="success",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="legitimate_interest",
                retention_days=90
            )

    def test_log_ai_response_generation(self, audit_service, mock_db_session, sample_uuids):
        """Test log_ai_response_generation method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_ai_response_generation(
                user_id=sample_uuids['user_id'],
                user_role="nurse",
                patient_id=sample_uuids['patient_id'],
                message_type="reminder",
                template_length=150,
                generated_length=200,
                readability_score=8.5,
                response_time_ms=120.0
            )

            expected_event_data = {
                "user_role": "nurse",
                "message_type": "reminder",
                "template_length": 150,
                "generated_length": 200,
                "readability_score": 8.5,
                "response_time_ms": 120.0
            }

            call_args = mock_log_event.call_args[1]
            assert call_args['event_data'] == expected_event_data
            assert call_args['event_type'] == "ai_response_generated"

    def test_log_ai_cache_hit(self, audit_service, mock_db_session, sample_uuids):
        """Test log_ai_cache_hit method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event, \
             patch('app.services.audit_service.hashlib.sha256') as mock_sha256:

            mock_hash = Mock()
            mock_hash.hexdigest.return_value = "cache123456789012345"
            mock_sha256.return_value = mock_hash

            cache_key = "patient_123_insights_30d"

            result = audit_service.log_ai_cache_hit(
                cache_key=cache_key,
                endpoint="/ai/insights",
                response_time_ms=15.0,
                user_id=sample_uuids['user_id']
            )

            mock_sha256.assert_called_once_with(cache_key.encode())

            expected_event_data = {
                "cache_key_hash": "cache123456789012",  # First 16 chars
                "endpoint": "/ai/insights",
                "response_time_ms": 15.0
            }

            mock_log_event.assert_called_once_with(
                event_type="ai_cache_hit",
                event_category="access",
                severity="info",
                actor_id=sample_uuids['user_id'],
                event_data=expected_event_data,
                result="success",
                retention_days=30  # Shorter retention for performance logs
            )

    def test_log_ai_cache_miss(self, audit_service, mock_db_session, sample_uuids):
        """Test log_ai_cache_miss method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event, \
             patch('app.services.audit_service.hashlib.sha256') as mock_sha256:

            mock_hash = Mock()
            mock_hash.hexdigest.return_value = "miss987654321098765"
            mock_sha256.return_value = mock_hash

            cache_key = "patient_456_recommendations_7d"

            result = audit_service.log_ai_cache_miss(
                cache_key=cache_key,
                endpoint="/ai/recommendations",
                response_time_ms=250.0,
                user_id=sample_uuids['user_id']
            )

            expected_event_data = {
                "cache_key_hash": "miss987654321098",  # First 16 chars
                "endpoint": "/ai/recommendations",
                "response_time_ms": 250.0
            }

            mock_log_event.assert_called_once_with(
                event_type="ai_cache_miss",
                event_category="access",
                severity="info",
                actor_id=sample_uuids['user_id'],
                event_data=expected_event_data,
                result="success",
                retention_days=30
            )

    def test_log_ai_cache_invalidation(self, audit_service, mock_db_session, sample_uuids):
        """Test log_ai_cache_invalidation method."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            result = audit_service.log_ai_cache_invalidation(
                user_id=sample_uuids['user_id'],
                patient_id=sample_uuids['patient_id'],
                invalidated_count=5,
                ip_address="10.0.1.1"
            )

            expected_event_data = {
                "invalidated_count": 5
            }

            mock_log_event.assert_called_once_with(
                event_type="ai_cache_invalidated",
                event_category="data_change",
                severity="info",
                actor_id=sample_uuids['user_id'],
                subject_id=sample_uuids['patient_id'],
                ip_address="10.0.1.1",
                event_data=expected_event_data,
                result="success",
                data_subject_id=sample_uuids['patient_id'],
                legal_basis="legitimate_interest",
                retention_days=90
            )


class TestQueryMethods:
    """Test query and reporting methods."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session = Mock(spec=Session)
        return session

    @pytest.fixture
    def audit_service(self, mock_db_session):
        """AuditService instance with mocked database."""
        return AuditService(mock_db_session)

    @pytest.fixture
    def sample_uuids(self):
        """Sample UUIDs for testing."""
        return {
            'patient_id': uuid4(),
            'user_id': uuid4()
        }

    def test_get_patient_audit_trail(self, audit_service, mock_db_session, sample_uuids):
        """Test get_patient_audit_trail method."""
        # Setup mock query chain
        mock_query = Mock()
        mock_filter = Mock()
        mock_order_by = Mock()
        mock_limit = Mock()

        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order_by
        mock_order_by.limit.return_value = mock_limit
        mock_limit.all.return_value = []

        mock_db_session.query.return_value = mock_query

        result = audit_service.get_patient_audit_trail(
            patient_id=sample_uuids['patient_id'],
            limit=50
        )

        # Verify query chain was called correctly
        mock_db_session.query.assert_called_once_with(AuditLog)
        mock_query.filter.assert_called_once()
        mock_filter.order_by.assert_called_once()
        mock_order_by.limit.assert_called_once_with(50)
        mock_limit.all.assert_called_once()

        assert result == []

    def test_get_patient_audit_trail_default_limit(self, audit_service, mock_db_session, sample_uuids):
        """Test get_patient_audit_trail with default limit."""
        mock_query = Mock()
        mock_filter = Mock()
        mock_order_by = Mock()
        mock_limit = Mock()

        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order_by
        mock_order_by.limit.return_value = mock_limit
        mock_limit.all.return_value = []

        mock_db_session.query.return_value = mock_query

        result = audit_service.get_patient_audit_trail(
            patient_id=sample_uuids['patient_id']
        )

        mock_order_by.limit.assert_called_once_with(100)  # Default limit

    def test_cleanup_expired_logs(self, audit_service, mock_db_session):
        """Test cleanup_expired_logs method."""
        with patch('app.services.audit_service.datetime') as mock_datetime:
            fixed_now = datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.utcnow.return_value = fixed_now

            # Setup mock query chain
            mock_query = Mock()
            mock_filter = Mock()

            mock_query.filter.return_value = mock_filter
            mock_filter.delete.return_value = 10  # 10 logs deleted

            mock_db_session.query.return_value = mock_query

            deleted_count = audit_service.cleanup_expired_logs()

            # Verify operations
            mock_db_session.query.assert_called_once_with(AuditLog)
            mock_query.filter.assert_called_once()
            mock_filter.delete.assert_called_once()
            mock_db_session.commit.assert_called_once()

            assert deleted_count == 10

    def test_get_ai_audit_report_minimal(self, audit_service, mock_db_session):
        """Test get_ai_audit_report with minimal parameters."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 31)

        # Setup mock query chain
        mock_query = Mock()
        mock_filter = Mock()
        mock_order_by = Mock()

        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order_by
        mock_order_by.all.return_value = []

        mock_db_session.query.return_value = mock_query

        result = audit_service.get_ai_audit_report(
            start_date=start_date,
            end_date=end_date
        )

        # Verify basic query structure
        mock_db_session.query.assert_called_once_with(AuditLog)
        mock_query.filter.assert_called_once()
        mock_filter.order_by.assert_called_once()
        mock_order_by.all.assert_called_once()

        assert result == []

    def test_get_ai_audit_report_all_filters(self, audit_service, mock_db_session, sample_uuids):
        """Test get_ai_audit_report with all filters."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 31)
        event_types = ["ai_chat_request", "ai_insights_generated"]

        # Setup mock query chain with multiple filter calls
        mock_query = Mock()

        # Chain filter calls
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        mock_db_session.query.return_value = mock_query

        result = audit_service.get_ai_audit_report(
            start_date=start_date,
            end_date=end_date,
            event_types=event_types,
            user_id=sample_uuids['user_id'],
            patient_id=sample_uuids['patient_id']
        )

        # Should have multiple filter calls (base filters + optional filters)
        assert mock_query.filter.call_count >= 3  # Base filters + event_types + user_id + patient_id
        mock_query.order_by.assert_called_once()
        mock_query.all.assert_called_once()

    def test_get_ai_performance_metrics(self, audit_service, mock_db_session):
        """Test get_ai_performance_metrics method."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 31)

        # Create mock logs for testing
        mock_logs = []

        # Cache hit log
        cache_hit_log = Mock()
        cache_hit_log.event_type = "ai_cache_hit"
        cache_hit_log.result = "success"
        cache_hit_log.event_data = {"response_time_ms": 50.0}
        mock_logs.append(cache_hit_log)

        # Cache miss log
        cache_miss_log = Mock()
        cache_miss_log.event_type = "ai_cache_miss"
        cache_miss_log.result = "success"
        cache_miss_log.event_data = {"response_time_ms": 200.0}
        mock_logs.append(cache_miss_log)

        # Error log
        error_log = Mock()
        error_log.event_type = "ai_chat_error"
        error_log.result = "failure"
        error_log.event_data = {}
        mock_logs.append(error_log)

        # Regular log with response time
        regular_log = Mock()
        regular_log.event_type = "ai_chat_request"
        regular_log.result = "success"
        regular_log.event_data = {"response_time_ms": 100.0}
        mock_logs.append(regular_log)

        # Setup mock query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_logs

        mock_db_session.query.return_value = mock_query

        metrics = audit_service.get_ai_performance_metrics(start_date, end_date)

        # Verify metrics calculations
        assert metrics["total_requests"] == 4
        assert metrics["cache_hit_rate"] == 0.5  # 1 hit out of 2 cache events
        assert metrics["error_rate"] == 0.25  # 1 error out of 4 total
        assert metrics["average_response_time_ms"] == 116.666666666666667  # (50+200+100)/3
        assert metrics["period"]["start"] == start_date.isoformat()
        assert metrics["period"]["end"] == end_date.isoformat()

    def test_get_ai_performance_metrics_no_cache_events(self, audit_service, mock_db_session):
        """Test get_ai_performance_metrics with no cache events."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 31)

        # Only regular logs, no cache events
        mock_logs = []
        regular_log = Mock()
        regular_log.event_type = "ai_chat_request"
        regular_log.result = "success"
        regular_log.event_data = {"response_time_ms": 150.0}
        mock_logs.append(regular_log)

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_logs

        mock_db_session.query.return_value = mock_query

        metrics = audit_service.get_ai_performance_metrics(start_date, end_date)

        assert metrics["cache_hit_rate"] == 0  # No cache events

    def test_get_ai_performance_metrics_no_response_times(self, audit_service, mock_db_session):
        """Test get_ai_performance_metrics with no response time data."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 31)

        # Logs without response_time_ms
        mock_logs = []
        log_without_time = Mock()
        log_without_time.event_type = "ai_cache_hit"
        log_without_time.result = "success"
        log_without_time.event_data = {}  # No response_time_ms
        mock_logs.append(log_without_time)

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_logs

        mock_db_session.query.return_value = mock_query

        metrics = audit_service.get_ai_performance_metrics(start_date, end_date)

        assert metrics["average_response_time_ms"] == 0  # No response times available

    def test_get_patient_ai_access_history(self, audit_service, mock_db_session, sample_uuids):
        """Test get_patient_ai_access_history method."""
        mock_query = Mock()
        mock_filter1 = Mock()
        mock_filter2 = Mock()
        mock_order_by = Mock()
        mock_limit = Mock()

        mock_query.filter.side_effect = [mock_filter1, mock_filter2]
        mock_filter1.filter.return_value = mock_filter2
        mock_filter2.order_by.return_value = mock_order_by
        mock_order_by.limit.return_value = mock_limit
        mock_limit.all.return_value = []

        mock_db_session.query.return_value = mock_query

        result = audit_service.get_patient_ai_access_history(
            patient_id=sample_uuids['patient_id'],
            limit=200
        )

        # Verify query chain
        mock_db_session.query.assert_called_once_with(AuditLog)
        assert mock_query.filter.call_count == 2  # Two filter conditions
        mock_order_by.limit.assert_called_once_with(200)

    def test_get_user_ai_activity(self, audit_service, mock_db_session, sample_uuids):
        """Test get_user_ai_activity method."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 31)

        # Setup complex mock query chain
        mock_query = Mock()

        # Mock multiple filter calls
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        mock_db_session.query.return_value = mock_query

        result = audit_service.get_user_ai_activity(
            user_id=sample_uuids['user_id'],
            start_date=start_date,
            end_date=end_date
        )

        # Should filter by actor_id, event_type pattern, and timestamp range
        assert mock_query.filter.call_count >= 3
        mock_query.order_by.assert_called_once()
        mock_query.all.assert_called_once()

    def test_get_ai_security_events_no_severity_filter(self, audit_service, mock_db_session):
        """Test get_ai_security_events without severity filter."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 31)

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        mock_db_session.query.return_value = mock_query

        result = audit_service.get_ai_security_events(
            start_date=start_date,
            end_date=end_date
        )

        # Should have base filters but no severity filter
        assert mock_query.filter.call_count >= 3
        mock_query.order_by.assert_called_once()
        mock_query.all.assert_called_once()

    def test_get_ai_security_events_with_severity_filter(self, audit_service, mock_db_session):
        """Test get_ai_security_events with severity filter."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 31)

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        mock_db_session.query.return_value = mock_query

        result = audit_service.get_ai_security_events(
            start_date=start_date,
            end_date=end_date,
            severity="error"
        )

        # Should have base filters plus severity filter
        assert mock_query.filter.call_count >= 4
        mock_query.order_by.assert_called_once()
        mock_query.all.assert_called_once()

    def test_export_ai_audit_data(self, audit_service, mock_db_session, sample_uuids):
        """Test export_ai_audit_data method."""
        with patch.object(audit_service, 'get_patient_ai_access_history') as mock_get_history, \
             patch('app.services.audit_service.datetime') as mock_datetime:

            fixed_now = datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.utcnow.return_value = fixed_now

            # Mock log data
            mock_log = Mock()
            mock_log.timestamp = datetime(2022, 12, 15, 10, 30, 0)
            mock_log.event_type = "ai_chat_request"
            mock_log.event_category = "access"
            mock_log.severity = "info"
            mock_log.actor_id = "user-123"
            mock_log.result = "success"
            mock_log.event_data = {"user_role": "doctor"}

            mock_get_history.return_value = [mock_log]

            result = audit_service.export_ai_audit_data(
                patient_id=sample_uuids['patient_id'],
                format='json'
            )

            # Verify method calls
            mock_get_history.assert_called_once_with(sample_uuids['patient_id'], limit=1000)

            # Verify export structure
            assert result["patient_id"] == str(sample_uuids['patient_id'])
            assert result["export_date"] == fixed_now.isoformat()
            assert result["total_logs"] == 1
            assert len(result["logs"]) == 1

            exported_log = result["logs"][0]
            assert exported_log["timestamp"] == mock_log.timestamp.isoformat()
            assert exported_log["event_type"] == "ai_chat_request"
            assert exported_log["event_category"] == "access"
            assert exported_log["severity"] == "info"
            assert exported_log["actor_id"] == "user-123"
            assert exported_log["result"] == "success"
            assert exported_log["event_data"] == {"user_role": "doctor"}


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session = Mock(spec=Session)
        return session

    @pytest.fixture
    def audit_service(self, mock_db_session):
        """AuditService instance with mocked database."""
        return AuditService(mock_db_session)

    def test_log_event_database_error_on_add(self, audit_service, mock_db_session):
        """Test database error during add operation."""
        mock_db_session.add.side_effect = Exception("Database connection lost")
        mock_db_session.rollback = Mock()

        with pytest.raises(Exception, match="Database connection lost"):
            audit_service.log_event(
                event_type="test_event",
                event_category="test"
            )

        mock_db_session.rollback.assert_called_once()

    def test_log_event_database_error_on_commit(self, audit_service, mock_db_session):
        """Test database error during commit operation."""
        mock_db_session.add = Mock()
        mock_db_session.commit.side_effect = Exception("Transaction failed")
        mock_db_session.rollback = Mock()

        with pytest.raises(Exception, match="Transaction failed"):
            audit_service.log_event(
                event_type="test_event",
                event_category="test"
            )

        mock_db_session.add.assert_called_once()
        mock_db_session.rollback.assert_called_once()

    def test_log_event_mask_dict_secrets_error(self, audit_service, mock_db_session):
        """Test error in mask_dict_secrets function."""
        with patch('app.services.audit_service.mask_dict_secrets') as mock_mask:
            mock_mask.side_effect = Exception("Masking failed")

            with pytest.raises(Exception, match="Masking failed"):
                audit_service.log_event(
                    event_type="test_event",
                    event_category="test",
                    event_data={"key": "value"}
                )

    def test_cleanup_expired_logs_database_error(self, audit_service, mock_db_session):
        """Test database error during cleanup operation."""
        mock_query = Mock()
        mock_filter = Mock()

        mock_query.filter.return_value = mock_filter
        mock_filter.delete.side_effect = Exception("Delete operation failed")
        mock_db_session.query.return_value = mock_query
        mock_db_session.rollback = Mock()

        with pytest.raises(Exception, match="Delete operation failed"):
            audit_service.cleanup_expired_logs()

        mock_db_session.rollback.assert_called_once()

    def test_get_patient_audit_trail_database_error(self, audit_service, mock_db_session):
        """Test database error during patient audit trail query."""
        mock_db_session.query.side_effect = Exception("Query failed")

        with pytest.raises(Exception, match="Query failed"):
            audit_service.get_patient_audit_trail(uuid4())

    def test_get_ai_performance_metrics_empty_logs(self, audit_service, mock_db_session):
        """Test performance metrics with empty log list."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 31)

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []  # Empty logs

        mock_db_session.query.return_value = mock_query

        metrics = audit_service.get_ai_performance_metrics(start_date, end_date)

        assert metrics["total_requests"] == 0
        assert metrics["cache_hit_rate"] == 0
        assert metrics["error_rate"] == 0
        assert metrics["average_response_time_ms"] == 0

    def test_log_ai_chat_error_message_truncation(self, audit_service, mock_db_session):
        """Test AI chat error message truncation."""
        with patch.object(audit_service, 'log_event', return_value=Mock()) as mock_log_event:
            long_error_message = "A" * 300  # Longer than 200 chars

            result = audit_service.log_ai_chat_error(
                user_id=uuid4(),
                user_role="doctor",
                patient_id=uuid4(),
                error_type="test_error",
                error_message=long_error_message
            )

            call_args = mock_log_event.call_args[1]
            event_data = call_args['event_data']

            # Should be truncated to 200 chars
            assert len(event_data['error_message']) == 200
            assert event_data['error_message'] == "A" * 200

    def test_export_ai_audit_data_no_logs(self, audit_service, mock_db_session):
        """Test export with no logs available."""
        with patch.object(audit_service, 'get_patient_ai_access_history') as mock_get_history, \
             patch('app.services.audit_service.datetime') as mock_datetime:

            fixed_now = datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.utcnow.return_value = fixed_now

            mock_get_history.return_value = []  # No logs

            patient_id = uuid4()
            result = audit_service.export_ai_audit_data(patient_id)

            assert result["patient_id"] == str(patient_id)
            assert result["total_logs"] == 0
            assert result["logs"] == []

    def test_log_event_very_large_event_data(self, audit_service, mock_db_session):
        """Test log_event with very large event_data."""
        with patch('app.services.audit_service.datetime') as mock_datetime, \
             patch('app.services.audit_service.mask_dict_secrets') as mock_mask:

            mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 12, 0, 0)
            mock_mask.return_value = {"sanitized": "data"}

            # Very large event data
            large_data = {}
            for i in range(1000):
                large_data[f"key_{i}"] = f"value_{i}" * 100

            # Should not raise an exception
            result = audit_service.log_event(
                event_type="large_data_test",
                event_category="test",
                event_data=large_data
            )

            mock_mask.assert_called_once_with(large_data)
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()

    def test_log_ai_performance_metrics_invalid_event_data(self, audit_service, mock_db_session):
        """Test performance metrics with invalid event_data."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 31)

        # Create logs with invalid event_data
        mock_logs = []

        # Log with None event_data
        log_none = Mock()
        log_none.event_type = "ai_chat_request"
        log_none.result = "success"
        log_none.event_data = None
        mock_logs.append(log_none)

        # Log with invalid response_time_ms
        log_invalid = Mock()
        log_invalid.event_type = "ai_cache_hit"
        log_invalid.result = "success"
        log_invalid.event_data = {"response_time_ms": "invalid"}
        mock_logs.append(log_invalid)

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_logs

        mock_db_session.query.return_value = mock_query

        # Should not raise an exception and handle gracefully
        metrics = audit_service.get_ai_performance_metrics(start_date, end_date)

        assert metrics["total_requests"] == 2
        assert metrics["average_response_time_ms"] == 0  # No valid response times


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--cov=app.services.audit_service", "--cov-report=term-missing"])