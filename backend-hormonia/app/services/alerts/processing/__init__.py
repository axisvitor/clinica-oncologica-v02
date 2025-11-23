from typing import Any
"""
Alert processing submodule.

Provides alert processing pipeline for validation, enrichment,
and persistence of alerts.
"""

from .processor import (
    AlertProcessor,
    get_alert_processor,
    set_alert_processor,
)

__all__ = [
    "AlertProcessor",
    "get_alert_processor",
    "set_alert_processor",
]
