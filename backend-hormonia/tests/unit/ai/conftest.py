"""Fixtures for AI agent unit tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.ai.agents.deps import AIDeps


@pytest.fixture
def ai_deps() -> AIDeps:
    """Standard AIDeps for testing."""
    return AIDeps(gemini_api_key="test-key-fake", model_name="gemini-2.0-flash")


@pytest.fixture
def mock_agent_run():
    """Patch PIISafeAgent._safe_run to return controlled output."""

    def _factory(output_value):
        return patch(
            "app.ai.agents.base.PIISafeAgent._safe_run",
            new_callable=AsyncMock,
            return_value=output_value,
        )

    return _factory
