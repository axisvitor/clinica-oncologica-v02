from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.adk.wrapper import PIISafeADKWrapper
from app.ai.agents.deps import AIDeps


class _ProbeWrapper(PIISafeADKWrapper):
    def __init__(self) -> None:
        self.invoked_prompt: str | None = None
        self.invoked_operation: str | None = None
        self.invoked_context: dict | None = None
        self.invoke_count = 0
        self.invocations: list[dict[str, object]] = []
        self.warned_output: str | None = None

    async def _invoke_adk(
        self,
        safe_prompt: str,
        deps: AIDeps,
        *,
        operation: str,
        context: dict | None = None,
    ) -> object:
        self.invoke_count += 1
        self.invoked_prompt = safe_prompt
        self.invoked_operation = operation
        self.invoked_context = context
        self.invocations.append(
            {
                "prompt": safe_prompt,
                "operation": operation,
                "context": context,
            }
        )
        return SimpleNamespace(output="Contato: +55 11 98888-7777")

    def _warn_on_output_pii(self, output_text: str, *, operation: str) -> None:
        self.warned_output = output_text
        self.invoked_operation = operation


@pytest.mark.asyncio
async def test_safe_run_sanitizes_prompt_before_adk_invocation(monkeypatch):
    wrapper = _ProbeWrapper()
    deps = AIDeps(gemini_api_key="test-key", model_name="gemini-2.0-flash")

    def _fake_sanitize(prompt: str) -> str:
        assert "123.456.789-09" in prompt
        return "Paciente [REDACTED]"

    monkeypatch.setattr(
        "app.ai.adk.wrapper.sanitize_prompt_text_for_external_ai",
        _fake_sanitize,
        raising=False,
    )

    await wrapper.safe_run(
        "cpf: 123.456.789-09",
        deps,
        operation="adk-safe-test",
    )

    assert wrapper.invoked_prompt == "Paciente [REDACTED]"


@pytest.mark.asyncio
async def test_safe_run_blocks_adk_call_when_sanitization_fails(monkeypatch):
    wrapper = _ProbeWrapper()
    deps = AIDeps(gemini_api_key="test-key", model_name="gemini-2.0-flash")

    def _broken_sanitize(_prompt: str) -> str:
        raise ValueError("redaction failure")

    monkeypatch.setattr(
        "app.ai.adk.wrapper.sanitize_prompt_text_for_external_ai",
        _broken_sanitize,
        raising=False,
    )

    with pytest.raises(RuntimeError, match="PII sanitization failed"):
        await wrapper.safe_run("nome: Maria", deps, operation="adk-block-test")

    assert wrapper.invoked_prompt is None


@pytest.mark.asyncio
async def test_safe_run_scans_output_for_synthetic_phi_warning_path(monkeypatch):
    wrapper = _ProbeWrapper()
    deps = AIDeps(gemini_api_key="test-key", model_name="gemini-2.0-flash")

    monkeypatch.setattr(
        "app.ai.adk.wrapper.sanitize_prompt_text_for_external_ai",
        lambda prompt: prompt,
        raising=False,
    )

    await wrapper.safe_run(
        "resuma o caso",
        deps,
        operation="adk-output-scan",
    )

    assert wrapper.warned_output == "Contato: +55 11 98888-7777"
    assert wrapper.invoked_operation == "adk-output-scan"


@pytest.mark.asyncio
async def test_safe_run_forwards_policy_context_after_sanitization_once(monkeypatch):
    wrapper = _ProbeWrapper()
    deps = AIDeps(gemini_api_key="test-key", model_name="gemini-2.0-flash")

    monkeypatch.setattr(
        "app.ai.adk.wrapper.sanitize_prompt_text_for_external_ai",
        lambda _prompt: "Paciente [REDACTED]",
        raising=False,
    )

    context = {
        "tool_name": "sentiment",
        "tool_policy": {
            "blocked_tools": {
                "sentiment": {
                    "reason": "manual_review_required",
                }
            }
        },
    }

    await wrapper.safe_run(
        "cpf: 123.456.789-09",
        deps,
        operation="adk-policy-forward",
        context=context,
    )

    assert wrapper.invoke_count == 1
    assert wrapper.invoked_prompt == "Paciente [REDACTED]"
    assert wrapper.invoked_context == context


@pytest.mark.asyncio
async def test_safe_run_preserves_sanitized_policy_context_on_repeated_calls(monkeypatch):
    wrapper = _ProbeWrapper()
    deps = AIDeps(gemini_api_key="test-key", model_name="gemini-2.0-flash")

    monkeypatch.setattr(
        "app.ai.adk.wrapper.sanitize_prompt_text_for_external_ai",
        lambda _prompt: "Paciente [REDACTED]",
        raising=False,
    )

    context = {
        "tool_name": "sentiment",
        "tool_policy": {
            "blocked_prompts": {
                "Paciente [REDACTED]": {
                    "reason": "manual_review_required",
                }
            }
        },
    }

    await wrapper.safe_run(
        "cpf: 123.456.789-09",
        deps,
        operation="adk-policy-repeat",
        context=context,
    )
    await wrapper.safe_run(
        "cpf: 123.456.789-09",
        deps,
        operation="adk-policy-repeat",
        context=context,
    )

    assert wrapper.invoke_count == 2
    assert wrapper.invocations == [
        {
            "prompt": "Paciente [REDACTED]",
            "operation": "adk-policy-repeat",
            "context": context,
        },
        {
            "prompt": "Paciente [REDACTED]",
            "operation": "adk-policy-repeat",
            "context": context,
        },
    ]
    assert context == {
        "tool_name": "sentiment",
        "tool_policy": {
            "blocked_prompts": {
                "Paciente [REDACTED]": {
                    "reason": "manual_review_required",
                }
            }
        },
    }
