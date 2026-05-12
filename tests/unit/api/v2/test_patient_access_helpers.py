"""Compatibility wrapper for root-cwd verification gates.

The canonical patient access helper tests live under
``backend-hormonia/tests/unit/api/v2/test_patient_access_helpers.py``. Some GSD
verification gates invoke this root-relative path, so this wrapper loads and
re-exports the canonical tests without duplicating their implementation.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[4]
_BACKEND_ROOT = _REPO_ROOT / "backend-hormonia"
_TARGET = _BACKEND_ROOT / "tests" / "unit" / "api" / "v2" / "test_patient_access_helpers.py"

_env_path = _BACKEND_ROOT / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

os.environ.setdefault("APP_ENVIRONMENT", "development")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("ENCRYPTION_KEY", "32byte-secret-key-for-testing-123")
os.environ.setdefault("ENCRYPTION_SALT", "test-salt-16bytes")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

sys.path.insert(0, str(_BACKEND_ROOT))

_spec = importlib.util.spec_from_file_location(
    "backend_unit_patient_access_helpers", _TARGET
)
_module = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_module)

for _name in dir(_module):
    if _name.startswith("test_"):
        globals()[_name] = getattr(_module, _name)
