"""
Unit tests for quiz session expiration functionality.
Tests HIGH-004: Timeout and cleanup for abandoned quiz sessions.
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.quiz import QuizSession, QuizTemplate
from app.models.patient import Patient


class TestQuizSessionExpirationModel:
    """Test QuizSession model expiration features."""

    def test_expiration_date_field_exists(self, db: Session):
        """Test that expiration_date field is added to QuizSession."""
        # Create test data
        patient = Patient(
            id=uuid4(),
            first_name="Test",
            last_name="Patient",
            email="test@example.com",
            phone="+1234567890"
        )
        template = QuizTemplate(
            id=uuid4(),
            name="Test Template",
            version="1.0",
            questions={"questions": []}
        )
        db.add(patient)
        db.add(template)
        db.flush()

        # Create session with expiration_date
        expiration = datetime.now(timezone.utc) + timedelta(hours=48)
        session = QuizSession(
            id=uuid4(),
            patient_id=patient.id,
            quiz_template_id=template.id,
            status='started',
            started_at=datetime.now(timezone.utc),
            expiration_date=expiration
        )
        db.add(session)
        db.commit()

        # Verify expiration_date is set
        assert session.expiration_date is not None
        assert session.expiration_date == expiration

    def test_expired_status_validation(self, db: Session):
        """Test that 'expired' is a valid status."""
        patient = Patient(
            id=uuid4(),
            first_name="Test",
            last_name="Patient",
            email="test@example.com",
            phone="+1234567890"
        )
        template = QuizTemplate(
            id=uuid4(),
            name="Test Template",
            version="1.0",
            questions={"questions": []}
        )
        db.add(patient)
        db.add(template)
        db.flush()

        # Create session with expired status
        session = QuizSession(
            id=uuid4(),
            patient_id=patient.id,
            quiz_template_id=template.id,
            status='expired',
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )
        db.add(session)
        db.commit()

        # Verify status is set correctly
        assert session.status == 'expired'

    def test_invalid_status_raises_error(self, db: Session):
        """Test that invalid status raises ValueError."""
        patient = Patient(
            id=uuid4(),
            first_name="Test",
            last_name="Patient",
            email="test@example.com",
            phone="+1234567890"
        )
        template = QuizTemplate(
            id=uuid4(),
            name="Test Template",
            version="1.0",
            questions={"questions": []}
        )
        db.add(patient)
        db.add(template)
        db.flush()

        # Attempt to create session with invalid status
        with pytest.raises(ValueError, match="Status must be one of"):
            session = QuizSession(
                id=uuid4(),
                patient_id=patient.id,
                quiz_template_id=template.id,
                status='invalid_status',
                started_at=datetime.now(timezone.utc)
            )
            db.add(session)
            db.commit()

    def test_is_expired_property_with_expired_status(self, db: Session):
        """Test is_expired property returns True for expired status."""
        patient = Patient(
            id=uuid4(),
            first_name="Test",
            last_name="Patient",
            email="test@example.com",
            phone="+1234567890"
        )
        template = QuizTemplate(
            id=uuid4(),
            name="Test Template",
            version="1.0",
            questions={"questions": []}
        )
        db.add(patient)
        db.add(template)
        db.flush()

        session = QuizSession(
            id=uuid4(),
            patient_id=patient.id,
            quiz_template_id=template.id,
            status='expired',
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )
        db.add(session)
        db.commit()

        assert session.is_expired is True

    def test_is_expired_property_with_past_expiration_date(self, db: Session):
        """Test is_expired property returns True when expiration_date has passed."""
        patient = Patient(
            id=uuid4(),
            first_name="Test",
            last_name="Patient",
            email="test@example.com",
            phone="+1234567890"
        )
        template = QuizTemplate(
            id=uuid4(),
            name="Test Template",
            version="1.0",
            questions={"questions": []}
        )
        db.add(patient)
        db.add(template)
        db.flush()

        # Set expiration_date in the past
        past_expiration = datetime.now(timezone.utc) - timedelta(hours=1)
        session = QuizSession(
            id=uuid4(),
            patient_id=patient.id,
            quiz_template_id=template.id,
            status='started',
            started_at=datetime.now(timezone.utc) - timedelta(hours=49),
            expiration_date=past_expiration
        )
        db.add(session)
        db.commit()

        assert session.is_expired is True

    def test_is_expired_property_with_future_expiration_date(self, db: Session):
        """Test is_expired property returns False when expiration_date is in future."""
        patient = Patient(
            id=uuid4(),
            first_name="Test",
            last_name="Patient",
            email="test@example.com",
            phone="+1234567890"
        )
        template = QuizTemplate(
            id=uuid4(),
            name="Test Template",
            version="1.0",
            questions={"questions": []}
        )
        db.add(patient)
        db.add(template)
        db.flush()

        # Set expiration_date in the future
        future_expiration = datetime.now(timezone.utc) + timedelta(hours=24)
        session = QuizSession(
            id=uuid4(),
            patient_id=patient.id,
            quiz_template_id=template.id,
            status='started',
            started_at=datetime.now(timezone.utc),
            expiration_date=future_expiration
        )
        db.add(session)
        db.commit()

        assert session.is_expired is False

    def test_set_expiration_date_method(self, db: Session):
        """Test set_expiration_date method sets correct expiration time."""
        patient = Patient(
            id=uuid4(),
            first_name="Test",
            last_name="Patient",
            email="test@example.com",
            phone="+1234567890"
        )
        template = QuizTemplate(
            id=uuid4(),
            name="Test Template",
            version="1.0",
            questions={"questions": []}
        )
        db.add(patient)
        db.add(template)
        db.flush()

        started_at = datetime.now(timezone.utc)
        session = QuizSession(
            id=uuid4(),
            patient_id=patient.id,
            quiz_template_id=template.id,
            status='started',
            started_at=started_at
        )
        db.add(session)
        db.commit()

        # Set expiration date
        session.set_expiration_date(hours=48)
        db.commit()

        # Verify expiration_date is set correctly (within 1 second tolerance)
        expected_expiration = started_at + timedelta(hours=48)
        assert session.expiration_date is not None
        time_diff = abs((session.expiration_date - expected_expiration).total_seconds())
        assert time_diff < 1

    def test_set_expiration_date_custom_hours(self, db: Session):
        """Test set_expiration_date with custom hours."""
        patient = Patient(
            id=uuid4(),
            first_name="Test",
            last_name="Patient",
            email="test@example.com",
            phone="+1234567890"
        )
        template = QuizTemplate(
            id=uuid4(),
            name="Test Template",
            version="1.0",
            questions={"questions": []}
        )
        db.add(patient)
        db.add(template)
        db.flush()

        started_at = datetime.now(timezone.utc)
        session = QuizSession(
            id=uuid4(),
            patient_id=patient.id,
            quiz_template_id=template.id,
            status='started',
            started_at=started_at
        )
        db.add(session)
        db.commit()

        # Set expiration date to 24 hours
        session.set_expiration_date(hours=24)
        db.commit()

        expected_expiration = started_at + timedelta(hours=24)
        time_diff = abs((session.expiration_date - expected_expiration).total_seconds())
        assert time_diff < 1

    def test_set_expiration_date_does_not_override_existing(self, db: Session):
        """Test set_expiration_date doesn't override existing expiration_date."""
        patient = Patient(
            id=uuid4(),
            first_name="Test",
            last_name="Patient",
            email="test@example.com",
            phone="+1234567890"
        )
        template = QuizTemplate(
            id=uuid4(),
            name="Test Template",
            version="1.0",
            questions={"questions": []}
        )
        db.add(patient)
        db.add(template)
        db.flush()

        started_at = datetime.now(timezone.utc)
        existing_expiration = started_at + timedelta(hours=72)
        session = QuizSession(
            id=uuid4(),
            patient_id=patient.id,
            quiz_template_id=template.id,
            status='started',
            started_at=started_at,
            expiration_date=existing_expiration
        )
        db.add(session)
        db.commit()

        # Attempt to set new expiration date
        session.set_expiration_date(hours=48)
        db.commit()

        # Verify original expiration_date is preserved
        assert session.expiration_date == existing_expiration


