"""
Data Synchronization Coordinator
Manages data consistency between database, cache, and real-time updates
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from app.core.redis_unified import get_async_redis
from app.orchestration.websocket_coordinator import (
    websocket_coordinator,
    WebSocketEvent,
    EventType,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SyncOperation(str, Enum):
    """Data synchronization operations"""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    BULK_UPDATE = "bulk_update"
    BULK_DELETE = "bulk_delete"


class SyncStatus(str, Enum):
    """Synchronization status"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SyncEvent:
    """Data synchronization event"""

    entity_type: str  # e.g., 'patient', 'message', 'report'
    entity_id: str
    operation: SyncOperation
    data: Dict[str, Any]
    user_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "operation": self.operation.value,
            "data": self.data,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SyncEvent":
        """Create from dictionary"""
        return cls(
            entity_type=data["entity_type"],
            entity_id=data["entity_id"],
            operation=SyncOperation(data["operation"]),
            data=data["data"],
            user_id=data.get("user_id"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CacheEntry:
    """Cache entry with TTL and metadata"""

    key: str
    value: Any
    ttl: int  # seconds
    created_at: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.utcnow)

    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        return (datetime.utcnow() - self.created_at).total_seconds() > self.ttl

    def update_access(self):
        """Update access statistics"""
        self.access_count += 1
        self.last_accessed = datetime.utcnow()


class DataSyncCoordinator:
    """
    Coordinates data synchronization between database, cache, and real-time updates
    """

    def __init__(self, redis_url: str = None):
        # redis_url parameter kept for backward compatibility but not used
        self.redis_client = None
        self.sync_handlers: Dict[str, Callable] = {}
        self.cache_policies: Dict[str, Dict[str, Any]] = {}
        self.sync_queue = asyncio.Queue()
        self.active_syncs: Dict[str, SyncStatus] = {}
        self.conflict_resolvers: Dict[str, Callable] = {}
        self._sync_worker_task: Optional[asyncio.Task] = None
        self._cache_cleanup_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize the data sync coordinator"""
        try:
            # Get unified Redis client
            self.redis_client = await get_async_redis()
            await self.redis_client.ping()

            # Set up default cache policies
            self._setup_default_cache_policies()

            # Start background workers
            self._sync_worker_task = asyncio.create_task(self._sync_worker())
            self._cache_cleanup_task = asyncio.create_task(self._cache_cleanup_worker())

            # Register default sync handlers
            self._register_default_handlers()

            logger.info("Data sync coordinator initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize data sync coordinator: {e}")
            raise

    async def shutdown(self):
        """Shutdown the data sync coordinator"""
        try:
            # Cancel background tasks
            if self._sync_worker_task:
                self._sync_worker_task.cancel()
            if self._cache_cleanup_task:
                self._cache_cleanup_task.cancel()

            # Close Redis connection
            if self.redis_client:
                await self.redis_client.aclose()  # Redis 5.x uses aclose() for async

            logger.info("Data sync coordinator shutdown completed")

        except Exception as e:
            logger.error(f"Error during data sync coordinator shutdown: {e}")

    async def sync_data(self, sync_event: SyncEvent) -> str:
        """Queue data synchronization event"""
        try:
            # Generate sync ID
            sync_id = f"{sync_event.entity_type}_{sync_event.entity_id}_{int(datetime.utcnow().timestamp() * 1000)}"

            # Mark as pending
            self.active_syncs[sync_id] = SyncStatus.PENDING

            # Add to sync queue
            await self.sync_queue.put((sync_id, sync_event))

            logger.debug(
                f"Queued sync event {sync_id} for {sync_event.entity_type}:{sync_event.entity_id}"
            )
            return sync_id

        except Exception as e:
            logger.error(f"Failed to queue sync event: {e}")
            raise

    async def get_cached_data(
        self, entity_type: str, entity_id: str, key: str = None
    ) -> Optional[Any]:
        """Get data from cache"""
        try:
            cache_key = self._generate_cache_key(entity_type, entity_id, key)
            cached_data = await self.redis_client.get(cache_key)

            if cached_data:
                return json.loads(cached_data)

            return None

        except Exception as e:
            logger.error(
                f"Failed to get cached data for {entity_type}:{entity_id}: {e}"
            )
            return None

    async def set_cached_data(
        self,
        entity_type: str,
        entity_id: str,
        data: Any,
        key: str = None,
        ttl: int = None,
    ) -> bool:
        """Set data in cache"""
        try:
            cache_key = self._generate_cache_key(entity_type, entity_id, key)

            # Get TTL from cache policy or use provided
            if ttl is None:
                policy = self.cache_policies.get(entity_type, {})
                ttl = policy.get("ttl", 3600)  # Default 1 hour

            # Store in Redis
            await self.redis_client.setex(cache_key, ttl, json.dumps(data, default=str))

            logger.debug(f"Cached data for {entity_type}:{entity_id} with TTL {ttl}s")
            return True

        except Exception as e:
            logger.error(f"Failed to cache data for {entity_type}:{entity_id}: {e}")
            return False

    async def invalidate_cache(
        self, entity_type: str, entity_id: str = None, pattern: str = None
    ) -> int:
        """Invalidate cache entries"""
        try:
            if pattern:
                # Use pattern to find keys
                cache_pattern = self._generate_cache_key(entity_type, "*", pattern)
            elif entity_id:
                # Invalidate specific entity
                cache_pattern = self._generate_cache_key(entity_type, entity_id, "*")
            else:
                # Invalidate all for entity type
                cache_pattern = self._generate_cache_key(entity_type, "*", "*")

            # Find matching keys
            keys = await self.redis_client.keys(cache_pattern)

            if keys:
                # Delete keys
                deleted = await self.redis_client.delete(*keys)
                logger.debug(
                    f"Invalidated {deleted} cache entries for pattern {cache_pattern}"
                )
                return deleted

            return 0

        except Exception as e:
            logger.error(f"Failed to invalidate cache for {entity_type}: {e}")
            return 0

    async def coordinate_database_update(
        self,
        entity_type: str,
        entity_id: str,
        data: Dict[str, Any],
        user_id: str = None,
    ) -> bool:
        """Coordinate a database update with cache invalidation and real-time sync"""
        try:
            # Create sync event
            sync_event = SyncEvent(
                entity_type=entity_type,
                entity_id=entity_id,
                operation=SyncOperation.UPDATE,
                data=data,
                user_id=user_id,
            )

            # Queue for synchronization
            sync_id = await self.sync_data(sync_event)

            # Wait for completion (with timeout)
            result = await self._wait_for_sync_completion(sync_id, timeout=30)

            return result == SyncStatus.COMPLETED

        except Exception as e:
            logger.error(
                f"Failed to coordinate database update for {entity_type}:{entity_id}: {e}"
            )
            return False

    async def coordinate_bulk_update(
        self, entity_type: str, updates: List[Dict[str, Any]], user_id: str = None
    ) -> bool:
        """Coordinate bulk database updates"""
        try:
            # Create bulk sync event
            sync_event = SyncEvent(
                entity_type=entity_type,
                entity_id="bulk",
                operation=SyncOperation.BULK_UPDATE,
                data={"updates": updates},
                user_id=user_id,
            )

            # Queue for synchronization
            sync_id = await self.sync_data(sync_event)

            # Wait for completion
            result = await self._wait_for_sync_completion(sync_id, timeout=60)

            return result == SyncStatus.COMPLETED

        except Exception as e:
            logger.error(f"Failed to coordinate bulk update for {entity_type}: {e}")
            return False

    def register_sync_handler(self, entity_type: str, handler: Callable):
        """Register a sync handler for an entity type"""
        self.sync_handlers[entity_type] = handler
        logger.debug(f"Registered sync handler for {entity_type}")

    def register_conflict_resolver(self, entity_type: str, resolver: Callable):
        """Register a conflict resolver for an entity type"""
        self.conflict_resolvers[entity_type] = resolver
        logger.debug(f"Registered conflict resolver for {entity_type}")

    def set_cache_policy(self, entity_type: str, policy: Dict[str, Any]):
        """Set cache policy for an entity type"""
        self.cache_policies[entity_type] = policy
        logger.debug(f"Set cache policy for {entity_type}: {policy}")

    async def _sync_worker(self):
        """Background worker for processing sync events"""
        while True:
            try:
                # Get sync event from queue
                sync_id, sync_event = await self.sync_queue.get()

                # Mark as in progress
                self.active_syncs[sync_id] = SyncStatus.IN_PROGRESS

                try:
                    # Process sync event
                    await self._process_sync_event(sync_event)

                    # Mark as completed
                    self.active_syncs[sync_id] = SyncStatus.COMPLETED

                    logger.debug(
                        f"Completed sync {sync_id} for {sync_event.entity_type}:{sync_event.entity_id}"
                    )

                except Exception as e:
                    # Mark as failed
                    self.active_syncs[sync_id] = SyncStatus.FAILED
                    logger.error(
                        f"Failed sync {sync_id} for {sync_event.entity_type}:{sync_event.entity_id}: {e}"
                    )

                # Mark task as done
                self.sync_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sync worker: {e}")

    async def _process_sync_event(self, sync_event: SyncEvent):
        """Process a single sync event"""
        try:
            # Get sync handler
            handler = self.sync_handlers.get(sync_event.entity_type)
            if not handler:
                logger.warning(
                    f"No sync handler for entity type {sync_event.entity_type}"
                )
                return

            # Execute sync handler
            result = await handler(sync_event)

            # Invalidate cache
            await self.invalidate_cache(sync_event.entity_type, sync_event.entity_id)

            # Broadcast real-time update
            await self._broadcast_sync_event(sync_event, result)

            logger.debug(
                f"Processed sync event for {sync_event.entity_type}:{sync_event.entity_id}"
            )

        except Exception as e:
            logger.error(f"Error processing sync event: {e}")
            raise

    async def _broadcast_sync_event(self, sync_event: SyncEvent, result: Any):
        """Broadcast sync event via WebSocket"""
        try:
            # Map sync operations to WebSocket events
            event_type_mapping = {
                SyncOperation.CREATE: {
                    "patient": EventType.PATIENT_CREATED,
                    "message": EventType.MESSAGE_SENT,
                    "alert": EventType.ALERT_CREATED,
                },
                SyncOperation.UPDATE: {
                    "patient": EventType.PATIENT_UPDATED,
                    "message": EventType.MESSAGE_DELIVERED,
                    "alert": EventType.ALERT_ACKNOWLEDGED,
                },
                SyncOperation.DELETE: {
                    "patient": EventType.PATIENT_UPDATED,  # Use updated for delete with status
                    "message": EventType.MESSAGE_FAILED,
                    "alert": EventType.ALERT_RESOLVED,
                },
            }

            # Get WebSocket event type
            event_mapping = event_type_mapping.get(sync_event.operation, {})
            ws_event_type = event_mapping.get(sync_event.entity_type)

            if ws_event_type:
                # Create WebSocket event
                ws_event = WebSocketEvent(
                    event_type=ws_event_type,
                    data={
                        "entity_type": sync_event.entity_type,
                        "entity_id": sync_event.entity_id,
                        "operation": sync_event.operation.value,
                        "data": sync_event.data,
                        "result": result,
                    },
                    user_id=sync_event.user_id,
                    correlation_id=sync_event.correlation_id,
                )

                # Broadcast via WebSocket coordinator
                await websocket_coordinator.broadcast_event(ws_event)

        except Exception as e:
            logger.error(f"Failed to broadcast sync event: {e}")

    async def _wait_for_sync_completion(
        self, sync_id: str, timeout: int = 30
    ) -> SyncStatus:
        """Wait for sync completion with timeout"""
        start_time = datetime.utcnow()

        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            status = self.active_syncs.get(sync_id, SyncStatus.PENDING)

            if status in [
                SyncStatus.COMPLETED,
                SyncStatus.FAILED,
                SyncStatus.CANCELLED,
            ]:
                return status

            await asyncio.sleep(0.1)  # Check every 100ms

        # Timeout reached
        self.active_syncs[sync_id] = SyncStatus.CANCELLED
        return SyncStatus.CANCELLED

    async def _cache_cleanup_worker(self):
        """Background worker for cache cleanup"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes

                # Get cache statistics
                info = await self.redis_client.info("memory")
                used_memory = info.get("used_memory", 0)
                max_memory = info.get("maxmemory", 0)

                # If memory usage is high, clean up expired keys
                if max_memory > 0 and used_memory / max_memory > 0.8:
                    await self._cleanup_expired_cache_entries()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup worker: {e}")

    async def _cleanup_expired_cache_entries(self):
        """Clean up expired cache entries"""
        try:
            # Get all cache keys
            cache_pattern = "sync:cache:*"
            keys = await self.redis_client.keys(cache_pattern)

            expired_count = 0
            for key in keys:
                # Check TTL
                ttl = await self.redis_client.ttl(key)
                if ttl == -2:  # Key doesn't exist (expired)
                    expired_count += 1
                elif ttl == -1:  # Key exists but has no TTL
                    # Set default TTL
                    await self.redis_client.expire(key, 3600)

            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired cache entries")

        except Exception as e:
            logger.error(f"Error cleaning up cache entries: {e}")

    def _generate_cache_key(
        self, entity_type: str, entity_id: str, key: str = None
    ) -> str:
        """Generate cache key"""
        if key:
            return f"sync:cache:{entity_type}:{entity_id}:{key}"
        return f"sync:cache:{entity_type}:{entity_id}"

    def _setup_default_cache_policies(self):
        """Set up default cache policies"""
        default_policies = {
            "patient": {"ttl": 1800, "max_size": 1000},  # 30 minutes
            "message": {"ttl": 300, "max_size": 5000},  # 5 minutes
            "report": {"ttl": 3600, "max_size": 500},  # 1 hour
            "alert": {"ttl": 600, "max_size": 2000},  # 10 minutes
            "flow": {"ttl": 1200, "max_size": 1000},  # 20 minutes
        }

        for entity_type, policy in default_policies.items():
            self.set_cache_policy(entity_type, policy)

    def _register_default_handlers(self):
        """Register default sync handlers"""
        # These would be implemented based on your specific models
        # For now, we'll use placeholder handlers

        async def default_patient_handler(sync_event: SyncEvent) -> Dict[str, Any]:
            """Default patient sync handler"""
            # This would implement actual database operations
            logger.debug(
                f"Processing patient sync: {sync_event.operation} for {sync_event.entity_id}"
            )
            return {"status": "processed", "timestamp": datetime.utcnow().isoformat()}

        async def default_message_handler(sync_event: SyncEvent) -> Dict[str, Any]:
            """Default message sync handler"""
            logger.debug(
                f"Processing message sync: {sync_event.operation} for {sync_event.entity_id}"
            )
            return {"status": "processed", "timestamp": datetime.utcnow().isoformat()}

        self.register_sync_handler("patient", default_patient_handler)
        self.register_sync_handler("message", default_message_handler)

    def get_sync_stats(self) -> Dict[str, Any]:
        """Get synchronization statistics"""
        return {
            "queue_size": self.sync_queue.qsize(),
            "active_syncs": len(self.active_syncs),
            "sync_status_counts": {
                status.value: sum(1 for s in self.active_syncs.values() if s == status)
                for status in SyncStatus
            },
            "registered_handlers": list(self.sync_handlers.keys()),
            "cache_policies": self.cache_policies,
        }


# Global data sync coordinator instance
data_sync_coordinator = DataSyncCoordinator()
