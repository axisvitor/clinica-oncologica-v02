from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

from app.ai.client_domain import GeminiDomainClient

if TYPE_CHECKING:
    from app.ai.agents.deps import AIDeps

ToolResult = dict[str, Any]
ToolHandler = Callable[..., Awaitable[ToolResult]]


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


def get_tool_registry() -> dict[str, ToolHandler]:
    """Return the canonical ADK tool registry for supported capabilities."""
    return {
        "sentiment": sentiment_tool,
        "humanize": humanize_tool,
        "variation": variation_tool,
        "empathy": empathy_tool,
    }
