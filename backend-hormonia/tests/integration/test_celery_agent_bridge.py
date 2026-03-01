from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.agents.base import PIISafeAgent
from app.ai.agents.deps import AIDeps


class TestCeleryAgentBridge:
    @pytest.fixture
    def agent_with_mocked_run_sync(self) -> tuple[PIISafeAgent, AIDeps, MagicMock]:
        agent = PIISafeAgent()
        run_sync_mock = MagicMock(side_effect=lambda prompt, **_: SimpleNamespace(output=f"ok::{prompt}"))
        agent._agent = MagicMock(run_sync=run_sync_mock)
        deps = AIDeps(gemini_api_key="test-key", model_name="gemini-2.0-flash")
        return agent, deps, run_sync_mock

    def test_100_sequential_calls_no_event_loop_error(
        self, agent_with_mocked_run_sync: tuple[PIISafeAgent, AIDeps, MagicMock]
    ) -> None:
        agent, deps, run_sync_mock = agent_with_mocked_run_sync
        errors: list[str] = []

        with (
            patch("app.ai.agents.base.sanitize_prompt_text_for_external_ai", side_effect=lambda text: text),
            patch("app.ai.agents.base.GoogleProvider", return_value="provider"),
            patch("app.ai.agents.base.GoogleModel", return_value="model"),
            patch.object(agent, "_warn_on_output_pii"),
        ):
            for i in range(100):
                try:
                    loop = asyncio.get_event_loop()
                    if not loop.is_closed():
                        loop.close()
                except RuntimeError:
                    pass

                try:
                    result = agent._safe_run_sync(
                        f"Test prompt {i}",
                        deps,
                        operation=f"load_test_{i}",
                    )
                    assert result == f"ok::Test prompt {i}"
                except RuntimeError as exc:
                    errors.append(f"Call {i}: {exc}")

        assert not errors, f"Event loop errors in {len(errors)}/100 calls: {errors[:5]}"
        assert run_sync_mock.call_count == 100

        current_loop = asyncio.get_event_loop()
        if not current_loop.is_closed():
            current_loop.close()
        asyncio.set_event_loop(None)

    def test_mixed_open_closed_loop_pattern(
        self, agent_with_mocked_run_sync: tuple[PIISafeAgent, AIDeps, MagicMock]
    ) -> None:
        agent, deps, run_sync_mock = agent_with_mocked_run_sync

        with (
            patch("app.ai.agents.base.sanitize_prompt_text_for_external_ai", side_effect=lambda text: text),
            patch("app.ai.agents.base.GoogleProvider", return_value="provider"),
            patch("app.ai.agents.base.GoogleModel", return_value="model"),
            patch.object(agent, "_warn_on_output_pii"),
        ):
            for i in range(50):
                if i % 2 == 0:
                    try:
                        loop = asyncio.get_event_loop()
                        if not loop.is_closed():
                            loop.close()
                    except RuntimeError:
                        pass

                result = agent._safe_run_sync(
                    f"Mixed prompt {i}",
                    deps,
                    operation=f"mixed_test_{i}",
                )
                assert result == f"ok::Mixed prompt {i}"

        assert run_sync_mock.call_count == 50

        current_loop = asyncio.get_event_loop()
        if not current_loop.is_closed():
            current_loop.close()
        asyncio.set_event_loop(None)

    @pytest.mark.asyncio
    async def test_fastapi_async_path_still_works(self) -> None:
        agent = PIISafeAgent()
        agent._agent = MagicMock(run=AsyncMock(return_value=SimpleNamespace(output="async-ok")))
        deps = AIDeps(gemini_api_key="test-key", model_name="gemini-2.0-flash")

        with (
            patch("app.ai.agents.base.sanitize_prompt_text_for_external_ai", return_value="sanitized async"),
            patch("app.ai.agents.base.GoogleProvider", return_value="provider"),
            patch("app.ai.agents.base.GoogleModel", return_value="model"),
            patch.object(agent, "_warn_on_output_pii") as warn_mock,
        ):
            result = await agent._safe_run("raw async", deps, operation="async-path")

        assert result == "async-ok"
        agent._agent.run.assert_awaited_once_with("sanitized async", model="model", deps=deps)
        warn_mock.assert_called_once_with("async-ok", operation="async-path")
