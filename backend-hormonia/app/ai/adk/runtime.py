from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

try:
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types as genai_types

    HAS_ADK_RUNTIME = True
except ModuleNotFoundError:
    Agent = None
    Runner = None
    genai_types = None
    HAS_ADK_RUNTIME = False

    class InMemorySessionService:  # type: ignore[no-redef]
        pass

if TYPE_CHECKING:
    from app.ai.agents.deps import AIDeps

from app.ai.adk.tools import (
    get_adk_function_tools,
    get_tool_registry,
    reset_adk_tool_context,
    set_adk_tool_context,
)


@dataclass(frozen=True)
class ADKToolRunRequest:
    prompt: str
    tool_name: str
    deps: AIDeps
    user_id: str
    session_id: str
    context: dict[str, Any] | None = None


async def run_adk_tool(request: ADKToolRunRequest) -> dict[str, Any]:
    """Execute a single ADK tool invocation and return normalized payload."""
    registry = get_tool_registry()
    tool_name = request.tool_name.strip().lower()
    handler = registry.get(tool_name)
    if handler is None:
        return {
            "status": "error",
            "result": {
                "message": f"Unsupported ADK tool: {request.tool_name}",
                "tool": request.tool_name,
            },
        }

    if HAS_ADK_RUNTIME and Agent is not None and Runner is not None:
        adk_tools = get_adk_function_tools()
        function_tool = adk_tools.get(tool_name)

        if function_tool is not None:
            context_token = set_adk_tool_context(deps=request.deps, context=request.context)
            try:
                agent = Agent(
                    name=f"hormonia-adk-{tool_name}",
                    model=request.deps.model_name or "gemini-2.0-flash",
                    tools=[function_tool],
                    instruction="Use the available tool to process the prompt and return the result.",
                )
                executor = Runner(
                    app_name="hormonia-adk",
                    agent=agent,
                    session_service=InMemorySessionService(),
                )
                message = _build_runner_message(
                    prompt=request.prompt,
                    tool_name=tool_name,
                    context=request.context,
                )
                events = executor.run_async(
                    user_id=request.user_id,
                    session_id=request.session_id,
                    new_message=message,
                )
                runner_output = await _extract_runner_output(events)
                if runner_output is not None:
                    return _normalize_result(runner_output)

                wrapped_result = await _invoke_function_tool(function_tool, request)
                if wrapped_result is not None:
                    return _normalize_result(wrapped_result)
            except Exception:  # noqa: BLE001
                pass
            finally:
                reset_adk_tool_context(context_token)

    result = await handler(prompt=request.prompt, deps=request.deps, context=request.context)
    return _normalize_result(result)


def _normalize_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict) and "status" in result and "result" in result:
        return result
    return {"status": "success", "result": result}


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


async def _invoke_function_tool(function_tool: Any, request: ADKToolRunRequest) -> Any:
    func = getattr(function_tool, "func", None)
    if func is None:
        func = getattr(function_tool, "callable", None)
    if not callable(func):
        return None

    call_kwargs = {
        "prompt": request.prompt,
        "context_json": json.dumps(request.context or {}, ensure_ascii=False),
    }
    try:
        result = func(**call_kwargs)
    except TypeError:
        result = func(request.prompt)

    if hasattr(result, "__await__"):
        return await result
    return result
