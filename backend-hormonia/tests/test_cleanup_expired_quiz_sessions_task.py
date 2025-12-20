"""
Integration tests for cleanup_expired_quiz_sessions_task.
Tests HIGH-004: Celery task for cleaning up expired quiz sessions.
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import Mock, patch, MagicMock

from app.models.quiz import QuizSession, QuizTemplate
from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.tasks.quiz_flow import (
    cleanup_expired_quiz_sessions_task,
    _notify_doctor_of_expired_session,
    _resume_patient_flow_after_expiration
)


class TestCleanupExpiredQuizSessionsTask:
    """Test cleanup_expired_quiz_sessions_task Celery task."""

    @patch('app.tasks.quiz_flow.get_db')
    @patch('app.tasks.quiz_flow._notify_doctor_of_expired_session')
    @patch('app.tasks.quiz_flow._resume_patient_flow_after_expiration')
    def test_cleanup_marks_expired_sessions(
        self,
        mock_resume_flow,
        mock_notify_doctor,
        mock_get_db,
        db_with_expired_session
    ):
        """Test task marks expired sessions correctly."""
        db, expired_session, patient = db_with_expired_session
        mock_get_db.return_value.__next__ = Mock(return_value=db)
        mock_notify_doctor.return_value = True
        mock_resume_flow.return_value = True

        # Run task
        result = cleanup_expired_quiz_sessions_task(max_age_hours=48)

        # Verify session was marked as expired
        db.refresh(expired_session)
        assert expired_session.status == 'expired'
        assert expired_session.completed_at is not None
        assert result['success'] is True
        assert result['cleaned_sessions'] == 1

    @patch('app.tasks.quiz_flow.get_db')
    @patch('app.tasks.quiz_flow._notify_doctor_of_expired_session')
    @patch('app.tasks.quiz_flow._resume_patient_flow_after_expiration')
    def test_cleanup_updates_session_metadata(
        self,
        mock_resume_flow,
        mock_notify_doctor,
        mock_get_db,
        db_with_expired_session
    ):
        """Test task updates session metadata with expiration info."""
        db, expired_session, patient = db_with_expired_session
        mock_get_db.return_value.__next__ = Mock(return_value=db)
        mock_notify_doctor.return_value = True
        mock_resume_flow.return_value = True

        # Run task
        cleanup_expired_quiz_sessions_task(max_age_hours=48)

        # Verify metadata was updated
        db.refresh(expired_session)
        assert 'expired_at' in expired_session.session_metadata
        assert 'expiration_reason' in expired_session.session_metadata
        assert expired_session.session_metadata['expiration_reason'] == 'timeout'
        assert 'questions_answered' in expired_session.session_metadata
        assert 'total_questions' in expired_session.session_metadata

    @patch('app.tasks.quiz_flow.get_db')
    @patch('app.tasks.quiz_flow._notify_doctor_of_expired_session')
    @patch('app.tasks.quiz_flow._resume_patient_flow_after_expiration')
    def test_cleanup_calls_notification_function(
        self,
        mock_resume_flow,
        mock_notify_doctor,
        mock_get_db,
        db_with_expired_session
    ):
        """Test task calls doctor notification function."""
        db, expired_session, patient = db_with_expired_session
        mock_get_db.return_value.__next__ = Mock(return_value=db)
        mock_notify_doctor.return_value = True
        mock_resume_flow.return_value = True

        # Run task
        result = cleanup_expired_quiz_sessions_task(max_age_hours=48)

        # Verify notification function was called
        assert mock_notify_doctor.called
        assert result['notifications_sent'] == 1

    @patch('app.tasks.quiz_flow.get_db')
    @patch('app.tasks.quiz_flow._notify_doctor_of_expired_session')
    @patch('app.tasks.quiz_flow._resume_patient_flow_after_expiration')
    def test_cleanup_calls_flow_resumption_function(
        self,
        mock_resume_flow,
        mock_notify_doctor,
        mock_get_db,
        db_with_expired_session
    ):
        """Test task calls flow resumption function."""
        db, expired_session, patient = db_with_expired_session
        mock_get_db.return_value.__next__ = Mock(return_value=db)
        mock_notify_doctor.return_value = True
        mock_resume_flow.return_value = True

        # Run task
        result = cleanup_expired_quiz_sessions_task(max_age_hours=48)

        # Verify flow resumption function was called
        assert mock_resume_flow.called
        assert result['flows_resumed'] == 1

    @patch('app.tasks.quiz_flow.get_db')
    def test_cleanup_does_not_affect_active_sessions(
        self,
        mock_get_db,
        db_with_active_session
    ):
        """Test task doesn't affect sessions that haven't expired."""
        db, active_session = db_with_active_session
        mock_get_db.return_value.__next__ = Mock(return_value=db)

        # Run task
        result = cleanup_expired_quiz_sessions_task(max_age_hours=48)

        # Verify session remains unchanged
        db.refresh(active_session)
        assert active_session.status == 'started'
        assert active_session.completed_at is None
        assert result['cleaned_sessions'] == 0

    @patch('app.tasks.quiz_flow.get_db')
    def test_cleanup_does_not_affect_completed_sessions(
        self,
        mock_get_db,
        db_with_completed_session
    ):
        """Test task doesn't affect already completed sessions."""
        db, completed_session = db_with_completed_session
        mock_get_db.return_value.__next__ = Mock(return_value=db)

        original_status = completed_session.status
        original_completed_at = completed_session.completed_at

        # Run task
        result = cleanup_expired_quiz_sessions_task(max_age_hours=48)

        # Verify session remains unchanged
        db.refresh(completed_session)
        assert completed_session.status == original_status
        assert completed_session.completed_at == original_completed_at
        assert result['cleaned_sessions'] == 0

    @patch('app.tasks.quiz_flow.get_db')
    @patch('app.tasks.quiz_flow._notify_doctor_of_expired_session')
    @patch('app.tasks.quiz_flow._resume_patient_flow_after_expiration')
    def test_cleanup_handles_errors_gracefully(
        self,
        mock_resume_flow,
        mock_notify_doctor,
        mock_get_db,
        db_with_expired_session
    ):
        """Test task handles errors without crashing."""
        db, expired_session, patient = db_with_expired_session
        mock_get_db.return_value.__next__ = Mock(return_value=db)
        # Simulate notification failure
        mock_notify_doctor.side_effect = Exception("Notification service down")
        mock_resume_flow.return_value = True

        # Run task
        result = cleanup_expired_quiz_sessions_task(max_age_hours=48)

        # Verify task completes with error tracking
        assert result['success'] is True
        # Session should still be marked as expired
        db.refresh(expired_session)
        assert expired_session.status == 'expired'

    @patch('app.tasks.quiz_flow.get_db')
    @patch('app.tasks.quiz_flow._notify_doctor_of_expired_session')
    @patch('app.tasks.quiz_flow._resume_patient_flow_after_expiration')
    def test_cleanup_returns_detailed_results(
        self,
        mock_resume_flow,
        mock_notify_doctor,
        mock_get_db,
        db_with_expired_session
    ):
        """Test task returns detailed results."""
        db, expired_session, patient = db_with_expired_session
        mock_get_db.return_value.__next__ = Mock(return_value=db)
        mock_notify_doctor.return_value = True
        mock_resume_flow.return_value = True

        # Run task
        result = cleanup_expired_quiz_sessions_task(max_age_hours=48)

        # Verify result structure
        assert 'success' in result
        assert 'cleaned_sessions' in result
        assert 'notifications_sent' in result
        assert 'flows_resumed' in result
        assert 'errors' in result
        assert 'session_details' in result
        assert len(result['session_details']) == 1

        # Verify session details
        session_detail = result['session_details'][0]
        assert 'session_id' in session_detail
        assert 'patient_id' in session_detail
        assert 'patient_name' in session_detail
        assert 'started_at' in session_detail
        assert 'expired_at' in session_detail
        assert 'questions_answered' in session_detail


