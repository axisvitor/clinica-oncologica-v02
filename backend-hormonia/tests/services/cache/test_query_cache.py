"""
Tests for QueryCache.

Tests all functionality of the specialized query cache wrapper.

Author: Backend Team
Date: 2025-01-20
"""

import pytest
from uuid import uuid4
from datetime import datetime

from app.services.cache.specialized.query_cache import (
    QueryCache,
    get_query_cache,
)
from app.services.ai.cache_layer import CacheLayer, CacheStrategy


@pytest.fixture
async def query_cache():
    """Create query cache instance for testing."""
    cache_layer = CacheLayer(strategy=CacheStrategy.MEMORY)
    await cache_layer.initialize()
    cache = QueryCache(cache_layer=cache_layer)
    yield cache
    await cache_layer.close()


@pytest.fixture
def sample_entity():
    """Sample entity data."""
    return {
        "id": str(uuid4()),
        "name": "John Doe",
        "email": "john@example.com",
        "created_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def sample_list_items():
    """Sample list of items."""
    return [
        {"id": str(uuid4()), "name": "Item 1"},
        {"id": str(uuid4()), "name": "Item 2"},
        {"id": str(uuid4()), "name": "Item 3"},
    ]


class TestEntityCaching:
    """Test entity caching functionality."""

    @pytest.mark.asyncio
    async def test_set_and_get_entity(self, query_cache, sample_entity):
        """Test setting and getting an entity."""
        entity_id = uuid4()

        # Set entity
        success = await query_cache.set_entity("patient", entity_id, sample_entity)
        assert success is True

        # Get entity
        result = await query_cache.get_entity("patient", entity_id)
        assert result is not None
        assert result["name"] == "John Doe"
        assert result["email"] == "john@example.com"

    @pytest.mark.asyncio
    async def test_entity_with_relations(self, query_cache, sample_entity):
        """Test entity with included relations."""
        entity_id = uuid4()
        relations = ["treatments", "appointments"]

        # Set entity with relations
        await query_cache.set_entity(
            "patient", entity_id, sample_entity, include_relations=relations
        )

        # Get entity with same relations
        result = await query_cache.get_entity(
            "patient", entity_id, include_relations=relations
        )
        assert result is not None

        # Different relations should not exist
        result_no_relations = await query_cache.get_entity("patient", entity_id)
        assert result_no_relations is None

    @pytest.mark.asyncio
    async def test_invalidate_entity(self, query_cache, sample_entity):
        """Test entity invalidation."""
        entity_id = uuid4()

        # Set entity (with and without relations)
        await query_cache.set_entity("patient", entity_id, sample_entity)
        await query_cache.set_entity(
            "patient", entity_id, sample_entity, include_relations=["treatments"]
        )

        # Invalidate all versions
        deleted = await query_cache.invalidate_entity("patient", entity_id)
        assert deleted >= 2

        # Verify they're gone
        result = await query_cache.get_entity("patient", entity_id)
        assert result is None


class TestListCaching:
    """Test list query caching functionality."""

    @pytest.mark.asyncio
    async def test_set_and_get_list(self, query_cache, sample_list_items):
        """Test setting and getting a list."""
        total_count = 100

        # Set list
        success = await query_cache.set_list(
            "patient", sample_list_items, total_count, page=1, page_size=20
        )
        assert success is True

        # Get list
        result = await query_cache.get_list("patient", page=1, page_size=20)
        assert result is not None
        items, total = result
        assert len(items) == 3
        assert total == 100

    @pytest.mark.asyncio
    async def test_list_with_filters(self, query_cache, sample_list_items):
        """Test list with filters."""
        filters = {"status": "active", "age_min": 18}
        total_count = 50

        # Set list with filters
        await query_cache.set_list(
            "patient", sample_list_items, total_count, filters=filters
        )

        # Get list with same filters
        result = await query_cache.get_list("patient", filters=filters)
        assert result is not None
        items, total = result
        assert total == 50

        # Different filters should not exist
        different_filters = {"status": "inactive"}
        result_diff = await query_cache.get_list("patient", filters=different_filters)
        assert result_diff is None

    @pytest.mark.asyncio
    async def test_list_with_sorting(self, query_cache, sample_list_items):
        """Test list with sorting."""
        sorting = {"name": "asc", "created_at": "desc"}

        # Set list with sorting
        await query_cache.set_list("patient", sample_list_items, 100, sorting=sorting)

        # Get list with same sorting
        result = await query_cache.get_list("patient", sorting=sorting)
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_pagination(self, query_cache, sample_list_items):
        """Test list pagination."""
        # Set different pages
        await query_cache.set_list(
            "patient", sample_list_items, 100, page=1, page_size=20
        )
        await query_cache.set_list(
            "patient", sample_list_items, 100, page=2, page_size=20
        )

        # Get different pages
        result_page1 = await query_cache.get_list("patient", page=1, page_size=20)
        result_page2 = await query_cache.get_list("patient", page=2, page_size=20)

        assert result_page1 is not None
        assert result_page2 is not None

    @pytest.mark.asyncio
    async def test_invalidate_lists(self, query_cache, sample_list_items):
        """Test invalidating all lists for entity type."""
        # Set multiple lists
        await query_cache.set_list("patient", sample_list_items, 100)
        await query_cache.set_list(
            "patient", sample_list_items, 50, filters={"status": "active"}
        )

        # Invalidate all
        deleted = await query_cache.invalidate_lists("patient")
        assert deleted >= 2


class TestAggregationCaching:
    """Test aggregation query caching functionality."""

    @pytest.mark.asyncio
    async def test_set_and_get_aggregation(self, query_cache):
        """Test setting and getting an aggregation."""
        aggregation_result = {
            "count": 100,
            "sum": 5000,
            "avg": 50,
            "min": 10,
            "max": 200,
        }

        # Set aggregation
        success = await query_cache.set_aggregation(
            "patient", "count", aggregation_result
        )
        assert success is True

        # Get aggregation
        result = await query_cache.get_aggregation("patient", "count")
        assert result is not None
        assert result["count"] == 100
        assert result["avg"] == 50

    @pytest.mark.asyncio
    async def test_aggregation_with_filters(self, query_cache):
        """Test aggregation with filters."""
        aggregation_result = {"count": 30}
        filters = {"status": "active", "city": "São Paulo"}

        # Set aggregation with filters
        await query_cache.set_aggregation(
            "patient", "count", aggregation_result, filters=filters
        )

        # Get aggregation with same filters
        result = await query_cache.get_aggregation("patient", "count", filters=filters)
        assert result is not None
        assert result["count"] == 30

    @pytest.mark.asyncio
    async def test_aggregation_with_group_by(self, query_cache):
        """Test aggregation with grouping."""
        aggregation_result = {
            "groups": [
                {"status": "active", "count": 60},
                {"status": "inactive", "count": 40},
            ]
        }
        group_by = ["status"]

        # Set aggregation with group by
        await query_cache.set_aggregation(
            "patient", "count", aggregation_result, group_by=group_by
        )

        # Get aggregation with same group by
        result = await query_cache.get_aggregation(
            "patient", "count", group_by=group_by
        )
        assert result is not None
        assert len(result["groups"]) == 2

    @pytest.mark.asyncio
    async def test_invalidate_aggregations(self, query_cache):
        """Test invalidating all aggregations."""
        # Set multiple aggregations
        await query_cache.set_aggregation("patient", "count", {"count": 100})
        await query_cache.set_aggregation("patient", "sum", {"sum": 5000})

        # Invalidate all
        deleted = await query_cache.invalidate_aggregations("patient")
        assert deleted >= 2


class TestSearchCaching:
    """Test search query caching functionality."""

    @pytest.mark.asyncio
    async def test_set_and_get_search(self, query_cache, sample_list_items):
        """Test setting and getting search results."""
        search_term = "john"
        total_count = 25

        # Set search
        success = await query_cache.set_search(
            "patient", search_term, sample_list_items, total_count
        )
        assert success is True

        # Get search
        result = await query_cache.get_search("patient", search_term)
        assert result is not None
        items, total = result
        assert len(items) == 3
        assert total == 25

    @pytest.mark.asyncio
    async def test_search_with_filters(self, query_cache, sample_list_items):
        """Test search with filters."""
        search_term = "john"
        filters = {"status": "active"}

        # Set search with filters
        await query_cache.set_search(
            "patient", search_term, sample_list_items, 10, filters=filters
        )

        # Get search with same filters
        result = await query_cache.get_search("patient", search_term, filters=filters)
        assert result is not None

    @pytest.mark.asyncio
    async def test_invalidate_searches(self, query_cache, sample_list_items):
        """Test invalidating all searches."""
        # Set multiple searches
        await query_cache.set_search("patient", "john", sample_list_items, 25)
        await query_cache.set_search("patient", "jane", sample_list_items, 15)

        # Invalidate all
        deleted = await query_cache.invalidate_searches("patient")
        assert deleted >= 2


class TestSmartInvalidation:
    """Test smart invalidation functionality."""

    @pytest.mark.asyncio
    async def test_invalidate_entity_related(
        self, query_cache, sample_entity, sample_list_items
    ):
        """Test invalidating all queries related to an entity."""
        entity_id = uuid4()

        # Set various queries
        await query_cache.set_entity("patient", entity_id, sample_entity)
        await query_cache.set_list("patient", sample_list_items, 100)
        await query_cache.set_aggregation("patient", "count", {"count": 100})
        await query_cache.set_search("patient", "john", sample_list_items, 25)

        # Invalidate all related
        stats = await query_cache.invalidate_entity_related("patient", entity_id)

        assert stats["total"] >= 4
        assert "entities" in stats
        assert "lists" in stats
        assert "aggregations" in stats
        assert "searches" in stats

    @pytest.mark.asyncio
    async def test_invalidate_entity_type_related(self, query_cache, sample_list_items):
        """Test invalidating all queries for entity type."""
        # Set various queries
        await query_cache.set_list("patient", sample_list_items, 100)
        await query_cache.set_aggregation("patient", "count", {"count": 100})
        await query_cache.set_search("patient", "john", sample_list_items, 25)

        # Invalidate all for type
        stats = await query_cache.invalidate_entity_related("patient")

        assert stats["total"] >= 3
        assert stats["lists"] >= 1
        assert stats["aggregations"] >= 1
        assert stats["searches"] >= 1


class TestBulkOperations:
    """Test bulk operations."""

    @pytest.mark.asyncio
    async def test_clear_all(self, query_cache, sample_entity, sample_list_items):
        """Test clearing all query cache."""
        entity_id = uuid4()

        # Set various items
        await query_cache.set_entity("patient", entity_id, sample_entity)
        await query_cache.set_list("patient", sample_list_items, 100)
        await query_cache.set_aggregation("patient", "count", {"count": 100})

        # Clear all
        deleted = await query_cache.clear_all()
        assert deleted >= 3

        # Verify they're gone
        result = await query_cache.get_entity("patient", entity_id)
        assert result is None


class TestCacheStats:
    """Test cache statistics."""

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, query_cache, sample_entity, sample_list_items):
        """Test getting cache statistics."""
        entity_id = uuid4()

        # Set some data
        await query_cache.set_entity("patient", entity_id, sample_entity)
        await query_cache.set_list("patient", sample_list_items, 100)
        await query_cache.set_aggregation("patient", "count", {"count": 100})

        # Get stats
        stats = await query_cache.get_cache_stats()
        assert "strategy" in stats
        assert "namespaces" in stats
        assert stats["namespaces"]["entities"] >= 1
        assert stats["namespaces"]["lists"] >= 1
        assert stats["namespaces"]["aggregations"] >= 1


