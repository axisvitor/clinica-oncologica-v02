"""
Data Corruption Types and Models
Defines enums and dataclasses for corruption detection.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List


class CorruptionType(Enum):
    """Types of data corruption that can be detected"""

    ENCODING_CORRUPTION = "encoding_corruption"
    FORMAT_CORRUPTION = "format_corruption"
    RELATIONSHIP_CORRUPTION = "relationship_corruption"
    TEMPORAL_CORRUPTION = "temporal_corruption"
    CONTENT_CORRUPTION = "content_corruption"
    METADATA_CORRUPTION = "metadata_corruption"
    REFERENTIAL_CORRUPTION = "referential_corruption"


@dataclass
class CorruptionPattern:
    """Represents a detected corruption pattern"""

    type: CorruptionType
    field: str
    pattern: str
    severity: str  # low, medium, high, critical
    description: str
    detection_method: str
    examples: List[str]
    confidence: float  # 0.0 to 1.0
