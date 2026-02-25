"""
TOMBSTONED -- Phase 16 (Dead Code Removal)

Tests for app.services.flow.templates which has been tombstoned.
"""

import pytest

pytest.skip(
    "app.services.flow.templates tombstoned in Phase 16 (Dead Code Removal)",
    allow_module_level=True,
)

from typing import Dict, Any, List
from unittest.mock import Mock

from app.services.flow.templates.manager import FlowTemplateManager
from app.services.flow.templates.repository import FlowTemplateRepository
from app.services.flow.templates.validator import FlowTemplateValidator
from app.services.flow.types import (
    FlowTemplate,
    FlowType,
    FlowStepType,
    FlowTransitionType,
    FlowValidationResult,
)


class TestFlowTemplateManagerCreation:
    """Test suite for template creation."""

    @pytest.fixture
    def repository(self) -> FlowTemplateRepository:
        """Create repository instance."""
        return FlowTemplateRepository()

    @pytest.fixture
    def validator(self) -> FlowTemplateValidator:
        """Create validator instance."""
        return FlowTemplateValidator()

    @pytest.fixture
    def manager(
        self, repository: FlowTemplateRepository, validator: FlowTemplateValidator
    ) -> FlowTemplateManager:
        """Create manager instance."""
        return FlowTemplateManager(repository=repository, validator=validator)

    @pytest.fixture
    def valid_template_data(self) -> Dict[str, Any]:
        """Create valid template data."""
        return {
            "template_id": "test-template-001",
            "name": "Test Template",
            "version": "1.0.0",
            "flow_type": FlowType.ONBOARDING.value,
            "description": "Test template",
            "steps": [
                {
                    "step_id": "start",
                    "name": "Start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {"message": "Welcome"},
                },
                {
                    "step_id": "end",
                    "name": "End",
                    "type": FlowStepType.END.value,
                    "action": "end_flow",
                    "config": {},
                },
            ],
            "transitions": [
                {"from_step": "start", "to_step": "end", "type": FlowTransitionType.AUTOMATIC.value},
            ],
            "is_active": True,
        }

    # ========================================================================
    # Create Template Tests
    # ========================================================================

    def test_create_template_success(
        self, manager: FlowTemplateManager, valid_template_data: Dict[str, Any]
    ):
        """Test successful template creation with validation."""
        # Act
        created = manager.create_template(valid_template_data, validate=True)

        # Assert
        assert created is not None
        assert created.template_id == valid_template_data["template_id"]
        assert created.name == valid_template_data["name"]
        assert manager.get_template(created.template_id) is not None

    def test_create_template_without_validation(
        self, manager: FlowTemplateManager, valid_template_data: Dict[str, Any]
    ):
        """Test template creation without validation."""
        # Act
        created = manager.create_template(valid_template_data, validate=False)

        # Assert
        assert created is not None
        assert created.template_id == valid_template_data["template_id"]

    def test_create_template_validation_fails(
        self, manager: FlowTemplateManager, valid_template_data: Dict[str, Any]
    ):
        """Test creation fails when validation fails."""
        # Arrange - create invalid template (missing required field)
        invalid_data = valid_template_data.copy()
        invalid_data["steps"] = []  # Empty steps - invalid

        # Act & Assert
        with pytest.raises(ValueError, match="Template validation failed"):
            manager.create_template(invalid_data, validate=True)

    def test_create_template_duplicate_raises_error(
        self, manager: FlowTemplateManager, valid_template_data: Dict[str, Any]
    ):
        """Test creating duplicate template raises error."""
        # Arrange
        manager.create_template(valid_template_data)

        # Act & Assert
        with pytest.raises(ValueError):
            manager.create_template(valid_template_data)

    def test_create_template_uses_validator(
        self, repository: FlowTemplateRepository, valid_template_data: Dict[str, Any]
    ):
        """Test create_template uses validator when validate=True."""
        # Arrange
        mock_validator = Mock(spec=FlowTemplateValidator)
        mock_validator.validate_template.return_value = FlowValidationResult(
            is_valid=True, errors=[], warnings=[]
        )
        manager = FlowTemplateManager(repository=repository, validator=mock_validator)

        # Act
        manager.create_template(valid_template_data, validate=True)

        # Assert
        mock_validator.validate_template.assert_called_once()

    def test_create_template_stores_in_repository(
        self, validator: FlowTemplateValidator, valid_template_data: Dict[str, Any]
    ):
        """Test create_template stores in repository."""
        # Arrange
        mock_repository = Mock(spec=FlowTemplateRepository)
        mock_repository.create.return_value = FlowTemplate(**valid_template_data)
        manager = FlowTemplateManager(repository=mock_repository, validator=validator)

        # Act
        manager.create_template(valid_template_data, validate=False)

        # Assert
        mock_repository.create.assert_called_once()


