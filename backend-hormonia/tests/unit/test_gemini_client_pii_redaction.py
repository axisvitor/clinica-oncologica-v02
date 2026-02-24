from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from app.ai import client as ai_client_module
from app.ai.client import GeminiClient
from app.services.ai.guardrails import OutputKind
from app.utils.rate_limiter import AIRateLimitExceeded


def _build_response_stub(text: str = "Mensagem segura.") -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name="STOP"))],
        usage_metadata=SimpleNamespace(total_token_count=0),
    )


def _build_client_stub() -> GeminiClient:
    client = GeminiClient.__new__(GeminiClient)
    client.api_key = "test-key"
    client.model_name = "gemini-test"
    client._genai_config = cast(Any, SimpleNamespace(name="test-config"))
    generate_content_mock = AsyncMock(return_value=_build_response_stub())
    client._genai_client = cast(Any, SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(generate_content=generate_content_mock)
        )
    ))
    client.model = client._genai_client
    return client


@pytest.mark.asyncio
async def test_generate_content_internal_redacts_pii_before_model_call(monkeypatch):
    async def _allow_rate_limit(**_kwargs):
        return True, 0

    monkeypatch.setattr("app.ai.client.check_ai_rate_limit", _allow_rate_limit)

    client = _build_client_stub()

    prompt = (
        '{"patient_name":"Maria Souza","patient_id":"abc-123","cpf":"123.456.789-09",'
        '"phone":"+55 11 98888-7777","email":"maria@example.com"}'
    )

    result = await GeminiClient._generate_content_internal(
        client,
        prompt,
        max_retries=1,
        retry_delay=0,
    )

    assert result == "Mensagem segura."
    sent_prompt = cast(
        Any,
        client._genai_client,
    ).aio.models.generate_content.await_args.kwargs["contents"]
    assert "Maria Souza" not in sent_prompt
    assert "abc-123" not in sent_prompt
    assert "123.456.789-09" not in sent_prompt
    assert "+55 11 98888-7777" not in sent_prompt
    assert "maria@example.com" not in sent_prompt
    assert "Paciente" in sent_prompt
    assert "[REDACTED]" in sent_prompt


@pytest.mark.asyncio
async def test_generate_content_redacts_prompt_before_cache_and_circuit():
    client = GeminiClient.__new__(GeminiClient)
    captured: dict[str, str] = {}

    def _cache_key(prompt: str, *, profile_hint: str = "raw") -> str:
        captured["cache_prompt"] = prompt
        captured["profile_hint"] = profile_hint
        return "cache-key"

    async def _call_gemini(_func, prompt: str, **_kwargs):
        captured["circuit_prompt"] = prompt
        return "Resposta final.", False

    client._generate_cache_key = _cache_key
    client._get_cached_response = AsyncMock(return_value=None)
    client._cache_response = AsyncMock()
    client._circuit_breaker = cast(Any, SimpleNamespace(call_gemini=_call_gemini))

    prompt = (
        'name: "Maria Souza"\n'
        "telefone: +55 11 98888-7777\n"
        "cpf: 123.456.789-09\n"
        "email: maria@example.com\n"
    )

    result = await GeminiClient.generate_content(
        client,
        prompt,
        guardrail_retries=0,
    )

    assert result == "Resposta final."
    assert "Maria Souza" not in captured["cache_prompt"]
    assert "123.456.789-09" not in captured["cache_prompt"]
    assert "maria@example.com" not in captured["cache_prompt"]
    assert "Maria Souza" not in captured["circuit_prompt"]
    assert "+55 11 98888-7777" not in captured["circuit_prompt"]
    assert "[REDACTED]" in captured["circuit_prompt"]
    assert "Paciente" in captured["circuit_prompt"]


@pytest.mark.asyncio
async def test_generate_content_repairs_missing_ending_punctuation_for_messages():
    client = GeminiClient.__new__(GeminiClient)

    client._generate_cache_key = lambda prompt, *, profile_hint="raw": "cache-key"
    client._get_cached_response = AsyncMock(return_value=None)
    client._cache_response = AsyncMock()
    client._circuit_breaker = cast(
        Any,
        SimpleNamespace(
            call_gemini=AsyncMock(return_value=("Mensagem sem ponto", False))
        ),
    )

    result = await GeminiClient.generate_content(
        client,
        "Teste de pontuacao",
        output_kind=OutputKind.MESSAGE,
        require_ending_punctuation=True,
        guardrail_retries=0,
    )

    assert result == "Mensagem sem ponto."
    client._cache_response.assert_awaited_once_with("cache-key", "Mensagem sem ponto.")


@pytest.mark.asyncio
async def test_generate_content_internal_rate_limit_timeout_uses_bounded_fallback(
    monkeypatch,
):
    async def _slow_rate_limit(**_kwargs):
        await asyncio.sleep(10)
        return True, 0

    monkeypatch.setattr("app.ai.client.check_ai_rate_limit", _slow_rate_limit)
    monkeypatch.setattr(ai_client_module.settings, "REDIS_OPERATION_TIMEOUT", 0.001)

    client = _build_client_stub()

    for index in range(60):
        await GeminiClient._generate_content_internal(
            client,
            f"prompt-timeout-{index}",
            max_retries=1,
        )

    with pytest.raises(AIRateLimitExceeded) as exc_info:
        await GeminiClient._generate_content_internal(
            client,
            "prompt-timeout-over-limit",
            max_retries=1,
        )

    assert exc_info.value.service == "gemini"
    assert exc_info.value.retry_after > 0


@pytest.mark.asyncio
async def test_generate_content_internal_rate_limit_error_uses_bounded_fallback(
    monkeypatch,
):
    async def _broken_rate_limit(**_kwargs):
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr("app.ai.client.check_ai_rate_limit", _broken_rate_limit)

    client = _build_client_stub()

    for index in range(60):
        await GeminiClient._generate_content_internal(
            client,
            f"prompt-error-{index}",
            max_retries=1,
        )

    with pytest.raises(AIRateLimitExceeded) as exc_info:
        await GeminiClient._generate_content_internal(
            client,
            "prompt-error-over-limit",
            max_retries=1,
        )

    assert exc_info.value.service == "gemini"
    assert exc_info.value.retry_after > 0
