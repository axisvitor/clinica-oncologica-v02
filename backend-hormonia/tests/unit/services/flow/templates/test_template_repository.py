"""
TOMBSTONED -- Phase 16 (Dead Code Removal)

Tests for app.services.flow.templates which has been tombstoned.
"""

import pytest

pytest.skip(
    "app.services.flow.templates tombstoned in Phase 16 (Dead Code Removal)",
    allow_module_level=True,
)

from datetime import datetime, timedelta

from app.services.flow.templates.repository import FlowTemplateRepository
from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
from app.services.flow.types import (
    FlowTemplate,
    FlowType,
)


@pytest.fixture
def repository():
    """Create FlowTemplateRepository instance."""
    return FlowTemplateRepository()


@pytest.fixture
def sample_template():
    """Create sample template for testing."""
    return FlowTemplate(
        template_id="test_template_001",
        flow_type=FlowType.DAILY_FOLLOW_UP,
        version="1.0.0",
        name="Test Template",
        description="Sample template for testing",
        steps=[
            {"step_id": "step_001", "type": "message", "name": "Greeting"},
            {"step_id": "step_002", "type": "question", "name": "Check-in"},
            {"step_id": "step_003", "type": "end", "name": "Complete"},
        ],
        transitions=[
            {"from_step": "step_001", "to_step": "step_002", "type": "automatic"},
            {"from_step": "step_002", "to_step": "step_003", "type": "user_response"},
        ],
    )


@pytest.fixture
def another_template():
    """Create another template for testing."""
    return FlowTemplate(
        template_id="test_template_002",
        flow_type=FlowType.QUIZ_MENSAL,
        version="1.0.0",
        name="Another Template",
        description="Another sample template",
        steps=[{"step_id": "step_001", "type": "message", "name": "Start"}],
    )


class TestFlowTemplateRepositoryInitialization:
    """Test FlowTemplateRepository initialization."""

    def test_initialization(self, repository):
        """Test repository initializes correctly."""
        assert repository is not None
        assert repository.config is not None
        assert len(repository._templates) == 0
        assert len(repository._templates_by_type) == 0

    def test_cache_enabled_by_default(self, repository):
        """Test cache is enabled by configuration."""
        assert repository._cache_enabled is not None


class TestCreateTemplate:
    """Test template creation."""

    def test_create_template(self, repository, sample_template):
        """Test creating a template."""
        created = repository.create(sample_template)

        assert created is not None
        assert created.template_id == sample_template.template_id
        assert sample_template.template_id in repository._templates

    def test_create_template_indexes_by_type(self, repository, sample_template):
        """Test template is indexed by flow type."""
        repository.create(sample_template)

        assert sample_template.flow_type in repository._templates_by_type
        assert (
            sample_template.template_id
            in repository._templates_by_type[sample_template.flow_type]
        )

    def test_create_template_duplicate_error(self, repository, sample_template):
        """Test creating duplicate template raises error."""
        repository.create(sample_template)

        with pytest.raises(ValueError) as exc_info:
            repository.create(sample_template)

        assert "already exists" in str(exc_info.value).lower()

    def test_create_template_adds_to_cache(self, repository, sample_template):
        """Test created template is cached."""
        repository.create(sample_template)

        assert sample_template.template_id in repository._cached_templates

    def test_create_template_initializes_version_history(
        self, repository, sample_template
    ):
        """Test version history is initialized."""
        repository.create(sample_template)

        if repository.config.enable_template_versioning:
            assert sample_template.template_id in repository._template_versions
            assert len(repository._template_versions[sample_template.template_id]) == 1


class TestGetTemplate:
    """Test template retrieval."""

    def test_get_existing_template(self, repository, sample_template):
        """Test getting an existing template."""
        repository.create(sample_template)

        retrieved = repository.get(sample_template.template_id)

        assert retrieved is not None
        assert retrieved.template_id == sample_template.template_id

    def test_get_non_existent_template(self, repository):
        """Test getting non-existent template returns None."""
        retrieved = repository.get("non_existent_id")

        assert retrieved is None

    def test_get_template_from_cache(self, repository, sample_template):
        """Test template is retrieved from cache."""
        repository.create(sample_template)

        # Clear storage but keep cache
        del repository._templates[sample_template.template_id]

        # Should still get from cache
        if repository._cache_enabled:
            retrieved = repository.get(sample_template.template_id)
            assert retrieved is not None

    def test_get_template_updates_cache(self, repository, sample_template):
        """Test getting template updates cache."""
        repository.create(sample_template)
        repository._cached_templates.clear()

        retrieved = repository.get(sample_template.template_id)

        if repository._cache_enabled:
            assert sample_template.template_id in repository._cached_templates


