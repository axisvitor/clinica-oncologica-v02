"""Root-level wrapper for the backend M015 runtime harness tests.

Some automation invokes this file from the repository root with ``PYTHONPATH=.``.
The canonical tests live under ``backend-hormonia/tests/security`` where backend
imports resolve with ``PYTHONPATH=.`` after changing into that directory.  This
wrapper adds the backend root to ``sys.path`` and re-exports the canonical test
functions so both invocation styles exercise the same assertions.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend-hormonia"
CANONICAL_TEST = BACKEND_ROOT / "tests" / "security" / "test_m015_runtime_harness.py"

sys.path.insert(0, str(BACKEND_ROOT))

spec = importlib.util.spec_from_file_location("_m015_backend_runtime_harness_tests", CANONICAL_TEST)
if spec is None or spec.loader is None:  # pragma: no cover - importlib defensive guard.
    raise RuntimeError(f"Unable to load canonical test module from {CANONICAL_TEST}")

module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

for name, value in vars(module).items():
    if name.startswith("test_"):
        globals()[name] = value
