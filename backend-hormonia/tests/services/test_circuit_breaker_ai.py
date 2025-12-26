"""
Test Circuit Breaker Integration with AI Services
==================================================

Tests circuit breaker protection for:
- GeminiClient
- AIService

Verifies:
- Circuit opens after threshold failures
- Fallback mechanisms work correctly
- Circuit recovers after timeout
- Metrics are tracked properly
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.integrations.gemini_client import GeminiClient, GeminiAPIError
from app.services.ai.ai_service import AIService, PatientContext, ConcernLevel
from app.services.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
    get_ai_circuit_breaker,
)


class TestGeminiClientCircuitBreaker:
    """Test circuit breaker integration in GeminiClient."""

    @pytest.fixture
    def gemini_client(self):
        """Create GeminiClient instance for testing."""
        with patch("app.integrations.gemini_client.settings") as mock_settings:
            mock_settings.AI_GEMINI_API_KEY = "test-api-key"
            mock_settings.AI_GEMINI_MODEL = "gemini-2.0-flash-exp"
            mock_settings.AI_GEMINI_TEMPERATURE = 0.7
            mock_settings.AI_GEMINI_MAX_OUTPUT_TOKENS = 1024
            mock_settings.AI_GEMINI_TOP_P = 0.95
            mock_settings.AI_GEMINI_TOP_K = 40
            mock_settings.AI_GEMINI_MAX_RETRIES = 3
            mock_settings.AI_GEMINI_TIMEOUT_SECONDS = 30

            client = GeminiClient()
            return client

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self, gemini_client):
        """Test that circuit breaker opens after consecutive failures."""
        # Mock the internal generation to always fail
        with patch.object(
            gemini_client, "_generate_content_internal", side_effect=GeminiAPIError("API Error")
        ):
            # Trigger multiple failures (threshold is 3 for Gemini)
            for i in range(4):
                result = await gemini_client.generate_content("test prompt")
                # Should get fallback response
                assert "temporariamente indisponível" in result

            # Check circuit state
            breaker = gemini_client._circuit_breaker.breakers["gemini"]
            assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_uses_fallback(self, gemini_client):
        """Test that fallback is used when circuit is open."""
        # Manually open the circuit
        breaker = gemini_client._circuit_breaker.breakers["gemini"]
        breaker.state = CircuitState.OPEN

        # Try to generate content
        result = await gemini_client.generate_content("test prompt")

        # Should get fallback response
        assert "temporariamente indisponível" in result

    @pytest.mark.asyncio
    async def test_circuit_breaker_custom_fallback(self, gemini_client):
        """Test custom fallback response."""
        # Manually open the circuit
        breaker = gemini_client._circuit_breaker.breakers["gemini"]
        breaker.state = CircuitState.OPEN

        # Try with custom fallback
        custom_fallback = "Custom fallback message"
        result = await gemini_client.generate_content(
            "test prompt", fallback_response=custom_fallback
        )

        assert result == custom_fallback

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self, gemini_client):
        """Test that circuit recovers after successful calls."""
        # Mock successful generation
        mock_response = MagicMock()
        mock_response.content = "Generated response"

        with patch.object(gemini_client.model, "ainvoke", return_value=mock_response):
            # Should succeed and keep circuit closed
            result = await gemini_client.generate_content("test prompt")
            assert result == "Generated response"

            # Check circuit is still closed
            breaker = gemini_client._circuit_breaker.breakers["gemini"]
            assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_cache_hit_bypasses_circuit_breaker(self, gemini_client):
        """Test that cache hits don't trigger circuit breaker."""
        # Mock cache to return a value
        with patch.object(
            gemini_client, "_get_cached_response", return_value="Cached response"
        ):
            # Even with circuit open, should get cached response
            breaker = gemini_client._circuit_breaker.breakers["gemini"]
            breaker.state = CircuitState.OPEN

            result = await gemini_client.generate_content("test prompt")
            assert result == "Cached response"