class TestUpdateTemplate:
    """Test template updates."""

    def test_update_existing_template(self, repository, sample_template):
        """Test updating an existing template."""
        repository.create(sample_template)

        sample_template.name = "Updated Name"
        sample_template.version = "1.1.0"

        updated = repository.update(sample_template)

        assert updated.name == "Updated Name"
        assert updated.version == "1.1.0"

    def test_update_non_existent_template(self, repository, sample_template):
        """Test updating non-existent template raises error."""
        with pytest.raises(ValueError) as exc_info:
            repository.update(sample_template)

        assert "not found" in str(exc_info.value).lower()

    def test_update_sets_timestamp(self, repository, sample_template):
        """Test update sets updated_at timestamp."""
        repository.create(sample_template)
        original_updated_at = sample_template.updated_at

        updated = repository.update(sample_template)

        assert updated.updated_at > original_updated_at

    def test_update_adds_to_version_history(self, repository, sample_template):
        """Test update adds to version history."""
        repository.create(sample_template)

        sample_template.version = "1.1.0"
        repository.update(sample_template)

        if repository.config.enable_template_versioning:
            versions = repository._template_versions[sample_template.template_id]
            assert len(versions) == 2

    def test_update_limits_version_history(self, repository, sample_template):
        """Test version history is limited to max versions."""
        repository.create(sample_template)

        max_versions = repository.config.max_template_versions

        # Create more versions than max
        for i in range(max_versions + 5):
            sample_template.version = f"1.{i}.0"
            repository.update(sample_template)

        if repository.config.enable_template_versioning:
            versions = repository._template_versions[sample_template.template_id]
            assert len(versions) <= max_versions + 1  # +1 for initial

    def test_update_invalidates_cache(self, repository, sample_template):
        """Test update updates cache."""
        repository.create(sample_template)

        sample_template.name = "Updated Name"
        repository.update(sample_template)

        if repository._cache_enabled:
            cached = repository._cached_templates[sample_template.template_id]
            assert cached.name == "Updated Name"


class TestDeleteTemplate:
    """Test template deletion."""

    def test_delete_existing_template(self, repository, sample_template):
        """Test deleting an existing template."""
        repository.create(sample_template)

        result = repository.delete(sample_template.template_id)

        assert result is True
        assert sample_template.template_id not in repository._templates

    def test_delete_non_existent_template(self, repository):
        """Test deleting non-existent template returns False."""
        result = repository.delete("non_existent_id")

        assert result is False

    def test_delete_removes_from_type_index(self, repository, sample_template):
        """Test deletion removes from type index."""
        repository.create(sample_template)

        repository.delete(sample_template.template_id)

        type_templates = repository._templates_by_type.get(
            sample_template.flow_type, []
        )
        assert sample_template.template_id not in type_templates

    def test_delete_removes_version_history(self, repository, sample_template):
        """Test deletion removes version history."""
        repository.create(sample_template)

        repository.delete(sample_template.template_id)

        assert sample_template.template_id not in repository._template_versions

    def test_delete_removes_from_cache(self, repository, sample_template):
        """Test deletion removes from cache."""
        repository.create(sample_template)

        repository.delete(sample_template.template_id)

        assert sample_template.template_id not in repository._cached_templates


class TestListTemplates:
    """Test template listing."""

    def test_list_all_empty(self, repository):
        """Test listing all templates when empty."""
        templates = repository.list_all()

        assert len(templates) == 0

    def test_list_all_templates(self, repository, sample_template, another_template):
        """Test listing all templates."""
        repository.create(sample_template)
        repository.create(another_template)

        templates = repository.list_all()

        assert len(templates) == 2

    def test_list_all_excludes_inactive_by_default(self, repository, sample_template):
        """Test list_all excludes inactive templates by default."""
        sample_template.is_active = False
        repository.create(sample_template)

        templates = repository.list_all()

        assert len(templates) == 0

    def test_list_all_includes_inactive_when_requested(
        self, repository, sample_template
    ):
        """Test list_all includes inactive when requested."""
        sample_template.is_active = False
        repository.create(sample_template)

        templates = repository.list_all(include_inactive=True)

        assert len(templates) == 1

    def test_list_all_sorted_by_created_at(self, repository):
        """Test templates are sorted by created_at."""
        template1 = FlowTemplate(
            template_id="t1",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="T1",
            description="First",
            steps=[{"step_id": "s1", "type": "message", "name": "S1"}],
            created_at=now_sao_paulo_naive() - timedelta(hours=2),
        )
        template2 = FlowTemplate(
            template_id="t2",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="T2",
            description="Second",
            steps=[{"step_id": "s1", "type": "message", "name": "S1"}],
            created_at=now_sao_paulo_naive() - timedelta(hours=1),
        )

        repository.create(template1)
        repository.create(template2)

        templates = repository.list_all()

        assert templates[0].template_id == "t2"  # Most recent first


