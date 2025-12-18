"""
Field Analyzer
Analyzes text fields for various corruption patterns.
"""

import re
import json
import logging
from typing import Any, Dict
from .base import BaseAnalyzer
from ..types import CorruptionType

logger = logging.getLogger(__name__)


class FieldAnalyzer(BaseAnalyzer):
    """Analyzes text and metadata fields for corruption"""

    async def analyze(self, data: Any) -> list:
        """Not used - use specific methods instead"""
        return self.corruption_patterns

    async def analyze_text_field(
        self, text: str, field_name: str, entity_id: Any
    ) -> None:
        """Analyze text field for corruption patterns"""
        try:
            if not text:
                return

            # Check for encoding corruption
            try:
                text.encode("utf-8").decode("utf-8")
            except UnicodeError:
                self._add_pattern(
                    type=CorruptionType.ENCODING_CORRUPTION,
                    field=field_name,
                    pattern="unicode_error",
                    severity="high",
                    description=f"Unicode encoding error in {field_name}",
                    detection_method="encoding_validation",
                    examples=[f"Entity {entity_id}: {text[:50]}..."],
                    confidence=0.9,
                )

            # Check for control characters
            control_chars = [
                c for c in text if ord(c) < 32 and c not in ["\n", "\r", "\t"]
            ]
            if control_chars:
                self._add_pattern(
                    type=CorruptionType.CONTENT_CORRUPTION,
                    field=field_name,
                    pattern="control_characters",
                    severity="medium",
                    description=f"Control characters found in {field_name}",
                    detection_method="character_analysis",
                    examples=[
                        f"Entity {entity_id}: Contains {len(control_chars)} control chars"
                    ],
                    confidence=0.8,
                )

            # Check for unusual character patterns
            if re.search(r"[^\w\s\-.,!?@]", text):
                unusual_chars = re.findall(r"[^\w\s\-.,!?@]", text)
                if len(unusual_chars) > 3:
                    self._add_pattern(
                        type=CorruptionType.CONTENT_CORRUPTION,
                        field=field_name,
                        pattern="unusual_characters",
                        severity="low",
                        description=f"Unusual character patterns in {field_name}",
                        detection_method="pattern_analysis",
                        examples=[f"Entity {entity_id}: {unusual_chars[:5]}"],
                        confidence=0.6,
                    )

            # Check for repeated character patterns
            if re.search(r"(.)\1{10,}", text):
                self._add_pattern(
                    type=CorruptionType.CONTENT_CORRUPTION,
                    field=field_name,
                    pattern="repeated_characters",
                    severity="high",
                    description=f"Repeated character patterns in {field_name}",
                    detection_method="repetition_analysis",
                    examples=[f"Entity {entity_id}: {text[:100]}..."],
                    confidence=0.9,
                )

        except Exception as e:
            logger.error(f"Text field analysis failed for {field_name}: {e}")

    async def analyze_metadata(
        self, metadata: Dict, field_name: str, entity_id: Any
    ) -> None:
        """Analyze metadata/JSON field for corruption patterns"""
        try:
            # Try to serialize/deserialize
            try:
                json_str = json.dumps(metadata)
                json.loads(json_str)
            except (TypeError, ValueError) as e:
                self._add_pattern(
                    type=CorruptionType.METADATA_CORRUPTION,
                    field=field_name,
                    pattern="json_serialization_error",
                    severity="high",
                    description=f"JSON serialization error in {field_name}",
                    detection_method="json_validation",
                    examples=[f"Entity {entity_id}: {str(e)}"],
                    confidence=0.9,
                )

            # Check for suspicious nested structures
            def count_nesting_depth(obj, depth=0):
                if isinstance(obj, dict):
                    if not obj:
                        return depth
                    return max(count_nesting_depth(v, depth + 1) for v in obj.values())
                elif isinstance(obj, list):
                    if not obj:
                        return depth
                    return max(count_nesting_depth(item, depth + 1) for item in obj)
                return depth

            nesting_depth = count_nesting_depth(metadata)
            if nesting_depth > 10:
                self._add_pattern(
                    type=CorruptionType.METADATA_CORRUPTION,
                    field=field_name,
                    pattern="excessive_nesting",
                    severity="medium",
                    description="Excessive nesting depth in metadata",
                    detection_method="structure_analysis",
                    examples=[f"Entity {entity_id}: Depth {nesting_depth}"],
                    confidence=0.7,
                )

            # Check for circular references
            try:
                json.dumps(metadata)
            except ValueError as e:
                if "circular" in str(e).lower():
                    self._add_pattern(
                        type=CorruptionType.METADATA_CORRUPTION,
                        field=field_name,
                        pattern="circular_reference",
                        severity="high",
                        description="Circular reference in metadata",
                        detection_method="circular_detection",
                        examples=[f"Entity {entity_id}: {str(e)}"],
                        confidence=0.95,
                    )

        except Exception as e:
            logger.error(f"Metadata analysis failed for {field_name}: {e}")
