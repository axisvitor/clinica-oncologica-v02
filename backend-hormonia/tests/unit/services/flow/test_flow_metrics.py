from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from prometheus_client import REGISTRY
from prometheus_client.metrics import Counter

os.environ.setdefault("WHATSAPP_WUZAPI_TOKEN", "test-token")

from app.services.flow.sequential_message_handler_pkg.personalization import (
    PersonalizationMixin,
)


def _sample_value(name: str, labels: dict[str, str]) -> float:
    value = REGISTRY.get_sample_value(name, labels=labels)
    return 0.0 if value is None else float(value)


class _StubPersonalizer(PersonalizationMixin):
    def __init__(self, *, use_ai_personalization: bool = True) -> None:
        self.use_ai_personalization = use_ai_personalization
        self.use_sync_agent_bridge = False
        self._enhanced_flow_engine = None

    def _build_fallback_content(self, **_: object) -> str:
        return "fallback message"


def _patient() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), name="Test Patient")


def _message(*, expects_response: bool = True) -> dict[str, object]:
    return {
        "content": "Como voce esta hoje?",
        "expects_response": expects_response,
    }


def test_record_ai_fallback_increments_timeout_counter() -> None:
    from app.services.flow.metrics import record_ai_fallback

    labels = {"reason": "timeout"}
    before = _sample_value("ai_personalization_fallback_total", labels)

    record_ai_fallback(reason="timeout")

    after = _sample_value("ai_personalization_fallback_total", labels)
    assert after == before + 1.0


def test_record_ai_fallback_keeps_reason_labels_distinct() -> None:
    from app.services.flow.metrics import record_ai_fallback

    timeout_labels = {"reason": "timeout"}
    empty_labels = {"reason": "empty_ai_result"}
    before_timeout = _sample_value("ai_personalization_fallback_total", timeout_labels)
    before_empty = _sample_value("ai_personalization_fallback_total", empty_labels)

    record_ai_fallback(reason="timeout")
    record_ai_fallback(reason="empty_ai_result")

    assert _sample_value("ai_personalization_fallback_total", timeout_labels) == (
        before_timeout + 1.0
    )
    assert _sample_value("ai_personalization_fallback_total", empty_labels) == (
        before_empty + 1.0
    )


def test_ai_fallback_metric_is_prometheus_counter() -> None:
    from app.services.flow.metrics import AI_PERSONALIZATION_FALLBACK_TOTAL

    assert isinstance(AI_PERSONALIZATION_FALLBACK_TOTAL, Counter)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("use_ai_personalization", "message", "engine_factory", "grounded", "reason"),
    [
        (
            False,
            _message(),
            lambda: None,
            True,
            "ai_disabled",
        ),
        (
            True,
            _message(expects_response=False),
            lambda: None,
            True,
            "non_response_message",
        ),
        (
            True,
            _message(),
            lambda: SimpleNamespace(
                generate_flow_message=Mock(return_value=asyncio.sleep(0, result=""))
            ),
            True,
            "empty_ai_result",
        ),
        (
            True,
            _message(),
            lambda: SimpleNamespace(
                generate_flow_message=Mock(
                    return_value=asyncio.sleep(0, result="conteudo desalinhado")
                )
            ),
            False,
            "not_grounded",
        ),
        (
            True,
            _message(),
            lambda: SimpleNamespace(
                generate_flow_message=Mock(side_effect=asyncio.TimeoutError())
            ),
            True,
            "timeout",
        ),
        (
            True,
            _message(),
            lambda: SimpleNamespace(
                generate_flow_message=Mock(side_effect=ValueError("bad prompt"))
            ),
            True,
            "value_runtime_error",
        ),
        (
            True,
            _message(),
            lambda: SimpleNamespace(
                generate_flow_message=Mock(side_effect=Exception("boom"))
            ),
            True,
            "unexpected_error",
        ),
    ],
)
async def test_personalization_mixin_records_all_fallback_paths(
    use_ai_personalization: bool,
    message: dict[str, object],
    engine_factory,
    grounded: bool,
    reason: str,
) -> None:
    personalizer = _StubPersonalizer(use_ai_personalization=use_ai_personalization)
    patient = _patient()

    with patch(
        "app.services.flow.sequential_message_handler_pkg.personalization.record_ai_fallback"
    ) as record_ai_fallback:
        if engine_factory() is not None:
            personalizer._enhanced_flow_engine = engine_factory()
        with patch.object(
            personalizer,
            "_personalization_is_grounded",
            return_value=grounded,
        ):
            result = await personalizer._personalize_message_ai(
                message=message,
                patient=patient,
                day_number=3,
                flow_kind="onboarding",
            )

    assert result == "fallback message"
    record_ai_fallback.assert_called_once_with(reason=reason)
