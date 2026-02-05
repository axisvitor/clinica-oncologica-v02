"""Compatibility alias for legacy app.api.v2.performance imports."""
import importlib
import sys

_module = importlib.import_module("app.api.v2.routers.performance")
sys.modules[__name__] = _module
