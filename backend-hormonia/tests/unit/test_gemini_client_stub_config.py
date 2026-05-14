from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.ai import client as ai_client_module
from app.ai.client import GeminiClient


def _patch_required_settings(monkeypatch, *, base_url: str | None) -> None:
    monkeypatch.setattr(ai_client_module.settings, "AI_GEMINI_API_KEY", "settings-api-key")
    monkeypatch.setattr(ai_client_module.settings, "AI_GEMINI_BASE_URL", base_url)
    monkeypatch.setattr(ai_client_module.settings, "AI_GEMINI_MODEL", "settings-model")
    monkeypatch.setattr(ai_client_module.settings, "AI_GEMINI_TEMPERATURE", 0.2)
    monkeypatch.setattr(ai_client_module.settings, "AI_GEMINI_MAX_OUTPUT_TOKENS", 123)
    monkeypatch.setattr(ai_client_module.settings, "AI_GEMINI_TOP_P", 0.7)
    monkeypatch.setattr(ai_client_module.settings, "AI_GEMINI_TOP_K", 12)


def test_gemini_client_uses_configured_base_url_for_runtime_stub(monkeypatch):
    _patch_required_settings(
        monkeypatch,
        base_url="http://provider-stub:18089",
    )
    captured_client_kwargs: dict[str, Any] = {}
    captured_log_extras: list[dict[str, Any]] = []
    fake_genai_client = SimpleNamespace(name="fake-genai-client")

    def fake_client(**kwargs):
        captured_client_kwargs.update(kwargs)
        return fake_genai_client

    def fake_info(_message, *_args, **kwargs):
        captured_log_extras.append(kwargs.get("extra", {}))

    monkeypatch.setattr(ai_client_module.genai, "Client", fake_client)
    monkeypatch.setattr(ai_client_module.logger, "info", fake_info)

    client = GeminiClient(api_key="unit-api-key", model="unit-model")

    assert client.model is fake_genai_client
    assert captured_client_kwargs["api_key"] == "unit-api-key"
    http_options = captured_client_kwargs["http_options"]
    assert http_options.base_url == "http://provider-stub:18089"
    assert captured_log_extras[-1]["custom_base_url_configured"] is True
    assert "unit-api-key" not in str(captured_log_extras[-1])
    assert "provider-stub" not in str(captured_log_extras[-1])


def test_gemini_client_omits_http_options_when_base_url_unset(monkeypatch):
    _patch_required_settings(monkeypatch, base_url=None)
    captured_client_kwargs: dict[str, Any] = {}
    captured_log_extras: list[dict[str, Any]] = []
    fake_genai_client = SimpleNamespace(name="fake-genai-client")

    def fake_client(**kwargs):
        captured_client_kwargs.update(kwargs)
        return fake_genai_client

    def fake_info(_message, *_args, **kwargs):
        captured_log_extras.append(kwargs.get("extra", {}))

    monkeypatch.setattr(ai_client_module.genai, "Client", fake_client)
    monkeypatch.setattr(ai_client_module.logger, "info", fake_info)

    client = GeminiClient(api_key="unit-api-key", model="unit-model")

    assert client.model is fake_genai_client
    assert captured_client_kwargs == {"api_key": "unit-api-key"}
    assert captured_log_extras[-1]["custom_base_url_configured"] is False
    assert "unit-api-key" not in str(captured_log_extras[-1])


def test_gemini_client_settings_api_key_still_works_with_base_url(monkeypatch):
    _patch_required_settings(
        monkeypatch,
        base_url="http://localhost:18089",
    )
    captured_client_kwargs: dict[str, Any] = {}
    fake_genai_client = SimpleNamespace(name="fake-genai-client")

    def fake_client(**kwargs):
        captured_client_kwargs.update(kwargs)
        return fake_genai_client

    monkeypatch.setattr(ai_client_module.genai, "Client", fake_client)

    client = GeminiClient()

    assert client.model is fake_genai_client
    assert captured_client_kwargs["api_key"] == "settings-api-key"
    assert captured_client_kwargs["http_options"].base_url == "http://localhost:18089"
