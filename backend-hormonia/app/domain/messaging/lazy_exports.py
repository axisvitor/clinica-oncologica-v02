"""Helpers for module-level lazy export resolution."""

from __future__ import annotations

from importlib import import_module
from typing import Dict, Tuple, Any


def resolve_lazy_export(
    *,
    name: str,
    exports: Dict[str, Tuple[str, str]],
    module_name: str,
    target_globals: dict[str, Any],
) -> Any:
    """Resolve and memoize lazy exported attributes for package modules."""
    if name not in exports:
        raise AttributeError(f"module {module_name!r} has no attribute {name!r}")

    module_path, attr_name = exports[name]
    module = import_module(module_path)
    value = getattr(module, attr_name)
    target_globals[name] = value
    return value
