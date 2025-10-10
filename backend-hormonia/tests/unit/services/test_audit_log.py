"""
Unit tests for Audit Log Service.

Tests audit logging functionality for critical security events.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session

from app.services.audit_log import AuditLogService
from app.models.audit_log import AuditLog, AuditEventType
from app.models.user import User, UserRole


@pytest.fixture
def db_session():
    """Mock database session."""
    session = Mock(spec=Session)
    session.add = Mock()
    session.commit = Mock()
    session.refresh = Mock()
    session.rollback = Mock()
    session.query = Mock()
    return session


@pytest.fixture
def audit_service(db_session):
    """Audit log service instance."""
    return AuditLogService(db_session)


@pytest.fixture
def sample_user():
    """Sample user for testing."""
    user = Mock(spec=User)
    user.id = "user-123"
    user.email = "test@example.com"
    user.firebase_uid = "firebase-uid-123"
    user.role = UserRole.DOCTOR
    user.is_active = True
    return user


@pytest.fixture
def mock_request():
    """Mock FastAPI request object."""
    request = Mock()
    request.client = Mock()
    request.client.host = "192.168.1.100"
    request.headers = {
        "User-Agent": "Mozilla/5.0 (Test Browser)"
    }
    return request


class TestClientInfoExtraction:
    """Test client information extraction from requests."""

    def test_extract_client_info_with_request(self, audit_service, mock_request):
        """Test extracting IP and user agent from request."""
        client_info = audit_service._extract_client_info(mock_request)

        assert client_info["ip_address"] == "192.168.1.100"
        assert client_info["user_agent"] == "Mozilla/5.0 (Test Browser)"

    def test_extract_client_info_with_forwarded_for(self, audit_service):
        """Test extracting IP from X-Forwarded-For header."""
        request = Mock()
        request.client = None
        request.headers = {
            "X-Forwarded-For": "10.0.0.1, 192.168.1.100",
            "User-Agent": "Test Agent"
        }

        client_info = audit_service._extract_client_info(request)

        assert client_info["ip_address"] == "10.0.0.1"
        assert client_info["user_agent"] == "Test Agent"

    def test_extract_client_info_with_real_ip(self, audit_service):
        """Test extracting IP from X-Real-IP header."""
        request = Mock()
        request.client = None
        request.headers = {
            "X-Real-IP": "10.0.0.5",
            "User-Agent": "Test Agent"
        }

        client_info = audit_service._extract_client_info(request)

        assert client_info["ip_address"] == "10.0.0.5"

    def test_extract_client_info_without_request(self, audit_service):
        """Test extracting client info when request is None."""
        client_info = audit_service._extract_client_info(None)

        assert client_info["ip_address"] is None
        assert client_info["user_agent"] is None


class TestLogEvent:
    """Test general event logging."""

    def test_log_event_basic(self, audit_service, db_session):
        """Test logging a basic event."""
        # Mock refresh to set created_at
        def mock_refresh(obj):
            obj.created_at = datetime.utcnow()

        db_session.refresh = mock_refresh

        result = audit_service.log_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            event_status="success",
            user_id="user-123",
            user_email="test@example.com",
            ip_address="192.168.1.100",
            user_agent="Test Browser",
            message="Test event"
        )

        # Verify database operations
        assert db_session.add.called
        assert db_session.commit.called
        assert db_session.refresh.called

    def test_log_event_with_request(self, audit_service, db_session, mock_request):
        """Test logging event with request object."""
        def mock_refresh(obj):
            obj.created_at = datetime.utcnow()

        db_session.refresh = mock_refresh

        result = audit_service.log_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="user-123",
            request=mock_request
        )

        # Client info should be extracted from request
        assert db_session.add.called

    def test_log_event_with_metadata(self, audit_service, db_session):
        """Test logging event with metadata."""
        def mock_refresh(obj):
            obj.created_at = datetime.utcnow()

        db_session.refresh = mock_refresh

        metadata = {"session_id": "sess-123", "device": "mobile"}

        result = audit_service.log_event(
            event_type=AuditEventType.SESSION_CREATED,
            user_id="user-123",
            metadata=metadata
        )

        assert db_session.add.called


class TestAuthenticationEventLogging:
    """Test authentication event logging methods."""

    def test_log_login_success(self, audit_service, db_session, sample_user, mock_request):
        """Test logging successful login."""
        def mock_refresh(obj):
            obj.created_at = datetime.utcnow()

        db_session.refresh = mock_refresh

        result = audit_service.log_login_success(
            user=sample_user,
            request=mock_request,
            metadata={"method": "firebase"}
        )

        assert db_session.add.called
        assert db_session.commit.called

    def test_log_login_failure(self, audit_service, db_session, mock_request):
        """Test logging failed login attempt."""
        def mock_refresh(obj):
            obj.created_at = datetime.utcnow()

        db_session.refresh = mock_refresh

        result = audit_service.log_login_failure(
            email="test@example.com",
            reason="Invalid password",
            request=mock_request
        )

        assert db_session.add.called
        assert db_session.commit.called

    def test_log_logout(self, audit_service, db_session, sample_user, mock_request):
        """Test logging logout event."""
        def mock_refresh(obj):
            obj.created_at = datetime.utcnow()

        db_session.refresh = mock_refresh

        result = audit_service.log_logout(
            user=sample_user,
            request=mock_request
        )

        assert db_session.add.called
        assert db_session.commit.called

    def test_log_session_created(self, audit_service, db_session, sample_user, mock_request):
        """Test logging session creation."""
        def mock_refresh(obj):
            obj.created_at = datetime.utcnow()

        db_session.refresh = mock_refresh

        result = audit_service.log_session_created(
            user=sample_user,
            session_id="session-123",
            request=mock_request
        )

        assert db_session.add.called
        assert db_session.commit.called

    def test_log_session_invalidated(self, audit_service, db_session):
        """Test logging session invalidation."""
        def mock_refresh(obj):
            obj.created_at = datetime.utcnow()

        db_session.refresh = mock_refresh

        result = audit_service.log_session_invalidated(
            user_id="user-123",
            session_id="session-123",
            reason="logout"
        )

        assert db_session.add.called
        assert db_session.commit.called

    def test_log_password_changed(self, audit_service, db_session, sample_user, mock_request):
        """Test logging password change."""
        def mock_refresh(obj):
            obj.created_at = datetime.utcnow()

        db_session.refresh = mock_refresh

        result = audit_service.log_password_changed(
            user=sample_user,
            request=mock_request
        )

        assert db_session.add.called
        assert db_session.commit.called


class TestSecurityEventLogging:
    """Test security event logging methods."""

    def test_log_access_denied(self, audit_service, db_session, mock_request):
        """Test logging access denied event."""
        def mock_refresh(obj):
            obj.created_at = datetime.utcnow()

        db_session.refresh = mock_refresh

        result = audit_service.log_access_denied(
            user_id="user-123",
            resource="/admin/users",
            reason="Insufficient permissions",
            request=mock_request
        )

        assert db_session.add.called
        assert db_session.commit.called

    def test_log_rate_limit_exceeded(self, audit_service, db_session, mock_request):
        """Test logging rate limit exceeded."""
        def mock_refresh(obj):
            obj.created_at = datetime.utcnow()

        db_session.refresh = mock_refresh

        result = audit_service.log_rate_limit_exceeded(
            user_email="test@example.com",
            resource="/api/v1/auth/login",
            request=mock_request
        )

        assert db_session.add.called
        assert db_session.commit.called


class TestQueryMethods:
    """Test audit log query methods."""

    def test_get_user_audit_logs(self, audit_service, db_session):
        """Test getting audit logs for a user."""
        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = []

        db_session.query.return_value = mock_query

        results = audit_service.get_user_audit_logs(
            user_id="user-123",
            limit=50,
            offset=0
        )

        assert db_session.query.called
        assert mock_query.filter.called
        assert mock_query.all.called

    def test_get_user_audit_logs_with_filters(self, audit_service, db_session):
        """Test getting user audit logs with filters."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = []

        db_session.query.return_value = mock_query

        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()

        results = audit_service.get_user_audit_logs(
            user_id="user-123",
            event_types=[AuditEventType.LOGIN_SUCCESS, AuditEventType.LOGOUT],
            start_date=start_date,
            end_date=end_date
        )

        assert mock_query.filter.called
        assert mock_query.all.called

    def test_get_security_events(self, audit_service, db_session):
        """Test getting security events."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = []

        db_session.query.return_value = mock_query

        results = audit_service.get_security_events(limit=100)

        assert db_session.query.called
        assert mock_query.filter.called

    def test_get_failed_login_attempts(self, audit_service, db_session):
        """Test getting failed login attempts."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        db_session.query.return_value = mock_query

        results = audit_service.get_failed_login_attempts(
            email="test@example.com",
            hours=24
        )

        assert db_session.query.called
        assert mock_query.filter.called

    def test_get_audit_statistics(self, audit_service, db_session):
        """Test getting audit statistics."""
        # Mock query for count
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 100
        mock_query.with_entities.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [
            (AuditEventType.LOGIN_SUCCESS, 50),
            (AuditEventType.LOGOUT, 30),
        ]
        mock_query.distinct.return_value = mock_query

        db_session.query.return_value = mock_query

        stats = audit_service.get_audit_statistics()

        assert stats["total_events"] == 100
        assert "events_by_type" in stats
        assert "unique_users" in stats


class TestErrorHandling:
    """Test error handling in audit logging."""

    def test_log_event_database_error(self, audit_service, db_session):
        """Test handling database error during logging."""
        db_session.commit.side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Database error"):
            audit_service.log_event(
                event_type=AuditEventType.LOGIN_SUCCESS,
                user_id="user-123"
            )

        assert db_session.rollback.called
