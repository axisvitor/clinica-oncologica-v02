"""
Pydantic schemas for template management (flows and quizzes).
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ConfigDict


# ==================== Flow Template Schemas ====================

class FlowTemplateStepBase(BaseModel):
    """Base schema for flow template step (message)."""
    intent: str = Field(..., description="Message intent/purpose")
    ai_instructions: Optional[str] = Field(None, description="AI instructions for message generation")
    personalization_hints: Optional[List[str]] = Field(default_factory=list, description="Personalization hints")
    interactive_elements: Optional[Dict[str, Any]] = Field(None, description="Interactive elements (buttons, etc)")
    message_type: str = Field(default="text", description="Message type (text, interactive, quiz_trigger)")
    base_content: Optional[str] = Field(None, description="Base message content")


class FlowTemplateMetadata(BaseModel):
    """Flow template metadata."""
    flow_type: str = Field(..., description="Flow type identifier")
    humanization_level: str = Field(default="high", description="Humanization level (high, medium, low)")
    version: str = Field(..., description="Template version")
    full_template: Optional[Dict[str, Any]] = Field(None, description="Complete original template data")


class FlowTemplateCreate(BaseModel):
    """Schema for creating a new flow template."""
    flow_kind_id: Optional[UUID] = Field(None, description="Existing flow kind ID (or create new)")
    kind_key: Optional[str] = Field(None, description="Flow kind key (if creating new)")
    display_name: str = Field(..., description="Template display name")
    description: Optional[str] = Field(None, description="Template description")
    version_number: int = Field(default=1, description="Version number")
    steps: Dict[str, FlowTemplateStepBase] = Field(..., description="Flow steps (messages) by day number")
    metadata: Optional[FlowTemplateMetadata] = Field(None, description="Template metadata")
    is_active: bool = Field(default=True, description="Whether template is active")
    is_draft: bool = Field(default=False, description="Whether template is draft")

    @field_validator('steps')
    @classmethod
    def validate_steps(cls, v):
        if not v:
            raise ValueError("steps cannot be empty")
        return v

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "kind_key": "custom_flow",
                "display_name": "Custom Patient Flow",
                "description": "Custom engagement flow for specific patient cohort",
                "version_number": 1,
                "steps": {
                    "1": {
                        "intent": "introduction",
                        "ai_instructions": "Create welcoming message",
                        "message_type": "text"
                    }
                },
                "metadata": {
                    "flow_type": "custom_flow",
                    "humanization_level": "high",
                    "version": "1.0.0"
                }
            }
        })


class FlowTemplateUpdate(BaseModel):
    """Schema for updating a flow template."""
    template_name: Optional[str] = Field(None, description="New template name")
    description: Optional[str] = Field(None, description="New description")
    steps: Optional[Dict[str, FlowTemplateStepBase]] = Field(None, description="Updated steps")
    metadata: Optional[FlowTemplateMetadata] = Field(None, description="Updated metadata")
    is_active: Optional[bool] = Field(None, description="Update active status")
    is_draft: Optional[bool] = Field(None, description="Update draft status")


class FlowTemplateResponse(BaseModel):
    """Schema for flow template response."""
    id: UUID = Field(..., description="Template version ID")
    flow_kind_id: UUID = Field(..., description="Flow kind ID")
    kind_key: Optional[str] = Field(None, description="Flow kind key")
    display_name: Optional[str] = Field(None, description="Flow display name")
    version_number: int = Field(..., description="Version number")
    template_name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Description")
    steps: Dict[str, Any] = Field(..., description="Flow steps (messages)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Template metadata")
    is_active: bool = Field(..., description="Whether template is active")
    is_draft: bool = Field(..., description="Whether template is draft")
    published_at: Optional[datetime] = Field(None, description="Publication timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class FlowTemplateListResponse(BaseModel):
    """Schema for flow template list response."""
    items: List[FlowTemplateResponse] = Field(..., description="Flow templates")
    total: int = Field(..., description="Total count")
    page: int = Field(default=1, description="Current page")
    size: int = Field(default=20, description="Page size")
    total_pages: int = Field(..., description="Total pages")


# ==================== Quiz Template Schemas ====================

class QuizQuestionOption(BaseModel):
    """Quiz question option."""
    text: str = Field(..., description="Option text")
    value: Optional[Any] = Field(None, description="Option value")
    score: Optional[int] = Field(None, description="Option score")


class QuizQuestion(BaseModel):
    """Quiz question schema."""
    id: str = Field(..., description="Question ID")
    type: str = Field(..., description="Question type (scale, multiple_choice, open_text, yes_no)")
    text: str = Field(..., description="Question text")
    category: Optional[str] = Field(None, description="Question category")
    required: bool = Field(default=True, description="Whether question is required")
    options: Optional[List[QuizQuestionOption]] = Field(None, description="Options for multiple choice")
    validation_rules: Optional[List[Dict[str, Any]]] = Field(None, description="Validation rules")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @field_validator('type')
    @classmethod
    def validate_question_type(cls, v):
        valid_types = ['scale', 'multiple_choice', 'open_text', 'yes_no']
        if v not in valid_types:
            raise ValueError(f"type must be one of {valid_types}")
        return v


class QuizTemplateCreate(BaseModel):
    """Schema for creating a new quiz template."""
    name: str = Field(..., description="Quiz template name", min_length=1, max_length=255)
    version: str = Field(default="1.0.0", description="Quiz version")
    description: Optional[str] = Field(None, description="Quiz description")
    questions: List[QuizQuestion] = Field(..., description="Quiz questions", min_length=1)
    category: str = Field(default="general", description="Quiz category", max_length=100)
    tags: Optional[List[str]] = Field(default_factory=list, description="Quiz tags")
    passing_score: Optional[int] = Field(default=0, description="Passing score (0-100)")
    time_limit_minutes: Optional[int] = Field(default=10, description="Time limit in minutes")
    randomize_questions: bool = Field(default=False, description="Whether to randomize question order")
    is_active: bool = Field(default=True, description="Whether quiz is active")

    @field_validator('questions')
    @classmethod
    def validate_questions(cls, v):
        if not v:
            raise ValueError("questions cannot be empty")
        return v

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "name": "monthly_wellness_check",
                "version": "1.0.0",
                "description": "Monthly wellness assessment",
                "category": "wellness",
                "tags": ["monthly", "wellness", "health"],
                "time_limit_minutes": 10,
                "questions": [
                    {
                        "id": "wellbeing",
                        "type": "scale",
                        "text": "Como você está se sentindo hoje?",
                        "validation_rules": [
                            {"type": "range", "value": {"min": 1, "max": 10}}
                        ]
                    }
                ]
            }
        })


class QuizTemplateUpdate(BaseModel):
    """Schema for updating a quiz template."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    version: Optional[str] = Field(None)
    description: Optional[str] = Field(None)
    questions: Optional[List[QuizQuestion]] = Field(None, min_length=1)
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = Field(None)
    passing_score: Optional[int] = Field(None)
    time_limit_minutes: Optional[int] = Field(None)
    randomize_questions: Optional[bool] = Field(None)
    is_active: Optional[bool] = Field(None)


