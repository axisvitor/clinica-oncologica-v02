"""Compatibility alias for legacy app.api.v2.reports imports."""
import importlib
import sys

_module = importlib.import_module("app.api.v2.routers.reports")
sys.modules[__name__] = _module
