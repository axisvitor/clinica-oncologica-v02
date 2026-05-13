from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import TYPE_CHECKING, Any
from uuid import uuid4

try:
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    try:
        from google.adk.runners import RunConfig
    except ImportError:
        RunConfig = None
    from google.adk.sessions import InMemorySessionService
    from google.genai import types as genai_types

    HAS_ADK_RUNTIME = True
except ModuleNotFoundError:
    Agent = None
    Runner = None
    RunConfig = None
    genai_types = None
    HAS_ADK_RUNTIME = False

    class InMemorySessionService:  # type: ignore[no-redef]
        pass

if TYPE_CHECKING:
    from app.ai.agents.deps import AIDeps

from app.ai.adk.session_store import ADKSessionStore, DEFAULT_STATE_SIZE_LIMIT_BYTES
from app.ai.adk.metrics import ADK_INVOCATIONS_IN_FLIGHT, record_adk_invocation
from app.ai.adk.tools import (
    ADKToolExecutionError,
    execute_tool_handler,
    get_adk_function_tools,
    get_tool_registry,
    reset_adk_tool_context,
    set_adk_tool_context,
)
from app.config import settings

DEFAULT_MAX_LLM_CALLS = 4
DEFAULT_TIMEOUT_SECONDS = float(
    getattr(settings, "AI_GEMINI_TIMEOUT_SECONDS", 30) or 30
)
_TERMINAL_INVOCATION_STATUSES = {
    "cancelled",
    "completed",
    "error",
    "limit_exceeded",
    "policy_block",
    "timeout",
    "tool_error",
    "unsupported_tool",
    "upstream_error",
}
_PROTECTED_POLICY_KEYS = frozenset({"tool_policy", "policy", "required_context_keys"})
_MISSING_CONTEXT_VALUE = object()
_IN_FLIGHT_INVOCATIONS: dict[str, asyncio.Task[Any]] = {}
_IN_FLIGHT_LOCK = Lock()
_SAFE_LOG_LABEL = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ADKRuntimeControls:
    max_llm_calls: int | None = None
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class ADKSessionControls:
    action: str = "auto"
    session_id: str | None = None
    state_size_limit_bytes: int | None = None


@dataclass(frozen=True)
class ADKInvocationControls:
    action: str = "run"
    invocation_id: str | None = None


@dataclass(frozen=True)
class ADKToolRunRequest:
    prompt: str
    tool_name: str
    deps: AIDeps
    user_id: str
    session_id: str | None = None
    invocation_id: str | None = None
    context: dict[str, Any] | None = None
    runtime: ADKRuntimeControls = field(default_factory=ADKRuntimeControls)
    session: ADKSessionControls = field(default_factory=ADKSessionControls)
    invocation: ADKInvocationControls = field(default_factory=ADKInvocationControls)


@dataclass(frozen=True)
class ADKToolPolicyBlock:
    reason: str
    message: str = "Tool call blocked by policy"
    missing_context_keys: tuple[str, ...] = ()


class ADKLimitExceededError(RuntimeError):
    pass


class ADKUpstreamExecutionError(RuntimeError):
    pass


class ADKLLMBudget:
    def __init__(self, max_calls: int) -> None:
        self.max_calls = max_calls
        self.used_calls = 0

    def consume(self, stage: str) -> None:
        self.used_calls += 1
        if self.used_calls > self.max_calls:
            raise ADKLimitExceededError(stage)


