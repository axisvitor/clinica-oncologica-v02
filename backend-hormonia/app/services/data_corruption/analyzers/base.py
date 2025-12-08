"""
Base Analyzer
Abstract base class for all analyzers following Strategy Pattern.
"""
from abc import ABC, abstractmethod
from typing import List, Any
from ..types import CorruptionPattern


class BaseAnalyzer(ABC):
    """Abstract base class for corruption analyzers"""

    def __init__(self):
        self.corruption_patterns: List[CorruptionPattern] = []

    @abstractmethod
    async def analyze(self, data: Any) -> List[CorruptionPattern]:
        """
        Analyze data for corruption patterns.

        Args:
            data: Data to analyze

        Returns:
            List of detected corruption patterns
        """
        pass

    def _add_pattern(self, **kwargs) -> None:
        """Add corruption pattern to list"""
        pattern = CorruptionPattern(**kwargs)
        self.corruption_patterns.append(pattern)

    def clear_patterns(self) -> None:
        """Clear accumulated patterns"""
        self.corruption_patterns = []
