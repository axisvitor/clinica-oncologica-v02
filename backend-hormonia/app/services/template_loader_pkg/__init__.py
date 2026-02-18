"""
DB-only template loader package with versioning support.

This package replaces the monolithic ``template_loader.py`` module.
Every public symbol that the old module exported is re-exported here so
that ``from app.services.template_loader_pkg import X`` works identically
to the previous ``from app.services.template_loader_pkg import X``.
"""

# --- Models (enums, dataclasses, data structures) ---
from app.services.template_loader_pkg.models import (
    MessageType,
    InteractiveType,
    InteractiveElements,
    FlowStepCondition,
    FlowStep,
    Condition,
    MessageTemplate,
    FlowTemplateData,
)

# --- Exceptions ---
from app.services.template_loader_pkg.exceptions import (
    TemplateValidationError,
    TemplateLoadError,
)

# --- Validation ---
from app.services.template_loader_pkg.validation import (
    TemplateValidationResult,
    TemplateValidator,
)

# --- Loader (main service) ---
from app.services.template_loader_pkg.loader import (
    EnhancedTemplateLoader,
)

__all__ = [
    # Models
    "MessageType",
    "InteractiveType",
    "InteractiveElements",
    "FlowStepCondition",
    "FlowStep",
    "Condition",
    "MessageTemplate",
    "FlowTemplateData",
    # Exceptions
    "TemplateValidationError",
    "TemplateLoadError",
    # Validation
    "TemplateValidationResult",
    "TemplateValidator",
    # Loader
    "EnhancedTemplateLoader",
]
