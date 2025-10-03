"""
Pydantic schema validators for JSONB fields across the system.
Provides centralized validation for patient metadata, flow data, and quiz data.
"""
import re
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, validator, root_validator
from datetime import datetime, date
from enum import Enum


class TreatmentPhase(str, Enum):
    """Valid treatment phases."""
    INITIAL = "initial"
    MAINTENANCE = "maintenance"
    FOLLOWUP = "followup"
    COMPLETED = "completed"


class ResponseType(str, Enum):
    """Valid quiz response types."""
    MULTIPLE_CHOICE = "multiple_choice"
    SINGLE_CHOICE = "single_choice"
    OPEN_TEXT = "open_text"
    SCALE = "scale"
    BOOLEAN = "boolean"
    RATING = "rating"
    YES_NO = "yes_no"
    NUMBER = "number"
    DATE = "date"


class SentimentType(str, Enum):
    """Valid sentiment analysis types."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


# Patient Metadata Validators
class PatientMetadataValidator(BaseModel):
    """Validator for patient metadata JSONB field."""

    # Brazilian healthcare fields
    cpf: Optional[str] = Field(None, description="Brazilian CPF number")
    diagnosis: Optional[str] = Field(None, description="Patient diagnosis")
    treatment_phase: Optional[TreatmentPhase] = Field(None, description="Current treatment phase")
    doctor_name: Optional[str] = Field(None, description="Attending doctor name (cached)")

    # Additional metadata fields
    insurance_number: Optional[str] = Field(None, description="Health insurance number")
    emergency_contact: Optional[str] = Field(None, description="Emergency contact info")
    allergies: Optional[List[str]] = Field(default_factory=list, description="Known allergies")
    medications: Optional[List[str]] = Field(default_factory=list, description="Current medications")

    # System metadata
    onboarding_completed: Optional[bool] = Field(False, description="Onboarding completion status")
    last_engagement: Optional[datetime] = Field(None, description="Last patient engagement timestamp")
    preferences: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Patient preferences")

    @validator('cpf')
    def validate_cpf(cls, v):
        """Validate Brazilian CPF format."""
        if v is None:
            return v

        # Remove non-digits
        cpf_digits = re.sub(r'\D', '', v)

        # Check length
        if len(cpf_digits) != 11:
            raise ValueError("CPF must have 11 digits")

        # Check for invalid patterns (all same digits)
        if len(set(cpf_digits)) == 1:
            raise ValueError("Invalid CPF: all digits are the same")

        # CPF validation algorithm
        def calculate_digit(cpf_partial, weights):
            total = sum(int(digit) * weight for digit, weight in zip(cpf_partial, weights))
            remainder = total % 11
            return '0' if remainder < 2 else str(11 - remainder)

        # Validate first check digit
        first_digit = calculate_digit(cpf_digits[:9], range(10, 1, -1))
        if cpf_digits[9] != first_digit:
            raise ValueError("Invalid CPF: first check digit")

        # Validate second check digit
        second_digit = calculate_digit(cpf_digits[:10], range(11, 1, -1))
        if cpf_digits[10] != second_digit:
            raise ValueError("Invalid CPF: second check digit")

        # Return formatted CPF
        return f"{cpf_digits[:3]}.{cpf_digits[3:6]}.{cpf_digits[6:9]}-{cpf_digits[9:]}"

    @validator('diagnosis')
    def validate_diagnosis(cls, v):
        """Validate diagnosis field."""
        if v is not None and len(v.strip()) == 0:
            raise ValueError("Diagnosis cannot be empty string")
        return v.strip() if v else None

    @validator('doctor_name')
    def validate_doctor_name(cls, v):
        """Validate doctor name field."""
        if v is not None and len(v.strip()) == 0:
            raise ValueError("Doctor name cannot be empty string")
        return v.strip() if v else None

    @validator('emergency_contact')
    def validate_emergency_contact(cls, v):
        """Validate emergency contact format."""
        if v is None:
            return v

        # Allow phone numbers or emails
        phone_pattern = r'^\+?[\d\s\-\(\)]{10,}$'
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        if not (re.match(phone_pattern, v) or re.match(email_pattern, v)):
            raise ValueError("Emergency contact must be a valid phone number or email")

        return v.strip()


# Flow Template Data Validators
class FlowTemplateDataValidator(BaseModel):
    """Validator for flow template_data JSONB field."""

    name: str = Field(..., description="Template name")
    version: str = Field(default="1.0.0", description="Template version")
    description: Optional[str] = Field(None, description="Template description")
    duration_days: int = Field(..., gt=0, description="Flow duration in days")

    # Message templates
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="Message templates")
    conditions: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Flow conditions")

    # AI optimization
    ai_optimization: Optional[Dict[str, Any]] = Field(default_factory=dict, description="AI optimization settings")
    personalization_rules: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Personalization rules")

    @validator('name')
    def validate_name(cls, v):
        """Validate template name."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Template name cannot be empty")
        return v.strip()

    @validator('version')
    def validate_version(cls, v):
        """Validate version format (semantic versioning)."""
        version_pattern = r'^\d+\.\d+\.\d+$'
        if not re.match(version_pattern, v):
            raise ValueError("Version must follow semantic versioning (x.y.z)")
        return v

    @validator('messages')
    def validate_messages(cls, v):
        """Validate message templates structure."""
        if not isinstance(v, list):
            raise ValueError("Messages must be a list")

        for idx, message in enumerate(v):
            if not isinstance(message, dict):
                raise ValueError(f"Message {idx} must be a dictionary")

            # Required fields
            if 'id' not in message:
                raise ValueError(f"Message {idx} missing required 'id' field")
            if 'content' not in message and 'template' not in message:
                raise ValueError(f"Message {idx} missing required 'content' or 'template' field")

        return v


