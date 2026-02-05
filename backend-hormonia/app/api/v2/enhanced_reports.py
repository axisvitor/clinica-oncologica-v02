"""Compatibility alias for legacy app.api.v2.enhanced_reports imports."""
import importlib
import sys

_module = importlib.import_module("app.api.v2.routers.enhanced_reports")
sys.modules[__name__] = _module
