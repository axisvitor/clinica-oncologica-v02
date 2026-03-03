from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

try:
    from google.adk.sessions import InMemorySessionService
except ModuleNotFoundError:
    class InMemorySessionService:  # type: ignore[no-redef]
        pass

if TYPE_CHECKING:
    from app.ai.agents.deps import AIDeps

from app.ai.adk.tools import get_tool_registry


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
    _session_service = InMemorySessionService()
    _ = _session_service

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

    result = await handler(prompt=request.prompt, deps=request.deps, context=request.context)
    if isinstance(result, dict) and "status" in result and "result" in result:
        return result

    return {"status": "success", "result": result}
