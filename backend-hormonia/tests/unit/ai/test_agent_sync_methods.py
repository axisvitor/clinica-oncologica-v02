from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.ai.agents.sentiment_agent import SentimentResult
from app.ai.client_domain import GeminiClient, GeminiDomainClient


def _build_domain_client() -> GeminiDomainClient:
    with patch.object(GeminiClient, "_initialize_model", autospec=True, return_value=None):
        return GeminiDomainClient(api_key="test-key", model="gemini-2.0-flash")


def test_domain_sync_methods_delegate_to_agent_sync_methods() -> None:
    client = _build_domain_client()

    with (
        patch("app.ai.client_domain.HumanizeAgent.humanize_sync", return_value="humanized") as humanize_sync,
        patch("app.ai.client_domain.VariationAgent.vary_sync", return_value="varied") as vary_sync,
        patch(
            "app.ai.client_domain.SentimentAgent.analyze_sync",
            return_value=SentimentResult(
                sentiment="neutral",
                confidence=0.6,
                emotional_indicators=["calm"],
                medical_concerns=[],
                requires_attention=False,
                key_themes=["routine"],
                suggested_follow_up="continue",
            ),
        ) as analyze_sync,
        patch("app.ai.client_domain.EmpathyAgent.follow_up_sync", return_value="empathetic") as follow_up_sync,
    ):
        humanized = client.humanize_flow_message_sync(
            template="Oi paciente",
            patient_name="Ana",
            patient_context={},
            conversation_history=[],
            personalization_hints=[],
        )
        varied = client.generate_varied_question_sync(
            base_question="Como voce esta hoje?",
            previous_questions=[],
            patient_context={},
        )
        sentiment = client.analyze_response_sentiment_sync(
            response="Estou bem",
            patient_context={},
        )
        empathy = client.create_empathetic_follow_up_sync(
            patient_response="Estou cansada",
            conversation_history=[],
            patient_context={},
        )

    assert humanized == "humanized"
    assert varied == "varied"
    assert empathy == "empathetic"
    assert isinstance(sentiment, dict)
    assert set(sentiment) == {
        "sentiment",
        "confidence",
        "emotional_indicators",
        "medical_concerns",
        "requires_attention",
        "key_themes",
        "suggested_follow_up",
    }

    humanize_sync.assert_called_once()
    vary_sync.assert_called_once()
    analyze_sync.assert_called_once()
    follow_up_sync.assert_called_once()


@pytest.mark.asyncio
async def test_domain_async_methods_remain_callable() -> None:
    client = _build_domain_client()

    with (
        patch("app.ai.client_domain.HumanizeAgent.humanize", new_callable=AsyncMock, return_value="humanized") as humanize,
        patch("app.ai.client_domain.VariationAgent.vary", new_callable=AsyncMock, return_value="varied") as vary,
        patch(
            "app.ai.client_domain.SentimentAgent.analyze",
            new_callable=AsyncMock,
            return_value=SentimentResult(),
        ) as analyze,
        patch("app.ai.client_domain.EmpathyAgent.follow_up", new_callable=AsyncMock, return_value="empathetic") as follow_up,
    ):
        assert (
            await client.humanize_flow_message(
                template="Oi paciente",
                patient_name="Ana",
                patient_context={},
                conversation_history=[],
                personalization_hints=[],
            )
            == "humanized"
        )
        assert (
            await client.generate_varied_question(
                base_question="Como voce esta hoje?",
                previous_questions=[],
                patient_context={},
            )
            == "varied"
        )
        sentiment = await client.analyze_response_sentiment(
            response="Tudo bem",
            patient_context={},
        )
        assert sentiment["sentiment"] == "neutral"
        assert (
            await client.create_empathetic_follow_up(
                patient_response="Estou cansada",
                conversation_history=[],
                patient_context={},
            )
            == "empathetic"
        )

    humanize.assert_awaited_once()
    vary.assert_awaited_once()
    analyze.assert_awaited_once()
    follow_up.assert_awaited_once()
