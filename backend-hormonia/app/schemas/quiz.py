"""
Quiz and assessment schemas for Hormonia Backend System.
"""

from datetime import datetime
from typing import List, Optional, Any, Union, Dict
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, field_validator, ConfigDict


class QuestionType(str, Enum):
    """Types of quiz questions."""

    MULTIPLE_CHOICE = "multiple_choice"
    SINGLE_CHOICE = "single_choice"
    OPEN_TEXT = "open_text"
    SCALE = "scale"
    YES_NO = "yes_no"
    DATE = "date"
    NUMBER = "number"
    BOOLEAN = "boolean"
    RATING = "rating"


class ValidationRule(BaseModel):
    """Validation rule for quiz questions."""

    type: str = Field(
        ...,
        description="Type of validation (required, min_length, max_length, range, etc.)",
    )
    value: Union[str, int, float, bool, list, dict] = Field(
        ...,
        description="Validation value (can be primitive or dict for complex rules like range)",
    )
    message: str = Field(..., description="Error message if validation fails")


class QuestionOption(BaseModel):
    """Option for multiple choice questions."""

    id: str = Field(..., description="Unique option identifier")
    text: str = Field(..., description="Option display text")
    value: Union[str, int, float] = Field(..., description="Option value")
    is_correct: Optional[bool] = Field(
        None, description="Whether this is the correct answer (for scored quizzes)"
    )
    allow_other: bool = Field(
        False, description="Whether this option allows custom 'other' text input"
    )


class QuizQuestion(BaseModel):
    """Individual quiz question definition."""

    id: str = Field(..., description="Unique question identifier")
    type: QuestionType = Field(..., description="Question type")
    text: str = Field(..., description="Question text")
    description: Optional[str] = Field(
        None, description="Additional question description"
    )
    required: bool = Field(True, description="Whether question is required")
    options: Optional[List[QuestionOption]] = Field(
        None, description="Options for multiple choice questions"
    )
    validation_rules: Optional[List[ValidationRule]] = Field(
        None, description="Validation rules"
    )
    metadata: Optional[dict[str, Any]] = Field(
        default_factory=dict, description="Additional question metadata"
    )
    allow_other: bool = Field(
        False, description="Whether question allows 'other' option with custom text"
    )

    @field_validator("options")
    @classmethod
    def validate_options(cls, v, info):
        """Validate that choice questions have options."""
        question_type = info.data.get("type")
        if question_type in [
            QuestionType.MULTIPLE_CHOICE,
            QuestionType.SINGLE_CHOICE,
        ] and (not v or len(v) == 0):
            raise ValueError("Choice questions must have at least one option")
        return v


class QuizTemplateCreate(BaseModel):
    """Schema for creating quiz templates."""

    name: str = Field(..., min_length=1, max_length=255, description="Template name")
    version: str = Field(
        ..., min_length=1, max_length=50, description="Template version"
    )
    questions: List[QuizQuestion] = Field(
        ..., min_length=1, description="List of questions"
    )
    is_active: bool = Field(True, description="Whether template is active")

    @field_validator("questions")
    @classmethod
    def validate_questions(cls, v):
        """Validate questions have unique IDs."""
        question_ids = [q.id for q in v]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Question IDs must be unique within a template")
        return v


class QuizTemplateUpdate(BaseModel):
    """Schema for updating quiz templates."""

    name: Optional[str] = Field(
        None, min_length=1, max_length=255, description="Template name"
    )
    version: Optional[str] = Field(
        None, min_length=1, max_length=50, description="Template version"
    )
    questions: Optional[List[QuizQuestion]] = Field(
        None, min_length=1, description="List of questions"
    )
    is_active: Optional[bool] = Field(None, description="Whether template is active")

    @field_validator("questions")
    @classmethod
    def validate_questions(cls, v):
        """Validate questions have unique IDs."""
        if v is not None:
            question_ids = [q.id for q in v]
            if len(question_ids) != len(set(question_ids)):
                raise ValueError("Question IDs must be unique within a template")
        return v


