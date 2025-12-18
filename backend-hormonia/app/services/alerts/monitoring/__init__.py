"""
Alert monitoring submodule.

Provides infrastructure health monitoring and database
monitoring integration for the alert system.
"""

from .database_monitor import (
    DatabaseMonitor,
    get_database_monitor,
    set_database_monitor,
    start_monitoring,
)

__all__ = [
    "DatabaseMonitor",
    "get_database_monitor",
    "set_database_monitor",
    "start_monitoring",
]