class TestFlowTemplateManagerUpdate:
    """Test suite for template updates."""

    @pytest.fixture
    def manager(self) -> FlowTemplateManager:
        """Create manager instance."""
        return FlowTemplateManager()

    @pytest.fixture
    def existing_template_data(self) -> Dict[str, Any]:
        """Create existing template data."""
        return {
            "template_id": "existing-template",
            "name": "Existing Template",
            "version": "1.0.0",
            "flow_type": FlowType.ONBOARDING.value,
            "description": "Original description",
            "steps": [
                {
                    "step_id": "start",
                    "name": "Start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {"message": "Original"},
                },
                {
                    "step_id": "end",
                    "name": "End",
                    "type": FlowStepType.END.value,
                    "action": "end_flow",
                    "config": {},
                },
            ],
            "transitions": [
                {"from_step": "start", "to_step": "end", "type": FlowTransitionType.AUTOMATIC.value},
            ],
            "is_active": True,
        }

    def test_update_template_success(
        self,
        manager: FlowTemplateManager,
        existing_template_data: Dict[str, Any],
    ):
        """Test successful template update."""
        # Arrange
        created = manager.create_template(existing_template_data)
        updates = {
            "name": "Updated Template",
            "description": "Updated description",
        }

        # Act
        updated = manager.update_template(created.template_id, updates, validate=True)

        # Assert
        assert updated.name == "Updated Template"
        assert updated.description == "Updated description"
        assert updated.template_id == created.template_id

    def test_update_template_not_found(self, manager: FlowTemplateManager):
        """Test updating non-existent template raises error."""
        # Act & Assert
        with pytest.raises(ValueError, match="Template not found"):
            manager.update_template("nonexistent", {"name": "New Name"})

    def test_update_template_validation_fails(
        self,
        manager: FlowTemplateManager,
        existing_template_data: Dict[str, Any],
    ):
        """Test update fails when validation fails."""
        # Arrange
        created = manager.create_template(existing_template_data)
        invalid_updates = {"steps": []}  # Empty steps - invalid

        # Act & Assert
        with pytest.raises(ValueError, match="Template validation failed"):
            manager.update_template(created.template_id, invalid_updates, validate=True)

    def test_update_template_without_validation(
        self,
        manager: FlowTemplateManager,
        existing_template_data: Dict[str, Any],
    ):
        """Test update without validation."""
        # Arrange
        created = manager.create_template(existing_template_data)
        updates = {"name": "Updated Name"}

        # Act
        updated = manager.update_template(created.template_id, updates, validate=False)

        # Assert
        assert updated.name == "Updated Name"

    def test_update_template_updates_timestamp(
        self,
        manager: FlowTemplateManager,
        existing_template_data: Dict[str, Any],
    ):
        """Test update sets updated_at timestamp."""
        # Arrange
        created = manager.create_template(existing_template_data)
        original_updated_at = created.updated_at

        # Act
        updated = manager.update_template(
            created.template_id, {"name": "New Name"}, validate=False
        )

        # Assert
        assert updated.updated_at > original_updated_at


