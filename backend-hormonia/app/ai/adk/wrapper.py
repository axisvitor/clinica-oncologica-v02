from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from app.ai.pii_redaction import sanitize_prompt_text_for_external_ai

if TYPE_CHECKING:
    from app.ai.agents.deps import AIDeps

logger = logging.getLogger(__name__)

_CPF_PATTERN = re.compile(r"\d{3}\.?(?:\d{3})\.?(?:\d{3})[-.]?\d{2}")
_PHONE_PATTERN = re.compile(r"\+?55\s?\(?\d{2}\)?\s?\d{4,5}[-\s]?\d{4}")
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


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
        raise NotImplementedError("ADK runner wiring is implemented in Phase 41")

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
