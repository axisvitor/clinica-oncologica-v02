"""Shared AI data models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ConcernLevel(str, Enum):
    """Medical concern severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PatientContext:
    """Patient context data structure for AI operations."""
    patient_id: str
    name: str
    treatment_type: str
    treatment_day: int
    age: Optional[int] = None
    recent_responses: Optional[List[str]] = None
    medical_history: Optional[Dict[str, Any]] = None
    preferences: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Initialize mutable defaults."""
        if self.recent_responses is None:
            self.recent_responses = []
        if self.medical_history is None:
            self.medical_history = {}
        if self.preferences is None:
            self.preferences = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for AI processing."""
        return {
            "patient_id": self.patient_id,
            "name": self.name,
            "treatment_type": self.treatment_type,
            "treatment_day": self.treatment_day,
            "age": self.age,
            "recent_responses": self.recent_responses,
            "medical_history": self.medical_history,
            "preferences": self.preferences,
        }
