"""Verify all app.ai.langgraph modules are tombstoned."""

import importlib

import pytest

TOMBSTONED_MODULES = [
    "app.ai.langgraph",
    "app.ai.langgraph.graphs",
    "app.ai.langgraph.nodes",
    "app.ai.langgraph.nodes_ai",
    "app.ai.langgraph.prompts",
    "app.ai.langgraph.runtime",
    "app.ai.langgraph.state",
    "app.ai.langgraph.ai_state",
    "app.ai.langgraph._invoke",
]


@pytest.mark.parametrize("module_path", TOMBSTONED_MODULES)
def test_tombstoned_module_raises_import_error(module_path: str) -> None:
    with pytest.raises(ImportError, match="tombstoned"):
        importlib.import_module(module_path)
