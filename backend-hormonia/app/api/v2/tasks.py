"""Compatibility alias for legacy app.api.v2.tasks imports."""
import importlib
import sys

_module = importlib.import_module("app.api.v2.routers.tasks")
sys.modules[__name__] = _module
