"""
Integration tests for Audit Log functionality.

Tests the complete audit logging flow including database operations.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base
from app.models.audit_log import AuditLog, AuditEventType
from app.models.user import User, UserRole, AuthProvider
from app.services.audit_log import AuditLogService


@pytest.fixture(scope="function")
def test_db():
    """Create a test database with audit_logs table."""
    # Use in-memory SQLite for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    yield db

    db.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def test_user(test_db):
    """Create a test user."""
    user = User(
        email="test@example.com",
        hashed_password="hashed_password",
        full_name="Test User",
        role=UserRole.DOCTOR,
        is_active=True,
        firebase_uid="firebase-uid-123",
        auth_provider=AuthProvider.FIREBASE
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def audit_service(test_db):
    """Audit log service with test database."""
    return AuditLogService(test_db)


class TestAuditLogPersistence:
    """Test audit log database persistence."""

    def test_create_audit_log_entry(self, test_db, audit_service, test_user):
        """Test creating an audit log entry in database."""
        audit_entry = audit_service.log_login_success(
            user=test_user,
            metadata={"method": "firebase"}
        )

        # Verify entry was created
        assert audit_entry.id is not None
        assert audit_entry.user_id == str(test_user.id)
        assert audit_entry.event_type == AuditEventType.LOGIN_SUCCESS
        assert audit_entry.event_status == "success"

        # Query database to verify persistence
        stored_entry = test_db.query(AuditLog).filter(
            AuditLog.id == audit_entry.id
        ).first()

        assert stored_entry is not None
        assert stored_entry.user_email == test_user.email

    def test_create_multiple_audit_entries(self, test_db, audit_service, test_user):
        """Test creating multiple audit entries."""
        # Create login event
        audit_service.log_login_success(user=test_user)

        # Create session event
        audit_service.log_session_created(
            user=test_user,
            session_id="session-123"
        )

        # Create logout event
        audit_service.log_logout(user=test_user)

        # Verify all entries were created
        entries = test_db.query(AuditLog).filter(
            AuditLog.user_id == str(test_user.id)
        ).all()

        assert len(entries) == 3
        event_types = {entry.event_type for entry in entries}
        assert AuditEventType.LOGIN_SUCCESS in event_types
        assert AuditEventType.SESSION_CREATED in event_types
        assert AuditEventType.LOGOUT in event_types

    def test_audit_log_with_metadata(self, test_db, audit_service, test_user):
        """Test storing metadata in audit log."""
        metadata = {
            "session_id": "session-123",
            "device": "mobile",
            "location": "São Paulo, Brazil"
        }

        audit_entry = audit_service.log_login_success(
            user=test_user,
            metadata=metadata
        )

        # Verify metadata was stored
        assert audit_entry.metadata == metadata

        # Query and verify
        stored_entry = test_db.query(AuditLog).filter(
            AuditLog.id == audit_entry.id
        ).first()

        assert stored_entry.metadata["session_id"] == "session-123"
        assert stored_entry.metadata["device"] == "mobile"


class TestAuditLogQuerying:
    """Test audit log query functionality."""

    def test_get_user_audit_logs(self, test_db, audit_service, test_user):
        """Test querying user audit logs."""
        # Create multiple entries
        for i in range(5):
            audit_service.log_login_success(user=test_user)
            audit_service.log_logout(user=test_user)

        # Query logs
        logs = audit_service.get_user_audit_logs(
            user_id=str(test_user.id),
            limit=10
        )

        assert len(logs) == 10

    def test_get_user_audit_logs_with_event_filter(self, test_db, audit_service, test_user):
        """Test filtering user logs by event type."""
        # Create different event types
        audit_service.log_login_success(user=test_user)
        audit_service.log_login_success(user=test_user)
        audit_service.log_logout(user=test_user)
        audit_service.log_password_changed(user=test_user)

        # Query only login events
        logs = audit_service.get_user_audit_logs(
            user_id=str(test_user.id),
            event_types=[AuditEventType.LOGIN_SUCCESS]
        )

        assert len(logs) == 2
        assert all(log.event_type == AuditEventType.LOGIN_SUCCESS for log in logs)

    def test_get_user_audit_logs_with_date_range(self, test_db, audit_service, test_user):
        """Test filtering logs by date range."""
        # Create old entries
        old_date = datetime.utcnow() - timedelta(days=10)

        # Create recent entries
        audit_service.log_login_success(user=test_user)
        audit_service.log_logout(user=test_user)

        # Query only recent logs (last 7 days)
        start_date = datetime.utcnow() - timedelta(days=7)
        logs = audit_service.get_user_audit_logs(
            user_id=str(test_user.id),
            start_date=start_date
        )

        assert len(logs) == 2

    def test_get_security_events(self, test_db, audit_service, test_user):
        """Test querying security events."""
        # Create normal events
        audit_service.log_login_success(user=test_user)
        audit_service.log_logout(user=test_user)

        # Create security events
        audit_service.log_login_failure("test@example.com", "Invalid password")
        audit_service.log_access_denied(str(test_user.id), "/admin", "Unauthorized")
        audit_service.log_rate_limit_exceeded("test@example.com", "/api/login")

        # Query security events
        security_logs = audit_service.get_security_events(limit=100)

        assert len(security_logs) == 3
        assert all(log.is_security_event or log.is_failure for log in security_logs)

    def test_get_failed_login_attempts(self, test_db, audit_service):
        """Test querying failed login attempts."""
        email = "test@example.com"

        # Create failed login attempts
        for i in range(3):
            audit_service.log_login_failure(email, "Invalid password")

        # Query failed logins
        failed_logins = audit_service.get_failed_login_attempts(
            email=email,
            hours=24
        )

        assert len(failed_logins) == 3
        assert all(log.event_type == AuditEventType.LOGIN_FAILURE for log in failed_logins)
        assert all(log.user_email == email for log in failed_logins)

    def test_get_failed_login_attempts_by_ip(self, test_db, audit_service):
        """Test querying failed logins by IP address."""
        ip_address = "192.168.1.100"

        # Create failed login attempts
        for i in range(2):
            audit_service.log_event(
                event_type=AuditEventType.LOGIN_FAILURE,
                event_status="failure",
                user_email="test@example.com",
                ip_address=ip_address
            )

        # Query by IP
        failed_logins = audit_service.get_failed_login_attempts(
            ip_address=ip_address,
            hours=24
        )

        assert len(failed_logins) == 2


class TestAuditStatistics:
    """Test audit statistics functionality."""

    def test_get_audit_statistics(self, test_db, audit_service, test_user):
        """Test getting audit statistics."""
        # Create various events
        audit_service.log_login_success(user=test_user)
        audit_service.log_login_success(user=test_user)
        audit_service.log_login_failure("fail@example.com", "Invalid")
        audit_service.log_logout(user=test_user)
        audit_service.log_password_changed(user=test_user)

        # Get statistics
        stats = audit_service.get_audit_statistics()

        assert stats["total_events"] == 5
        assert stats["failure_count"] == 1
        assert stats["unique_users"] >= 1
        assert "events_by_type" in stats
        assert len(stats["events_by_type"]) > 0

    def test_get_audit_statistics_with_date_range(self, test_db, audit_service, test_user):
        """Test statistics with date range filter."""
        # Create events
        audit_service.log_login_success(user=test_user)
        audit_service.log_logout(user=test_user)

        # Get statistics for last 7 days
        start_date = datetime.utcnow() - timedelta(days=7)
        stats = audit_service.get_audit_statistics(start_date=start_date)

        assert stats["total_events"] == 2


class TestAuditLogProperties:
    """Test audit log model properties."""

    def test_is_failure_property(self, test_db, audit_service):
        """Test is_failure property."""
        # Create failure event
        failed_login = audit_service.log_login_failure(
            "test@example.com",
            "Invalid password"
        )

        assert failed_login.is_failure is True

        # Create success event
        user = User(
            email="success@example.com",
            role=UserRole.DOCTOR,
            is_active=True
        )
        test_db.add(user)
        test_db.commit()

        success_login = audit_service.log_login_success(user)
        assert success_login.is_failure is False

    def test_is_authentication_event_property(self, test_db, audit_service, test_user):
        """Test is_authentication_event property."""
        # Auth event
        login = audit_service.log_login_success(test_user)
        assert login.is_authentication_event is True

        # Non-auth event
        password_change = audit_service.log_password_changed(test_user)
        assert password_change.is_authentication_event is False

    def test_is_security_event_property(self, test_db, audit_service):
        """Test is_security_event property."""
        # Security event
        rate_limit = audit_service.log_rate_limit_exceeded(
            "test@example.com",
            "/api/login"
        )
        assert rate_limit.is_security_event is True

        # Non-security event
        user = User(
            email="test@example.com",
            role=UserRole.DOCTOR,
            is_active=True
        )
        test_db.add(user)
        test_db.commit()

        login = audit_service.log_login_success(user)
        assert login.is_security_event is False


class TestPagination:
    """Test pagination in audit log queries."""

    def test_pagination_with_limit_and_offset(self, test_db, audit_service, test_user):
        """Test pagination functionality."""
        # Create 20 entries
        for i in range(20):
            audit_service.log_login_success(user=test_user)

        # Get first page
        page1 = audit_service.get_user_audit_logs(
            user_id=str(test_user.id),
            limit=10,
            offset=0
        )

        # Get second page
        page2 = audit_service.get_user_audit_logs(
            user_id=str(test_user.id),
            limit=10,
            offset=10
        )

        assert len(page1) == 10
        assert len(page2) == 10

        # Ensure no overlap
        page1_ids = {log.id for log in page1}
        page2_ids = {log.id for log in page2}
        assert len(page1_ids.intersection(page2_ids)) == 0
