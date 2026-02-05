"""
Unified cache abstraction service for consolidating cache operations.
Provides consistent cache interface and invalidation patterns across the system.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from app.infrastructure.cache import UnifiedCacheManager, get_unified_cache_manager
from app.config.template_loader import get_template_loader

logger = logging.getLogger(__name__)


class UnifiedCacheService:
    """
    Unified cache service that consolidates cache operations across the system.
    Provides consistent TTL values, key patterns, and invalidation strategies.
    """

    def __init__(self, cache_manager: Optional[UnifiedCacheManager] = None):
        """
        Initialize unified cache service.

        Args:
            cache_manager: Optional cache manager instance
        """
        self.cache_manager = cache_manager or get_unified_cache_manager()
        self.async_cache_manager = self.cache_manager
        self.template_loader = get_template_loader()
        
        # Register cache configs used by this service
        from app.infrastructure.cache import CacheConfig
        
        self._register_configs(CacheConfig)

    def _register_configs(self, cache_config_cls):
        """Register cache configurations."""
        configs = {
            "patient_data": cache_config_cls(ttl=1800, key_prefix="patient", namespace="patients"),
            "flow_data": cache_config_cls(ttl=1800, key_prefix="flow", namespace="flows"),
            "patient_flow": cache_config_cls(ttl=1800, key_prefix="patient_flow", namespace="flows"),
            "template_data": cache_config_cls(ttl=3600, key_prefix="template", namespace="templates"),
            "quiz_data": cache_config_cls(ttl=3600, key_prefix="quiz", namespace="quiz"),
            "quiz_session": cache_config_cls(ttl=3600, key_prefix="quiz_session", namespace="quiz"),
            "user_data": cache_config_cls(ttl=3600, key_prefix="user", namespace="users"),
        }
        
        for name, config in configs.items():
            self.cache_manager.register_cache_config(name, config)

    # Patient Cache Operations
    def cache_patient_data(
        self, patient_id: Union[str, UUID], data: Any, ttl: Optional[int] = None
    ) -> bool:
        """
        Cache patient data with consistent TTL and key pattern.

        Args:
            patient_id: Patient identifier
            data: Data to cache
            ttl: Time-to-live in seconds (uses config default if None)

        Returns:
            True if cached successfully, False otherwise
        """
        if ttl is None:
            ttl = self.template_loader.get_cache_ttl("patient_cache_ttl")

        return self.cache_manager.set("patient_data", data, key_parts=[str(patient_id)], ttl_override=ttl)

    def get_cached_patient_data(self, patient_id: Union[str, UUID]) -> Optional[Any]:
        """
        Get cached patient data.

        Args:
            patient_id: Patient identifier

        Returns:
            Cached data or None if not found
        """
        return self.cache_manager.get("patient_data", key_parts=[str(patient_id)])

    def invalidate_patient_cache(self, patient_id: Union[str, UUID]) -> bool:
        """
        Invalidate specific patient cache.

        Args:
            patient_id: Patient identifier

        Returns:
            True if invalidated successfully, False otherwise
        """
        return self.cache_manager.delete("patient_data", key_parts=[str(patient_id)])

    def invalidate_all_patient_cache(self) -> int:
        """
        Invalidate all patient cache entries.

        Returns:
            Number of entries invalidated
        """
        return self.cache_manager.invalidate_pattern("patient:*", namespace="patients")

    # Flow Cache Operations
    def cache_flow_data(
        self, flow_id: Union[str, UUID], data: Any, ttl: Optional[int] = None
    ) -> bool:
        """
        Cache flow data with consistent TTL and key pattern.

        Args:
            flow_id: Flow identifier
            data: Data to cache
            ttl: Time-to-live in seconds (uses config default if None)

        Returns:
            True if cached successfully, False otherwise
        """
        if ttl is None:
            ttl = self.template_loader.get_cache_ttl("flow_state_cache_ttl")

        return self.cache_manager.set("flow_data", data, key_parts=[str(flow_id)], ttl_override=ttl)

    def get_cached_flow_data(self, flow_id: Union[str, UUID]) -> Optional[Any]:
        """
        Get cached flow data.

        Args:
            flow_id: Flow identifier

        Returns:
            Cached data or None if not found
        """
        return self.cache_manager.get("flow_data", key_parts=[str(flow_id)])

    def cache_patient_flow_state(
        self,
        patient_id: Union[str, UUID],
        flow_type: str,
        state_data: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache patient flow state data.

        Args:
            patient_id: Patient identifier
            flow_type: Flow type (e.g., 'day_1_15', 'monthly')
            state_data: Flow state data
            ttl: Time-to-live in seconds

        Returns:
            True if cached successfully, False otherwise
        """
        if ttl is None:
            ttl = self.template_loader.get_cache_ttl("flow_state_cache_ttl")

        return self.cache_manager.set("patient_flow", state_data, key_parts=[str(patient_id), flow_type], ttl_override=ttl)

    def get_cached_patient_flow_state(
        self, patient_id: Union[str, UUID], flow_type: str
    ) -> Optional[Any]:
        """
        Get cached patient flow state.

        Args:
            patient_id: Patient identifier
            flow_type: Flow type

        Returns:
            Cached flow state or None if not found
        """
        return self.cache_manager.get("patient_flow", key_parts=[str(patient_id), flow_type])

    def invalidate_flow_cache(self, flow_id: Union[str, UUID]) -> bool:
        """
        Invalidate specific flow cache.

        Args:
            flow_id: Flow identifier

        Returns:
            True if invalidated successfully, False otherwise
        """
        return self.cache_manager.delete("flow_data", key_parts=[str(flow_id)])

    def invalidate_patient_flow_cache(
        self, patient_id: Union[str, UUID], flow_type: Optional[str] = None
    ) -> int:
        """
        Invalidate patient flow cache entries.

        Args:
            patient_id: Patient identifier
            flow_type: Specific flow type to invalidate (all if None)

        """
        if flow_type:
            return 1 if self.cache_manager.delete("patient_flow", key_parts=[str(patient_id), flow_type]) else 0
        else:
            pattern = f"patient_flow:{patient_id}:*"
            return self.cache_manager.invalidate_pattern(pattern, namespace="flows")

    # Template Cache Operations
    def cache_template_data(
        self, template_id: str, data: Any, ttl: Optional[int] = None
    ) -> bool:
        """
        Cache template data.

        Args:
            template_id: Template identifier
            data: Template data
            ttl: Time-to-live in seconds

        Returns:
            True if cached successfully, False otherwise
        """
        if ttl is None:
            ttl = self.template_loader.get_cache_ttl("template_cache_ttl")

        return self.cache_manager.set("template_data", data, key_parts=[str(template_id)], ttl_override=ttl)

    def get_cached_template_data(self, template_id: str) -> Optional[Any]:
        """
        Get cached template data.

        Args:
            template_id: Template identifier

        Returns:
            Cached template data or None if not found
        """
        return self.cache_manager.get("template_data", key_parts=[str(template_id)])

    def invalidate_template_cache(self, template_id: str) -> bool:
        """
        Invalidate specific template cache.

        Args:
            template_id: Template identifier

        Returns:
            True if invalidated successfully, False otherwise
        """
        return self.cache_manager.delete("template_data", key_parts=[str(template_id)])

    def invalidate_all_template_cache(self) -> int:
        """
        Invalidate all template cache entries.

        Returns:
            Number of entries invalidated
        """
        return self.cache_manager.invalidate_pattern(
            "template:*", namespace="templates"
        )

    # Quiz Cache Operations
    def cache_quiz_data(
        self, quiz_id: Union[str, UUID], data: Any, ttl: Optional[int] = None
    ) -> bool:
        """
        Cache quiz data.

        Args:
            quiz_id: Quiz identifier
            data: Quiz data
            ttl: Time-to-live in seconds

        Returns:
            True if cached successfully, False otherwise
        """
        if ttl is None:
            ttl = self.template_loader.get_cache_ttl("quiz_cache_ttl")

        return self.cache_manager.set("quiz_data", data, key_parts=[str(quiz_id)], ttl_override=ttl)

    def get_cached_quiz_data(self, quiz_id: Union[str, UUID]) -> Optional[Any]:
        """
        Get cached quiz data.

        Args:
            quiz_id: Quiz identifier

        Returns:
            Cached quiz data or None if not found
        """
        return self.cache_manager.get("quiz_data", key_parts=[str(quiz_id)])

    def cache_quiz_session(
        self, session_id: Union[str, UUID], session_data: Any, ttl: Optional[int] = None
    ) -> bool:
        """
        Cache quiz session data.

        Args:
            session_id: Any identifier
            session_data: Any data
            ttl: Time-to-live in seconds

        Returns:
            True if cached successfully, False otherwise
        """
        if ttl is None:
            ttl = self.template_loader.get_cache_ttl("quiz_session_cache_ttl")

        return self.cache_manager.set("quiz_session", session_data, key_parts=[str(session_id)], ttl_override=ttl)

    def get_cached_quiz_session(self, session_id: Union[str, UUID]) -> Optional[Any]:
        """
        Get cached quiz session data.

        Args:
            session_id: Any identifier

        Returns:
            Cached session data or None if not found
        """
        return self.cache_manager.get("quiz_session", key_parts=[str(session_id)])

    def invalidate_quiz_cache(self, quiz_id: Union[str, UUID]) -> bool:
        """
        Invalidate specific quiz cache.

        Args:
            quiz_id: Quiz identifier

        Returns:
            True if invalidated successfully, False otherwise
        """
        return self.cache_manager.delete("quiz_data", key_parts=[str(quiz_id)])

    def invalidate_quiz_session_cache(self, session_id: Union[str, UUID]) -> bool:
        """
        Invalidate specific quiz session cache.

        Args:
            session_id: Any identifier

        Returns:
            True if invalidated successfully, False otherwise
        """
        return self.cache_manager.delete("quiz_session", key_parts=[str(session_id)])

    # User/Doctor Cache Operations
    def cache_user_data(
        self, user_id: Union[str, UUID], data: Any, ttl: Optional[int] = None
    ) -> bool:
        """
        Cache user/doctor data.

        Args:
            user_id: User identifier
            data: User data
            ttl: Time-to-live in seconds

        Returns:
            True if cached successfully, False otherwise
        """
        if ttl is None:
            ttl = self.template_loader.get_cache_ttl("user_cache_ttl")

        return self.cache_manager.set("user_data", data, key_parts=[str(user_id)], ttl_override=ttl)

    def get_cached_user_data(self, user_id: Union[str, UUID]) -> Optional[Any]:
        """
        Get cached user data.

        Args:
            user_id: User identifier

        Returns:
            Cached user data or None if not found
        """
        return self.cache_manager.get("user_data", key_parts=[str(user_id)])

    def invalidate_user_cache(self, user_id: Union[str, UUID]) -> bool:
        """
        Invalidate specific user cache.

        Args:
            user_id: User identifier

        Returns:
            True if invalidated successfully, False otherwise
        """
        return self.cache_manager.delete("user_data", key_parts=[str(user_id)])

    # Bulk Operations
    def invalidate_patient_related_cache(
        self, patient_id: Union[str, UUID]
    ) -> Dict[str, int]:
        """
        Invalidate all cache entries related to a specific patient.

        Args:
            patient_id: Patient identifier

        Returns:
            Dictionary with namespace -> count of invalidated entries
        """
        results = {}

        # Invalidate patient data
        results["patients"] = 1 if self.invalidate_patient_cache(patient_id) else 0

        # Invalidate patient flow states
        results["flows"] = self.invalidate_patient_flow_cache(patient_id)

        # Invalidate quiz sessions for patient
        pattern = f"quiz_session:*:{patient_id}:*"
        results["quiz"] = self.cache_manager.invalidate_pattern(
            pattern, namespace="quiz"
        )

        logger.info(f"Invalidated patient {patient_id} related cache: {results}")
        return results

    def invalidate_flow_type_cache(self, flow_type: str) -> Dict[str, int]:
        """
        Invalidate all cache entries related to a specific flow type.

        Args:
            flow_type: Flow type identifier

        Returns:
            Dictionary with namespace -> count of invalidated entries
        """
        results = {}

        # Invalidate flow templates
        pattern = f"template:*:{flow_type}:*"
        results["templates"] = self.cache_manager.invalidate_pattern(
            pattern, namespace="templates"
        )

        # Invalidate patient flows of this type
        pattern = f"patient_flow:*:{flow_type}"
        results["flows"] = self.cache_manager.invalidate_pattern(
            pattern, namespace="flows"
        )

        logger.info(f"Invalidated flow type {flow_type} related cache: {results}")
        return results

    def warm_up_cache(self, patient_ids: List[Union[str, UUID]]) -> Dict[str, int]:
        """
        Warm up cache for a list of patients by pre-loading common data.

        Args:
            patient_ids: List of patient identifiers

        Returns:
            Dictionary with operation -> count of warmed entries
        """
        results = {"patients": 0, "flows": 0, "templates": 0}

        try:
            # This would typically involve fetching and caching common data
            # Implementation depends on specific business logic
            logger.info(f"Cache warm-up initiated for {len(patient_ids)} patients")

            # Example warm-up operations (implement based on actual data sources)
            for patient_id in patient_ids:
                # Warm up patient data (would fetch from database)
                # self.cache_patient_data(patient_id, fetch_patient_data(patient_id))
                results["patients"] += 1

            logger.info(f"Cache warm-up completed: {results}")

        except Exception as e:
            logger.error(f"Error during cache warm-up: {e}")

        return results

    # Health and Monitoring
    def get_cache_health(self) -> Dict[str, Any]:
        """
        Get cache health and statistics.

        Returns:
            Dictionary with cache health information
        """
        try:
            health = {"status": "healthy", "namespaces": {}, "errors": []}

            namespaces = ["patients", "flows", "templates", "quiz", "users"]

            for namespace in namespaces:
                try:
                    # Check if we can perform basic operations
                    test_key = f"health_check_{namespace}"
                    set_success = self.cache_manager.set(
                        test_key, "test", ttl=60, namespace=namespace
                    )
                    get_success = (
                        self.cache_manager.get(test_key, namespace=namespace)
                        is not None
                    )
                    delete_success = self.cache_manager.delete(
                        test_key, namespace=namespace
                    )

                    health["namespaces"][namespace] = {
                        "set": set_success,
                        "get": get_success,
                        "delete": delete_success,
                        "operational": set_success and get_success and delete_success,
                    }

                    if not (set_success and get_success and delete_success):
                        health["errors"].append(
                            f"Namespace {namespace} has operational issues"
                        )

                except Exception as e:
                    health["namespaces"][namespace] = {
                        "error": str(e),
                        "operational": False,
                    }
                    health["errors"].append(f"Error testing namespace {namespace}: {e}")

            # Overall health status
            operational_namespaces = sum(
                1
                for ns_health in health["namespaces"].values()
                if ns_health.get("operational", False)
            )

            if operational_namespaces == 0:
                health["status"] = "critical"
            elif operational_namespaces < len(namespaces):
                health["status"] = "degraded"

            return health

        except Exception as e:
            return {
                "status": "critical",
                "error": str(e),
                "namespaces": {},
                "errors": [f"Health check failed: {e}"],
            }

    def clear_all_cache(self) -> Dict[str, int]:
        """
        Clear all cache entries across all namespaces.
        Use with caution - this will clear ALL cached data.

        Returns:
            Dictionary with namespace -> count of cleared entries
        """
        results = {}
        namespaces = ["patients", "flows", "templates", "quiz", "users"]

        for namespace in namespaces:
            try:
                count = self.cache_manager.invalidate_namespace(namespace)
                results[namespace] = count
            except Exception as e:
                logger.error(f"Error clearing namespace {namespace}: {e}")
                results[namespace] = 0

        total_cleared = sum(results.values())
        logger.warning(
            f"Cleared all cache entries: {total_cleared} total across {len(namespaces)} namespaces"
        )

        return results


