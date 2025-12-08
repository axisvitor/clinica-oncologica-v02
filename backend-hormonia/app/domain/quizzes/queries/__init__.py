"""Query submodule for quiz link status and history."""

from .status import StatusQuery
from .history import HistoryQuery

__all__ = ["StatusQuery", "HistoryQuery"]
