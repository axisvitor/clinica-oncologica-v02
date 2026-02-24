from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from app.ai.agents.deps import AIDeps
from app.ai.pii_redaction import sanitize_prompt_text_for_external_ai

logger = logging.getLogger(__name__)

_CPF_PATTERN = re.compile(r"\d{3}\.?(?:\d{3})\.?(?:\d{3})[-.]?\d{2}")
_PHONE_PATTERN = re.compile(r"\+?55\s?\(?\d{2}\)?\s?\d{4,5}[-\s]?\d{4}")
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


class PIISafeAgent:
    """LGPD-compliant agent wrapper for all pydantic-ai operations.

    Every subclass call goes through ``_safe_run`` to guarantee mandatory PII
    sanitization before Gemini invocation and structured call logging.
    Direct ``agent.run()`` calls outside this wrapper are prohibited.
    """

    _agent: Agent

    async def _safe_run(self, prompt: str, deps: AIDeps, *, operation: str) -> Any:
        try:
            safe_prompt = sanitize_prompt_text_for_external_ai(prompt)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"PII sanitization failed for {operation} -- blocking Gemini call"
            ) from exc

        model = GoogleModel(
            deps.model_name,
            provider=GoogleProvider(api_key=deps.gemini_api_key),
        )

        input_hash = hashlib.sha256(safe_prompt.encode("utf-8")).hexdigest()[:12]
        start = time.monotonic()
        logger.info(
            "Agent call started",
            extra={
                "operation": operation,
                "input_hash": input_hash,
                "retry_count": 0,
            },
        )

        try:
            result = await self._agent.run(safe_prompt, model=model, deps=deps)
        except Exception as exc:  # noqa: BLE001
            latency_ms = round((time.monotonic() - start) * 1000)
            logger.error(
                "Agent call failed",
                extra={
                    "operation": operation,
                    "input_hash": input_hash,
                    "latency_ms": latency_ms,
                    "success": False,
                    "error_type": type(exc).__name__,
                },
            )
            raise

        latency_ms = round((time.monotonic() - start) * 1000)
        logger.info(
            "Agent call completed",
            extra={
                "operation": operation,
                "input_hash": input_hash,
                "latency_ms": latency_ms,
                "success": True,
            },
        )

        self._warn_on_output_pii(str(result.output), operation=operation)
        return result.output

    def _warn_on_output_pii(self, output_text: str, *, operation: str) -> None:
        scans = (
            ("cpf", _CPF_PATTERN),
            ("phone", _PHONE_PATTERN),
            ("email", _EMAIL_PATTERN),
        )
        for pii_type, pattern in scans:
            if pattern.search(output_text):
                logger.warning(
                    "PII detected in agent output",
                    extra={"operation": operation, "pii_type": pii_type},
                )