async def run_adk_tool(request: ADKToolRunRequest) -> dict[str, Any]:
    """Execute a single ADK tool invocation with lifecycle-aware controls."""
    registry = get_tool_registry()
    tool_name = request.tool_name.strip().lower()
    handler = registry.get(tool_name)
    if handler is None:
        record_adk_invocation(
            tool_name=tool_name,
            status="unsupported_tool",
            duration_seconds=0.0,
            invocation_id=request.invocation.invocation_id or request.invocation_id,
            session_id=request.session.session_id or request.session_id,
        )
        return _build_result(
            status="unsupported_tool",
            result={
                "message": f"Unsupported ADK tool: {request.tool_name}",
                "tool": request.tool_name,
                "type": "unsupported_tool",
            },
        )

    metrics_start = time.monotonic()

    def _record_metrics(result: dict[str, Any]) -> None:
        record_adk_invocation(
            tool_name=tool_name,
            status=result["status"],
            duration_seconds=max(time.monotonic() - metrics_start, 0.0),
            invocation_id=result.get("invocation_id"),
            session_id=result.get("session_id"),
        )

    store = ADKSessionStore()
    if request.invocation.action == "cancel":
        cancel_result = await _cancel_invocation(
            store=store,
            request=request,
            tool_name=tool_name,
        )
        _record_metrics(cancel_result)
        return cancel_result

    session_resolution = await _resolve_session(store=store, request=request, tool_name=tool_name)
    if "status" in session_resolution:
        _record_metrics(session_resolution)
        return session_resolution

    session_id = str(session_resolution["session_id"])
    merged_context = dict(session_resolution["context"])
    invocation_id = request.invocation.invocation_id or f"adk-invocation-{uuid4().hex}"
    merged_context["session_id"] = session_id
    merged_context["invocation_id"] = invocation_id

    runtime_payload = {
        "max_llm_calls": _resolve_max_llm_calls(request.runtime),
        "timeout_seconds": _resolve_timeout_seconds(request.runtime),
    }

    enriched_request = ADKToolRunRequest(
        prompt=request.prompt,
        tool_name=tool_name,
        deps=request.deps,
        user_id=request.user_id,
        session_id=session_id,
        invocation_id=invocation_id,
        context=merged_context,
        runtime=ADKRuntimeControls(**runtime_payload),
        session=ADKSessionControls(
            action=request.session.action,
            session_id=session_id,
            state_size_limit_bytes=(
                request.session.state_size_limit_bytes
                or DEFAULT_STATE_SIZE_LIMIT_BYTES
            ),
        ),
        invocation=ADKInvocationControls(
            action="run",
            invocation_id=invocation_id,
        ),
    )

    await store.register_invocation(
        invocation_id=invocation_id,
        session_id=session_id,
        tool_name=tool_name,
        user_id=request.user_id,
        runtime=runtime_payload,
    )
    await store.mark_invocation_running(invocation_id)
    _register_in_flight(invocation_id, asyncio.current_task())
    ADK_INVOCATIONS_IN_FLIGHT.labels(tool_name=tool_name).inc()

    try:
        raw_result = await asyncio.wait_for(
            _execute_request(enriched_request, handler=handler),
            timeout=runtime_payload["timeout_seconds"],
        )
        normalized = _normalize_result(raw_result)
        final_invocation = await store.finish_invocation(
            invocation_id,
            status=_invocation_status_for(normalized["status"]),
            result=normalized.get("result"),
        )
        if final_invocation and final_invocation.get("status") == "cancelled":
            cancelled_result = _build_result(
                status="cancelled",
                result=final_invocation.get("result")
                or {
                    "message": "Invocation cancelled by operator",
                    "invocation_id": invocation_id,
                },
                session_id=session_id,
            )
            _record_metrics(cancelled_result)
            return cancelled_result

        if normalized["status"] == "success":
            await store.update_session_state(
                session_id,
                tool_name=tool_name,
                prompt=request.prompt,
                context=merged_context,
                result=normalized.get("result"),
                state_size_limit_bytes=request.session.state_size_limit_bytes,
                invocation_id=invocation_id,
            )

        result = _build_result(
            status=normalized["status"],
            result=normalized.get("result"),
            session_id=session_id,
            invocation_id=invocation_id,
        )
        _record_metrics(result)
        return result
    except asyncio.TimeoutError:
        timeout_result = {
            "message": (
                f"ADK execution timed out after {runtime_payload['timeout_seconds']} seconds"
            ),
            "invocation_id": invocation_id,
            "type": "timeout",
        }
        await store.finish_invocation(
            invocation_id,
            status="timeout",
            result=timeout_result,
        )
        result = _build_result(
            status="timeout",
            result=timeout_result,
            session_id=session_id,
            invocation_id=invocation_id,
        )
        _record_metrics(result)
        return result
    except asyncio.CancelledError:
        cancel_result = {
            "message": "Invocation cancelled by operator",
            "invocation_id": invocation_id,
            "type": "cancelled",
        }
        await store.finish_invocation(
            invocation_id,
            status="cancelled",
            result=cancel_result,
        )
        result = _build_result(
            status="cancelled",
            result=cancel_result,
            session_id=session_id,
            invocation_id=invocation_id,
        )
        _record_metrics(result)
        return result
    except ADKLimitExceededError:
        limit_result = {
            "message": "LLM call budget exhausted before execution completed",
            "invocation_id": invocation_id,
            "max_llm_calls": runtime_payload["max_llm_calls"],
            "type": "limit_exceeded",
        }
        await store.finish_invocation(
            invocation_id,
            status="limit_exceeded",
            result=limit_result,
        )
        result = _build_result(
            status="limit_exceeded",
            result=limit_result,
            session_id=session_id,
            invocation_id=invocation_id,
        )
        _record_metrics(result)
        return result
    except Exception as exc:  # noqa: BLE001
        error_payload = _classify_execution_failure(
            exc,
            tool_name=tool_name,
            invocation_id=invocation_id,
        )
        await store.finish_invocation(
            invocation_id,
            status=error_payload["status"],
            result=error_payload["result"],
        )
        result = _build_result(
            status=error_payload["status"],
            result=error_payload["result"],
            session_id=session_id,
            invocation_id=invocation_id,
        )
        _record_metrics(result)
        return result
    finally:
        ADK_INVOCATIONS_IN_FLIGHT.labels(tool_name=tool_name).dec()
        _unregister_in_flight(invocation_id)


