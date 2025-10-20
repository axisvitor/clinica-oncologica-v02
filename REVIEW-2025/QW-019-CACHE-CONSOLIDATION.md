# 🗄️ QW-019: Cache Services Consolidation (10 → 1)
## Backend Hormonia - Consolidação de Cache Services

**Status:** 📋 PLANEJADO  
**Data Início:** 20 de Janeiro de 2025  
**Prioridade:** 🔥 ALTA - Low Risk  
**Categoria:** Phase 3 - Consolidation  
**Tempo Estimado:** 6-8 horas  

---

## 📋 EXECUTIVE SUMMARY

### Objetivo

Consolidar **10 arquivos de cache** em **1 módulo unificado** aproveitando o `cache_layer.py` já criado em QW-018 e adicionando caches especializados.

### Problema Atual

```
app/services/
├── cache.py                    # Cache genérico base
├── cache_service.py            # Service de cache
├── cache_invalidation.py       # Invalidação
├── unified_cache.py            # Cache unificado (tentativa)
├── template_cache.py           # Cache de templates
├── analytics_cache.py          # Cache de analytics
├── jwt_cache_service.py        # Cache de JWT
├── ai_cache.py                 # ✅ JÁ CONSOLIDADO em QW-018
├── ai_cache_service.py         # ✅ JÁ CONSOLIDADO em QW-018
└── ai_redis_cache.py           # ✅ JÁ CONSOLIDADO em QW-018
```

**Problemas Identificados:**
- ❌ Múltiplas implementações de cache base
- ❌ `cache.py` vs `cache_service.py` vs `unified_cache.py` - qual usar?
- ❌ Cada cache especializado reimplementa TTL, invalidation, etc
- ❌ Código duplicado entre caches
- ❌ Difícil saber qual cache usar para qual propósito

### Solução Proposta

```
app/services/cache/
├── __init__.py                 # Exports públicos
├── base/
│   └── cache_service.py        # ← Usar cache_layer.py do QW-018
├── specialized/
│   ├── __init__.py
│   ├── jwt_cache.py            # JWT caching (usando base)
│   ├── template_cache.py       # Template caching (usando base)
│   ├── analytics_cache.py      # Analytics caching (usando base)
│   └── query_cache.py          # Query caching (usando base)
└── invalidation/
    └── invalidator.py          # Cache invalidation utilities
```

**Estratégia:**
- ✅ Reusar `app/services/ai/cache_layer.py` como base universal
- ✅ Criar wrappers especializados que usam CacheLayer
- ✅ Consolidar invalidation logic
- ✅ Eliminar duplicações

**Benefícios:**
- ✅ 10 arquivos → 1 módulo (6 arquivos organizados)
- ✅ Cache base unificado (já existe!)
- ✅ Caches especializados com funcionalidades únicas
- ✅ Zero duplicação de código base
- ✅ API consistente

---

## 🔍 ANÁLISE DETALHADA DOS ARQUIVOS

### Categoria 1: Cache Base (Consolidar)

#### 1. `cache.py` - Cache Genérico Base
**LOC:** ~300  
**Responsabilidade:** Cache genérico com Redis

**Principais Features:**
- Redis connection management
- Basic get/set operations
- TTL support
- Serialization/deserialization

**Decisão:** ⚠️ **SUBSTITUIR** - Usar `cache_layer.py` do QW-018

---

#### 2. `cache_service.py` - Service de Cache
**LOC:** ~400  
**Responsabilidade:** Cache service com padrões

**Principais Features:**
- Cache patterns (aside, through, etc)
- Invalidation logic
- Warming capabilities
- Metrics

**Decisão:** ⚠️ **CONSOLIDAR** - Migrar features únicas para cache_layer

---

#### 3. `unified_cache.py` - Tentativa de Unificação
**LOC:** ~350  
**Responsabilidade:** Cache unificado (incomplete)

**Principais Features:**
- Multi-backend support attempt
- Pattern-based keys
- Batch operations

**Decisão:** ⚠️ **CONSOLIDAR** - Já temos melhor em cache_layer.py

---

#### 4. `cache_invalidation.py` - Invalidação
**LOC:** ~250  
**Responsabilidade:** Cache invalidation utilities

**Principais Features:**
- Pattern-based invalidation
- Tag-based invalidation
- Cascade invalidation
- Event-based invalidation

**Decisão:** ✅ **MANTER SEPARADO** - Criar `invalidator.py` com estas features

---

### Categoria 2: Caches Especializados (Refatorar)

