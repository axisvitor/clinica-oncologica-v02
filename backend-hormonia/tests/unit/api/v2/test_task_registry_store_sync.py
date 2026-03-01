"""Store-backed task registry synchronization tests."""

from app.api.v2.routers.tasks import registry as tasks_registry


def test_hydrate_registry_from_store_merges_valid_entries(monkeypatch):
    tasks_registry.task_registry.clear()
    monkeypatch.setattr(
        tasks_registry,
        "list_stored_tasks",
        lambda limit=None: [
            {"id": "task-1", "celery_task_id": "celery-1", "task_name": "A"},
            {"id": "task-2", "task_name": "missing-celery"},
            {"celery_task_id": "celery-3", "task_name": "missing-public-id"},
        ],
    )

    merged = tasks_registry.hydrate_registry_from_store()

    assert merged == 1
    assert "celery-1" in tasks_registry.task_registry
    assert "celery-3" not in tasks_registry.task_registry


def test_get_task_by_id_uses_store_fallback(monkeypatch):
    tasks_registry.task_registry.clear()
    payload = {
        "id": "task-public-id",
        "celery_task_id": "celery-task-id",
        "task_name": "demo",
    }
    monkeypatch.setattr(
        tasks_registry,
        "get_stored_task",
        lambda task_id: payload if task_id == "task-public-id" else None,
    )

    result = tasks_registry.get_task_by_id("task-public-id")

    assert result is not None
    assert result["celery_task_id"] == "celery-task-id"
    assert tasks_registry.task_registry["celery-task-id"]["id"] == "task-public-id"


def test_update_task_syncs_local_and_store(monkeypatch):
    tasks_registry.task_registry.clear()
    tasks_registry.task_registry["celery-1"] = {"id": "task-1", "status": "PENDING"}
    captured = {}

    monkeypatch.setattr(
        tasks_registry,
        "update_stored_task",
        lambda task_id, updates: captured.setdefault("calls", []).append((task_id, updates)),
    )

    tasks_registry.update_task("celery-1", {"status": "SUCCESS"})

    assert tasks_registry.task_registry["celery-1"]["status"] == "SUCCESS"
    assert captured["calls"] == [("task-1", {"status": "SUCCESS"})]


def test_delete_task_removes_local_and_store(monkeypatch):
    tasks_registry.task_registry.clear()
    tasks_registry.task_registry["celery-1"] = {"id": "task-1", "status": "PENDING"}
    captured = {}

    monkeypatch.setattr(
        tasks_registry,
        "delete_stored_task",
        lambda task_id: captured.setdefault("calls", []).append(task_id),
    )

    removed = tasks_registry.delete_task("celery-1")

    assert removed is True
    assert "celery-1" not in tasks_registry.task_registry
    assert captured["calls"] == ["task-1"]
