"""
Message Analyzer
Analyzes message-specific corruption patterns.
"""

import re
import logging
from .base import BaseAnalyzer
from .field_analyzer import FieldAnalyzer
from .temporal_analyzer import TemporalAnalyzer
from .encoding_analyzer import EncodingAnalyzer
from ..types import CorruptionType

logger = logging.getLogger(__name__)


class MessageAnalyzer(BaseAnalyzer):
    """Analyzes message data for corruption"""

    def __init__(self):
        super().__init__()
        self.field_analyzer = FieldAnalyzer()
        self.temporal_analyzer = TemporalAnalyzer()
        self.encoding_analyzer = EncodingAnalyzer()

    async def analyze(self, message) -> list:
        """Analyze message for corruption patterns"""
        try:
            # Analyze content corruption
            await self._analyze_content(message)

            # Analyze metadata corruption
            if hasattr(message, "message_metadata") and message.message_metadata:
                await self.field_analyzer.analyze_metadata(
                    message.message_metadata, "message.metadata", message.id
                )

            # Analyze temporal consistency
            await self.temporal_analyzer.analyze_message_temporal(message)

            # Analyze encoding issues
            if message.content:
                await self.encoding_analyzer.check_encoding(
                    message.content, "message.content", message.id
                )

            # Collect all patterns
            all_patterns = (
                self.corruption_patterns
                + self.field_analyzer.corruption_patterns
                + self.temporal_analyzer.corruption_patterns
                + self.encoding_analyzer.corruption_patterns
            )

            return all_patterns

        except Exception as e:
            logger.error(f"Message analysis failed for message {message.id}: {e}")
            return []

    async def _analyze_content(self, message) -> None:
        """Analyze message content for corruption patterns"""
        try:
            if not message.content:
                return

            content = message.content

            # Check for binary data in text content
            if re.search(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\xFF]", content):
                self._add_pattern(
                    type=CorruptionType.CONTENT_CORRUPTION,
                    field="message.content",
                    pattern="binary_data_in_text",
                    severity="high",
                    description="Binary data found in text content",
                    detection_method="binary_detection",
                    examples=[f"Message {message.id}: Contains binary data"],
                    confidence=0.9,
                )

            # Check for extremely long messages
            if len(content) > 10000:
                self._add_pattern(
                    type=CorruptionType.CONTENT_CORRUPTION,
                    field="message.content",
                    pattern="excessive_message_length",
                    severity="medium",
                    description="Message content is excessively long",
                    detection_method="length_validation",
                    examples=[
                        f"Message {message.id}: Length {len(content)} characters"
                    ],
                    confidence=0.7,
                )

            # Check for message content that's only whitespace
            if content.strip() == "":
                self._add_pattern(
                    type=CorruptionType.CONTENT_CORRUPTION,
                    field="message.content",
                    pattern="empty_message_content",
                    severity="low",
                    description="Message content is empty or only whitespace",
                    detection_method="content_validation",
                    examples=[f"Message {message.id}: Empty content"],
                    confidence=0.8,
                )

        except Exception as e:
            logger.error(
                f"Message content analysis failed for message {message.id}: {e}"
            )