#### 5. `jwt_cache_service.py` - JWT Cache
**LOC:** ~280  
**Responsabilidade:** Cache de JWT tokens

**Features Únicas:**
- JWT token caching
- Token validation caching
- Blacklist management
- Short TTL (minutes)

**Decisão:** ✅ **REFATORAR** - Criar wrapper usando CacheLayer

---

#### 6. `template_cache.py` - Template Cache
**LOC:** ~200  
**Responsabilidade:** Cache de templates

**Features Únicas:**
- Template caching by key
- Version management
- Preloading
- Long TTL (hours)

**Decisão:** ✅ **REFATORAR** - Criar wrapper usando CacheLayer

---

#### 7. `analytics_cache.py` - Analytics Cache
**LOC:** ~320  
**Responsabilidade:** Cache de dados analytics

**Features Únicas:**
- Time-series data caching
- Aggregation caching
- Compression for large datasets
- Warming for dashboards

**Decisão:** ✅ **REFATORAR** - Criar wrapper usando CacheLayer

---

### Categoria 3: AI Caches (JÁ CONSOLIDADOS ✅)

#### 8-10. AI Caches
- `ai_cache.py` (419 LOC) → ✅ Consolidado em `cache_layer.py`
- `ai_cache_service.py` (436 LOC) → ❌ Removido (duplicado)
- `ai_redis_cache.py` (281 LOC) → ✅ Consolidado em `cache_layer.py`

**Status:** ✅ **JÁ COMPLETO** em QW-018

---

## 🎯 ARQUITETURA TARGET

### Estrutura do Módulo

```
app/services/cache/
├── __init__.py                     # Public exports
│
├── base/
│   ├── __init__.py
│   └── cache_service.py            # Symlink ou import de ai/cache_layer.py
│
├── specialized/
│   ├── __init__.py
│   ├── jwt_cache.py                # JWT-specific caching
│   ├── template_cache.py           # Template-specific caching
│   ├── analytics_cache.py          # Analytics-specific caching
│   └── query_cache.py              # Query-specific caching
│
└── invalidation/
    ├── __init__.py
    └── invalidator.py              # Cache invalidation utilities
```

---

## 📝 IMPLEMENTAÇÃO DETALHADA

### 1. `__init__.py` - Public API

```python
"""
Cache Services Module
=====================

Unified caching system with specialized wrappers.

Base cache from QW-018: app.services.ai.cache_layer.CacheLayer

Public API:
    CacheService: Alias for CacheLayer
    JWTCache: JWT token caching
    TemplateCache: Template caching
    AnalyticsCache: Analytics data caching
    QueryCache: Query result caching
    CacheInvalidator: Invalidation utilities

Example:
    >>> from app.services.cache import JWTCache
    >>> jwt_cache = JWTCache()
    >>> await jwt_cache.cache_token("user:123", token_data, ttl=300)
"""

# Base cache (from QW-018)
from app.services.ai.cache_layer import (
    CacheLayer as CacheService,
    CacheOperation,
    CacheStrategy,
    CacheMetrics,
    get_cache_layer as get_cache_service
)

# Specialized caches
from .specialized.jwt_cache import JWTCache
from .specialized.template_cache import TemplateCache
from .specialized.analytics_cache import AnalyticsCache
from .specialized.query_cache import QueryCache

# Invalidation
from .invalidation.invalidator import CacheInvalidator

__all__ = [
    # Base
    "CacheService",
    "CacheOperation",
    "CacheStrategy",
    "CacheMetrics",
    "get_cache_service",
    
    # Specialized
    "JWTCache",
    "TemplateCache",
    "AnalyticsCache",
    "QueryCache",
    
    # Invalidation
    "CacheInvalidator",
]

__version__ = "2.0.0"
```

---

### 2. `specialized/jwt_cache.py` - JWT Cache

