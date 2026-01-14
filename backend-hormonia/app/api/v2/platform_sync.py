"""Compatibility alias for legacy app.api.v2.platform_sync imports."""
import importlib
import sys

_module = importlib.import_module("app.api.v2.routers.platform_sync")
sys.modules[__name__] = _module
