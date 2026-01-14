"""Compatibility alias for legacy app.api.v2.localization imports."""
import importlib
import sys

_module = importlib.import_module("app.api.v2.routers.localization")
sys.modules[__name__] = _module
