"""LangGraph runtime helpers for checkpointing and node observability."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import os
import re
import time
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from functools import wraps
from threading import Lock
from typing import NamedTuple
from typing import Any, Callable

try:
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:
    MemorySaver = None  # type: ignore[assignment]
try:
    from langgraph.checkpoint.base import (
        BaseCheckpointSaver,
        CheckpointTuple,
        WRITES_IDX_MAP,
        get_checkpoint_id,
        get_checkpoint_metadata,
    )
except ImportError:
    BaseCheckpointSaver = None  # type: ignore[assignment]
    CheckpointTuple = None  # type: ignore[assignment]
    WRITES_IDX_MAP = {}  # type: ignore[assignment]

    def get_checkpoint_id(config: Any) -> str | None:
        configurable = (config or {}).get("configurable")
        if isinstance(configurable, Mapping):
            checkpoint_id = configurable.get("checkpoint_id")
            return str(checkpoint_id) if checkpoint_id else None
        return None

    def get_checkpoint_metadata(config: Any, metadata: Any) -> dict[str, Any]:
        if isinstance(metadata, Mapping):
            return dict(metadata)
        return {}

logger = logging.getLogger(__name__)

_CHECKPOINTERS: dict[str, Any] = {}
_CHECKPOINTERS_LOCK = Lock()
_THREAD_ID_REQUIRED_MESSAGE = (
    "LangGraph thread_id missing. Pass it via config['configurable']['thread_id']."
)
_THREAD_ID_MAX_LENGTH = 96
_THREAD_ID_SANITIZE_PATTERN = re.compile(r"[\s\0\r\n\t]+")
_CHECKPOINTER_METHOD_SETS: tuple[tuple[str, ...], ...] = (
    ("get", "put"),
    ("get_tuple", "put"),
)
_DEFAULT_CHECKPOINT_TTL_SECONDS = 3600

if CheckpointTuple is None:

    class _CompatCheckpointTuple(NamedTuple):
        config: dict[str, Any]
        checkpoint: dict[str, Any]
        metadata: dict[str, Any]
        parent_config: dict[str, Any] | None = None
        pending_writes: list[tuple[str, str, Any]] | None = None

else:
    _CompatCheckpointTuple = CheckpointTuple

_RedisCheckpointerBase = BaseCheckpointSaver if BaseCheckpointSaver is not None else object


def _checkpoint_ttl_seconds() -> int:
    """Load checkpoint TTL from environment with a safe fallback."""
    raw_value = os.getenv("LANGGRAPH_CHECKPOINT_TTL_SECONDS")
    if raw_value is None:
        return _DEFAULT_CHECKPOINT_TTL_SECONDS
    try:
        parsed = int(raw_value)
    except ValueError:
        logger.warning(
            "Invalid LANGGRAPH_CHECKPOINT_TTL_SECONDS=%s; using default %s",
            raw_value,
            _DEFAULT_CHECKPOINT_TTL_SECONDS,
        )
        return _DEFAULT_CHECKPOINT_TTL_SECONDS
    if parsed < 60:
        logger.warning(
            "LANGGRAPH_CHECKPOINT_TTL_SECONDS too low (%s); using minimum 60 seconds",
            parsed,
        )
        return 60
    return parsed


def _is_supported_checkpointer(checkpointer: Any) -> bool:
    """Return whether a checkpointer is accepted by the installed LangGraph runtime."""
    if checkpointer is None:
        return False
    if BaseCheckpointSaver is not None:
        # LangGraph>=1.0 validates against BaseCheckpointSaver explicitly.
        return isinstance(checkpointer, BaseCheckpointSaver)

    # Compatibility path for older LangGraph versions that accepted duck typing.
    for method_names in _CHECKPOINTER_METHOD_SETS:
        if all(callable(getattr(checkpointer, method_name, None)) for method_name in method_names):
            return True
    return False


def get_graph_checkpointer(graph_name: str) -> Any | None:
    """Return a cached checkpointer isolated by graph name.

    Tries Redis-backed persistence first (survives Cloud Run restarts),
    falls back to in-memory MemorySaver.
    """
    with _CHECKPOINTERS_LOCK:
        checkpointer = _CHECKPOINTERS.get(graph_name)
        if checkpointer is not None:
            if isinstance(checkpointer, RedisCheckpointer):
                try:
                    checkpointer.redis.ping()
                except Exception as exc:
                    logger.warning(
                        "Discarding stale Redis checkpointer for graph %s: %s",
                        graph_name,
                        exc,
                    )
                    _CHECKPOINTERS.pop(graph_name, None)
                    checkpointer = None
            if _is_supported_checkpointer(checkpointer):
                return checkpointer
            logger.warning(
                "Discarding incompatible cached checkpointer for graph %s: %s",
                graph_name,
                type(checkpointer).__name__,
            )
            _CHECKPOINTERS.pop(graph_name, None)
            checkpointer = None

        # Try Redis-backed checkpointer first
        try:
            from app.core.redis_manager import get_sync_redis_client
            redis_client = get_sync_redis_client()
            if redis_client is not None:
                # Validate connectivity before registering the Redis checkpointer.
                redis_client.ping()
                checkpointer = RedisCheckpointer(
                    redis_client,
                    ttl=_checkpoint_ttl_seconds(),
                    prefix=f"langgraph:checkpoint:{graph_name}:",
                )
                if _is_supported_checkpointer(checkpointer):
                    _CHECKPOINTERS[graph_name] = checkpointer
                    logger.info("Using Redis-backed checkpointer for graph %s", graph_name)
                    return checkpointer
                logger.warning(
                    "Redis checkpointer incompatible with current LangGraph runtime "
                    "for graph %s; falling back to in-memory saver",
                    graph_name,
                )
        except Exception as exc:
            logger.warning("Redis checkpointer unavailable for graph %s: %s", graph_name, exc)

        # Fallback to in-memory
        if MemorySaver is None:
            return None
        checkpointer = MemorySaver()
        if not _is_supported_checkpointer(checkpointer):
            logger.warning(
                "In-memory checkpointer incompatible with current LangGraph runtime for graph %s",
                graph_name,
            )
            return None
        _CHECKPOINTERS[graph_name] = checkpointer
        logger.info("Using in-memory checkpointer for graph %s (state lost on restart)", graph_name)
        return checkpointer



class RedisCheckpointer(_RedisCheckpointerBase):
    """Redis-backed LangGraph checkpointer compatible with BaseCheckpointSaver."""

    def __init__(
        self,
        redis_client: Any,
        ttl: int = 3600,
        prefix: str = "langgraph:checkpoint:",
    ):
        if BaseCheckpointSaver is not None:
            super().__init__()
        self.redis = redis_client
        self.ttl = ttl
        self.prefix = prefix

    def _checkpoint_key(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> str:
        return f"{self.prefix}ckpt:{thread_id}:{checkpoint_ns}:{checkpoint_id}"

    def _latest_key(self, thread_id: str, checkpoint_ns: str) -> str:
        return f"{self.prefix}latest:{thread_id}:{checkpoint_ns}"

    def _index_key(self, thread_id: str, checkpoint_ns: str) -> str:
        return f"{self.prefix}index:{thread_id}:{checkpoint_ns}"

    def _writes_key(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> str:
        return f"{self.prefix}writes:{thread_id}:{checkpoint_ns}:{checkpoint_id}"

    @staticmethod
    def _to_str(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore")
        return str(value)

    @staticmethod
    def _loads(payload: Any, default: Any) -> Any:
        if not payload:
            return default
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", errors="ignore")
        if not isinstance(payload, str):
            return default
        try:
            return json.loads(payload)
        except Exception:
            return default

    @staticmethod
    def _dumps(payload: Any) -> str:
        return json.dumps(payload, default=str, ensure_ascii=False)

    def _thread_context(self, config: Any) -> tuple[str, str]:
        configurable = (config or {}).get("configurable")
        if not isinstance(configurable, Mapping):
            raise ValueError(_THREAD_ID_REQUIRED_MESSAGE)
        thread_id = validate_thread_id(configurable.get("thread_id"))
        checkpoint_ns = str(configurable.get("checkpoint_ns", ""))
        return thread_id, checkpoint_ns

    def _checkpoint_id_from_config(self, config: Any) -> str | None:
        checkpoint_id = get_checkpoint_id(config)
        return self._to_str(checkpoint_id)

    def _load_checkpoint_payload(
        self, thread_id: str, checkpoint_ns: str, checkpoint_id: str
    ) -> dict[str, Any] | None:
        data = self.redis.get(self._checkpoint_key(thread_id, checkpoint_ns, checkpoint_id))
        payload = self._loads(data, default=None)
        if not isinstance(payload, dict):
            return None
        checkpoint = payload.get("checkpoint")
        metadata = payload.get("metadata")
        if not isinstance(checkpoint, dict):
            return None
        if not isinstance(metadata, dict):
            payload["metadata"] = {}
        return payload

    def _list_checkpoint_ids(self, thread_id: str, checkpoint_ns: str) -> list[str]:
        checkpoint_ids: list[str] = []
        try:
            raw_ids = self.redis.smembers(self._index_key(thread_id, checkpoint_ns)) or set()
            checkpoint_ids.extend(
                self._to_str(item) or "" for item in raw_ids if self._to_str(item)
            )
        except Exception:
            pass

        latest_id = self._to_str(self.redis.get(self._latest_key(thread_id, checkpoint_ns)))
        if latest_id:
            checkpoint_ids.append(latest_id)

        # UUIDv6 strings sort chronologically lexicographically.
        return sorted(set(checkpoint_ids), reverse=True)

    def _build_checkpoint_tuple(
        self,
        *,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        payload: dict[str, Any],
    ) -> _CompatCheckpointTuple:
        checkpoint = payload.get("checkpoint", {})
        metadata = payload.get("metadata", {})
        parent_checkpoint_id = self._to_str(payload.get("parent_checkpoint_id"))

        pending_writes_payload = self._loads(
            self.redis.get(self._writes_key(thread_id, checkpoint_ns, checkpoint_id)),
            default=[],
        )
        pending_writes: list[tuple[str, str, Any]] = []
        if isinstance(pending_writes_payload, list):
            for entry in pending_writes_payload:
                if not isinstance(entry, dict):
                    continue
                task_id = self._to_str(entry.get("task_id")) or ""
                channel = self._to_str(entry.get("channel")) or ""
                pending_writes.append((task_id, channel, entry.get("value")))

        config_payload = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }
        parent_config = (
            {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": parent_checkpoint_id,
                }
            }
            if parent_checkpoint_id
            else None
        )
        return _CompatCheckpointTuple(
            config=config_payload,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
            pending_writes=pending_writes,
        )

    def get(self, config: dict) -> Any | None:
        tuple_value = self.get_tuple(config)
        return tuple_value.checkpoint if tuple_value else None

    def get_tuple(self, config: dict) -> _CompatCheckpointTuple | None:
        try:
            thread_id, checkpoint_ns = self._thread_context(config)
        except ValueError:
            logger.warning("Skipping checkpoint load because thread_id is missing in config")
            return None

        checkpoint_id = self._checkpoint_id_from_config(config)
        if checkpoint_id is None:
            checkpoint_id = self._to_str(self.redis.get(self._latest_key(thread_id, checkpoint_ns)))
        if checkpoint_id is None:
            return None

        payload = self._load_checkpoint_payload(thread_id, checkpoint_ns, checkpoint_id)
        if payload is None:
            return None
        return self._build_checkpoint_tuple(
            thread_id=thread_id,
            checkpoint_ns=checkpoint_ns,
            checkpoint_id=checkpoint_id,
            payload=payload,
        )

    def list(
        self,
        config: dict | None,
        *,
        filter: dict[str, Any] | None = None,
        before: dict | None = None,
        limit: int | None = None,
    ) -> Iterator[_CompatCheckpointTuple]:
        if config is None:
            return iter(())

        try:
            thread_id, checkpoint_ns = self._thread_context(config)
        except ValueError:
            return iter(())

        target_checkpoint_id = self._checkpoint_id_from_config(config)
        before_checkpoint_id = self._checkpoint_id_from_config(before) if before else None

        def _iter() -> Iterator[_CompatCheckpointTuple]:
            yielded = 0
            for checkpoint_id in self._list_checkpoint_ids(thread_id, checkpoint_ns):
                if target_checkpoint_id and checkpoint_id != target_checkpoint_id:
                    continue
                if before_checkpoint_id and checkpoint_id >= before_checkpoint_id:
                    continue
                payload = self._load_checkpoint_payload(thread_id, checkpoint_ns, checkpoint_id)
                if payload is None:
                    continue
                metadata = payload.get("metadata", {})
                if filter and any(metadata.get(k) != v for k, v in filter.items()):
                    continue
                yield self._build_checkpoint_tuple(
                    thread_id=thread_id,
                    checkpoint_ns=checkpoint_ns,
                    checkpoint_id=checkpoint_id,
                    payload=payload,
                )
                yielded += 1
                if limit is not None and yielded >= limit:
                    break

        return _iter()

    def put(
        self,
        config: dict,
        checkpoint: dict,
        metadata: dict | None = None,
        new_versions: dict | None = None,
    ) -> dict:
        del new_versions
        try:
            thread_id, checkpoint_ns = self._thread_context(config)
        except ValueError:
            logger.warning("Skipping checkpoint save because thread_id is missing in config")
            return config

        checkpoint_id = self._to_str(checkpoint.get("id"))
        if not checkpoint_id:
            logger.warning(
                "Skipping checkpoint save because checkpoint id is missing for thread %s",
                thread_id,
            )
            return config

        enriched_metadata = get_checkpoint_metadata(config, metadata or {})
        payload = {
            "checkpoint": checkpoint,
            "metadata": enriched_metadata,
            "parent_checkpoint_id": self._checkpoint_id_from_config(config),
        }

        checkpoint_key = self._checkpoint_key(thread_id, checkpoint_ns, checkpoint_id)
        latest_key = self._latest_key(thread_id, checkpoint_ns)
        index_key = self._index_key(thread_id, checkpoint_ns)
        serialized = self._dumps(payload)

        try:
            self.redis.setex(checkpoint_key, self.ttl, serialized)
            self.redis.setex(latest_key, self.ttl, checkpoint_id)
            self.redis.sadd(index_key, checkpoint_id)
            self.redis.expire(index_key, self.ttl)
        except Exception as exc:
            logger.warning("Failed to save checkpoint for thread %s: %s", thread_id, exc)

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    def put_writes(
        self,
        config: dict,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        try:
            thread_id, checkpoint_ns = self._thread_context(config)
        except ValueError:
            return

        checkpoint_id = self._checkpoint_id_from_config(config)
        if not checkpoint_id:
            return

        writes_key = self._writes_key(thread_id, checkpoint_ns, checkpoint_id)
        existing_payload = self._loads(self.redis.get(writes_key), default=[])
        existing: list[dict[str, Any]] = (
            existing_payload if isinstance(existing_payload, list) else []
        )
        dedupe = {
            (self._to_str(item.get("task_id")) or "", int(item.get("idx", -1)))
            for item in existing
            if isinstance(item, dict)
        }

        for idx, (channel, value) in enumerate(writes):
            write_idx = int(WRITES_IDX_MAP.get(channel, idx))
            dedupe_key = (task_id, write_idx)
            if write_idx >= 0 and dedupe_key in dedupe:
                continue
            existing.append(
                {
                    "task_id": task_id,
                    "channel": channel,
                    "value": value,
                    "task_path": task_path,
                    "idx": write_idx,
                }
            )
            dedupe.add(dedupe_key)

        try:
            self.redis.setex(writes_key, self.ttl, self._dumps(existing))
        except Exception as exc:
            logger.warning("Failed to save checkpoint writes for thread %s: %s", thread_id, exc)

    def delete_thread(self, thread_id: str) -> None:
        normalized_thread_id = validate_thread_id(thread_id)
        patterns = (
            f"{self.prefix}ckpt:{normalized_thread_id}:*",
            f"{self.prefix}latest:{normalized_thread_id}:*",
            f"{self.prefix}index:{normalized_thread_id}:*",
            f"{self.prefix}writes:{normalized_thread_id}:*",
        )
        keys: list[str] = []
        try:
            for pattern in patterns:
                for key in self.redis.scan_iter(match=pattern):
                    key_str = self._to_str(key)
                    if key_str:
                        keys.append(key_str)
            if keys:
                self.redis.delete(*keys)
        except Exception as exc:
            logger.warning(
                "Failed to delete checkpoints for thread %s: %s",
                normalized_thread_id,
                exc,
            )

    async def aget(self, config: dict) -> Any | None:
        return self.get(config)

    async def aget_tuple(self, config: dict) -> _CompatCheckpointTuple | None:
        return self.get_tuple(config)

    async def alist(
        self,
        config: dict | None,
        *,
        filter: dict[str, Any] | None = None,
        before: dict | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[_CompatCheckpointTuple]:
        for item in self.list(config, filter=filter, before=before, limit=limit):
            yield item

    async def aput(
        self,
        config: dict,
        checkpoint: dict,
        metadata: dict | None = None,
        new_versions: dict | None = None,
    ) -> dict:
        return self.put(config, checkpoint, metadata, new_versions)

    async def aput_writes(
        self,
        config: dict,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        self.put_writes(config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id: str) -> None:
        self.delete_thread(thread_id)


def compile_graph(builder: Any, *, graph_name: str) -> Any:
    """Compile a graph with an isolated per-graph checkpointer when available."""
    checkpointer = get_graph_checkpointer(graph_name)
    if checkpointer is not None:
        return builder.compile(checkpointer=checkpointer)
    return builder.compile()


def validate_thread_id(thread_id: Any) -> str:
    """Validate and normalize LangGraph thread ids."""
    if thread_id is None:
        raise ValueError(_THREAD_ID_REQUIRED_MESSAGE)
    normalized = _THREAD_ID_SANITIZE_PATTERN.sub("-", str(thread_id).strip())
    if not normalized:
        raise ValueError(_THREAD_ID_REQUIRED_MESSAGE)
    if len(normalized) > _THREAD_ID_MAX_LENGTH:
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
        normalized = f"{normalized[:48]}:{digest}"
    return normalized


def build_configurable_payload(*, thread_id: Any, **extra: Any) -> dict[str, Any]:
    """Build a canonical configurable payload with validated thread_id."""
    payload = {"thread_id": validate_thread_id(thread_id)}
    payload.update({k: v for k, v in extra.items() if k != "thread_id"})
    return payload


def build_graph_config(*, thread_id: Any, **extra: Any) -> dict[str, dict[str, Any]]:
    """Build canonical LangGraph config payload."""
    return {"configurable": build_configurable_payload(thread_id=thread_id, **extra)}


def require_configurable_thread_id(config: Any) -> str:
    """Extract and validate thread_id from LangGraph run config."""
    configurable = (config or {}).get("configurable")
    if not isinstance(configurable, Mapping):
        raise ValueError(_THREAD_ID_REQUIRED_MESSAGE)
    return validate_thread_id(configurable.get("thread_id"))


def _duration_ms(start_time: float) -> float:
    return round((time.perf_counter() - start_time) * 1000.0, 3)


def _extract_thread_id(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str | None:
    """Best-effort extraction of thread_id from node call args/kwargs."""
    config = kwargs.get("config")
    if config is None and len(args) >= 2:
        candidate = args[1]
        if isinstance(candidate, Mapping):
            config = candidate
    if not isinstance(config, Mapping):
        return None
    configurable = config.get("configurable")
    if not isinstance(configurable, Mapping):
        return None
    try:
        return validate_thread_id(configurable.get("thread_id"))
    except ValueError:
        return None


def instrument_node(
    node_name: str,
    node_fn: Callable[..., Any],
    *,
    graph_name: str,
) -> Callable[..., Any]:
    """Wrap a LangGraph node function with lightweight execution logs."""
    if inspect.iscoroutinefunction(node_fn):

        @wraps(node_fn)
        async def async_wrapped(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            thread_id = _extract_thread_id(args, kwargs)
            logger.info(
                "node_start",
                extra={
                    "graph_name": graph_name,
                    "node_name": node_name,
                    "thread_id": thread_id,
                    "duration_ms": 0.0,
                },
            )
            try:
                result = await node_fn(*args, **kwargs)
            except Exception as exc:
                logger.exception(
                    "node_error",
                    extra={
                        "graph_name": graph_name,
                        "node_name": node_name,
                        "thread_id": thread_id,
                        "error_type": type(exc).__name__,
                        "duration_ms": _duration_ms(start_time),
                    },
                )
                raise
            logger.info(
                "node_end",
                extra={
                    "graph_name": graph_name,
                    "node_name": node_name,
                    "thread_id": thread_id,
                    "duration_ms": _duration_ms(start_time),
                },
            )
            return result

        return async_wrapped

    @wraps(node_fn)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        start_time = time.perf_counter()
        thread_id = _extract_thread_id(args, kwargs)
        logger.info(
            "node_start",
            extra={
                "graph_name": graph_name,
                "node_name": node_name,
                "thread_id": thread_id,
                "duration_ms": 0.0,
            },
        )
        try:
            result = node_fn(*args, **kwargs)
        except Exception as exc:
            logger.exception(
                "node_error",
                extra={
                    "graph_name": graph_name,
                    "node_name": node_name,
                    "thread_id": thread_id,
                    "error_type": type(exc).__name__,
                    "duration_ms": _duration_ms(start_time),
                },
            )
            raise
        logger.info(
            "node_end",
            extra={
                "graph_name": graph_name,
                "node_name": node_name,
                "thread_id": thread_id,
                "duration_ms": _duration_ms(start_time),
            },
        )
        return result

    return wrapped
