"""
Unit tests for quiz alert → notification chain.

Tests cover the complete chain:
1. evaluate_quiz_session() with triggering responses creates Alert with correct data
2. Notification created for the correct doctor via patient.doctor_id
3. Severity mapping: config CRITICAL→URGENT, WARNING→HIGH, INFO→MEDIUM
4. No notification when patient has no doctor_id (alert still created)
5. Duplicate alert prevention for same session+rule
6. No alerts/notifications when no rules trigger
7. Alert serializer includes title, message, recommendation fields

Slice: S05 — Alertas do quiz mensal acionáveis para o médico
Milestone: M007
"""

import pytest
import asyncio
import logging
from uuid import uuid4, UUID
from unittest.mock import MagicMock, AsyncMock, patch, call
from datetime import datetime, timezone

from app.config.quiz_alert_rules import AlertSeverity as ConfigAlertSeverity
from app.models.alert import Alert, AlertSeverity as ModelAlertSeverity, AlertStatus
from app.models.notification import Notification, NotificationType, NotificationPriority
from app.models.patient import Patient
from app.domain.quizzes.evaluation.response_evaluator import QuizResponseEvaluator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_db():
    """
    Create a mock DB session following the shim pattern from
    test_sequential_message_handler.py.
    """
    db = MagicMock()
    # .query().filter().first() chain defaults to None
    db.query.return_value.filter.return_value.first.return_value = None
    db.add = MagicMock()
    db.commit = MagicMock()
    db.flush = MagicMock()
    db.rollback = MagicMock()
    db.refresh = MagicMock()
    return db


def _make_patient(doctor_id=None, patient_id=None):
    """Build a mock Patient with configurable doctor_id."""
    patient = MagicMock(spec=Patient)
    patient.id = patient_id or uuid4()
    patient.doctor_id = doctor_id
    patient.name = "Test Patient"
    return patient


