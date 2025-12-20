"""
Tests for CacheInvalidator.

Tests all functionality of the centralized cache invalidation system.

Author: Backend Team
Date: 2025-01-20
"""

import pytest
from uuid import uuid4
from datetime import datetime

from app.services.cache.invalidation import (
    CacheInvalidator,
    InvalidationStrategy,
    get_cache_invalidator,
)
from app.services.cache.specialized import (
    JWTCache,
    TemplateCache,
    AnalyticsCache,
    QueryCache,
)
from app.services.ai.cache_layer import CacheLayer, CacheStrategy


@pytest.fixture
async def cache_layer():
    """Create cache layer for testing."""
    cache = CacheLayer(strategy=CacheStrategy.MEMORY)
    await cache.initialize()
    yield cache
    await cache.close()


@pytest.fixture
async def jwt_cache(cache_layer):
    """Create JWT cache instance."""
    return JWTCache(cache_layer=cache_layer)


@pytest.fixture
async def template_cache(cache_layer):
    """Create template cache instance."""
    return TemplateCache(cache_layer=cache_layer)


@pytest.fixture
async def analytics_cache(cache_layer):
    """Create analytics cache instance."""
    return AnalyticsCache(cache_layer=cache_layer)


@pytest.fixture
async def query_cache(cache_layer):
    """Create query cache instance."""
    return QueryCache(cache_layer=cache_layer)


@pytest.fixture
async def invalidator(jwt_cache, template_cache, analytics_cache, query_cache):
    """Create invalidator instance."""
    return CacheInvalidator(
        jwt_cache=jwt_cache,
        template_cache=template_cache,
        analytics_cache=analytics_cache,
        query_cache=query_cache,
    )


