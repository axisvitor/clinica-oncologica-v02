"""
Data integrity types, enums, and dataclasses.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class CorruptionType(Enum):
    """Types of data corruption."""
    INVALID_STATE = "invalid_state"
    MISSING_REFERENCES = "missing_references"
    INCONSISTENT_DATES = "inconsistent_dates"
    DUPLICATE_RECORDS = "duplicate_records"
    ORPHANED_DATA = "orphaned_data"
    INVALID_TRANSITIONS = "invalid_transitions"
    CORRUPTED_JSON = "corrupted_json"


class CorruptionSeverity(Enum):
    """Severity levels for data corruption."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CorruptionIssue:
    """Represents a data corruption issue."""
    id: str
    corruption_type: CorruptionType
    severity: CorruptionSeverity
    description: str
    affected_records: list[dict[str, Any]]
    suggested_fix: str
    auto_fixable: bool
    detected_at: datetime = field(default_factory=datetime.utcnow)
    fixed: bool = False
    fixed_at: Optional[datetime] = None


@dataclass
class IntegrityCheckResult:
    """Result of data integrity check."""
    total_records_checked: int
    issues_found: list[CorruptionIssue]
    corruption_score: float  # 0-100, higher is worse
    recommendations: list[str]
    check_duration_seconds: float
    checked_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CorrectionResult:
    """Result of data correction operation."""
    issue_id: str
    success: bool
    records_affected: int
    backup_created: bool
    correction_details: dict[str, Any]
    error_message: Optional[str] = None
    corrected_at: datetime = field(default_factory=datetime.utcnow)