class TestNotifyDoctorOfExpiredSession:
    """Test _notify_doctor_of_expired_session function."""

    @patch('app.tasks.quiz_flow.AlertService')
    def test_creates_alert_with_correct_data(self, mock_alert_service, db, sample_expired_session, sample_patient):
        """Test notification creates alert with correct data."""
        mock_service_instance = MagicMock()
        mock_alert_service.return_value = mock_service_instance

        result = _notify_doctor_of_expired_session(
            db=db,
            session=sample_expired_session,
            patient=sample_patient
        )

        # Verify alert was created
        assert mock_service_instance.create_alert.called
        call_args = mock_service_instance.create_alert.call_args[0][0]

        assert call_args['patient_id'] == sample_expired_session.patient_id
        assert call_args['alert_type'] == 'quiz_expired'
        assert call_args['priority'] == 'medium'
        assert 'Quiz Session Expired' in call_args['title']
        assert result is True

    @patch('app.tasks.quiz_flow.AlertService')
    def test_includes_completion_rate_in_alert(self, mock_alert_service, db, sample_expired_session, sample_patient):
        """Test notification includes completion rate."""
        mock_service_instance = MagicMock()
        mock_alert_service.return_value = mock_service_instance

        # Set some answered questions
        sample_expired_session.answered_questions = 5
        sample_expired_session.total_questions = 10

        _notify_doctor_of_expired_session(
            db=db,
            session=sample_expired_session,
            patient=sample_patient
        )

        call_args = mock_service_instance.create_alert.call_args[0][0]
        assert '5 of 10 questions' in call_args['message']
        assert call_args['metadata']['completion_rate'] == 50.0