class TestFlowTemplateManagerDelete:
    """Test suite for template deletion."""

    @pytest.fixture
    def manager(self) -> FlowTemplateManager:
        """Create manager instance."""
        return FlowTemplateManager()

    @pytest.fixture
    def template_data(self) -> Dict[str, Any]:
        """Create template data."""
        return {
            "template_id": "delete-test",
            "name": "Delete Test",
            "version": "1.0.0",
            "flow_type": FlowType.ONBOARDING.value,
            "description": "Test",
            "steps": [
                {
                    "step_id": "start",
                    "name": "Start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
            ],
            "transitions": [],
        }

    def test_delete_template_success(
        self, manager: FlowTemplateManager, template_data: Dict[str, Any]
    ):
        """Test successful template deletion."""
        # Arrange
        created = manager.create_template(template_data, validate=False)

        # Act
        result = manager.delete_template(created.template_id)

        # Assert
        assert result is True
        assert manager.get_template(created.template_id) is None

    def test_delete_template_not_found(self, manager: FlowTemplateManager):
        """Test deleting non-existent template returns False."""
        # Act
        result = manager.delete_template("nonexistent")

        # Assert
        assert result is False


class TestFlowTemplateManagerRetrieval:
    """Test suite for template retrieval."""

    @pytest.fixture
    def manager(self) -> FlowTemplateManager:
        """Create manager instance."""
        return FlowTemplateManager()

    @pytest.fixture
    def multiple_templates(self, manager: FlowTemplateManager) -> List[FlowTemplate]:
        """Create multiple templates."""
        templates = []
        for i in range(3):
            template_data = {
                "template_id": f"template-{i}",
                "name": f"Template {i}",
                "version": "1.0.0",
                "flow_type": FlowType.ONBOARDING.value
                if i < 2
                else FlowType.QUIZ_MENSAL.value,
                "description": "Test",
                "steps": [
                    {
                        "step_id": "start",
                        "name": "Start",
                        "type": FlowStepType.START.value,
                        "action": "send_message",
                        "config": {},
                    },
                ],
                "transitions": [],
                "is_active": i % 2 == 0,
            }
            template = manager.create_template(template_data, validate=False)
            templates.append(template)
        return templates

    def test_get_template_found(
        self, manager: FlowTemplateManager, multiple_templates: List[FlowTemplate]
    ):
        """Test getting existing template."""
        # Act
        template = manager.get_template(multiple_templates[0].template_id)

        # Assert
        assert template is not None
        assert template.template_id == multiple_templates[0].template_id

    def test_get_template_not_found(self, manager: FlowTemplateManager):
        """Test getting non-existent template returns None."""
        # Act
        template = manager.get_template("nonexistent")

        # Assert
        assert template is None

    def test_get_template_for_flow_type(
        self, manager: FlowTemplateManager, multiple_templates: List[FlowTemplate]
    ):
        """Test getting active template for flow type."""
        # Act
        template = manager.get_template_for_flow_type(FlowType.ONBOARDING)

        # Assert
        assert template is not None
        assert template.flow_type == FlowType.ONBOARDING
        assert template.is_active

    def test_list_templates_all(
        self, manager: FlowTemplateManager, multiple_templates: List[FlowTemplate]
    ):
        """Test listing all templates."""
        # Act
        templates = manager.list_templates(include_inactive=True)

        # Assert
        assert len(templates) == 3

    def test_list_templates_active_only(
        self, manager: FlowTemplateManager, multiple_templates: List[FlowTemplate]
    ):
        """Test listing only active templates."""
        # Act
        templates = manager.list_templates(include_inactive=False)

        # Assert
        assert len(templates) == 2
        assert all(t.is_active for t in templates)

    def test_list_templates_by_type(
        self, manager: FlowTemplateManager, multiple_templates: List[FlowTemplate]
    ):
        """Test listing templates by flow type."""
        # Act
        templates = manager.list_templates(
            flow_type=FlowType.ONBOARDING, include_inactive=True
        )

        # Assert
        assert len(templates) == 2
        assert all(t.flow_type == FlowType.ONBOARDING for t in templates)

    def test_find_templates_by_name(
        self, manager: FlowTemplateManager, multiple_templates: List[FlowTemplate]
    ):
        """Test finding templates by name."""
        # Act
        templates = manager.find_templates_by_name("Template 1")

        # Assert
        assert len(templates) == 1
        assert templates[0].name == "Template 1"


class TestFlowTemplateManagerValidation:
    """Test suite for template validation."""

    @pytest.fixture
    def manager(self) -> FlowTemplateManager:
        """Create manager instance."""
        return FlowTemplateManager()

    @pytest.fixture
    def valid_template(self, manager: FlowTemplateManager) -> FlowTemplate:
        """Create valid template."""
        template_data = {
            "template_id": "valid-template",
            "name": "Valid Template",
            "version": "1.0.0",
            "flow_type": FlowType.ONBOARDING.value,
            "description": "Valid",
            "steps": [
                {
                    "step_id": "start",
                    "name": "Start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {"message": "Welcome"},
                },
                {
                    "step_id": "end",
                    "name": "End",
                    "type": FlowStepType.END.value,
                    "action": "end_flow",
                    "config": {},
                },
            ],
            "transitions": [
                {"from_step": "start", "to_step": "end", "type": FlowTransitionType.AUTOMATIC.value},
            ],
        }
        return manager.create_template(template_data, validate=False)

    def test_validate_template_valid(
        self, manager: FlowTemplateManager, valid_template: FlowTemplate
    ):
        """Test validating valid template."""
        # Act
        result = manager.validate_template(valid_template)

        # Assert
        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_template_invalid(self, manager: FlowTemplateManager):
        """Test validating invalid template."""
        # Arrange - create invalid template
        invalid_template = FlowTemplate(
            template_id="invalid",
            name="Invalid",
            version="1.0.0",
            flow_type=FlowType.ONBOARDING,
            description="Invalid",
            steps=[],  # Empty steps - invalid
            transitions=[],
        )

        # Act
        result = manager.validate_template(invalid_template)

        # Assert
        assert not result.is_valid
        assert len(result.errors) > 0

    def test_validate_template_by_id_found(
        self, manager: FlowTemplateManager, valid_template: FlowTemplate
    ):
        """Test validating template by ID."""
        # Act
        result = manager.validate_template_by_id(valid_template.template_id)

        # Assert
        assert result.is_valid

    def test_validate_template_by_id_not_found(self, manager: FlowTemplateManager):
        """Test validating non-existent template by ID raises error."""
        # Act & Assert
        with pytest.raises(ValueError, match="Template not found"):
            manager.validate_template_by_id("nonexistent")


class TestFlowTemplateManagerActivation:
    """Test suite for template activation/deactivation."""

    @pytest.fixture
    def manager(self) -> FlowTemplateManager:
        """Create manager instance."""
        return FlowTemplateManager()

    @pytest.fixture
    def template(self, manager: FlowTemplateManager) -> FlowTemplate:
        """Create test template."""
        template_data = {
            "template_id": "activation-test",
            "name": "Activation Test",
            "version": "1.0.0",
            "flow_type": FlowType.ONBOARDING.value,
            "description": "Test",
            "steps": [
                {
                    "step_id": "start",
                    "name": "Start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
            ],
            "transitions": [],
            "is_active": False,
        }
        return manager.create_template(template_data, validate=False)

    def test_activate_template_success(
        self, manager: FlowTemplateManager, template: FlowTemplate
    ):
        """Test activating template."""
        # Act
        activated = manager.activate_template(template.template_id)

        # Assert
        assert activated.is_active is True
        assert manager.get_template(template.template_id).is_active is True

    def test_activate_template_not_found(self, manager: FlowTemplateManager):
        """Test activating non-existent template raises error."""
        # Act & Assert
        with pytest.raises(ValueError, match="Template not found"):
            manager.activate_template("nonexistent")

    def test_deactivate_template_success(
        self, manager: FlowTemplateManager, template: FlowTemplate
    ):
        """Test deactivating template."""
        # Arrange - activate first
        manager.activate_template(template.template_id)

        # Act
        deactivated = manager.deactivate_template(template.template_id)

        # Assert
        assert deactivated.is_active is False
        assert manager.get_template(template.template_id).is_active is False

    def test_deactivate_template_not_found(self, manager: FlowTemplateManager):
        """Test deactivating non-existent template raises error."""
        # Act & Assert
        with pytest.raises(ValueError, match="Template not found"):
            manager.deactivate_template("nonexistent")


class TestFlowTemplateManagerVersioning:
    """Test suite for version management."""

    @pytest.fixture
    def manager(self) -> FlowTemplateManager:
        """Create manager instance."""
        return FlowTemplateManager()

    @pytest.fixture
    def versioned_template(self, manager: FlowTemplateManager) -> FlowTemplate:
        """Create template with multiple versions."""
        template_data = {
            "template_id": "versioned",
            "name": "Versioned Template",
            "version": "1.0.0",
            "flow_type": FlowType.ONBOARDING.value,
            "description": "Test",
            "steps": [
                {
                    "step_id": "start",
                    "name": "Start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
            ],
            "transitions": [],
        }
        template = manager.create_template(template_data, validate=False)

        # Create additional versions
        for i in range(1, 3):
            manager.update_template(
                template.template_id, {"version": f"1.{i}.0"}, validate=False
            )

        return template

    def test_get_template_version(
        self, manager: FlowTemplateManager, versioned_template: FlowTemplate
    ):
        """Test getting specific version."""
        # Act
        version = manager.get_template_version(versioned_template.template_id, "1.1.0")

        # Assert
        assert version is not None
        assert version.version == "1.1.0"

    def test_list_template_versions(
        self, manager: FlowTemplateManager, versioned_template: FlowTemplate
    ):
        """Test listing all versions."""
        # Act
        versions = manager.list_template_versions(versioned_template.template_id)

        # Assert
        assert len(versions) == 3
        assert versions[0].version == "1.0.0"
        assert versions[2].version == "1.2.0"

    def test_get_latest_version(
        self, manager: FlowTemplateManager, versioned_template: FlowTemplate
    ):
        """Test getting latest version."""
        # Act
        latest = manager.get_latest_version(versioned_template.template_id)

        # Assert
        assert latest is not None
        assert latest.version == "1.2.0"


class TestFlowTemplateManagerBulkOperations:
    """Test suite for bulk operations."""

    @pytest.fixture
    def manager(self) -> FlowTemplateManager:
        """Create manager instance."""
        return FlowTemplateManager()

    @pytest.fixture
    def bulk_template_data(self) -> List[Dict[str, Any]]:
        """Create list of template data."""
        templates = []
        for i in range(3):
            templates.append(
                {
                    "template_id": f"bulk-{i}",
                    "name": f"Bulk Template {i}",
                    "version": "1.0.0",
                    "flow_type": FlowType.ONBOARDING.value,
                    "description": "Test",
                    "steps": [
                        {
                            "step_id": "start",
                            "name": "Start",
                            "type": FlowStepType.START.value,
                            "action": "send_message",
                            "config": {},
                        },
                    ],
                    "transitions": [],
                }
            )
        return templates

    def test_create_templates_bulk_all_success(
        self, manager: FlowTemplateManager, bulk_template_data: List[Dict[str, Any]]
    ):
        """Test bulk create with all successful."""
        # Act
        created = manager.create_templates_bulk(bulk_template_data, validate=False)

        # Assert
        assert len(created) == 3
        assert all(manager.get_template(t.template_id) for t in created)

    def test_create_templates_bulk_with_validation(
        self, manager: FlowTemplateManager, bulk_template_data: List[Dict[str, Any]]
    ):
        """Test bulk create with validation."""
        # Act
        created = manager.create_templates_bulk(bulk_template_data, validate=True)

        # Assert
        assert len(created) == 3

    def test_validate_templates_bulk(
        self, manager: FlowTemplateManager, bulk_template_data: List[Dict[str, Any]]
    ):
        """Test bulk validation."""
        # Arrange
        created_templates = manager.create_templates_bulk(
            bulk_template_data, validate=False
        )
        template_ids = [template.template_id for template in created_templates]

        # Act
        results = manager.validate_templates_bulk(template_ids)

        # Assert
        assert len(results) == 3
        assert all(result.is_valid for result in results.values())


class TestFlowTemplateManagerImportExport:
    """Test suite for import/export operations."""

    @pytest.fixture
    def manager(self) -> FlowTemplateManager:
        """Create manager instance."""
        return FlowTemplateManager()

    @pytest.fixture
    def template(self, manager: FlowTemplateManager) -> FlowTemplate:
        """Create test template."""
        template_data = {
            "template_id": "export-test",
            "name": "Export Test",
            "version": "1.0.0",
            "flow_type": FlowType.ONBOARDING.value,
            "description": "Test",
            "steps": [
                {
                    "step_id": "start",
                    "name": "Start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
            ],
            "transitions": [],
        }
        return manager.create_template(template_data, validate=False)

    def test_export_template_success(
        self, manager: FlowTemplateManager, template: FlowTemplate
    ):
        """Test exporting template."""
        # Act
        exported = manager.export_template(template.template_id)

        # Assert
        assert exported is not None
        assert exported["template_id"] == template.template_id

    def test_export_template_not_found(self, manager: FlowTemplateManager):
        """Test exporting non-existent template returns None."""
        # Act
        exported = manager.export_template("nonexistent")

        # Assert
        assert exported is None

    def test_import_template_success(self, manager: FlowTemplateManager):
        """Test importing template."""
        # Arrange
        template_data = {
            "template_id": "import-test",
            "name": "Import Test",
            "version": "1.0.0",
            "flow_type": FlowType.ONBOARDING.value,
            "description": "Test",
            "steps": [
                {
                    "step_id": "start",
                    "name": "Start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
            ],
            "transitions": [],
        }

        # Act
        imported = manager.import_template(template_data, validate=False)

        # Assert
        assert imported is not None
        assert imported.template_id == "import-test"
        assert manager.get_template("import-test") is not None

    def test_export_all_templates(self, manager: FlowTemplateManager):
        """Test exporting all templates."""
        # Arrange - create multiple templates
        for i in range(2):
            template_data = {
                "template_id": f"export-all-{i}",
                "name": f"Template {i}",
                "version": "1.0.0",
                "flow_type": FlowType.ONBOARDING.value,
                "description": "Test",
                "steps": [
                    {
                        "step_id": "start",
                        "name": "Start",
                        "type": FlowStepType.START.value,
                        "action": "send_message",
                        "config": {},
                    },
                ],
                "transitions": [],
            }
            manager.create_template(template_data, validate=False)

        # Act
        exported = manager.export_all_templates()

        # Assert
        assert len(exported) == 2

    def test_import_templates_bulk(self, manager: FlowTemplateManager):
        """Test bulk import."""
        # Arrange
        templates_data = [
            {
                "template_id": f"import-bulk-{i}",
                "name": f"Import {i}",
                "version": "1.0.0",
                "flow_type": FlowType.ONBOARDING.value,
                "description": "Test",
                "steps": [
                    {
                        "step_id": "start",
                        "name": "Start",
                        "type": FlowStepType.START.value,
                        "action": "send_message",
                        "config": {},
                    },
                ],
                "transitions": [],
            }
            for i in range(2)
        ]

        # Act
        imported = manager.import_templates_bulk(templates_data, validate=False)

        # Assert
        assert len(imported) == 2


class TestFlowTemplateManagerCache:
    """Test suite for cache management."""

    @pytest.fixture
    def manager(self) -> FlowTemplateManager:
        """Create manager instance."""
        return FlowTemplateManager()

    def test_clear_cache(self, manager: FlowTemplateManager):
        """Test clearing cache."""
        # Arrange - create template
        template_data = {
            "template_id": "cache-test",
            "name": "Cache Test",
            "version": "1.0.0",
            "flow_type": FlowType.ONBOARDING.value,
            "description": "Test",
            "steps": [
                {
                    "step_id": "start",
                    "name": "Start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
            ],
            "transitions": [],
        }
        manager.create_template(template_data, validate=False)

        # Act
        manager.clear_cache()

        # Assert - cache should be empty
        assert len(manager.repository._cached_templates) == 0

    def test_invalidate_cache(self, manager: FlowTemplateManager):
        """Test invalidating specific template cache."""
        # Arrange
        template_data = {
            "template_id": "invalidate-test",
            "name": "Invalidate Test",
            "version": "1.0.0",
            "flow_type": FlowType.ONBOARDING.value,
            "description": "Test",
            "steps": [
                {
                    "step_id": "start",
                    "name": "Start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
            ],
            "transitions": [],
        }
        template = manager.create_template(template_data, validate=False)

        # Act
        manager.invalidate_cache(template.template_id)

        # Assert
        assert template.template_id not in manager.repository._cached_templates


class TestFlowTemplateManagerStatistics:
    """Test suite for statistics and health."""

    @pytest.fixture
    def manager(self) -> FlowTemplateManager:
        """Create manager instance."""
        return FlowTemplateManager()

    def test_get_statistics(self, manager: FlowTemplateManager):
        """Test getting statistics."""
        # Arrange - create some templates
        for i in range(2):
            template_data = {
                "template_id": f"stats-{i}",
                "name": f"Stats {i}",
                "version": "1.0.0",
                "flow_type": FlowType.ONBOARDING.value,
                "description": "Test",
                "steps": [
                    {
                        "step_id": "start",
                        "name": "Start",
                        "type": FlowStepType.START.value,
                        "action": "send_message",
                        "config": {},
                    },
                ],
                "transitions": [],
                "is_active": i == 0,
            }
            manager.create_template(template_data, validate=False)

        # Act
        stats = manager.get_statistics()

        # Assert
        assert stats is not None
        assert "total_templates" in stats
        assert stats["total_templates"] == 2
        assert stats["active_templates"] == 1

    def test_get_health_report(self, manager: FlowTemplateManager):
        """Test getting health report."""
        # Arrange - create some templates
        for i in range(2):
            template_data = {
                "template_id": f"health-{i}",
                "name": f"Health {i}",
                "version": "1.0.0",
                "flow_type": FlowType.ONBOARDING.value,
                "description": "Test",
                "steps": [
                    {
                        "step_id": "start",
                        "name": "Start",
                        "type": FlowStepType.START.value,
                        "action": "send_message",
                        "config": {},
                    },
                ],
                "transitions": [],
            }
            manager.create_template(template_data, validate=False)

        # Act
        health = manager.get_health_report()

        # Assert
        assert health is not None
        assert "checked_at" in health
        assert "total_templates" in health
        assert "templates_with_issues" in health
        assert "issues" in health
