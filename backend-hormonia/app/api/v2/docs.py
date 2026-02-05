"""Compatibility alias for legacy app.api.v2.docs imports."""
import importlib
import sys

_module = importlib.import_module("app.api.v2.routers.docs.cache_utils")
sys.modules[__name__] = _module