class TestResumePatientFlowAfterExpiration:
    """Test _resume_patient_flow_after_expiration function."""

    def test_updates_flow_state_correctly(self, db, sample_flow_state):
        """Test flow state is updated correctly."""
        result = _resume_patient_flow_after_expiration(
            db=db,
            patient_id=sample_flow_state.patient_id,
            quiz_session_id=uuid4()
        )

        db.refresh(sample_flow_state)
        assert result is True
        assert sample_flow_state.state_data['quiz_expired'] is True
        assert sample_flow_state.state_data['waiting_for_quiz'] is False
        assert 'flow_resumed_at' in sample_flow_state.state_data

    def test_handles_missing_flow_state(self, db):
        """Test handles case when flow state doesn't exist."""
        result = _resume_patient_flow_after_expiration(
            db=db,
            patient_id=uuid4(),
            quiz_session_id=uuid4()
        )

        assert result is False


# Fixtures
@pytest.fixture
def db():
    """Database session fixture."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def db_with_expired_session(db):
    """Create database with an expired quiz session."""
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
        questions={"questions": [{"id": "q1"}, {"id": "q2"}]}
    )
    db.add(patient)
    db.add(template)
    db.flush()

    current_time = datetime.now(timezone.utc)
    expired_session = QuizSession(
        id=uuid4(),
        patient_id=patient.id,
        quiz_template_id=template.id,
        status='started',
        started_at=current_time - timedelta(hours=50),
        expiration_date=current_time - timedelta(hours=2),
        answered_questions=1,
        total_questions=2
    )

    db.add(expired_session)
    db.commit()

    return db, expired_session, patient


@pytest.fixture
def db_with_active_session(db):
    """Create database with an active quiz session."""
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
    active_session = QuizSession(
        id=uuid4(),
        patient_id=patient.id,
        quiz_template_id=template.id,
        status='started',
        started_at=current_time - timedelta(hours=1),
        expiration_date=current_time + timedelta(hours=47)
    )

    db.add(active_session)
    db.commit()

    return db, active_session


@pytest.fixture
def db_with_completed_session(db):
    """Create database with a completed quiz session."""
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

    return db, completed_session


@pytest.fixture
def sample_expired_session(db):
    """Sample expired session."""
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
        status='started',
        started_at=datetime.now(timezone.utc) - timedelta(hours=50),
        expiration_date=datetime.now(timezone.utc) - timedelta(hours=2),
        answered_questions=0,
        total_questions=10
    )
    db.add(session)
    db.commit()
    return session


@pytest.fixture
def sample_patient(db):
    """Sample patient."""
    patient = Patient(
        id=uuid4(),
        first_name="Test",
        last_name="Patient",
        email="test@example.com",
        phone="+1234567890"
    )
    db.add(patient)
    db.commit()
    return patient


@pytest.fixture
def sample_flow_state(db, sample_patient):
    """Sample flow state."""
    flow_state = PatientFlowState(
        id=uuid4(),
        patient_id=sample_patient.id,
        flow_type='monthly_recurring',
        current_day=15,
        state_data={'waiting_for_quiz': True}
    )
    db.add(flow_state)
    db.commit()
    return flow_state
