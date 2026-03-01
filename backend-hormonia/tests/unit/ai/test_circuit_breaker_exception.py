"""
Unit tests for circuit breaker exception type in GeminiClient.generate_content().

Verifies that when the circuit breaker is open (used_fallback=True),
FeatureNotAvailableError is raised instead of GeminiAPIError.

AI-04 requirement satisfaction.
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from app.core.exceptions import FeatureNotAvailableError, AIServiceError


class TestFeatureNotAvailableErrorSubclassing:
    """Static / sync checks — no event loop required."""

    def test_feature_not_available_error_is_catchable_as_ai_service_error(self):
        """
        FeatureNotAvailableError must be a subclass of AIServiceError so that
        existing broad ``except AIServiceError`` handlers still work after the
        circuit-breaker exception type change.
        """
        assert issubclass(FeatureNotAvailableError, AIServiceError)

    def test_feature_not_available_error_carries_expected_attributes(self):
        """Sanity-check the exception's own attributes."""
        err = FeatureNotAvailableError(
            "Gemini circuit breaker open — feature unavailable",
            "gemini",
            "generate_content",
        )
        assert err.graph_name == "gemini"
        assert err.operation == "generate_content"
        assert "circuit breaker" in str(err).lower()


@pytest.mark.asyncio
class TestCircuitBreakerExceptionType:
    """Async tests for GeminiClient.generate_content() circuit-open behaviour."""

    @pytest.fixture()
    def client(self):
        """
        Create a GeminiClient without a real API key.

        The test replaces _circuit_breaker.call_gemini so no Gemini API call
        is ever made; the API-key check in _generate_content_internal is never
        reached.
        """
        from app.ai.client import GeminiClient

        # Pass a dummy key so __init__ doesn't skip model init; the model
        # itself is never invoked because call_gemini is monkeypatched below.
        c = GeminiClient.__new__(GeminiClient)
        # Minimal initialisation — avoids hitting real external services.
        import asyncio
        from collections import deque

        c.api_key = "dummy-key-for-tests"
        c.model_name = "gemini-test"
        c.model = None
        c._redis_client = None
        c._redis_initialized = False
        c._model_loop_id = None
        c._fallback_rate_limit_lock = asyncio.Lock()
        c._fallback_rate_limit_events = deque()
        # Attach a real circuit breaker reference so attribute access doesn't
        # fail — the actual call_gemini coroutine is replaced per test.
        from app.resilience.circuit_breaker import get_ai_circuit_breaker
        c._circuit_breaker = get_ai_circuit_breaker()
        return c

    async def test_generate_content_raises_feature_not_available_on_circuit_open(
        self, client, monkeypatch
    ):
        """
        When call_gemini returns (text, True) — i.e. circuit is open and a
        fallback was used — generate_content() must raise FeatureNotAvailableError
        with the canonical graph_name and operation attributes.
        """

        async def _fake_call_gemini(_fn, _prompt, **_kw):
            return ("fallback text", True)

        monkeypatch.setattr(client._circuit_breaker, "call_gemini", _fake_call_gemini)

        # Cache must be cold so we don't get a cached hit before the CB path.
        async def _no_cache(_key):
            return None

        monkeypatch.setattr(client, "_get_cached_response", _no_cache)

        # Rate limiter must allow the call.
        async def _allow_rate_limit(*_a, **_kw):
            return (True, 0)

        import app.ai.client as client_module
        monkeypatch.setattr(client_module, "check_ai_rate_limit", _allow_rate_limit)

        with pytest.raises(FeatureNotAvailableError) as exc_info:
            await client.generate_content("test prompt")

        err = exc_info.value
        assert err.graph_name == "gemini"
        assert err.operation == "generate_content"

    async def test_generate_content_returns_normally_when_circuit_closed(
        self, client, monkeypatch
    ):
        """
        When call_gemini returns (text, False) — circuit closed, normal
        operation — generate_content() must return the response text without
        raising FeatureNotAvailableError.
        """

        async def _fake_call_gemini(_fn, _prompt, **_kw):
            return ("valid response text.", False)

        monkeypatch.setattr(client._circuit_breaker, "call_gemini", _fake_call_gemini)

        # Cold cache.
        async def _no_cache(_key):
            return None

        monkeypatch.setattr(client, "_get_cached_response", _no_cache)

        # Skip Redis write in _cache_response.
        async def _noop_cache(_key, _val, **_kw):
            return None

        monkeypatch.setattr(client, "_cache_response", _noop_cache)

        # Rate limiter allows.
        async def _allow_rate_limit(*_a, **_kw):
            return (True, 0)

        import app.ai.client as client_module
        monkeypatch.setattr(client_module, "check_ai_rate_limit", _allow_rate_limit)

        result = await client.generate_content("test prompt")
        assert result == "valid response text."
