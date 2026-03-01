"""Focused tests for alert Celery task failure semantics and payload hygiene."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest


def _scoped_session(db):
    @contextmanager
    def _ctx():
        yield db

    return _ctx()


def test_check_patient_alerts_propagates_failures():
    from app.tasks.alerts import check_patient_alerts

    with patch(
        "app.tasks.alerts.get_db_session",
        side_effect=RuntimeError("db unavailable"),
    ):
        with pytest.raises(RuntimeError, match="db unavailable"):
            check_patient_alerts.run()


def test_process_alert_notification_removes_patient_name_from_metadata_and_payload():
    from app.tasks.alerts import process_alert_notification

    alert_repo = Mock()
    alert_repo.create.return_value = SimpleNamespace(id=uuid4())
    websocket_events = Mock()

    class _WebSocketEventType:
        ALERT_CREATED = "ALERT_CREATED"

    alert_data = {
        "patient_id": str(uuid4()),
        "patient_name": "Sensitive Name",
        "doctor_id": str(uuid4()),
        "priority": "high",
        "alert_type": "symptom",
        "message": "Patient reported side effects",
    }

    with patch(
        "app.tasks.alerts.get_db_session",
        return_value=_scoped_session(Mock()),
    ), patch(
        "app.repositories.alert.AlertRepository", return_value=alert_repo
    ), patch(
        "app.services.websocket_events.websocket_events", websocket_events
    ), patch(
        "app.schemas.websocket.WebSocketEventType", _WebSocketEventType
    ):
        result = process_alert_notification.run(alert_data=alert_data)

    assert result["success"] is True
    create_payload = alert_repo.create.call_args.args[0]
    assert "patient_name" not in create_payload["metadata"]

    for call in websocket_events.emit.call_args_list:
        assert "patient_name" not in call.kwargs["data"]


def test_process_alert_notification_propagates_failures():
    from app.tasks.alerts import process_alert_notification

    with patch(
        "app.tasks.alerts.get_db_session",
        return_value=_scoped_session(Mock()),
    ), patch(
        "app.repositories.alert.AlertRepository",
        side_effect=RuntimeError("write failed"),
    ):
        with pytest.raises(RuntimeError, match="write failed"):
            process_alert_notification.run(
                alert_data={"patient_id": str(uuid4()), "message": "alert"}
            )


def test_process_alert_escalation_uses_retry_on_unexpected_failure():
    from app.tasks.alerts import process_alert_escalation

    with patch(
        "app.tasks.alerts.get_db_session",
        side_effect=RuntimeError("db unavailable"),
    ), patch.object(
        process_alert_escalation,
        "retry",
        side_effect=RuntimeError("retry-called"),
    ) as retry_mock:
        with pytest.raises(RuntimeError, match="retry-called"):
            process_alert_escalation.run(alert_id=str(uuid4()), escalation_level="high")

    retry_mock.assert_called_once()


def test_periodic_escalation_check_uses_retry_on_unexpected_failure():
    from app.tasks.alerts import periodic_escalation_check

    with patch(
        "app.tasks.alerts.get_db_session",
        side_effect=RuntimeError("db unavailable"),
    ), patch.object(
        periodic_escalation_check,
        "retry",
        side_effect=RuntimeError("retry-called"),
    ) as retry_mock:
        with pytest.raises(RuntimeError, match="retry-called"):
            periodic_escalation_check.run()

    retry_mock.assert_called_once()
