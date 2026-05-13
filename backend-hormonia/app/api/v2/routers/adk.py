from __future__ import annotations

import hashlib
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.ai.adk import PIISafeADKWrapper
from app.ai.agents.deps import AIDeps
from app.config import settings
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.schemas.v2.adk import ADKRunRequest, ADKRunResponse

router = APIRouter()
logger = logging.getLogger(__name__)

_SAFE_LOG_LABEL = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def _safe_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _safe_log_label(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    if _SAFE_LOG_LABEL.fullmatch(text):
        return text
    return f"hashed-{_safe_hash(text)}"


def _log_adk_route_denial(
    request: Request,
    *,
    reason: str,
    tool_name: str | None,
    lifecycle_action: str,
) -> None:
    """Emit low-cardinality, PHI-safe diagnostics for denied ADK route calls."""
    logger.warning(
        "ADK route request denied",
        extra={
            "event_type": "adk_route_denied",
            "reason": reason,
            "route": request.url.path,
            "method": request.method,
            "tool_name": _safe_log_label(tool_name),
            "lifecycle_action": lifecycle_action,
            "request_id": _safe_log_label(
                getattr(request.state, "request_id", None)
                or request.headers.get("X-Request-ID")
            ),
        },
    )


def _deny_adk_route(
    request: Request,
    *,
    status_code: int,
    reason: str,
    tool_name: str | None,
    lifecycle_action: str,
) -> None:
    _log_adk_route_denial(
        request,
        reason=reason,
        tool_name=tool_name,
        lifecycle_action=lifecycle_action,
    )
    if status_code == status.HTTP_401_UNAUTHORIZED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Session"},
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden",
    )


def _canonical_authenticated_user_id(
    request: Request,
    current_user: dict,
    *,
    tool_name: str | None,
) -> str:
    raw_user_id = None
    if isinstance(current_user, dict):
        raw_user_id = current_user.get("id") or current_user.get("user_id")

    canonical_user_id = str(raw_user_id).strip() if raw_user_id is not None else ""
    if not canonical_user_id:
        _deny_adk_route(
            request,
            status_code=status.HTTP_401_UNAUTHORIZED,
            reason="missing_canonical_user",
            tool_name=tool_name,
            lifecycle_action="authenticate",
        )

    return canonical_user_id


@router.post("/run", response_model=ADKRunResponse)
async def run_adk(
    request: Request,
    payload: ADKRunRequest,
    current_user: dict = Depends(get_current_user_from_session),
) -> ADKRunResponse:
    canonical_user_id = _canonical_authenticated_user_id(
        request,
        current_user,
        tool_name=payload.tool_name,
    )
    if payload.user_id is not None and str(payload.user_id).strip() != canonical_user_id:
        _deny_adk_route(
            request,
            status_code=status.HTTP_403_FORBIDDEN,
            reason="payload_user_mismatch",
            tool_name=payload.tool_name,
            lifecycle_action="authorize",
        )

    session_controls = payload.resolved_session_controls()
    invocation_controls = payload.resolved_invocation_controls()
    runtime_controls = payload.resolved_runtime_controls()

    context = dict(payload.context or {})
    context.update(
        {
            "tool_name": payload.tool_name,
            "user_id": canonical_user_id,
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
