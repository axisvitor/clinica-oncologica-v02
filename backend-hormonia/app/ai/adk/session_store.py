from __future__ import annotations

import asyncio
import inspect
import json
from copy import deepcopy
from datetime import datetime, timedelta
from threading import Lock
from typing import Any
from uuid import uuid4

from app.core.redis_manager import get_sync_redis_client
from app.utils.timezone import now_sao_paulo

SESSION_TTL_SECONDS = int(timedelta(hours=24).total_seconds())
SESSION_RETENTION_TTL_SECONDS = int(timedelta(days=7).total_seconds())
INVOCATION_TTL_SECONDS = int(timedelta(days=3).total_seconds())
DEFAULT_STATE_SIZE_LIMIT_BYTES = 32 * 1024

_SESSION_KEY_PREFIX = "adk:session:"
_INVOCATION_KEY_PREFIX = "adk:invocation:"
_MEMORY_STORE_LOCK = Lock()
_MEMORY_SESSIONS: dict[str, tuple[dict[str, Any], datetime]] = {}
_MEMORY_INVOCATIONS: dict[str, tuple[dict[str, Any], datetime]] = {}


def _iso_now() -> str:
    return now_sao_paulo().isoformat()


def _expires_at(ttl_seconds: int) -> str:
    return (now_sao_paulo() + timedelta(seconds=ttl_seconds)).isoformat()


def _memory_expiry(ttl_seconds: int) -> datetime:
    return now_sao_paulo() + timedelta(seconds=ttl_seconds)


