"""
Flow Template Repository - Storage for Flow Templates (QW-021).

This module provides repository pattern implementation for flow template
storage, retrieval, and versioning.

Migration Note:
    This consolidates template storage from:
    - flow_template.py (legacy template storage)
    - Various template management scattered across flow services
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID
import logging
import json

from ..types import FlowType, FlowTemplate
from ..config import get_flow_config


logger = logging.getLogger(__name__)


class FlowTemplateRepository:
    """
    Repository for flow template storage and retrieval.

    Manages template persistence, versioning, and caching.
    """

    def __init__(self):
        """Initialize template repository."""
        self.config = get_flow_config().templates

        # In-memory storage (in production, use database)
        self._templates: Dict[str, FlowTemplate] = {}
        self._templates_by_type: Dict[FlowType, List[str]] = {}
        self._template_versions: Dict[str, List[FlowTemplate]] = {}

        # Cache
        self._cache_enabled = self.config.template_cache_enabled
        self._cached_templates: Dict[str, FlowTemplate] = {}

        logger.info("FlowTemplateRepository initialized")

    # ========================================================================
    # CRUD Operations
    # ========================================================================

    def create(self, template: FlowTemplate) -> FlowTemplate:
        """
        Create a new template.

        Args:
            template: Template to create.

        Returns:
            Created template.

        Raises:
            ValueError: If template already exists.
        """
        if template.template_id in self._templates:
            raise ValueError(f"Template already exists: {template.template_id}")

        # Store template
        self._templates[template.template_id] = template

        # Index by flow type
        if template.flow_type not in self._templates_by_type:
            self._templates_by_type[template.flow_type] = []
        self._templates_by_type[template.flow_type].append(template.template_id)

        # Initialize version history
        if self.config.enable_template_versioning:
            self._template_versions[template.template_id] = [template]

        # Cache
        if self._cache_enabled:
            self._cached_templates[template.template_id] = template

        logger.info(f"Created template: {template.template_id} (v{template.version})")
        return template

    def get(self, template_id: str) -> Optional[FlowTemplate]:
        """
        Get template by ID.

        Args:
            template_id: Template ID.

        Returns:
            Template if found, None otherwise.
        """
        # Check cache first
        if self._cache_enabled and template_id in self._cached_templates:
            return self._cached_templates[template_id]

        # Get from storage
        template = self._templates.get(template_id)

        # Update cache
        if template and self._cache_enabled:
            self._cached_templates[template_id] = template

        return template

    def update(self, template: FlowTemplate) -> FlowTemplate:
        """
        Update existing template.

        Args:
            template: Template to update.

        Returns:
            Updated template.

        Raises:
            ValueError: If template doesn't exist.
        """
        if template.template_id not in self._templates:
            raise ValueError(f"Template not found: {template.template_id}")

        # Update timestamp
        template.updated_at = datetime.utcnow()

        # Store updated template
        old_template = self._templates[template.template_id]
        self._templates[template.template_id] = template

        # Add to version history
        if self.config.enable_template_versioning:
            versions = self._template_versions.get(template.template_id, [])
            versions.append(template)

            # Limit version history
            max_versions = self.config.max_template_versions
            if len(versions) > max_versions:
                versions = versions[-max_versions:]

            self._template_versions[template.template_id] = versions

        # Update cache
        if self._cache_enabled:
            self._cached_templates[template.template_id] = template

        logger.info(
            f"Updated template: {template.template_id} "
            f"(v{old_template.version} -> v{template.version})"
        )
        return template

    def delete(self, template_id: str) -> bool:
        """
        Delete template.

        Args:
            template_id: Template ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        if template_id not in self._templates:
            return False

        template = self._templates[template_id]

        # Remove from storage
        del self._templates[template_id]

        # Remove from type index
        if template.flow_type in self._templates_by_type:
            type_templates = self._templates_by_type[template.flow_type]
            if template_id in type_templates:
                type_templates.remove(template_id)

        # Remove from version history
        if template_id in self._template_versions:
            del self._template_versions[template_id]

        # Remove from cache
        if template_id in self._cached_templates:
            del self._cached_templates[template_id]

        logger.info(f"Deleted template: {template_id}")
        return True

    # ========================================================================
    # Query Operations
    # ========================================================================

    def list_all(self, include_inactive: bool = False) -> List[FlowTemplate]:
        """
        List all templates.

        Args:
            include_inactive: Include inactive templates.

        Returns:
            List of templates.
        """
        templates = list(self._templates.values())

        if not include_inactive:
            templates = [t for t in templates if t.is_active]

        return sorted(templates, key=lambda t: t.created_at, reverse=True)

    def list_by_type(
        self,
        flow_type: FlowType,
        include_inactive: bool = False,
    ) -> List[FlowTemplate]:
        """
        List templates by flow type.

        Args:
            flow_type: Flow type to filter by.
            include_inactive: Include inactive templates.

        Returns:
            List of templates for this flow type.
        """
        template_ids = self._templates_by_type.get(flow_type, [])
        templates = [
            self._templates[tid] for tid in template_ids if tid in self._templates
        ]

        if not include_inactive:
            templates = [t for t in templates if t.is_active]

        return sorted(templates, key=lambda t: t.created_at, reverse=True)

    def get_active_template_for_type(
        self, flow_type: FlowType
    ) -> Optional[FlowTemplate]:
        """
        Get the active template for a flow type.

        Args:
            flow_type: Flow type.

        Returns:
            Active template if found, None otherwise.
        """
        templates = self.list_by_type(flow_type, include_inactive=False)

        if not templates:
            return None

        # Return most recent active template
        return templates[0]

    def find_by_name(self, name: str) -> List[FlowTemplate]:
        """
        Find templates by name (partial match).

        Args:
            name: Name to search for.

        Returns:
            List of matching templates.
        """
        name_lower = name.lower()
        return [t for t in self._templates.values() if name_lower in t.name.lower()]

    def exists(self, template_id: str) -> bool:
        """
        Check if template exists.

        Args:
            template_id: Template ID to check.

        Returns:
            True if exists, False otherwise.
        """
        return template_id in self._templates

    # ========================================================================
    # Version Management
    # ========================================================================

    def get_version(self, template_id: str, version: str) -> Optional[FlowTemplate]:
        """
        Get specific version of template.

        Args:
            template_id: Template ID.
            version: Version string.

        Returns:
            Template version if found, None otherwise.
        """
        if not self.config.enable_template_versioning:
            return self.get(template_id)

        versions = self._template_versions.get(template_id, [])
        for template in versions:
            if template.version == version:
                return template

        return None

    def list_versions(self, template_id: str) -> List[FlowTemplate]:
        """
        List all versions of a template.

        Args:
            template_id: Template ID.

        Returns:
            List of template versions, ordered by version.
        """
        if not self.config.enable_template_versioning:
            template = self.get(template_id)
            return [template] if template else []

        return self._template_versions.get(template_id, [])

    def get_latest_version(self, template_id: str) -> Optional[FlowTemplate]:
        """
        Get latest version of template.

        Args:
            template_id: Template ID.

        Returns:
            Latest version if found, None otherwise.
        """
        return self.get(template_id)

    # ========================================================================
    # Cache Management
    # ========================================================================

    def clear_cache(self) -> None:
        """Clear template cache."""
        self._cached_templates.clear()
        logger.info("Template cache cleared")

    def invalidate_cache(self, template_id: str) -> None:
        """
        Invalidate cache for specific template.

        Args:
            template_id: Template ID to invalidate.
        """
        if template_id in self._cached_templates:
            del self._cached_templates[template_id]
            logger.debug(f"Cache invalidated for template: {template_id}")

    # ========================================================================
    # Bulk Operations
    # ========================================================================

    def bulk_create(self, templates: List[FlowTemplate]) -> List[FlowTemplate]:
        """
        Create multiple templates.

        Args:
            templates: List of templates to create.

        Returns:
            List of created templates.
        """
        created = []
        for template in templates:
            try:
                created_template = self.create(template)
                created.append(created_template)
            except ValueError as e:
                logger.warning(f"Failed to create template {template.template_id}: {e}")

        logger.info(f"Bulk created {len(created)} templates")
        return created

    def bulk_update(self, templates: List[FlowTemplate]) -> List[FlowTemplate]:
        """
        Update multiple templates.

        Args:
            templates: List of templates to update.

        Returns:
            List of updated templates.
        """
        updated = []
        for template in templates:
            try:
                updated_template = self.update(template)
                updated.append(updated_template)
            except ValueError as e:
                logger.warning(f"Failed to update template {template.template_id}: {e}")

        logger.info(f"Bulk updated {len(updated)} templates")
        return updated

    # ========================================================================
    # Import/Export
    # ========================================================================

    def export_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        Export template as dictionary.

        Args:
            template_id: Template ID to export.

        Returns:
            Template data as dictionary, or None if not found.
        """
        template = self.get(template_id)
        if not template:
            return None

        return template.model_dump()

    def import_template(self, template_data: Dict[str, Any]) -> FlowTemplate:
        """
        Import template from dictionary.

        Args:
            template_data: Template data.

        Returns:
            Imported template.
        """
        template = FlowTemplate(**template_data)
        return self.create(template)

    def export_all(self) -> List[Dict[str, Any]]:
        """
        Export all templates.

        Returns:
            List of template data dictionaries.
        """
        return [t.model_dump() for t in self._templates.values()]

    def import_all(self, templates_data: List[Dict[str, Any]]) -> List[FlowTemplate]:
        """
        Import multiple templates.

        Args:
            templates_data: List of template data dictionaries.

        Returns:
            List of imported templates.
        """
        imported = []
        for template_data in templates_data:
            try:
                template = self.import_template(template_data)
                imported.append(template)
            except Exception as e:
                logger.warning(f"Failed to import template: {e}")

        logger.info(f"Imported {len(imported)} templates")
        return imported

    # ========================================================================
    # Statistics
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """
        Get repository statistics.

        Returns:
            Dictionary with repository stats.
        """
        templates = list(self._templates.values())
        active_count = sum(1 for t in templates if t.is_active)

        return {
            "total_templates": len(templates),
            "active_templates": active_count,
            "inactive_templates": len(templates) - active_count,
            "templates_by_type": {
                flow_type.value: len(template_ids)
                for flow_type, template_ids in self._templates_by_type.items()
            },
            "cache_size": len(self._cached_templates),
            "cache_enabled": self._cache_enabled,
            "versioning_enabled": self.config.enable_template_versioning,
        }


# ============================================================================
# Exports
# ============================================================================

__all__ = ["FlowTemplateRepository"]
