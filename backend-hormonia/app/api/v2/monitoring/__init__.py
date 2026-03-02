"""Monitoring endpoints package."""

from .whatsapp import router as whatsapp_monitoring_router
from .wuzapi import router as wuzapi_monitoring_router

__all__ = ["whatsapp_monitoring_router", "wuzapi_monitoring_router"]
