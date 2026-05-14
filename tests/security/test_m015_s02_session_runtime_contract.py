"""Root test-path shim for backend M015 S02 session runtime contract tests.

The GSD verification gate invokes this path from the repository root, while the
canonical backend test lives under backend-hormonia/tests.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


os.environ.setdefault("APP_ENVIRONMENT", "development")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("ENCRYPTION_KEY", "32byte-secret-key-for-testing-123")
os.environ.setdefault("ENCRYPTION_SALT", "test-salt-16bytes")
os.environ.setdefault("SECURITY_CSRF_SECRET_KEY", "u4vT9qW2eR8yU6iO1pA7sD3fG5hJ9kL2zX4cV6bN8mQ0")
os.environ.setdefault("DATABASE_URL", "postgresql://test_user:test_password@db.invalid:5432/hormonia_test")

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend-hormonia"
CANONICAL_TEST = BACKEND_ROOT / "tests" / "security" / "test_m015_s02_session_runtime_contract.py"

sys.path.insert(0, str(BACKEND_ROOT))
spec = importlib.util.spec_from_file_location("_backend_test_m015_s02_session_runtime_contract", CANONICAL_TEST)
if spec is None or spec.loader is None:  # pragma: no cover - importlib safety net
    raise RuntimeError(f"Unable to load canonical test module: {CANONICAL_TEST}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

for name, value in vars(module).items():
    if name.startswith("test_"):
        globals()[name] = value
