from __future__ import annotations

from typing import Any

from app.ai.agents.deps import AIDeps


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
        raise NotImplementedError

    async def _invoke_adk(
        self,
        safe_prompt: str,
        deps: AIDeps,
        *,
        operation: str,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Invoke ADK with already-sanitized inputs."""
        raise NotImplementedError

    def _warn_on_output_pii(self, output_text: str, *, operation: str) -> None:
        """Scan ADK output and emit warning when potential PII is detected."""
        raise NotImplementedError
