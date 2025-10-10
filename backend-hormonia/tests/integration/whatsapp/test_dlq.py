"""
Integration tests for Dead Letter Queue (DLQ) functionality.
Tests full workflow from message failure to DLQ routing, review, and retry.
"""
import pytest
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.message import Message, MessageType, MessageDirection, MessageStatus
from app.models.patient import Patient, FlowState
from app.models.user import User, UserRole
from app.models.failed_message import FailedMessage, FailureReason, DLQStatus
from app.integrations.whatsapp.queue.dlq import DLQHandler
from app.services.message_scheduler import MessageScheduler
from app.exceptions import NotFoundError, ValidationError


@pytest.fixture
def test_patient(db_session: Session) -> Patient:
    """Create a test patient."""
    patient = Patient(
        id=uuid4(),
        name="Test Patient",
        phone="+5511999999999",
        email="test@example.com",
        flow_state=FlowState.ACTIVE,
        doctor_id=uuid4()  # Assuming doctor exists
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


@pytest.fixture
def test_admin(db_session: Session) -> User:
    """Create a test admin user."""
    admin = User(
        id=uuid4(),
        email="admin@clinic.com",
        firebase_uid=f"test_admin_{uuid4()}",
        role=UserRole.ADMIN,
        is_active=True
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def failed_message(db_session: Session, test_patient: Patient) -> Message:
    """Create a failed message."""
    message = Message(
        id=uuid4(),
        patient_id=test_patient.id,
        direction=MessageDirection.OUTBOUND,
        type=MessageType.TEXT,
        content="Test message that failed",
        status=MessageStatus.FAILED,
        retry_count=3,
        message_metadata={"flow_context": {"flow_day": 1}}
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)
    return message


@pytest.fixture
def dlq_handler(db_session: Session) -> DLQHandler:
    """Create DLQ handler instance."""
    return DLQHandler(db_session)


class TestDLQRouting:
    """Test routing messages to DLQ."""

    @pytest.mark.asyncio
    async def test_route_to_dlq_success(
        self,
        dlq_handler: DLQHandler,
        test_patient: Patient,
        failed_message: Message
    ):
        """Test successfully routing a message to DLQ."""
        failure_details = {
            "error": "Network timeout",
            "error_code": "ETIMEDOUT",
            "timestamp": datetime.utcnow().isoformat()
        }

        dlq_entry = await dlq_handler.route_to_dlq(
            message_id=failed_message.id,
            patient_id=test_patient.id,
            content=failed_message.content,
            whatsapp_phone=test_patient.phone,
            failure_reason=FailureReason.TIMEOUT,
            failure_details=failure_details,
            retry_count=3,
            metadata=failed_message.message_metadata
        )

        assert dlq_entry is not None
        assert dlq_entry.patient_id == test_patient.id
        assert dlq_entry.original_message_id == failed_message.id
        assert dlq_entry.failure_reason == FailureReason.TIMEOUT
        assert dlq_entry.retry_count == 3
        assert dlq_entry.dlq_status == DLQStatus.PENDING_REVIEW
        assert dlq_entry.failure_details == failure_details

    @pytest.mark.asyncio
    async def test_route_to_dlq_missing_patient(
        self,
        dlq_handler: DLQHandler
    ):
        """Test routing to DLQ with non-existent patient."""
        with pytest.raises(NotFoundError):
            await dlq_handler.route_to_dlq(
                message_id=uuid4(),
                patient_id=uuid4(),  # Non-existent
                content="Test message",
                whatsapp_phone="+5511999999999",
                failure_reason=FailureReason.NETWORK_ERROR,
                failure_details={},
                retry_count=3
            )

    @pytest.mark.asyncio
    async def test_route_to_dlq_missing_content(
        self,
        dlq_handler: DLQHandler,
        test_patient: Patient
    ):
        """Test routing to DLQ with empty content."""
        with pytest.raises(ValidationError):
            await dlq_handler.route_to_dlq(
                message_id=None,
                patient_id=test_patient.id,
                content="",  # Empty content
                whatsapp_phone=test_patient.phone,
                failure_reason=FailureReason.NETWORK_ERROR,
                failure_details={},
                retry_count=3
            )


class TestDLQReview:
    """Test DLQ review functionality."""

    @pytest.mark.asyncio
    async def test_get_pending_review(
        self,
        dlq_handler: DLQHandler,
        test_patient: Patient
    ):
        """Test getting messages pending review."""
        # Create multiple DLQ entries
        for i in range(3):
            await dlq_handler.route_to_dlq(
                message_id=None,
                patient_id=test_patient.id,
                content=f"Failed message {i}",
                whatsapp_phone=test_patient.phone,
                failure_reason=FailureReason.NETWORK_ERROR,
                failure_details={"error": f"Error {i}"},
                retry_count=3
            )

        pending_messages = await dlq_handler.get_pending_review(limit=10)

        assert len(pending_messages) >= 3
        assert all(msg.dlq_status == DLQStatus.PENDING_REVIEW for msg in pending_messages)

    @pytest.mark.asyncio
    async def test_review_message_approve(
        self,
        dlq_handler: DLQHandler,
        test_patient: Patient,
        test_admin: User
    ):
        """Test reviewing and approving a message for retry."""
        # Create DLQ entry
        dlq_entry = await dlq_handler.route_to_dlq(
            message_id=None,
            patient_id=test_patient.id,
            content="Failed message",
            whatsapp_phone=test_patient.phone,
            failure_reason=FailureReason.NETWORK_ERROR,
            failure_details={},
            retry_count=3
        )

        # Review and approve
        reviewed_message = await dlq_handler.review_message(
            dlq_id=dlq_entry.id,
            reviewer_id=test_admin.id,
            approve_retry=True,
            notes="Network was down, safe to retry"
        )

        assert reviewed_message.dlq_status == DLQStatus.APPROVED_FOR_RETRY
        assert reviewed_message.reviewed_by == test_admin.id
        assert reviewed_message.reviewed_at is not None
        assert reviewed_message.review_notes == "Network was down, safe to retry"

    @pytest.mark.asyncio
    async def test_review_message_reject(
        self,
        dlq_handler: DLQHandler,
        test_patient: Patient,
        test_admin: User
    ):
        """Test reviewing and rejecting a message."""
        # Create DLQ entry
        dlq_entry = await dlq_handler.route_to_dlq(
            message_id=None,
            patient_id=test_patient.id,
            content="Failed message",
            whatsapp_phone=test_patient.phone,
            failure_reason=FailureReason.INVALID_PHONE,
            failure_details={},
            retry_count=3
        )

        # Review and reject
        reviewed_message = await dlq_handler.review_message(
            dlq_id=dlq_entry.id,
            reviewer_id=test_admin.id,
            approve_retry=False,
            notes="Invalid phone number, cannot retry"
        )

        assert reviewed_message.dlq_status == DLQStatus.UNDER_REVIEW
        assert reviewed_message.reviewed_by == test_admin.id


class TestDLQRequeue:
    """Test DLQ requeue functionality."""

    @pytest.mark.asyncio
    async def test_requeue_approved_message(
        self,
        dlq_handler: DLQHandler,
        test_patient: Patient,
        test_admin: User,
        db_session: Session
    ):
        """Test re-queuing an approved message."""
        # Create and approve DLQ entry
        dlq_entry = await dlq_handler.route_to_dlq(
            message_id=None,
            patient_id=test_patient.id,
            content="Failed message",
            whatsapp_phone=test_patient.phone,
            failure_reason=FailureReason.NETWORK_ERROR,
            failure_details={},
            retry_count=3
        )

        await dlq_handler.review_message(
            dlq_id=dlq_entry.id,
            reviewer_id=test_admin.id,
            approve_retry=True,
            notes="Approved for retry"
        )

        # Requeue
        result = await dlq_handler.requeue_for_retry(
            dlq_id=dlq_entry.id,
            immediate=False
        )

        assert result["dlq_id"] == str(dlq_entry.id)
        assert "new_message_id" in result
        assert "scheduled_for" in result
        assert result["requeue_count"] == 1

        # Verify DLQ entry updated
        db_session.refresh(dlq_entry)
        assert dlq_entry.dlq_status == DLQStatus.REQUEUED
        assert dlq_entry.requeue_count == 1
        assert dlq_entry.last_requeue_at is not None

        # Verify new message created
        new_message_id = UUID(result["new_message_id"])
        new_message = db_session.query(Message).filter(Message.id == new_message_id).first()
        assert new_message is not None
        assert new_message.content == dlq_entry.content
        assert new_message.status == MessageStatus.SCHEDULED

    @pytest.mark.asyncio
    async def test_requeue_unapproved_message(
        self,
        dlq_handler: DLQHandler,
        test_patient: Patient
    ):
        """Test re-queuing an unapproved message fails."""
        # Create DLQ entry without approval
        dlq_entry = await dlq_handler.route_to_dlq(
            message_id=None,
            patient_id=test_patient.id,
            content="Failed message",
            whatsapp_phone=test_patient.phone,
            failure_reason=FailureReason.NETWORK_ERROR,
            failure_details={},
            retry_count=3
        )

        # Requeue should work for PENDING_REVIEW status
        result = await dlq_handler.requeue_for_retry(
            dlq_id=dlq_entry.id,
            immediate=False
        )

        assert result is not None
        assert "new_message_id" in result


class TestDLQMetrics:
    """Test DLQ metrics and analytics."""

    @pytest.mark.asyncio
    async def test_get_dlq_metrics(
        self,
        dlq_handler: DLQHandler,
        test_patient: Patient
    ):
        """Test getting DLQ metrics."""
        # Create multiple failures with different reasons
        failures = [
            (FailureReason.NETWORK_ERROR, 2),
            (FailureReason.TIMEOUT, 3),
            (FailureReason.API_ERROR, 1)
        ]

        for reason, count in failures:
            for _ in range(count):
                await dlq_handler.route_to_dlq(
                    message_id=None,
                    patient_id=test_patient.id,
                    content="Failed message",
                    whatsapp_phone=test_patient.phone,
                    failure_reason=reason,
                    failure_details={},
                    retry_count=3
                )

        metrics = await dlq_handler.get_dlq_metrics(days_back=1)

        assert metrics["total_failures"] >= 6
        assert "failure_by_reason" in metrics
        assert metrics["failure_by_reason"]["network_error"] >= 2
        assert metrics["failure_by_reason"]["timeout"] >= 3
        assert metrics["failure_by_reason"]["api_error"] >= 1

    @pytest.mark.asyncio
    async def test_get_critical_failures(
        self,
        dlq_handler: DLQHandler,
        test_patient: Patient
    ):
        """Test getting critical failures."""
        # Create high-retry-count failure
        critical_entry = await dlq_handler.route_to_dlq(
            message_id=None,
            patient_id=test_patient.id,
            content="Critical failed message",
            whatsapp_phone=test_patient.phone,
            failure_reason=FailureReason.API_ERROR,
            failure_details={},
            retry_count=5  # High retry count
        )

        critical_failures = await dlq_handler.get_critical_failures(
            hours_back=1,
            limit=10
        )

        assert len(critical_failures) > 0
        assert any(f.id == critical_entry.id for f in critical_failures)
        assert all(f.retry_count >= 3 for f in critical_failures)


class TestMessageSchedulerDLQIntegration:
    """Test integration between MessageScheduler and DLQ."""

    @pytest.mark.asyncio
    async def test_categorize_failure_reason(self, db_session: Session):
        """Test failure reason categorization."""
        scheduler = MessageScheduler(db_session)

        # Test timeout
        assert scheduler._categorize_failure_reason(
            {"error": "Connection timed out"}
        ) == FailureReason.TIMEOUT

        # Test network error
        assert scheduler._categorize_failure_reason(
            {"error": "Network connection failed"}
        ) == FailureReason.NETWORK_ERROR

        # Test rate limit
        assert scheduler._categorize_failure_reason(
            {"error": "Rate limit exceeded", "error_code": 429}
        ) == FailureReason.RATE_LIMIT

        # Test invalid phone
        assert scheduler._categorize_failure_reason(
            {"error": "Invalid phone number"}
        ) == FailureReason.INVALID_PHONE

        # Test unknown
        assert scheduler._categorize_failure_reason(
            {"error": "Unknown error"}
        ) == FailureReason.UNKNOWN