```python
"""
JWT Cache - Specialized JWT Token Caching
==========================================

Wrapper around CacheLayer for JWT-specific operations.
"""
import logging
from typing import Optional, Dict, Any
from datetime import timedelta
from uuid import UUID

from app.services.ai.cache_layer import CacheLayer, CacheOperation, get_cache_layer

logger = logging.getLogger(__name__)


class JWTCache:
    """
    JWT token caching with blacklist management.
    
    Features:
    - Token validation caching
    - Blacklist management
    - Short TTL (minutes)
    - Fast lookups
    
    Example:
        >>> jwt_cache = JWTCache()
        >>> await jwt_cache.initialize()
        >>> await jwt_cache.cache_token("user:123", token_data, ttl=300)
        >>> is_valid = await jwt_cache.is_token_valid("user:123")
    """
    
    # TTL for JWT cache (5 minutes)
    DEFAULT_TTL = 300
    BLACKLIST_TTL = 86400  # 24 hours
    
    def __init__(self, cache_layer: Optional[CacheLayer] = None):
        """Initialize JWT cache."""
        self.cache = cache_layer
        self._initialized = False
    
    async def initialize(self):
        """Initialize cache layer."""
        if self._initialized:
            return
        
        if not self.cache:
            self.cache = await get_cache_layer()
        
        self._initialized = True
        logger.info("JWTCache initialized")
    
    async def cache_token(
        self,
        user_id: str,
        token_data: Dict[str, Any],
        ttl: Optional[int] = None
    ):
        """
        Cache JWT token data.
        
        Args:
            user_id: User identifier
            token_data: Token data to cache
            ttl: Time to live in seconds (default: 300)
        """
        key = f"jwt:{user_id}"
        await self.cache.set(
            key,
            token_data,
            CacheOperation.RESPONSE_GENERATION,  # Reuse operation type
            ttl=ttl or self.DEFAULT_TTL,
            tags=[f"user:{user_id}", "jwt"]
        )
    
    async def get_token(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached token data."""
        key = f"jwt:{user_id}"
        return await self.cache.get(key, CacheOperation.RESPONSE_GENERATION)
    
    async def invalidate_token(self, user_id: str):
        """Invalidate token for user."""
        key = f"jwt:{user_id}"
        await self.cache.invalidate(key)
    
    async def blacklist_token(self, token_jti: str, ttl: Optional[int] = None):
        """Add token to blacklist."""
        key = f"jwt:blacklist:{token_jti}"
        await self.cache.set(
            key,
            {"blacklisted": True, "timestamp": datetime.utcnow().isoformat()},
            CacheOperation.RESPONSE_GENERATION,
            ttl=ttl or self.BLACKLIST_TTL,
            tags=["jwt:blacklist"]
        )
    
    async def is_blacklisted(self, token_jti: str) -> bool:
        """Check if token is blacklisted."""
        key = f"jwt:blacklist:{token_jti}"
        result = await self.cache.get(key, CacheOperation.RESPONSE_GENERATION)
        return result is not None
    
    async def invalidate_user_tokens(self, user_id: str):
        """Invalidate all tokens for a user."""
        await self.cache.invalidate_by_tag(f"user:{user_id}")
```

---

### 3. `specialized/template_cache.py` - Template Cache

```python
"""
Template Cache - Specialized Template Caching
==============================================

Wrapper around CacheLayer for template-specific operations.
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
    - Long TTL (hours)
    
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
    
    async def initialize(self):
        """Initialize cache layer."""
        if self._initialized:
            return
        
        if not self.cache:
            self.cache = await get_cache_layer()
        
        self._initialized = True
        logger.info("TemplateCache initialized")
    
    async def cache_template(
        self,
        template_key: str,
        template_data: Dict[str, Any],
        version: Optional[str] = None,
        ttl: Optional[int] = None
    ):
        """Cache template data."""
        key = self._build_key(template_key, version)
        await self.cache.set(
            key,
            {**template_data, "_version": version, "_cached_at": datetime.utcnow().isoformat()},
            CacheOperation.TEMPLATE_HUMANIZATION,
            ttl=ttl or self.DEFAULT_TTL,
            tags=["template", f"template:{template_key}"]
        )
    
    async def get_template(
        self,
        template_key: str,
        version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get cached template."""
        key = self._build_key(template_key, version)
        return await self.cache.get(key, CacheOperation.TEMPLATE_HUMANIZATION)
    
    async def invalidate_template(self, template_key: str):
        """Invalidate all versions of a template."""
        await self.cache.invalidate_by_tag(f"template:{template_key}")
    
    async def preload_templates(self, template_keys: List[str]):
        """Preload multiple templates into cache."""
        # Implementation would load templates from DB and cache them
        pass
    
    def _build_key(self, template_key: str, version: Optional[str] = None) -> str:
        """Build cache key for template."""
        if version:
            return f"template:{template_key}:v{version}"
        return f"template:{template_key}"
```

---

### 4. `specialized/analytics_cache.py` - Analytics Cache

