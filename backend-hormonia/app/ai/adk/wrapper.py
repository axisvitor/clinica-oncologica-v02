from __future__ import annotations

import logging
import re
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from app.ai.adk.runtime import (
    ADKInvocationControls,
    ADKRuntimeControls,
    ADKSessionControls,
    ADKToolRunRequest,
    run_adk_tool,
)
from app.ai.pii_redaction import sanitize_prompt_text_for_external_ai

if TYPE_CHECKING:
    from app.ai.agents.deps import AIDeps

logger = logging.getLogger(__name__)

_CPF_PATTERN = re.compile(r"\d{3}\.?(?:\d{3})\.?(?:\d{3})[-.]?\d{2}")
_PHONE_PATTERN = re.compile(r"\+?55\s?\(?\d{2}\)?\s?\d{4,5}[-\s]?\d{4}")
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def _clean_optional_text(value: Any) -> str | None:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


class PIISafeADKWrapper:
    """LGPD-safe call-site wrapper for ADK Gemini executions.

    This wrapper establishes a single mandatory boundary for all ADK calls,
    mirroring PIISafeAgent behavior: sanitize input before invocation and scan
    output for possible PII leakage.
    """

    async def safe_run(
        self,
        prompt: str,
        deps: AIDeps,
        *,
        operation: str,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Execute an ADK operation through the safety boundary."""
        try:
            safe_prompt = sanitize_prompt_text_for_external_ai(prompt)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"PII sanitization failed for {operation} -- blocking ADK call"
            ) from exc

        result = await self._invoke_adk(
            safe_prompt,
            deps,
            operation=operation,
            context=context,
        )
        output_text = str(getattr(result, "output", result))
        self._warn_on_output_pii(output_text, operation=operation)
        return result

    async def _invoke_adk(
        self,
        safe_prompt: str,
        deps: AIDeps,
        *,
        operation: str,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Invoke ADK with already-sanitized inputs."""
        payload = context or {}
        runtime_payload = payload.get("runtime")
        session_payload = payload.get("session")
        invocation_payload = payload.get("invocation")

        runtime = ADKRuntimeControls(
            max_llm_calls=(
                runtime_payload.get("max_llm_calls")
                if isinstance(runtime_payload, dict)
                else None
            ),
            timeout_seconds=(
                runtime_payload.get("timeout_seconds")
                if isinstance(runtime_payload, dict)
                else None
            ),
        )
        session = ADKSessionControls(
            action=str(session_payload.get("action") or "auto")
            if isinstance(session_payload, dict)
            else "auto",
            session_id=_clean_optional_text(
                session_payload.get("session_id") if isinstance(session_payload, dict) else None
            ),
            state_size_limit_bytes=(
                session_payload.get("state_size_limit_bytes")
                if isinstance(session_payload, dict)
                else None
            ),
        )
        invocation = ADKInvocationControls(
            action=str(invocation_payload.get("action") or "run")
            if isinstance(invocation_payload, dict)
            else "run",
            invocation_id=_clean_optional_text(
                invocation_payload.get("invocation_id")
                if isinstance(invocation_payload, dict)
                else None
            ),
        )

        if session.session_id is None:
            legacy_session_id = _clean_optional_text(payload.get("session_id"))
            if legacy_session_id is not None:
                session = replace(session, session_id=legacy_session_id)

        if invocation.invocation_id is None:
            legacy_invocation_id = _clean_optional_text(payload.get("invocation_id"))
            if legacy_invocation_id is not None:
                invocation = replace(invocation, invocation_id=legacy_invocation_id)

        request = ADKToolRunRequest(
            prompt=safe_prompt,
            tool_name=str(payload.get("tool_name") or operation),
            deps=deps,
            user_id=str(payload.get("user_id") or "pii-safe-adk"),
            session_id=session.session_id,
            invocation_id=invocation.invocation_id,
            context=payload,
            runtime=runtime,
            session=session,
            invocation=invocation,
        )
        return await run_adk_tool(request)

    def _warn_on_output_pii(self, output_text: str, *, operation: str) -> None:
        """Scan ADK output and emit warning when potential PII is detected."""
        scans = (
            ("cpf", _CPF_PATTERN),
            ("phone", _PHONE_PATTERN),
            ("email", _EMAIL_PATTERN),
        )
        for pii_type, pattern in scans:
            if pattern.search(output_text):
                logger.warning(
                    "PII detected in ADK output",
                    extra={"operation": operation, "pii_type": pii_type},
                )
