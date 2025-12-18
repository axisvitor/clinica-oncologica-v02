"""
Cache Services Package - HIGH-002 Implementation

Provides high-performance caching services for:
- Flow templates (TTL: 1h)
- Doctor data (TTL: 30min)
- User data (TTL: 15min)

All cache services use Redis with:
- Cache-aside pattern
- Automatic TTL expiration
- Cache invalidation support
- Hit rate monitoring
"""
from .flow_template_cache import (
    FlowTemplateCacheService,
    get_flow_template_cache,
)

__all__ = [
    "FlowTemplateCacheService",
    "get_flow_template_cache",
]
