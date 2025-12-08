"""
Database base compatibility layer - imports from the actual location.
This ensures backwards compatibility for tests and imports expecting app.db.base.
"""
from app.models.base import Base

__all__ = ['Base']
