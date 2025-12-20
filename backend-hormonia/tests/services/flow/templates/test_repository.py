"""
Tests for FlowTemplateRepository - CRUD Operations, Versioning, Cache, Import/Export.

This module tests the repository pattern implementation for flow template
storage, retrieval, and versioning.
"""

import pytest
from typing import Dict, Any, List

from app.services.flow.templates.repository import FlowTemplateRepository
from app.services.flow.types import (
    FlowTemplate,
    FlowType,
    FlowStepType,
)


class TestFlowTemplateRepositoryCRUD:
    """Test suite for CRUD operations."""

    @pytest.fixture
    def repository(self) -> FlowTemplateRepository:
        """Create repository instance."""
        return FlowTemplateRepository()

    @pytest.fixture
    def sample_template_dict(self) -> Dict[str, Any]:
        """Create sample template dictionary."""
        return {
            "template_id": "test-template-001",
            "name": "Test Template",
            "version": "1.0.0",
            "flow_type": FlowType.ONBOARDING.value,
            "description": "Test template for unit tests",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {"message": "Welcome"},
                },
                {
                    "step_id": "end",
                    "type": FlowStepType.END.value,
                    "action": "end_flow",
                    "config": {},
                },
            ],
            "transitions": [
                {"from_step": "start", "to_step": "end", "type": "direct"},
            ],
            "is_active": True,
        }

    @pytest.fixture
    def sample_template(self, sample_template_dict) -> FlowTemplate:
        """Create sample template instance."""
        return FlowTemplate(**sample_template_dict)

    # ========================================================================
    # Create Tests
    # ========================================================================

    def test_create_template_success(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test successful template creation."""
        # Act
        created = repository.create(sample_template)

        # Assert
        assert created == sample_template
        assert repository.exists(sample_template.template_id)
        assert repository.get(sample_template.template_id) == sample_template

    def test_create_template_duplicate_raises_error(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test creating duplicate template raises ValueError."""
        # Arrange
        repository.create(sample_template)

        # Act & Assert
        with pytest.raises(ValueError, match="Template already exists"):
            repository.create(sample_template)

    def test_create_template_indexes_by_type(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test template is indexed by flow type on creation."""
        # Act
        repository.create(sample_template)

        # Assert
        templates_by_type = repository.list_by_type(sample_template.flow_type)
        assert len(templates_by_type) == 1
        assert templates_by_type[0].template_id == sample_template.template_id

    def test_create_template_initializes_version_history(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test version history is initialized on creation."""
        # Act
        repository.create(sample_template)

        # Assert
        versions = repository.list_versions(sample_template.template_id)
        assert len(versions) == 1
        assert versions[0].version == sample_template.version

    def test_create_template_adds_to_cache(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test template is added to cache on creation."""
        # Act
        repository.create(sample_template)

        # Assert - cache hit should not access storage
        assert sample_template.template_id in repository._cached_templates
        cached = repository._cached_templates[sample_template.template_id]
        assert cached == sample_template

    # ========================================================================
    # Read Tests
    # ========================================================================

    def test_get_template_found(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test getting existing template."""
        # Arrange
        repository.create(sample_template)

        # Act
        result = repository.get(sample_template.template_id)

        # Assert
        assert result is not None
        assert result.template_id == sample_template.template_id

    def test_get_template_not_found(self, repository: FlowTemplateRepository):
        """Test getting non-existent template returns None."""
        # Act
        result = repository.get("nonexistent-template")

        # Assert
        assert result is None

    def test_get_template_uses_cache(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test get uses cache when available."""
        # Arrange
        repository.create(sample_template)

        # Clear storage but keep cache
        template_id = sample_template.template_id
        stored_template = repository._templates[template_id]

        # Act
        result = repository.get(template_id)

        # Assert - should get from cache
        assert result is not None
        assert result == stored_template

    def test_get_template_updates_cache_on_miss(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test cache is updated on cache miss."""
        # Arrange
        repository.create(sample_template)
        repository.clear_cache()

        # Act
        result = repository.get(sample_template.template_id)

        # Assert
        assert result is not None
        assert sample_template.template_id in repository._cached_templates

    def test_exists_returns_true_for_existing_template(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test exists returns True for existing template."""
        # Arrange
        repository.create(sample_template)

        # Act & Assert
        assert repository.exists(sample_template.template_id)

    def test_exists_returns_false_for_nonexistent_template(
        self, repository: FlowTemplateRepository
    ):
        """Test exists returns False for non-existent template."""
        # Act & Assert
        assert not repository.exists("nonexistent-template")

    # ========================================================================
    # Update Tests
    # ========================================================================

    def test_update_template_success(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test successful template update."""
        # Arrange
        repository.create(sample_template)
        sample_template.name = "Updated Name"
        sample_template.version = "1.1.0"

        # Act
        updated = repository.update(sample_template)

        # Assert
        assert updated.name == "Updated Name"
        assert updated.version == "1.1.0"
        assert repository.get(sample_template.template_id).name == "Updated Name"

    def test_update_template_not_found_raises_error(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test updating non-existent template raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Template not found"):
            repository.update(sample_template)

    def test_update_template_updates_timestamp(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test update sets updated_at timestamp."""
        # Arrange
        repository.create(sample_template)
        original_updated_at = sample_template.updated_at

        # Act
        updated = repository.update(sample_template)

        # Assert
        assert updated.updated_at > original_updated_at

    def test_update_template_adds_to_version_history(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test update adds new version to history."""
        # Arrange
        repository.create(sample_template)
        sample_template.version = "1.1.0"

        # Act
        repository.update(sample_template)

        # Assert
        versions = repository.list_versions(sample_template.template_id)
        assert len(versions) == 2
        assert versions[0].version == "1.0.0"
        assert versions[1].version == "1.1.0"

    def test_update_template_limits_version_history(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test version history is limited to max_template_versions."""
        # Arrange
        repository.create(sample_template)
        max_versions = repository.config.max_template_versions

        # Create more versions than max
        for i in range(max_versions + 5):
            sample_template.version = f"1.{i}.0"
            repository.update(sample_template)

        # Assert
        versions = repository.list_versions(sample_template.template_id)
        assert len(versions) == max_versions

    def test_update_template_invalidates_cache(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test update updates cache with new version."""
        # Arrange
        repository.create(sample_template)
        sample_template.name = "Updated Name"

        # Act
        repository.update(sample_template)

        # Assert
        cached = repository._cached_templates.get(sample_template.template_id)
        assert cached is not None
        assert cached.name == "Updated Name"

    # ========================================================================
    # Delete Tests
    # ========================================================================

    def test_delete_template_success(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test successful template deletion."""
        # Arrange
        repository.create(sample_template)

        # Act
        result = repository.delete(sample_template.template_id)

        # Assert
        assert result is True
        assert not repository.exists(sample_template.template_id)
        assert repository.get(sample_template.template_id) is None

    def test_delete_template_not_found_returns_false(
        self, repository: FlowTemplateRepository
    ):
        """Test deleting non-existent template returns False."""
        # Act
        result = repository.delete("nonexistent-template")

        # Assert
        assert result is False

    def test_delete_template_removes_from_type_index(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test deletion removes template from type index."""
        # Arrange
        repository.create(sample_template)
        flow_type = sample_template.flow_type

        # Act
        repository.delete(sample_template.template_id)

        # Assert
        templates_by_type = repository.list_by_type(flow_type)
        assert len(templates_by_type) == 0

    def test_delete_template_removes_version_history(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test deletion removes version history."""
        # Arrange
        repository.create(sample_template)

        # Act
        repository.delete(sample_template.template_id)

        # Assert
        versions = repository.list_versions(sample_template.template_id)
        assert len(versions) == 0

    def test_delete_template_removes_from_cache(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test deletion removes template from cache."""
        # Arrange
        repository.create(sample_template)

        # Act
        repository.delete(sample_template.template_id)

        # Assert
        assert sample_template.template_id not in repository._cached_templates


class TestFlowTemplateRepositoryQuery:
    """Test suite for query operations."""

    @pytest.fixture
    def repository(self) -> FlowTemplateRepository:
        """Create repository instance."""
        return FlowTemplateRepository()

    @pytest.fixture
    def multiple_templates(
        self, repository: FlowTemplateRepository
    ) -> List[FlowTemplate]:
        """Create multiple test templates."""
        templates = []

        for i in range(5):
            template_dict = {
                "template_id": f"template-{i:03d}",
                "name": f"Template {i}",
                "version": "1.0.0",
                "flow_type": FlowType.ONBOARDING.value
                if i < 3
                else FlowType.MONTHLY_QUIZ.value,
                "description": f"Test template {i}",
                "steps": [
                    {
                        "step_id": "start",
                        "type": FlowStepType.START.value,
                        "action": "send_message",
                        "config": {},
                    },
                ],
                "transitions": [],
                "is_active": i % 2 == 0,  # Even templates are active
            }
            template = FlowTemplate(**template_dict)
            repository.create(template)
            templates.append(template)

        return templates

    def test_list_all_active_only(
        self, repository: FlowTemplateRepository, multiple_templates: List[FlowTemplate]
    ):
        """Test list_all returns only active templates by default."""
        # Act
        templates = repository.list_all(include_inactive=False)

        # Assert
        assert len(templates) == 3  # 0, 2, 4 are active
        assert all(t.is_active for t in templates)

    def test_list_all_include_inactive(
        self, repository: FlowTemplateRepository, multiple_templates: List[FlowTemplate]
    ):
        """Test list_all with include_inactive returns all templates."""
        # Act
        templates = repository.list_all(include_inactive=True)

        # Assert
        assert len(templates) == 5

    def test_list_all_sorted_by_created_at_descending(
        self, repository: FlowTemplateRepository, multiple_templates: List[FlowTemplate]
    ):
        """Test list_all returns templates sorted by created_at descending."""
        # Act
        templates = repository.list_all(include_inactive=True)

        # Assert - most recent first
        for i in range(len(templates) - 1):
            assert templates[i].created_at >= templates[i + 1].created_at

    def test_list_by_type_filters_correctly(
        self, repository: FlowTemplateRepository, multiple_templates: List[FlowTemplate]
    ):
        """Test list_by_type filters by flow type."""
        # Act
        onboarding_templates = repository.list_by_type(
            FlowType.ONBOARDING, include_inactive=True
        )
        quiz_templates = repository.list_by_type(
            FlowType.MONTHLY_QUIZ, include_inactive=True
        )

        # Assert
        assert len(onboarding_templates) == 3  # 0, 1, 2
        assert len(quiz_templates) == 2  # 3, 4
        assert all(t.flow_type == FlowType.ONBOARDING for t in onboarding_templates)
        assert all(t.flow_type == FlowType.MONTHLY_QUIZ for t in quiz_templates)

    def test_list_by_type_active_only(
        self, repository: FlowTemplateRepository, multiple_templates: List[FlowTemplate]
    ):
        """Test list_by_type returns only active templates by default."""
        # Act
        templates = repository.list_by_type(FlowType.ONBOARDING, include_inactive=False)

        # Assert
        assert len(templates) == 2  # 0 and 2 are active ONBOARDING
        assert all(t.is_active for t in templates)

    def test_get_active_template_for_type_returns_most_recent(
        self, repository: FlowTemplateRepository, multiple_templates: List[FlowTemplate]
    ):
        """Test get_active_template_for_type returns most recent active template."""
        # Act
        template = repository.get_active_template_for_type(FlowType.ONBOARDING)

        # Assert
        assert template is not None
        assert template.flow_type == FlowType.ONBOARDING
        assert template.is_active

    def test_get_active_template_for_type_returns_none_when_no_active(
        self, repository: FlowTemplateRepository
    ):
        """Test get_active_template_for_type returns None when no active templates."""
        # Act
        template = repository.get_active_template_for_type(FlowType.ONBOARDING)

        # Assert
        assert template is None

    def test_find_by_name_partial_match(
        self, repository: FlowTemplateRepository, multiple_templates: List[FlowTemplate]
    ):
        """Test find_by_name with partial match."""
        # Act
        results = repository.find_by_name("Template")

        # Assert
        assert len(results) == 5  # All have "Template" in name

    def test_find_by_name_case_insensitive(
        self, repository: FlowTemplateRepository, multiple_templates: List[FlowTemplate]
    ):
        """Test find_by_name is case insensitive."""
        # Act
        results = repository.find_by_name("template")

        # Assert
        assert len(results) == 5

    def test_find_by_name_specific_match(
        self, repository: FlowTemplateRepository, multiple_templates: List[FlowTemplate]
    ):
        """Test find_by_name with specific match."""
        # Act
        results = repository.find_by_name("Template 2")

        # Assert
        assert len(results) == 1
        assert results[0].name == "Template 2"

    def test_find_by_name_no_match(
        self, repository: FlowTemplateRepository, multiple_templates: List[FlowTemplate]
    ):
        """Test find_by_name with no matches."""
        # Act
        results = repository.find_by_name("Nonexistent")

        # Assert
        assert len(results) == 0


class TestFlowTemplateRepositoryVersioning:
    """Test suite for version management."""

    @pytest.fixture
    def repository(self) -> FlowTemplateRepository:
        """Create repository instance."""
        return FlowTemplateRepository()

    @pytest.fixture
    def versioned_template(self, repository: FlowTemplateRepository) -> FlowTemplate:
        """Create template with multiple versions."""
        template_dict = {
            "template_id": "versioned-template",
            "name": "Versioned Template",
            "version": "1.0.0",
            "flow_type": FlowType.ONBOARDING.value,
            "description": "Template with versions",
            "steps": [
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
            ],
            "transitions": [],
            "is_active": True,
        }

        template = FlowTemplate(**template_dict)
        repository.create(template)

        # Create additional versions
        for i in range(1, 4):
            template.version = f"1.{i}.0"
            repository.update(template)

        return template

    def test_get_version_specific(
        self, repository: FlowTemplateRepository, versioned_template: FlowTemplate
    ):
        """Test getting specific version."""
        # Act
        version = repository.get_version(versioned_template.template_id, "1.1.0")

        # Assert
        assert version is not None
        assert version.version == "1.1.0"

    def test_get_version_not_found(
        self, repository: FlowTemplateRepository, versioned_template: FlowTemplate
    ):
        """Test getting non-existent version returns None."""
        # Act
        version = repository.get_version(versioned_template.template_id, "9.9.9")

        # Assert
        assert version is None

    def test_list_versions_all(
        self, repository: FlowTemplateRepository, versioned_template: FlowTemplate
    ):
        """Test listing all versions."""
        # Act
        versions = repository.list_versions(versioned_template.template_id)

        # Assert
        assert len(versions) == 4  # 1.0.0, 1.1.0, 1.2.0, 1.3.0
        assert versions[0].version == "1.0.0"
        assert versions[3].version == "1.3.0"

    def test_list_versions_empty_for_nonexistent(
        self, repository: FlowTemplateRepository
    ):
        """Test listing versions for non-existent template returns empty list."""
        # Act
        versions = repository.list_versions("nonexistent")

        # Assert
        assert versions == []

    def test_get_latest_version(
        self, repository: FlowTemplateRepository, versioned_template: FlowTemplate
    ):
        """Test getting latest version."""
        # Act
        latest = repository.get_latest_version(versioned_template.template_id)

        # Assert
        assert latest is not None
        assert latest.version == "1.3.0"


class TestFlowTemplateRepositoryCache:
    """Test suite for cache management."""

    @pytest.fixture
    def repository(self) -> FlowTemplateRepository:
        """Create repository instance."""
        return FlowTemplateRepository()

    @pytest.fixture
    def sample_template(self) -> FlowTemplate:
        """Create sample template."""
        return FlowTemplate(
            template_id="cache-test",
            name="Cache Test",
            version="1.0.0",
            flow_type=FlowType.ONBOARDING.value,
            description="Test",
            steps=[],
            transitions=[],
        )

    def test_clear_cache_removes_all(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test clear_cache removes all cached templates."""
        # Arrange
        repository.create(sample_template)
        assert len(repository._cached_templates) > 0

        # Act
        repository.clear_cache()

        # Assert
        assert len(repository._cached_templates) == 0

    def test_invalidate_cache_removes_specific(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test invalidate_cache removes specific template from cache."""
        # Arrange
        repository.create(sample_template)
        assert sample_template.template_id in repository._cached_templates

        # Act
        repository.invalidate_cache(sample_template.template_id)

        # Assert
        assert sample_template.template_id not in repository._cached_templates

    def test_invalidate_cache_nonexistent_no_error(
        self, repository: FlowTemplateRepository
    ):
        """Test invalidating non-existent cache entry doesn't error."""
        # Act & Assert - should not raise
        repository.invalidate_cache("nonexistent")


class TestFlowTemplateRepositoryBulkOperations:
    """Test suite for bulk operations."""

    @pytest.fixture
    def repository(self) -> FlowTemplateRepository:
        """Create repository instance."""
        return FlowTemplateRepository()

    @pytest.fixture
    def bulk_templates(self) -> List[FlowTemplate]:
        """Create list of templates for bulk operations."""
        templates = []
        for i in range(5):
            template = FlowTemplate(
                template_id=f"bulk-{i}",
                name=f"Bulk Template {i}",
                version="1.0.0",
                flow_type=FlowType.ONBOARDING.value,
                description=f"Bulk test {i}",
                steps=[],
                transitions=[],
            )
            templates.append(template)
        return templates

    def test_bulk_create_all_success(
        self, repository: FlowTemplateRepository, bulk_templates: List[FlowTemplate]
    ):
        """Test bulk_create with all successful."""
        # Act
        created = repository.bulk_create(bulk_templates)

        # Assert
        assert len(created) == 5
        assert all(repository.exists(t.template_id) for t in created)

    def test_bulk_create_with_duplicates(
        self, repository: FlowTemplateRepository, bulk_templates: List[FlowTemplate]
    ):
        """Test bulk_create handles duplicates gracefully."""
        # Arrange - create first template
        repository.create(bulk_templates[0])

        # Act - try to bulk create all (including duplicate)
        created = repository.bulk_create(bulk_templates)

        # Assert - should create all except the duplicate
        assert len(created) == 4

    def test_bulk_update_all_success(
        self, repository: FlowTemplateRepository, bulk_templates: List[FlowTemplate]
    ):
        """Test bulk_update with all successful."""
        # Arrange
        repository.bulk_create(bulk_templates)

        # Modify templates
        for template in bulk_templates:
            template.name = f"Updated {template.name}"

        # Act
        updated = repository.bulk_update(bulk_templates)

        # Assert
        assert len(updated) == 5
        assert all("Updated" in t.name for t in updated)

    def test_bulk_update_with_nonexistent(
        self, repository: FlowTemplateRepository, bulk_templates: List[FlowTemplate]
    ):
        """Test bulk_update handles non-existent templates gracefully."""
        # Arrange - only create first 3
        repository.bulk_create(bulk_templates[:3])

        # Act - try to update all 5
        updated = repository.bulk_update(bulk_templates)

        # Assert - should only update existing 3
        assert len(updated) == 3


class TestFlowTemplateRepositoryImportExport:
    """Test suite for import/export operations."""

    @pytest.fixture
    def repository(self) -> FlowTemplateRepository:
        """Create repository instance."""
        return FlowTemplateRepository()

    @pytest.fixture
    def sample_template(self, repository: FlowTemplateRepository) -> FlowTemplate:
        """Create and store sample template."""
        template = FlowTemplate(
            template_id="export-test",
            name="Export Test",
            version="1.0.0",
            flow_type=FlowType.ONBOARDING.value,
            description="Test export",
            steps=[
                {
                    "step_id": "start",
                    "type": FlowStepType.START.value,
                    "action": "send_message",
                    "config": {},
                },
            ],
            transitions=[],
        )
        repository.create(template)
        return template

    def test_export_template_success(
        self, repository: FlowTemplateRepository, sample_template: FlowTemplate
    ):
        """Test exporting template as dictionary."""
        # Act
        exported = repository.export_template(sample_template.template_id)

        # Assert
        assert exported is not None
        assert exported["template_id"] == sample_template.template_id
        assert exported["name"] == sample_template.name
        assert "steps" in exported
        assert "transitions" in exported

    def test_export_template_not_found(self, repository: FlowTemplateRepository):
        """Test exporting non-existent template returns None."""
        # Act
        exported = repository.export_template("nonexistent")

        # Assert
        assert exported is None

    def test_import_template_success(self, repository: FlowTemplateRepository):
        """Test importing template from dictionary."""
        # Arrange
        template_data = {
            "template_id": "import-test",
            "name": "Import Test",
            "version": "1.0.0",
            "flow_type": FlowType.ONBOARDING.value,
            "description": "Test import",
            "steps": [],
            "transitions": [],
        }

        # Act
        imported = repository.import_template(template_data)

        # Assert
        assert imported is not None
        assert imported.template_id == "import-test"
        assert repository.exists("import-test")

    def test_export_all_returns_all_templates(self, repository: FlowTemplateRepository):
        """Test export_all returns all templates."""
        # Arrange - create multiple templates
        for i in range(3):
            template = FlowTemplate(
                template_id=f"export-all-{i}",
                name=f"Template {i}",
                version="1.0.0",
                flow_type=FlowType.ONBOARDING.value,
                description="Test",
                steps=[],
                transitions=[],
            )
            repository.create(template)

        # Act
        exported = repository.export_all()

        # Assert
        assert len(exported) == 3
        assert all(isinstance(item, dict) for item in exported)

    def test_import_all_success(self, repository: FlowTemplateRepository):
        """Test importing multiple templates."""
        # Arrange
        templates_data = [
            {
                "template_id": f"import-all-{i}",
                "name": f"Import Template {i}",
                "version": "1.0.0",
                "flow_type": FlowType.ONBOARDING.value,
                "description": "Test",
                "steps": [],
                "transitions": [],
            }
            for i in range(3)
        ]

        # Act
        imported = repository.import_all(templates_data)

        # Assert
        assert len(imported) == 3
        assert all(repository.exists(t.template_id) for t in imported)

    def test_import_all_handles_errors_gracefully(
        self, repository: FlowTemplateRepository
    ):
        """Test import_all handles invalid data gracefully."""
        # Arrange - mix valid and invalid templates
        templates_data = [
            {
                "template_id": "valid-1",
                "name": "Valid",
                "version": "1.0.0",
                "flow_type": FlowType.ONBOARDING.value,
                "description": "Test",
                "steps": [],
                "transitions": [],
            },
            {
                "template_id": "invalid",
                # Missing required fields
            },
            {
                "template_id": "valid-2",
                "name": "Valid 2",
                "version": "1.0.0",
                "flow_type": FlowType.ONBOARDING.value,
                "description": "Test",
                "steps": [],
                "transitions": [],
            },
        ]

        # Act
        imported = repository.import_all(templates_data)

        # Assert - should import only valid ones
        assert len(imported) == 2
        assert repository.exists("valid-1")
        assert repository.exists("valid-2")
        assert not repository.exists("invalid")


class TestFlowTemplateRepositoryStatistics:
    """Test suite for statistics operations."""

    @pytest.fixture
    def repository(self) -> FlowTemplateRepository:
        """Create repository instance."""
        return FlowTemplateRepository()

    @pytest.fixture
    def populated_repository(
        self, repository: FlowTemplateRepository
    ) -> FlowTemplateRepository:
        """Create repository with test data."""
        # Create templates with different types and statuses
        for i in range(5):
            template = FlowTemplate(
                template_id=f"stats-{i}",
                name=f"Stats Template {i}",
                version="1.0.0",
                flow_type=FlowType.ONBOARDING.value
                if i < 3
                else FlowType.MONTHLY_QUIZ.value,
                description="Test",
                steps=[],
                transitions=[],
                is_active=i % 2 == 0,
            )
            repository.create(template)

        return repository

    def test_get_stats_counts_templates(
        self, populated_repository: FlowTemplateRepository
    ):
        """Test get_stats returns correct template counts."""
        # Act
        stats = populated_repository.get_stats()

        # Assert
        assert stats["total_templates"] == 5
        assert stats["active_templates"] == 3  # 0, 2, 4 are active
        assert stats["inactive_templates"] == 2  # 1, 3 are inactive

    def test_get_stats_counts_by_type(
        self, populated_repository: FlowTemplateRepository
    ):
        """Test get_stats returns correct counts by type."""
        # Act
        stats = populated_repository.get_stats()

        # Assert
        templates_by_type = stats["templates_by_type"]
        assert templates_by_type[FlowType.ONBOARDING.value] == 3
        assert templates_by_type[FlowType.MONTHLY_QUIZ.value] == 2

    def test_get_stats_cache_info(self, populated_repository: FlowTemplateRepository):
        """Test get_stats returns cache information."""
        # Act
        stats = populated_repository.get_stats()

        # Assert
        assert "cache_size" in stats
        assert "cache_enabled" in stats
        assert stats["cache_enabled"] is True

    def test_get_stats_versioning_info(
        self, populated_repository: FlowTemplateRepository
    ):
        """Test get_stats returns versioning information."""
        # Act
        stats = populated_repository.get_stats()

        # Assert
        assert "versioning_enabled" in stats
        assert isinstance(stats["versioning_enabled"], bool)

    def test_get_stats_empty_repository(self, repository: FlowTemplateRepository):
        """Test get_stats with empty repository."""
        # Act
        stats = repository.get_stats()

        # Assert
        assert stats["total_templates"] == 0
        assert stats["active_templates"] == 0
        assert stats["inactive_templates"] == 0
        assert stats["cache_size"] == 0
