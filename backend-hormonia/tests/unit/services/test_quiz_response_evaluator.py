"""
Unit tests for QuizResponseEvaluator service.

Sprint 2 - Week 1, Task 3: Automatic Alert Evaluation
"""
import pytest
from uuid import uuid4
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from app.services.quiz_response_evaluator import QuizResponseEvaluator
from app.config.quiz_alert_rules import QUIZ_ALERT_RULES, AlertSeverity
from app.models.alert import Alert, AlertStatus, AlertSeverity as ModelAlertSeverity
from app.exceptions import ValidationError, DatabaseError


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock()


@pytest.fixture
def mock_alert_repository(mock_db):
    """Mock alert repository."""
    with patch('app.services.quiz_response_evaluator.AlertRepository') as mock:
        yield mock.return_value


@pytest.fixture
def mock_audit_service(mock_db):
    """Mock audit service."""
    with patch('app.services.quiz_response_evaluator.AuditService') as mock:
        mock.return_value.log_action = AsyncMock()
        yield mock.return_value


@pytest.fixture
def evaluator(mock_db):
    """QuizResponseEvaluator instance."""
    return QuizResponseEvaluator(mock_db)


@pytest.mark.asyncio
class TestQuizResponseEvaluator:
    """Test suite for QuizResponseEvaluator."""

    async def test_evaluate_critical_pain_score(self, evaluator, mock_alert_repository, mock_audit_service):
        """Test critical pain score triggers CRITICAL alert."""
        quiz_session_id = uuid4()
        patient_id = uuid4()
        responses = {
            "pain_scale": 9,
            "nausea_days": 1
        }

        # Mock alert creation
        mock_alert = Alert(
            id=uuid4(),
            patient_id=patient_id,
            alert_type="quiz_response",
            severity=ModelAlertSeverity.CRITICAL,
            description="Paciente relatou dor intensa (nível 9/10)",
            status=AlertStatus.PENDING,
            data={
                "quiz_session_id": str(quiz_session_id),
                "triggered_rule_id": "pain_score_critical"
            }
        )
        mock_alert_repository.create.return_value = mock_alert
        evaluator.alert_repository = mock_alert_repository
        evaluator.audit_service = mock_audit_service

        # Execute
        alerts, risk_score = await evaluator.evaluate_quiz_session(
            quiz_session_id, patient_id, responses
        )

        # Assertions
        assert len(alerts) == 1
        assert alerts[0].severity == ModelAlertSeverity.CRITICAL
        assert "dor intensa" in alerts[0].description.lower()
        assert risk_score == 50.0  # CRITICAL = 50 points
        mock_alert_repository.create.assert_called_once()

    async def test_evaluate_fever_with_chills(self, evaluator, mock_alert_repository, mock_audit_service):
        """Test fever with chills triggers CRITICAL alert."""
        quiz_session_id = uuid4()
        patient_id = uuid4()
        responses = {
            "has_fever": True,
            "has_chills": True,
            "pain_scale": 3
        }

        # Mock alert creation
        mock_alert = Alert(
            id=uuid4(),
            patient_id=patient_id,
            alert_type="quiz_response",
            severity=ModelAlertSeverity.CRITICAL,
            description="Febre com calafrios",
            status=AlertStatus.PENDING,
            data={"triggered_rule_id": "fever_with_chills"}
        )
        mock_alert_repository.create.return_value = mock_alert
        evaluator.alert_repository = mock_alert_repository
        evaluator.audit_service = mock_audit_service

        # Execute
        alerts, risk_score = await evaluator.evaluate_quiz_session(
            quiz_session_id, patient_id, responses
        )

        # Assertions
        assert len(alerts) == 1
        assert alerts[0].severity == ModelAlertSeverity.CRITICAL
        assert risk_score == 50.0

    async def test_evaluate_prolonged_nausea(self, evaluator, mock_alert_repository, mock_audit_service):
        """Test prolonged nausea triggers WARNING alert."""
        quiz_session_id = uuid4()
        patient_id = uuid4()
        responses = {
            "nausea_days": 5,
            "pain_scale": 2
        }

        # Mock alert creation
        mock_alert = Alert(
            id=uuid4(),
            patient_id=patient_id,
            alert_type="quiz_response",
            severity=ModelAlertSeverity.HIGH,  # WARNING mapped to HIGH
            description="Náusea prolongada",
            status=AlertStatus.PENDING,
            data={"triggered_rule_id": "prolonged_nausea"}
        )
        mock_alert_repository.create.return_value = mock_alert
        evaluator.alert_repository = mock_alert_repository
        evaluator.audit_service = mock_audit_service

        # Execute
        alerts, risk_score = await evaluator.evaluate_quiz_session(
            quiz_session_id, patient_id, responses
        )

        # Assertions
        assert len(alerts) == 1
        assert alerts[0].severity == ModelAlertSeverity.HIGH
        assert risk_score == 30.0  # WARNING = 30 points

    async def test_evaluate_multiple_severe_symptoms(self, evaluator, mock_alert_repository, mock_audit_service):
        """Test multiple severe symptoms trigger CRITICAL alert."""
        quiz_session_id = uuid4()
        patient_id = uuid4()
        responses = {
            "pain_scale": 8,
            "fatigue_scale": 9,
            "nausea_scale": 7
        }

        # Mock alert creation - should trigger both multiple_severe_symptoms and individual symptom alerts
        mock_alerts = [
            Alert(
                id=uuid4(),
                patient_id=patient_id,
                alert_type="quiz_response",
                severity=ModelAlertSeverity.CRITICAL,
                description="Dor intensa",
                status=AlertStatus.PENDING,
                data={"triggered_rule_id": "pain_score_critical"}
            ),
            Alert(
                id=uuid4(),
                patient_id=patient_id,
                alert_type="quiz_response",
                severity=ModelAlertSeverity.CRITICAL,
                description="Múltiplos sintomas severos",
                status=AlertStatus.PENDING,
                data={"triggered_rule_id": "multiple_severe_symptoms"}
            )
        ]
        mock_alert_repository.create.side_effect = mock_alerts
        evaluator.alert_repository = mock_alert_repository
        evaluator.audit_service = mock_audit_service

        # Execute
        alerts, risk_score = await evaluator.evaluate_quiz_session(
            quiz_session_id, patient_id, responses
        )

        # Assertions
        assert len(alerts) >= 1
        assert risk_score >= 50.0  # Multiple CRITICAL alerts

    async def test_normalize_responses_string_numbers(self, evaluator):
        """Test response normalization converts string numbers to floats."""
        responses = {
            "pain_scale": "7",
            "nausea_days": "4"
        }

        normalized = evaluator._normalize_responses(responses)

        assert normalized["pain_scale"] == 7.0
        assert normalized["nausea_days"] == 4.0

    async def test_normalize_responses_boolean_strings(self, evaluator):
        """Test response normalization converts boolean strings."""
        responses = {
            "has_fever": "yes",
            "has_chills": "sim",
            "has_bleeding": "no",
            "has_pain": "não"
        }

        normalized = evaluator._normalize_responses(responses)

        assert normalized["has_fever"] is True
        assert normalized["has_chills"] is True
        assert normalized["has_bleeding"] is False
        assert normalized["has_pain"] is False

    async def test_normalize_responses_nested_values(self, evaluator):
        """Test response normalization extracts nested values."""
        responses = {
            "pain_scale": {"value": 8},
            "nausea_days": {"response_value": 3}
        }

        normalized = evaluator._normalize_responses(responses)

        assert normalized["pain_scale"] == 8.0
        assert normalized["nausea_days"] == 3.0

    async def test_calculate_risk_score_single_critical(self, evaluator):
        """Test risk score calculation for single CRITICAL alert."""
        alerts = [
            Alert(
                id=uuid4(),
                patient_id=uuid4(),
                severity=ModelAlertSeverity.CRITICAL,
                alert_type="quiz_response",
                description="Test"
            )
        ]

        risk_score = evaluator._calculate_risk_score(alerts)

        assert risk_score == 50.0

    async def test_calculate_risk_score_multiple_alerts(self, evaluator):
        """Test risk score calculation for multiple alerts."""
        alerts = [
            Alert(
                id=uuid4(),
                patient_id=uuid4(),
                severity=ModelAlertSeverity.CRITICAL,
                alert_type="quiz_response",
                description="Critical"
            ),
            Alert(
                id=uuid4(),
                patient_id=uuid4(),
                severity=ModelAlertSeverity.HIGH,
                alert_type="quiz_response",
                description="Warning"
            ),
            Alert(
                id=uuid4(),
                patient_id=uuid4(),
                severity=ModelAlertSeverity.MEDIUM,
                alert_type="quiz_response",
                description="Info"
            )
        ]

        risk_score = evaluator._calculate_risk_score(alerts)

        # CRITICAL=50 + HIGH=30 + MEDIUM=10 = 90
        assert risk_score == 90.0

    async def test_calculate_risk_score_capped_at_100(self, evaluator):
        """Test risk score is capped at 100."""
        alerts = [
            Alert(
                id=uuid4(),
                patient_id=uuid4(),
                severity=ModelAlertSeverity.CRITICAL,
                alert_type="quiz_response",
                description="Critical 1"
            ),
            Alert(
                id=uuid4(),
                patient_id=uuid4(),
                severity=ModelAlertSeverity.CRITICAL,
                alert_type="quiz_response",
                description="Critical 2"
            ),
            Alert(
                id=uuid4(),
                patient_id=uuid4(),
                severity=ModelAlertSeverity.CRITICAL,
                alert_type="quiz_response",
                description="Critical 3"
            )
        ]

        risk_score = evaluator._calculate_risk_score(alerts)

        # Would be 150 but capped at 100
        assert risk_score == 100.0

    async def test_evaluate_no_alerts(self, evaluator, mock_alert_repository, mock_audit_service):
        """Test evaluation with responses that don't trigger any alerts."""
        quiz_session_id = uuid4()
        patient_id = uuid4()
        responses = {
            "pain_scale": 2,
            "nausea_days": 1,
            "fatigue_level": 3
        }

        evaluator.alert_repository = mock_alert_repository
        evaluator.audit_service = mock_audit_service

        # Execute
        alerts, risk_score = await evaluator.evaluate_quiz_session(
            quiz_session_id, patient_id, responses
        )

        # Assertions
        assert len(alerts) == 0
        assert risk_score == 0.0
        mock_alert_repository.create.assert_not_called()

    async def test_validation_errors(self, evaluator):
        """Test validation errors for invalid inputs."""
        # Missing quiz_session_id
        with pytest.raises(ValidationError, match="quiz_session_id is required"):
            await evaluator.evaluate_quiz_session(None, uuid4(), {})

        # Missing patient_id
        with pytest.raises(ValidationError, match="patient_id is required"):
            await evaluator.evaluate_quiz_session(uuid4(), None, {})

        # Empty responses
        with pytest.raises(ValidationError, match="responses must be a non-empty dictionary"):
            await evaluator.evaluate_quiz_session(uuid4(), uuid4(), {})

    async def test_database_error_handling(self, evaluator, mock_alert_repository, mock_audit_service):
        """Test graceful handling of database errors during alert creation."""
        quiz_session_id = uuid4()
        patient_id = uuid4()
        responses = {
            "pain_scale": 8
        }

        # Mock database error
        mock_alert_repository.create.side_effect = DatabaseError("Database error")
        evaluator.alert_repository = mock_alert_repository
        evaluator.audit_service = mock_audit_service

        # Execute
        alerts, risk_score = await evaluator.evaluate_quiz_session(
            quiz_session_id, patient_id, responses
        )

        # Should return empty list and continue evaluation
        assert len(alerts) == 0
        assert risk_score == 0.0


