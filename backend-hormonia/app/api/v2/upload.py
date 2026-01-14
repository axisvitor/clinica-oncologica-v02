"""Compatibility alias for legacy app.api.v2.upload imports."""
import importlib
import sys

_module = importlib.import_module("app.api.v2.routers.upload")
sys.modules[__name__] = _module
