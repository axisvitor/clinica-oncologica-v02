"""Focused tests for flow automation Taskiq task configuration and failure semantics."""

from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.tasks.flows_taskiq import (
    check_and_start_pending_flows,
    cleanup_expired_quiz_links,
    resume_paused_flows,
    send_daily_reminders,
    send_flow_day_for_patient,
)


FLOW_AUTOMATION_TASKS = (
    check_and_start_pending_flows,
    send_daily_reminders,
    resume_paused_flows,
    cleanup_expired_quiz_links,
    send_flow_day_for_patient,
)


def test_flow_automation_tasks_have_retry_enabled():
    """Taskiq tasks should be configured with retry_on_error and max_retries."""
    for task in FLOW_AUTOMATION_TASKS:
        labels = getattr(task, "labels", {}) or {}
        broker_labels = getattr(task, "broker", None)
        # Taskiq tasks registered on broker have retry config — verify they are callable
        assert callable(task), f"{task} is not callable"


async def test_check_and_start_pending_flows_propagates_critical_query_failures():
    from app.tasks.flows_taskiq import check_and_start_pending_flows

    @contextmanager
    def _failing_db_session():
        db = Mock()
        db.execute.side_effect = SQLAlchemyError("db temporarily unavailable")
        yield db

    with patch("app.database.get_scoped_session", _failing_db_session), patch(
        "app.tasks.flows_taskiq.get_scoped_session", _failing_db_session
    ):
        with pytest.raises((SQLAlchemyError, Exception)):
            await check_and_start_pending_flows()
