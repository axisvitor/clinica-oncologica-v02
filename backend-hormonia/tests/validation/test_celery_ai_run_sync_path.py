"""Validation guardrails for SDK-03 Celery AI sync wiring."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

BATCH_TASKS_PATH = ROOT / "app/tasks/flows/batch_tasks.py"
FLOW_AUTOMATION_PATH = ROOT / "app/tasks/flow_automation.py"
ENHANCED_FLOW_ENGINE_PATH = ROOT / "app/services/enhanced_flow_engine.py"

NON_AI_WRAPPER_PATHS = (
    ROOT / "app/tasks/flows/base.py",
    ROOT / "app/tasks/follow_up.py",
)


def _parse_file(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _calls_with_keyword_true(tree: ast.AST, call_name: str, keyword_name: str) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name = None
        if isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id
        if func_name != call_name:
            continue
        for kw in node.keywords:
            if kw.arg != keyword_name:
                continue
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return True
    return False


def test_batch_tasks_uses_sync_agent_keyword_for_ai_generation() -> None:
    tree = _parse_file(BATCH_TASKS_PATH)
    assert _calls_with_keyword_true(
        tree,
        call_name="generate_flow_message",
        keyword_name="use_sync_agents",
    )


def test_flow_automation_uses_sync_agent_bridge_for_sequential_handler() -> None:
    tree = _parse_file(FLOW_AUTOMATION_PATH)
    assert _calls_with_keyword_true(
        tree,
        call_name="SequentialMessageHandler",
        keyword_name="use_sync_agent_bridge",
    )


def test_enhanced_flow_engine_has_sync_agent_branch_and_sync_api_calls() -> None:
    source = ENHANCED_FLOW_ENGINE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(ENHANCED_FLOW_ENGINE_PATH))

    generate_fn = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "EnhancedFlowEngine":
            for body_item in node.body:
                if isinstance(body_item, ast.AsyncFunctionDef) and body_item.name == "generate_flow_message":
                    generate_fn = body_item
                    break

    assert generate_fn is not None
    assert "use_sync_agents" in [arg.arg for arg in generate_fn.args.args]
    assert "if use_sync_agents" in source
    assert "generate_varied_question_sync" in source
    assert "humanize_flow_message_sync" in source
    assert "analyze_response_sentiment_sync" in source
    assert "create_empathetic_follow_up_sync" in source


def _collect_import_targets(tree: ast.AST) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.add(module)
            for alias in node.names:
                imports.add(f"{module}.{alias.name}" if module else alias.name)
    return imports


def test_non_ai_async_wrappers_do_not_import_ai_or_langchain() -> None:
    banned_prefixes = (
        "app.ai",
        "app.ai.agents",
        "app.ai.client_domain.GeminiDomainClient",
        "langchain",
        "langgraph",
    )

    for path in NON_AI_WRAPPER_PATHS:
        imports = _collect_import_targets(_parse_file(path))
        bad = sorted(
            imported
            for imported in imports
            if any(imported.startswith(prefix) for prefix in banned_prefixes)
        )
        assert not bad, f"{path} imports banned AI modules: {bad}"
