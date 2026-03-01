"""
Integration tests for cleanup_expired_quiz_sessions_task.
Tests HIGH-004: Celery task for cleaning up expired quiz sessions.
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import Mock, patch

from app.models.quiz import QuizSession, QuizTemplate
from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.models.alert import Alert, AlertSeverity
from app.utils.timezone import now_sao_paulo
from app.tasks.quiz_flow.cleanup_tasks import (
    cleanup_expired_quiz_sessions_task,
    _notify_doctor_of_expired_session,
    _resume_patient_flow_after_expiration
)


class TestCleanupExpiredQuizSessionsTask:
    """Test cleanup_expired_quiz_sessions_task Celery task."""

    @patch('app.tasks.quiz_flow.cleanup_tasks.get_scoped_session')
    @patch('app.tasks.quiz_flow.cleanup_tasks._notify_doctor_of_expired_session')
    @patch('app.tasks.quiz_flow.cleanup_tasks._resume_patient_flow_after_expiration')
    def test_cleanup_marks_expired_sessions(
        self,
        mock_resume_flow,
        mock_notify_doctor,
        mock_get_scoped_session,
        db_with_expired_session
    ):
        """Test task marks expired sessions correctly."""
        db, expired_session, patient = db_with_expired_session
        mock_get_scoped_session.return_value.__enter__.return_value = db
        mock_get_scoped_session.return_value.__exit__.return_value = False
        mock_notify_doctor.return_value = True
        mock_resume_flow.return_value = True

        # Run task
        result = cleanup_expired_quiz_sessions_task(max_age_hours=48)

        # Verify session was marked as expired
        db.refresh(expired_session)
        assert expired_session.status == 'expired'
        assert expired_session.completed_at is not None
        assert result['success'] is True
        assert result['cleaned_sessions'] >= 1

    @patch('app.tasks.quiz_flow.cleanup_tasks.get_scoped_session')
    @patch('app.tasks.quiz_flow.cleanup_tasks._notify_doctor_of_expired_session')
    @patch('app.tasks.quiz_flow.cleanup_tasks._resume_patient_flow_after_expiration')
    def test_cleanup_updates_session_metadata(
        self,
        mock_resume_flow,
        mock_notify_doctor,
        mock_get_scoped_session,
        db_with_expired_session
    ):
        """Test task updates session metadata with expiration info."""
        db, expired_session, patient = db_with_expired_session
        mock_get_scoped_session.return_value.__enter__.return_value = db
        mock_get_scoped_session.return_value.__exit__.return_value = False
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

    @patch('app.tasks.quiz_flow.cleanup_tasks.get_scoped_session')
    @patch('app.tasks.quiz_flow.cleanup_tasks._notify_doctor_of_expired_session')
    @patch('app.tasks.quiz_flow.cleanup_tasks._resume_patient_flow_after_expiration')
    def test_cleanup_calls_notification_function(
        self,
        mock_resume_flow,
        mock_notify_doctor,
        mock_get_scoped_session,
        db_with_expired_session
    ):
        """Test task calls doctor notification function."""
        db, expired_session, patient = db_with_expired_session
        mock_get_scoped_session.return_value.__enter__.return_value = db
        mock_get_scoped_session.return_value.__exit__.return_value = False
        mock_notify_doctor.return_value = True
        mock_resume_flow.return_value = True

        # Run task
        result = cleanup_expired_quiz_sessions_task(max_age_hours=48)

        # Verify notification function was called
        assert mock_notify_doctor.called
        assert result['notifications_sent'] >= 1

    @patch('app.tasks.quiz_flow.cleanup_tasks.get_scoped_session')
    @patch('app.tasks.quiz_flow.cleanup_tasks._notify_doctor_of_expired_session')
    @patch('app.tasks.quiz_flow.cleanup_tasks._resume_patient_flow_after_expiration')
    def test_cleanup_calls_flow_resumption_function(
        self,
        mock_resume_flow,
        mock_notify_doctor,
        mock_get_scoped_session,
        db_with_expired_session
    ):
        """Test task calls flow resumption function."""
        db, expired_session, patient = db_with_expired_session
        mock_get_scoped_session.return_value.__enter__.return_value = db
        mock_get_scoped_session.return_value.__exit__.return_value = False
        mock_notify_doctor.return_value = True
        mock_resume_flow.return_value = True

        # Run task
        result = cleanup_expired_quiz_sessions_task(max_age_hours=48)

        # Verify flow resumption function was called
        assert mock_resume_flow.called
        assert result['flows_resumed'] >= 1

    @patch('app.tasks.quiz_flow.cleanup_tasks.get_scoped_session')
    def test_cleanup_does_not_affect_active_sessions(
        self,
        mock_get_scoped_session,
        db_with_active_session
    ):
        """Test task doesn't affect sessions that haven't expired."""
        db, active_session = db_with_active_session
        mock_get_scoped_session.return_value.__enter__.return_value = db
        mock_get_scoped_session.return_value.__exit__.return_value = False

        # Run task
        result = cleanup_expired_quiz_sessions_task(max_age_hours=48)

        # Verify session remains unchanged
        db.refresh(active_session)
        assert active_session.status == 'started'
        assert active_session.completed_at is None
        assert result['cleaned_sessions'] >= 0

    @patch('app.tasks.quiz_flow.cleanup_tasks.get_scoped_session')
    def test_cleanup_does_not_affect_completed_sessions(
        self,
        mock_get_scoped_session,
        db_with_completed_session
    ):
        """Test task doesn't affect already completed sessions."""
        db, completed_session = db_with_completed_session
        mock_get_scoped_session.return_value.__enter__.return_value = db
        mock_get_scoped_session.return_value.__exit__.return_value = False

        original_status = completed_session.status
        original_completed_at = completed_session.completed_at

        # Run task
        result = cleanup_expired_quiz_sessions_task(max_age_hours=48)

        # Verify session remains unchanged
        db.refresh(completed_session)
        assert completed_session.status == original_status
        current_completed_at = completed_session.completed_at
        current_naive = (
            current_completed_at.replace(tzinfo=None)
            if current_completed_at and current_completed_at.tzinfo
            else current_completed_at
        )
        original_naive = (
            original_completed_at.replace(tzinfo=None)
            if original_completed_at and original_completed_at.tzinfo
            else original_completed_at
        )
        assert current_naive == original_naive
        assert result['cleaned_sessions'] >= 0

    @patch('app.tasks.quiz_flow.cleanup_tasks.get_scoped_session')
    @patch('app.tasks.quiz_flow.cleanup_tasks._notify_doctor_of_expired_session')
    @patch('app.tasks.quiz_flow.cleanup_tasks._resume_patient_flow_after_expiration')
    def test_cleanup_handles_errors_gracefully(
        self,
        mock_resume_flow,
        mock_notify_doctor,
        mock_get_scoped_session,
        db_with_expired_session
    ):
        """Test task handles errors without crashing."""
        db, expired_session, patient = db_with_expired_session
        mock_get_scoped_session.return_value.__enter__.return_value = db
        mock_get_scoped_session.return_value.__exit__.return_value = False
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

    @patch('app.tasks.quiz_flow.cleanup_tasks.get_scoped_session')
    @patch('app.tasks.quiz_flow.cleanup_tasks._notify_doctor_of_expired_session')
    @patch('app.tasks.quiz_flow.cleanup_tasks._resume_patient_flow_after_expiration')
    def test_cleanup_returns_detailed_results(
        self,
        mock_resume_flow,
        mock_notify_doctor,
        mock_get_scoped_session,
        db_with_expired_session
    ):
        """Test task returns detailed results."""
        db, expired_session, patient = db_with_expired_session
        mock_get_scoped_session.return_value.__enter__.return_value = db
        mock_get_scoped_session.return_value.__exit__.return_value = False
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
        assert len(result['session_details']) >= 1

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

    def test_creates_alert_with_correct_data(self, db, sample_expired_session, sample_patient):
        """Test notification persists alert with canonical schema fields."""
        result = _notify_doctor_of_expired_session(
            db=db,
            session=sample_expired_session,
            patient=sample_patient
        )

        alert = (
            db.query(Alert)
            .filter(
                Alert.patient_id == sample_expired_session.patient_id,
                Alert.alert_type == "quiz_expired",
            )
            .order_by(Alert.created_at.desc())
            .first()
        )

        assert alert is not None
        assert alert.patient_id == sample_expired_session.patient_id
        assert alert.alert_type == "quiz_expired"
        assert alert.severity == AlertSeverity.MEDIUM
        assert "Quiz Session Expired" in alert.description
        assert result is True

    def test_includes_completion_rate_in_alert(self, db, sample_expired_session, sample_patient):
        """Test notification includes completion rate."""
        # Set some answered questions
        sample_expired_session.answered_questions = 5
        sample_expired_session.total_questions = 10

        _notify_doctor_of_expired_session(
            db=db,
            session=sample_expired_session,
            patient=sample_patient
        )

        alert = (
            db.query(Alert)
            .filter(
                Alert.patient_id == sample_expired_session.patient_id,
                Alert.alert_type == "quiz_expired",
            )
            .order_by(Alert.created_at.desc())
            .first()
        )
        assert alert is not None
        assert "5 of 10 questions" in alert.description
        assert alert.data["completion_rate"] == 50.0


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
def db(db_session):
    """Database session fixture backed by the shared test session."""
    yield db_session


