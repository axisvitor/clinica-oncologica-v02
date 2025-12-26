"""
Flow Template Manager - Template management for Flow Services (QW-021).

This module provides the main template management service that coordinates
template creation, validation, storage, and retrieval.

Migration Note:
    This consolidates template management from:
    - flow_template.py (legacy template management)
    - Various template operations scattered across flow services
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging

from ..types import (
    FlowType,
    FlowTemplate,
    FlowValidationResult,
)
from ..config import get_flow_config

from .validator import FlowTemplateValidator
from .repository import FlowTemplateRepository


logger = logging.getLogger(__name__)


class FlowTemplateManager:
    """
    Main template management service.

    Coordinates template validation, storage, and retrieval operations.
    """

    def __init__(
        self,
        repository: Optional[FlowTemplateRepository] = None,
        validator: Optional[FlowTemplateValidator] = None,
    ):
        """
        Initialize template manager.

        Args:
            repository: Optional repository instance (creates new if not provided).
            validator: Optional validator instance (creates new if not provided).
        """
        self.config = get_flow_config().templates
        self.repository = repository or FlowTemplateRepository()
        self.validator = validator or FlowTemplateValidator()

        logger.info("FlowTemplateManager initialized")

    # ========================================================================
    # Template Creation and Updates
    # ========================================================================

    def create_template(
        self,
        template_data: Dict[str, Any],
        validate: bool = True,
    ) -> FlowTemplate:
        """
        Create a new flow template.

        Args:
            template_data: Template data dictionary.
            validate: Whether to validate template before creation.

        Returns:
            Created template.

        Raises:
            ValueError: If validation fails or template already exists.
        """
        # Create template object
        template = FlowTemplate(**template_data)

        # Validate if requested
        if validate or self.config.validate_template_on_load:
            validation_result = self.validator.validate_template(template)
            if not validation_result.is_valid:
                error_msg = "; ".join(validation_result.errors)
                raise ValueError(f"Template validation failed: {error_msg}")

        # Store template
        created_template = self.repository.create(template)

        logger.info(
            f"Created template: {created_template.template_id} "
            f"(type: {created_template.flow_type.value})"
        )

        return created_template

    def update_template(
        self,
        template_id: str,
        updates: Dict[str, Any],
        validate: bool = True,
    ) -> FlowTemplate:
        """
        Update existing template.

        Args:
            template_id: Template ID to update.
            updates: Dictionary with fields to update.
            validate: Whether to validate template after update.

        Returns:
            Updated template.

        Raises:
            ValueError: If template not found or validation fails.
        """
        # Get existing template
        template = self.repository.get(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        # Apply updates
        template_dict = template.model_dump()
        template_dict.update(updates)
        template_dict["updated_at"] = datetime.now(timezone.utc)

        # Create updated template
        updated_template = FlowTemplate(**template_dict)

        # Validate if requested
        if validate or self.config.validate_template_on_load:
            validation_result = self.validator.validate_template(updated_template)
            if not validation_result.is_valid:
                error_msg = "; ".join(validation_result.errors)
                raise ValueError(f"Template validation failed: {error_msg}")

        # Update in repository
        updated_template = self.repository.update(updated_template)

        logger.info(f"Updated template: {template_id}")

        return updated_template

    def delete_template(self, template_id: str) -> bool:
        """
        Delete template.

        Args:
            template_id: Template ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        deleted = self.repository.delete(template_id)

        if deleted:
            logger.info(f"Deleted template: {template_id}")
        else:
            logger.warning(f"Template not found for deletion: {template_id}")

        return deleted

    # ========================================================================
    # Template Retrieval
    # ========================================================================

    def get_template(self, template_id: str) -> Optional[FlowTemplate]:
        """
        Get template by ID.

        Args:
            template_id: Template ID.

        Returns:
            Template if found, None otherwise.
        """
        return self.repository.get(template_id)

    def get_template_for_flow_type(
        self,
        flow_type: FlowType,
    ) -> Optional[FlowTemplate]:
        """
        Get active template for flow type.

        Args:
            flow_type: Flow type.

        Returns:
            Active template if found, None otherwise.
        """
        return self.repository.get_active_template_for_type(flow_type)

    def list_templates(
        self,
        flow_type: Optional[FlowType] = None,
        include_inactive: bool = False,
    ) -> List[FlowTemplate]:
        """
        List templates.

        Args:
            flow_type: Optional filter by flow type.
            include_inactive: Include inactive templates.

        Returns:
            List of templates.
        """
        if flow_type:
            return self.repository.list_by_type(flow_type, include_inactive)
        else:
            return self.repository.list_all(include_inactive)

    def find_templates_by_name(self, name: str) -> List[FlowTemplate]:
        """
        Find templates by name (partial match).

        Args:
            name: Name to search for.

        Returns:
            List of matching templates.
        """
        return self.repository.find_by_name(name)

    # ========================================================================
    # Template Validation
    # ========================================================================

    def validate_template(self, template: FlowTemplate) -> FlowValidationResult:
        """
        Validate a template.

        Args:
            template: Template to validate.

        Returns:
            Validation result.
        """
        return self.validator.validate_template(template)

    def validate_template_by_id(self, template_id: str) -> FlowValidationResult:
        """
        Validate template by ID.

        Args:
            template_id: Template ID to validate.

        Returns:
            Validation result.

        Raises:
            ValueError: If template not found.
        """
        template = self.repository.get(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        return self.validator.validate_template(template)

    # ========================================================================
    # Template Activation/Deactivation
    # ========================================================================

    def activate_template(self, template_id: str) -> FlowTemplate:
        """
        Activate template.

        Args:
            template_id: Template ID to activate.

        Returns:
            Activated template.

        Raises:
            ValueError: If template not found.
        """
        return self.update_template(
            template_id,
            {"is_active": True},
            validate=False,
        )

    def deactivate_template(self, template_id: str) -> FlowTemplate:
        """
        Deactivate template.

        Args:
            template_id: Template ID to deactivate.

        Returns:
            Deactivated template.

        Raises:
            ValueError: If template not found.
        """
        return self.update_template(
            template_id,
            {"is_active": False},
            validate=False,
        )

    # ========================================================================
    # Version Management
    # ========================================================================

    def get_template_version(
        self,
        template_id: str,
        version: str,
    ) -> Optional[FlowTemplate]:
        """
        Get specific version of template.

        Args:
            template_id: Template ID.
            version: Version string.

        Returns:
            Template version if found, None otherwise.
        """
        return self.repository.get_version(template_id, version)

    def list_template_versions(self, template_id: str) -> List[FlowTemplate]:
        """
        List all versions of a template.

        Args:
            template_id: Template ID.

        Returns:
            List of template versions.
        """
        return self.repository.list_versions(template_id)

    def get_latest_version(self, template_id: str) -> Optional[FlowTemplate]:
        """
        Get latest version of template.

        Args:
            template_id: Template ID.

        Returns:
            Latest version if found, None otherwise.
        """
        return self.repository.get_latest_version(template_id)

    # ========================================================================
    # Bulk Operations
    # ========================================================================

    def create_templates_bulk(
        self,
        templates_data: List[Dict[str, Any]],
        validate: bool = True,
    ) -> List[FlowTemplate]:
        """
        Create multiple templates with transaction management.

        All templates are created in a single transaction - either all succeed or all fail.
        This prevents partial batch failures and maintains data consistency.

        Args:
            templates_data: List of template data dictionaries.
            validate: Whether to validate templates before creation.

        Returns:
            List of created templates.

        Raises:
            Exception: If any template creation fails, all changes are rolled back.
        """
        from app.utils.transaction_manager import sync_transaction
        from app.database import get_db

        # Get database session for transaction
        db = next(get_db())
        created = []

        try:
            with sync_transaction(db):
                for template_data in templates_data:
                    template = self.create_template(template_data, validate=validate)
                    created.append(template)
                # Transaction manager handles commit/rollback automatically

            logger.info(f"Bulk created {len(created)} templates")
            return created

        except Exception as e:
            logger.error(f"Bulk template creation failed, all changes rolled back: {e}")
            raise
        finally:
            db.close()

    def validate_templates_bulk(
        self,
        template_ids: List[str],
    ) -> Dict[str, FlowValidationResult]:
        """
        Validate multiple templates.

        Args:
            template_ids: List of template IDs to validate.

        Returns:
            Dictionary mapping template IDs to validation results.
        """
        results = {}
        for template_id in template_ids:
            try:
                result = self.validate_template_by_id(template_id)
                results[template_id] = result
            except Exception as e:
                logger.warning(f"Failed to validate template {template_id}: {e}")
                results[template_id] = FlowValidationResult(
                    is_valid=False,
                    errors=[str(e)],
                    warnings=[],
                )

        return results

    # ========================================================================
    # Import/Export
    # ========================================================================

    def export_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        Export template as dictionary.

        Args:
            template_id: Template ID to export.

        Returns:
            Template data dictionary, or None if not found.
        """
        return self.repository.export_template(template_id)

    def import_template(
        self,
        template_data: Dict[str, Any],
        validate: bool = True,
    ) -> FlowTemplate:
        """
        Import template from dictionary.

        Args:
            template_data: Template data.
            validate: Whether to validate before import.

        Returns:
            Imported template.

        Raises:
            ValueError: If validation fails.
        """
        if validate or self.config.validate_template_on_load:
            template = FlowTemplate(**template_data)
            validation_result = self.validator.validate_template(template)
            if not validation_result.is_valid:
                error_msg = "; ".join(validation_result.errors)
                raise ValueError(f"Template validation failed: {error_msg}")

        return self.repository.import_template(template_data)

    def export_all_templates(self) -> List[Dict[str, Any]]:
        """
        Export all templates.

        Returns:
            List of template data dictionaries.
        """
        return self.repository.export_all()

    def import_templates_bulk(
        self,
        templates_data: List[Dict[str, Any]],
        validate: bool = True,
    ) -> List[FlowTemplate]:
        """
        Import multiple templates.

        Args:
            templates_data: List of template data dictionaries.
            validate: Whether to validate before import.

        Returns:
            List of imported templates.
        """
        imported = []
        for template_data in templates_data:
            try:
                template = self.import_template(template_data, validate=validate)
                imported.append(template)
            except Exception as e:
                logger.warning(
                    f"Failed to import template {template_data.get('template_id')}: {e}"
                )

        logger.info(f"Imported {len(imported)} templates")
        return imported

    # ========================================================================
    # Cache Management
    # ========================================================================

    def clear_cache(self) -> None:
        """Clear template cache."""
        self.repository.clear_cache()
        logger.info("Template cache cleared")

    def invalidate_cache(self, template_id: str) -> None:
        """
        Invalidate cache for specific template.

        Args:
            template_id: Template ID to invalidate.
        """
        self.repository.invalidate_cache(template_id)

    # ========================================================================
    # Statistics and Reporting
    # ========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get template management statistics.

        Returns:
            Dictionary with statistics.
        """
        stats = self.repository.get_stats()

        # Add validation stats
        templates = self.repository.list_all(include_inactive=True)
        valid_count = 0
        invalid_count = 0

        for template in templates:
            result = self.validator.validate_template(template)
            if result.is_valid:
                valid_count += 1
            else:
                invalid_count += 1

        stats["valid_templates"] = valid_count
        stats["invalid_templates"] = invalid_count

        return stats

    def get_health_report(self) -> Dict[str, Any]:
        """
        Get health report for templates.

        Returns:
            Dictionary with health information.
        """
        templates = self.repository.list_all(include_inactive=True)
        issues = []

        for template in templates:
            result = self.validator.validate_template(template)
            if not result.is_valid:
                issues.append(
                    {
                        "template_id": template.template_id,
                        "errors": result.errors,
                        "warnings": result.warnings,
                    }
                )

        return {
            "total_templates": len(templates),
            "templates_with_issues": len(issues),
            "issues": issues,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


# ============================================================================
# Singleton Instance
# ============================================================================

_template_manager_instance: Optional[FlowTemplateManager] = None


def get_template_manager() -> FlowTemplateManager:
    """
    Get global template manager instance.

    Returns:
        Global FlowTemplateManager instance (singleton).
    """
    global _template_manager_instance
    if _template_manager_instance is None:
        _template_manager_instance = FlowTemplateManager()
    return _template_manager_instance


def reset_template_manager() -> None:
    """
    Reset global template manager instance.

    Useful for testing.
    """
    global _template_manager_instance
    _template_manager_instance = None


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "FlowTemplateManager",
    "get_template_manager",
    "reset_template_manager",
]
