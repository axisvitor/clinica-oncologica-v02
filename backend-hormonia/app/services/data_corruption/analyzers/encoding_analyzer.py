"""
Encoding Analyzer
Detects encoding corruption patterns.
"""
import re
import logging
from typing import Any
from .base import BaseAnalyzer
from ..types import CorruptionType

logger = logging.getLogger(__name__)


class EncodingAnalyzer(BaseAnalyzer):
    """Analyzes text for encoding corruption"""

    async def analyze(self, data: Any) -> list:
        """Not used - use check_encoding instead"""
        return self.corruption_patterns

    async def check_encoding(self, text: str, field_name: str, entity_id: Any) -> None:
        """Check specific text for encoding corruption patterns"""
        try:
            # Check for common encoding corruption patterns
            corruption_patterns = [
                (r'Ã¡', 'latin1_to_utf8', 'á character corruption'),
                (r'Ã©', 'latin1_to_utf8', 'é character corruption'),
                (r'Ã§', 'latin1_to_utf8', 'ç character corruption'),
                (r'â€™', 'windows1252_corruption', 'apostrophe corruption'),
                (r'â€œ', 'windows1252_corruption', 'quote corruption'),
                (r'\\x[0-9a-fA-F]{2}', 'hex_escape_corruption', 'hex escape sequences'),
                (r'\\u[0-9a-fA-F]{4}', 'unicode_escape_corruption', 'unicode escape sequences'),
            ]

            for pattern, corruption_type, description in corruption_patterns:
                if re.search(pattern, text):
                    self._add_pattern(
                        type=CorruptionType.ENCODING_CORRUPTION,
                        field=field_name,
                        pattern=corruption_type,
                        severity="medium",
                        description=f"Encoding corruption: {description}",
                        detection_method="pattern_matching",
                        examples=[f"Entity {entity_id}: {text[:100]}..."],
                        confidence=0.8
                    )

        except Exception as e:
            logger.error(f"Encoding corruption check failed: {e}")