@pytest.fixture
def sample_entity():
    """Sample entity data."""
    return {
        "id": str(uuid4()),
        "name": "Test Entity",
        "created_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def sample_list_items():
    """Sample list items."""
    return [
        {"id": str(uuid4()), "name": "Item 1"},
        {"id": str(uuid4()), "name": "Item 2"},
    ]


class TestEntityInvalidation:
    """Test entity invalidation functionality."""

    @pytest.mark.asyncio
    async def test_invalidate_entity_immediate(
        self, invalidator, query_cache, sample_entity
    ):
        """Test immediate entity invalidation."""
        entity_id = uuid4()

        # Set entity and related caches
        await query_cache.set_entity("patient", entity_id, sample_entity)
        await query_cache.set_list("patient", [sample_entity], 1)

        # Invalidate entity
        stats = await invalidator.invalidate_entity(
            "patient", entity_id, InvalidationStrategy.IMMEDIATE
        )

        assert stats["entity_type"] == "patient"
        assert stats["entity_id"] == str(entity_id)
        assert stats["total_deleted"] >= 1

    @pytest.mark.asyncio
    async def test_invalidate_entity_cascade(
        self, invalidator, query_cache, analytics_cache, sample_entity
    ):
        """Test cascade entity invalidation."""
        entity_id = uuid4()

        # Set entity, list, and analytics
        await query_cache.set_entity("patient", entity_id, sample_entity)
        await query_cache.set_list("patient", [sample_entity], 1)
        await analytics_cache.set_metric("patient_count", {"value": 100})

        # Invalidate with cascade
        stats = await invalidator.invalidate_entity(
            "patient", entity_id, InvalidationStrategy.CASCADE
        )

        assert "caches" in stats
        assert "query" in stats["caches"]
        assert "analytics" in stats["caches"]
        assert stats["total_deleted"] >= 1

    @pytest.mark.asyncio
    async def test_invalidate_entity_logs_action(self, invalidator, query_cache):
        """Test that invalidation is logged."""
        entity_id = uuid4()

        # Invalidate
        await invalidator.invalidate_entity("patient", entity_id)

        # Check log
        stats = await invalidator.get_invalidation_stats()
        assert stats["total_invalidations"] >= 1


class TestEntityTypeInvalidation:
    """Test entity type invalidation functionality."""

    @pytest.mark.asyncio
    async def test_invalidate_entity_type(
        self, invalidator, query_cache, sample_entity, sample_list_items
    ):
        """Test invalidating all caches for entity type."""
        # Set multiple entities
        entity_id_1 = uuid4()
        entity_id_2 = uuid4()
        await query_cache.set_entity("patient", entity_id_1, sample_entity)
        await query_cache.set_entity("patient", entity_id_2, sample_entity)
        await query_cache.set_list("patient", sample_list_items, 2)

        # Invalidate entire type
        stats = await invalidator.invalidate_entity_type("patient")

        assert stats["entity_type"] == "patient"
        assert "caches" in stats
        assert stats["total_deleted"] >= 3

    @pytest.mark.asyncio
    async def test_invalidate_entity_type_cascade(
        self, invalidator, query_cache, analytics_cache
    ):
        """Test cascade invalidation for entity type."""
        # Set queries and analytics
        await query_cache.set_aggregation("patient", "count", {"count": 100})
        await analytics_cache.set_report("patient_summary", {"total": 100})

        # Invalidate with cascade
        stats = await invalidator.invalidate_entity_type(
            "patient", InvalidationStrategy.CASCADE
        )

        assert "analytics" in stats["caches"]


class TestUserInvalidation:
    """Test user invalidation functionality."""

    @pytest.mark.asyncio
    async def test_invalidate_user_without_logout(
        self, invalidator, jwt_cache, analytics_cache
    ):
        """Test invalidating user caches without logout."""
        user_id = uuid4()

        # Set user caches
        await analytics_cache.set_dashboard("user_dashboard", {"data": "test"}, user_id)

        # Invalidate without logout
        stats = await invalidator.invalidate_user(user_id, logout=False)

        assert stats["user_id"] == str(user_id)
        assert stats["logout"] is False

    @pytest.mark.asyncio
    async def test_invalidate_user_with_logout(self, invalidator, jwt_cache):
        """Test invalidating user with logout."""
        user_id = uuid4()

        # Set JWT token
        await jwt_cache.cache_token(
            "access_token",
            {"user_id": str(user_id), "token": "test_token"},
            user_id=user_id,
        )

        # Invalidate with logout
        stats = await invalidator.invalidate_user(user_id, logout=True)

        assert stats["logout"] is True
        assert "jwt" in stats["caches"]


class TestBulkInvalidation:
    """Test bulk invalidation functionality."""

    @pytest.mark.asyncio
    async def test_invalidate_multiple_entities(
        self, invalidator, query_cache, sample_entity
    ):
        """Test invalidating multiple entities at once."""
        entity_ids = [uuid4(), uuid4(), uuid4()]

        # Set entities
        for entity_id in entity_ids:
            await query_cache.set_entity("patient", entity_id, sample_entity)

        # Invalidate multiple
        stats = await invalidator.invalidate_multiple_entities("patient", entity_ids)

        assert stats["entity_count"] == 3
        assert len(stats["entities"]) == 3
        assert stats["total_deleted"] >= 3


class TestNamespaceInvalidation:
    """Test namespace invalidation functionality."""

    @pytest.mark.asyncio
    async def test_invalidate_analytics_metrics_namespace(
        self, invalidator, analytics_cache
    ):
        """Test invalidating analytics metrics namespace."""
        # Set metrics
        await analytics_cache.set_metric("metric1", {"value": 100})
        await analytics_cache.set_metric("metric2", {"value": 200})

        # Invalidate namespace
        stats = await invalidator.invalidate_namespace("analytics", "metrics")

        assert stats["cache_type"] == "analytics"
        assert stats["namespace"] == "metrics"
        assert stats["deleted"] >= 2

    @pytest.mark.asyncio
    async def test_invalidate_analytics_reports_namespace(
        self, invalidator, analytics_cache
    ):
        """Test invalidating analytics reports namespace."""
        # Set reports
        await analytics_cache.set_report("report1", {"data": "test"})
        await analytics_cache.set_report("report2", {"data": "test"})

        # Invalidate namespace
        stats = await invalidator.invalidate_namespace("analytics", "reports")

        assert stats["deleted"] >= 2

    @pytest.mark.asyncio
    async def test_invalidate_template_namespace(self, invalidator, template_cache):
        """Test invalidating template namespace."""
        # Set templates
        await template_cache.cache_template("email", "welcome", "Welcome {{name}}")

        # Invalidate namespace
        stats = await invalidator.invalidate_namespace("template", "email")

        assert stats["cache_type"] == "template"
        assert stats["namespace"] == "email"


class TestGlobalInvalidation:
    """Test global invalidation functionality."""

    @pytest.mark.asyncio
    async def test_clear_all_caches(
        self, invalidator, jwt_cache, template_cache, analytics_cache, query_cache
    ):
        """Test clearing all caches."""
        # Set data in all caches
        await jwt_cache.cache_token("test", {"token": "value"})
        await template_cache.cache_template("email", "test", "content")
        await analytics_cache.set_metric("test", {"value": 100})
        await query_cache.set_aggregation("patient", "count", {"count": 100})

        # Clear all
        stats = await invalidator.clear_all_caches()

        assert stats["operation"] == "clear_all"
        assert "caches" in stats
        assert stats["total_deleted"] >= 4

    @pytest.mark.asyncio
    async def test_clear_all_with_exclusions(
        self, invalidator, jwt_cache, template_cache
    ):
        """Test clearing all caches with exclusions."""
        # Set data
        await jwt_cache.cache_token("test", {"token": "value"})
        await template_cache.cache_template("email", "test", "content")

        # Clear all except JWT
        stats = await invalidator.clear_all_caches(exclude={"jwt"})

        assert "jwt" not in stats["caches"]
        assert "template" in stats["caches"]


class TestSmartInvalidation:
    """Test smart invalidation functionality."""

    @pytest.mark.asyncio
    async def test_invalidate_on_create(
        self, invalidator, query_cache, sample_list_items
    ):
        """Test smart invalidation when entity is created."""
        # Set lists and aggregations
        await query_cache.set_list("patient", sample_list_items, 2)
        await query_cache.set_aggregation("patient", "count", {"count": 2})

        # Invalidate on create
        entity_id = uuid4()
        stats = await invalidator.invalidate_on_create("patient", entity_id)

        assert stats["operation"] == "on_create"
        assert "lists" in stats["caches"]
        assert "aggregations" in stats["caches"]

    @pytest.mark.asyncio
    async def test_invalidate_on_update(self, invalidator, query_cache, sample_entity):
        """Test smart invalidation when entity is updated."""
        entity_id = uuid4()

        # Set entity
        await query_cache.set_entity("patient", entity_id, sample_entity)

        # Invalidate on update
        stats = await invalidator.invalidate_on_update("patient", entity_id)

        assert stats["entity_id"] == str(entity_id)
        assert stats["total_deleted"] >= 1

    @pytest.mark.asyncio
    async def test_invalidate_on_delete(
        self, invalidator, query_cache, sample_entity, sample_list_items
    ):
        """Test smart invalidation when entity is deleted."""
        entity_id = uuid4()

        # Set entity and lists
        await query_cache.set_entity("patient", entity_id, sample_entity)
        await query_cache.set_list("patient", sample_list_items, 2)

        # Invalidate on delete
        stats = await invalidator.invalidate_on_delete("patient", entity_id)

        assert stats["strategy"] == InvalidationStrategy.CASCADE
        assert stats["total_deleted"] >= 2


class TestInvalidationLogging:
    """Test invalidation logging and stats."""

    @pytest.mark.asyncio
    async def test_logging_tracks_invalidations(self, invalidator, query_cache):
        """Test that invalidations are tracked."""
        entity_id = uuid4()

        # Clear previous log
        invalidator.clear_log()

        # Perform invalidations
        await invalidator.invalidate_entity("patient", entity_id)
        await invalidator.invalidate_entity_type("doctor")

        # Check stats
        stats = await invalidator.get_invalidation_stats()
        assert stats["total_invalidations"] == 2

    @pytest.mark.asyncio
    async def test_stats_count_by_operation(self, invalidator, query_cache):
        """Test stats count by operation type."""
        entity_id = uuid4()

        # Clear previous log
        invalidator.clear_log()

        # Perform different operations
        await invalidator.invalidate_on_create("patient", entity_id)
        await invalidator.invalidate_on_update("patient", entity_id)

        # Check stats
        stats = await invalidator.get_invalidation_stats()
        assert "by_operation" in stats
        assert stats["by_operation"]["on_create"] >= 1

    @pytest.mark.asyncio
    async def test_stats_count_by_entity_type(self, invalidator, query_cache):
        """Test stats count by entity type."""
        # Clear previous log
        invalidator.clear_log()

        # Invalidate different types
        await invalidator.invalidate_entity_type("patient")
        await invalidator.invalidate_entity_type("patient")
        await invalidator.invalidate_entity_type("doctor")

        # Check stats
        stats = await invalidator.get_invalidation_stats()
        assert "by_entity_type" in stats
        assert stats["by_entity_type"]["patient"] == 2
        assert stats["by_entity_type"]["doctor"] == 1

    @pytest.mark.asyncio
    async def test_recent_invalidations(self, invalidator, query_cache):
        """Test getting recent invalidations."""
        entity_id = uuid4()

        # Clear previous log
        invalidator.clear_log()

        # Perform invalidation
        await invalidator.invalidate_entity("patient", entity_id)

        # Check recent
        stats = await invalidator.get_invalidation_stats()
        assert "recent_invalidations" in stats
        assert len(stats["recent_invalidations"]) >= 1

    def test_clear_log(self, invalidator):
        """Test clearing invalidation log."""
        # Clear log
        invalidator.clear_log()

        # Check it's empty (through internal access since this is a test)
        assert len(invalidator._invalidation_log) == 0


class TestSingleton:
    """Test singleton pattern."""

    def test_get_cache_invalidator_singleton(self):
        """Test that get_cache_invalidator returns singleton."""
        invalidator1 = get_cache_invalidator()
        invalidator2 = get_cache_invalidator()
        assert invalidator1 is invalidator2


class TestInvalidationStrategies:
    """Test different invalidation strategies."""

    @pytest.mark.asyncio
    async def test_immediate_strategy(self, invalidator, query_cache, sample_entity):
        """Test immediate invalidation strategy."""
        entity_id = uuid4()
        await query_cache.set_entity("patient", entity_id, sample_entity)

        stats = await invalidator.invalidate_entity(
            "patient", entity_id, InvalidationStrategy.IMMEDIATE
        )

        assert stats["strategy"] == InvalidationStrategy.IMMEDIATE

    @pytest.mark.asyncio
    async def test_cascade_strategy(self, invalidator, query_cache, sample_entity):
        """Test cascade invalidation strategy."""
        entity_id = uuid4()
        await query_cache.set_entity("patient", entity_id, sample_entity)

        stats = await invalidator.invalidate_entity(
            "patient", entity_id, InvalidationStrategy.CASCADE
        )

        assert stats["strategy"] == InvalidationStrategy.CASCADE


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_entity(self, invalidator):
        """Test invalidating non-existent entity."""
        entity_id = uuid4()

        # Should not raise error
        stats = await invalidator.invalidate_entity("patient", entity_id)
        assert stats["total_deleted"] >= 0

    @pytest.mark.asyncio
    async def test_invalidate_empty_entity_type(self, invalidator):
        """Test invalidating entity type with no cached data."""
        # Should not raise error
        stats = await invalidator.invalidate_entity_type("nonexistent")
        assert stats["total_deleted"] >= 0

    @pytest.mark.asyncio
    async def test_clear_all_empty_caches(self, invalidator):
        """Test clearing already empty caches."""
        # Should not raise error
        stats = await invalidator.clear_all_caches()
        assert "total_deleted" in stats
