"""Regression tests for Celery metrics task metadata lifecycle handling."""

from types import SimpleNamespace

import pytest

from app.tasks import celery_metrics


def _active_value(task_name: str) -> float:
    return celery_metrics.celery_task_active.labels(task_name=task_name)._value.get()


@pytest.fixture(autouse=True)
def _reset_task_metadata():
    celery_metrics._task_metadata.clear()
    yield
    celery_metrics._task_metadata.clear()


def test_failure_without_postrun_is_eventually_cleaned(monkeypatch):
    task_name = "tests.celery_metrics.failure_cleanup"
    task_id = "task-failure-cleanup-1"
    sender = SimpleNamespace(name=task_name)

    celery_metrics.celery_task_active.labels(task_name=task_name).set(0)

    celery_metrics.task_prerun_handler(sender=sender, task_id=task_id, kwargs={})
    assert _active_value(task_name) == 1
    assert task_id in celery_metrics._task_metadata

    celery_metrics.task_failure_handler(
        sender=sender,
        task_id=task_id,
        exception=RuntimeError("boom"),
    )
    assert celery_metrics._task_metadata[task_id]["terminal_status"] == "failure"

    monkeypatch.setattr(celery_metrics, "_TASK_TERMINAL_METADATA_TTL_SECONDS", 0)
    cleaned = celery_metrics._cleanup_stale_task_metadata()

    assert cleaned == 1
    assert task_id not in celery_metrics._task_metadata
    assert _active_value(task_name) == 0


def test_rejected_signal_uses_message_task_id_for_cleanup(monkeypatch):
    task_name = "tests.celery_metrics.rejected_cleanup"
    task_id = "task-rejected-cleanup-1"
    sender = SimpleNamespace(name=task_name)
    message = SimpleNamespace(headers={"task": task_name, "id": task_id}, properties={})

    celery_metrics.celery_task_active.labels(task_name=task_name).set(0)

    celery_metrics.task_prerun_handler(sender=sender, task_id=task_id, kwargs={})
    assert _active_value(task_name) == 1

    celery_metrics.task_rejected_handler(message=message, exc=RuntimeError("rejected"))
    assert celery_metrics._task_metadata[task_id]["terminal_status"] == "rejected"

    monkeypatch.setattr(celery_metrics, "_TASK_TERMINAL_METADATA_TTL_SECONDS", 0)
    cleaned = celery_metrics._cleanup_stale_task_metadata()

    assert cleaned == 1
    assert task_id not in celery_metrics._task_metadata
    assert _active_value(task_name) == 0


def test_worker_shutdown_clears_remaining_task_metadata():
    task_name_a = "tests.celery_metrics.shutdown_cleanup.a"
    task_name_b = "tests.celery_metrics.shutdown_cleanup.b"
    task_id_a = "task-shutdown-a"
    task_id_b = "task-shutdown-b"

    celery_metrics.celery_task_active.labels(task_name=task_name_a).set(0)
    celery_metrics.celery_task_active.labels(task_name=task_name_b).set(0)

    celery_metrics.task_prerun_handler(
        sender=SimpleNamespace(name=task_name_a),
        task_id=task_id_a,
        kwargs={},
    )
    celery_metrics.task_prerun_handler(
        sender=SimpleNamespace(name=task_name_b),
        task_id=task_id_b,
        kwargs={},
    )
    assert len(celery_metrics._task_metadata) == 2

    celery_metrics.worker_shutdown_handler(sender=SimpleNamespace(hostname="worker-test"))

    assert celery_metrics._task_metadata == {}
    assert _active_value(task_name_a) == 0
    assert _active_value(task_name_b) == 0


def test_postrun_still_cleans_metadata_on_happy_path():
    task_name = "tests.celery_metrics.postrun_cleanup"
    task_id = "task-postrun-cleanup-1"
    sender = SimpleNamespace(name=task_name)

    celery_metrics.celery_task_active.labels(task_name=task_name).set(0)

    celery_metrics.task_prerun_handler(sender=sender, task_id=task_id, kwargs={})
    assert task_id in celery_metrics._task_metadata
    assert _active_value(task_name) == 1

    celery_metrics.task_postrun_handler(sender=sender, task_id=task_id)

    assert task_id not in celery_metrics._task_metadata
    assert _active_value(task_name) == 0
