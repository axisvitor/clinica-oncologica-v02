"""Compatibility alias for legacy app.api.v2.ai imports."""
import importlib
import sys

_module = importlib.import_module("app.api.v2.routers.ai")
sys.modules[__name__] = _module
