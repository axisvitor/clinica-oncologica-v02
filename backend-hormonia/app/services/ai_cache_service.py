"""
FIX #8: AI Response Caching Service
High-performance caching system for AI responses with intelligent invalidation.
"""
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from uuid import UUID
import json
import hashlib
import logging
from contextlib import asynccontextmanager
import asyncio
from enum import Enum

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from config.performance_optimization import get_performance_config

logger = logging.getLogger(__name__)


class CacheStatus(Enum):
    """Cache operation status."""
    HIT = "hit"
    MISS = "miss"
    ERROR = "error"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_errors: int = 0
    total_size: int = 0
    avg_response_time: float = 0.0
    hit_rate: float = 0.0
    
    def calculate_hit_rate(self):
        """Calculate cache hit rate."""
        if self.total_requests > 0:
            self.hit_rate = self.cache_hits / self.total_requests
        else:
            self.hit_rate = 0.0


class AICacheService:
    """FIX #8: High-performance AI response caching service."""
    
    def __init__(self):
        self.config = get_performance_config().cache
        self.redis_client: Optional[redis.Redis] = None
        self.local_cache: Dict[str, CacheEntry] = {}
        self.metrics = CacheMetrics()
        self._lock = asyncio.Lock()
        self._initialized = False
        
    async def initialize(self) -> bool:
        """Initialize cache service."""
        if self._initialized:
            return True
            
        try:
            if REDIS_AVAILABLE:
                redis_config = get_performance_config().get_redis_config()
                self.redis_client = redis.from_url(**redis_config)
                
                # Test connection
                await self.redis_client.ping()
                logger.info("Redis cache initialized successfully")
            else:
                logger.warning("Redis not available, using local cache only")
            
            self._initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize cache service: {e}")
            # Fall back to local cache
            self.redis_client = None
            self._initialized = True
            return False
    
    async def get_ai_response(self, model: str, prompt: str, parameters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """FIX #8: Get cached AI response."""
        if not self._initialized:
            await self.initialize()
        
        cache_key = self._generate_ai_cache_key(model, prompt, parameters)
        
        try:
            # Try Redis first
            if self.redis_client:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    self._record_cache_hit()
                    result = json.loads(cached_data)
                    logger.debug(f"AI response cache hit for key: {cache_key[:16]}...")
                    return result
            
            # Try local cache
            if cache_key in self.local_cache:
                entry = self.local_cache[cache_key]
                if datetime.utcnow() < entry.expires_at:
                    entry.access_count += 1
                    entry.last_accessed = datetime.utcnow()
                    self._record_cache_hit()
                    logger.debug(f"Local AI response cache hit for key: {cache_key[:16]}...")
                    return entry.value
                else:
                    # Expired entry
                    del self.local_cache[cache_key]
            
            self._record_cache_miss()
            return None
            
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            self._record_cache_error()
            return None
    
    async def set_ai_response(self, model: str, prompt: str, parameters: Dict[str, Any], 
                            response: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """FIX #8: Cache AI response with intelligent TTL."""
        if not self._initialized:
            await self.initialize()
        
        cache_key = self._generate_ai_cache_key(model, prompt, parameters)
        ttl = ttl or self.config.ai_response_ttl
        
        try:
            # Prepare cache data
            cache_data = {
                'response': response,
                'model': model,
                'cached_at': datetime.utcnow().isoformat(),
                'expires_at': (datetime.utcnow() + timedelta(seconds=ttl)).isoformat(),
                'parameters': parameters
            }
            
            # Store in Redis
            if self.redis_client:
                await self.redis_client.setex(
                    cache_key, 
                    ttl, 
                    json.dumps(cache_data, default=str)
                )
                
                # Add to model-specific index for invalidation
                model_key = f"ai_model:{model}"
                await self.redis_client.sadd(model_key, cache_key)
                await self.redis_client.expire(model_key, ttl + 3600)  # Keep index longer
            
            # Store in local cache (with size limit)
            if len(self.local_cache) >= self.config.ai_response_max_size:
                await self._evict_local_cache()
            
            entry = CacheEntry(
                key=cache_key,
                value=cache_data,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(seconds=ttl),
                tags=[f"model:{model}"]
            )
            self.local_cache[cache_key] = entry
            
            logger.debug(f"Cached AI response for key: {cache_key[:16]}... (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    async def invalidate_ai_responses(self, model: Optional[str] = None, 
                                    patient_id: Optional[UUID] = None) -> int:
        """FIX #8: Intelligent cache invalidation."""
        if not self._initialized:
            await self.initialize()
        
        invalidated_count = 0
        
        try:
            # Invalidate by model
            if model:
                if self.redis_client:
                    model_key = f"ai_model:{model}"
                    cache_keys = await self.redis_client.smembers(model_key)
                    if cache_keys:
                        await self.redis_client.delete(*cache_keys)
                        await self.redis_client.delete(model_key)
                        invalidated_count += len(cache_keys)
                
                # Local cache invalidation
                local_keys_to_remove = [
                    key for key, entry in self.local_cache.items()
                    if f"model:{model}" in entry.tags
                ]
                for key in local_keys_to_remove:
                    del self.local_cache[key]
                    invalidated_count += 1
            
            # Invalidate by patient
            if patient_id:
                patient_tag = f"patient:{patient_id}"
                
                if self.redis_client:
                    # Use pattern matching for patient-specific keys
                    pattern = f"ai:response:*:patient:{patient_id}:*"
                    async for key in self.redis_client.scan_iter(match=pattern):
                        await self.redis_client.delete(key)
                        invalidated_count += 1
                
                # Local cache invalidation
                local_keys_to_remove = [
                    key for key, entry in self.local_cache.items()
                    if patient_tag in entry.tags
                ]
                for key in local_keys_to_remove:
                    del self.local_cache[key]
                    invalidated_count += 1
            
            logger.info(f"Invalidated {invalidated_count} AI response cache entries")
            return invalidated_count
            
        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")
            return 0
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """FIX #8: Get comprehensive cache statistics."""
        self.metrics.calculate_hit_rate()
        
        stats = {
            'performance': asdict(self.metrics),
            'local_cache': {
                'size': len(self.local_cache),
                'max_size': self.config.ai_response_max_size,
                'usage_percent': (len(self.local_cache) / self.config.ai_response_max_size) * 100
            },
            'redis_cache': {
                'available': self.redis_client is not None,
                'connected': False
            },
            'configuration': {
                'ai_response_ttl': self.config.ai_response_ttl,
                'max_cache_size': self.config.ai_response_max_size,
                'query_cache_ttl': self.config.query_cache_ttl
            }
        }
        
        # Redis statistics
        if self.redis_client:
            try:
                await self.redis_client.ping()
                stats['redis_cache']['connected'] = True
                
                # Get Redis info
                redis_info = await self.redis_client.info('memory')
                stats['redis_cache'].update({
                    'memory_used': redis_info.get('used_memory_human', 'unknown'),
                    'memory_peak': redis_info.get('used_memory_peak_human', 'unknown'),
                    'fragmentation_ratio': redis_info.get('mem_fragmentation_ratio', 0)
                })
                
            except Exception as e:
                logger.error(f"Failed to get Redis stats: {e}")
                stats['redis_cache']['connected'] = False
        
        return stats
    
    async def cleanup_expired_entries(self) -> int:
        """FIX #8: Clean up expired cache entries."""
        if not self._initialized:
            return 0
        
        cleaned_count = 0
        current_time = datetime.utcnow()
        
        # Clean local cache
        expired_keys = [
            key for key, entry in self.local_cache.items()
            if current_time >= entry.expires_at
        ]
        
        for key in expired_keys:
            del self.local_cache[key]
            cleaned_count += 1
        
        logger.debug(f"Cleaned up {cleaned_count} expired cache entries")
        return cleaned_count
    
    async def warm_cache(self, model: str, common_prompts: List[Dict[str, Any]]) -> int:
        """FIX #8: Warm cache with common prompts."""
        if not self._initialized:
            await self.initialize()
        
        warmed_count = 0
        
        # This would typically be called with pre-computed responses
        # for common prompts that are known to be frequently used
        
        logger.info(f"Cache warming completed: {warmed_count} entries")
        return warmed_count
    
    def _generate_ai_cache_key(self, model: str, prompt: str, parameters: Dict[str, Any]) -> str:
        """Generate consistent cache key for AI requests."""
        # Create deterministic hash from model, prompt, and parameters
        key_data = {
            'model': model,
            'prompt': prompt,
            'parameters': sorted(parameters.items())  # Sort for consistency
        }
        
        key_string = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:32]
        
        patterns = get_performance_config().get_cache_key_patterns()
        return patterns['ai_response'].format(model=model, hash=key_hash)
    
    async def _evict_local_cache(self):
        """Evict least recently used entries from local cache."""
        if not self.local_cache:
            return
        
        # Sort by last accessed time (LRU)
        sorted_entries = sorted(
            self.local_cache.items(),
            key=lambda x: x[1].last_accessed or x[1].created_at
        )
        
        # Remove oldest 25% of entries
        evict_count = max(1, len(sorted_entries) // 4)
        for i in range(evict_count):
            key, _ = sorted_entries[i]
            del self.local_cache[key]
        
        logger.debug(f"Evicted {evict_count} entries from local cache")
    
    def _record_cache_hit(self):
        """Record cache hit metric."""
        self.metrics.total_requests += 1
        self.metrics.cache_hits += 1
    
    def _record_cache_miss(self):
        """Record cache miss metric."""
        self.metrics.total_requests += 1
        self.metrics.cache_misses += 1
    
    def _record_cache_error(self):
        """Record cache error metric."""
        self.metrics.total_requests += 1
        self.metrics.cache_errors += 1
    
    async def close(self):
        """Close cache service and connections."""
        if self.redis_client:
            await self.redis_client.close()
        
        self.local_cache.clear()
        logger.info("AI cache service closed")


# Global cache service instance
_ai_cache_service: Optional[AICacheService] = None


async def get_ai_cache_service() -> AICacheService:
    """Get the global AI cache service instance."""
    global _ai_cache_service
    
    if _ai_cache_service is None:
        _ai_cache_service = AICacheService()
        await _ai_cache_service.initialize()
    
    return _ai_cache_service


@asynccontextmanager
async def cached_ai_request(model: str, prompt: str, parameters: Dict[str, Any]):
    """Context manager for cached AI requests."""
    cache_service = await get_ai_cache_service()
    
    # Try to get cached response
    cached_response = await cache_service.get_ai_response(model, prompt, parameters)
    
    if cached_response:
        yield cached_response['response'], CacheStatus.HIT
    else:
        # Context manager will yield None, indicating cache miss
        # The caller should make the AI request and then cache the result
        yield None, CacheStatus.MISS


async def cache_ai_response(model: str, prompt: str, parameters: Dict[str, Any], 
                          response: Dict[str, Any], ttl: Optional[int] = None) -> bool:
    """Cache an AI response."""
    cache_service = await get_ai_cache_service()
    return await cache_service.set_ai_response(model, prompt, parameters, response, ttl)


async def invalidate_ai_cache(model: Optional[str] = None, 
                            patient_id: Optional[UUID] = None) -> int:
    """Invalidate AI cache entries."""
    cache_service = await get_ai_cache_service()
    return await cache_service.invalidate_ai_responses(model, patient_id)


async def get_ai_cache_stats() -> Dict[str, Any]:
    """Get AI cache statistics."""
    cache_service = await get_ai_cache_service()
    return await cache_service.get_cache_statistics()