@pytest.fixture
def db_with_expired_session(db):
    """Create database with an expired quiz session."""
    patient = Patient(
        id=uuid4(),
        name="Test Patient",
        email="test@example.com",
        phone="+1234567890"
    )
    template = QuizTemplate(
        id=uuid4(),
        name=f"Test Template {uuid4().hex[:8]}",
        version="1.0",
        questions={"questions": [{"id": "q1"}, {"id": "q2"}]}
    )
    db.add(patient)
    db.add(template)
    db.flush()

    current_time = now_sao_paulo()
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
        name="Test Patient",
        email="test@example.com",
        phone="+1234567890"
    )
    template = QuizTemplate(
        id=uuid4(),
        name=f"Test Template {uuid4().hex[:8]}",
        version="1.0",
        questions={"questions": []}
    )
    db.add(patient)
    db.add(template)
    db.flush()

    current_time = now_sao_paulo()
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
        name="Test Patient",
        email="test@example.com",
        phone="+1234567890"
    )
    template = QuizTemplate(
        id=uuid4(),
        name=f"Test Template {uuid4().hex[:8]}",
        version="1.0",
        questions={"questions": []}
    )
    db.add(patient)
    db.add(template)
    db.flush()

    current_time = now_sao_paulo()
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
        name="Test Patient",
        email="test@example.com",
        phone="+1234567890"
    )
    template = QuizTemplate(
        id=uuid4(),
        name=f"Test Template {uuid4().hex[:8]}",
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
        started_at=now_sao_paulo() - timedelta(hours=50),
        expiration_date=now_sao_paulo() - timedelta(hours=2),
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
        name="Test Patient",
        email="test@example.com",
        phone="+1234567890"
    )
    db.add(patient)
    db.commit()
    return patient


@pytest.fixture
def sample_flow_state(db, sample_patient):
    """Sample flow state."""
    from app.models.flow import FlowKind, FlowTemplateVersion

    flow_kind = FlowKind(
        id=uuid4(),
        kind_key=f"quiz_mensal_{uuid4().hex[:8]}",
        display_name="Quiz Mensal",
        is_active=True,
    )
    db.add(flow_kind)
    db.flush()

    template_version = FlowTemplateVersion(
        id=uuid4(),
        flow_kind_id=flow_kind.id,
        version_number=1,
        template_name="Quiz Mensal v1",
        is_active=True,
        is_draft=False,
        steps=[],
    )
    db.add(template_version)
    db.flush()

    flow_state = PatientFlowState(
        id=uuid4(),
        patient_id=sample_patient.id,
        flow_template_version_id=template_version.id,
        current_day=15,
        state_data={'waiting_for_quiz': True}
    )
    db.add(flow_state)
    db.commit()
    return flow_state