class QuizTemplateResponse(BaseModel):
    """Schema for quiz template responses."""

    id: UUID = Field(..., description="Template ID")
    name: str = Field(..., description="Template name")
    version: str = Field(..., description="Template version")
    questions: List[QuizQuestion] = Field(..., description="List of questions")
    is_active: bool = Field(..., description="Whether template is active")
    category: Optional[str] = Field(None, description="Template category")
    description: Optional[str] = Field(None, description="Template description")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class QuizResponseCreate(BaseModel):
    """Schema for creating quiz responses."""

    patient_id: UUID = Field(..., description="Patient ID")
    quiz_template_id: UUID = Field(..., description="Quiz template ID")
    question_id: str = Field(..., description="Question ID")
    question_text: str = Field(..., description="Question text")
    response_type: QuestionType = Field(..., description="Response type")
    response_value: Union[str, List[str]] = Field(
        ..., description="Response value (single or list for multi-select)"
    )
    response_metadata: Optional[dict[str, Any]] = Field(
        default_factory=dict, description="Response metadata"
    )
    responded_at: datetime = Field(..., description="Response timestamp")
    other_text: Optional[str] = Field(
        None, description="Custom text for 'other' option"
    )

    @field_validator("response_value")
    @classmethod
    def validate_response_value(cls, v):
        """Validate response_value handles both single and multiple selections."""
        if isinstance(v, list):
            # Multi-select: validate each item
            if not v:  # Empty list not allowed
                raise ValueError("Multi-select requires at least one selection")
            return [str(item).strip() for item in v if item]
        else:
            # Single select
            return str(v).strip()

    @field_validator("other_text")
    @classmethod
    def validate_other_text(cls, v, info):
        """Validate other_text when 'Outra' is selected."""
        response_value = info.data.get("response_value")
        if response_value and v:
            # Check if "other" option selected
            other_aliases = ["other", "outro", "outra", "otra", "autre", "altro"]
            if isinstance(response_value, list):
                has_other = any(
                    str(val).lower().strip() in other_aliases for val in response_value
                )
            else:
                has_other = str(response_value).lower().strip() in other_aliases

            if has_other and not v.strip():
                raise ValueError("Custom text required when 'Outra' option is selected")

        # Ensure other_text is not empty if provided
        if v is not None and len(v.strip()) == 0:
            raise ValueError("other_text cannot be empty if provided")
        return v


class QuizResponseResponse(BaseModel):
    """Schema for quiz response responses."""

    id: UUID = Field(..., description="Response ID")
    patient_id: UUID = Field(..., description="Patient ID")
    quiz_template_id: UUID = Field(..., description="Quiz template ID")
    question_id: str = Field(..., description="Question ID")
    question_text: str = Field(..., description="Question text")
    response_type: str = Field(..., description="Response type")
    response_value: str = Field(..., description="Response value")
    response_metadata: dict[str, Any] = Field(..., description="Response metadata")
    responded_at: datetime = Field(..., description="Response timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    other_text: Optional[str] = Field(
        None, description="Custom text for 'other' option"
    )

    model_config = ConfigDict(from_attributes=True)


class QuizSessionCreate(BaseModel):
    """Schema for creating quiz sessions."""

    patient_id: UUID = Field(..., description="Patient ID")
    quiz_template_id: Optional[UUID] = Field(None, description="Quiz template ID")
    template_id: Optional[UUID] = Field(
        None, description="Template ID (alias for quiz_template_id)"
    )

    @field_validator("quiz_template_id", mode="before")
    @classmethod
    def set_quiz_template_id(cls, v, info):
        """Accept both 'template_id' and 'quiz_template_id' for backwards compatibility."""
        # If quiz_template_id is already set, use it
        if v is not None:
            return v
        # Otherwise, check if template_id is in info.data
        if (
            hasattr(info, "data")
            and "template_id" in info.data
            and info.data["template_id"] is not None
        ):
            return info.data["template_id"]
        # Will be validated by the required field validator
        return v

    @field_validator("quiz_template_id")
    @classmethod
    def validate_template_required(cls, v):
        """Ensure at least one template ID is provided."""
        if v is None:
            raise ValueError(
                "Either 'quiz_template_id' or 'template_id' must be provided"
            )
        return v

    model_config = ConfigDict(extra="allow")


