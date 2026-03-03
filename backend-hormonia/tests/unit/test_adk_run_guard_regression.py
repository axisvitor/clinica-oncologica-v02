"""Regression tests for ADK direct-run CI guard."""

import subprocess
import sys
from pathlib import Path


def _run_guard(target: Path) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).resolve().parents[2] / "scripts" / "check_agent_run_calls.py"
    assert script.exists(), f"CI guard script not found: {script}"
    return subprocess.run(
        [sys.executable, str(script), str(target)],
        capture_output=True,
        text=True,
        cwd=str(script.parent.parent),
    )


def test_direct_adk_runner_call_fails_guard(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad_adk.py"
    bad_file.write_text(
        "def run_task(runner):\n"
        "    return runner.run_async('unsafe')\n",
        encoding="utf-8",
    )

    result = _run_guard(tmp_path)

    assert result.returncode == 1
    assert "bad_adk.py:" in result.stdout
    assert "runner.run_async(" in result.stdout


def test_clean_file_passes_guard(tmp_path: Path) -> None:
    clean_file = tmp_path / "clean.py"
    clean_file.write_text(
        "def run_task(value):\n"
        "    return value\n",
        encoding="utf-8",
    )

    result = _run_guard(tmp_path)

    assert result.returncode == 0
    assert "No direct agent/adk run() calls found outside approved wrappers" in result.stdout
