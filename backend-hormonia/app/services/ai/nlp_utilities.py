"""
Lightweight NLP utilities used by legacy services and baseline tests.
"""
import re
from typing import Any, List


class NLPUtilities:
    """Utility helpers for keyword extraction and basic NLP heuristics."""

    _stop_words = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "to",
        "of",
        "in",
        "on",
        "for",
        "with",
        "am",
        "is",
        "are",
        "was",
        "were",
        "be",
        "feeling",
        "feels",
    }

    @classmethod
    def extract_keywords(cls, text: str, min_length: int = 3) -> List[str]:
        """
        Extract simple keywords from text by removing stop words and short tokens.

        Args:
            text: Input sentence or paragraph.
            min_length: Minimum token length to be considered a keyword.

        Returns:
            List of keyword strings.
        """
        if not text:
            return []

        tokens = re.findall(r"[\\w']+", text.lower())
        keywords = [
            token
            for token in tokens
            if len(token) >= min_length and token not in cls._stop_words
        ]
        return keywords


__all__ = ["NLPUtilities"]
