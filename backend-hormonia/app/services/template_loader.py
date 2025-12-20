"""
DB-only template loader with versioning support.
All templates MUST be in the database - no file system access.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta, timezone
import logging

from pydantic import BaseModel, Field

from app.models.flow import FlowTemplateVersion
from app.repositories.flow_kind import FlowKindRepository
from app.repositories.flow_template_version import FlowTemplateVersionRepository

logger = logging.getLogger(__name__)


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
            # This creates a linked chain regardless of day number gaps
            next_step = sorted_days[idx + 1] if idx + 1 < len(sorted_days) else None

            # Calculate delay based on day difference from previous
            delay_hours = 0
            if idx > 0:
                prev_day = sorted_days[idx - 1]
                delay_hours = (day - prev_day) * 24  # Convert days to hours

            # Convert MessageTemplate to FlowStep
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


class TemplateValidationError(Exception):
    """Template validation error."""

    pass


class TemplateLoadError(Exception):
    """Template loading error."""

    pass


class TemplateValidationResult(BaseModel):
    """Template validation result."""

    is_valid: bool = Field(..., description="Whether template is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    message_count: int = Field(default=0, description="Number of messages in template")
    ai_optimized_count: int = Field(
        default=0, description="Number of AI-optimized messages"
    )


class TemplateValidator:
    """Dedicated template validation logic."""

    def validate(self, template_data: FlowTemplateData) -> TemplateValidationResult:
        """Validate template data structure and content."""
        errors = []
        warnings = []
        ai_optimized_count = 0

        # Validate basic structure
        errors.extend(self._validate_basic_structure(template_data))

        # Validate messages
        message_errors, message_warnings, ai_count = self._validate_messages(
            template_data.messages
        )
        errors.extend(message_errors)
        warnings.extend(message_warnings)
        ai_optimized_count = ai_count

        # Validate AI optimization requirements
        warnings.extend(
            self._validate_ai_optimization(template_data, ai_optimized_count)
        )

        # Validate flow progression
        warnings.extend(self._validate_flow_progression(template_data.messages))

        return TemplateValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            message_count=len(template_data.messages),
            ai_optimized_count=ai_optimized_count,
        )

    def _validate_basic_structure(self, template_data: FlowTemplateData) -> List[str]:
        """Validate basic template structure."""
        errors = []
        if not template_data.flow_type:
            errors.append("flow_type is required")
        if not template_data.name:
            errors.append("name is required")
        if not template_data.messages:
            errors.append("messages dictionary is required and cannot be empty")
        return errors

    def _validate_messages(
        self, messages: Dict[int, MessageTemplate]
    ) -> tuple[List[str], List[str], int]:
        """Validate individual messages."""
        errors = []
        warnings = []
        ai_optimized_count = 0

        for day, message in messages.items():
            if not isinstance(day, int) or day < 1:
                errors.append(f"Invalid day number: {day}")

            if not message.intent:
                errors.append(f"Message for day {day} missing intent")

            if not message.base_content:
                errors.append(f"Message for day {day} missing base_content")

            # Validate message_type against allowed values to avoid DB enum mismatches
            try:
                allowed_types = {"text", "media", "quiz_trigger"}
                mt_value = (
                    message.message_type.value
                    if hasattr(message.message_type, "value")
                    else str(message.message_type)
                )
                if mt_value not in allowed_types:
                    errors.append(
                        f"Invalid message_type '{mt_value}' for day {day}. Allowed: {sorted(allowed_types)}"
                    )
            except Exception:
                errors.append(f"Invalid message_type for day {day}")

            # Check AI optimization
            if message.ai_instructions or message.personalization_hints:
                ai_optimized_count += 1

            # Validate interactive elements
            if (
                message.interactive_elements
                and not message.interactive_elements.options
            ):
                warnings.append(
                    f"Message for day {day} has interactive elements but no options"
                )

            # Validate conditions
            for condition in message.conditions:
                if not condition.type or not condition.field or not condition.operator:
                    errors.append(f"Invalid condition in message for day {day}")

        return errors, warnings, ai_optimized_count

    def _validate_ai_optimization(
        self, template_data: FlowTemplateData, ai_optimized_count: int
    ) -> List[str]:
        """Validate AI optimization requirements."""
        warnings = []
        if template_data.humanization_level == "high" and ai_optimized_count == 0:
            warnings.append(
                "High humanization level template has no AI-optimized messages"
            )
        return warnings

    def _validate_flow_progression(
        self, messages: Dict[int, MessageTemplate]
    ) -> List[str]:
        """Validate flow progression logic."""
        warnings = []
        days = sorted(messages.keys())

        if days and days[0] != 1:
            warnings.append("Flow should start with day 1")

        # Check for gaps in days
        for i in range(len(days) - 1):
            if days[i + 1] - days[i] > 7:  # More than 7 days gap
                warnings.append(
                    f"Large gap between day {days[i]} and day {days[i + 1]}"
                )

        return warnings


# Rename the class to EnhancedTemplateLoader (keeping the original name)
class EnhancedTemplateLoader:
    """
    DB-only template loader that uses the new versioning system.
    All templates MUST be in the database - no YAML fallback.
    """

    def __init__(self, db: Any, cache_ttl_hours: int = 1, max_cache_size: int = 50):
        """
        Initialize versioned template loader.

        Args:
            db: Database session
            cache_ttl_hours: Cache time-to-live in hours
            max_cache_size: Maximum number of cached templates
        """
        self.db = db

        # Repositories
        self.flow_kind_repo = FlowKindRepository(db)
        self.template_version_repo = FlowTemplateVersionRepository(db)

        # Cache management
        self._template_cache: Dict[str, tuple[FlowTemplateData, datetime]] = {}
        self._validator = TemplateValidator()
        self._cache_ttl = timedelta(hours=cache_ttl_hours)
        self._max_cache_size = max_cache_size

        logger.info("Initialized versioned template loader - DB-only mode")

    def load_flow_template(
        self, flow_type: str, version: Optional[str] = None
    ) -> FlowTemplateData:
        """
        Load flow template by type and version (DB-only).

        Args:
            flow_type: Type of flow (initial_15_days, days_16_45, monthly_recurring)
            version: Template version (defaults to current published version)

        Returns:
            FlowTemplateData: Loaded template data

        Raises:
            TemplateLoadError: If template cannot be loaded from database
        """
        cache_key = f"{flow_type}:{version or 'current'}"

        # Check cache first
        if cache_key in self._template_cache:
            cached_template, cached_time = self._template_cache[cache_key]
            if datetime.now(timezone.utc) - cached_time < self._cache_ttl:
                logger.debug(f"Loading template from cache: {cache_key}")
                return cached_template
            else:
                # Cache expired, remove it
                del self._template_cache[cache_key]
                logger.debug(f"Cache expired for template: {cache_key}")

        try:
            # Load from database only
            template_data = self._load_from_database(flow_type, version)

            if template_data:
                # Cache and return database template
                self._cache_template(cache_key, template_data)
                logger.info(
                    f"Successfully loaded template from DB: {flow_type} v{template_data.version}"
                )
                return template_data

            # No template found
            raise TemplateLoadError(f"Template {flow_type} not found in database")

        except Exception as e:
            logger.error(f"Failed to load template {flow_type}: {str(e)}")
            raise TemplateLoadError(f"Failed to load template {flow_type}: {str(e)}")

    def _load_from_database(
        self, flow_type: str, version: Optional[str] = None
    ) -> Optional[FlowTemplateData]:
        """Load template from database using versioning system."""
        try:
            # Convert string version to int if provided
            version_num = int(version) if version and version.isdigit() else None
            
            if version_num:
                # Load specific version
                template_version = (
                    self.template_version_repo.get_by_flow_type_and_version(
                        flow_type, version_num
                    )
                )
            else:
                # Load current published version
                template_version = (
                    self.template_version_repo.get_current_version_by_flow_type(
                        flow_type
                    )
                )

                # If no current version set, try latest published
                if not template_version:
                    kind = self.flow_kind_repo.get_by_kind_key(flow_type)
                    if kind:
                        template_version = (
                            self.template_version_repo.get_latest_published_by_kind(
                                kind.id
                            )
                        )

            if not template_version:
                return None

            # Convert database template to FlowTemplateData
            return self._parse_db_template_version(template_version)

        except Exception as e:
            logger.error(f"Error loading template from database: {e}")
            return None

    def get_message_for_day(
        self, flow_type: str, day: int, version: Optional[str] = None
    ) -> Optional[MessageTemplate]:
        """Get message template for specific day."""
        try:
            template = self.load_flow_template(flow_type, version)
            return template.messages.get(day)
        except TemplateLoadError:
            logger.warning(f"Could not load template {flow_type} for day {day}")
            return None

    def get_current_version_info(self, flow_type: str) -> Optional[Dict[str, Any]]:
        """Get current version information for a flow type."""
        try:
            kind_with_version = self.flow_kind_repo.get_with_current_version(flow_type)
            if kind_with_version:
                return {
                    "flow_type": kind_with_version.flow_type,
                    "kind_name": kind_with_version.kind_name,
                    "current_version": kind_with_version.version,
                    "status": kind_with_version.status,
                    "published_at": kind_with_version.published_at,
                    "duration_days": kind_with_version.duration_days,
                }
            return None
        except Exception as e:
            logger.error(f"Error getting current version info: {e}")
            return None

    def list_available_flow_types(self) -> List[Dict[str, Any]]:
        """List all available flow types with their current versions."""
        try:
            kinds_with_stats = self.flow_kind_repo.list_kinds_with_stats()
            return [
                {
                    "flow_type": kind.flow_type,
                    "name": kind.name,
                    "description": kind.description,
                    "total_versions": kind.total_versions,
                    "published_versions": kind.published_versions,
                    "draft_versions": kind.draft_versions,
                    "latest_version_date": kind.latest_version_date,
                    "has_current_version": hasattr(kind, "current_version_id_alias")
                    and kind.current_version_id_alias is not None,
                }
                for kind in kinds_with_stats
            ]
        except Exception as e:
            logger.error(f"Error listing flow types: {e}")
            return []

    def list_versions_for_flow_type(
        self, flow_type: str, status: str = None
    ) -> List[Dict[str, Any]]:
        """List all versions for a specific flow type."""
        try:
            kind = self.flow_kind_repo.get_by_flow_type(flow_type)
            if not kind:
                return []

            versions = self.template_version_repo.list_versions_by_kind(kind.id, status)
            return [
                {
                    "id": str(version.id),
                    "version": version.version,
                    "description": version.description,
                    "status": version.status,
                    "duration_days": version.duration_days,
                    "published_at": version.published_at,
                    "created_at": version.created_at,
                }
                for version in versions
            ]
        except Exception as e:
            logger.error(f"Error listing versions for flow type {flow_type}: {e}")
            return []

    def create_template_version(
        self,
        flow_type: str,
        version: str,
        template_data: FlowTemplateData,
        description: str = None,
        created_by: str = None,
    ) -> bool:
        """Create a new template version."""
        try:
            # Get or create flow kind
            kind = self.flow_kind_repo.get_by_flow_type(flow_type)
            if not kind:
                kind = self.flow_kind_repo.create_kind(
                    flow_type=flow_type,
                    name=template_data.name,
                    description=description or template_data.description,
                )

            # Create template version
            self.template_version_repo.create_version(
                kind_id=kind.id,
                version=version,
                template_data=template_data.to_dict(),
                duration_days=len(template_data.messages),
                description=description,
                created_by=created_by,
            )

            # Clear cache for this flow type
            self._invalidate_cache_for_flow_type(flow_type)

            logger.info(f"Created new template version: {flow_type} v{version}")
            return True

        except Exception as e:
            logger.error(f"Error creating template version: {e}")
            return False

    def publish_template_version(
        self, flow_type: str, version: str, set_as_current: bool = True
    ) -> bool:
        """Publish a draft template version."""
        try:
            template_version = self.template_version_repo.get_by_flow_type_and_version(
                flow_type, version
            )
            if not template_version:
                logger.error(f"Template version not found: {flow_type} v{version}")
                return False

            # Publish the version
            success = self.template_version_repo.publish_version(template_version.id)
            if not success:
                return False

            # Optionally set as current version
            if set_as_current:
                kind = self.flow_kind_repo.get_by_flow_type(flow_type)
                if kind:
                    self.flow_kind_repo.update_current_version(
                        kind.id, template_version.id
                    )

            # Clear cache
            self._invalidate_cache_for_flow_type(flow_type)

            logger.info(f"Published template version: {flow_type} v{version}")
            return True

        except Exception as e:
            logger.error(f"Error publishing template version: {e}")
            return False

    def _parse_db_template_version(
        self, version_model: FlowTemplateVersion
    ) -> FlowTemplateData:
        """Parse database model to FlowTemplateData object."""
        # The database column 'steps' contains the template data
        db_steps = version_model.steps or {}
        
        # Normalize steps: handle both list (from UI) and dict (from RDS)
        normalized_steps = {}
        if isinstance(db_steps, list):
            for idx, content in enumerate(db_steps):
                day_num = content.get("day") or content.get("step_number") or (idx + 1)
                normalized_steps[str(day_num)] = content
        else:
            normalized_steps = db_steps

        # Standardize to MessageTemplate dictionary
        message_templates = {}
        for day_str, content in normalized_steps.items():
            try:
                day_num = int(day_str)
                if isinstance(content, dict):
                    # Ensure required fields are present
                    content.setdefault("day", day_num)
                    content.setdefault("intent", "general_message")
                    # Map content key to base_content if needed
                    if "content" in content and "base_content" not in content:
                        content["base_content"] = content.pop("content")
                    
                    message_templates[day_num] = MessageTemplate(**content)
                else:
                    # Handle simplified text-only templates
                    message_templates[day_num] = MessageTemplate(
                        day=day_num,
                        intent="general_message",
                        base_content=str(content)
                    )
            except (ValueError, TypeError, Exception) as e:
                logger.warning(f"Skipping invalid day '{day_str}' in template: {e}")

        return FlowTemplateData(
            flow_type=version_model.kind.kind_key if version_model.kind else "unknown",
            name=version_model.template_name,
            description=version_model.description or f"Template version {version_model.version_number}",
            version=str(version_model.version_number),
            messages=message_templates,
            metadata=version_model.metadata_json or {}
        )

    def _cache_template(self, cache_key: str, template_data: FlowTemplateData) -> None:
        """Cache template with size and TTL management."""
        if len(self._template_cache) >= self._max_cache_size:
            oldest_key = min(
                self._template_cache.keys(), key=lambda k: self._template_cache[k][1]
            )
            del self._template_cache[oldest_key]
            logger.debug(f"Removed oldest cached template: {oldest_key}")

        self._template_cache[cache_key] = (template_data, datetime.now(timezone.utc))
        logger.debug(f"Cached template: {cache_key}")

    def _invalidate_cache_for_flow_type(self, flow_type: str) -> None:
        """Invalidate cache entries for a specific flow type."""
        cache_keys_to_remove = [
            k for k in self._template_cache.keys() if k.startswith(flow_type)
        ]
        for key in cache_keys_to_remove:
            del self._template_cache[key]
        logger.debug(
            f"Invalidated {len(cache_keys_to_remove)} cache entries for flow_type: {flow_type}"
        )

    def clear_cache(self) -> None:
        """Clear template cache."""
        self._template_cache.clear()
        logger.info("Template cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        now = datetime.now(timezone.utc)
        expired_count = sum(
            1
            for _, cached_time in self._template_cache.values()
            if now - cached_time >= self._cache_ttl
        )

        return {
            "cache_size": len(self._template_cache),
            "max_cache_size": self._max_cache_size,
            "cache_utilization": len(self._template_cache) / self._max_cache_size,
            "expired_entries": expired_count,
            "cache_ttl_hours": self._cache_ttl.total_seconds() / 3600,
            "database_enabled": True,
        }
