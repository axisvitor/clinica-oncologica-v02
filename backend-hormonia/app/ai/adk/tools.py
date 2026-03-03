from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from app.ai.agents.deps import AIDeps

ToolResult = dict[str, Any]
ToolHandler = Callable[..., Awaitable[ToolResult]]


async def sentiment_tool(
    *,
    prompt: str,
    deps: AIDeps,
    context: dict[str, Any] | None = None,
) -> ToolResult:
    """Analyze patient response sentiment through ADK tool wiring."""
    raise NotImplementedError


async def humanize_tool(
    *,
    prompt: str,
    deps: AIDeps,
    context: dict[str, Any] | None = None,
) -> ToolResult:
    """Humanize a template/message through ADK tool wiring."""
    raise NotImplementedError


async def variation_tool(
    *,
    prompt: str,
    deps: AIDeps,
    context: dict[str, Any] | None = None,
) -> ToolResult:
    """Generate question/message variation through ADK tool wiring."""
    raise NotImplementedError


async def empathy_tool(
    *,
    prompt: str,
    deps: AIDeps,
    context: dict[str, Any] | None = None,
) -> ToolResult:
    """Generate empathetic follow-up through ADK tool wiring."""
    raise NotImplementedError


def get_tool_registry() -> dict[str, ToolHandler]:
    """Return the canonical ADK tool registry for supported capabilities."""
    return {
        "sentiment": sentiment_tool,
        "humanize": humanize_tool,
        "variation": variation_tool,
        "empathy": empathy_tool,
    }