class TestAIServiceCircuitBreaker:
    """Test circuit breaker integration in AIService."""

    @pytest.fixture
    async def ai_service(self):
        """Create AIService instance for testing."""
        service = AIService()
        # Mock the orchestrator
        service.orchestrator = AsyncMock()
        service.cache = AsyncMock()
        service._initialized = True
        return service

    @pytest.fixture
    def patient_context(self):
        """Create test patient context."""
        return PatientContext(
            patient_id="test-123",
            name="Test Patient",
            treatment_type="hormone",
            treatment_day=10,
            age=45,
        )

    @pytest.mark.asyncio
    async def test_sentiment_analysis_with_circuit_breaker(
        self, ai_service, patient_context
    ):
        """Test sentiment analysis with circuit breaker protection."""
        from app.integrations.openai_client import SentimentAnalysisResponse, SentimentType

        # Mock successful sentiment analysis
        mock_response = SentimentAnalysisResponse(
            sentiment=SentimentType.POSITIVE,
            key_phrases=["feeling good", "better"],
            medical_concerns=[],
            confidence_score=0.9,
        )

        ai_service.orchestrator.analyze_sentiment = AsyncMock(return_value=mock_response)

        # Should succeed
        response, concern = await ai_service.analyze_sentiment(
            "I'm feeling much better today!", patient_context
        )

        assert response.sentiment == SentimentType.POSITIVE
        assert concern == ConcernLevel.LOW

    @pytest.mark.asyncio
    async def test_sentiment_analysis_circuit_breaker_fallback(
        self, ai_service, patient_context
    ):
        """Test sentiment analysis fallback when circuit is open."""
        # Manually open the circuit
        breaker = ai_service._circuit_breaker.breakers["sentiment"]
        breaker.state = CircuitState.OPEN

        # Try sentiment analysis
        response, concern = await ai_service.analyze_sentiment(
            "I'm feeling sick", patient_context
        )

        # Should get fallback response (rule-based)
        assert response.sentiment in ["neutral", "negative"]
        assert response.get("fallback", False) is True or concern is not None

    @pytest.mark.asyncio
    async def test_circuit_breaker_stats(self, ai_service):
        """Test that circuit breaker stats are tracked."""
        breaker = ai_service._circuit_breaker

        # Get stats
        stats = breaker.get_all_stats()

        # Should have stats for all breakers
        assert "gemini" in stats
        assert "sentiment" in stats
        assert "quiz" in stats

        # Each should have state info
        for name, stat in stats.items():
            assert "state" in stat
            assert "total_requests" in stat
            assert stat["state"] in ["closed", "open", "half_open"]


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker behavior."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_state_transitions(self):
        """Test circuit breaker state transitions."""
        breaker = CircuitBreaker(
            name="test-breaker", failure_threshold=3, recovery_timeout=1
        )

        # Start in CLOSED state
        assert breaker.state == CircuitState.CLOSED

        # Simulate failures
        async def failing_func():
            raise Exception("Test failure")

        # Should fail threshold times before opening
        for i in range(3):
            try:
                await breaker.call(failing_func)
            except Exception:
                pass

        # Circuit should now be OPEN
        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(1.5)

        # Should transition to HALF_OPEN on next attempt
        async def success_func():
            return "success"

        # This should transition to HALF_OPEN and then CLOSED on success
        result = await breaker.call(success_func)
        assert result == "success"

        # After success threshold met, should be CLOSED
        # (Default success_threshold is 2, so need one more success)
        await breaker.call(success_func)
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_concurrent_circuit_breaker_calls(self):
        """Test circuit breaker handles concurrent calls correctly."""
        breaker = CircuitBreaker(name="concurrent-test", failure_threshold=5)

        call_count = 0

        async def tracked_func():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # Simulate some work
            return "success"

        # Make concurrent calls
        tasks = [breaker.call(tracked_func) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r == "success" for r in results)
        assert call_count == 10

        # Circuit should still be closed
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_metrics(self):
        """Test circuit breaker metrics collection."""
        breaker = CircuitBreaker(name="metrics-test")

        async def success_func():
            return "success"

        async def fail_func():
            raise Exception("fail")

        # Mix of successes and failures
        await breaker.call(success_func)
        await breaker.call(success_func)
        try:
            await breaker.call(fail_func)
        except Exception:
            pass

        # Check stats
        stats = breaker.get_stats()
        assert stats["total_requests"] == 3
        assert stats["successful_requests"] == 2
        assert stats["failed_requests"] == 1
        assert "success_rate" in stats


# Fixtures for pytest
@pytest.fixture(autouse=True)
def reset_circuit_breakers():
    """Reset circuit breakers between tests."""
    breaker = get_ai_circuit_breaker()
    breaker.reset_all()
    yield
    breaker.reset_all()
