from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.ai.agents.base import PIISafeAgent
from app.ai.agents.deps import AIDeps


def _build_agent_with_mocked_runner(output_text: str) -> tuple[PIISafeAgent, AIDeps, MagicMock]:
    agent = PIISafeAgent()
    run_sync_mock = MagicMock(return_value=SimpleNamespace(output=output_text))
    agent._agent = MagicMock(run_sync=run_sync_mock)
    deps = AIDeps(gemini_api_key="test-key", model_name="gemini-2.0-flash")
    return agent, deps, run_sync_mock


def test_safe_run_sync_keeps_open_loop_and_calls_expected_layers() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    agent, deps, run_sync_mock = _build_agent_with_mocked_runner("ok-normal")

    with (
        patch(
            "app.ai.agents.base.sanitize_prompt_text_for_external_ai",
            return_value="sanitized prompt",
        ) as sanitize_mock,
        patch("app.ai.agents.base.GoogleProvider", return_value="provider") as provider_ctor,
        patch("app.ai.agents.base.GoogleModel", return_value="model") as model_ctor,
        patch.object(agent, "_warn_on_output_pii") as warn_mock,
    ):
        output = agent._safe_run_sync("raw prompt", deps, operation="normal-loop")

    assert output == "ok-normal"
    assert asyncio.get_event_loop() is loop
    sanitize_mock.assert_called_once_with("raw prompt")
    provider_ctor.assert_called_once_with(api_key="test-key")
    model_ctor.assert_called_once_with("gemini-2.0-flash", provider="provider")
    run_sync_mock.assert_called_once_with("sanitized prompt", model="model", deps=deps)
    warn_mock.assert_called_once_with("ok-normal", operation="normal-loop")

    loop.close()
    asyncio.set_event_loop(None)


def test_safe_run_sync_replaces_closed_loop() -> None:
    closed_loop = asyncio.new_event_loop()
    closed_loop.close()
    asyncio.set_event_loop(closed_loop)
    agent, deps, _ = _build_agent_with_mocked_runner("ok-closed")

    with (
        patch(
            "app.ai.agents.base.sanitize_prompt_text_for_external_ai",
            return_value="sanitized prompt",
        ),
        patch("app.ai.agents.base.GoogleProvider", return_value="provider"),
        patch("app.ai.agents.base.GoogleModel", return_value="model"),
        patch.object(agent, "_warn_on_output_pii"),
    ):
        output = agent._safe_run_sync("raw prompt", deps, operation="closed-loop")

    assert output == "ok-closed"
    current_loop = asyncio.get_event_loop()
    assert current_loop is not closed_loop
    assert not current_loop.is_closed()

    current_loop.close()
    asyncio.set_event_loop(None)


def test_safe_run_sync_creates_loop_when_none_exists() -> None:
    asyncio.set_event_loop(None)
    agent, deps, _ = _build_agent_with_mocked_runner("ok-no-loop")

    with (
        patch(
            "app.ai.agents.base.sanitize_prompt_text_for_external_ai",
            return_value="sanitized prompt",
        ),
        patch("app.ai.agents.base.GoogleProvider", return_value="provider"),
        patch("app.ai.agents.base.GoogleModel", return_value="model"),
        patch.object(agent, "_warn_on_output_pii"),
    ):
        output = agent._safe_run_sync("raw prompt", deps, operation="no-loop")

    assert output == "ok-no-loop"
    current_loop = asyncio.get_event_loop()
    assert not current_loop.is_closed()

    current_loop.close()
    asyncio.set_event_loop(None)
