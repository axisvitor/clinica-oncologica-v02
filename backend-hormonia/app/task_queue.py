"""
Task queue abstraction backed by Celery.
"""

from __future__ import annotations

from datetime import datetime
import json
import logging
import importlib
from typing import Any, Dict, Optional

from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

_TASK_MODULES = [
    "app.tasks.messaging",
    "app.tasks.flows",
    "app.tasks.flow_automation",
    "app.tasks.reports",
    "app.tasks.alerts",
    "app.tasks.quiz_link_tasks",
    "app.tasks.quiz_flow",
    "app.tasks.saga_retry",
    "app.tasks.saga_monitoring",
    "app.tasks.follow_up",
    "app.tasks.webhook_dlq",
    "app.tasks.audit_cleanup",
    "app.tasks.monitoring",
    "app.tasks.lgpd_tasks",
    "app.tasks.lgpd.reencrypt_patients",
]
_registry_loaded = False
_TASK_STORE_PREFIX = "tasks:registry:"
_TASK_STORE_INDEX = "tasks:registry:index"
_TASK_STORE_TTL_SECONDS = 7 * 24 * 60 * 60


def ensure_task_registry_loaded() -> None:
    global _registry_loaded
    if _registry_loaded:
        return
    for module_name in _TASK_MODULES:
        importlib.import_module(module_name)
    _registry_loaded = True


def _get_task_store_client():
    try:
        from app.core.redis_manager import get_redis_manager

        manager = get_redis_manager()
        return manager.get_sync_client()
    except Exception as exc:
        logger.warning("Task store unavailable: %s", exc)
        return None


def _serialize_task_payload(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, default=str)


def store_task(payload: Dict[str, Any]) -> None:
    client = _get_task_store_client()
    if not client:
        return

    task_id = payload.get("id")
    if not task_id:
        return

    key = f"{_TASK_STORE_PREFIX}{task_id}"
    created_at = payload.get("created_at")
    if isinstance(created_at, datetime):
        created_at_ts = created_at.timestamp()
    elif isinstance(created_at, str):
        try:
            created_at_ts = datetime.fromisoformat(created_at).timestamp()
        except ValueError:
            created_at_ts = now_sao_paulo().timestamp()
    else:
        created_at_ts = now_sao_paulo().timestamp()

    client.setex(key, _TASK_STORE_TTL_SECONDS, _serialize_task_payload(payload))
    client.zadd(_TASK_STORE_INDEX, {task_id: created_at_ts})
    client.expire(_TASK_STORE_INDEX, _TASK_STORE_TTL_SECONDS)


def update_task(task_id: str, updates: Dict[str, Any]) -> None:
    client = _get_task_store_client()
    if not client:
        return

    key = f"{_TASK_STORE_PREFIX}{task_id}"
    current = client.get(key)
    if current:
        try:
            current_payload = json.loads(current)
        except Exception:
            current_payload = {}
    else:
        current_payload = {}

    current_payload.update(updates)
    current_payload.setdefault("id", task_id)
    client.setex(key, _TASK_STORE_TTL_SECONDS, _serialize_task_payload(current_payload))


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    client = _get_task_store_client()
    if not client:
        return None

    key = f"{_TASK_STORE_PREFIX}{task_id}"
    payload = client.get(key)
    if not payload:
        return None
    try:
        return json.loads(payload)
    except Exception:
        return None


def list_tasks(limit: Optional[int] = None) -> list[Dict[str, Any]]:
    client = _get_task_store_client()
    if not client:
        return []

    if limit is not None and limit > 0:
        task_ids = client.zrange(_TASK_STORE_INDEX, 0, limit - 1, desc=True)
    else:
        task_ids = client.zrange(_TASK_STORE_INDEX, 0, -1, desc=True)
    tasks = []
    for raw_id in task_ids:
        task_id = raw_id.decode() if isinstance(raw_id, (bytes, bytearray)) else raw_id
        payload = get_task(task_id)
        if payload:
            tasks.append(payload)
    return tasks


def append_task_log(task_id: str, entry: Dict[str, Any]) -> None:
    client = _get_task_store_client()
    if not client:
        return

    key = f"{_TASK_STORE_PREFIX}{task_id}"
    payload = client.get(key)
    if not payload:
        return
    try:
        current_payload = json.loads(payload)
    except Exception:
        return

    logs = current_payload.get("logs") or []
    logs.insert(0, entry)
    current_payload["logs"] = logs[:200]
    client.setex(key, _TASK_STORE_TTL_SECONDS, _serialize_task_payload(current_payload))


def delete_task(task_id: str) -> None:
    client = _get_task_store_client()
    if not client:
        return

    key = f"{_TASK_STORE_PREFIX}{task_id}"
    client.delete(key)
    client.zrem(_TASK_STORE_INDEX, task_id)


class TaskQueue:
    """Task queue backed by Celery (with Taskiq coexistence, M009)."""

    @property
    def control(self):
        from app.celery_app import celery_app
        return celery_app.control

    def task(self, *dargs: Any, **dkwargs: Any):
        from app.celery_app import celery_app
        return celery_app.task(*dargs, **dkwargs)

    def send_task(self, name: str, args=None, kwargs=None, **options):
        from app.celery_app import celery_app
        return celery_app.send_task(name, args=args, kwargs=kwargs, **options)

    def enqueue(self, task_name: str, args=None, kwargs=None, eta=None, countdown=None, **options):
        from app.celery_app import celery_app
        return celery_app.send_task(
            task_name, args=args, kwargs=kwargs, eta=eta, countdown=countdown, **options
        )


task_queue = TaskQueue()


# ---------------------------------------------------------------------------
# Taskiq broker access (M009 coexistence period).
#
# During migration, both Celery and Taskiq may be running.
# New tasks should use the Taskiq broker directly:
#   from app.taskiq_broker import broker
#   @broker.task
#   async def my_new_task(): ...
#
# Legacy callers that need a unified interface can use get_taskiq_broker().
# ---------------------------------------------------------------------------

def get_taskiq_broker():
    """
    Return the Taskiq broker instance.

    Lazy import to avoid circular dependencies and heavy settings chain.
    Returns None if Taskiq is not configured (should not happen after M009/S01).
    """
    try:
        from app.taskiq_broker import broker
        return broker
    except ImportError:
        logger.warning("Taskiq broker not available — taskiq_broker module not found")
        return None


async def get_taskiq_broker_health() -> dict:
    """
    Return Taskiq broker health status.

    Convenience wrapper for health checks that need both Celery and Taskiq status.
    """
    try:
        from app.taskiq_broker import check_broker_health
        return await check_broker_health()
    except ImportError:
        return {"taskiq_broker": "not_installed", "dragonfly_reachable": False}
    except Exception as e:
        return {"taskiq_broker": "error", "error": str(e), "dragonfly_reachable": False}
