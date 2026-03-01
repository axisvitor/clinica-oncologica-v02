"""Compatibility checks for physicians router module resolution."""

from importlib.util import find_spec
from pathlib import Path

from fastapi import APIRouter

import app.api.v2.routers.physicians as physicians_module


def test_physicians_import_resolves_to_package():
    """The canonical physicians import must resolve to the package, not .py shim."""
    spec = find_spec("app.api.v2.routers.physicians")

    assert spec is not None
    assert spec.submodule_search_locations is not None
    assert isinstance(physicians_module.router, APIRouter)

    module_file = Path(physicians_module.__file__)
    assert module_file.name == "__init__.py"
    assert module_file.parent.name == "physicians"