# Flow State Data Validators
class FlowStateDataValidator(BaseModel):
    """Validator for flow state_data JSONB field."""

    # Current state information
    current_step: int = Field(default=0, ge=0, description="Current flow step")
    completed_steps: List[int] = Field(default_factory=list, description="Completed step indices")

    # Progress tracking
    progress_percentage: Optional[float] = Field(None, ge=0, le=100, description="Flow completion percentage")
    last_interaction: Optional[datetime] = Field(None, description="Last patient interaction")

    # Step-specific data
    step_data: Dict[str, Any] = Field(default_factory=dict, description="Data for each step")
    user_responses: Dict[str, Any] = Field(default_factory=dict, description="User responses by step")

    # Flow control
    paused: bool = Field(default=False, description="Flow is paused")
    pause_reason: Optional[str] = Field(None, description="Reason for pause")
    auto_advance: bool = Field(default=True, description="Auto-advance to next step")

    # Personalization
    personalization_data: Dict[str, Any] = Field(default_factory=dict, description="Personalization metadata")
    ai_insights: Dict[str, Any] = Field(default_factory=dict, description="AI-generated insights")

    @validator('completed_steps')
    def validate_completed_steps(cls, v):
        """Validate completed steps list."""
        if not isinstance(v, list):
            raise ValueError("Completed steps must be a list")

        # Ensure all values are non-negative integers
        for step in v:
            if not isinstance(step, int) or step < 0:
                raise ValueError("All completed steps must be non-negative integers")

        # Remove duplicates and sort
        return sorted(list(set(v)))

    @validator('pause_reason')
    def validate_pause_reason(cls, v, values):
        """Validate pause reason when paused."""
        if values.get('paused') and not v:
            raise ValueError("Pause reason is required when flow is paused")
        return v


