"""Guardrail for Celery beat schedule and task registration names."""

from __future__ import annotations

import ast
from pathlib import Path


def _extract_beat_task_names(celery_app_file: Path) -> list[str]:
    module = ast.parse(celery_app_file.read_text(encoding="utf-8"))
    task_names: list[str] = []

    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue

        if not any(
            isinstance(target, ast.Attribute) and target.attr == "beat_schedule"
            for target in node.targets
        ):
            continue

        if not isinstance(node.value, ast.Dict):
            continue

        for schedule_entry in node.value.values:
            if not isinstance(schedule_entry, ast.Dict):
                continue
            for key, value in zip(schedule_entry.keys, schedule_entry.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "task"
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    task_names.append(value.value)

    return task_names


def _extract_registered_task_names(tasks_root: Path, app_root: Path) -> set[str]:
    task_names: set[str] = set()

    for py_file in tasks_root.rglob("*.py"):
        module_ast = ast.parse(py_file.read_text(encoding="utf-8"))
        module_rel = py_file.relative_to(app_root).with_suffix("")
        module_name = "app." + ".".join(module_rel.parts)

        for node in module_ast.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if not (
                    isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "task"
                ):
                    continue

                explicit_name = None
                for keyword in decorator.keywords:
                    if (
                        keyword.arg == "name"
                        and isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, str)
                    ):
                        explicit_name = keyword.value.value
                        break

                if explicit_name:
                    task_names.add(explicit_name)
                else:
                    task_names.add(f"{module_name}.{node.name}")

        # Also capture assignment style registrations:
        #   system_health_check_task = task_queue.task(name="...")(SystemHealthCheckTask())
        for call_node in ast.walk(module_ast):
            if not isinstance(call_node, ast.Call):
                continue
            if not (
                isinstance(call_node.func, ast.Attribute) and call_node.func.attr == "task"
            ):
                continue
            for keyword in call_node.keywords:
                if (
                    keyword.arg == "name"
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ):
                    task_names.add(keyword.value.value)

    return task_names


def test_celery_beat_schedule_points_to_registered_tasks() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_root = repo_root / "app"
    tasks_root = app_root / "tasks"
    celery_app_file = app_root / "celery_app.py"

    beat_task_names = _extract_beat_task_names(celery_app_file)
    assert beat_task_names, "Expected non-empty celery_app.conf.beat_schedule"
    assert len(beat_task_names) == len(set(beat_task_names)), (
        "Duplicate task names found in celery beat schedule"
    )

    registered_task_names = _extract_registered_task_names(tasks_root, app_root)
    missing = sorted(name for name in beat_task_names if name not in registered_task_names)

    assert not missing, (
        "Celery beat schedule points to missing task names:\n"
        + "\n".join(f"- {name}" for name in missing)
    )
