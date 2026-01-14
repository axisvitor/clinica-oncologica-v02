"""Compatibility alias for legacy app.api.v2.webhooks imports."""
import importlib
import sys

_module = importlib.import_module("app.api.v2.routers.webhooks")
sys.modules[__name__] = _module
