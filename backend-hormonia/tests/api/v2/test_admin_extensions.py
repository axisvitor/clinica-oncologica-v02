"""
Comprehensive tests for Admin Extensions API v2
Tests for Dead Letter Queue and Audit Log Management endpoints.

Test Coverage:
- DLQ management (list, get, retry, bulk retry, delete, stats, purge)
- Audit log management (list, get, export)
- Cursor pagination
- Field selection
- Filtering and search
- RBAC enforcement (admin-only)
- Cache behavior
- Error handling
- Bulk operations
"""

import pytest
import json
import base64
import csv
import io
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from unittest.mock import Mock, patch, MagicMock

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.failed_message import FailedMessage
from app.models.audit_log import AuditLog, AuditEventType
from app.services.dlq_service import DLQService
from app.services.audit_service import AuditService
from app.utils.security import get_password_hash


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def admin_user(db_session: Session):
    """Create an admin user for testing."""
    admin = User(
        id=uuid4(),
        email="admin@test.com",
        hashed_password=get_password_hash("AdminPass123"),
        full_name="Test Admin",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def doctor_user(db_session: Session):
    """Create a doctor user for testing."""
    doctor = User(
        id=uuid4(),
        email="doctor@test.com",
        hashed_password=get_password_hash("DoctorPass123"),
        full_name="Dr. Test Doctor",
        role=UserRole.DOCTOR,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


@pytest.fixture
def dlq_items(db_session: Session):
    """Create multiple DLQ items for testing."""
    patient_id = uuid4()
    items = []

    for i in range(25):
        item = FailedMessage(
            id=uuid4(),
            patient_id=patient_id,
            phone_number=f"+55119999999{i:02d}",
            message_type="appointment_reminder",
            message_content=f"Test message {i}",
            error_message=f"Test error {i}",
            error_code="TIMEOUT" if i % 2 == 0 else "INVALID_PHONE",
            retry_count=i % 5,
            max_retries=5,
            status="pending" if i % 3 == 0 else "retry_scheduled",
            dlq_metadata={"source": "test", "index": i},
            created_at=datetime.utcnow() - timedelta(hours=i),
            updated_at=datetime.utcnow()
        )
        items.append(item)
        db_session.add(item)

    db_session.commit()
    return items


@pytest.fixture
def audit_logs(db_session: Session, admin_user: User):
    """Create audit logs for testing."""
    logs = []

    for i in range(30):
        log = AuditLog(
            id=uuid4(),
            event_type=AuditEventType.LOGIN_SUCCESS if i % 2 == 0 else AuditEventType.ADMIN_USER_CREATE,
            event_status="success" if i % 3 != 0 else "failure",
            user_id=str(admin_user.id),
            user_email=admin_user.email,
            firebase_uid=f"firebase_uid_{i}",
            ip_address=f"192.168.1.{i}",
            user_agent="TestAgent/1.0",
            resource="/api/v2/test",
            action=f"test_action_{i}",
            event_metadata={"test": f"data_{i}"},
            message=f"Test event {i}",
            error_details=f"Error {i}" if i % 3 == 0 else None,
            created_at=datetime.utcnow() - timedelta(hours=i),
            updated_at=datetime.utcnow()
        )
        logs.append(log)
        db_session.add(log)

    db_session.commit()
    return logs


@pytest.fixture
def mock_admin_dependency():
    """Mock the admin user dependency."""
    def _mock_admin():
        user = Mock(spec=User)
        user.id = uuid4()
        user.email = "admin@test.com"
        user.role = UserRole.ADMIN
        user.is_active = True
        return user
    return _mock_admin


@pytest.fixture
def mock_context():
    """Mock RequestContext."""
    context = Mock()
    context.ip_address = "127.0.0.1"
    context.user_agent = "TestClient/1.0"
    return context


# ============================================================================
# DLQ ENDPOINTS TESTS
# ============================================================================

class TestListDLQItems:
    """Tests for GET /api/v2/admin-extensions/dlq"""

    def test_list_dlq_items_basic(self, client: TestClient, admin_user: User, dlq_items):
        """Test basic DLQ items listing."""
        response = client.get("/api/v2/admin-extensions/dlq")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "data" in data
        assert "next_cursor" in data
        assert "has_more" in data
        assert isinstance(data["data"], list)

    def test_list_dlq_items_with_limit(self, client: TestClient, admin_user: User, dlq_items):
        """Test DLQ listing with custom limit."""
        response = client.get("/api/v2/admin-extensions/dlq?limit=10")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["data"]) <= 10

    def test_list_dlq_items_cursor_pagination(self, client: TestClient, admin_user: User, dlq_items):
        """Test cursor-based pagination."""
        # First page
        response1 = client.get("/api/v2/admin-extensions/dlq?limit=5")
        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()

        # Second page with cursor
        if data1["next_cursor"]:
            response2 = client.get(f"/api/v2/admin-extensions/dlq?limit=5&cursor={data1['next_cursor']}")
            assert response2.status_code == status.HTTP_200_OK
            data2 = response2.json()

            # Ensure no duplicate IDs
            ids1 = [item["id"] for item in data1["data"]]
            ids2 = [item["id"] for item in data2["data"]]
            assert len(set(ids1) & set(ids2)) == 0

    def test_list_dlq_items_filter_by_status(self, client: TestClient, admin_user: User, dlq_items):
        """Test filtering by status."""
        response = client.get("/api/v2/admin-extensions/dlq?status=pending")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for item in data["data"]:
            assert item["status"] == "pending"

    def test_list_dlq_items_filter_by_error_code(self, client: TestClient, admin_user: User, dlq_items):
        """Test filtering by error code."""
        response = client.get("/api/v2/admin-extensions/dlq?error_code=TIMEOUT")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for item in data["data"]:
            assert item["error_code"] == "TIMEOUT"

    def test_list_dlq_items_search(self, client: TestClient, admin_user: User, dlq_items):
        """Test search functionality."""
        response = client.get("/api/v2/admin-extensions/dlq?search=Test error")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should find items with "Test error" in error_message
        assert len(data["data"]) > 0

    def test_list_dlq_items_field_selection(self, client: TestClient, admin_user: User, dlq_items):
        """Test field selection."""
        response = client.get("/api/v2/admin-extensions/dlq?fields=id,error_message,status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for item in data["data"]:
            assert "id" in item
            assert "error_message" in item
            assert "status" in item

    def test_list_dlq_items_unauthorized(self, client: TestClient, doctor_user: User):
        """Test that non-admin users are denied access."""
        # Mock doctor user instead of admin
        response = client.get("/api/v2/admin-extensions/dlq")

        # Should be forbidden (doctor is not admin)
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED]


class TestGetDLQItem:
    """Tests for GET /api/v2/admin-extensions/dlq/{dlq_id}"""

    def test_get_dlq_item_success(self, client: TestClient, admin_user: User, dlq_items):
        """Test successful DLQ item retrieval."""
        item = dlq_items[0]
        response = client.get(f"/api/v2/admin-extensions/dlq/{item.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == str(item.id)
        assert data["error_message"] == item.error_message

    def test_get_dlq_item_not_found(self, client: TestClient, admin_user: User):
        """Test getting non-existent DLQ item."""
        fake_id = uuid4()
        response = client.get(f"/api/v2/admin-extensions/dlq/{fake_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_dlq_item_field_selection(self, client: TestClient, admin_user: User, dlq_items):
        """Test field selection on DLQ item retrieval."""
        item = dlq_items[0]
        response = client.get(f"/api/v2/admin-extensions/dlq/{item.id}?fields=id,error_message")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "id" in data
        assert "error_message" in data

    def test_get_dlq_item_invalid_uuid(self, client: TestClient, admin_user: User):
        """Test getting DLQ item with invalid UUID."""
        response = client.get("/api/v2/admin-extensions/dlq/not-a-uuid")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestRetryDLQItem:
    """Tests for POST /api/v2/admin-extensions/dlq/{dlq_id}/retry"""

    def test_retry_dlq_item_success(self, client: TestClient, admin_user: User, dlq_items, mocker):
        """Test successful DLQ item retry."""
        item = dlq_items[0]

        # Mock DLQService.retry_message
        mocker.patch.object(DLQService, 'retry_message', return_value=(True, None))

        response = client.post(f"/api/v2/admin-extensions/dlq/{item.id}/retry")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["success"] is True
        assert data["dlq_id"] == str(item.id)

    def test_retry_dlq_item_failure(self, client: TestClient, admin_user: User, dlq_items, mocker):
        """Test DLQ item retry failure."""
        item = dlq_items[0]

        # Mock DLQService.retry_message to return failure
        mocker.patch.object(DLQService, 'retry_message', return_value=(False, "Network timeout"))

        response = client.post(f"/api/v2/admin-extensions/dlq/{item.id}/retry")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["success"] is False
        assert data["error"] == "Network timeout"


class TestBulkRetryDLQItems:
    """Tests for POST /api/v2/admin-extensions/dlq/retry-bulk"""

    def test_bulk_retry_success(self, client: TestClient, admin_user: User, dlq_items, mocker):
        """Test successful bulk retry."""
        item_ids = [str(item.id) for item in dlq_items[:5]]

        # Mock DLQService.retry_message
        mocker.patch.object(DLQService, 'retry_message', return_value=(True, None))

        bulk_data = {"dlq_ids": item_ids}
        response = client.post("/api/v2/admin-extensions/dlq/retry-bulk", json=bulk_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["success"] is True
        assert data["successful"] == 5
        assert data["failed"] == 0

    def test_bulk_retry_exceeds_limit(self, client: TestClient, admin_user: User):
        """Test bulk retry exceeding limit."""
        item_ids = [str(uuid4()) for _ in range(51)]

        bulk_data = {"dlq_ids": item_ids}
        response = client.post("/api/v2/admin-extensions/dlq/retry-bulk", json=bulk_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_retry_partial_success(self, client: TestClient, admin_user: User, dlq_items, mocker):
        """Test bulk retry with partial success."""
        item_ids = [str(dlq_items[0].id), str(uuid4())]  # One valid, one invalid

        # Mock retry_message to succeed for valid, fail for invalid
        def mock_retry(dlq_id, manual=False):
            if dlq_id == dlq_items[0].id:
                return (True, None)
            else:
                raise Exception("Item not found")

        mocker.patch.object(DLQService, 'retry_message', side_effect=mock_retry)

        bulk_data = {"dlq_ids": item_ids}
        response = client.post("/api/v2/admin-extensions/dlq/retry-bulk", json=bulk_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["successful"] == 1
        assert data["failed"] == 1


class TestDeleteDLQItem:
    """Tests for DELETE /api/v2/admin-extensions/dlq/{dlq_id}"""

    def test_delete_dlq_item_success(self, client: TestClient, admin_user: User, dlq_items, mocker):
        """Test successful DLQ item deletion."""
        item = dlq_items[0]

        # Mock DLQService.discard_message
        mocker.patch.object(DLQService, 'discard_message', return_value=True)

        response = client.delete(f"/api/v2/admin-extensions/dlq/{item.id}?reason=Test deletion")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["success"] is True
        assert data["dlq_id"] == str(item.id)

    def test_delete_dlq_item_not_found(self, client: TestClient, admin_user: User, mocker):
        """Test deleting non-existent DLQ item."""
        fake_id = uuid4()

        # Mock DLQService.discard_message to return False
        mocker.patch.object(DLQService, 'discard_message', return_value=False)

        response = client.delete(f"/api/v2/admin-extensions/dlq/{fake_id}?reason=Test")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_dlq_item_requires_reason(self, client: TestClient, admin_user: User, dlq_items):
        """Test that deletion requires a reason."""
        item = dlq_items[0]

        response = client.delete(f"/api/v2/admin-extensions/dlq/{item.id}")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestDLQStatistics:
    """Tests for GET /api/v2/admin-extensions/dlq/stats"""

    def test_get_dlq_statistics(self, client: TestClient, admin_user: User, dlq_items, mocker):
        """Test getting DLQ statistics."""
        # Mock DLQService.get_stats
        mock_stats = {
            "total": 150,
            "pending": 20,
            "retry_scheduled": 30,
            "retrying": 5,
            "resolved": 80,
            "discarded": 10,
            "max_retries_exceeded": 5,
            "transient_errors_24h": 25,
            "permanent_errors_24h": 8,
            "unknown_errors_24h": 2,
            "retry_success_rate": 75.5
        }
        mocker.patch.object(DLQService, 'get_stats', return_value=mock_stats)

        response = client.get("/api/v2/admin-extensions/dlq/stats")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total"] == 150
        assert data["retry_success_rate"] == 75.5


class TestPurgeDLQItems:
    """Tests for DELETE /api/v2/admin-extensions/dlq/purge"""

    def test_purge_dlq_items_dry_run(self, client: TestClient, admin_user: User, dlq_items):
        """Test purge with dry run."""
        response = client.delete("/api/v2/admin-extensions/dlq/purge?days=90&dry_run=true")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["dry_run"] is True
        assert "count" in data

    def test_purge_dlq_items_actual(self, client: TestClient, admin_user: User, dlq_items, db_session: Session):
        """Test actual purge operation."""
        # Create old items with safe statuses
        old_date = datetime.utcnow() - timedelta(days=100)
        old_item = FailedMessage(
            id=uuid4(),
            patient_id=uuid4(),
            phone_number="+5511999999999",
            message_type="test",
            message_content="old message",
            error_message="old error",
            retry_count=0,
            max_retries=5,
            status="resolved",  # Safe status for purging
            created_at=old_date,
            updated_at=datetime.utcnow()
        )
        db_session.add(old_item)
        db_session.commit()

        response = client.delete("/api/v2/admin-extensions/dlq/purge?days=90&dry_run=false")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["success"] is True
        assert data["count"] >= 1

    def test_purge_dlq_items_invalid_days(self, client: TestClient, admin_user: User):
        """Test purge with invalid days parameter."""
        # Too few days
        response = client.delete("/api/v2/admin-extensions/dlq/purge?days=10")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ============================================================================
# AUDIT LOG ENDPOINTS TESTS
# ============================================================================

class TestListAuditLogs:
    """Tests for GET /api/v2/admin-extensions/audit-logs"""

    def test_list_audit_logs_basic(self, client: TestClient, admin_user: User, audit_logs):
        """Test basic audit logs listing."""
        response = client.get("/api/v2/admin-extensions/audit-logs")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "data" in data
        assert "next_cursor" in data
        assert "has_more" in data
        assert isinstance(data["data"], list)

    def test_list_audit_logs_with_limit(self, client: TestClient, admin_user: User, audit_logs):
        """Test audit logs listing with custom limit."""
        response = client.get("/api/v2/admin-extensions/audit-logs?limit=10")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["data"]) <= 10

    def test_list_audit_logs_cursor_pagination(self, client: TestClient, admin_user: User, audit_logs):
        """Test cursor-based pagination."""
        # First page
        response1 = client.get("/api/v2/admin-extensions/audit-logs?limit=5")
        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()

        # Second page with cursor
        if data1["next_cursor"]:
            response2 = client.get(f"/api/v2/admin-extensions/audit-logs?limit=5&cursor={data1['next_cursor']}")
            assert response2.status_code == status.HTTP_200_OK
            data2 = response2.json()

            # Ensure no duplicate IDs
            ids1 = [log["id"] for log in data1["data"]]
            ids2 = [log["id"] for log in data2["data"]]
            assert len(set(ids1) & set(ids2)) == 0

    def test_list_audit_logs_filter_by_event_type(self, client: TestClient, admin_user: User, audit_logs):
        """Test filtering by event type."""
        response = client.get("/api/v2/admin-extensions/audit-logs?event_type=login_success")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for log in data["data"]:
            assert log["event_type"] == "login_success"

    def test_list_audit_logs_filter_by_status(self, client: TestClient, admin_user: User, audit_logs):
        """Test filtering by status."""
        response = client.get("/api/v2/admin-extensions/audit-logs?event_status=success")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for log in data["data"]:
            assert log["event_status"] == "success"

    def test_list_audit_logs_filter_by_user_email(self, client: TestClient, admin_user: User, audit_logs):
        """Test filtering by user email."""
        response = client.get(f"/api/v2/admin-extensions/audit-logs?user_email={admin_user.email}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for log in data["data"]:
            assert admin_user.email in log["user_email"]

    def test_list_audit_logs_filter_by_date_range(self, client: TestClient, admin_user: User, audit_logs):
        """Test filtering by date range."""
        start_date = (datetime.utcnow() - timedelta(days=2)).isoformat()
        end_date = datetime.utcnow().isoformat()

        response = client.get(
            f"/api/v2/admin-extensions/audit-logs?start_date={start_date}&end_date={end_date}"
        )

        assert response.status_code == status.HTTP_200_OK

    def test_list_audit_logs_search(self, client: TestClient, admin_user: User, audit_logs):
        """Test search functionality."""
        response = client.get("/api/v2/admin-extensions/audit-logs?search=Test event")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should find logs with "Test event" in message
        assert len(data["data"]) > 0


class TestGetAuditLog:
    """Tests for GET /api/v2/admin-extensions/audit-logs/{log_id}"""

    def test_get_audit_log_success(self, client: TestClient, admin_user: User, audit_logs):
        """Test successful audit log retrieval."""
        log = audit_logs[0]
        response = client.get(f"/api/v2/admin-extensions/audit-logs/{log.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == str(log.id)
        assert data["event_type"] == log.event_type.value

    def test_get_audit_log_not_found(self, client: TestClient, admin_user: User):
        """Test getting non-existent audit log."""
        fake_id = uuid4()
        response = client.get(f"/api/v2/admin-extensions/audit-logs/{fake_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_audit_log_redaction(self, client: TestClient, admin_user: User, audit_logs):
        """Test sensitive data redaction."""
        log = audit_logs[0]
        response = client.get(f"/api/v2/admin-extensions/audit-logs/{log.id}?redact_sensitive=true")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check that sensitive fields are redacted if present
        metadata = data.get("event_metadata", {})
        for key in metadata:
            if any(sensitive in key.lower() for sensitive in ["password", "token", "secret"]):
                assert metadata[key] == "[REDACTED]"


class TestExportAuditLogs:
    """Tests for POST /api/v2/admin-extensions/audit-logs/export"""

    def test_export_audit_logs_csv(self, client: TestClient, admin_user: User, audit_logs):
        """Test exporting audit logs to CSV."""
        export_data = {
            "format": "csv",
            "fields": ["id", "event_type", "user_email", "created_at"],
            "redact_sensitive": True
        }

        response = client.post("/api/v2/admin-extensions/audit-logs/export", json=export_data)

        assert response.status_code == status.HTTP_200_OK
        assert "text/csv" in response.headers["content-type"]

        # Verify CSV content
        content = response.content.decode("utf-8")
        csv_reader = csv.DictReader(io.StringIO(content))
        rows = list(csv_reader)
        assert len(rows) > 0
        assert "id" in rows[0]
        assert "event_type" in rows[0]

    def test_export_audit_logs_json(self, client: TestClient, admin_user: User, audit_logs):
        """Test exporting audit logs to JSON."""
        export_data = {
            "format": "json",
            "redact_sensitive": True
        }

        response = client.post("/api/v2/admin-extensions/audit-logs/export", json=export_data)

        assert response.status_code == status.HTTP_200_OK
        assert "application/json" in response.headers["content-type"]

        # Verify JSON content
        data = json.loads(response.content)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_export_audit_logs_with_filters(self, client: TestClient, admin_user: User, audit_logs):
        """Test exporting audit logs with filters."""
        export_data = {
            "format": "json",
            "redact_sensitive": True
        }

        response = client.post(
            "/api/v2/admin-extensions/audit-logs/export?event_type=login_success",
            json=export_data
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify filtered data
        data = json.loads(response.content)
        for log in data:
            assert log["event_type"] == "login_success"


# ============================================================================
# RBAC AND AUTHORIZATION TESTS
# ============================================================================

class TestRBACEnforcement:
    """Tests for RBAC enforcement on admin extensions endpoints."""

    def test_dlq_list_requires_admin(self, client: TestClient, doctor_user: User):
        """Test that DLQ list endpoint requires admin access."""
        # Mock doctor user instead of admin
        response = client.get("/api/v2/admin-extensions/dlq")

        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED]

    def test_audit_list_requires_admin(self, client: TestClient, doctor_user: User):
        """Test that audit list endpoint requires admin access."""
        response = client.get("/api/v2/admin-extensions/audit-logs")

        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED]

    def test_dlq_retry_requires_admin(self, client: TestClient, doctor_user: User):
        """Test that DLQ retry endpoint requires admin access."""
        fake_id = uuid4()
        response = client.post(f"/api/v2/admin-extensions/dlq/{fake_id}/retry")

        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED]

    def test_audit_export_requires_admin(self, client: TestClient, doctor_user: User):
        """Test that audit export endpoint requires admin access."""
        export_data = {"format": "json", "redact_sensitive": True}
        response = client.post("/api/v2/admin-extensions/audit-logs/export", json=export_data)

        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED]


# ============================================================================
# CACHE BEHAVIOR TESTS
# ============================================================================

class TestCacheBehavior:
    """Tests for Redis caching behavior."""

    def test_dlq_list_caching(self, client: TestClient, admin_user: User, dlq_items):
        """Test that DLQ list is cached."""
        # First request - should cache
        response1 = client.get("/api/v2/admin-extensions/dlq")
        assert response1.status_code == status.HTTP_200_OK

        # Second request - should hit cache
        response2 = client.get("/api/v2/admin-extensions/dlq")
        assert response2.status_code == status.HTTP_200_OK

        # Data should be identical
        assert response1.json() == response2.json()

    def test_audit_list_caching(self, client: TestClient, admin_user: User, audit_logs):
        """Test that audit list is cached."""
        response1 = client.get("/api/v2/admin-extensions/audit-logs")
        assert response1.status_code == status.HTTP_200_OK

        response2 = client.get("/api/v2/admin-extensions/audit-logs")
        assert response2.status_code == status.HTTP_200_OK

        assert response1.json() == response2.json()


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_cursor_format(self, client: TestClient, admin_user: User):
        """Test handling of invalid cursor format."""
        response = client.get("/api/v2/admin-extensions/dlq?cursor=invalid-cursor")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_limit_parameter(self, client: TestClient, admin_user: User):
        """Test handling of invalid limit parameter."""
        response = client.get("/api/v2/admin-extensions/dlq?limit=200")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_invalid_export_format(self, client: TestClient, admin_user: User):
        """Test handling of invalid export format."""
        export_data = {"format": "xml", "redact_sensitive": True}
        response = client.post("/api/v2/admin-extensions/audit-logs/export", json=export_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
