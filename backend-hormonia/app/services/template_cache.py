"""
Template cache system with hot-reload support using the versioning system.
Integrates Redis cache with the DB-only template loader.
"""
import json
import logging
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from dataclasses import asdict
from uuid import UUID

import redis
from sqlalchemy.orm import Session

from app.services.template_loader import EnhancedTemplateLoader, FlowTemplateData, MessageTemplate
from app.repositories.flow_kind import FlowKindRepository
from app.repositories.flow_template_version import FlowTemplateVersionRepository
from app.config import settings

logger = logging.getLogger(__name__)


class TemplateRedisCache:
    """
    Redis cache system for templates with hot-reload support.
    Works exclusively with the flow_kinds/flow_template_versions system.
    """

    def __init__(self, db: Session, redis_client: Optional[redis.Redis] = None):
        """
        Initialize versioned template cache with Redis.

        Args:
            db: Database session
            redis_client: Redis client (optional, will create if not provided)
        """
        self.db = db
        self.template_loader = EnhancedTemplateLoader(db=db)
        self.flow_kind_repo = FlowKindRepository(db)
        self.template_version_repo = FlowTemplateVersionRepository(db)

        # Redis configuration
        self.redis_client = redis_client or redis.Redis(
            host=getattr(settings, 'REDIS_HOST', 'localhost'),
            port=getattr(settings, 'REDIS_PORT', 6379),
            db=getattr(settings, 'REDIS_DB', 0),
            decode_responses=True
        )

        # Cache settings
        self.cache_prefix = "versioned_template"
        self.cache_ttl_seconds = 900  # 15 minutes
        self.pubsub_channel = "template_version_updates"

        # Hot-reload setup
        self.pubsub = self.redis_client.pubsub()
        self.pubsub.subscribe(self.pubsub_channel)

        logger.info("Versioned template Redis cache initialized with hot-reload support")

    def _make_cache_key(self, flow_type: str, version: Optional[str] = None) -> str:
        """Create cache key for flow template (version-aware)."""
        if version:
            return f"{self.cache_prefix}:{flow_type}:v_{version}"
        else:
            return f"{self.cache_prefix}:{flow_type}:current"

    def _make_message_cache_key(self, flow_type: str, day: int, version: Optional[str] = None) -> str:
        """Create cache key for specific message (version-aware)."""
        if version:
            return f"{self.cache_prefix}:msg:{flow_type}:v_{version}:day_{day}"
        else:
            return f"{self.cache_prefix}:msg:{flow_type}:current:day_{day}"

    def _make_version_info_key(self, flow_type: str) -> str:
        """Create cache key for version info."""
        return f"{self.cache_prefix}:info:{flow_type}"

    async def get_template(self, flow_type: str, version: Optional[str] = None) -> Optional[FlowTemplateData]:
        """
        Get template from cache or load from database (DB-first).

        Args:
            flow_type: Type of flow template
            version: Template version (optional, defaults to current)

        Returns:
            FlowTemplateData or None if not found
        """
        cache_key = self._make_cache_key(flow_type, version)

        try:
            # Try Redis cache first
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                logger.debug(f"Template loaded from Redis cache: {cache_key}")
                template_dict = json.loads(cached_data)
                return self._dict_to_template_data(template_dict)

            # Load from database via versioned template loader
            try:
                template_data = self.template_loader.load_flow_template(flow_type, version)
                if template_data:
                    # Cache in Redis
                    await self._cache_template(cache_key, template_data)
                    logger.debug(f"Template loaded from database and cached: {cache_key}")
                    return template_data
            except Exception as e:
                logger.error(f"Template load error for {flow_type}: {e}")
                return None

        except Exception as e:
            logger.error(f"Cache error for template {flow_type}: {e}")
            # Fallback to direct database load
            try:
                return self.template_loader.load_flow_template(flow_type, version)
            except Exception as fallback_error:
                logger.error(f"Fallback load failed for {flow_type}: {fallback_error}")
                return None

        return None

    async def get_message_for_day(self, flow_type: str, day: int, version: Optional[str] = None) -> Optional[MessageTemplate]:
        """
        Get message template for specific day from cache or database.

        Args:
            flow_type: Type of flow template
            day: Day number
            version: Template version (optional)

        Returns:
            MessageTemplate or None if not found
        """
        cache_key = self._make_message_cache_key(flow_type, day, version)

        try:
            # Try Redis cache first
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                logger.debug(f"Message loaded from Redis cache: {cache_key}")
                message_dict = json.loads(cached_data)
                return self._dict_to_message_template(message_dict)

            # Load from template loader
            message_template = self.template_loader.get_message_for_day(flow_type, day, version)
            if message_template:
                # Cache the message
                await self._cache_message(cache_key, message_template)
                logger.debug(f"Message loaded from database and cached: {cache_key}")
                return message_template

        except Exception as e:
            logger.error(f"Cache error for message {flow_type} day {day}: {e}")
            # Fallback to direct loader
            try:
                return self.template_loader.get_message_for_day(flow_type, day, version)
            except Exception as fallback_error:
                logger.error(f"Fallback message load failed: {fallback_error}")
                return None

        return None

    async def get_current_version_info(self, flow_type: str) -> Optional[Dict[str, Any]]:
        """Get current version information for a flow type (cached)."""
        cache_key = self._make_version_info_key(flow_type)

        try:
            # Try cache first
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)

            # Load from database
            version_info = self.template_loader.get_current_version_info(flow_type)
            if version_info:
                # Cache for 5 minutes (shorter TTL for metadata)
                self.redis_client.setex(cache_key, 300, json.dumps(version_info, default=str))
                return version_info

        except Exception as e:
            logger.error(f"Error getting version info for {flow_type}: {e}")

        return None

    async def invalidate_flow_type(self, flow_type: str) -> int:
        """
        Invalidate all cache entries for a specific flow type.

        Args:
            flow_type: Flow type to invalidate

        Returns:
            Number of keys invalidated
        """
        try:
            # Pattern to match all cache keys for this flow type
            patterns = [
                f"{self.cache_prefix}:{flow_type}:*",
                f"{self.cache_prefix}:msg:{flow_type}:*",
                f"{self.cache_prefix}:info:{flow_type}"
            ]

            total_invalidated = 0
            for pattern in patterns:
                keys = self.redis_client.keys(pattern)
                if keys:
                    total_invalidated += self.redis_client.delete(*keys)

            logger.info(f"Invalidated {total_invalidated} cache entries for flow_type: {flow_type}")

            # Publish hot-reload notification
            await self._publish_template_update(flow_type, "invalidated")

            return total_invalidated

        except Exception as e:
            logger.error(f"Error invalidating cache for flow_type {flow_type}: {e}")
            return 0

    async def invalidate_version(self, flow_type: str, version: str) -> int:
        """
        Invalidate cache entries for a specific version.

        Args:
            flow_type: Flow type
            version: Specific version to invalidate

        Returns:
            Number of keys invalidated
        """
        try:
            patterns = [
                f"{self.cache_prefix}:{flow_type}:v_{version}",
                f"{self.cache_prefix}:msg:{flow_type}:v_{version}:*"
            ]

            total_invalidated = 0
            for pattern in patterns:
                keys = self.redis_client.keys(pattern)
                if keys:
                    total_invalidated += self.redis_client.delete(*keys)

            logger.info(f"Invalidated {total_invalidated} cache entries for {flow_type} v{version}")

            # Publish hot-reload notification
            await self._publish_template_update(flow_type, "version_invalidated", {"version": version})

            return total_invalidated

        except Exception as e:
            logger.error(f"Error invalidating cache for {flow_type} v{version}: {e}")
            return 0

    async def warm_cache_for_version(self, flow_type: str, version: str) -> bool:
        """
        Warm cache by pre-loading a specific template version.

        Args:
            flow_type: Flow type
            version: Version to warm

        Returns:
            True if successful
        """
        try:
            # Load the template (this will cache it)
            template_data = await self.get_template(flow_type, version)
            if not template_data:
                logger.warning(f"Could not load template for cache warming: {flow_type} v{version}")
                return False

            # Pre-load all messages for this template
            for day in template_data.messages.keys():
                await self.get_message_for_day(flow_type, day, version)

            logger.info(f"Cache warmed for {flow_type} v{version} with {len(template_data.messages)} messages")

            # Publish hot-reload notification
            await self._publish_template_update(flow_type, "cache_warmed", {"version": version})

            return True

        except Exception as e:
            logger.error(f"Error warming cache for {flow_type} v{version}: {e}")
            return False

    async def on_version_published(self, flow_type: str, version: str, set_as_current: bool = False) -> None:
        """
        Handle version published event - invalidate and warm cache.

        Args:
            flow_type: Flow type
            version: Published version
            set_as_current: Whether this version was set as current
        """
        try:
            # If this version is set as current, invalidate current cache entries
            if set_as_current:
                current_keys = self.redis_client.keys(f"{self.cache_prefix}:{flow_type}:current*")
                if current_keys:
                    self.redis_client.delete(*current_keys)

                # Invalidate version info cache
                info_key = self._make_version_info_key(flow_type)
                self.redis_client.delete(info_key)

            # Warm cache for the new published version
            await self.warm_cache_for_version(flow_type, version)

            # Publish hot-reload notification
            await self._publish_template_update(
                flow_type,
                "version_published",
                {"version": version, "set_as_current": set_as_current}
            )

            logger.info(f"Processed version published event: {flow_type} v{version}")

        except Exception as e:
            logger.error(f"Error handling version published event: {e}")

    async def _cache_template(self, cache_key: str, template_data: FlowTemplateData) -> None:
        """Cache template data in Redis."""
        try:
            template_dict = template_data.to_dict()
            self.redis_client.setex(
                cache_key,
                self.cache_ttl_seconds,
                json.dumps(template_dict, default=str)
            )
        except Exception as e:
            logger.error(f"Error caching template {cache_key}: {e}")

    async def _cache_message(self, cache_key: str, message_template: MessageTemplate) -> None:
        """Cache message template in Redis."""
        try:
            message_dict = message_template.to_dict()
            self.redis_client.setex(
                cache_key,
                self.cache_ttl_seconds,
                json.dumps(message_dict, default=str)
            )
        except Exception as e:
            logger.error(f"Error caching message {cache_key}: {e}")

    async def _publish_template_update(self, flow_type: str, action: str, metadata: Optional[Dict] = None) -> None:
        """Publish template update notification for hot-reload."""
        try:
            update_message = {
                "timestamp": datetime.utcnow().isoformat(),
                "flow_type": flow_type,
                "action": action,
                "metadata": metadata or {}
            }
            self.redis_client.publish(
                self.pubsub_channel,
                json.dumps(update_message, default=str)
            )
        except Exception as e:
            logger.error(f"Error publishing template update: {e}")

    def _dict_to_template_data(self, template_dict: Dict[str, Any]) -> FlowTemplateData:
        """Convert dictionary back to FlowTemplateData object."""
        # This would need proper implementation based on the template structure
        # For now, create a basic conversion
        from app.services.template_loader import MessageTemplate, MessageType

        messages = {}
        for day_str, msg_data in template_dict.get("messages", {}).items():
            day = int(day_str)
            messages[day] = MessageTemplate(
                day=day,
                intent=msg_data.get("intent", ""),
                base_content=msg_data.get("base_content", ""),
                message_type=MessageType(msg_data.get("message_type", "text")),
                core_elements=msg_data.get("core_elements", {}),
                personalization_hints=msg_data.get("personalization_hints", []),
                ai_instructions=msg_data.get("ai_instructions"),
                variations=msg_data.get("variations", [])
            )

        return FlowTemplateData(
            flow_type=template_dict.get("flow_type", ""),
            name=template_dict.get("name", ""),
            description=template_dict.get("description", ""),
            version=template_dict.get("version", "1.0.0"),
            humanization_level=template_dict.get("humanization_level", "medium"),
            messages=messages,
            metadata=template_dict.get("metadata", {})
        )

    def _dict_to_message_template(self, message_dict: Dict[str, Any]) -> MessageTemplate:
        """Convert dictionary back to MessageTemplate object."""
        from app.services.template_loader import MessageTemplate, MessageType

        return MessageTemplate(
            day=message_dict.get("day", 1),
            intent=message_dict.get("intent", ""),
            base_content=message_dict.get("base_content", ""),
            message_type=MessageType(message_dict.get("message_type", "text")),
            core_elements=message_dict.get("core_elements", {}),
            personalization_hints=message_dict.get("personalization_hints", []),
            ai_instructions=message_dict.get("ai_instructions"),
            variations=message_dict.get("variations", [])
        )

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        try:
            # Get cache keys count by type
            template_keys = len(self.redis_client.keys(f"{self.cache_prefix}:*:v_*"))
            current_keys = len(self.redis_client.keys(f"{self.cache_prefix}:*:current"))
            message_keys = len(self.redis_client.keys(f"{self.cache_prefix}:msg:*"))
            info_keys = len(self.redis_client.keys(f"{self.cache_prefix}:info:*"))

            return {
                "total_keys": template_keys + current_keys + message_keys + info_keys,
                "template_versions": template_keys,
                "current_templates": current_keys,
                "cached_messages": message_keys,
                "version_info": info_keys,
                "cache_prefix": self.cache_prefix,
                "ttl_seconds": self.cache_ttl_seconds,
                "pubsub_channel": self.pubsub_channel
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}


# Dependency injection for FastAPI
def get_template_cache(db: Session) -> TemplateRedisCache:
    """Get template cache instance."""
    return TemplateRedisCache(db)