class QuizSessionResponse(BaseModel):
    """Schema for quiz session responses."""

    id: UUID = Field(..., description="Session ID")
    patient_id: UUID = Field(..., description="Patient ID")
    quiz_template_id: UUID = Field(..., description="Quiz template ID")
    current_question_index: int = Field(..., description="Current question index")
    is_completed: bool = Field(..., description="Whether session is completed")
    started_at: datetime = Field(..., description="Session start timestamp")
    completed_at: Optional[datetime] = Field(
        None, description="Session completion timestamp"
    )

    # Enriched fields (optional, set by service layer)
    patient_name: Optional[str] = Field(None, description="Patient name")
    template_name: Optional[str] = Field(None, description="Template name")
    template_version: Optional[str] = Field(None, description="Template version")
    humanized_questions: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Humanized variations of quiz questions for patient delivery",
    )

    model_config = ConfigDict(from_attributes=True)


class QuizAnalytics(BaseModel):
    """Schema for quiz analytics."""

    quiz_template_id: UUID = Field(..., description="Quiz template ID")
    total_responses: int = Field(..., description="Total number of responses")
    completion_rate: float = Field(..., description="Completion rate percentage")
    average_completion_time: Optional[float] = Field(
        None, description="Average completion time in minutes"
    )
    question_analytics: List[dict[str, Any]] = Field(
        ..., description="Per-question analytics"
    )
    trends: dict[str, Any] = Field(..., description="Response trends over time")


class QuizValidationResult(BaseModel):
    """Schema for quiz validation results."""

    is_valid: bool = Field(..., description="Whether quiz is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")


class QuizTemplateListResponse(BaseModel):
    """Paginated quiz template response."""

    items: List[QuizTemplateResponse] = Field(..., description="List of quiz templates")
    total: int = Field(..., description="Total number of templates")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")

    # Backwards compatibility alias
    @property
    def templates(self) -> List[QuizTemplateResponse]:
        """Alias for items for backwards compatibility."""
        return self.items


class QuizResponseListResponse(BaseModel):
    """Paginated quiz response response."""

    items: List[QuizResponseResponse] = Field(..., description="List of quiz responses")
    total: int = Field(..., description="Total number of responses")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")

    # Backwards compatibility alias
    @property
    def responses(self) -> List[QuizResponseResponse]:
        """Alias for items for backwards compatibility."""
        return self.items


class QuizSessionListResponse(BaseModel):
    """Paginated quiz session response."""

    items: List[QuizSessionResponse] = Field(..., description="List of quiz sessions")
    total: int = Field(..., description="Total number of sessions")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")

    # Backwards compatibility alias
    @property
    def sessions(self) -> List[QuizSessionResponse]:
        """Alias for items for backwards compatibility."""
        return self.items


class PatientQuizAnalytics(BaseModel):
    """Patient quiz analytics response."""

    patient_id: UUID = Field(..., description="Patient ID")
    total_quizzes_completed: int = Field(
        ..., description="Total number of completed quizzes"
    )
    completion_rate: float = Field(..., description="Completion rate percentage")
    average_score: Optional[float] = Field(None, description="Average quiz score")
    recent_activity: List[dict[str, Any]] = Field(
        default_factory=list, description="Recent quiz activity"
    )
    trends: dict[str, Any] = Field(
        default_factory=dict, description="Quiz performance trends"
    )
