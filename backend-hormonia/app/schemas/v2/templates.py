"""
Template schemas for API v2
Enhanced template models for flow templates, quiz templates, and version management.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from uuid import UUID

from .common import CursorPaginatedResponse


# ==================== Flow Template Schemas ====================


class FlowTemplateV2Base(BaseModel):
    """Base schema for flow templates."""

    template_name: str = Field(
        ..., min_length=1, max_length=255, description="Template name"
    )
    description: Optional[str] = Field(None, description="Template description")
    steps: Dict[str, Any] = Field(
        ..., description="Template steps/messages configuration"
    )
    metadata: Optional[Dict[str, Any]] = Field(None, description="Template metadata")
    is_active: Optional[bool] = Field(None, description="Active status")
    is_draft: Optional[bool] = Field(None, description="Draft status")


class FlowTemplateV2Create(FlowTemplateV2Base):
    """Schema for creating a flow template."""

    flow_kind_id: Optional[UUID] = Field(None, description="Existing flow kind ID")
    kind_key: Optional[str] = Field(
        None, max_length=100, description="Flow kind key (for new kinds)"
    )
    display_name: Optional[str] = Field(
        None, max_length=255, description="Display name (for new kinds)"
    )
    version_number: int = Field(..., ge=1, description="Version number")

    @field_validator("flow_kind_id", "kind_key")
    @classmethod
    def validate_kind_reference(cls, v, info):
        """Ensure either flow_kind_id or kind_key is provided."""
        if info.data.get("flow_kind_id") is None and v is None:
            raise ValueError("Either flow_kind_id or kind_key must be provided")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "kind_key": "hormonal_treatment",
                "display_name": "Hormonal Treatment Flow",
                "version_number": 1,
                "template_name": "Standard Hormonal Treatment v1",
                "description": "Standard flow for hormonal treatment patients",
                "steps": {
                    "day_1": {"message": "Welcome message", "type": "greeting"},
                    "day_7": {"message": "Week 1 check-in", "type": "check_in"},
                },
                "metadata": {"duration_days": 90, "author": "Dr. Silva"},
                "is_active": True,
                "is_draft": False,
            }
        }
    )


class FlowTemplateV2Update(BaseModel):
    """Schema for updating a flow template."""

    template_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    steps: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    is_draft: Optional[bool] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "template_name": "Updated Template Name",
                "description": "Updated description",
                "is_active": True,
            }
        }
    )


class FlowTemplateV2Duplicate(BaseModel):
    """Schema for duplicating a flow template."""

    new_version_number: int = Field(..., ge=1, description="New version number")
    new_template_name: Optional[str] = Field(
        None, max_length=255, description="New template name"
    )
    description: Optional[str] = Field(None, description="Description for new version")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "new_version_number": 2,
                "new_template_name": "Hormonal Treatment v2",
                "description": "Enhanced version with additional checkpoints",
            }
        }
    )


class FlowTemplateV2Response(BaseModel):
    """Full flow template response."""

    id: str
    flow_kind_id: str
    kind_key: Optional[str] = None
    display_name: Optional[str] = None
    version_number: int
    template_name: str
    description: Optional[str] = None
    steps: Dict[str, Any]
    metadata: Dict[str, Any]
    is_active: bool
    is_draft: bool
    published_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "flow_kind_id": "223e4567-e89b-12d3-a456-426614174001",
                "kind_key": "hormonal_treatment",
                "display_name": "Hormonal Treatment Flow",
                "version_number": 1,
                "template_name": "Standard Hormonal Treatment v1",
                "description": "Standard flow for hormonal treatment patients",
                "steps": {"day_1": {"message": "Welcome", "type": "greeting"}},
                "metadata": {"duration_days": 90},
                "is_active": True,
                "is_draft": False,
                "published_at": "2025-01-01T10:00:00Z",
                "created_at": "2025-01-01T09:00:00Z",
                "updated_at": "2025-01-15T14:30:00Z",
                "created_by": "323e4567-e89b-12d3-a456-426614174002",
            }
        }
    )


class FlowTemplateV2List(CursorPaginatedResponse[FlowTemplateV2Response]):
    """Paginated list of flow templates."""

    pass


# ==================== Quiz Template Schemas ====================


class QuizQuestionSchema(BaseModel):
    """Schema for quiz question."""

    id: str = Field(..., description="Question ID")
    text: str = Field(..., description="Question text")
    type: str = Field(
        ..., description="Question type (multiple_choice, open_text, scale, etc.)"
    )
    options: Optional[List[str]] = Field(None, description="Answer options")
    correct_answer: Optional[str] = Field(
        None, description="Correct answer (for graded quizzes)"
    )
    points: Optional[int] = Field(None, ge=0, description="Points for this question")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "q1",
                "text": "How are you feeling today?",
                "type": "multiple_choice",
                "options": ["Great", "Good", "Fair", "Poor"],
                "points": 10,
            }
        }
    )


class QuizTemplateV2Base(BaseModel):
    """Base schema for quiz templates."""

    name: str = Field(..., min_length=1, max_length=255, description="Quiz name")
    version: str = Field(..., min_length=1, max_length=50, description="Quiz version")
    description: Optional[str] = Field(None, description="Quiz description")
    category: Optional[str] = Field(None, max_length=100, description="Quiz category")
    tags: Optional[List[str]] = Field(None, description="Quiz tags")
    passing_score: Optional[int] = Field(
        None, ge=0, le=100, description="Passing score percentage"
    )
    time_limit_minutes: Optional[int] = Field(
        None, ge=1, description="Time limit in minutes"
    )
    randomize_questions: Optional[bool] = Field(
        None, description="Randomize question order"
    )
    is_active: Optional[bool] = Field(None, description="Active status")


class QuizTemplateV2Create(QuizTemplateV2Base):
    """Schema for creating a quiz template."""

    questions: List[Dict[str, Any]] = Field(
        ..., min_length=1, description="Quiz questions"
    )

    @field_validator("questions")
    @classmethod
    def validate_questions(cls, v):
        """Ensure questions is not empty."""
        if not v or len(v) == 0:
            raise ValueError("Quiz must have at least one question")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Weekly Health Check",
                "version": "1.0",
                "description": "Standard weekly health assessment",
                "category": "health_check",
                "tags": ["weekly", "health", "assessment"],
                "questions": [
                    {
                        "id": "q1",
                        "text": "How are you feeling?",
                        "type": "multiple_choice",
                        "options": ["Great", "Good", "Fair", "Poor"],
                    }
                ],
                "passing_score": 70,
                "time_limit_minutes": 15,
                "randomize_questions": False,
                "is_active": True,
            }
        }
    )


class QuizTemplateV2Update(BaseModel):
    """Schema for updating a quiz template."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    version: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    questions: Optional[List[Dict[str, Any]]] = None
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None
    passing_score: Optional[int] = Field(None, ge=0, le=100)
    time_limit_minutes: Optional[int] = Field(None, ge=1)
    randomize_questions: Optional[bool] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "description": "Updated description",
                "passing_score": 75,
                "is_active": True,
            }
        }
    )