class TestKeyGeneration:
    """Test query key generation."""

    @pytest.mark.asyncio
    async def test_deterministic_key_generation(self, query_cache, sample_list_items):
        """Test that same parameters generate same cache key."""
        filters = {"status": "active", "city": "São Paulo"}

        # Set list with filters
        await query_cache.set_list("patient", sample_list_items, 100, filters=filters)

        # Get with same filters (order doesn't matter)
        filters_reordered = {"city": "São Paulo", "status": "active"}
        result = await query_cache.get_list("patient", filters=filters_reordered)

        # Should get same cached result
        assert result is not None


class TestSingleton:
    """Test singleton pattern."""

    def test_get_query_cache_singleton(self):
        """Test that get_query_cache returns singleton."""
        cache1 = get_query_cache()
        cache2 = get_query_cache()
        assert cache1 is cache2


class TestTTLs:
    """Test TTL functionality."""

    @pytest.mark.asyncio
    async def test_custom_ttl(self, query_cache, sample_entity):
        """Test custom TTL override."""
        entity_id = uuid4()

        # Set entity with custom TTL
        success = await query_cache.set_entity(
            "patient", entity_id, sample_entity, ttl=1
        )
        assert success is True

        # Immediately should exist
        result = await query_cache.get_entity("patient", entity_id)
        assert result is not None