def _non_triggering_responses():
    """Responses that do NOT trigger any alert rule.

    Key suppressions:
    - pain_scale=1 → below 5 (no moderate_pain or pain_score_critical)
    - sleep_quality=10 → above 3 (no sleep_disturbance)
    - has_fever=False, has_chills=False → no fever_with_chills
    - No other flags set → all bool rules evaluate False
    - No _scale/_level/_intensity fields above 3 → no mild_symptoms
    """
    return {
        "pain_scale": 1,
        "sleep_quality": 10,
        "has_fever": False,
        "has_chills": False,
        "anxiety_level": 0,
        "depression_score": 0,
        "decreased_appetite": False,
        "appetite_change": 0,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    return _make_mock_db()


@pytest.fixture
def doctor_id():
    return uuid4()


@pytest.fixture
def patient_id():
    return uuid4()


@pytest.fixture
def quiz_session_id():
    return uuid4()


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestQuizAlertNotificationChain:
    """Tests for the quiz response → alert → notification chain."""

    # ---- Test 1: Triggering responses create Alert with correct JSONB data ----

    @pytest.mark.asyncio
    async def test_evaluate_creates_alert_with_correct_data(
        self, mock_db, patient_id, quiz_session_id, doctor_id,
    ):
        """pain_scale ≥ 7 triggers pain_score_critical.
        Assert AlertRepository.create() is called, and alert has correct JSONB fields.
        """
        patient = _make_patient(doctor_id=doctor_id, patient_id=patient_id)

        # --- stub DB queries ---
        # 1st call: duplicate-guard query → no existing alert
        # 2nd call: patient query → our patient
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            None,      # duplicate check → no duplicate
            patient,   # patient lookup
        ]

        evaluator = QuizResponseEvaluator(mock_db)

        # Mock alert_repository.create to capture and return the alert
        created_alerts = []

        def capture_create(alert_obj):
            alert_obj.id = uuid4()  # simulate DB assigning id
            created_alerts.append(alert_obj)
            return alert_obj

        evaluator.alert_repository.create = MagicMock(side_effect=capture_create)

        # Mock async notification methods to avoid websocket import errors
        evaluator._notify_medical_team = AsyncMock()

        # Responses that trigger pain_score_critical (pain_scale ≥ 7, CRITICAL)
        responses = {**_non_triggering_responses(), "pain_scale": 9}

        alerts, risk_score = await evaluator.evaluate_quiz_session(
            quiz_session_id=quiz_session_id,
            patient_id=patient_id,
            responses=responses,
        )

        # At least one alert created (pain_score_critical triggers)
        assert len(alerts) >= 1

        # Find the pain_score_critical alert
        pain_alert = next(
            (a for a in alerts if a.data.get("triggered_rule_id") == "pain_score_critical"),
            None,
        )
        assert pain_alert is not None, (
            f"Expected pain_score_critical alert, got rule_ids: "
            f"{[a.data.get('triggered_rule_id') for a in alerts]}"
        )

        # Verify alert fields
        assert pain_alert.alert_type == "quiz_response"
        assert pain_alert.severity == ModelAlertSeverity.CRITICAL
        assert pain_alert.data["quiz_session_id"] == str(quiz_session_id)
        assert pain_alert.data["triggered_rule_id"] == "pain_score_critical"
        assert pain_alert.data["rule_name"] == "Dor Crítica"
        assert "recommendation" in pain_alert.data
        assert pain_alert.data["recommendation"] != ""

    # ---- Test 2: Notification created for correct doctor ----

    @pytest.mark.asyncio
    async def test_notification_created_for_correct_doctor(
        self, mock_db, patient_id, quiz_session_id, doctor_id,
    ):
        """After alert creation, a Notification is added for patient.doctor_id."""
        patient = _make_patient(doctor_id=doctor_id, patient_id=patient_id)

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            None,      # duplicate check
            patient,   # patient lookup
        ]

        evaluator = QuizResponseEvaluator(mock_db)

        def passthrough_create(alert_obj):
            alert_obj.id = uuid4()
            return alert_obj

        evaluator.alert_repository.create = MagicMock(side_effect=passthrough_create)
        evaluator._notify_medical_team = AsyncMock()

        responses = {**_non_triggering_responses(), "pain_scale": 9}

        await evaluator.evaluate_quiz_session(
            quiz_session_id=quiz_session_id,
            patient_id=patient_id,
            responses=responses,
        )

        # db.add() should have been called with a Notification instance
        notification_adds = [
            c for c in mock_db.add.call_args_list
            if isinstance(c[0][0], Notification)
        ]
        assert len(notification_adds) >= 1, (
            "Expected at least one Notification added via db.add(), "
            f"got {len(notification_adds)} notification adds"
        )

        notification = notification_adds[0][0][0]
        assert notification.user_id == doctor_id
        assert notification.related_patient_id == patient_id
        assert notification.notification_type == NotificationType.ALERT

    # ---- Test 3: Severity mapping across all three levels ----

    def test_severity_mapping_critical_to_urgent(self):
        """CRITICAL alert severity → URGENT notification priority."""
        evaluator = QuizResponseEvaluator.__new__(QuizResponseEvaluator)
        assert evaluator._map_notification_priority(ModelAlertSeverity.CRITICAL) == NotificationPriority.URGENT

    def test_severity_mapping_high_to_high(self):
        """HIGH alert severity (from config WARNING) → HIGH notification priority."""
        evaluator = QuizResponseEvaluator.__new__(QuizResponseEvaluator)
        assert evaluator._map_notification_priority(ModelAlertSeverity.HIGH) == NotificationPriority.HIGH

    def test_severity_mapping_medium_to_medium(self):
        """MEDIUM alert severity (from config INFO) → MEDIUM notification priority."""
        evaluator = QuizResponseEvaluator.__new__(QuizResponseEvaluator)
        assert evaluator._map_notification_priority(ModelAlertSeverity.MEDIUM) == NotificationPriority.MEDIUM

    def test_severity_config_to_model_mapping(self):
        """Config AlertSeverity maps to Model AlertSeverity correctly."""
        smap = QuizResponseEvaluator.SEVERITY_MAP
        assert smap[ConfigAlertSeverity.CRITICAL] == ModelAlertSeverity.CRITICAL
        assert smap[ConfigAlertSeverity.WARNING] == ModelAlertSeverity.HIGH
        assert smap[ConfigAlertSeverity.INFO] == ModelAlertSeverity.MEDIUM

    def test_notification_priority_map_constants(self):
        """NOTIFICATION_PRIORITY_MAP covers all four model severities."""
        pmap = QuizResponseEvaluator.NOTIFICATION_PRIORITY_MAP
        assert pmap[ModelAlertSeverity.CRITICAL] == NotificationPriority.URGENT
        assert pmap[ModelAlertSeverity.HIGH] == NotificationPriority.HIGH
        assert pmap[ModelAlertSeverity.MEDIUM] == NotificationPriority.MEDIUM
        assert pmap[ModelAlertSeverity.LOW] == NotificationPriority.LOW

    # ---- Test 4: No notification when patient has no doctor_id ----

    @pytest.mark.asyncio
    async def test_no_notification_when_patient_has_no_doctor(
        self, mock_db, patient_id, quiz_session_id, caplog,
    ):
        """When patient.doctor_id is None, alert IS created but NO Notification."""
        patient = _make_patient(doctor_id=None, patient_id=patient_id)

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            None,      # duplicate check
            patient,   # patient lookup
        ]

        evaluator = QuizResponseEvaluator(mock_db)

        def passthrough_create(alert_obj):
            alert_obj.id = uuid4()
            return alert_obj

        evaluator.alert_repository.create = MagicMock(side_effect=passthrough_create)
        evaluator._notify_medical_team = AsyncMock()

        responses = {**_non_triggering_responses(), "pain_scale": 9}

        with caplog.at_level(logging.WARNING):
            alerts, _ = await evaluator.evaluate_quiz_session(
                quiz_session_id=quiz_session_id,
                patient_id=patient_id,
                responses=responses,
            )

        # Alert IS created
        assert len(alerts) >= 1

        # NO Notification added
        notification_adds = [
            c for c in mock_db.add.call_args_list
            if isinstance(c[0][0], Notification)
        ]
        assert len(notification_adds) == 0, (
            "Expected 0 Notifications when doctor_id is None, "
            f"got {len(notification_adds)}"
        )

        # Warning logged about missing doctor_id
        assert any("No doctor_id" in rec.message or "doctor_id" in rec.message.lower()
                    for rec in caplog.records), (
            "Expected a warning log about missing doctor_id"
        )

    # ---- Test 5: Duplicate alert prevention ----

    @pytest.mark.asyncio
    async def test_duplicate_alert_returns_existing_no_new_notification(
        self, mock_db, patient_id, quiz_session_id, doctor_id, caplog,
    ):
        """When an alert already exists for the same session+rule, return existing."""
        patient = _make_patient(doctor_id=doctor_id, patient_id=patient_id)

        # Build a fake "existing alert" to be returned by duplicate check
        existing_alert = MagicMock(spec=Alert)
        existing_alert.id = uuid4()
        existing_alert.patient_id = patient_id
        existing_alert.alert_type = "quiz_response"
        existing_alert.severity = ModelAlertSeverity.CRITICAL
        existing_alert.data = {
            "triggered_rule_id": "pain_score_critical",
            "quiz_session_id": str(quiz_session_id),
        }

        # duplicate-guard returns existing alert
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            existing_alert,  # duplicate check → found existing
        ]

        evaluator = QuizResponseEvaluator(mock_db)
        evaluator.alert_repository.create = MagicMock()
        evaluator._notify_medical_team = AsyncMock()

        responses = {**_non_triggering_responses(), "pain_scale": 9}

        with caplog.at_level(logging.INFO):
            alerts, _ = await evaluator.evaluate_quiz_session(
                quiz_session_id=quiz_session_id,
                patient_id=patient_id,
                responses=responses,
            )

        # The existing alert should be in the returned list
        pain_alerts = [
            a for a in alerts
            if a.data.get("triggered_rule_id") == "pain_score_critical"
        ]
        assert len(pain_alerts) >= 1
        assert pain_alerts[0].id == existing_alert.id

        # No NEW alert created via repository
        evaluator.alert_repository.create.assert_not_called()

        # No Notification created for duplicate
        notification_adds = [
            c for c in mock_db.add.call_args_list
            if isinstance(c[0][0], Notification)
        ]
        assert len(notification_adds) == 0

        # Log message about duplicate
        assert any("Duplicate" in rec.message or "duplicate" in rec.message.lower()
                    for rec in caplog.records)

    # ---- Test 6: No alerts when no rules trigger ----

    @pytest.mark.asyncio
    async def test_no_alerts_when_no_rules_trigger(
        self, mock_db, patient_id, quiz_session_id,
    ):
        """Low-symptom responses → empty alerts list, risk score 0.0."""
        evaluator = QuizResponseEvaluator(mock_db)
        evaluator.alert_repository.create = MagicMock()
        evaluator._notify_medical_team = AsyncMock()

        responses = _non_triggering_responses()

        alerts, risk_score = await evaluator.evaluate_quiz_session(
            quiz_session_id=quiz_session_id,
            patient_id=patient_id,
            responses=responses,
        )

        assert len(alerts) == 0
        assert risk_score == 0.0

        # No Notification added
        notification_adds = [
            c for c in mock_db.add.call_args_list
            if isinstance(c[0][0], Notification)
        ]
        assert len(notification_adds) == 0

    # ---- Test 7: Alert serializer includes title, message, recommendation ----

    def test_alert_serializer_includes_title_message_recommendation(self):
        """_serialize_alert returns title from data.rule_name, message from
        description, and recommendation from data.recommendation."""
        from app.api.v2.routers.alerts import _serialize_alert

        alert = MagicMock(spec=Alert)
        alert.id = uuid4()
        alert.patient_id = uuid4()
        alert.alert_type = "quiz_response"
        alert.severity = ModelAlertSeverity.HIGH
        alert.description = "Paciente relata dor 9/10"
        alert.status = AlertStatus.PENDING
        alert.data = {
            "rule_name": "Dor Crítica",
            "recommendation": "Avaliar paciente",
            "quiz_session_id": str(uuid4()),
        }
        alert.acknowledged = False
        alert.acknowledged_by = None
        alert.acknowledged_at = None
        alert.created_at = datetime.now(timezone.utc)
        alert.updated_at = datetime.now(timezone.utc)

        result = _serialize_alert(alert)

        assert result["title"] == "Dor Crítica"
        assert result["message"] == "Paciente relata dor 9/10"
        assert result["recommendation"] == "Avaliar paciente"

    # ---- Test 8: Serializer falls back for missing data ----

    def test_alert_serializer_fallback_when_data_is_none(self):
        """When alert.data is None, title falls back to alert_type, recommendation to ''."""
        from app.api.v2.routers.alerts import _serialize_alert

        alert = MagicMock(spec=Alert)
        alert.id = uuid4()
        alert.patient_id = uuid4()
        alert.alert_type = "quiz_response"
        alert.severity = ModelAlertSeverity.MEDIUM
        alert.description = "Some description"
        alert.status = AlertStatus.PENDING
        alert.data = None
        alert.acknowledged = False
        alert.acknowledged_by = None
        alert.acknowledged_at = None
        alert.created_at = datetime.now(timezone.utc)
        alert.updated_at = datetime.now(timezone.utc)

        result = _serialize_alert(alert)

        assert result["title"] == "quiz_response"  # fallback to alert_type
        assert result["recommendation"] == ""  # fallback to empty

    # ---- Test 9: fever_with_chills rule triggers correctly ----

    @pytest.mark.asyncio
    async def test_fever_with_chills_triggers_critical_alert(
        self, mock_db, patient_id, quiz_session_id, doctor_id,
    ):
        """has_fever=True + has_chills=True triggers fever_with_chills rule."""
        patient = _make_patient(doctor_id=doctor_id, patient_id=patient_id)

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            None,      # duplicate check
            patient,   # patient lookup
        ]

        evaluator = QuizResponseEvaluator(mock_db)

        def passthrough_create(alert_obj):
            alert_obj.id = uuid4()
            return alert_obj

        evaluator.alert_repository.create = MagicMock(side_effect=passthrough_create)
        evaluator._notify_medical_team = AsyncMock()

        responses = {
            **_non_triggering_responses(),
            "has_fever": True,
            "has_chills": True,
        }

        alerts, risk_score = await evaluator.evaluate_quiz_session(
            quiz_session_id=quiz_session_id,
            patient_id=patient_id,
            responses=responses,
        )

        fever_alert = next(
            (a for a in alerts if a.data.get("triggered_rule_id") == "fever_with_chills"),
            None,
        )
        assert fever_alert is not None, (
            f"Expected fever_with_chills alert, got rule_ids: "
            f"{[a.data.get('triggered_rule_id') for a in alerts]}"
        )
        assert fever_alert.severity == ModelAlertSeverity.CRITICAL

    # ---- Test 10: Risk score calculation ----

    @pytest.mark.asyncio
    async def test_risk_score_positive_for_critical_alert(
        self, mock_db, patient_id, quiz_session_id, doctor_id,
    ):
        """Triggering a CRITICAL rule produces risk_score > 0."""
        patient = _make_patient(doctor_id=doctor_id, patient_id=patient_id)

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            None,      # duplicate check
            patient,   # patient lookup
        ]

        evaluator = QuizResponseEvaluator(mock_db)

        def passthrough_create(alert_obj):
            alert_obj.id = uuid4()
            return alert_obj

        evaluator.alert_repository.create = MagicMock(side_effect=passthrough_create)
        evaluator._notify_medical_team = AsyncMock()

        responses = {**_non_triggering_responses(), "pain_scale": 9}

        _, risk_score = await evaluator.evaluate_quiz_session(
            quiz_session_id=quiz_session_id,
            patient_id=patient_id,
            responses=responses,
        )

        # CRITICAL = 50 points, risk_score should be ≥ 50
        assert risk_score >= 50.0