class QuizTemplateV2Duplicate(BaseModel):
    """Schema for duplicating a quiz template."""

    new_name: Optional[str] = Field(None, max_length=255, description="New quiz name")
    new_version: str = Field(
        ..., min_length=1, max_length=50, description="New version"
    )
    description: Optional[str] = Field(None, description="Description for new version")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "new_version": "2.0",
                "description": "Enhanced version with additional questions",
            }
        }
    )


class QuizTemplateV2Response(BaseModel):
    """Full quiz template response."""

    id: str
    name: str
    version: str
    description: Optional[str] = None
    questions: List[Dict[str, Any]]
    category: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    passing_score: Optional[int] = None
    time_limit_minutes: Optional[int] = None
    randomize_questions: Optional[bool] = None
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Weekly Health Check",
                "version": "1.0",
                "description": "Standard weekly health assessment",
                "questions": [
                    {
                        "id": "q1",
                        "text": "How are you feeling?",
                        "type": "multiple_choice",
                        "options": ["Great", "Good", "Fair", "Poor"],
                    }
                ],
                "category": "health_check",
                "tags": ["weekly", "health"],
                "passing_score": 70,
                "time_limit_minutes": 15,
                "randomize_questions": False,
                "is_active": True,
                "created_at": "2025-01-01T10:00:00Z",
                "updated_at": "2025-01-15T14:30:00Z",
            }
        }
    )


class QuizTemplateV2List(CursorPaginatedResponse[QuizTemplateV2Response]):
    """Paginated list of quiz templates."""

    pass


# ==================== Flow Kind Schemas ====================


