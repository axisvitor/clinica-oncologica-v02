"""Compatibility alias for legacy app.api.v2.templates imports."""
import importlib
import sys

_module = importlib.import_module("app.api.v2.templates_shared")
sys.modules[__name__] = _module