class QuizTemplateResponse(BaseModel):
    """Schema for quiz template response."""
    id: UUID = Field(..., description="Quiz template ID")
    name: str = Field(..., description="Quiz name")
    version: str = Field(..., description="Quiz version")
    description: Optional[str] = Field(None, description="Description")
    questions: List[Dict[str, Any]] = Field(..., description="Quiz questions")
    category: str = Field(..., description="Quiz category")
    tags: Optional[List[str]] = Field(default_factory=list, description="Quiz tags")
    passing_score: int = Field(..., description="Passing score")
    time_limit_minutes: int = Field(..., description="Time limit")
    randomize_questions: bool = Field(..., description="Randomize questions")
    is_active: bool = Field(..., description="Is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class QuizTemplateListResponse(BaseModel):
    """Schema for quiz template list response."""
    items: List[QuizTemplateResponse] = Field(..., description="Quiz templates")
    total: int = Field(..., description="Total count")
    page: int = Field(default=1, description="Current page")
    size: int = Field(default=20, description="Page size")
    total_pages: int = Field(..., description="Total pages")


# ==================== Flow Kind Schemas ====================

class FlowKindCreate(BaseModel):
    """Schema for creating a flow kind."""
    kind_key: str = Field(..., description="Unique flow kind key", min_length=1, max_length=50)
    display_name: str = Field(..., description="Display name", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="Flow kind description")
    is_active: bool = Field(default=True, description="Whether flow kind is active")


class FlowKindResponse(BaseModel):
    """Schema for flow kind response."""
    id: UUID = Field(..., description="Flow kind ID")
    kind_key: str = Field(..., description="Flow kind key")
    display_name: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="Description")
    is_active: bool = Field(..., description="Is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class FlowKindListResponse(BaseModel):
    """Schema for flow kind list response."""
    items: List[FlowKindResponse] = Field(..., description="Flow kinds")
    total: int = Field(..., description="Total count")
