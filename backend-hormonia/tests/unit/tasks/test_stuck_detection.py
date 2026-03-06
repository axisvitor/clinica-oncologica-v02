from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch
from uuid import uuid4

from app.celery_app import celery_app
from app.tasks.flows.stuck_detection import detect_stuck_flows


@contextmanager
def _db_session(db):
    yield db


def _flow_state():
    return SimpleNamespace(id=uuid4(), patient_id=uuid4())


def test_detect_stuck_flows_recovers_all_detected_flows():
    db = MagicMock()
    redis_client = MagicMock()
    flows = [_flow_state(), _flow_state(), _flow_state()]
    redis_manager = MagicMock()
    redis_manager.get_sync_client.return_value = redis_client

    with patch(
        "app.tasks.flows.stuck_detection.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows.stuck_detection.get_redis_manager",
        return_value=redis_manager,
    ), patch(
        "app.tasks.flows.stuck_detection.find_stuck_flows",
        return_value=flows,
    ) as find_mock, patch(
        "app.tasks.flows.stuck_detection.attempt_recovery",
        side_effect=[
            {"status": "recovered", "action": "resend_prompt"},
            {"status": "recovered", "action": "resend_prompt"},
            {"status": "recovered", "action": "advance_day"},
        ],
    ) as recover_mock:
        result = detect_stuck_flows.run()

    assert result["detected_count"] == 3
    assert result["recovered_count"] == 3
    assert result["skipped_count"] == 0
    assert result["failed_count"] == 0
    find_mock.assert_called_once_with(db)
    recover_mock.assert_has_calls([call(db, flow, redis_client) for flow in flows])


def test_detect_stuck_flows_returns_zero_summary_when_no_flows_are_stuck():
    db = MagicMock()
    redis_manager = MagicMock()
    redis_manager.get_sync_client.return_value = MagicMock()

    with patch(
        "app.tasks.flows.stuck_detection.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows.stuck_detection.get_redis_manager",
        return_value=redis_manager,
    ), patch(
        "app.tasks.flows.stuck_detection.find_stuck_flows",
        return_value=[],
    ), patch(
        "app.tasks.flows.stuck_detection.attempt_recovery"
    ) as recover_mock:
        result = detect_stuck_flows.run()

    assert result["detected_count"] == 0
    assert result["recovered_count"] == 0
    assert result["skipped_count"] == 0
    assert result["failed_count"] == 0
    recover_mock.assert_not_called()


def test_detect_stuck_flows_isolates_per_flow_failures():
    db = MagicMock()
    redis_client = MagicMock()
    redis_manager = MagicMock()
    redis_manager.get_sync_client.return_value = redis_client
    flows = [_flow_state(), _flow_state(), _flow_state()]

    with patch(
        "app.tasks.flows.stuck_detection.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows.stuck_detection.get_redis_manager",
        return_value=redis_manager,
    ), patch(
        "app.tasks.flows.stuck_detection.find_stuck_flows",
        return_value=flows,
    ), patch(
        "app.tasks.flows.stuck_detection.attempt_recovery",
        side_effect=[
            {"status": "recovered", "action": "resend_prompt"},
            RuntimeError("boom"),
            {"status": "recovered", "action": "advance_day"},
        ],
    ):
        result = detect_stuck_flows.run()

    assert result["detected_count"] == 3
    assert result["recovered_count"] == 2
    assert result["skipped_count"] == 0
    assert result["failed_count"] == 1


def test_detect_stuck_flows_counts_skipped_recoveries():
    db = MagicMock()
    redis_client = MagicMock()
    redis_manager = MagicMock()
    redis_manager.get_sync_client.return_value = redis_client
    flows = [_flow_state(), _flow_state(), _flow_state()]

    with patch(
        "app.tasks.flows.stuck_detection.get_scoped_session",
        return_value=_db_session(db),
    ), patch(
        "app.tasks.flows.stuck_detection.get_redis_manager",
        return_value=redis_manager,
    ), patch(
        "app.tasks.flows.stuck_detection.find_stuck_flows",
        return_value=flows,
    ), patch(
        "app.tasks.flows.stuck_detection.attempt_recovery",
        side_effect=[
            {"status": "max_attempts_exceeded"},
            {"status": "already_recovering"},
            {"status": "no_longer_stuck"},
        ],
    ):
        result = detect_stuck_flows.run()

    assert result["detected_count"] == 3
    assert result["recovered_count"] == 0
    assert result["skipped_count"] == 3
    assert result["failed_count"] == 0


def test_celery_beat_schedule_includes_detect_stuck_flows():
    entry = celery_app.conf.beat_schedule["detect-stuck-flows"]

    assert entry["task"] == "app.tasks.flows.stuck_detection.detect_stuck_flows"
    assert entry["schedule"] == 900.0
