"""
Unit tests for quiz alert → notification chain.

Tests cover:
1. evaluate_quiz_session() creates both Alert and Notification records
2. Notification is created for the correct doctor via patient.doctor_id
3. Severity mapping: config CRITICAL→notification URGENT, WARNING→HIGH, INFO→MEDIUM
4. No notification when patient has no doctor_id (warning logged, no crash)
5. Duplicate alert prevention for same session+rule
6. No alerts/notifications created when no rules trigger
7. Alert serializer includes title, message, recommendation fields

Created by T01 as skeleton; T02 will implement full tests.
"""

import pytest
from uuid import uuid4

from app.models.alert import AlertSeverity as ModelAlertSeverity
from app.models.notification import NotificationPriority


class TestQuizAlertNotificationChain:
    """Tests for the quiz response → alert → notification chain."""

    def test_severity_mapping_constants(self):
        """Verify the notification priority map exists with correct mappings."""
        from app.domain.quizzes.evaluation.response_evaluator import QuizResponseEvaluator
        assert ModelAlertSeverity.CRITICAL in QuizResponseEvaluator.NOTIFICATION_PRIORITY_MAP
        assert QuizResponseEvaluator.NOTIFICATION_PRIORITY_MAP[ModelAlertSeverity.CRITICAL] == NotificationPriority.URGENT
        assert QuizResponseEvaluator.NOTIFICATION_PRIORITY_MAP[ModelAlertSeverity.HIGH] == NotificationPriority.HIGH
        assert QuizResponseEvaluator.NOTIFICATION_PRIORITY_MAP[ModelAlertSeverity.MEDIUM] == NotificationPriority.MEDIUM
        assert QuizResponseEvaluator.NOTIFICATION_PRIORITY_MAP[ModelAlertSeverity.LOW] == NotificationPriority.LOW

    def test_alert_serializer_includes_title_message_recommendation(self):
        """Verify _serialize_alert returns title, message, recommendation fields."""
        from app.api.v2.routers.alerts import _serialize_alert
        from app.models.alert import Alert, AlertStatus
        from unittest.mock import MagicMock
        from datetime import datetime, timezone

        alert = MagicMock(spec=Alert)
        alert.id = uuid4()
        alert.patient_id = uuid4()
        alert.alert_type = "quiz_response"
        alert.severity = ModelAlertSeverity.HIGH
        alert.description = "Test alert description"
        alert.status = AlertStatus.PENDING
        alert.data = {
            "rule_name": "Pain Scale Alert",
            "recommendation": "Schedule follow-up",
            "quiz_session_id": str(uuid4()),
        }
        alert.acknowledged = False
        alert.acknowledged_by = None
        alert.acknowledged_at = None
        alert.created_at = datetime.now(timezone.utc)
        alert.updated_at = datetime.now(timezone.utc)

        result = _serialize_alert(alert)

        assert result["title"] == "Pain Scale Alert"
        assert result["message"] == "Test alert description"
        assert result["recommendation"] == "Schedule follow-up"

    def test_placeholder_evaluate_creates_notification(self):
        """Placeholder: T02 will implement full integration test with mock DB."""
        pytest.skip("Full integration test deferred to T02")

    def test_placeholder_no_doctor_graceful(self):
        """Placeholder: T02 will test missing doctor_id handling."""
        pytest.skip("Full integration test deferred to T02")

    def test_placeholder_duplicate_prevention(self):
        """Placeholder: T02 will test duplicate alert guard."""
        pytest.skip("Full integration test deferred to T02")
