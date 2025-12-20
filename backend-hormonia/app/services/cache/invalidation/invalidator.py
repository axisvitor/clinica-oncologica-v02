"""
Cache Invalidator Module.

Centralized cache invalidation system with smart strategies.
Coordinates invalidation across all specialized caches.

Author: Backend Team
Date: 2025-01-20
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Set
from uuid import UUID
from enum import Enum

from app.services.cache.specialized import (
    JWTCache,
    TemplateCache,
    AnalyticsCache,
    QueryCache,
    get_jwt_cache,
    get_template_cache,
    get_analytics_cache,
    get_query_cache,
)


class InvalidationStrategy(str, Enum):
    """Cache invalidation strategies."""

    IMMEDIATE = "immediate"  # Invalidate immediately
    LAZY = "lazy"  # Mark for invalidation, clean on next access
    SCHEDULED = "scheduled"  # Schedule for invalidation
    CASCADE = "cascade"  # Invalidate related caches


class InvalidationScope(str, Enum):
    """Cache invalidation scope."""

    ENTITY = "entity"  # Single entity
    ENTITY_TYPE = "entity_type"  # All entities of a type
    USER = "user"  # User-specific caches
    GLOBAL = "global"  # All caches
    NAMESPACE = "namespace"  # Specific namespace


class CacheInvalidator:
    """
    Centralized cache invalidation coordinator.

    Features:
    - Smart invalidation strategies
    - Cross-cache coordination
    - Cascade invalidation
    - Invalidation tracking
    - Bulk operations
    """

    def __init__(
        self,
        jwt_cache: Optional[JWTCache] = None,
        template_cache: Optional[TemplateCache] = None,
        analytics_cache: Optional[AnalyticsCache] = None,
        query_cache: Optional[QueryCache] = None,
    ):
        """
        Initialize Cache Invalidator.

        Args:
            jwt_cache: Optional JWTCache instance
            template_cache: Optional TemplateCache instance
            analytics_cache: Optional AnalyticsCache instance
            query_cache: Optional QueryCache instance
        """
        self.jwt_cache = jwt_cache or get_jwt_cache()
        self.template_cache = template_cache or get_template_cache()
        self.analytics_cache = analytics_cache or get_analytics_cache()
        self.query_cache = query_cache or get_query_cache()

        # Track invalidations for analytics
        self._invalidation_log: List[Dict[str, Any]] = []

    # ==================== ENTITY INVALIDATION ====================

    async def invalidate_entity(
        self,
        entity_type: str,
        entity_id: UUID,
        strategy: InvalidationStrategy = InvalidationStrategy.CASCADE,
    ) -> Dict[str, Any]:
        """
        Invalidate all caches related to a specific entity.

        Args:
            entity_type: Type of entity (patient, doctor, treatment, etc)
            entity_id: Entity ID
            strategy: Invalidation strategy

        Returns:
            Invalidation statistics
        """
        stats = {
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "strategy": strategy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "caches": {},
        }

        # Query cache - invalidate entity and related queries
        query_stats = await self.query_cache.invalidate_entity_related(
            entity_type, entity_id
        )
        stats["caches"]["query"] = query_stats

        if strategy == InvalidationStrategy.CASCADE:
            # Analytics cache - invalidate related metrics
            analytics_deleted = await self._invalidate_entity_analytics(
                entity_type, entity_id
            )
            stats["caches"]["analytics"] = {"deleted": analytics_deleted}

            # Template cache - invalidate entity-specific templates
            template_deleted = await self._invalidate_entity_templates(
                entity_type, entity_id
            )
            stats["caches"]["template"] = {"deleted": template_deleted}

        stats["total_deleted"] = sum(
            v.get("total", v.get("deleted", 0)) for v in stats["caches"].values()
        )

        self._log_invalidation(stats)
        return stats

    async def _invalidate_entity_analytics(
        self, entity_type: str, entity_id: UUID
    ) -> int:
        """Invalidate analytics related to entity."""
        deleted = 0

        # Invalidate metrics that might include this entity
        # Example: patient count, treatment stats, etc.
        if entity_type == "patient":
            deleted += await self.analytics_cache.invalidate_report("patient_summary")
            deleted += await self.analytics_cache.invalidate_dashboard("patients")

        elif entity_type == "treatment":
            deleted += await self.analytics_cache.invalidate_report("treatment_stats")
            deleted += await self.analytics_cache.invalidate_dashboard("treatments")

        return deleted

    async def _invalidate_entity_templates(
        self, entity_type: str, entity_id: UUID
    ) -> int:
        """Invalidate templates related to entity."""
        # Entity-specific templates are rare, but can exist
        # Example: personalized email templates
        return 0

    # ==================== ENTITY TYPE INVALIDATION ====================

    async def invalidate_entity_type(
        self,
        entity_type: str,
        strategy: InvalidationStrategy = InvalidationStrategy.CASCADE,
    ) -> Dict[str, Any]:
        """
        Invalidate all caches for an entity type.

        Args:
            entity_type: Type of entity
            strategy: Invalidation strategy

        Returns:
            Invalidation statistics
        """
        stats = {
            "entity_type": entity_type,
            "strategy": strategy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "caches": {},
        }

        # Query cache - invalidate all queries for this entity type
        query_stats = await self.query_cache.invalidate_entity_related(entity_type)
        stats["caches"]["query"] = query_stats

        if strategy == InvalidationStrategy.CASCADE:
            # Analytics - invalidate all related analytics
            analytics_deleted = await self._invalidate_type_analytics(entity_type)
            stats["caches"]["analytics"] = {"deleted": analytics_deleted}

        stats["total_deleted"] = sum(
            v.get("total", v.get("deleted", 0)) for v in stats["caches"].values()
        )

        self._log_invalidation(stats)
        return stats

    async def _invalidate_type_analytics(self, entity_type: str) -> int:
        """Invalidate analytics for entity type."""
        deleted = 0

        # Invalidate type-specific reports
        deleted += await self.analytics_cache.invalidate_report(
            f"{entity_type}_summary"
        )
        deleted += await self.analytics_cache.invalidate_report(f"{entity_type}_stats")

        # Invalidate type-specific dashboards
        deleted += await self.analytics_cache.invalidate_dashboard(f"{entity_type}s")

        return deleted

    # ==================== USER INVALIDATION ====================

    async def invalidate_user(
        self, user_id: UUID, logout: bool = False
    ) -> Dict[str, Any]:
        """
        Invalidate all caches for a user.

        Args:
            user_id: User ID
            logout: If True, also invalidate JWT tokens (logout user)

        Returns:
            Invalidation statistics
        """
        stats = {
            "user_id": str(user_id),
            "logout": logout,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "caches": {},
        }

        # JWT cache - invalidate user sessions
        if logout:
            jwt_deleted = await self.jwt_cache.invalidate_user_tokens(user_id)
            stats["caches"]["jwt"] = {"deleted": jwt_deleted}

        # Analytics - invalidate user-specific dashboards
        analytics_deleted = await self.analytics_cache.invalidate_dashboard(
            "user_dashboard", user_id
        )
        stats["caches"]["analytics"] = {"deleted": analytics_deleted}

        stats["total_deleted"] = sum(
            v.get("deleted", 0) for v in stats["caches"].values()
        )

        self._log_invalidation(stats)
        return stats

    # ==================== BULK INVALIDATION ====================

    async def invalidate_multiple_entities(
        self,
        entity_type: str,
        entity_ids: List[UUID],
        strategy: InvalidationStrategy = InvalidationStrategy.CASCADE,
    ) -> Dict[str, Any]:
        """
        Invalidate multiple entities at once.

        Args:
            entity_type: Type of entity
            entity_ids: List of entity IDs
            strategy: Invalidation strategy

        Returns:
            Invalidation statistics
        """
        stats = {
            "entity_type": entity_type,
            "entity_count": len(entity_ids),
            "strategy": strategy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entities": [],
        }

        for entity_id in entity_ids:
            entity_stats = await self.invalidate_entity(
                entity_type, entity_id, strategy
            )
            stats["entities"].append(entity_stats)

        stats["total_deleted"] = sum(e["total_deleted"] for e in stats["entities"])

        self._log_invalidation(stats)
        return stats

    # ==================== NAMESPACE INVALIDATION ====================

    async def invalidate_namespace(
        self, cache_type: str, namespace: str
    ) -> Dict[str, Any]:
        """
        Invalidate a specific cache namespace.

        Args:
            cache_type: Type of cache (jwt, template, analytics, query)
            namespace: Namespace to invalidate

        Returns:
            Invalidation statistics
        """
        stats = {
            "cache_type": cache_type,
            "namespace": namespace,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "deleted": 0,
        }

        if cache_type == "analytics":
            if namespace == "metrics":
                stats["deleted"] = await self.analytics_cache.invalidate_all_metrics()
            elif namespace == "reports":
                stats["deleted"] = await self.analytics_cache.invalidate_all_reports()
            elif namespace == "dashboards":
                stats[
                    "deleted"
                ] = await self.analytics_cache.invalidate_all_dashboards()

        elif cache_type == "query":
            # Query cache namespaces handled by entity type
            pass

        elif cache_type == "template":
            if namespace == "email":
                stats["deleted"] = await self.template_cache.invalidate_category(
                    "email"
                )
            elif namespace == "whatsapp":
                stats["deleted"] = await self.template_cache.invalidate_category(
                    "whatsapp"
                )

        self._log_invalidation(stats)
        return stats

    # ==================== GLOBAL INVALIDATION ====================

    async def clear_all_caches(
        self, exclude: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """
        Clear all caches (DANGER: use with caution).

        Args:
            exclude: Optional set of cache types to exclude (jwt, template, analytics, query)

        Returns:
            Invalidation statistics
        """
        exclude = exclude or set()

        stats = {
            "operation": "clear_all",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "caches": {},
        }

        if "jwt" not in exclude:
            stats["caches"]["jwt"] = {"deleted": await self.jwt_cache.clear_all()}

        if "template" not in exclude:
            stats["caches"]["template"] = {
                "deleted": await self.template_cache.clear_all()
            }

        if "analytics" not in exclude:
            stats["caches"]["analytics"] = {
                "deleted": await self.analytics_cache.clear_all()
            }

        if "query" not in exclude:
            stats["caches"]["query"] = {"deleted": await self.query_cache.clear_all()}

        stats["total_deleted"] = sum(v["deleted"] for v in stats["caches"].values())

        self._log_invalidation(stats)
        return stats

    # ==================== SMART INVALIDATION ====================

    async def invalidate_on_create(
        self, entity_type: str, entity_id: UUID
    ) -> Dict[str, Any]:
        """
        Smart invalidation when entity is created.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID

        Returns:
            Invalidation statistics
        """
        # On create: invalidate lists and aggregations, but not individual entity cache
        stats = {
            "operation": "on_create",
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "caches": {},
        }

        # Invalidate lists (new entity not in cached lists)
        stats["caches"]["lists"] = {
            "deleted": await self.query_cache.invalidate_lists(entity_type)
        }

        # Invalidate aggregations (counts changed)
        stats["caches"]["aggregations"] = {
            "deleted": await self.query_cache.invalidate_aggregations(entity_type)
        }

        # Invalidate analytics
        stats["caches"]["analytics"] = {
            "deleted": await self._invalidate_type_analytics(entity_type)
        }

        stats["total_deleted"] = sum(v["deleted"] for v in stats["caches"].values())

        self._log_invalidation(stats)
        return stats

    async def invalidate_on_update(
        self, entity_type: str, entity_id: UUID
    ) -> Dict[str, Any]:
        """
        Smart invalidation when entity is updated.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID

        Returns:
            Invalidation statistics
        """
        # On update: invalidate entity and related caches
        return await self.invalidate_entity(
            entity_type, entity_id, InvalidationStrategy.CASCADE
        )

    async def invalidate_on_delete(
        self, entity_type: str, entity_id: UUID
    ) -> Dict[str, Any]:
        """
        Smart invalidation when entity is deleted.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID

        Returns:
            Invalidation statistics
        """
        # On delete: full cascade invalidation
        return await self.invalidate_entity(
            entity_type, entity_id, InvalidationStrategy.CASCADE
        )

    # ==================== LOGGING & STATS ====================

    def _log_invalidation(self, stats: Dict[str, Any]) -> None:
        """
        Log invalidation for tracking.

        Args:
            stats: Invalidation statistics
        """
        self._invalidation_log.append(stats)

        # Keep only last 1000 invalidations
        if len(self._invalidation_log) > 1000:
            self._invalidation_log = self._invalidation_log[-1000:]

    async def get_invalidation_stats(self) -> Dict[str, Any]:
        """
        Get invalidation statistics.

        Returns:
            Dictionary with invalidation statistics
        """
        total_invalidations = len(self._invalidation_log)
        total_deleted = sum(
            log.get("total_deleted", log.get("deleted", 0))
            for log in self._invalidation_log
        )

        # Count by operation
        by_operation = {}
        for log in self._invalidation_log:
            operation = log.get("operation", "entity_invalidation")
            by_operation[operation] = by_operation.get(operation, 0) + 1

        # Count by entity type
        by_entity_type = {}
        for log in self._invalidation_log:
            entity_type = log.get("entity_type")
            if entity_type:
                by_entity_type[entity_type] = by_entity_type.get(entity_type, 0) + 1

        return {
            "total_invalidations": total_invalidations,
            "total_keys_deleted": total_deleted,
            "by_operation": by_operation,
            "by_entity_type": by_entity_type,
            "recent_invalidations": self._invalidation_log[-10:],
        }

    def clear_log(self) -> None:
        """Clear invalidation log."""
        self._invalidation_log.clear()


# Singleton instance
_invalidator_instance: Optional[CacheInvalidator] = None


def get_cache_invalidator() -> CacheInvalidator:
    """
    Get singleton CacheInvalidator instance.

    Returns:
        CacheInvalidator instance
    """
    global _invalidator_instance
    if _invalidator_instance is None:
        _invalidator_instance = CacheInvalidator()
    return _invalidator_instance
