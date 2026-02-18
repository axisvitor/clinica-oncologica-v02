"""Regression guard for monitoring Celery task registration signatures."""

from __future__ import annotations

import ast
from pathlib import Path


EXPECTED_MONITORING_TASKS = {
    "monitoring.system_health_check": "SystemHealthCheckTask",
    "monitoring.performance_metrics_collection": "PerformanceMetricsCollectionTask",
    "monitoring.bottleneck_detection": "BottleneckDetectionTask",
    "monitoring.alert_monitoring": "AlertMonitoringTask",
    "monitoring.escalation_check": "EscalationCheckTask",
    "monitoring.automated_recovery": "AutomatedRecoveryTask",
    "monitoring.cleanup_old_data": "CleanupOldMonitoringDataTask",
    "monitoring.data_integrity_guardrails": "DataIntegrityGuardrailsTask",
}


def _extract_task_name(decorator: ast.expr) -> str | None:
    if not isinstance(decorator, ast.Call):
        return None
    if not (isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "task"):
        return None
    for keyword in decorator.keywords:
        if (
            keyword.arg == "name"
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
        ):
            return keyword.value.value
    return None


def _extract_assignment_style_monitoring_names(module_ast: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in module_ast.body:
        if not isinstance(node, ast.Assign):
            continue
        # Legacy style:
        # foo = task_queue.task(name="...")(SomeTask().run)
        if not isinstance(node.value, ast.Call):
            continue
        if not isinstance(node.value.func, ast.Call):
            continue
        inner_call = node.value.func
        if not (
            isinstance(inner_call.func, ast.Attribute) and inner_call.func.attr == "task"
        ):
            continue
        for keyword in inner_call.keywords:
            if (
                keyword.arg == "name"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
                and keyword.value.value.startswith("monitoring.")
            ):
                names.add(keyword.value.value)
    return names


def test_monitoring_tasks_use_zero_arg_wrappers() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    file_path = repo_root / "app" / "tasks" / "monitoring.py"
    module_ast = ast.parse(file_path.read_text(encoding="utf-8"))

    wrapper_functions: dict[str, ast.FunctionDef] = {}
    for node in module_ast.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            task_name = _extract_task_name(decorator)
            if task_name and task_name.startswith("monitoring."):
                wrapper_functions[task_name] = node

    missing = sorted(set(EXPECTED_MONITORING_TASKS) - set(wrapper_functions))
    assert not missing, f"Missing monitoring task wrappers: {missing}"

    for task_name, expected_class in EXPECTED_MONITORING_TASKS.items():
        fn = wrapper_functions[task_name]
        assert not fn.args.args, f"{task_name} wrapper must not declare positional args"
        assert fn.args.vararg is None, f"{task_name} wrapper must not declare *args"
        assert not fn.args.kwonlyargs, f"{task_name} wrapper must not declare kw-only args"
        assert fn.args.kwarg is None, f"{task_name} wrapper must not declare **kwargs"
        assert len(fn.body) == 1 and isinstance(fn.body[0], ast.Return), (
            f"{task_name} wrapper must be a single return statement"
        )

        returned = fn.body[0].value
        assert isinstance(returned, ast.Call), (
            f"{task_name} wrapper must return a task method call"
        )
        assert isinstance(returned.func, ast.Attribute) and returned.func.attr == "run", (
            f"{task_name} wrapper must call .run()"
        )
        assert isinstance(returned.func.value, ast.Call), (
            f"{task_name} wrapper must instantiate {expected_class}"
        )
        class_call = returned.func.value
        assert isinstance(class_call.func, ast.Name) and class_call.func.id == expected_class, (
            f"{task_name} wrapper must instantiate {expected_class}"
        )
        assert not returned.args and not returned.keywords, (
            f"{task_name} wrapper must call .run() without args"
        )

    legacy_registration = _extract_assignment_style_monitoring_names(module_ast)
    assert not legacy_registration, (
        "Monitoring tasks must not use assignment-style registration. "
        f"Found legacy registrations: {sorted(legacy_registration)}"
    )
