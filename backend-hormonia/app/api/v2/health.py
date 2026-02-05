"""Compatibility alias for legacy app.api.v2.health imports."""
import importlib
import sys

_module = importlib.import_module("app.api.v2.routers.health")
sys.modules[__name__] = _module
