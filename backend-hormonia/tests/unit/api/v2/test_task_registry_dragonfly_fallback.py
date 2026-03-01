"""Task registry fallback tests for Dragonfly-backed metadata store."""

from app.api.v2.routers.tasks import dependencies as tasks_dependencies
from app.api.v2.routers.tasks.utils import celery_integration
from app.schemas.v2.tasks import TaskPriority, TaskType


def test_find_task_in_registry_uses_stored_task_fallback(monkeypatch):
    tasks_dependencies.task_registry.clear()
    stored_payload = {
        "id": "task-public-id",
        "celery_task_id": "celery-task-id",
        "task_name": "demo",
        "task_type": "scheduled_job",
        "priority": "medium",
    }
    monkeypatch.setattr(
        tasks_dependencies,
        "_registry_get_task_by_id",
        lambda task_id: stored_payload if task_id == "task-public-id" else None,
    )

    celery_id, task_data = tasks_dependencies._find_task_in_registry("task-public-id")

    assert celery_id == "celery-task-id"
    assert task_data == stored_payload


def test_find_task_in_registry_ignores_invalid_stored_payload(monkeypatch):
    tasks_dependencies.task_registry.clear()
    monkeypatch.setattr(
        tasks_dependencies,
        "_registry_get_task_by_id",
        lambda task_id: {"id": task_id},
    )

    celery_id, task_data = tasks_dependencies._find_task_in_registry("task-public-id")

    assert celery_id is None
    assert task_data is None
    assert tasks_dependencies.task_registry == {}


def test_register_task_persists_metadata_to_store(monkeypatch):
    captured = {}

    def _capture_store(payload):
        captured["payload"] = payload

    monkeypatch.setattr(celery_integration, "store_task", _capture_store)
    task_registry = {}

    task_id = celery_integration._register_task(
        celery_task_id="celery-123",
        task_name="My Task",
        task_type=TaskType.SCHEDULED_JOB,
        priority=TaskPriority.MEDIUM,
        user_id=None,
        task_registry=task_registry,
        metadata={"source": "test"},
    )

    assert task_registry["celery-123"]["id"] == task_id
    assert task_registry["celery-123"]["celery_task_id"] == "celery-123"
    assert captured["payload"]["id"] == task_id
    assert captured["payload"]["celery_task_id"] == "celery-123"
    assert captured["payload"]["metadata"] == {"source": "test"}
