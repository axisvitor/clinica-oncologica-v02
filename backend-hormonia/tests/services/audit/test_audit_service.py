"""
Unit tests for HIPAA Audit Service - Phase 3 Sprint 1

Tests cover:
- Event logging with tamper-proof checksums
- Integrity verification
- PHI access tracking
- Data modification tracking
- Compliance statistics
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.models.audit_log import AuditEventType
from app.services.audit import AuditService, AuditEventContext


from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
class TestAuditService:
    """Test suite for AuditService."""

    @pytest.mark.asyncio
    async def test_log_basic_event(self, db_session):
        """Test basic audit event logging."""
        # Arrange
        audit_service = AuditService(db_session)
        user_id = uuid4()

        context = AuditEventContext(
            user_id=user_id,
            user_email="test@example.com",
            ip_address="192.168.1.1",
            status="SUCCESS",
            description="Test event"
        )

        # Act
        audit_log = await audit_service.log_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            event_category="AUTHENTICATION",
            context=context
        )

        # Assert
        assert audit_log is not None
        assert audit_log.id is not None
        assert audit_log.event_type == AuditEventType.LOGIN_SUCCESS
        assert audit_log.event_category == "AUTHENTICATION"
        assert audit_log.user_id == user_id
        assert audit_log.user_email == "test@example.com"
        assert audit_log.ip_address == "192.168.1.1"
        assert audit_log.status == "SUCCESS"
        assert audit_log.checksum is not None  # Checksum auto-calculated by trigger
        assert audit_log.archive_eligible_at is not None  # Auto-set by trigger

    @pytest.mark.asyncio
    async def test_log_phi_access(self, db_session):
        """Test PHI access event logging."""
        # Arrange
        audit_service = AuditService(db_session)
        user_id = uuid4()
        patient_id = uuid4()

        context = AuditEventContext(
            user_id=user_id,
            resource_type="PATIENT",
            resource_id=patient_id,
            operation="READ",
            ip_address="192.168.1.1",
            status="SUCCESS",
            metadata={"patient_mrn": "12345", "accessed_fields": ["name", "dob"]}
        )

        # Act
        audit_log = await audit_service.log_event(
            event_type=AuditEventType.SUSPICIOUS_ACTIVITY,  # Placeholder
            event_category="PHI_ACCESS",
            context=context
        )

        # Assert
        assert audit_log.event_category == "PHI_ACCESS"
        assert audit_log.resource_type == "PATIENT"
        assert audit_log.resource_id == patient_id
        assert audit_log.operation == "READ"
        assert audit_log.event_metadata["patient_mrn"] == "12345"

    @pytest.mark.asyncio
    async def test_log_data_modification(self, db_session):
        """Test data modification event logging with before/after states."""
        # Arrange
        audit_service = AuditService(db_session)
        user_id = uuid4()
        patient_id = uuid4()

        before_state = {"name": "John Doe", "phone": "555-0100"}
        after_state = {"name": "John Doe", "phone": "555-0200"}

        context = AuditEventContext(
            user_id=user_id,
            resource_type="PATIENT",
            resource_id=patient_id,
            operation="UPDATE",
            changes_before=before_state,
            changes_after=after_state,
            status="SUCCESS"
        )

        # Act
        audit_log = await audit_service.log_event(
            event_type=AuditEventType.SUSPICIOUS_ACTIVITY,  # Placeholder
            event_category="DATA_MODIFICATION",
            context=context
        )

        # Assert
        assert audit_log.event_category == "DATA_MODIFICATION"
        assert audit_log.operation == "UPDATE"
        assert audit_log.changes_before == before_state
        assert audit_log.changes_after == after_state
        assert audit_log.changed_fields == ["phone"]  # Auto-calculated

    @pytest.mark.asyncio
    async def test_verify_integrity(self, db_session):
        """Test audit log integrity verification."""
        # Arrange
        audit_service = AuditService(db_session)

        # Create multiple audit logs
        for i in range(5):
            context = AuditEventContext(
                user_id=uuid4(),
                status="SUCCESS",
                description=f"Test event {i}"
            )
            await audit_service.log_event(
                event_type=AuditEventType.LOGIN_SUCCESS,
                event_category="AUTHENTICATION",
                context=context
            )

        # Act
        result = await audit_service.verify_integrity()

        # Assert
        assert result["total_checked"] == 5
        assert result["valid_count"] == 5
        assert result["invalid_count"] == 0
        assert result["chain_breaks"] == 0
        assert result["has_tampering"] is False
        assert result["integrity_score"] == 100.0

    @pytest.mark.asyncio
    async def test_get_phi_access_logs(self, db_session):
        """Test retrieving PHI access logs."""
        # Arrange
        audit_service = AuditService(db_session)
        patient_id = uuid4()

        # Create PHI access logs
        for i in range(3):
            context = AuditEventContext(
                user_id=uuid4(),
                resource_type="PATIENT",
                resource_id=patient_id,
                operation="READ",
                status="SUCCESS"
            )
            await audit_service.log_event(
                event_type=AuditEventType.SUSPICIOUS_ACTIVITY,
                event_category="PHI_ACCESS",
                context=context
            )

        # Act
        logs = await audit_service.get_phi_access_logs(
            resource_type="PATIENT",
            resource_id=patient_id
        )

        # Assert
        assert len(logs) == 3
        for log in logs:
            assert log.event_category == "PHI_ACCESS"
            assert log.resource_type == "PATIENT"
            assert log.resource_id == patient_id

    @pytest.mark.asyncio
    async def test_get_compliance_statistics(self, db_session):
        """Test compliance statistics generation."""
        # Arrange
        audit_service = AuditService(db_session)
        start_date = now_sao_paulo_naive() - timedelta(days=1)
        end_date = now_sao_paulo_naive() + timedelta(days=1)

        # Create diverse audit logs
        categories = ["AUTHENTICATION", "PHI_ACCESS", "DATA_MODIFICATION"]
        for category in categories:
            for i in range(2):
                context = AuditEventContext(
                    user_id=uuid4(),
                    status="SUCCESS" if i == 0 else "FAILURE"
                )
                await audit_service.log_event(
                    event_type=AuditEventType.LOGIN_SUCCESS if i == 0 else AuditEventType.LOGIN_FAILURE,
                    event_category=category,
                    context=context
                )

        # Act
        stats = await audit_service.get_compliance_statistics(start_date, end_date)

        # Assert
        assert stats["total_events"] == 6
        assert stats["events_by_category"]["AUTHENTICATION"] == 2
        assert stats["events_by_category"]["PHI_ACCESS"] == 2
        assert stats["events_by_category"]["DATA_MODIFICATION"] == 2
        assert stats["failed_events"] == 3
        assert stats["compliance_rate"] == 50.0

    @pytest.mark.asyncio
    async def test_calculate_changed_fields(self):
        """Test changed fields calculation."""
        # Arrange
        before = {"name": "John", "age": 30, "city": "NYC"}
        after = {"name": "John", "age": 31, "city": "LA"}

        # Act
        changed = AuditService._calculate_changed_fields(before, after)

        # Assert
        assert set(changed) == {"age", "city"}

    def test_calculate_checksum(self):
        """Test checksum calculation."""
        # Arrange
        data = {"user_id": "123", "event": "login"}

        # Act
        checksum = AuditService.calculate_checksum(data)

        # Assert
        assert len(checksum) == 64  # SHA-256 produces 64 hex characters
        assert isinstance(checksum, str)

        # Same data should produce same checksum
        checksum2 = AuditService.calculate_checksum(data)
        assert checksum == checksum2

    def test_hash_session_token(self):
        """Test session token hashing."""
        # Arrange
        token = "my-secret-session-token"

        # Act
        hashed = AuditService.hash_session_token(token)

        # Assert
        assert len(hashed) == 64  # SHA-256
        assert hashed != token  # Should be hashed, not plaintext