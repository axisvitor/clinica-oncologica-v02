from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.config.settings.tasks import (
    FLOW_MAX_RETRIES,
    FLOW_RETRY_DELAY,
    TASK_SOFT_TIME_LIMIT,
    TASK_TIME_LIMIT,
)
from app.tasks.flow_automation import (
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


def test_flow_automation_tasks_have_robust_retry_defaults():
    for task in FLOW_AUTOMATION_TASKS:
        assert task.max_retries == FLOW_MAX_RETRIES
        assert task.default_retry_delay == FLOW_RETRY_DELAY
        assert task.retry_backoff == FLOW_RETRY_DELAY
        assert task.retry_backoff_max == max(FLOW_RETRY_DELAY * 8, FLOW_RETRY_DELAY)
        assert task.retry_jitter is True
        assert SQLAlchemyError in task.autoretry_for
        assert ConnectionError in task.autoretry_for
        assert TimeoutError in task.autoretry_for
        assert OSError in task.autoretry_for
        assert task.time_limit == TASK_TIME_LIMIT
        assert task.soft_time_limit == TASK_SOFT_TIME_LIMIT


def test_check_and_start_pending_flows_propagates_critical_query_failures():
    @contextmanager
    def _failing_db_session():
        db = Mock()
        db.execute.side_effect = SQLAlchemyError("db temporarily unavailable")
        yield db

    with patch("app.tasks.flow_automation.get_db_session", _failing_db_session):
        with pytest.raises(SQLAlchemyError):
            check_and_start_pending_flows.run()
