"""
Config compatibility layer - imports settings from the new location.
This file ensures backwards compatibility for tests and imports.
"""
from app.config.settings import settings, Settings

__all__ = ['settings', 'Settings']
