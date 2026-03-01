"""
Data models for the template loader package.

Contains enums, dataclasses, and data structures used across the
template loading system.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class MessageType(str, Enum):
    """Message types supported in flow templates."""

    TEXT = "text"
    INTERACTIVE = "interactive"
    QUIZ_TRIGGER = "quiz_trigger"
    MEDIA = "media"


class InteractiveType(str, Enum):
    """Interactive element types."""

    BUTTONS = "buttons"
    LIST = "list"
    QUICK_REPLY = "quick_reply"


@dataclass
class InteractiveElements:
    """Interactive elements for messages."""

    type: InteractiveType
    options: List[Dict[str, Any]] = field(default_factory=list)
    header: Optional[str] = None
    footer: Optional[str] = None


@dataclass
class FlowStepCondition:
    """Flow step condition definition."""

    type: str
    field: str
    operator: str
    value: Any


@dataclass
class FlowStep:
    """Flow step definition."""

    id: int
    name: str
    type: str  # "message", "quiz", etc.
    content: str
    delay_hours: int = 0
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    next_step: Optional[int] = None
    quiz_template: Optional[str] = None


@dataclass
class Condition:
    """Flow condition definition."""

    type: str  # quiz_response, time_based, patient_data
    field: str
    operator: str  # equals, not_equals, greater_than, less_than, contains
    value: Any
    logical_operator: Optional[str] = None  # and, or (for chaining conditions)


@dataclass
class MessageTemplate:
    """Enhanced message template with AI optimization support."""

    day: int
    intent: str
    base_content: str
    message_type: MessageType = MessageType.TEXT
    core_elements: Dict[str, bool] = field(default_factory=dict)
    personalization_hints: List[str] = field(default_factory=list)
    ai_instructions: Optional[str] = None
    interactive_elements: Optional[InteractiveElements] = None
    conditions: List[Condition] = field(default_factory=list)
    follow_up: Optional[Dict[str, Any]] = None
    variations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "day": self.day,
            "intent": self.intent,
            "base_content": self.base_content,
            "message_type": self.message_type.value,
            "core_elements": self.core_elements,
            "personalization_hints": self.personalization_hints,
            "ai_instructions": self.ai_instructions,
            "interactive_elements": self.interactive_elements.__dict__
            if self.interactive_elements
            else None,
            "conditions": [
                {
                    "type": c.type,
                    "field": c.field,
                    "operator": c.operator,
                    "value": c.value,
                    "logical_operator": c.logical_operator,
                }
                for c in self.conditions
            ],
            "follow_up": self.follow_up,
            "variations": self.variations,
        }


@dataclass
class FlowTemplateData:
    """Enhanced flow template data structure."""

    flow_type: str
    name: str
    description: str
    version: str = "1.0.0"
    humanization_level: str = "high"  # high, medium, low
    messages: Dict[int, MessageTemplate] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def steps(self) -> List[FlowStep]:
        """
        Convert messages to FlowStep objects for StateMachine compatibility.
        Creates a sequential chain of steps with proper next_step references.
        """
        flow_steps = []
        sorted_days = sorted(self.messages.keys())

        for idx, day in enumerate(sorted_days):
            msg = self.messages[day]

            # Determine next step (next day in sequence, or None if last)
            next_step = sorted_days[idx + 1] if idx + 1 < len(sorted_days) else None

            # Calculate delay based on day difference from previous
            delay_hours = 0
            if idx > 0:
                prev_day = sorted_days[idx - 1]
                delay_hours = (day - prev_day) * 24

            step = FlowStep(
                id=day,
                name=f"day_{day}",
                type="message",
                content=msg.base_content,
                delay_hours=delay_hours,
                conditions=[c.__dict__ for c in msg.conditions]
                if msg.conditions
                else [],
                next_step=next_step,
                quiz_template=None,
            )
            flow_steps.append(step)

        return flow_steps

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "flow_type": self.flow_type,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "humanization_level": self.humanization_level,
            "messages": {str(k): v.to_dict() for k, v in self.messages.items()},
            "metadata": self.metadata,
        }