@pytest.mark.asyncio
class TestAlertRules:
    """Test individual alert rules."""

    def test_all_rules_have_required_fields(self):
        """Test that all rules have required fields."""
        for rule in QUIZ_ALERT_RULES:
            assert hasattr(rule, 'rule_id')
            assert hasattr(rule, 'name')
            assert hasattr(rule, 'description')
            assert hasattr(rule, 'severity')
            assert hasattr(rule, 'condition')
            assert hasattr(rule, 'message_template')
            assert rule.rule_id
            assert rule.name
            assert rule.description

    def test_rule_ids_are_unique(self):
        """Test that all rule IDs are unique."""
        rule_ids = [rule.rule_id for rule in QUIZ_ALERT_RULES]
        assert len(rule_ids) == len(set(rule_ids))

    def test_severity_distribution(self):
        """Test that we have rules for all severity levels."""
        severities = {rule.severity for rule in QUIZ_ALERT_RULES}
        assert AlertSeverity.CRITICAL in severities
        assert AlertSeverity.WARNING in severities
        assert AlertSeverity.INFO in severities

    async def test_pain_rule_conditions(self):
        """Test pain score rule with various conditions."""
        rule = next(r for r in QUIZ_ALERT_RULES if r.rule_id == "pain_score_critical")

        # Should trigger
        assert rule.evaluate({"pain_scale": 7})
        assert rule.evaluate({"pain_scale": 10})
        assert rule.evaluate({"pain_level": 8})

        # Should not trigger
        assert not rule.evaluate({"pain_scale": 6})
        assert not rule.evaluate({"pain_scale": 0})
        assert not rule.evaluate({})

    async def test_fever_chills_rule(self):
        """Test fever with chills rule."""
        rule = next(r for r in QUIZ_ALERT_RULES if r.rule_id == "fever_with_chills")

        # Should trigger
        assert rule.evaluate({"has_fever": True, "has_chills": True})

        # Should not trigger
        assert not rule.evaluate({"has_fever": True, "has_chills": False})
        assert not rule.evaluate({"has_fever": False, "has_chills": True})
        assert not rule.evaluate({"has_fever": False, "has_chills": False})

    async def test_weight_loss_rule(self):
        """Test significant weight loss rule."""
        rule = next(r for r in QUIZ_ALERT_RULES if r.rule_id == "significant_weight_loss")

        # Should trigger
        assert rule.evaluate({"weight_loss_percent": 5})
        assert rule.evaluate({"weight_loss_percent": 10})

        # Should not trigger
        assert not rule.evaluate({"weight_loss_percent": 4})
        assert not rule.evaluate({"weight_loss_percent": 0})