```python
"""
Analytics Cache - Specialized Analytics Data Caching
=====================================================

Wrapper around CacheLayer for analytics-specific operations.
"""
import logging
import gzip
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from app.services.ai.cache_layer import CacheLayer, CacheOperation, get_cache_layer

logger = logging.getLogger(__name__)


class AnalyticsCache:
    """
    Analytics data caching with compression.
    
    Features:
    - Time-series data caching
    - Aggregation caching
    - Compression for large datasets
    - Dashboard warming
    
    Example:
        >>> analytics_cache = AnalyticsCache()
        >>> await analytics_cache.initialize()
        >>> await analytics_cache.cache_aggregation("daily_stats", data)
    """
    
    # TTL for analytics (1 hour)
    DEFAULT_TTL = 3600
    AGGREGATION_TTL = 7200  # 2 hours
    
    def __init__(self, cache_layer: Optional[CacheLayer] = None):
        """Initialize analytics cache."""
        self.cache = cache_layer
        self._initialized = False
        self.compression_threshold = 1024  # Compress if > 1KB
    
    async def initialize(self):
        """Initialize cache layer."""
        if self._initialized:
            return
        
        if not self.cache:
            self.cache = await get_cache_layer()
        
        self._initialized = True
        logger.info("AnalyticsCache initialized")
    
    async def cache_aggregation(
        self,
        key: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None,
        compress: bool = True
    ):
        """Cache aggregated analytics data."""
        # Compress large datasets
        if compress and self._should_compress(data):
            data = self._compress_data(data)
        
        cache_key = f"analytics:agg:{key}"
        await self.cache.set(
            cache_key,
            data,
            CacheOperation.RESPONSE_GENERATION,
            ttl=ttl or self.AGGREGATION_TTL,
            tags=["analytics", "aggregation"]
        )
    
    async def get_aggregation(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached aggregation."""
        cache_key = f"analytics:agg:{key}"
        data = await self.cache.get(cache_key, CacheOperation.RESPONSE_GENERATION)
        
        # Decompress if needed
        if data and isinstance(data, dict) and data.get("_compressed"):
            data = self._decompress_data(data)
        
        return data
    
    async def cache_time_series(
        self,
        metric: str,
        start_date: datetime,
        end_date: datetime,
        data: List[Dict[str, Any]]
    ):
        """Cache time-series data."""
        key = f"analytics:ts:{metric}:{start_date.date()}:{end_date.date()}"
        await self.cache.set(
            key,
            {"data": data, "start": start_date.isoformat(), "end": end_date.isoformat()},
            CacheOperation.RESPONSE_GENERATION,
            ttl=self.DEFAULT_TTL,
            tags=["analytics", "time-series", f"metric:{metric}"]
        )
    
    async def warm_dashboard(self, dashboard_id: str, metrics: List[str]):
        """Warm cache for dashboard metrics."""
        # Pre-compute and cache common dashboard queries
        pass
    
    def _should_compress(self, data: Dict[str, Any]) -> bool:
        """Check if data should be compressed."""
        size = len(json.dumps(data))
        return size > self.compression_threshold
    
    def _compress_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Compress data using gzip."""
        json_str = json.dumps(data)
        compressed = gzip.compress(json_str.encode())
        return {
            "_compressed": True,
            "_original_size": len(json_str),
            "data": compressed.hex()
        }
    
    def _decompress_data(self, compressed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Decompress gzipped data."""
        compressed_bytes = bytes.fromhex(compressed_data["data"])
        decompressed = gzip.decompress(compressed_bytes)
        return json.loads(decompressed.decode())
```

---

### 5. `invalidation/invalidator.py` - Cache Invalidation

