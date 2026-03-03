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
    raise NotImplementedError
