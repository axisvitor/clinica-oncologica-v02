"""
Template Cache - Specialized Template Caching
==============================================

Wrapper around CacheLayer for template-specific operations.

Features:
- Template caching by key
- Version management
- Preloading support
- Long TTL (hours)

Author: AI Architect
Date: 20 Jan 2025
Version: 2.0.0 (Consolidated)
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.services.ai.cache_layer import CacheLayer, CacheOperation, get_cache_layer

logger = logging.getLogger(__name__)


class TemplateCache:
    """
    Template caching with version management.

    Features:
    - Template caching by key
    - Version management
    - Preloading support
    - Long TTL (24 hours default)
    - Tag-based invalidation

    Example:
        >>> template_cache = TemplateCache()
        >>> await template_cache.initialize()
        >>> await template_cache.cache_template("welcome", template_data)
        >>> template = await template_cache.get_template("welcome")
    """

    # TTL for templates (24 hours)
    DEFAULT_TTL = 86400

    def __init__(self, cache_layer: Optional[CacheLayer] = None):
        """Initialize template cache."""
        self.cache = cache_layer
        self._initialized = False
        logger.info("TemplateCache initialized")

    async def initialize(self):
        """Initialize cache layer."""
        if self._initialized:
            return

        if not self.cache:
            self.cache = await get_cache_layer()

        self._initialized = True
        logger.info("TemplateCache initialized successfully")

    async def cache_template(
        self,
        template_key: str,
        template_data: Dict[str, Any],
        version: Optional[str] = None,
        ttl: Optional[int] = None,
    ):
        """
        Cache template data.

        Args:
            template_key: Unique template identifier
            template_data: Template data to cache
            version: Optional version identifier
            ttl: Time to live in seconds (default: 24 hours)
        """
        key = self._build_key(template_key, version)

        cache_data = {
            **template_data,
            "_version": version,
            "_cached_at": datetime.utcnow().isoformat(),
            "_template_key": template_key,
        }

        await self.cache.set(
            key,
            cache_data,
            CacheOperation.TEMPLATE_HUMANIZATION,
            ttl=ttl or self.DEFAULT_TTL,
            tags=["template", f"template:{template_key}"],
        )

        logger.debug(f"Cached template: {template_key}, version: {version or 'latest'}")

    async def get_template(
        self, template_key: str, version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached template.

        Args:
            template_key: Template identifier
            version: Optional version to retrieve

        Returns:
            Template data if cached, None if not found
        """
        key = self._build_key(template_key, version)
        return await self.cache.get(key, CacheOperation.TEMPLATE_HUMANIZATION)

    async def invalidate_template(self, template_key: str):
        """
        Invalidate all versions of a template.

        Args:
            template_key: Template identifier
        """
        await self.cache.invalidate_by_tag(f"template:{template_key}")
        logger.info(f"Invalidated all versions of template: {template_key}")

    async def invalidate_all_templates(self):
        """Invalidate all cached templates."""
        await self.cache.invalidate_by_tag("template")
        logger.info("Invalidated all templates")

    async def preload_templates(
        self, template_keys: List[str], loader_func: Optional[callable] = None
    ):
        """
        Preload multiple templates into cache.

        Args:
            template_keys: List of template keys to preload
            loader_func: Optional function to load templates (key) -> template_data
        """
        if not loader_func:
            logger.warning("No loader function provided, skipping preload")
            return

        for key in template_keys:
            try:
                template_data = await loader_func(key)
                if template_data:
                    await self.cache_template(key, template_data)
            except Exception as e:
                logger.error(f"Failed to preload template {key}: {e}")

        logger.info(f"Preloaded {len(template_keys)} templates")

    async def list_cached_templates(self) -> List[str]:
        """
        List all cached template keys.

        Note: This is a simplified implementation.
        Returns empty list as pattern scanning is expensive.
        """
        logger.warning("list_cached_templates not fully implemented")
        return []

    async def get_stats(self) -> Dict[str, Any]:
        """Get template cache statistics."""
        cache_stats = await self.cache.get_stats()

        return {
            **cache_stats,
            "cache_type": "template",
            "default_ttl": self.DEFAULT_TTL,
        }

    def _build_key(self, template_key: str, version: Optional[str] = None) -> str:
        """Build cache key for template."""
        if version:
            return f"template:{template_key}:v{version}"
        return f"template:{template_key}"


# Singleton instance
_template_cache: Optional[TemplateCache] = None


async def get_template_cache() -> TemplateCache:
    """
    Get or create singleton TemplateCache instance.

    Returns:
        Initialized TemplateCache instance
    """
    global _template_cache

    if _template_cache is None:
        _template_cache = TemplateCache()
        await _template_cache.initialize()

    return _template_cache


async def reset_template_cache():
    """Reset singleton instance (for testing)."""
    global _template_cache
    _template_cache = None
