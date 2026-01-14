"""
Task queue abstraction to support Celery (local) and Cloud Tasks (production).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
import importlib
from types import SimpleNamespace
from typing import Any, Callable, Dict, Mapping, Optional
from uuid import uuid4

from app.config import settings

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
    "app.tasks.deprecation_notifications",
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
            created_at_ts = datetime.now(timezone.utc).timestamp()
    else:
        created_at_ts = datetime.now(timezone.utc).timestamp()

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


def list_tasks() -> list[Dict[str, Any]]:
    client = _get_task_store_client()
    if not client:
        return []

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


class TaskAuthError(Exception):
    """Raised when task execution authentication fails."""


class CloudTaskRetry(Exception):
    """Raised to request a task retry with a countdown."""

    def __init__(
        self,
        countdown: Optional[int] = None,
        exc: Optional[Exception] = None,
        max_retries: Optional[int] = None,
    ):
        super().__init__(str(exc) if exc else "retry")
        self.countdown = countdown
        self.exc = exc
        self.max_retries = max_retries


@dataclass(frozen=True)
class TaskDefinition:
    func: Callable[..., Any]
    name: str
    bind: bool
    base: Optional[type]
    max_retries: Optional[int]
    default_retry_delay: Optional[int]
    retry_backoff_max: int


class TaskExecutionContext:
    """Lightweight task context for Cloud Tasks execution."""

    def __init__(self, definition: TaskDefinition, task_id: str, retries: int) -> None:
        self.name = definition.name
        self.request = SimpleNamespace(retries=retries, id=task_id)
        self.max_retries = (
            definition.max_retries
            if definition.max_retries is not None
            else 999999
        )
        self.default_retry_delay = definition.default_retry_delay
        self.retry_backoff_max = definition.retry_backoff_max
        self._logger = logging.getLogger(f"tasks.{self.name}")

    def get_task_logger(self) -> logging.Logger:
        return self._logger

    def log_task_start(self, **kwargs: Any) -> None:
        self._logger.info("Starting task %s with params: %s", self.name, kwargs)

    def log_task_success(self, result: Any, **kwargs: Any) -> None:
        self._logger.info("Task %s completed successfully", self.name)

    def log_task_error(self, exc: Exception, **kwargs: Any) -> None:
        self._logger.error("Task %s failed: %s", self.name, exc, exc_info=True)

    def create_error_result(self, error: str, **context: Any) -> Dict[str, Any]:
        return {
            "success": False,
            "error": error,
            "task_name": self.name,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            **context,
        }

    def create_success_result(self, **data: Any) -> Dict[str, Any]:
        return {
            "success": True,
            "task_name": self.name,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            **data,
        }

    def retry(
        self,
        exc: Optional[Exception] = None,
        countdown: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        effective_max_retries = (
            max_retries if max_retries is not None else self.max_retries
        )
        if effective_max_retries is not None and self.request.retries >= effective_max_retries:
            if exc:
                raise exc
            raise RuntimeError("Max retries exceeded")

        if countdown is None:
            countdown = self.default_retry_delay or 0

        raise CloudTaskRetry(
            countdown=countdown, exc=exc, max_retries=effective_max_retries
        )

    def handle_retry(self, exc: Exception, **context: Any) -> None:
        if self.max_retries is not None and self.request.retries >= self.max_retries:
            self.log_task_error(exc, **context)
            raise exc

        countdown = min(60 * (2**self.request.retries), self.retry_backoff_max)
        self._logger.warning(
            "Retrying task %s in %s seconds (attempt %s/%s): %s",
            self.name,
            countdown,
            self.request.retries + 1,
            self.max_retries,
            exc,
        )
        raise CloudTaskRetry(countdown=countdown, exc=exc)


class TaskHandle:
    def __init__(self, definition: TaskDefinition, queue: "TaskQueue") -> None:
        self._definition = definition
        self._queue = queue
        self.name = definition.name
        self.__name__ = definition.func.__name__
        self.__doc__ = definition.func.__doc__

    def delay(self, *args: Any, **kwargs: Any) -> "TaskEnqueueResult":
        return self._queue.enqueue(self.name, args=list(args), kwargs=kwargs)

    def apply_async(
        self,
        args: Optional[list] = None,
        kwargs: Optional[dict] = None,
        eta: Optional[datetime] = None,
        countdown: Optional[int] = None,
        **options: Any,
    ) -> "TaskEnqueueResult":
        return self._queue.enqueue(
            self.name,
            args=args or [],
            kwargs=kwargs or {},
            eta=eta,
            countdown=countdown,
            **options,
        )

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if self._definition.bind:
            context = TaskExecutionContext(self._definition, task_id="inline", retries=0)
            return self._definition.func(context, *args, **kwargs)
        return self._definition.func(*args, **kwargs)


@dataclass(frozen=True)
class TaskEnqueueResult:
    id: str
    name: Optional[str] = None


class NullInspector:
    def active(self):
        return {}

    def scheduled(self):
        return {}

    def stats(self):
        return {}


class NullControl:
    def inspect(self, *args: Any, **kwargs: Any) -> NullInspector:
        return NullInspector()

    def revoke(self, *args: Any, **kwargs: Any) -> bool:
        return False


class TaskQueue:
    def __init__(self) -> None:
        self._provider = settings.TASK_QUEUE_PROVIDER.lower()
        self._registry: Dict[str, TaskDefinition] = {}

    @property
    def registry(self) -> Dict[str, TaskDefinition]:
        return self._registry

    @property
    def control(self):
        if self._provider == "celery":
            from app.celery_app import celery_app
            return celery_app.control
        return NullControl()

    def task(self, *dargs: Any, **dkwargs: Any) -> Callable[..., Any]:
        if self._provider == "celery":
            from app.celery_app import celery_app
            return celery_app.task(*dargs, **dkwargs)

        def decorator(func: Callable[..., Any]) -> TaskHandle:
            task_name = dkwargs.get("name") or f"{func.__module__}.{func.__name__}"
            bind = bool(dkwargs.get("bind", False))
            base = dkwargs.get("base")
            max_retries = dkwargs.get("max_retries")
            default_retry_delay = dkwargs.get("default_retry_delay")
            retry_backoff_max = getattr(base, "retry_backoff_max", 600) if base else 600

            if max_retries is None and base is not None:
                base_retry = getattr(base, "retry_kwargs", {}) or {}
                max_retries = base_retry.get("max_retries")
                default_retry_delay = default_retry_delay or base_retry.get("countdown")

            definition = TaskDefinition(
                func=func,
                name=task_name,
                bind=bind,
                base=base,
                max_retries=max_retries,
                default_retry_delay=default_retry_delay,
                retry_backoff_max=retry_backoff_max,
            )
            self._registry[task_name] = definition
            return TaskHandle(definition, self)

        if dargs and callable(dargs[0]) and not dkwargs:
            return decorator(dargs[0])
        return decorator

    def send_task(
        self,
        name: str,
        args: Optional[list] = None,
        kwargs: Optional[dict] = None,
        **options: Any,
    ) -> TaskEnqueueResult:
        if self._provider == "celery":
            from app.celery_app import celery_app
            return celery_app.send_task(name, args=args, kwargs=kwargs, **options)
        return self.enqueue(name, args=args or [], kwargs=kwargs or {}, **options)

    def enqueue(
        self,
        task_name: str,
        args: Optional[list] = None,
        kwargs: Optional[dict] = None,
        eta: Optional[datetime] = None,
        countdown: Optional[int] = None,
        task_id: Optional[str] = None,
        retries: int = 0,
        **options: Any,
    ) -> TaskEnqueueResult:
        if self._provider == "celery":
            from app.celery_app import celery_app
            return celery_app.send_task(
                task_name,
                args=args,
                kwargs=kwargs,
                eta=eta,
                countdown=countdown,
                **options,
            )

        if not settings.CLOUD_TASKS_QUEUE:
            raise RuntimeError("CLOUD_TASKS_QUEUE is required for Cloud Tasks provider")
        if not settings.CLOUD_TASKS_PROJECT_ID:
            raise RuntimeError("CLOUD_TASKS_PROJECT_ID is required for Cloud Tasks provider")
        if not settings.CLOUD_TASKS_SERVICE_URL:
            raise RuntimeError("CLOUD_TASKS_SERVICE_URL is required for Cloud Tasks provider")

        from google.cloud import tasks_v2
        from google.protobuf import timestamp_pb2

        client = tasks_v2.CloudTasksClient()
        queue_path = client.queue_path(
            settings.CLOUD_TASKS_PROJECT_ID,
            settings.CLOUD_TASKS_LOCATION,
            settings.CLOUD_TASKS_QUEUE,
        )

        now = datetime.now(timezone.utc)
        schedule_time = None
        if eta:
            schedule_time = eta if eta.tzinfo else eta.replace(tzinfo=timezone.utc)
        elif countdown:
            schedule_time = now + timedelta(seconds=countdown)

        payload = {
            "task_name": task_name,
            "args": args or [],
            "kwargs": kwargs or {},
            "task_id": task_id or str(uuid4()),
            "retries": retries,
        }

        http_request: Dict[str, Any] = {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{settings.CLOUD_TASKS_SERVICE_URL.rstrip('/')}{settings.CLOUD_TASKS_HANDLER_PATH}",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(payload).encode("utf-8"),
        }

        if settings.CLOUD_TASKS_OIDC_SERVICE_ACCOUNT:
            http_request["oidc_token"] = {
                "service_account_email": settings.CLOUD_TASKS_OIDC_SERVICE_ACCOUNT,
                "audience": settings.CLOUD_TASKS_AUDIENCE or settings.CLOUD_TASKS_SERVICE_URL,
            }

        task: Dict[str, Any] = {"http_request": http_request}

        if schedule_time:
            timestamp = timestamp_pb2.Timestamp()
            timestamp.FromDatetime(schedule_time)
            task["schedule_time"] = timestamp

        task_name_path = f"{queue_path}/tasks/{payload['task_id']}"
        task["name"] = task_name_path

        created_task = client.create_task(parent=queue_path, task=task)
        task_metadata = {
            "id": payload["task_id"],
            "task_name": task_name,
            "args": payload["args"],
            "kwargs": payload["kwargs"],
            "status": "PENDING",
            "queue_name": "cloud_tasks",
            "created_at": now.isoformat(),
            "scheduled_at": schedule_time.isoformat() if schedule_time else None,
        }
        task_metadata.update(options.pop("task_metadata", {}) or {})
        store_task(task_metadata)
        return TaskEnqueueResult(id=payload["task_id"], name=created_task.name)

    def execute(
        self,
        task_name: str,
        args: list,
        kwargs: dict,
        task_id: str,
        retries: int,
    ) -> Any:
        if self._provider == "cloud_tasks":
            ensure_task_registry_loaded()
        definition = self._registry.get(task_name)
        if not definition:
            raise RuntimeError(f"Unknown task: {task_name}")

        context = TaskExecutionContext(definition, task_id=task_id, retries=retries)
        update_task(
            task_id,
            {
                "status": "RUNNING",
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        if definition.bind:
            return definition.func(context, *args, **kwargs)
        return definition.func(*args, **kwargs)


task_queue = TaskQueue()


def validate_task_request(headers: Mapping[str, str]) -> None:
    shared_secret = settings.CLOUD_TASKS_SHARED_SECRET
    if shared_secret:
        provided = headers.get("x-cloud-tasks-token") or headers.get("x-tasks-token")
        if provided == shared_secret:
            return

    auth_header = headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise TaskAuthError("Missing Authorization header")

    audience = settings.CLOUD_TASKS_AUDIENCE or settings.CLOUD_TASKS_SERVICE_URL
    if not audience:
        raise TaskAuthError("Missing audience configuration")

    token = auth_header.split(" ", 1)[1]

    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests

        id_info = id_token.verify_oauth2_token(token, requests.Request(), audience=audience)
    except Exception as exc:
        raise TaskAuthError(f"Invalid token: {exc}") from exc

    issuer = id_info.get("iss")
    if issuer not in ("https://accounts.google.com", "accounts.google.com"):
        raise TaskAuthError("Invalid token issuer")
