"""Regression test: zero imports of tombstoned Evolution API in application code.

Calls scripts/check_evolution_imports.py and asserts exit 0.
Phase 38 requirement TEST-05.
"""

import subprocess
import sys
from pathlib import Path


def test_no_evolution_imports_in_app():
    """Source-level regression: zero Evolution imports outside tombstone files."""
    script = Path(__file__).resolve().parents[2] / "scripts" / "check_evolution_imports.py"
    assert script.exists(), f"CI guard script not found: {script}"

    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(script.parent.parent),
    )
    assert result.returncode == 0, (
        f"Evolution import violations found:\n{result.stdout}\n{result.stderr}"
    )