class FlowKindV2Base(BaseModel):
    """Base schema for flow kinds."""

    kind_key: str = Field(
        ..., min_length=1, max_length=100, description="Unique kind key"
    )
    display_name: str = Field(
        ..., min_length=1, max_length=255, description="Display name"
    )
    description: Optional[str] = Field(None, description="Kind description")
    is_active: Optional[bool] = Field(None, description="Active status")


class FlowKindV2Create(FlowKindV2Base):
    """Schema for creating a flow kind."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "kind_key": "hormonal_treatment",
                "display_name": "Hormonal Treatment Flow",
                "description": "Flow for patients undergoing hormonal treatment",
                "is_active": True,
            }
        }
    )


class FlowKindV2Update(BaseModel):
    """Schema for updating a flow kind."""

    display_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"display_name": "Updated Display Name", "is_active": True}
        }
    )


class FlowKindV2Response(BaseModel):
    """Full flow kind response with optional version statistics."""

    id: str
    kind_key: str
    display_name: str
    description: Optional[str] = None
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # Optional version statistics
    total_versions: Optional[int] = Field(None, description="Total version count")
    published_versions: Optional[int] = Field(
        None, description="Published version count"
    )
    draft_versions: Optional[int] = Field(None, description="Draft version count")
    active_version: Optional[str] = Field(None, description="Active version ID")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "kind_key": "hormonal_treatment",
                "display_name": "Hormonal Treatment Flow",
                "description": "Flow for hormonal treatment patients",
                "is_active": True,
                "created_at": "2025-01-01T10:00:00Z",
                "updated_at": "2025-01-15T14:30:00Z",
                "total_versions": 5,
                "published_versions": 3,
                "draft_versions": 2,
                "active_version": "223e4567-e89b-12d3-a456-426614174001",
            }
        }
    )


class FlowKindV2List(BaseModel):
    """List of flow kinds."""

    data: List[FlowKindV2Response]
    total: int

    model_config = ConfigDict(json_schema_extra={"example": {"data": [], "total": 10}})


# ==================== Version Management Schemas ====================


class TemplateVersionV2Create(BaseModel):
    """Schema for creating a new template version."""

    version_number: int = Field(..., ge=1, description="Version number")
    description: Optional[str] = Field(None, description="Version description")
    based_on_version_id: Optional[UUID] = Field(
        None, description="Base version to copy from"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version_number": 2,
                "description": "Enhanced version with new features",
                "based_on_version_id": "123e4567-e89b-12d3-a456-426614174000",
            }
        }
    )


class TemplateVersionV2Response(FlowTemplateV2Response):
    """Template version response (extends flow template response)."""

    changelog: Optional[str] = Field(None, description="Version changelog")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "version_number": 2,
                "changelog": "Added new checkpoints at days 15 and 30",
            }
        }
    )


class TemplateVersionV2List(BaseModel):
    """List of template versions."""

    data: List[FlowTemplateV2Response]
    kind_key: Optional[str] = None
    total: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"data": [], "kind_key": "hormonal_treatment", "total": 5}
        }
    )


class TemplateVersionCompareChange(BaseModel):
    """Single change in version comparison."""

    type: str = Field(..., description="Change type (added, removed, modified)")
    content: str = Field(..., description="Changed content")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"type": "added", "content": "New step added at day 15"}
        }
    )


class TemplateVersionCompareResponse(BaseModel):
    """Version comparison response."""

    version1: FlowTemplateV2Response
    version2: FlowTemplateV2Response
    diff: str = Field(..., description="Unified diff format")
    changes: List[Dict[str, str]] = Field(..., description="List of changes")
    total_changes: int = Field(..., description="Total number of changes")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version1": {"id": "v1", "version_number": 1},
                "version2": {"id": "v2", "version_number": 2},
                "diff": "--- version1\n+++ version2\n...",
                "changes": [{"type": "added", "content": "New step"}],
                "total_changes": 1,
            }
        }
    )


class TemplateVersionHistoryResponse(BaseModel):
    """Version history response."""

    versions: List[FlowTemplateV2Response]
    kind_key: str
    total_versions: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "versions": [],
                "kind_key": "hormonal_treatment",
                "total_versions": 5,
            }
        }
    )


class TemplateVersionRollbackRequest(BaseModel):
    """Request to rollback to a previous version."""

    reason: Optional[str] = Field(None, description="Reason for rollback")
    set_as_active: Optional[bool] = Field(
        False, description="Set rolled back version as active"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reason": "Reverting to previous stable version due to issues",
                "set_as_active": True,
            }
        }
    )


# ==================== Template Preview & Validation ====================


class TemplatePreviewRequest(BaseModel):
    """Request for template preview."""

    template_id: UUID = Field(..., description="Template ID to preview")
    context_data: Optional[Dict[str, Any]] = Field(
        None, description="Context data for rendering"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "template_id": "123e4567-e89b-12d3-a456-426614174000",
                "context_data": {"patient_name": "João Silva", "current_day": 7},
            }
        }
    )


class TemplatePreviewResponse(BaseModel):
    """Template preview response."""

    template_id: str
    rendered_content: Dict[str, Any] = Field(
        ..., description="Rendered template content"
    )
    variables_used: List[str] = Field(..., description="Variables used in rendering")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "template_id": "123e4567-e89b-12d3-a456-426614174000",
                "rendered_content": {"message": "Hello João Silva, welcome to day 7!"},
                "variables_used": ["patient_name", "current_day"],
            }
        }
    )


class TemplateValidationError(BaseModel):
    """Validation error details."""

    field: str = Field(..., description="Field with error")
    message: str = Field(..., description="Error message")
    severity: str = Field(..., description="Error severity (error, warning)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "field": "steps",
                "message": "Missing required field",
                "severity": "error",
            }
        }
    )


class TemplateValidationResponse(BaseModel):
    """Template validation response."""

    valid: bool = Field(..., description="Whether template is valid")
    errors: List[str] = Field(..., description="Validation errors")
    warnings: List[str] = Field(..., description="Validation warnings")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "valid": False,
                "errors": ["Missing required field: steps"],
                "warnings": ["Consider adding description field"],
            }
        }
    )


# ==================== Search & Filter ====================


class TemplateSearchFilters(BaseModel):
    """Template search filters."""

    template_type: Optional[str] = Field(None, description="Template type (flow, quiz)")
    is_active: Optional[bool] = Field(None, description="Active status")
    category: Optional[str] = Field(None, description="Category filter")
    tags: Optional[List[str]] = Field(None, description="Tags filter")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "template_type": "flow",
                "is_active": True,
                "tags": ["hormonal", "treatment"],
            }
        }
    )


class TemplateSearchResult(BaseModel):
    """Single search result."""

    type: str = Field(..., description="Template type (flow, quiz)")
    id: str = Field(..., description="Template ID")
    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    relevance_score: float = Field(
        ..., ge=0, le=1, description="Search relevance score"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "flow",
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Hormonal Treatment Flow",
                "description": "Standard flow for hormonal treatment",
                "relevance_score": 0.95,
            }
        }
    )


class TemplateSearchResponse(BaseModel):
    """Template search response."""

    query: str = Field(..., description="Search query")
    results: List[TemplateSearchResult] = Field(..., description="Search results")
    total: int = Field(..., description="Total results")

    model_config = ConfigDict(
        json_schema_extra={"example": {"query": "hormonal", "results": [], "total": 5}}
    )


# ==================== Import/Export ====================


class TemplateExportFormat(BaseModel):
    """Template export format specification."""

    format: str = Field(..., description="Export format (json, yaml)")
    include_metadata: bool = Field(True, description="Include metadata")
    include_history: bool = Field(False, description="Include version history")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "format": "json",
                "include_metadata": True,
                "include_history": False,
            }
        }
    )


class TemplateExportResponse(BaseModel):
    """Template export response."""

    template_id: str
    template_type: str
    export_data: Dict[str, Any] = Field(..., description="Exported template data")
    export_format: str
    exported_at: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "template_id": "123e4567-e89b-12d3-a456-426614174000",
                "template_type": "flow",
                "export_data": {},
                "export_format": "json",
                "exported_at": "2025-01-17T15:00:00Z",
            }
        }
    )


class TemplateImportRequest(BaseModel):
    """Template import request."""

    template_type: str = Field(..., description="Template type (flow, quiz)")
    import_data: Dict[str, Any] = Field(..., description="Template data to import")
    import_format: str = Field("json", description="Import format (json, yaml)")
    merge_strategy: str = Field(
        "create_new", description="Merge strategy (create_new, overwrite, merge)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "template_type": "flow",
                "import_data": {},
                "import_format": "json",
                "merge_strategy": "create_new",
            }
        }
    )


class TemplateImportResponse(BaseModel):
    """Template import response."""

    success: bool
    template_id: Optional[str] = None
    message: str
    warnings: Optional[List[str]] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "template_id": "123e4567-e89b-12d3-a456-426614174000",
                "message": "Template imported successfully",
                "warnings": [],
            }
        }
    )
