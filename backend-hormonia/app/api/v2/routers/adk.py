from __future__ import annotations

from fastapi import APIRouter

from app.ai.adk import PIISafeADKWrapper
from app.ai.agents.deps import AIDeps
from app.config import settings
from app.schemas.v2.adk import ADKRunRequest, ADKRunResponse

router = APIRouter()


@router.post("/run", response_model=ADKRunResponse)
async def run_adk(payload: ADKRunRequest) -> ADKRunResponse:
    session_controls = payload.resolved_session_controls()
    invocation_controls = payload.resolved_invocation_controls()
    runtime_controls = payload.resolved_runtime_controls()

    context = dict(payload.context or {})
    context.update(
        {
        "tool_name": payload.tool_name,
        "user_id": payload.user_id or "api-v2-adk-user",
        "request_source": "api_v2_adk",
        "runtime": runtime_controls.model_dump(exclude_none=True),
        "session": session_controls.model_dump(exclude_none=True),
        "invocation": invocation_controls.model_dump(exclude_none=True),
        }
    )
    if session_controls.session_id:
        context["session_id"] = session_controls.session_id
    if invocation_controls.invocation_id:
        context["invocation_id"] = invocation_controls.invocation_id

    deps = AIDeps(
        gemini_api_key=(getattr(settings, "AI_GEMINI_API_KEY", "") or ""),
        model_name=(
            getattr(settings, "AI_GEMINI_MODEL", "gemini-2.0-flash")
            or "gemini-2.0-flash"
        ),
    )

    raw_result = await PIISafeADKWrapper().safe_run(
        prompt=payload.prompt or "",
        deps=deps,
        operation="adk_endpoint_run",
        context=context,
    )

    normalized = (
        raw_result
        if isinstance(raw_result, dict)
        else {"status": "success", "result": raw_result}
    )
    return ADKRunResponse(
        status=str(normalized.get("status", "success")),
        tool_name=payload.tool_name,
        session_id=str(normalized.get("session_id") or context.get("session_id") or "")
        or None,
        output=normalized.get("result", normalized),
    )
