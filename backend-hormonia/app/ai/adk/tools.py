from __future__ import annotations

import json
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable

try:
    from google.adk.tools import FunctionTool

    HAS_ADK_FUNCTION_TOOL = True
except ModuleNotFoundError:
    FunctionTool = None
    HAS_ADK_FUNCTION_TOOL = False

from app.ai.client_domain import GeminiDomainClient

if TYPE_CHECKING:
    from app.ai.agents.deps import AIDeps

ToolResult = dict[str, Any]
ToolHandler = Callable[..., Awaitable[ToolResult]]
_ADK_TOOL_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar(
    "_ADK_TOOL_CONTEXT",
    default=None,
)


@dataclass(frozen=True)
class FallbackFunctionTool:
    func: Callable[..., Awaitable[ToolResult]]
    name: str

    @property
    def callable(self) -> Callable[..., Awaitable[ToolResult]]:
        return self.func


def _get_domain_client(deps: AIDeps) -> GeminiDomainClient:
    try:
        return GeminiDomainClient(api_key=deps.gemini_api_key, model=deps.model_name)
    except TypeError:
        return GeminiDomainClient()


async def sentiment_tool(
    *,
    prompt: str,
    deps: AIDeps,
    context: dict[str, Any] | None = None,
) -> ToolResult:
    """Analyze patient response sentiment through ADK tool wiring."""
    payload = context or {}
    client = _get_domain_client(deps)
    result = await client.analyze_response_sentiment(
        response=prompt,
        patient_context=payload.get("patient_context", {}),
    )
    return {"status": "success", "result": result}


async def humanize_tool(
    *,
    prompt: str,
    deps: AIDeps,
    context: dict[str, Any] | None = None,
) -> ToolResult:
    """Humanize a template/message through ADK tool wiring."""
    payload = context or {}
    client = _get_domain_client(deps)
    result = await client.humanize_flow_message(
        template=prompt,
        patient_name=payload.get("patient_name", "Paciente"),
        patient_context=payload.get("patient_context", {}),
        conversation_history=payload.get("conversation_history", []),
        personalization_hints=payload.get("personalization_hints", []),
    )
    return {"status": "success", "result": result}


async def variation_tool(
    *,
    prompt: str,
    deps: AIDeps,
    context: dict[str, Any] | None = None,
) -> ToolResult:
    """Generate question/message variation through ADK tool wiring."""
    payload = context or {}
    client = _get_domain_client(deps)
    result = await client.generate_varied_question(
        base_question=prompt,
        previous_questions=payload.get("previous_questions", []),
        patient_context=payload.get("patient_context", {}),
    )
    return {"status": "success", "result": result}


async def empathy_tool(
    *,
    prompt: str,
    deps: AIDeps,
    context: dict[str, Any] | None = None,
) -> ToolResult:
    """Generate empathetic follow-up through ADK tool wiring."""
    payload = context or {}
    client = _get_domain_client(deps)
    result = await client.create_empathetic_follow_up(
        patient_response=prompt,
        conversation_history=payload.get("conversation_history", []),
        patient_context=payload.get("patient_context", {}),
    )
    return {"status": "success", "result": result}


def set_adk_tool_context(
    *,
    deps: AIDeps,
    context: dict[str, Any] | None,
) -> Token[dict[str, Any] | None]:
    return _ADK_TOOL_CONTEXT.set({"deps": deps, "context": context or {}})


def reset_adk_tool_context(token: Token[dict[str, Any] | None]) -> None:
    _ADK_TOOL_CONTEXT.reset(token)


def _parse_context_json(context_json: str) -> dict[str, Any]:
    try:
        parsed = json.loads(context_json)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _merge_context(runtime_context: dict[str, Any], context_json: str) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    base_context = runtime_context.get("context")
    if isinstance(base_context, dict):
        merged.update(base_context)
    merged.update(_parse_context_json(context_json))
    return merged


async def _dispatch_tool_from_adk(
    *,
    tool_name: str,
    prompt: str,
    context_json: str = "{}",
) -> ToolResult:
    runtime_context = _ADK_TOOL_CONTEXT.get() or {}
    deps = runtime_context.get("deps")
    if deps is None:
        return {
            "status": "error",
            "result": {
                "message": "ADK tool context is not initialized",
                "tool": tool_name,
            },
        }

    handler = get_tool_registry()[tool_name]
    merged_context = _merge_context(runtime_context, context_json)
    return await handler(prompt=prompt, deps=deps, context=merged_context)


async def sentiment_tool_adk_compat(prompt: str, context_json: str = "{}") -> ToolResult:
    """Analyze patient response sentiment through ADK FunctionTool."""
    return await _dispatch_tool_from_adk(
        tool_name="sentiment",
        prompt=prompt,
        context_json=context_json,
    )


async def humanize_tool_adk_compat(prompt: str, context_json: str = "{}") -> ToolResult:
    """Humanize flow messages through ADK FunctionTool."""
    return await _dispatch_tool_from_adk(
        tool_name="humanize",
        prompt=prompt,
        context_json=context_json,
    )


async def variation_tool_adk_compat(prompt: str, context_json: str = "{}") -> ToolResult:
    """Generate prompt variation through ADK FunctionTool."""
    return await _dispatch_tool_from_adk(
        tool_name="variation",
        prompt=prompt,
        context_json=context_json,
    )


async def empathy_tool_adk_compat(prompt: str, context_json: str = "{}") -> ToolResult:
    """Generate empathetic follow up through ADK FunctionTool."""
    return await _dispatch_tool_from_adk(
        tool_name="empathy",
        prompt=prompt,
        context_json=context_json,
    )


def _build_function_tool(
    *,
    tool_name: str,
    handler: Callable[..., Awaitable[ToolResult]],
) -> Any:
    if HAS_ADK_FUNCTION_TOOL and FunctionTool is not None:
        return FunctionTool(func=handler)
    return FallbackFunctionTool(func=handler, name=tool_name)


def get_adk_function_tools() -> dict[str, Any]:
    return {
        "sentiment": _build_function_tool(
            tool_name="sentiment",
            handler=sentiment_tool_adk_compat,
        ),
        "humanize": _build_function_tool(
            tool_name="humanize",
            handler=humanize_tool_adk_compat,
        ),
        "variation": _build_function_tool(
            tool_name="variation",
            handler=variation_tool_adk_compat,
        ),
        "empathy": _build_function_tool(
            tool_name="empathy",
            handler=empathy_tool_adk_compat,
        ),
    }


def get_tool_registry() -> dict[str, ToolHandler]:
    """Return the canonical ADK tool registry for supported capabilities."""
    return {
        "sentiment": sentiment_tool,
        "humanize": humanize_tool,
        "variation": variation_tool,
        "empathy": empathy_tool,
    }
