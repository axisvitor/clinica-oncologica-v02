"""
Query Cache Module.

Specialized cache wrapper for database query results.
Provides optimized caching for expensive queries with smart invalidation.

Author: Backend Team
Date: 2025-01-20
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
import hashlib
import json

from app.services.ai.cache_layer import CacheLayer, get_cache_layer


class QueryCache:
    """
    Specialized cache for database query results.

    Features:
    - Query result caching with automatic key generation
    - Smart invalidation based on entity changes
    - Pagination support
    - Query statistics tracking
    - Automatic key namespacing
    """

    def __init__(self, cache_layer: Optional[CacheLayer] = None):
        """
        Initialize Query Cache.

        Args:
            cache_layer: Optional CacheLayer instance. If not provided, uses singleton.
        """
        self.cache = cache_layer or get_cache_layer()
        self.prefix = "query"

        # TTLs específicos para queries
        self.simple_query_ttl = 300  # 5 minutos para queries simples
        self.complex_query_ttl = 900  # 15 minutos para queries complexas
        self.aggregation_ttl = 1800  # 30 minutos para agregações
        self.list_query_ttl = 600  # 10 minutos para listagens

    def _make_key(self, namespace: str, key: str) -> str:
        """
        Create namespaced cache key.

        Args:
            namespace: Cache namespace (queries, lists, aggregations)
            key: Cache key

        Returns:
            Namespaced key
        """
        return f"{self.prefix}:{namespace}:{key}"

    def _generate_query_key(
        self, entity_type: str, query_params: Dict[str, Any], operation: str = "query"
    ) -> str:
        """
        Generate deterministic cache key from query parameters.

        Args:
            entity_type: Type of entity (patients, doctors, etc)
            query_params: Query parameters (filters, sorting, etc)
            operation: Operation type (query, list, count, etc)

        Returns:
            Generated cache key
        """
        # Sort params for deterministic key
        sorted_params = json.dumps(query_params, sort_keys=True)

        # Hash params for shorter key
        params_hash = hashlib.md5(sorted_params.encode()).hexdigest()[:12]

        return f"{entity_type}:{operation}:{params_hash}"

    # ==================== SINGLE ENTITY QUERIES ====================

    async def get_entity(
        self,
        entity_type: str,
        entity_id: UUID,
        include_relations: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached entity by ID.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            include_relations: Optional list of relations to include

        Returns:
            Cached entity data or None
        """
        key = f"{entity_type}:{entity_id}"
        if include_relations:
            relations_str = ":".join(sorted(include_relations))
            key = f"{key}:{relations_str}"

        return await self.cache.get(self._make_key("entities", key))

    async def set_entity(
        self,
        entity_type: str,
        entity_id: UUID,
        data: Dict[str, Any],
        include_relations: Optional[List[str]] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache entity data.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            data: Entity data
            include_relations: Optional list of relations included
            ttl: Optional TTL override

        Returns:
            True if successful
        """
        key = f"{entity_type}:{entity_id}"
        if include_relations:
            relations_str = ":".join(sorted(include_relations))
            key = f"{key}:{relations_str}"

        ttl = ttl or self.simple_query_ttl
        return await self.cache.set(self._make_key("entities", key), data, ttl)

    async def invalidate_entity(self, entity_type: str, entity_id: UUID) -> int:
        """
        Invalidate all cached versions of an entity.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID

        Returns:
            Number of keys deleted
        """
        pattern = f"{self.prefix}:entities:{entity_type}:{entity_id}*"
        return await self.cache.delete_pattern(pattern)

    # ==================== LIST QUERIES ====================

    async def get_list(
        self,
        entity_type: str,
        filters: Optional[Dict[str, Any]] = None,
        sorting: Optional[Dict[str, str]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Optional[Tuple[List[Dict[str, Any]], int]]:
        """
        Get cached list query result.

        Args:
            entity_type: Type of entity
            filters: Optional filters
            sorting: Optional sorting (field -> direction)
            page: Page number
            page_size: Page size

        Returns:
            Tuple of (items, total_count) or None
        """
        query_params = {
            "filters": filters or {},
            "sorting": sorting or {},
            "page": page,
            "page_size": page_size,
        }

        key = self._generate_query_key(entity_type, query_params, "list")
        result = await self.cache.get(self._make_key("lists", key))

        if result:
            return (result["items"], result["total"])
        return None

    async def set_list(
        self,
        entity_type: str,
        items: List[Dict[str, Any]],
        total_count: int,
        filters: Optional[Dict[str, Any]] = None,
        sorting: Optional[Dict[str, str]] = None,
        page: int = 1,
        page_size: int = 20,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache list query result.

        Args:
            entity_type: Type of entity
            items: List of items
            total_count: Total count (for pagination)
            filters: Optional filters
            sorting: Optional sorting
            page: Page number
            page_size: Page size
            ttl: Optional TTL override

        Returns:
            True if successful
        """
        query_params = {
            "filters": filters or {},
            "sorting": sorting or {},
            "page": page,
            "page_size": page_size,
        }

        key = self._generate_query_key(entity_type, query_params, "list")

        data = {
            "items": items,
            "total": total_count,
            "cached_at": datetime.utcnow().isoformat(),
        }

        ttl = ttl or self.list_query_ttl
        return await self.cache.set(self._make_key("lists", key), data, ttl)

    async def invalidate_lists(self, entity_type: str) -> int:
        """
        Invalidate all list queries for an entity type.

        Args:
            entity_type: Type of entity

        Returns:
            Number of keys deleted
        """
        pattern = f"{self.prefix}:lists:{entity_type}:*"
        return await self.cache.delete_pattern(pattern)

    # ==================== AGGREGATION QUERIES ====================

    async def get_aggregation(
        self,
        entity_type: str,
        aggregation_type: str,
        filters: Optional[Dict[str, Any]] = None,
        group_by: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached aggregation result.

        Args:
            entity_type: Type of entity
            aggregation_type: Type of aggregation (count, sum, avg, etc)
            filters: Optional filters
            group_by: Optional grouping fields

        Returns:
            Cached aggregation result or None
        """
        query_params = {
            "type": aggregation_type,
            "filters": filters or {},
            "group_by": group_by or [],
        }

        key = self._generate_query_key(entity_type, query_params, "aggregation")
        return await self.cache.get(self._make_key("aggregations", key))

    async def set_aggregation(
        self,
        entity_type: str,
        aggregation_type: str,
        result: Dict[str, Any],
        filters: Optional[Dict[str, Any]] = None,
        group_by: Optional[List[str]] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache aggregation result.

        Args:
            entity_type: Type of entity
            aggregation_type: Type of aggregation
            result: Aggregation result
            filters: Optional filters
            group_by: Optional grouping fields
            ttl: Optional TTL override

        Returns:
            True if successful
        """
        query_params = {
            "type": aggregation_type,
            "filters": filters or {},
            "group_by": group_by or [],
        }

        key = self._generate_query_key(entity_type, query_params, "aggregation")
        ttl = ttl or self.aggregation_ttl
        return await self.cache.set(self._make_key("aggregations", key), result, ttl)

    async def invalidate_aggregations(self, entity_type: str) -> int:
        """
        Invalidate all aggregations for an entity type.

        Args:
            entity_type: Type of entity

        Returns:
            Number of keys deleted
        """
        pattern = f"{self.prefix}:aggregations:{entity_type}:*"
        return await self.cache.delete_pattern(pattern)

    # ==================== SEARCH QUERIES ====================

    async def get_search(
        self,
        entity_type: str,
        search_term: str,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Optional[Tuple[List[Dict[str, Any]], int]]:
        """
        Get cached search result.

        Args:
            entity_type: Type of entity
            search_term: Search term
            filters: Optional filters
            page: Page number
            page_size: Page size

        Returns:
            Tuple of (items, total_count) or None
        """
        query_params = {
            "search": search_term,
            "filters": filters or {},
            "page": page,
            "page_size": page_size,
        }

        key = self._generate_query_key(entity_type, query_params, "search")
        result = await self.cache.get(self._make_key("searches", key))

        if result:
            return (result["items"], result["total"])
        return None

    async def set_search(
        self,
        entity_type: str,
        search_term: str,
        items: List[Dict[str, Any]],
        total_count: int,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache search result.

        Args:
            entity_type: Type of entity
            search_term: Search term
            items: Search results
            total_count: Total count
            filters: Optional filters
            page: Page number
            page_size: Page size
            ttl: Optional TTL override

        Returns:
            True if successful
        """
        query_params = {
            "search": search_term,
            "filters": filters or {},
            "page": page,
            "page_size": page_size,
        }

        key = self._generate_query_key(entity_type, query_params, "search")

        data = {
            "items": items,
            "total": total_count,
            "cached_at": datetime.utcnow().isoformat(),
        }

        ttl = ttl or self.list_query_ttl
        return await self.cache.set(self._make_key("searches", key), data, ttl)

    async def invalidate_searches(self, entity_type: str) -> int:
        """
        Invalidate all search queries for an entity type.

        Args:
            entity_type: Type of entity

        Returns:
            Number of keys deleted
        """
        pattern = f"{self.prefix}:searches:{entity_type}:*"
        return await self.cache.delete_pattern(pattern)

    # ==================== SMART INVALIDATION ====================

    async def invalidate_entity_related(
        self, entity_type: str, entity_id: Optional[UUID] = None
    ) -> Dict[str, int]:
        """
        Invalidate all queries related to an entity type or specific entity.

        Args:
            entity_type: Type of entity
            entity_id: Optional specific entity ID

        Returns:
            Dictionary with count of deleted keys by type
        """
        stats = {}

        if entity_id:
            # Invalidate specific entity
            stats["entities"] = await self.invalidate_entity(entity_type, entity_id)

        # Invalidate all lists (they might contain this entity)
        stats["lists"] = await self.invalidate_lists(entity_type)

        # Invalidate aggregations
        stats["aggregations"] = await self.invalidate_aggregations(entity_type)

        # Invalidate searches
        stats["searches"] = await self.invalidate_searches(entity_type)

        stats["total"] = sum(stats.values())

        return stats

    # ==================== BULK OPERATIONS ====================

    async def clear_all(self) -> int:
        """
        Clear all query cache.

        Returns:
            Total number of keys deleted
        """
        pattern = f"{self.prefix}:*"
        return await self.cache.delete_pattern(pattern)

    # ==================== STATS ====================

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get query cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        stats = await self.cache.get_stats()

        # Add query-specific stats
        stats["namespaces"] = {
            "entities": await self._count_keys("entities"),
            "lists": await self._count_keys("lists"),
            "aggregations": await self._count_keys("aggregations"),
            "searches": await self._count_keys("searches"),
        }

        return stats

    async def _count_keys(self, namespace: str) -> int:
        """
        Count keys in namespace.

        Args:
            namespace: Cache namespace

        Returns:
            Number of keys
        """
        pattern = f"{self.prefix}:{namespace}:*"
        keys = await self.cache.get_keys(pattern)
        return len(keys) if keys else 0


# Singleton instance
_query_cache_instance: Optional[QueryCache] = None


def get_query_cache() -> QueryCache:
    """
    Get singleton QueryCache instance.

    Returns:
        QueryCache instance
    """
    global _query_cache_instance
    if _query_cache_instance is None:
        _query_cache_instance = QueryCache()
    return _query_cache_instance