# Quiz Data Validators
class QuizQuestionValidator(BaseModel):
    """Validator for individual quiz questions."""

    id: str = Field(..., description="Question ID")
    text: str = Field(..., description="Question text")
    type: ResponseType = Field(..., description="Response type")

    # Options for choice-based questions
    options: Optional[List[Dict[str, str]]] = Field(None, description="Answer options")

    # Validation rules
    required: bool = Field(default=True, description="Question is required")
    validation: Optional[Dict[str, Any]] = Field(None, description="Validation rules")

    # Metadata
    category: Optional[str] = Field(None, description="Question category")
    weight: Optional[float] = Field(None, ge=0, description="Question weight for scoring")

    @validator('id')
    def validate_id(cls, v):
        """Validate question ID format."""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Question ID must contain only alphanumeric characters, hyphens, and underscores")
        return v

    @validator('text')
    def validate_text(cls, v):
        """Validate question text."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Question text cannot be empty")
        return v.strip()

    @validator('options')
    def validate_options(cls, v, values):
        """Validate options for choice-based questions."""
        question_type = values.get('type')

        if question_type in [ResponseType.MULTIPLE_CHOICE, ResponseType.SINGLE_CHOICE]:
            if not v or len(v) < 2:
                raise ValueError("Choice questions must have at least 2 options")

            for idx, option in enumerate(v):
                if not isinstance(option, dict):
                    raise ValueError(f"Option {idx} must be a dictionary")
                if 'value' not in option or 'label' not in option:
                    raise ValueError(f"Option {idx} must have 'value' and 'label' fields")

        return v


class QuizResponseMetadataValidator(BaseModel):
    """Validator for quiz response metadata JSONB field."""

    # Response analysis
    sentiment: Optional[SentimentType] = Field(None, description="Sentiment analysis result")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Confidence score")

    # Text analysis (for open text responses)
    entities: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Named entities extracted")
    keywords: Optional[List[str]] = Field(default_factory=list, description="Key terms identified")

    # Response quality metrics
    response_time_seconds: Optional[float] = Field(None, ge=0, description="Time taken to respond")
    word_count: Optional[int] = Field(None, ge=0, description="Word count for text responses")

    # Clinical relevance
    clinical_flags: Optional[List[str]] = Field(default_factory=list, description="Clinical attention flags")
    risk_indicators: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Risk assessment indicators")

    # Follow-up triggers
    requires_followup: bool = Field(default=False, description="Response requires follow-up")
    followup_priority: Optional[str] = Field(None, description="Follow-up priority level")

    @validator('entities')
    def validate_entities(cls, v):
        """Validate entities structure."""
        if not isinstance(v, list):
            raise ValueError("Entities must be a list")

        for idx, entity in enumerate(v):
            if not isinstance(entity, dict):
                raise ValueError(f"Entity {idx} must be a dictionary")

            required_fields = ['text', 'label', 'start', 'end']
            for field in required_fields:
                if field not in entity:
                    raise ValueError(f"Entity {idx} missing required field: {field}")

        return v

    @validator('followup_priority')
    def validate_followup_priority(cls, v, values):
        """Validate follow-up priority."""
        if v is not None:
            valid_priorities = ['low', 'medium', 'high', 'urgent']
            if v.lower() not in valid_priorities:
                raise ValueError(f"Follow-up priority must be one of: {valid_priorities}")
            return v.lower()
        return v


# Utility functions for validation
def validate_patient_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate patient metadata JSONB field.

    Args:
        data: Raw metadata dictionary

    Returns:
        Validated metadata dictionary

    Raises:
        ValidationError: If validation fails
    """
    try:
        validator = PatientMetadataValidator(**data)
        return validator.dict(exclude_unset=True)
    except Exception as e:
        raise ValueError(f"Patient metadata validation failed: {e}")


def validate_flow_template_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate flow template data JSONB field.

    Args:
        data: Raw template data dictionary

    Returns:
        Validated template data dictionary

    Raises:
        ValidationError: If validation fails
    """
    try:
        validator = FlowTemplateDataValidator(**data)
        return validator.dict(exclude_unset=True)
    except Exception as e:
        raise ValueError(f"Flow template data validation failed: {e}")


def validate_flow_state_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate flow state data JSONB field.

    Args:
        data: Raw state data dictionary

    Returns:
        Validated state data dictionary

    Raises:
        ValidationError: If validation fails
    """
    try:
        validator = FlowStateDataValidator(**data)
        return validator.dict(exclude_unset=True)
    except Exception as e:
        raise ValueError(f"Flow state data validation failed: {e}")


def validate_quiz_questions(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate quiz questions list.

    Args:
        data: Raw questions list

    Returns:
        Validated questions list

    Raises:
        ValidationError: If validation fails
    """
    try:
        validated_questions = []
        for question_data in data:
            validator = QuizQuestionValidator(**question_data)
            validated_questions.append(validator.dict(exclude_unset=True))
        return validated_questions
    except Exception as e:
        raise ValueError(f"Quiz questions validation failed: {e}")


def validate_response_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate quiz response metadata JSONB field.

    Args:
        data: Raw response metadata dictionary

    Returns:
        Validated response metadata dictionary

    Raises:
        ValidationError: If validation fails
    """
    try:
        validator = QuizResponseMetadataValidator(**data)
        return validator.dict(exclude_unset=True)
    except Exception as e:
        raise ValueError(f"Response metadata validation failed: {e}")