def _register_in_flight(invocation_id: str, task: asyncio.Task[Any] | None) -> None:
    if task is None:
        return
    with _IN_FLIGHT_LOCK:
        _IN_FLIGHT_INVOCATIONS[invocation_id] = task


def _unregister_in_flight(invocation_id: str) -> None:
    with _IN_FLIGHT_LOCK:
        _IN_FLIGHT_INVOCATIONS.pop(invocation_id, None)


def _cancel_in_flight_task(invocation_id: str) -> None:
    with _IN_FLIGHT_LOCK:
        task = _IN_FLIGHT_INVOCATIONS.get(invocation_id)
    if task is not None and not task.done():
        task.cancel()


def _safe_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _safe_log_label(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if _SAFE_LOG_LABEL.fullmatch(text):
        return text
    return f"hashed-{_safe_hash(text)}"


def _context_log_label(context: dict[str, Any] | None, key: str) -> str | None:
    if not isinstance(context, dict):
        return None
    return _safe_log_label(context.get(key))


def _log_adk_runtime_denial(
    *,
    reason: str,
    tool_name: str,
    lifecycle_action: str,
    context: dict[str, Any] | None = None,
) -> None:
    """Emit low-cardinality, PHI-safe diagnostics for denied ADK runtime calls."""
    logger.warning(
        "ADK runtime lifecycle denied",
        extra={
            "event_type": "adk_runtime_denied",
            "reason": reason,
            "route": "adk_runtime",
            "tool_name": _safe_log_label(tool_name),
            "lifecycle_action": lifecycle_action,
            "request_id": _context_log_label(context, "request_id"),
            "correlation_id": _context_log_label(context, "correlation_id"),
        },
    )


def _normalized_owner(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _ownership_error_type(
    payload: dict[str, Any],
    *,
    request_user_id: str,
    resource: str,
) -> str | None:
    stored_owner = _normalized_owner(payload.get("user_id"))
    if stored_owner is None:
        return f"{resource}_owner_missing"

    request_owner = _normalized_owner(request_user_id)
    if request_owner is None or stored_owner != request_owner:
        return f"{resource}_owner_mismatch"

    return None


def _ownership_error_result(
    *,
    resource: str,
    error_type: str,
    resource_id: str,
    tool_name: str,
    lifecycle_action: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _log_adk_runtime_denial(
        reason=error_type,
        tool_name=tool_name,
        lifecycle_action=lifecycle_action,
        context=context,
    )
    label = "Session" if resource == "session" else "Invocation"
    payload: dict[str, Any] = {
        "message": f"{label} cannot be accessed by the current user",
        "type": error_type,
    }
    if resource == "session":
        payload["session_id"] = resource_id
        return _build_result(status="error", result=payload, session_id=resource_id)

    payload["invocation_id"] = resource_id
    return _build_result(status="error", result=payload, invocation_id=resource_id)


async def _cancel_invocation(
    *,
    store: ADKSessionStore,
    request: ADKToolRunRequest,
    tool_name: str,
) -> dict[str, Any]:
    invocation_id = request.invocation.invocation_id or request.invocation_id
    if invocation_id is None:
        return _build_result(
            status="error",
            result={
                "message": "Invocation id is required to cancel a running invocation",
                "type": "invocation_id_required",
            },
        )

    payload = await store.get_invocation(invocation_id)
    if payload is None:
        return _build_result(
            status="error",
            result={
                "message": f"Invocation '{invocation_id}' was not found",
                "invocation_id": invocation_id,
                "type": "invocation_not_found",
            },
            session_id=request.session.session_id or request.session_id,
        )

    ownership_error = _ownership_error_type(
        payload,
        request_user_id=request.user_id,
        resource="invocation",
    )
    if ownership_error is not None:
        return _ownership_error_result(
            resource="invocation",
            error_type=ownership_error,
            resource_id=invocation_id,
            tool_name=tool_name,
            lifecycle_action="cancel",
            context=request.context,
        )

    if payload.get("tool_name") != tool_name:
        return _build_result(
            status="error",
            result={
                "message": "Invocation belongs to a different ADK tool",
                "invocation_id": invocation_id,
                "requested_tool": tool_name,
                "stored_tool": payload.get("tool_name"),
                "type": "invocation_tool_mismatch",
            },
            session_id=payload.get("session_id"),
        )

    payload = await store.cancel_invocation(invocation_id)
    if payload is None:
        return _build_result(
            status="error",
            result={
                "message": f"Invocation '{invocation_id}' was not found",
                "invocation_id": invocation_id,
                "type": "invocation_not_found",
            },
            session_id=request.session.session_id or request.session_id,
        )

    _cancel_in_flight_task(invocation_id)
    return _build_result(
        status="cancelled",
        result=payload.get("result")
        or {
            "message": "Invocation cancelled by operator",
            "invocation_id": invocation_id,
            "type": "cancelled",
        },
        session_id=payload.get("session_id"),
        invocation_id=invocation_id,
    )


async def _resolve_session(
    *,
    store: ADKSessionStore,
    request: ADKToolRunRequest,
    tool_name: str,
) -> dict[str, Any]:
    request_context = dict(request.context or {})
    session_controls = request.session
    session_id = session_controls.session_id or request.session_id

    if session_controls.action == "close":
        if session_id is None:
            return _build_result(
                status="error",
                result={
                    "message": "Session id is required to close a session",
                    "type": "session_id_required",
                },
            )
        payload = await store.get_session(session_id)
        if payload is None:
            return _build_result(
                status="error",
                result={
                    "message": f"Session '{session_id}' was not found",
                    "session_id": session_id,
                    "type": "session_not_found",
                },
                session_id=session_id,
            )
        ownership_error = _ownership_error_type(
            payload,
            request_user_id=request.user_id,
            resource="session",
        )
        if ownership_error is not None:
            return _ownership_error_result(
                resource="session",
                error_type=ownership_error,
                resource_id=session_id,
                tool_name=tool_name,
                lifecycle_action="close",
                context=request_context,
            )
        if payload.get("tool_name") != tool_name:
            return _build_result(
                status="error",
                result={
                    "message": "Session belongs to a different ADK tool",
                    "session_id": session_id,
                    "requested_tool": tool_name,
                    "stored_tool": payload.get("tool_name"),
                    "type": "session_tool_mismatch",
                },
                session_id=session_id,
            )
        payload = await store.close_session(session_id)
        return _build_result(
            status="closed",
            result={
                "message": "Session closed",
                "session_id": session_id,
                "type": "session_closed",
            },
            session_id=session_id,
        )

    if session_controls.action == "resume" or (
        session_controls.action == "auto" and session_id is not None
    ):
        if session_id is None:
            return _build_result(
                status="error",
                result={
                    "message": "Session id is required to resume a session",
                    "type": "session_id_required",
                },
            )
        payload = await store.get_session(session_id)
        if payload is None:
            return _session_error(
                "not_found",
                session_id=session_id,
                requested_tool=tool_name,
                stored_tool=None,
            )
        ownership_error = _ownership_error_type(
            payload,
            request_user_id=request.user_id,
            resource="session",
        )
        if ownership_error is not None:
            return _ownership_error_result(
                resource="session",
                error_type=ownership_error,
                resource_id=session_id,
                tool_name=tool_name,
                lifecycle_action="resume",
                context=request_context,
            )
        payload, session_context, error = await store.prepare_resume(
            session_id,
            tool_name=tool_name,
            state_size_limit_bytes=session_controls.state_size_limit_bytes,
        )
        if error is not None:
            return _session_error(
                error,
                session_id=session_id,
                requested_tool=tool_name,
                stored_tool=payload.get("tool_name") if payload else None,
            )
        context = store.build_run_context(
            request_context=request_context,
            session_context=session_context,
        )
        return {"context": context, "session_id": session_id}

    if session_controls.action == "create" and session_id is not None:
        existing = await store.get_session(session_id)
        if existing is not None and existing.get("status") != "expired":
            return _build_result(
                status="error",
                result={
                    "message": f"Session '{session_id}' already exists",
                    "session_id": session_id,
                    "type": "session_exists",
                },
                session_id=session_id,
            )

    created_session = await store.create_session(
        tool_name=tool_name,
        user_id=request.user_id,
        session_id=session_id if session_controls.action == "create" else None,
        state_size_limit_bytes=session_controls.state_size_limit_bytes,
    )
    context = store.build_run_context(
        request_context=request_context,
        session_context=created_session.get("state"),
    )
    return {"context": context, "session_id": created_session["session_id"]}


def _session_error(
    reason: str,
    *,
    session_id: str,
    requested_tool: str,
    stored_tool: str | None,
) -> dict[str, Any]:
    if reason == "closed":
        message = f"Session '{session_id}' is closed and cannot be reused"
        error_type = "session_closed"
    elif reason == "expired":
        message = f"Session '{session_id}' expired due to inactivity"
        error_type = "session_expired"
    elif reason == "tool_mismatch":
        message = "Session belongs to a different ADK tool"
        error_type = "session_tool_mismatch"
    elif reason == "oversized":
        message = (
            f"Session '{session_id}' exceeds the configured state budget and must be restarted"
        )
        error_type = "session_state_limit_exceeded"
    else:
        message = f"Session '{session_id}' was not found"
        error_type = "session_not_found"

    payload: dict[str, Any] = {
        "message": message,
        "session_id": session_id,
        "type": error_type,
    }
    if stored_tool is not None and stored_tool != requested_tool:
        payload["requested_tool"] = requested_tool
        payload["stored_tool"] = stored_tool

    return _build_result(
        status="error",
        result=payload,
        session_id=session_id,
    )


async def _execute_request(
    request: ADKToolRunRequest,
    *,
    handler: Any,
) -> dict[str, Any]:
    budget = ADKLLMBudget(_resolve_max_llm_calls(request.runtime))
    budget.consume("orchestration")
    budget.consume("tool_execution")

    if HAS_ADK_RUNTIME and Agent is not None and Runner is not None:
        adk_tools = get_adk_function_tools()
        function_tool = adk_tools.get(request.tool_name)

        if function_tool is not None:
            return await _execute_with_adk_runner(
                request=request,
                function_tool=function_tool,
            )

    policy_block = _policy_block_for_request(request)
    if policy_block is not None:
        return policy_block

    result = await execute_tool_handler(
        tool_name=request.tool_name,
        handler=handler,
        prompt=request.prompt,
        deps=request.deps,
        context=request.context,
    )
    return _normalize_result(result)


def _build_run_config(runtime: ADKRuntimeControls) -> Any:
    if RunConfig is None:
        return None
    return RunConfig(max_llm_calls=_resolve_max_llm_calls(runtime))


def _build_result(
    *,
    status: str,
    result: Any,
    session_id: str | None = None,
    invocation_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "status": status,
        "result": result,
    }
    if session_id is not None:
        payload["session_id"] = session_id
    if invocation_id is not None:
        payload["invocation_id"] = invocation_id
    return payload


def _resolve_timeout_seconds(runtime: ADKRuntimeControls) -> float:
    return float(runtime.timeout_seconds or DEFAULT_TIMEOUT_SECONDS)


def _resolve_max_llm_calls(runtime: ADKRuntimeControls) -> int:
    return int(runtime.max_llm_calls or DEFAULT_MAX_LLM_CALLS)


def _invocation_status_for(status: str) -> str:
    if status == "success":
        return "completed"
    if status in _TERMINAL_INVOCATION_STATUSES:
        return status
    return "error"


def _normalize_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict) and "status" in result and "result" in result:
        return result
    return {"status": "success", "result": result}


def _classify_execution_failure(
    exc: Exception,
    *,
    tool_name: str,
    invocation_id: str | None,
) -> dict[str, Any]:
    if isinstance(exc, ADKToolExecutionError):
        status = "tool_error"
        message = str(exc) or f"{tool_name} tool execution failed"
    else:
        status = "upstream_error"
        message = str(exc) or "ADK upstream execution failed"

    payload: dict[str, Any] = {
        "message": message,
        "tool_name": tool_name,
        "type": status,
    }
    if invocation_id is not None:
        payload["invocation_id"] = invocation_id

    return _build_result(
        status=status,
        result=payload,
        invocation_id=invocation_id,
    )


def _policy_block_for_request(request: ADKToolRunRequest) -> dict[str, Any] | None:
    return _evaluate_tool_policy(
        tool_name=request.tool_name,
        prompt=request.prompt,
        context=request.context,
        invocation_id=request.invocation.invocation_id or request.invocation_id,
    )


def _evaluate_tool_policy(
    *,
    tool_name: str,
    prompt: str,
    context: dict[str, Any] | None,
    invocation_id: str | None,
) -> dict[str, Any] | None:
    policy = _extract_tool_policy(context)
    if not policy:
        return None

    global_block = _resolve_global_policy_block(policy, tool_name=tool_name)
    if global_block is not None:
        return _build_policy_block_result(
            tool_name=tool_name,
            invocation_id=invocation_id,
            block=global_block,
        )

    tool_block = _resolve_blocked_tool(policy, tool_name=tool_name)
    if tool_block is not None:
        return _build_policy_block_result(
            tool_name=tool_name,
            invocation_id=invocation_id,
            block=tool_block,
        )

    prompt_block = _resolve_blocked_prompt(policy, prompt=prompt)
    if prompt_block is not None:
        return _build_policy_block_result(
            tool_name=tool_name,
            invocation_id=invocation_id,
            block=prompt_block,
        )

    required_context_block = _resolve_required_context_block(
        policy,
        tool_name=tool_name,
        context=context,
    )
    if required_context_block is not None:
        return _build_policy_block_result(
            tool_name=tool_name,
            invocation_id=invocation_id,
            block=required_context_block,
        )

    return None


def _build_policy_block_result(
    *,
    tool_name: str,
    invocation_id: str | None,
    block: ADKToolPolicyBlock,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "policy_block",
        "message": block.message,
        "tool_name": tool_name,
        "reason": block.reason,
    }
    if invocation_id is not None:
        payload["invocation_id"] = invocation_id
    if block.missing_context_keys:
        payload["missing_context_keys"] = list(block.missing_context_keys)
    return _build_result(
        status="policy_block",
        result=payload,
        invocation_id=invocation_id,
    )


def _extract_tool_policy(context: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(context, dict):
        return {}
    for key in ("tool_policy", "policy"):
        candidate = context.get(key)
        if isinstance(candidate, dict):
            return candidate
    return {}


def _resolve_global_policy_block(
    policy: dict[str, Any],
    *,
    tool_name: str,
) -> ADKToolPolicyBlock | None:
    if not bool(policy.get("block") or policy.get("blocked")):
        return None
    if not _policy_targets_tool(policy.get("tools"), tool_name=tool_name):
        return None
    return _policy_block_from_value(
        policy,
        default_reason="policy_blocked",
    )


def _resolve_blocked_tool(
    policy: dict[str, Any],
    *,
    tool_name: str,
) -> ADKToolPolicyBlock | None:
    blocked_tools = policy.get("blocked_tools")
    if isinstance(blocked_tools, dict):
        entry = blocked_tools.get(tool_name)
        if entry is None:
            entry = blocked_tools.get("*")
        if entry is None:
            return None
        return _policy_block_from_value(
            entry,
            default_reason="tool_not_allowed",
        )

    if _string_list_contains(blocked_tools, tool_name):
        return _policy_block_from_value(
            True,
            default_reason="tool_not_allowed",
        )

    return None


def _resolve_blocked_prompt(
    policy: dict[str, Any],
    *,
    prompt: str,
) -> ADKToolPolicyBlock | None:
    blocked_prompts = policy.get("blocked_prompts")
    if isinstance(blocked_prompts, dict):
        entry = blocked_prompts.get(prompt)
        if entry is None:
            entry = blocked_prompts.get("*")
        if entry is None:
            return None
        return _policy_block_from_value(
            entry,
            default_reason="blocked_prompt",
        )

    if _string_list_contains(blocked_prompts, prompt):
        return _policy_block_from_value(
            True,
            default_reason="blocked_prompt",
        )

    return None


def _resolve_required_context_block(
    policy: dict[str, Any],
    *,
    tool_name: str,
    context: dict[str, Any] | None,
) -> ADKToolPolicyBlock | None:
    raw_required = policy.get("required_context_keys")
    entry: Any = raw_required
    if isinstance(raw_required, dict):
        entry = raw_required.get(tool_name)
        if entry is None:
            entry = raw_required.get("*")

    missing_keys: list[str]
    if isinstance(entry, dict):
        missing_keys = [
            key for key in _normalize_string_list(entry.get("keys"))
            if not _context_has_path(context, key)
        ]
        if not missing_keys:
            return None
        return _policy_block_from_value(
            {
                "reason": entry.get("reason") or "missing_required_context",
                "message": entry.get("message") or "Tool call blocked by policy",
                "missing_context_keys": missing_keys,
            },
            default_reason="missing_required_context",
        )

    missing_keys = [
        key for key in _normalize_string_list(entry)
        if not _context_has_path(context, key)
    ]
    if not missing_keys:
        return None
    return _policy_block_from_value(
        {
            "reason": "missing_required_context",
            "missing_context_keys": missing_keys,
        },
        default_reason="missing_required_context",
    )


def _policy_block_from_value(
    value: Any,
    *,
    default_reason: str,
) -> ADKToolPolicyBlock:
    if isinstance(value, str):
        return ADKToolPolicyBlock(reason=value or default_reason)
    if isinstance(value, dict):
        return ADKToolPolicyBlock(
            reason=str(value.get("reason") or default_reason),
            message=str(value.get("message") or "Tool call blocked by policy"),
            missing_context_keys=tuple(_normalize_string_list(value.get("missing_context_keys"))),
        )
    return ADKToolPolicyBlock(reason=default_reason)


def _policy_targets_tool(raw_tools: Any, *, tool_name: str) -> bool:
    if raw_tools is None:
        return True
    if isinstance(raw_tools, str):
        return raw_tools in {"*", tool_name}
    if isinstance(raw_tools, (list, tuple, set)):
        return any(str(item) in {"*", tool_name} for item in raw_tools)
    return True


def _string_list_contains(raw_value: Any, expected: str) -> bool:
    if isinstance(raw_value, str):
        return raw_value == expected
    if isinstance(raw_value, (list, tuple, set)):
        return any(str(item) == expected for item in raw_value)
    return False


def _normalize_string_list(raw_value: Any) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        cleaned = raw_value.strip()
        return [cleaned] if cleaned else []
    if isinstance(raw_value, (list, tuple, set)):
        values: list[str] = []
        for item in raw_value:
            cleaned = str(item).strip()
            if cleaned:
                values.append(cleaned)
        return values
    return []


def _context_has_path(context: dict[str, Any] | None, path: str) -> bool:
    if not isinstance(context, dict):
        return False
    current: Any = context
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return False
        current = current[segment]
    return True


def _build_before_tool_callback(request: ADKToolRunRequest) -> Any:
    async def _before_tool_callback(*args: Any, **kwargs: Any) -> Any:
        tool = kwargs.get("tool")
        if tool is None and args:
            tool = args[0]

        raw_tool_args = kwargs.get("args")
        if raw_tool_args is None and len(args) > 1:
            raw_tool_args = args[1]
        tool_args = raw_tool_args if isinstance(raw_tool_args, dict) else {}

        tool_name = _resolve_callback_tool_name(tool, fallback=request.tool_name)
        prompt = _resolve_callback_prompt(tool_args, fallback=request.prompt)
        context = _resolve_callback_context(
            request_context=request.context,
            tool_args=tool_args,
            tool_name=tool_name,
        )
        return _evaluate_tool_policy(
            tool_name=tool_name,
            prompt=prompt,
            context=context,
            invocation_id=request.invocation.invocation_id or request.invocation_id,
        )

    return _before_tool_callback


def _resolve_callback_tool_name(tool: Any, *, fallback: str) -> str:
    if isinstance(tool, dict):
        raw_name = tool.get("name") or tool.get("tool_name")
    else:
        raw_name = getattr(tool, "name", None)
    if isinstance(raw_name, str) and raw_name.strip():
        return raw_name.strip().lower()
    return fallback


def _resolve_callback_prompt(tool_args: dict[str, Any], *, fallback: str) -> str:
    prompt = tool_args.get("prompt")
    if isinstance(prompt, str):
        return prompt
    user_input = tool_args.get("input")
    if isinstance(user_input, str):
        return user_input
    return fallback


def _resolve_callback_context(
    *,
    request_context: dict[str, Any] | None,
    tool_args: dict[str, Any],
    tool_name: str,
) -> dict[str, Any] | None:
    original_context = dict(request_context or {})
    merged_context = dict(original_context)
    context_json = tool_args.get("context_json")
    if isinstance(context_json, str):
        merged_context.update(_parse_callback_context_json(context_json))

    raw_context = tool_args.get("context")
    if isinstance(raw_context, dict):
        merged_context.update(raw_context)

    _restore_operator_policy_context(
        merged_context,
        original_context=original_context,
        tool_name=tool_name,
    )
    return merged_context


def _parse_callback_context_json(raw_value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _restore_operator_policy_context(
    merged_context: dict[str, Any],
    *,
    original_context: dict[str, Any],
    tool_name: str,
) -> None:
    for key in _PROTECTED_POLICY_KEYS:
        if key in original_context:
            merged_context[key] = original_context[key]
        elif key in merged_context:
            del merged_context[key]

    for path in _required_context_paths_for_tool(original_context, tool_name=tool_name):
        original_value = _get_context_path_value(original_context, path)
        if original_value is _MISSING_CONTEXT_VALUE:
            _delete_context_path(merged_context, path)
        else:
            _set_context_path_value(merged_context, path, original_value)


def _required_context_paths_for_tool(
    context: dict[str, Any] | None,
    *,
    tool_name: str,
) -> tuple[str, ...]:
    policy = _extract_tool_policy(context)
    raw_required = policy.get("required_context_keys")
    entry: Any = raw_required
    if isinstance(raw_required, dict):
        entry = raw_required.get(tool_name)
        if entry is None:
            entry = raw_required.get("*")

    if isinstance(entry, dict):
        return tuple(_normalize_string_list(entry.get("keys")))
    return tuple(_normalize_string_list(entry))


def _get_context_path_value(context: dict[str, Any] | None, path: str) -> Any:
    if not isinstance(context, dict):
        return _MISSING_CONTEXT_VALUE
    current: Any = context
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return _MISSING_CONTEXT_VALUE
        current = current[segment]
    return current


def _set_context_path_value(context: dict[str, Any], path: str, value: Any) -> None:
    current = context
    segments = path.split(".")
    for segment in segments[:-1]:
        next_value = current.get(segment)
        if not isinstance(next_value, dict):
            next_value = {}
            current[segment] = next_value
        current = next_value
    current[segments[-1]] = value


def _delete_context_path(context: dict[str, Any], path: str) -> None:
    segments = path.split(".")
    current = context
    parents: list[tuple[dict[str, Any], str, dict[str, Any]]] = []
    for segment in segments[:-1]:
        next_value = current.get(segment)
        if not isinstance(next_value, dict):
            return
        parents.append((current, segment, next_value))
        current = next_value

    if segments[-1] not in current:
        return
    del current[segments[-1]]

    for parent, key, child in reversed(parents):
        if child:
            break
        del parent[key]


def _build_runner_message(
    *,
    prompt: str,
    tool_name: str,
    context: dict[str, Any] | None,
) -> Any:
    if genai_types is None:
        return {
            "prompt": prompt,
            "tool_name": tool_name,
            "context": context or {},
        }

    try:
        part = genai_types.Part(text=prompt)
        return genai_types.Content(role="user", parts=[part])
    except Exception:  # noqa: BLE001
        return {
            "prompt": prompt,
            "tool_name": tool_name,
            "context": context or {},
        }


def _extract_text_parts(content: Any) -> str | None:
    parts = getattr(content, "parts", None)
    if parts is None and isinstance(content, dict):
        parts = content.get("parts")
    if not isinstance(parts, list):
        return None

    texts: list[str] = []
    for part in parts:
        text_value: Any = None
        if isinstance(part, dict):
            text_value = part.get("text")
        else:
            text_value = getattr(part, "text", None)
        if isinstance(text_value, str) and text_value.strip():
            texts.append(text_value)

    if texts:
        return "\n".join(texts)
    return None


def _extract_event_output(event: Any) -> Any:
    if isinstance(event, dict):
        if "result" in event:
            return event["result"]
        content = event.get("content")
        content_text = _extract_text_parts(content)
        if content_text is not None:
            return content_text
        if "text" in event and isinstance(event["text"], str):
            return event["text"]

    for attr_name in ("result", "output", "text"):
        attr_value = getattr(event, attr_name, None)
        if attr_value is not None:
            return attr_value

    content = getattr(event, "content", None)
    content_text = _extract_text_parts(content)
    if content_text is not None:
        return content_text

    return None


async def _extract_runner_output(events: Any) -> Any:
    latest_output: Any = None
    async for event in events:
        candidate = _extract_event_output(event)
        if candidate is not None:
            latest_output = candidate
    return latest_output


async def _execute_with_adk_runner(
    *,
    request: ADKToolRunRequest,
    function_tool: Any,
) -> dict[str, Any]:
    context_token = set_adk_tool_context(
        deps=request.deps,
        context=request.context,
    )
    try:
        agent = Agent(
            name=f"hormonia-adk-{request.tool_name}",
            model=request.deps.model_name or "gemini-2.0-flash",
            tools=[function_tool],
            instruction="Use the available tool to process the prompt and return the result.",
            before_tool_callback=_build_before_tool_callback(request),
        )
        executor = Runner(
            app_name="hormonia-adk",
            agent=agent,
            session_service=InMemorySessionService(),
        )
        message = _build_runner_message(
            prompt=request.prompt,
            tool_name=request.tool_name,
            context=request.context,
        )
        run_kwargs: dict[str, Any] = {
            "user_id": request.user_id,
            "session_id": request.session_id or "default-session",
            "new_message": message,
        }
        run_config = _build_run_config(request.runtime)
        if run_config is not None:
            run_kwargs["run_config"] = run_config
        events = executor.run_async(**run_kwargs)
        runner_output = await _extract_runner_output(events)
    except ADKToolExecutionError:
        raise
    except Exception as exc:
        raise ADKUpstreamExecutionError(
            str(exc) or "ADK runner execution failed"
        ) from exc
    finally:
        reset_adk_tool_context(context_token)

    if runner_output is None:
        raise ADKUpstreamExecutionError(
            "ADK runner completed without returning a result"
        )

    return _normalize_result(runner_output)