class TestQuizSessionExpirationQuery:
    """Test querying expired quiz sessions."""

    def test_query_expired_sessions(self, db: Session):
        """Test querying sessions that have expired."""
        patient = Patient(
            id=uuid4(),
            first_name="Test",
            last_name="Patient",
            email="test@example.com",
            phone="+1234567890"
        )
        template = QuizTemplate(
            id=uuid4(),
            name="Test Template",
            version="1.0",
            questions={"questions": []}
        )
        db.add(patient)
        db.add(template)
        db.flush()

        current_time = datetime.now(timezone.utc)

        # Create expired session
        expired_session = QuizSession(
            id=uuid4(),
            patient_id=patient.id,
            quiz_template_id=template.id,
            status='started',
            started_at=current_time - timedelta(hours=50),
            expiration_date=current_time - timedelta(hours=2)
        )

        # Create active session
        active_session = QuizSession(
            id=uuid4(),
            patient_id=patient.id,
            quiz_template_id=template.id,
            status='started',
            started_at=current_time - timedelta(hours=1),
            expiration_date=current_time + timedelta(hours=47)
        )

        db.add(expired_session)
        db.add(active_session)
        db.commit()

        # Query expired sessions
        expired = db.query(QuizSession).filter(
            QuizSession.status == 'started',
            QuizSession.expiration_date.isnot(None),
            QuizSession.expiration_date <= current_time
        ).all()

        assert len(expired) == 1
        assert expired[0].id == expired_session.id

    def test_query_does_not_return_completed_sessions(self, db: Session):
        """Test query excludes completed sessions even if expiration_date passed."""
        patient = Patient(
            id=uuid4(),
            first_name="Test",
            last_name="Patient",
            email="test@example.com",
            phone="+1234567890"
        )
        template = QuizTemplate(
            id=uuid4(),
            name="Test Template",
            version="1.0",
            questions={"questions": []}
        )
        db.add(patient)
        db.add(template)
        db.flush()

        current_time = datetime.now(timezone.utc)

        # Create completed session with past expiration_date
        completed_session = QuizSession(
            id=uuid4(),
            patient_id=patient.id,
            quiz_template_id=template.id,
            status='completed',
            started_at=current_time - timedelta(hours=50),
            completed_at=current_time - timedelta(hours=3),
            expiration_date=current_time - timedelta(hours=2)
        )

        db.add(completed_session)
        db.commit()

        # Query expired sessions
        expired = db.query(QuizSession).filter(
            QuizSession.status == 'started',
            QuizSession.expiration_date.isnot(None),
            QuizSession.expiration_date <= current_time
        ).all()

        assert len(expired) == 0


# Fixtures
@pytest.fixture
def db():
    """Database session fixture."""
    # This would be provided by your test configuration
    # Placeholder for actual implementation
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
