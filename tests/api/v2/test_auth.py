"""Root test-path shim for backend auth API v2 tests.

The GSD verification gate invokes this path from the repository root, while the
canonical backend test lives under backend-hormonia/tests.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest


os.environ.setdefault("APP_ENVIRONMENT", "development")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("ENCRYPTION_KEY", "32byte-secret-key-for-testing-123")
os.environ.setdefault("ENCRYPTION_SALT", "test-salt-16bytes")
os.environ.setdefault("SECURITY_CSRF_SECRET_KEY", "u4vT9qW2eR8yU6iO1pA7sD3fG5hJ9kL2zX4cV6bN8mQ0")
os.environ.setdefault("DATABASE_URL", "postgresql://test_user:test_password@db.invalid:5432/hormonia_test")

ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = ROOT / "backend-hormonia"
CANONICAL_TEST = BACKEND_ROOT / "tests" / "api" / "v2" / "test_auth.py"

sys.path.insert(0, str(BACKEND_ROOT))
pytest_plugins = ("tests.conftest", "tests.api.v2.conftest", "tests.api.v2.conftest_auth")


@pytest.fixture
def admin_user(test_admin_user):
    """Alias canonical backend admin fixture for legacy auth tests."""
    return test_admin_user


spec = importlib.util.spec_from_file_location("_backend_test_auth_api_v2", CANONICAL_TEST)
if spec is None or spec.loader is None:  # pragma: no cover - importlib safety net
    raise RuntimeError(f"Unable to load canonical test module: {CANONICAL_TEST}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

for name, value in vars(module).items():
    if name.startswith("test_") or name.startswith("Test"):
        globals()[name] = value