```python
"""
Cache Invalidator - Unified Invalidation Utilities
===================================================

Provides advanced cache invalidation strategies.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.services.ai.cache_layer import get_cache_layer, CacheLayer

logger = logging.getLogger(__name__)


class CacheInvalidator:
    """
    Unified cache invalidation utilities.
    
    Features:
    - Pattern-based invalidation
    - Tag-based invalidation
    - Cascade invalidation
    - Event-based invalidation
    - Scheduled invalidation
    
    Example:
        >>> invalidator = CacheInvalidator()
        >>> await invalidator.initialize()
        >>> await invalidator.invalidate_pattern("patient:*")
        >>> await invalidator.cascade_invalidate("patient:123", related_tags)
    """
    
    def __init__(self, cache_layer: Optional[CacheLayer] = None):
        """Initialize invalidator."""
        self.cache = cache_layer
        self._initialized = False
    
    async def initialize(self):
        """Initialize cache layer."""
        if self._initialized:
            return
        
        if not self.cache:
            self.cache = await get_cache_layer()
        
        self._initialized = True
        logger.info("CacheInvalidator initialized")
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching pattern.
        
        Args:
            pattern: Pattern to match (supports wildcards)
        
        Returns:
            Number of keys invalidated
        """
        await self.cache.invalidate(pattern)
        logger.info(f"Invalidated keys matching pattern: {pattern}")
        return 0  # CacheLayer doesn't return count
    
    async def invalidate_tags(self, tags: List[str]) -> int:
        """
        Invalidate all keys with any of the given tags.
        
        Args:
            tags: List of tags to invalidate
        
        Returns:
            Total number of keys invalidated
        """
        count = 0
        for tag in tags:
            await self.cache.invalidate_by_tag(tag)
            count += 1
        
        logger.info(f"Invalidated {count} tags")
        return count
    
    async def cascade_invalidate(
        self,
        primary_key: str,
        related_tags: List[str]
    ):
        """
        Cascade invalidation from primary key to related tags.
        
        Args:
            primary_key: Primary key to invalidate
            related_tags: Related tags to also invalidate
        """
        # Invalidate primary
        await self.cache.invalidate(primary_key)
        
        # Invalidate related
        await self.invalidate_tags(related_tags)
        
        logger.info(f"Cascade invalidation from {primary_key} to {len(related_tags)} tags")
    
    async def invalidate_user_data(self, user_id: str):
        """Invalidate all user-related caches."""
        await self.invalidate_tags([
            f"user:{user_id}",
            f"patient:{user_id}",
            f"jwt:user:{user_id}"
        ])
    
    async def invalidate_patient_data(self, patient_id: str):
        """Invalidate all patient-related caches."""
        await self.invalidate_tags([
            f"patient:{patient_id}",
            f"analytics:patient:{patient_id}",
            f"quiz:patient:{patient_id}"
        ])
```

---

## 📋 MIGRATION PLAN

### Phase 1: Preparação (30min)

- [ ] Criar estrutura `app/services/cache/`
- [ ] Criar `__init__.py` base
- [ ] Criar subdiretórios (specialized, invalidation)
- [ ] Documentar arquivos a serem removidos

### Phase 2: Implementação (4-5h)

- [ ] Implementar `specialized/jwt_cache.py` (1h)
- [ ] Implementar `specialized/template_cache.py` (1h)
- [ ] Implementar `specialized/analytics_cache.py` (1.5h)
- [ ] Implementar `specialized/query_cache.py` (1h)
- [ ] Implementar `invalidation/invalidator.py` (30min)

### Phase 3: Testing (1h)

- [ ] Rodar testes baseline de cache (45+ tests)
- [ ] Validar JWT cache funcionando
- [ ] Validar template cache funcionando
- [ ] Validar analytics cache funcionando

### Phase 4: Migration (1h)

- [ ] Identificar imports de caches antigos
- [ ] Atualizar para novo módulo
- [ ] Testar alterações

### Phase 5: Cleanup (30min)

- [ ] Remover arquivos antigos
- [ ] Atualizar SERVICES_MAP.md
- [ ] Atualizar documentação

**Tempo Total:** 6-8 horas

---

## ✅ CRITÉRIOS DE SUCESSO

### Métricas

- ✅ **10 arquivos → 1 módulo** (6 arquivos organizados)
- ✅ **Base cache unificado** (reusar cache_layer.py)
- ✅ **Caches especializados** funcionais
- ✅ **Zero duplicação** de código base
- ✅ **100% testes passando** (45+ tests)

### Funcionalidades Mantidas

- ✅ JWT token caching e blacklist
- ✅ Template caching com versões
- ✅ Analytics caching com compressão
- ✅ Query caching
- ✅ Pattern/tag-based invalidation
- ✅ Cache warming
- ✅ Performance metrics

---

## 🎯 IMPACTO ESPERADO

### Código

- 📦 **Arquivos:** 10 → 6 (40% redução)
- 📝 **LOC:** ~2,500 → ~1,200 (52% redução)
- 🔄 **Duplicação:** ~800 LOC → 0 (100% eliminação)
- 🗂️ **Organização:** Módulo estruturado

### Quality

- ✅ **API consistente** (todas usam CacheLayer)
- ✅ **Type hints 100%**
- ✅ **Docstrings completas**
- ✅ **Design patterns** (Strategy, Facade)

### Performance

- ⚡ **Cache:** Mantido (Redis + memory fallback)
- 🚀 **Latency:** Mantido
- 📊 **Métricas:** Unificadas

---

**Status:** 📋 PLANEJADO  
**Próximo:** Implementação  
**Dependências:** QW-018 ✅ Completo  

**Última Atualização:** 20 de Janeiro de 2025  
**Autor:** AI Architect