def _json_bytes(payload: Any) -> int:
    return len(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"))


def _copy_payload(payload: Any) -> Any:
    return deepcopy(payload)


def _summary_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        if "text" in result and isinstance(result["text"], str):
            return result["text"]
        if "message" in result and isinstance(result["message"], str):
            return result["message"]
    return json.dumps(result, ensure_ascii=False, default=str)


class ADKSessionStore:
    """Application-owned ADK session and invocation metadata store.

    Redis is the primary backing store. A process-local memory fallback keeps
    local test and host-compatibility flows working when Redis is unavailable.
    """

    def __init__(
        self,
        redis_client: Any | None = None,
        *,
        session_ttl_seconds: int = SESSION_TTL_SECONDS,
        session_retention_ttl_seconds: int = SESSION_RETENTION_TTL_SECONDS,
        invocation_ttl_seconds: int = INVOCATION_TTL_SECONDS,
        default_state_size_limit_bytes: int = DEFAULT_STATE_SIZE_LIMIT_BYTES,
    ) -> None:
        if redis_client is None:
            try:
                redis_client = get_sync_redis_client()
            except Exception:  # noqa: BLE001
                redis_client = None

        self.redis = redis_client
        self.session_ttl_seconds = session_ttl_seconds
        self.session_retention_ttl_seconds = session_retention_ttl_seconds
        self.invocation_ttl_seconds = invocation_ttl_seconds
        self.default_state_size_limit_bytes = default_state_size_limit_bytes

    async def create_session(
        self,
        *,
        tool_name: str,
        user_id: str,
        session_id: str | None = None,
        state_size_limit_bytes: int | None = None,
    ) -> dict[str, Any]:
        session_id = session_id or f"adk-session-{uuid4().hex}"
        limit_bytes = state_size_limit_bytes or self.default_state_size_limit_bytes
        payload = {
            "session_id": session_id,
            "tool_name": tool_name,
            "user_id": user_id,
            "status": "open",
            "created_at": _iso_now(),
            "last_activity": _iso_now(),
            "expires_at": _expires_at(self.session_ttl_seconds),
            "closed_at": None,
            "last_invocation_id": None,
            "state_size_limit_bytes": limit_bytes,
            "state_size_bytes": 0,
            "state": {},
        }
        await self._write_session(payload, ttl_seconds=self.session_ttl_seconds)
        return payload

    async def get_session(
        self,
        session_id: str,
        *,
        touch: bool = False,
    ) -> dict[str, Any] | None:
        payload = await self._read_session(session_id)
        if payload is None:
            return None

        if payload.get("status") == "open" and self._is_expired(payload):
            payload["status"] = "expired"
            payload["closed_at"] = payload.get("closed_at") or _iso_now()
            await self._write_session(
                payload, ttl_seconds=self.session_retention_ttl_seconds
            )
            return payload

        if touch and payload.get("status") == "open":
            payload["last_activity"] = _iso_now()
            payload["expires_at"] = _expires_at(self.session_ttl_seconds)
            await self._write_session(payload, ttl_seconds=self.session_ttl_seconds)

        return payload

    async def close_session(self, session_id: str) -> dict[str, Any] | None:
        payload = await self.get_session(session_id)
        if payload is None:
            return None

        if payload.get("status") != "closed":
            payload["status"] = "closed"
            payload["closed_at"] = _iso_now()
            payload["last_activity"] = _iso_now()
            payload["expires_at"] = _expires_at(self.session_retention_ttl_seconds)
            await self._write_session(
                payload, ttl_seconds=self.session_retention_ttl_seconds
            )

        return payload

    async def update_session_state(
        self,
        session_id: str,
        *,
        tool_name: str,
        prompt: str,
        context: dict[str, Any] | None,
        result: Any,
        state_size_limit_bytes: int | None = None,
        invocation_id: str | None = None,
    ) -> dict[str, Any] | None:
        payload = await self.get_session(session_id)
        if payload is None or payload.get("status") != "open":
            return payload

        limit_bytes = (
            state_size_limit_bytes
            or payload.get("state_size_limit_bytes")
            or self.default_state_size_limit_bytes
        )
        state = _copy_payload(payload.get("state") or {})
        state = self._merge_operator_state(state, context or {})
        state.setdefault("recent_turns", [])
        if isinstance(state["recent_turns"], list):
            state["recent_turns"].append(
                {
                    "prompt": prompt,
                    "output": _summary_text(result),
                    "tool_name": tool_name,
                    "timestamp": _iso_now(),
                }
            )
        state["recent_successful_turn"] = {
            "prompt": prompt,
            "output": _summary_text(result),
            "tool_name": tool_name,
            "timestamp": _iso_now(),
        }

        pruned_state, state_size_bytes, oversized = self._prune_state(
            state, limit_bytes=limit_bytes
        )
        payload["state"] = pruned_state
        payload["state_size_limit_bytes"] = limit_bytes
        payload["state_size_bytes"] = state_size_bytes
        payload["last_activity"] = _iso_now()
        payload["expires_at"] = _expires_at(self.session_ttl_seconds)
        payload["last_invocation_id"] = invocation_id
        payload["oversized_after_prune"] = oversized
        await self._write_session(payload, ttl_seconds=self.session_ttl_seconds)
        return payload

    async def prepare_resume(
        self,
        session_id: str,
        *,
        tool_name: str,
        state_size_limit_bytes: int | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
        payload = await self.get_session(session_id)
        if payload is None:
            return None, None, "not_found"
        if payload.get("status") == "closed":
            return payload, None, "closed"
        if payload.get("status") == "expired":
            return payload, None, "expired"
        if payload.get("tool_name") != tool_name:
            return payload, None, "tool_mismatch"

        limit_bytes = (
            state_size_limit_bytes
            or payload.get("state_size_limit_bytes")
            or self.default_state_size_limit_bytes
        )
        pruned_state, state_size_bytes, oversized = self._prune_state(
            payload.get("state") or {}, limit_bytes=limit_bytes
        )
        payload["state"] = pruned_state
        payload["state_size_limit_bytes"] = limit_bytes
        payload["state_size_bytes"] = state_size_bytes
        payload["oversized_after_prune"] = oversized
        payload["last_activity"] = _iso_now()
        payload["expires_at"] = _expires_at(self.session_ttl_seconds)
        await self._write_session(payload, ttl_seconds=self.session_ttl_seconds)

        if oversized:
            return payload, None, "oversized"

        return payload, self._context_from_state(pruned_state), None

    def _invocation_payload(
        self,
        *,
        invocation_id: str,
        session_id: str | None,
        tool_name: str,
        user_id: str,
        runtime: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "invocation_id": invocation_id,
            "session_id": session_id,
            "tool_name": tool_name,
            "user_id": user_id,
            "status": "pending",
            "created_at": _iso_now(),
            "updated_at": _iso_now(),
            "completed_at": None,
            "cancelled_at": None,
            "runtime": runtime,
            "result": None,
        }

    async def register_invocation(
        self,
        *,
        invocation_id: str,
        session_id: str | None,
        tool_name: str,
        user_id: str,
        runtime: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self._invocation_payload(
            invocation_id=invocation_id,
            session_id=session_id,
            tool_name=tool_name,
            user_id=user_id,
            runtime=runtime,
        )
        await self._write_invocation(payload)
        if session_id:
            session = await self.get_session(session_id)
            if session is not None:
                session["last_invocation_id"] = invocation_id
                await self._write_session(session, ttl_seconds=self.session_ttl_seconds)
        return payload

    async def reserve_invocation(
        self,
        *,
        invocation_id: str,
        session_id: str | None,
        tool_name: str,
        user_id: str,
        runtime: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, bool]:
        """Create an invocation only if the id is currently unclaimed.

        Runtime callers may supply invocation ids for lifecycle correlation. Treat
        those ids as globally reserved so a second caller cannot overwrite an
        existing invocation's stored owner before ownership checks run.
        """
        payload = self._invocation_payload(
            invocation_id=invocation_id,
            session_id=session_id,
            tool_name=tool_name,
            user_id=user_id,
            runtime=runtime,
        )
        reserved = await self._write_invocation_if_absent(payload)
        if not reserved:
            return await self.get_invocation(invocation_id), False

        if session_id:
            session = await self.get_session(session_id)
            if session is not None:
                session["last_invocation_id"] = invocation_id
                await self._write_session(session, ttl_seconds=self.session_ttl_seconds)
        return payload, True

    async def get_invocation(self, invocation_id: str) -> dict[str, Any] | None:
        return await self._read_invocation(invocation_id)

    async def mark_invocation_running(self, invocation_id: str) -> dict[str, Any] | None:
        payload = await self.get_invocation(invocation_id)
        if payload is None:
            return None

        payload["status"] = "running"
        payload["updated_at"] = _iso_now()
        await self._write_invocation(payload)
        return payload

    async def cancel_invocation(self, invocation_id: str) -> dict[str, Any] | None:
        payload = await self.get_invocation(invocation_id)
        if payload is None:
            return None

        if payload.get("status") not in {"completed", "cancelled", "timeout", "limit_exceeded"}:
            payload["status"] = "cancelled"
            payload["cancelled_at"] = _iso_now()
            payload["updated_at"] = _iso_now()
            payload["completed_at"] = payload["cancelled_at"]
            payload["result"] = {
                "message": "Invocation cancelled by operator",
                "invocation_id": invocation_id,
            }
            await self._write_invocation(payload)
        return payload

    async def finish_invocation(
        self,
        invocation_id: str,
        *,
        status: str,
        result: Any,
    ) -> dict[str, Any] | None:
        payload = await self.get_invocation(invocation_id)
        if payload is None:
            return None

        if payload.get("status") == "cancelled":
            return payload

        payload["status"] = status
        payload["updated_at"] = _iso_now()
        payload["completed_at"] = _iso_now()
        payload["result"] = result
        await self._write_invocation(payload)
        return payload

    def build_run_context(
        self,
        *,
        request_context: dict[str, Any] | None,
        session_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        merged = _copy_payload(request_context or {})
        if not session_context:
            return merged

        for key, value in session_context.items():
            if key not in merged:
                merged[key] = _copy_payload(value)
                continue

            if (
                key == "patient_context"
                and isinstance(value, dict)
                and isinstance(merged.get(key), dict)
            ):
                merged[key] = {**value, **merged[key]}
                continue

            if isinstance(value, list) and isinstance(merged.get(key), list):
                merged[key] = [*_copy_payload(value), *merged[key]]

        if "recent_successful_turn" in session_context:
            merged.setdefault(
                "recent_successful_turn",
                _copy_payload(session_context["recent_successful_turn"]),
            )
        return merged

    def _merge_operator_state(
        self,
        state: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        payload = _copy_payload(state)
        operator_context = self._operator_context(context)
        for key, value in operator_context.items():
            if key == "patient_context" and isinstance(value, dict):
                base_value = payload.get(key)
                if isinstance(base_value, dict):
                    payload[key] = {**base_value, **value}
                else:
                    payload[key] = _copy_payload(value)
                continue

            payload[key] = _copy_payload(value)
        return payload

    def _context_from_state(self, state: dict[str, Any]) -> dict[str, Any]:
        context = _copy_payload(state)
        recent_turns = context.get("recent_turns")
        if isinstance(recent_turns, list):
            context.setdefault("conversation_history", _copy_payload(recent_turns))
        return context

    def _prune_state(
        self,
        state: dict[str, Any],
        *,
        limit_bytes: int,
    ) -> tuple[dict[str, Any], int, bool]:
        payload = _copy_payload(state)
        for list_key in (
            "conversation_history",
            "previous_questions",
            "recent_turns",
            "personalization_hints",
        ):
            current = payload.get(list_key)
            if not isinstance(current, list):
                continue

            while current and _json_bytes(payload) > limit_bytes:
                current.pop(0)

            if current:
                payload[list_key] = current
            else:
                payload.pop(list_key, None)

        size_bytes = _json_bytes(payload)
        return payload, size_bytes, size_bytes > limit_bytes

    def _operator_context(self, context: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for key, value in context.items():
            if key in {
                "tool_name",
                "user_id",
                "request_source",
                "runtime",
                "session",
                "invocation",
                "session_id",
                "invocation_id",
            }:
                continue
            payload[key] = _copy_payload(value)
        return payload

    def _is_expired(self, payload: dict[str, Any]) -> bool:
        expires_at = payload.get("expires_at")
        if not isinstance(expires_at, str):
            return False
        try:
            expires_dt = datetime.fromisoformat(expires_at)
        except ValueError:
            return False
        return expires_dt <= now_sao_paulo()

    async def _read_session(self, session_id: str) -> dict[str, Any] | None:
        return await self._read_payload(
            store=_MEMORY_SESSIONS,
            key=f"{_SESSION_KEY_PREFIX}{session_id}",
        )

    async def _write_session(
        self,
        payload: dict[str, Any],
        *,
        ttl_seconds: int,
    ) -> None:
        await self._write_payload(
            store=_MEMORY_SESSIONS,
            key=f"{_SESSION_KEY_PREFIX}{payload['session_id']}",
            payload=payload,
            ttl_seconds=ttl_seconds,
        )

    async def _read_invocation(self, invocation_id: str) -> dict[str, Any] | None:
        return await self._read_payload(
            store=_MEMORY_INVOCATIONS,
            key=f"{_INVOCATION_KEY_PREFIX}{invocation_id}",
        )

    async def _write_invocation(self, payload: dict[str, Any]) -> None:
        await self._write_payload(
            store=_MEMORY_INVOCATIONS,
            key=f"{_INVOCATION_KEY_PREFIX}{payload['invocation_id']}",
            payload=payload,
            ttl_seconds=self.invocation_ttl_seconds,
        )

    async def _write_invocation_if_absent(self, payload: dict[str, Any]) -> bool:
        return await self._write_payload_if_absent(
            store=_MEMORY_INVOCATIONS,
            key=f"{_INVOCATION_KEY_PREFIX}{payload['invocation_id']}",
            payload=payload,
            ttl_seconds=self.invocation_ttl_seconds,
        )

    async def _read_payload(
        self,
        *,
        store: dict[str, tuple[dict[str, Any], datetime]],
        key: str,
    ) -> dict[str, Any] | None:
        if self.redis is not None:
            raw = await self._redis_call("get", key)
            if raw is None:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            try:
                return json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                return None

        with _MEMORY_STORE_LOCK:
            entry = store.get(key)
            if entry is None:
                return None
            payload, expires_at = entry
            if expires_at <= now_sao_paulo():
                store.pop(key, None)
                return None
            return _copy_payload(payload)

    async def _write_payload(
        self,
        *,
        store: dict[str, tuple[dict[str, Any], datetime]],
        key: str,
        payload: dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        if self.redis is not None:
            await self._redis_call(
                "setex",
                key,
                ttl_seconds,
                json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
            )
            return

        with _MEMORY_STORE_LOCK:
            store[key] = (_copy_payload(payload), _memory_expiry(ttl_seconds))

    async def _write_payload_if_absent(
        self,
        *,
        store: dict[str, tuple[dict[str, Any], datetime]],
        key: str,
        payload: dict[str, Any],
        ttl_seconds: int,
    ) -> bool:
        if self.redis is not None:
            value = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
            result = await self._redis_call(
                "set",
                key,
                value,
                ex=ttl_seconds,
                nx=True,
            )
            return bool(result)

        with _MEMORY_STORE_LOCK:
            entry = store.get(key)
            if entry is not None:
                _, expires_at = entry
                if expires_at > now_sao_paulo():
                    return False
                store.pop(key, None)
            store[key] = (_copy_payload(payload), _memory_expiry(ttl_seconds))
            return True

    async def _redis_call(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        if self.redis is None:
            return None
        method = getattr(self.redis, method_name, None)
        if method is None:
            return None
        if inspect.iscoroutinefunction(method):
            return await method(*args, **kwargs)
        return await asyncio.to_thread(method, *args, **kwargs)
