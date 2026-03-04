from __future__ import annotations

from fastapi import APIRouter

from app.ai.adk import PIISafeADKWrapper
from app.ai.agents.deps import AIDeps
from app.config import settings
from app.schemas.v2.adk import ADKRunRequest, ADKRunResponse

router = APIRouter()


@router.post("/run", response_model=ADKRunResponse)
async def run_adk(payload: ADKRunRequest) -> ADKRunResponse:
    context = {
        "tool_name": payload.tool_name,
        "user_id": payload.user_id or "api-v2-adk-user",
        "session_id": payload.session_id or "api-v2-adk-session",
    }
    if payload.context:
        context.update(payload.context)

    deps = AIDeps(
        gemini_api_key=(getattr(settings, "AI_GEMINI_API_KEY", "") or ""),
        model_name=(
            getattr(settings, "AI_GEMINI_MODEL", "gemini-2.0-flash")
            or "gemini-2.0-flash"
        ),
    )

    raw_result = await PIISafeADKWrapper().safe_run(
        prompt=payload.prompt,
        deps=deps,
        operation="adk_endpoint_run",
        context=context,
    )

    normalized = raw_result if isinstance(raw_result, dict) else {"status": "success", "result": raw_result}
    return ADKRunResponse(
        status=str(normalized.get("status", "success")),
        tool_name=payload.tool_name,
        session_id=context.get("session_id"),
        output=normalized.get("result", normalized),
    )