class TestListByType:
    """Test listing templates by type."""

    def test_list_by_type(self, repository, sample_template, another_template):
        """Test listing templates by flow type."""
        repository.create(sample_template)
        repository.create(another_template)

        daily_templates = repository.list_by_type(FlowType.DAILY_FOLLOW_UP)

        assert len(daily_templates) == 1
        assert daily_templates[0].flow_type == FlowType.DAILY_FOLLOW_UP

    def test_list_by_type_empty(self, repository):
        """Test listing by type when none exist."""
        templates = repository.list_by_type(FlowType.EMERGENCY_PROTOCOL)

        assert len(templates) == 0

    def test_list_by_type_excludes_inactive(self, repository, sample_template):
        """Test list_by_type excludes inactive templates."""
        sample_template.is_active = False
        repository.create(sample_template)

        templates = repository.list_by_type(FlowType.DAILY_FOLLOW_UP)

        assert len(templates) == 0

    def test_get_active_template_for_type(self, repository, sample_template):
        """Test getting active template for type."""
        repository.create(sample_template)

        active = repository.get_active_template_for_type(FlowType.DAILY_FOLLOW_UP)

        assert active is not None
        assert active.template_id == sample_template.template_id

    def test_get_active_template_for_type_none(self, repository):
        """Test getting active template when none exist."""
        active = repository.get_active_template_for_type(FlowType.EMERGENCY_PROTOCOL)

        assert active is None


class TestFindTemplates:
    """Test template search functionality."""

    def test_find_by_name_exact(self, repository, sample_template):
        """Test finding by exact name."""
        repository.create(sample_template)

        found = repository.find_by_name("Test Template")

        assert len(found) == 1
        assert found[0].template_id == sample_template.template_id

    def test_find_by_name_partial(self, repository, sample_template):
        """Test finding by partial name."""
        repository.create(sample_template)

        found = repository.find_by_name("Test")

        assert len(found) == 1

    def test_find_by_name_case_insensitive(self, repository, sample_template):
        """Test finding by name is case-insensitive."""
        repository.create(sample_template)

        found = repository.find_by_name("test template")

        assert len(found) == 1

    def test_find_by_name_no_matches(self, repository, sample_template):
        """Test finding with no matches."""
        repository.create(sample_template)

        found = repository.find_by_name("NonExistent")

        assert len(found) == 0

    def test_exists_true(self, repository, sample_template):
        """Test exists returns True for existing template."""
        repository.create(sample_template)

        assert repository.exists(sample_template.template_id) is True

    def test_exists_false(self, repository):
        """Test exists returns False for non-existent template."""
        assert repository.exists("non_existent") is False


class TestVersionManagement:
    """Test version management functionality."""

    def test_get_specific_version(self, repository, sample_template):
        """Test getting specific version of template."""
        repository.create(sample_template)

        sample_template.version = "1.1.0"
        repository.update(sample_template)

        v1 = repository.get_version(sample_template.template_id, "1.0.0")

        if repository.config.enable_template_versioning:
            assert v1 is not None
            assert v1.version == "1.0.0"

    def test_get_non_existent_version(self, repository, sample_template):
        """Test getting non-existent version."""
        repository.create(sample_template)

        version = repository.get_version(sample_template.template_id, "9.9.9")

        assert version is None

    def test_list_versions(self, repository, sample_template):
        """Test listing all versions of template."""
        repository.create(sample_template)

        sample_template.version = "1.1.0"
        repository.update(sample_template)

        sample_template.version = "1.2.0"
        repository.update(sample_template)

        versions = repository.list_versions(sample_template.template_id)

        if repository.config.enable_template_versioning:
            assert len(versions) >= 2

    def test_get_latest_version(self, repository, sample_template):
        """Test getting latest version."""
        repository.create(sample_template)

        sample_template.version = "1.1.0"
        repository.update(sample_template)

        latest = repository.get_latest_version(sample_template.template_id)

        assert latest is not None
        assert latest.version == "1.1.0"


class TestCacheManagement:
    """Test cache management functionality."""

    def test_clear_cache(self, repository, sample_template):
        """Test clearing cache."""
        repository.create(sample_template)

        repository.clear_cache()

        assert len(repository._cached_templates) == 0

    def test_invalidate_cache(self, repository, sample_template):
        """Test invalidating specific template cache."""
        repository.create(sample_template)

        repository.invalidate_cache(sample_template.template_id)

        assert sample_template.template_id not in repository._cached_templates


