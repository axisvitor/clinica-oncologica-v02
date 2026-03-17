"""Focused tests for alert Taskiq task failure semantics and payload hygiene."""

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


async def test_check_patient_alerts_propagates_failures():
    from app.tasks.alerts_taskiq import check_patient_alerts

    with patch(
        "app.tasks.alerts_taskiq.get_scoped_session",
        side_effect=RuntimeError("db unavailable"),
    ):
        with pytest.raises(RuntimeError, match="db unavailable"):
            await check_patient_alerts()


async def test_process_alert_notification_removes_patient_name_from_metadata_and_payload():
    from app.tasks.alerts_taskiq import process_alert_notification

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
        "app.tasks.alerts_taskiq.get_scoped_session",
        return_value=_scoped_session(Mock()),
    ), patch(
        "app.repositories.alert.AlertRepository", return_value=alert_repo
    ), patch(
        "app.services.websocket_events.websocket_events", websocket_events
    ), patch(
        "app.schemas.websocket.WebSocketEventType", _WebSocketEventType
    ):
        result = await process_alert_notification(alert_data=alert_data)

    assert result["success"] is True
    create_payload = alert_repo.create.call_args.args[0]
    assert "patient_name" not in create_payload["metadata"]

    for call in websocket_events.emit.call_args_list:
        assert "patient_name" not in call.kwargs["data"]


async def test_process_alert_notification_propagates_failures():
    from app.tasks.alerts_taskiq import process_alert_notification

    with patch(
        "app.tasks.alerts_taskiq.get_scoped_session",
        return_value=_scoped_session(Mock()),
    ), patch(
        "app.repositories.alert.AlertRepository",
        side_effect=RuntimeError("write failed"),
    ):
        with pytest.raises(RuntimeError, match="write failed"):
            await process_alert_notification(
                alert_data={"patient_id": str(uuid4()), "message": "alert"}
            )


async def test_process_alert_escalation_propagates_on_unexpected_failure():
    """Taskiq tasks propagate exceptions for SmartRetryMiddleware to handle."""
    from app.tasks.alerts_taskiq import process_alert_escalation

    with patch(
        "app.tasks.alerts_taskiq.get_scoped_session",
        side_effect=RuntimeError("db unavailable"),
    ):
        with pytest.raises(RuntimeError, match="db unavailable"):
            await process_alert_escalation(
                alert_id=str(uuid4()), escalation_level="high"
            )


async def test_periodic_escalation_check_propagates_on_unexpected_failure():
    """Taskiq tasks propagate exceptions for SmartRetryMiddleware to handle."""
    from app.tasks.alerts_taskiq import periodic_escalation_check

    with patch(
        "app.tasks.alerts_taskiq.get_scoped_session",
        side_effect=RuntimeError("db unavailable"),
    ):
        with pytest.raises(RuntimeError, match="db unavailable"):
            await periodic_escalation_check()
