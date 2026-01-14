"""Compatibility alias for legacy app.api.v2.system imports."""
import importlib
import sys

_module = importlib.import_module("app.api.v2.routers.system")
sys.modules[__name__] = _module
