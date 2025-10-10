"""
Integration tests for quiz alert evaluation workflow.

Sprint 2 - Week 1, Task 3: Automatic Alert Evaluation
"""
import pytest
from uuid import uuid4
from datetime import datetime

from app.models.quiz import QuizTemplate, QuizSession, QuizResponse
from app.models.patient import Patient
from app.models.alert import Alert, AlertStatus, AlertSeverity
from app.services.quiz import QuizSessionService
from app.services.quiz_response_evaluator import QuizResponseEvaluator
from app.repositories.alert import AlertRepository


@pytest.mark.asyncio
class TestQuizAlertEvaluationIntegration:
    """Integration tests for end-to-end quiz alert evaluation."""

    async def test_complete_quiz_session_generates_alerts(self, db_session, test_patient, test_quiz_template):
        """Test that completing a quiz session generates appropriate alerts."""
        # Create quiz session
        session = QuizSession(
            patient_id=test_patient.id,
            quiz_template_id=test_quiz_template.id,
            status="started",
            started_at=datetime.utcnow()
        )
        db_session.add(session)
        db_session.commit()

        # Add quiz responses with high pain score
        response1 = QuizResponse(
            patient_id=test_patient.id,
            quiz_template_id=test_quiz_template.id,
            quiz_session_id=session.id,
            question_id="pain_question",
            question_text="How is your pain?",
            response_type="scale",
            response_value="9",
            responded_at=datetime.utcnow()
        )

        response2 = QuizResponse(
            patient_id=test_patient.id,
            quiz_template_id=test_quiz_template.id,
            quiz_session_id=session.id,
            question_id="nausea_question",
            question_text="How many days of nausea?",
            response_type="number",
            response_value="5",
            responded_at=datetime.utcnow()
        )

        db_session.add_all([response1, response2])
        db_session.commit()

        # Complete quiz session
        quiz_service = QuizSessionService(db_session)
        completed_session = await quiz_service.complete_session(session.id)

        # Verify session is completed
        assert completed_session.status == "completed"

        # Verify alerts were generated
        alert_repository = AlertRepository(db_session)
        alerts = alert_repository.get_by_patient(test_patient.id)

        # Should have at least one alert for high pain
        pain_alerts = [a for a in alerts if "dor" in a.description.lower()]
        assert len(pain_alerts) > 0

        # Should have alert for prolonged nausea
        nausea_alerts = [a for a in alerts if "náusea" in a.description.lower()]
        assert len(nausea_alerts) > 0

        # Verify alert properties
        for alert in alerts:
            assert alert.patient_id == test_patient.id
            assert alert.quiz_session_id == session.id
            assert alert.alert_type == "quiz_response"
            assert alert.status == AlertStatus.PENDING
            assert "triggered_rule_id" in alert.data

    async def test_critical_alerts_for_high_risk_responses(self, db_session, test_patient, test_quiz_template):
        """Test that critical symptoms generate CRITICAL alerts."""
        # Create quiz session
        session = QuizSession(
            patient_id=test_patient.id,
            quiz_template_id=test_quiz_template.id,
            status="started",
            started_at=datetime.utcnow()
        )
        db_session.add(session)
        db_session.commit()

        # Add responses indicating high risk
        responses = [
            QuizResponse(
                patient_id=test_patient.id,
                quiz_template_id=test_quiz_template.id,
                quiz_session_id=session.id,
                question_id="fever",
                question_text="Do you have fever?",
                response_type="yes_no",
                response_value="yes",
                responded_at=datetime.utcnow()
            ),
            QuizResponse(
                patient_id=test_patient.id,
                quiz_template_id=test_quiz_template.id,
                quiz_session_id=session.id,
                question_id="chills",
                question_text="Do you have chills?",
                response_type="yes_no",
                response_value="yes",
                responded_at=datetime.utcnow()
            )
        ]
        db_session.add_all(responses)
        db_session.commit()

        # Complete session
        quiz_service = QuizSessionService(db_session)
        await quiz_service.complete_session(session.id)

        # Verify CRITICAL alert was generated
        alert_repository = AlertRepository(db_session)
        critical_alerts = alert_repository.get_by_severity(AlertSeverity.CRITICAL)

        fever_chills_alerts = [
            a for a in critical_alerts
            if a.patient_id == test_patient.id and "febre" in a.description.lower()
        ]

        assert len(fever_chills_alerts) > 0
        alert = fever_chills_alerts[0]
        assert alert.data.get("triggered_rule_id") == "fever_with_chills"

    async def test_no_alerts_for_normal_responses(self, db_session, test_patient, test_quiz_template):
        """Test that normal responses don't generate alerts."""
        # Create quiz session
        session = QuizSession(
            patient_id=test_patient.id,
            quiz_template_id=test_quiz_template.id,
            status="started",
            started_at=datetime.utcnow()
        )
        db_session.add(session)
        db_session.commit()

        # Add normal responses
        response = QuizResponse(
            patient_id=test_patient.id,
            quiz_template_id=test_quiz_template.id,
            quiz_session_id=session.id,
            question_id="pain_question",
            question_text="Pain level?",
            response_type="scale",
            response_value="2",
            responded_at=datetime.utcnow()
        )
        db_session.add(response)
        db_session.commit()

        # Get alert count before
        alert_repository = AlertRepository(db_session)
        alerts_before = alert_repository.get_by_patient(test_patient.id)
        count_before = len(alerts_before)

        # Complete session
        quiz_service = QuizSessionService(db_session)
        await quiz_service.complete_session(session.id)

        # Verify no new alerts
        alerts_after = alert_repository.get_by_patient(test_patient.id)
        count_after = len(alerts_after)

        assert count_after == count_before

    async def test_risk_score_calculation(self, db_session, test_patient, test_quiz_template):
        """Test that risk scores are calculated correctly."""
        # Create quiz session with multiple severe symptoms
        session = QuizSession(
            patient_id=test_patient.id,
            quiz_template_id=test_quiz_template.id,
            status="started",
            started_at=datetime.utcnow()
        )
        db_session.add(session)
        db_session.commit()

        # Add responses for multiple severe symptoms
        responses = [
            QuizResponse(
                patient_id=test_patient.id,
                quiz_template_id=test_quiz_template.id,
                quiz_session_id=session.id,
                question_id="pain_scale",
                question_text="Pain level?",
                response_type="scale",
                response_value="8",
                responded_at=datetime.utcnow()
            ),
            QuizResponse(
                patient_id=test_patient.id,
                quiz_template_id=test_quiz_template.id,
                quiz_session_id=session.id,
                question_id="fatigue_scale",
                question_text="Fatigue level?",
                response_type="scale",
                response_value="9",
                responded_at=datetime.utcnow()
            ),
            QuizResponse(
                patient_id=test_patient.id,
                quiz_template_id=test_quiz_template.id,
                quiz_session_id=session.id,
                question_id="nausea_scale",
                question_text="Nausea level?",
                response_type="scale",
                response_value="7",
                responded_at=datetime.utcnow()
            )
        ]
        db_session.add_all(responses)
        db_session.commit()

        # Complete session
        quiz_service = QuizSessionService(db_session)
        await quiz_service.complete_session(session.id)

        # Verify multiple alerts were generated
        alert_repository = AlertRepository(db_session)
        session_alerts = [
            a for a in alert_repository.get_by_patient(test_patient.id)
            if a.quiz_session_id == session.id
        ]

        # Should have multiple alerts
        assert len(session_alerts) >= 2

        # Risk score should be high due to multiple CRITICAL alerts
        evaluator = QuizResponseEvaluator(db_session)
        risk_score = evaluator._calculate_risk_score(session_alerts)
        assert risk_score >= 50.0  # At least one CRITICAL alert


@pytest.fixture
def test_patient(db_session):
    """Create test patient."""
    patient = Patient(
        id=uuid4(),
        name="Test Patient",
        email="test@example.com",
        phone="1234567890"
    )
    db_session.add(patient)
    db_session.commit()
    return patient


@pytest.fixture
def test_quiz_template(db_session):
    """Create test quiz template."""
    template = QuizTemplate(
        id=uuid4(),
        name="Symptom Assessment",
        version="1.0",
        questions=[
            {
                "id": "pain_question",
                "text": "Como está sua dor?",
                "type": "scale"
            },
            {
                "id": "nausea_question",
                "text": "Quantos dias de náusea?",
                "type": "number"
            }
        ],
        is_active=True
    )
    db_session.add(template)
    db_session.commit()
    return template