# Global singleton instance
_unified_cache_service: Optional[UnifiedCacheService] = None


def get_unified_cache_service() -> UnifiedCacheService:
    """
    Get the global unified cache service singleton.

    Returns:
        UnifiedCacheService instance
    """
    global _unified_cache_service
    if _unified_cache_service is None:
        _unified_cache_service = UnifiedCacheService()
    return _unified_cache_service


# Convenience functions for common operations
def invalidate_patient_cache(patient_id: Union[str, UUID]) -> bool:
    """
    Convenience function to invalidate patient cache.

    Args:
        patient_id: Patient identifier

    Returns:
        True if successful, False otherwise
    """
    return get_unified_cache_service().invalidate_patient_cache(patient_id)


def invalidate_flow_cache(flow_id: Union[str, UUID]) -> bool:
    """
    Convenience function to invalidate flow cache.

    Args:
        flow_id: Flow identifier

    Returns:
        True if successful, False otherwise
    """
    return get_unified_cache_service().invalidate_flow_cache(flow_id)


def invalidate_template_cache(template_id: str) -> bool:
    """
    Convenience function to invalidate template cache.

    Args:
        template_id: Template identifier

    Returns:
        True if successful, False otherwise
    """
    return get_unified_cache_service().invalidate_template_cache(template_id)


def invalidate_all_patient_related_cache(
    patient_id: Union[str, UUID],
) -> Dict[str, int]:
    """
    Convenience function to invalidate all patient-related cache.

    Args:
        patient_id: Patient identifier

    Returns:
        Dictionary with invalidation results
    """
    return get_unified_cache_service().invalidate_patient_related_cache(patient_id)
