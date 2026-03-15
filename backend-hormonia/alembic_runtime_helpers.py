"""Importable shim for migration-only helpers stored under `alembic/`.

The project-local `alembic/` directory is not importable as `alembic.*` because the
installed Alembic package already owns that name. Historical revisions import this
shim instead, while the actual helper implementation stays alongside the migration
scripts in `alembic/runtime_helpers.py`.
"""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

_HELPER_MODULE: ModuleType | None = None
_HELPERS_PATH = Path(__file__).resolve().parent / "alembic" / "runtime_helpers.py"


def _load_helper_module() -> ModuleType:
    global _HELPER_MODULE

    if _HELPER_MODULE is not None:
        return _HELPER_MODULE

    spec = spec_from_file_location("_alembic_runtime_helpers", _HELPERS_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load migration runtime helpers from {_HELPERS_PATH}")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    _HELPER_MODULE = module
    return module



def __getattr__(name: str):
    return getattr(_load_helper_module(), name)


__all__ = [
    "PATIENT_METADATA_SCHEMA",
    "get_validation_errors",
    "is_valid_metadata",
    "now_sao_paulo_naive",
    "sanitize_metadata",
]