class TestBulkOperations:
    """Test bulk operations."""

    def test_bulk_create(self, repository, sample_template, another_template):
        """Test bulk creating templates."""
        templates = [sample_template, another_template]

        created = repository.bulk_create(templates)

        assert len(created) == 2

    def test_bulk_create_with_duplicate(self, repository, sample_template, another_template):
        """Test bulk create handles duplicates gracefully."""
        repository.create(sample_template)

        # Try to bulk create including existing template
        templates = [sample_template, another_template]

        created = repository.bulk_create(templates)

        # Should create only the new one
        assert len(created) == 1

    def test_bulk_update(self, repository):
        """Test bulk updating templates."""
        t1 = FlowTemplate(
            template_id="t1",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="T1",
            description="First",
            steps=[{"step_id": "s1", "type": "message", "name": "S1"}],
        )
        t2 = FlowTemplate(
            template_id="t2",
            flow_type=FlowType.DAILY_FOLLOW_UP,
            name="T2",
            description="Second",
            steps=[{"step_id": "s1", "type": "message", "name": "S1"}],
        )

        repository.create(t1)
        repository.create(t2)

        t1.name = "Updated T1"
        t2.name = "Updated T2"

        updated = repository.bulk_update([t1, t2])

        assert len(updated) == 2


class TestImportExport:
    """Test import/export functionality."""

    def test_export_template(self, repository, sample_template):
        """Test exporting template."""
        repository.create(sample_template)

        exported = repository.export_template(sample_template.template_id)

        assert exported is not None
        assert isinstance(exported, dict)
        assert exported["template_id"] == sample_template.template_id

    def test_export_non_existent_template(self, repository):
        """Test exporting non-existent template."""
        exported = repository.export_template("non_existent")

        assert exported is None

    def test_import_template(self, repository, sample_template):
        """Test importing template."""
        template_data = sample_template.model_dump()

        imported = repository.import_template(template_data)

        assert imported is not None
        assert imported.template_id == sample_template.template_id

    def test_export_all(self, repository, sample_template, another_template):
        """Test exporting all templates."""
        repository.create(sample_template)
        repository.create(another_template)

        exported = repository.export_all()

        assert len(exported) == 2

    def test_import_all(self, repository):
        """Test importing multiple templates."""
        templates_data = [
            {
                "template_id": "t1",
                "flow_type": "daily_follow_up",
                "version": "1.0.0",
                "name": "T1",
                "description": "First",
                "steps": [{"step_id": "s1", "type": "message", "name": "S1"}],
            },
            {
                "template_id": "t2",
                "flow_type": "quiz_mensal",
                "version": "1.0.0",
                "name": "T2",
                "description": "Second",
                "steps": [{"step_id": "s1", "type": "message", "name": "S1"}],
            },
        ]

        imported = repository.import_all(templates_data)

        assert len(imported) == 2


class TestStatistics:
    """Test repository statistics."""

    def test_get_stats_empty(self, repository):
        """Test getting stats when empty."""
        stats = repository.get_stats()

        assert stats["total_templates"] == 0
        assert stats["active_templates"] == 0

    def test_get_stats_with_templates(
        self, repository, sample_template, another_template
    ):
        """Test getting stats with templates."""
        repository.create(sample_template)

        another_template.is_active = False
        repository.create(another_template)

        stats = repository.get_stats()

        assert stats["total_templates"] == 2
        assert stats["active_templates"] == 1
        assert stats["inactive_templates"] == 1

    def test_get_stats_by_type(self, repository, sample_template, another_template):
        """Test stats include breakdown by type."""
        repository.create(sample_template)
        repository.create(another_template)

        stats = repository.get_stats()

        assert "templates_by_type" in stats
        assert FlowType.DAILY_FOLLOW_UP.value in stats["templates_by_type"]


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_update_changes_flow_type(self, repository, sample_template):
        """Test updating template with different flow type."""
        repository.create(sample_template)

        sample_template.flow_type = FlowType.QUIZ_MENSAL
        repository.update(sample_template)

        # Should be indexed under new type
        assert (
            sample_template.template_id
            in repository._templates_by_type[FlowType.QUIZ_MENSAL]
        )

    def test_cache_disabled(self, repository, sample_template):
        """Test operations with cache disabled."""
        repository._cache_enabled = False

        repository.create(sample_template)

        # Should not be in cache
        assert sample_template.template_id not in repository._cached_templates
