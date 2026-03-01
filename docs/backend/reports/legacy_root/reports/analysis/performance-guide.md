# Guia de Performance - Backend Hormonia

**Versao**: 2.0.0
**Data**: Dezembro 2025
**Status**: Producao

---

## Indice

1. [Metricas de Performance](#1-metricas-de-performance)
2. [Cache de 3 Camadas](#2-cache-de-3-camadas-redis-l2--memory-l1--tanstack)
3. [Connection Pooling](#3-connection-pooling)
4. [Indices de Database](#4-indices-de-database)
5. [Otimizacao de Startup](#5-otimizacao-de-startup)
6. [Rate Limiting](#6-rate-limiting)
7. [Monitoramento](#7-monitoramento)
8. [Troubleshooting de Performance](#8-troubleshooting-de-performance)

---

## 1. Metricas de Performance

### 1.1 Resultados Alcancados

| Metrica | Antes | Depois | Melhoria |
|---------|-------|--------|----------|
| Tempo de Startup | 56s | 16s | **73%** |
| Queries N+1 | 120+ | 4 | **97%** |
| Tempo de Resposta API | 800ms | 120ms | **85%** |
| CPU Database | 70% | <15% | **78%** |
| Cache Hit Rate | 0% | 85%+ | **85%** |

### 1.2 Baseline de Performance

```
Endpoint Performance Targets:
----------------------------
GET /patients          < 200ms (p95)
GET /dashboard         < 300ms (p95)
POST /messages         < 150ms (p95)
GET /analytics         < 500ms (p95)
WebSocket latency      < 50ms
```

### 1.3 Metricas Criticas para Monitorar

```python
# Metricas de Sistema
CPU_THRESHOLD_WARNING = 70
CPU_THRESHOLD_CRITICAL = 85
MEMORY_THRESHOLD_WARNING = 75
MEMORY_THRESHOLD_CRITICAL = 90

# Metricas de Database
DB_QUERY_TIME_WARNING = 100  # ms
DB_QUERY_TIME_CRITICAL = 500  # ms
CONNECTION_POOL_WARNING = 80  # % utilizacao
CONNECTION_POOL_CRITICAL = 95  # % utilizacao

# Metricas de Cache
CACHE_HIT_RATE_TARGET = 80  # %
CACHE_LATENCY_TARGET = 5  # ms
```

### 1.4 Analise de Bottlenecks Identificados

| Componente | Impacto | Tempo | Status |
|------------|---------|-------|--------|
| Firebase Admin SDK | Critico | 10-30s | Paralelizado |
| Redis Connection | Alto | 5-15s | Fast-fail 2s |
| Monitoring Init | Alto | 8-30s | Paralelizado |
| N+1 Queries | Alto | +500ms | Corrigido |
| Missing Indexes | Medio | +200ms | Adicionados |

---

## 2. Cache de 3 Camadas (Redis L2 + Memory L1 + TanStack)

### 2.1 Arquitetura de Cache

```
                    +------------------+
                    |    TanStack      |
                    |  (Client-Side)   |
                    |    L0 Cache      |
                    +--------+---------+
                             |
                    +--------v---------+
                    |   Memory L1      |
                    |   (In-Process)   |
                    |   TTL: 60s       |
                    +--------+---------+
                             |
                    +--------v---------+
                    |   Redis L2       |
                    |   (Distributed)  |
                    |   TTL: 300s      |
                    +--------+---------+
                             |
                    +--------v---------+
                    |   PostgreSQL     |
                    |   (Source)       |
                    +------------------+
```

### 2.2 Configuracao de TTL por Endpoint

```python
CACHE_TTL_CONFIG = {
    # Dados frequentemente acessados
    "patients": 120,        # 2 minutos
    "patients_list": 60,    # 1 minuto

    # Dashboard (dados agregados)
    "dashboard": 60,        # 1 minuto
    "analytics": 180,       # 3 minutos

    # Templates (raramente mudam)
    "templates": 300,       # 5 minutos
    "message_templates": 300,

    # Reports (computacao pesada)
    "reports": 180,         # 3 minutos
    "statistics": 120,      # 2 minutos

    # Sessoes de quiz
    "quiz_sessions": 60,    # 1 minuto

    # Contagens (alta frequencia)
    "counts": 60,           # 1 minuto
}
```

### 2.3 Implementacao do Cache Middleware

```python
from functools import wraps
from typing import Optional, Callable
import hashlib
import json

class CacheMiddleware:
    """Middleware de cache com isolamento por usuario."""

    def __init__(self, redis_client, memory_cache):
        self.redis = redis_client
        self.memory = memory_cache

    def generate_cache_key(
        self,
        method: str,
        path: str,
        query_params: dict,
        user_id: Optional[str] = None
    ) -> str:
        """
        Gera chave de cache com isolamento por usuario.

        Formato: http:{method}:{path}:{query_hash}:{user_id}
        """
        query_hash = hashlib.md5(
            json.dumps(query_params, sort_keys=True).encode()
        ).hexdigest()[:8]

        parts = [f"http:{method}:{path}:{query_hash}"]
        if user_id:
            parts.append(user_id)

        return ":".join(parts)

    async def get(self, key: str) -> Optional[dict]:
        """
        Busca em L1 (memory) primeiro, depois L2 (Redis).
        """
        # L1: Memory cache
        value = self.memory.get(key)
        if value:
            return value

        # L2: Redis cache
        value = await self.redis.get(key)
        if value:
            # Promove para L1
            self.memory.set(key, value, ttl=60)
            return value

        return None

    async def set(
        self,
        key: str,
        value: dict,
        ttl: int = 120
    ) -> None:
        """
        Armazena em ambas as camadas.
        """
        # L1: Memory (TTL menor)
        self.memory.set(key, value, ttl=min(ttl, 60))

        # L2: Redis (TTL completo)
        await self.redis.setex(key, ttl, json.dumps(value))

    async def invalidate(self, pattern: str) -> int:
        """
        Invalida cache por pattern.
        Retorna numero de chaves removidas.
        """
        # Limpa L1
        self.memory.clear_pattern(pattern)

        # Limpa L2
        keys = await self.redis.keys(pattern)
        if keys:
            return await self.redis.delete(*keys)
        return 0
```

### 2.4 Decorator de Cache para Endpoints

```python
def cached_endpoint(
    ttl: int = 120,
    key_prefix: str = "",
    user_isolated: bool = True
):
    """
    Decorator para cache de endpoints.

    Args:
        ttl: Time-to-live em segundos
        key_prefix: Prefixo para a chave de cache
        user_isolated: Se True, isola cache por usuario
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extrai request e user do contexto
            request = kwargs.get('request')
            current_user = kwargs.get('current_user')

            # Gera chave de cache
            user_id = current_user.id if user_isolated and current_user else None
            cache_key = cache_middleware.generate_cache_key(
                method=request.method,
                path=request.url.path,
                query_params=dict(request.query_params),
                user_id=user_id
            )

            if key_prefix:
                cache_key = f"{key_prefix}:{cache_key}"

            # Tenta buscar do cache
            cached = await cache_middleware.get(cache_key)
            if cached:
                return cached

            # Executa funcao original
            result = await func(*args, **kwargs)

            # Armazena no cache
            await cache_middleware.set(cache_key, result, ttl)

            return result

        return wrapper
    return decorator


# Exemplo de uso
@router.get("/patients")
@cached_endpoint(ttl=120, key_prefix="patients", user_isolated=True)
async def list_patients(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await patient_service.list_patients(db, current_user.id)
```

### 2.5 Invalidacao de Cache

```python
class CacheInvalidationService:
    """Servico de invalidacao de cache por eventos."""

    INVALIDATION_PATTERNS = {
        "patient_created": ["patients:*", "dashboard:*", "counts:*"],
        "patient_updated": ["patients:{id}:*", "patients:list:*"],
        "message_sent": ["messages:*", "analytics:*"],
        "quiz_completed": ["quiz:*", "analytics:*"],
    }

    async def on_event(self, event_type: str, **kwargs) -> None:
        """
        Invalida cache baseado em evento.
        """
        patterns = self.INVALIDATION_PATTERNS.get(event_type, [])

        for pattern in patterns:
            # Substitui placeholders
            resolved_pattern = pattern.format(**kwargs)

            count = await cache_middleware.invalidate(resolved_pattern)
            logger.debug(
                f"Cache invalidated: {resolved_pattern} ({count} keys)"
            )

    async def invalidate_user_cache(self, user_id: str) -> None:
        """Invalida todo cache de um usuario."""
        await cache_middleware.invalidate(f"*:{user_id}")

    async def invalidate_all(self) -> None:
        """Invalida todo o cache (usar com cuidado)."""
        await cache_middleware.invalidate("*")
```

### 2.6 TanStack Query (Frontend)

```typescript
// Configuracao TanStack Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000,      // 1 minuto
      gcTime: 5 * 60 * 1000,     // 5 minutos (garbage collection)
      refetchOnWindowFocus: false,
      retry: 3,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    },
  },
});

// Hook com cache otimizado
export function usePatients() {
  return useQuery({
    queryKey: ['patients'],
    queryFn: () => api.get('/patients'),
    staleTime: 2 * 60 * 1000,  // 2 minutos
    gcTime: 10 * 60 * 1000,    // 10 minutos
  });
}

// Invalidacao apos mutacao
export function useCreatePatient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data) => api.post('/patients', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}
```

---

## 3. Connection Pooling

### 3.1 Configuracao do Pool de Conexoes

```python
# app/core/database.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

# Configuracao otimizada do pool
DATABASE_POOL_CONFIG = {
    "pool_size": 10,           # Conexoes permanentes por worker
    "max_overflow": 10,        # Conexoes extras sob demanda
    "pool_timeout": 30,        # Timeout para obter conexao
    "pool_recycle": 1800,      # Recicla conexoes a cada 30 min
    "pool_pre_ping": True,     # Verifica conexao antes de usar
    "echo": False,             # Desabilita logging SQL em producao
}

# Total de conexoes: workers * (pool_size + max_overflow)
# Exemplo: 4 workers * (10 + 10) = 80 conexoes maximas

engine = create_async_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    **DATABASE_POOL_CONFIG
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)
```

### 3.2 Dimensionamento do Pool

```
Calculo de Conexoes:
-------------------
PostgreSQL max_connections = 100 (default)

Reservas:
- Superuser: 3 conexoes
- Monitoring: 5 conexoes
- Migrations: 2 conexoes
- Disponivel: 90 conexoes

Workers Gunicorn: 4 (2 * CPU cores)
Pool por Worker: 10 + 10 overflow = 20
Total Maximo: 4 * 20 = 80 conexoes

Margem de Seguranca: 90 - 80 = 10 conexoes
```

### 3.3 Monitoramento do Pool

```python
async def check_pool_health() -> dict:
    """
    Verifica saude do pool de conexoes.

    Returns:
        Dict com metricas do pool
    """
    pool = engine.pool

    pool_size = pool.size()
    checked_out = pool.checkedout()
    overflow = pool.overflow()
    utilization = (checked_out / pool_size * 100) if pool_size > 0 else 0

    health = {
        "pool_size": pool_size,
        "checked_out": checked_out,
        "checked_in": pool.checkedin(),
        "overflow": overflow,
        "overflow_max": pool._max_overflow,
        "utilization_percent": round(utilization, 2),
        "status": "healthy"
    }

    # Alertas por threshold
    if utilization >= 95:
        health["status"] = "critical"
        logger.error(
            f"CRITICAL: Connection pool near exhaustion: {utilization:.1f}%",
            extra={
                "event_type": "connection_pool_critical",
                "utilization": utilization,
                "checked_out": checked_out,
                "pool_size": pool_size
            }
        )
    elif utilization >= 80:
        health["status"] = "warning"
        logger.warning(
            f"WARNING: High connection pool utilization: {utilization:.1f}%",
            extra={
                "event_type": "connection_pool_warning",
                "utilization": utilization
            }
        )

    return health
```

### 3.4 Redis Connection Pool

```python
# app/core/redis.py

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

REDIS_POOL_CONFIG = {
    "max_connections": 50,
    "socket_timeout": 5.0,
    "socket_connect_timeout": 2.0,
    "retry_on_timeout": True,
    "health_check_interval": 30,
}

redis_pool = ConnectionPool.from_url(
    REDIS_URL,
    **REDIS_POOL_CONFIG,
    decode_responses=True,
)

redis_client = redis.Redis(connection_pool=redis_pool)

# Circuit breaker para Redis
class RedisCircuitBreaker:
    """Circuit breaker para proteger contra falhas do Redis."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 30
    ):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    async def call(self, func, *args, **kwargs):
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise CircuitBreakerOpen("Redis circuit breaker is open")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        self.failure_count = 0
        self.state = "closed"

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.error("Redis circuit breaker opened")

    def _should_attempt_reset(self) -> bool:
        return (
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
```

---

## 4. Indices de Database

### 4.1 Indices Criticos Implementados

```sql
-- Indice para busca de pacientes por clinica
CREATE INDEX CONCURRENTLY idx_patients_clinic_created
ON patients (clinic_id, created_at DESC)
WHERE deleted_at IS NULL;

-- Indice para mensagens nao lidas
CREATE INDEX CONCURRENTLY idx_messages_unread
ON messages (patient_id, is_read, created_at DESC)
WHERE is_read = FALSE;

-- Indice composto para flow analytics
CREATE INDEX CONCURRENTLY idx_flow_analytics_patient_type
ON flow_analytics (patient_id, event_type, created_at DESC);

-- Indice para sessoes de quiz ativas
CREATE INDEX CONCURRENTLY idx_quiz_sessions_active
ON quiz_sessions (patient_id, status, updated_at DESC)
WHERE status IN ('pending', 'in_progress');

-- Indice parcial para pacientes ativos
CREATE INDEX CONCURRENTLY idx_patients_active
ON patients (clinic_id, status, last_activity_at DESC)
WHERE status = 'active' AND deleted_at IS NULL;

-- Indice GIN para busca full-text em pacientes
CREATE INDEX CONCURRENTLY idx_patients_search
ON patients USING GIN (
    to_tsvector('portuguese', coalesce(name, '') || ' ' || coalesce(email, ''))
);

-- Indice para metricas de entrega
CREATE INDEX CONCURRENTLY idx_messages_delivery_metrics
ON messages (clinic_id, sent_at, delivery_status)
WHERE sent_at IS NOT NULL;

-- Indice para contagem de sentimentos
CREATE INDEX CONCURRENTLY idx_messages_sentiment
ON messages (clinic_id, sentiment, created_at)
WHERE sentiment IS NOT NULL;
```

### 4.2 Analise de Queries Lentas

```sql
-- Identificar queries lentas
SELECT
    query,
    calls,
    total_time / 1000 as total_seconds,
    mean_time / 1000 as mean_seconds,
    rows
FROM pg_stat_statements
WHERE mean_time > 100  -- queries > 100ms
ORDER BY mean_time DESC
LIMIT 20;

-- Identificar indices nao utilizados
SELECT
    schemaname,
    relname as table_name,
    indexrelname as index_name,
    idx_scan as times_used,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC;

-- Verificar uso de indices
SELECT
    relname as table_name,
    seq_scan,
    idx_scan,
    CASE
        WHEN seq_scan + idx_scan = 0 THEN 0
        ELSE round(100.0 * idx_scan / (seq_scan + idx_scan), 2)
    END as idx_usage_percent
FROM pg_stat_user_tables
ORDER BY seq_scan DESC;
```

### 4.3 Script de Manutencao de Indices

```python
# scripts/maintain_indexes.py

import asyncio
from sqlalchemy import text

async def analyze_tables():
    """Atualiza estatisticas das tabelas."""
    tables = [
        'patients', 'messages', 'quiz_sessions',
        'flow_analytics', 'appointments'
    ]

    async with engine.begin() as conn:
        for table in tables:
            await conn.execute(text(f"ANALYZE {table}"))
            logger.info(f"Analyzed table: {table}")

async def reindex_if_bloated(threshold: float = 30.0):
    """
    Reindexa indices com bloat acima do threshold.

    Args:
        threshold: Porcentagem de bloat para trigger reindex
    """
    query = """
    SELECT
        schemaname || '.' || indexrelname as index_name,
        pg_relation_size(indexrelid) as index_size,
        pg_stat_get_live_tuples(indexrelid) as live_tuples
    FROM pg_stat_user_indexes
    WHERE pg_relation_size(indexrelid) > 1024 * 1024  -- > 1MB
    """

    async with engine.begin() as conn:
        result = await conn.execute(text(query))

        for row in result:
            # Estima bloat (simplificado)
            estimated_bloat = estimate_index_bloat(row)

            if estimated_bloat > threshold:
                logger.info(
                    f"Reindexing {row.index_name} "
                    f"(bloat: {estimated_bloat:.1f}%)"
                )
                await conn.execute(
                    text(f"REINDEX INDEX CONCURRENTLY {row.index_name}")
                )

# Executar semanalmente via cron
if __name__ == "__main__":
    asyncio.run(analyze_tables())
    asyncio.run(reindex_if_bloated())
```

---

## 5. Otimizacao de Startup

### 5.1 Inicializacao Paralela em 2 Fases

```python
# app/core/lifespan.py

import asyncio
import time
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager com inicializacao paralela.

    Fase 1: Servicos independentes (paralelo)
    Fase 2: Servicos dependentes (sequencial)
    """
    start_time = time.time()
    logger.info("Starting Hormonia Backend System (parallel initialization)")

    # ==========================================
    # FASE 1: Servicos Independentes (Paralelo)
    # ==========================================
    phase1_start = time.time()
    logger.info("Phase 1: Initializing independent services in parallel...")

    results = await asyncio.gather(
        _initialize_monitoring(app),           # 10-30s
        _initialize_redis_websocket(app),      # 5-15s
        _initialize_ai_services(app),          # 1-3s
        _initialize_enum_validation(app),      # <1s
        return_exceptions=True
    )

    # Log erros da Fase 1
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Phase 1 service {i} failed: {result}")

    phase1_time = time.time() - phase1_start
    logger.info(f"Phase 1 completed in {phase1_time:.2f}s")

    # ==========================================
    # FASE 2a: Servicos Semi-dependentes (Paralelo)
    # ==========================================
    phase2a_start = time.time()

    await asyncio.gather(
        _initialize_websocket_manager(app),    # 2-5s
        _initialize_session_manager(app),      # 2-5s
        return_exceptions=True
    )

    phase2a_time = time.time() - phase2a_start

    # ==========================================
    # FASE 2b: Servicos Dependentes (Sequencial)
    # ==========================================
    phase2b_start = time.time()

    await _initialize_redis_pubsub(app)        # 2-5s (needs WebSocket)
    await _initialize_follow_up_system(app)    # 2-5s (needs Session)

    phase2b_time = time.time() - phase2b_start
    logger.info(f"Phase 2 completed in {phase2a_time + phase2b_time:.2f}s")

    # ==========================================
    # Startup Completo
    # ==========================================
    total_time = time.time() - start_time
    logger.info(f"Hormonia Backend startup completed in {total_time:.2f}s")

    yield

    # Shutdown
    await _shutdown(app)


async def _initialize_with_timeout(
    name: str,
    coro,
    timeout: float = 30.0
) -> bool:
    """
    Inicializa servico com timeout.

    Args:
        name: Nome do servico
        coro: Coroutine de inicializacao
        timeout: Timeout em segundos

    Returns:
        True se sucesso, False se falhou
    """
    start = time.time()

    try:
        await asyncio.wait_for(coro, timeout=timeout)
        elapsed = time.time() - start
        logger.info(f"[OK] {name} initialized ({elapsed:.2f}s)")
        return True

    except asyncio.TimeoutError:
        elapsed = time.time() - start
        logger.error(
            f"[TIMEOUT] {name} timed out after {elapsed:.2f}s"
        )
        return False

    except Exception as e:
        elapsed = time.time() - start
        logger.error(
            f"[FAILED] {name} failed ({elapsed:.2f}s): {e}"
        )
        return False
```

### 5.2 Configuracao de Timeouts

```python
# app/core/settings.py

class StartupSettings:
    """Configuracoes de timeout para startup."""

    # Timeouts por servico (segundos)
    FIREBASE_TIMEOUT = 30.0
    REDIS_TIMEOUT = 10.0
    DATABASE_TIMEOUT = 15.0
    MONITORING_TIMEOUT = 30.0
    WEBSOCKET_TIMEOUT = 10.0

    # Fast-fail para servicos nao-criticos
    AI_SERVICES_TIMEOUT = 5.0
    ENUM_VALIDATION_TIMEOUT = 2.0

    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # segundos
    RETRY_BACKOFF = 2.0  # multiplicador
```

### 5.3 Timeline de Startup Otimizado

```
Sequencial (Antes):
==================
0s   [=========] Monitoring (10-30s)
30s  [====] Redis (5-15s)
45s  [==] WebSocket Manager (2-5s)
50s  [==] Redis Pub/Sub (2-5s)
55s  [==] Session Manager (2-5s)
60s  [=] AI Services (1-3s)
63s  [.] Enum Validation (<1s)
64s  [==] Follow-up System (2-5s)
---
Total: 56-68s


Paralelo (Depois):
==================
       Fase 1 (Paralelo)
0s   [=========] Monitoring (10-30s)
0s   [====] Redis (5-15s)
0s   [=] AI Services (1-3s)
0s   [.] Enum Validation (<1s)
       |
       v max(10-30s) = 10-30s

       Fase 2a (Paralelo)
30s  [==] WebSocket Manager (2-5s)
30s  [==] Session Manager (2-5s)
       |
       v max(2-5s) = 2-5s

       Fase 2b (Sequencial)
35s  [==] Redis Pub/Sub (2-5s)
40s  [==] Follow-up System (2-5s)
---
Total: 16-45s (media 28s)

Melhoria: 50-73%
```

---

## 6. Rate Limiting

### 6.1 Configuracao de Rate Limits

```python
# app/core/rate_limiting.py

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Limites por tipo de endpoint
RATE_LIMITS = {
    # Autenticacao (protecer contra brute force)
    "auth": "5/minute",
    "login": "10/minute",
    "password_reset": "3/hour",

    # APIs de leitura (mais permissivo)
    "read": "100/minute",
    "list": "60/minute",

    # APIs de escrita (mais restritivo)
    "write": "30/minute",
    "create": "20/minute",

    # Endpoints pesados
    "export": "5/minute",
    "report": "10/minute",

    # WebSocket
    "websocket_connect": "10/minute",
    "websocket_message": "60/minute",
}

# Limites por role
ROLE_MULTIPLIERS = {
    "admin": 3.0,
    "manager": 2.0,
    "staff": 1.0,
    "patient": 0.5,
}
```

### 6.2 Implementacao do Rate Limiter

```python
from fastapi import Request, HTTPException
from slowapi.errors import RateLimitExceeded

def rate_limit(limit_type: str = "read"):
    """
    Decorator de rate limiting.

    Args:
        limit_type: Tipo de limite (auth, read, write, etc)
    """
    base_limit = RATE_LIMITS.get(limit_type, "60/minute")

    def decorator(func):
        @wraps(func)
        @limiter.limit(base_limit)
        async def wrapper(request: Request, *args, **kwargs):
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


# Handler de erro de rate limit
@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded
):
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please try again later.",
            "retry_after": exc.detail
        },
        headers={
            "Retry-After": str(exc.detail),
            "X-RateLimit-Limit": request.state.view_rate_limit,
            "X-RateLimit-Remaining": "0",
        }
    )


# Exemplo de uso
@router.post("/login")
@rate_limit("login")
async def login(request: Request, credentials: LoginRequest):
    return await auth_service.login(credentials)


@router.get("/patients")
@rate_limit("list")
async def list_patients(request: Request, db: AsyncSession = Depends(get_db)):
    return await patient_service.list(db)
```

### 6.3 Rate Limiting Distribuido com Redis

```python
import redis.asyncio as redis
from datetime import datetime

class DistributedRateLimiter:
    """Rate limiter distribuido usando Redis."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> tuple[bool, int]:
        """
        Verifica se requisicao e permitida.

        Usa algoritmo de sliding window.

        Returns:
            (allowed: bool, remaining: int)
        """
        now = datetime.now().timestamp()
        window_start = now - window_seconds

        pipe = self.redis.pipeline()

        # Remove requests antigos
        pipe.zremrangebyscore(key, 0, window_start)

        # Conta requests na janela
        pipe.zcard(key)

        # Adiciona request atual
        pipe.zadd(key, {str(now): now})

        # Define expiracao
        pipe.expire(key, window_seconds)

        results = await pipe.execute()
        request_count = results[1]

        remaining = max(0, limit - request_count - 1)
        allowed = request_count < limit

        return allowed, remaining

    async def get_rate_limit_key(
        self,
        identifier: str,
        endpoint: str
    ) -> str:
        """Gera chave de rate limit."""
        return f"ratelimit:{endpoint}:{identifier}"
```

---

## 7. Monitoramento

### 7.1 Componentes de Monitoramento

```python
# app/monitoring/manager.py

class MonitoringManager:
    """Gerenciador central de monitoramento."""

    def __init__(self):
        self.apm_collector = None
        self.db_monitor = None
        self.resource_monitor = None
        self.business_metrics = None
        self.anomaly_detector = None

    async def initialize(self):
        """Inicializa componentes em paralelo."""
        await asyncio.gather(
            self._init_apm_collector(),
            self._init_db_monitor(),
            self._init_resource_monitor(),
            self._init_business_metrics(),
            return_exceptions=True
        )

        # Componentes dependentes
        await self._init_anomaly_detector()

    async def _init_apm_collector(self):
        """Application Performance Monitoring."""
        self.apm_collector = APMCollector(
            sample_rate=0.1,  # 10% das requests
            slow_threshold_ms=500
        )

    async def _init_db_monitor(self):
        """Monitoramento de database."""
        self.db_monitor = DatabasePerformanceMonitor(
            connection_pool=engine.pool,
            alert_threshold_ms=100
        )

    async def _init_resource_monitor(self):
        """Monitoramento de recursos do sistema."""
        self.resource_monitor = ResourceMonitor(
            cpu_threshold=80,
            memory_threshold=85,
            disk_threshold=90
        )
```

### 7.2 APM Collector

```python
class APMCollector:
    """Coleta metricas de performance da aplicacao."""

    def __init__(self, sample_rate: float = 0.1):
        self.sample_rate = sample_rate
        self.metrics = defaultdict(list)

    async def record_request(
        self,
        endpoint: str,
        method: str,
        duration_ms: float,
        status_code: int
    ):
        """Registra metricas de uma request."""
        if random.random() > self.sample_rate:
            return

        self.metrics[endpoint].append({
            "method": method,
            "duration_ms": duration_ms,
            "status_code": status_code,
            "timestamp": datetime.now()
        })

        # Alerta para requests lentas
        if duration_ms > 500:
            logger.warning(
                f"Slow request: {method} {endpoint} ({duration_ms:.0f}ms)",
                extra={
                    "event_type": "slow_request",
                    "endpoint": endpoint,
                    "duration_ms": duration_ms
                }
            )

    def get_percentiles(self, endpoint: str) -> dict:
        """Calcula percentis de latencia."""
        durations = [m["duration_ms"] for m in self.metrics[endpoint]]

        if not durations:
            return {}

        durations.sort()
        n = len(durations)

        return {
            "p50": durations[int(n * 0.5)],
            "p90": durations[int(n * 0.9)],
            "p95": durations[int(n * 0.95)],
            "p99": durations[int(n * 0.99)] if n > 100 else durations[-1],
        }
```

### 7.3 Memory Profiler

```python
# app/monitoring/memory_profiler.py

import tracemalloc
from typing import List, Dict, Any

class MemoryProfiler:
    """Profiler de memoria com deteccao de leaks."""

    def __init__(self):
        self.enabled = False
        self.snapshots = []
        self.baseline = None

    def start(self):
        """Inicia profiling de memoria."""
        tracemalloc.start()
        self.enabled = True
        self.baseline = tracemalloc.take_snapshot()
        logger.info("Memory profiling started")

    def take_snapshot(self) -> Dict[str, Any]:
        """Tira snapshot e compara com baseline."""
        if not self.enabled:
            return {"error": "Profiling not enabled"}

        snapshot = tracemalloc.take_snapshot()
        self.snapshots.append({
            "timestamp": datetime.now(),
            "snapshot": snapshot
        })

        # Compara com baseline
        top_stats = snapshot.compare_to(self.baseline, 'lineno')

        # Top 10 consumidores
        top_10 = []
        for stat in top_stats[:10]:
            top_10.append({
                "file": stat.traceback.format()[0],
                "size_mb": stat.size / 1024 / 1024,
                "size_diff_mb": stat.size_diff / 1024 / 1024,
                "count": stat.count,
                "count_diff": stat.count_diff
            })

        current, peak = tracemalloc.get_traced_memory()

        return {
            "timestamp": datetime.now().isoformat(),
            "current_mb": current / 1024 / 1024,
            "peak_mb": peak / 1024 / 1024,
            "top_10_consumers": top_10,
            "total_snapshots": len(self.snapshots)
        }

    def detect_leaks(self, threshold_mb: float = 10.0) -> List[Dict]:
        """Detecta potenciais memory leaks."""
        if len(self.snapshots) < 2:
            return []

        leaks = []

        for i in range(len(self.snapshots) - 1):
            old = self.snapshots[i]["snapshot"]
            new = self.snapshots[i + 1]["snapshot"]

            diff = new.compare_to(old, 'lineno')

            for stat in diff:
                size_diff_mb = stat.size_diff / 1024 / 1024

                if size_diff_mb > threshold_mb:
                    leaks.append({
                        "file": stat.traceback.format()[0],
                        "size_increase_mb": size_diff_mb,
                        "timestamp_start": self.snapshots[i]["timestamp"],
                        "timestamp_end": self.snapshots[i + 1]["timestamp"]
                    })

        return leaks


# Task periodica de verificacao
async def periodic_memory_check():
    """Executa a cada hora para detectar leaks."""
    profiler = get_memory_profiler()

    while True:
        await asyncio.sleep(3600)  # 1 hora

        snapshot = profiler.take_snapshot()
        leaks = profiler.detect_leaks(threshold_mb=10.0)

        logger.info(
            f"Memory check: {snapshot['current_mb']:.2f}MB current, "
            f"{snapshot['peak_mb']:.2f}MB peak"
        )

        if leaks:
            logger.error(f"Potential memory leaks detected: {len(leaks)}")
            for leak in leaks:
                logger.error(f"Leak: {leak}")
```

### 7.4 Health Check Endpoints

```python
# app/routers/health.py

@router.get("/health")
async def health_check():
    """Health check basico."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@router.get("/health/detailed")
async def detailed_health_check(
    db: AsyncSession = Depends(get_db)
):
    """Health check detalhado com todos os componentes."""
    checks = {}

    # Database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = {"status": "healthy"}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}

    # Redis
    try:
        await redis_client.ping()
        checks["redis"] = {"status": "healthy"}
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "error": str(e)}

    # Connection Pool
    pool_health = await check_pool_health()
    checks["connection_pool"] = pool_health

    # Memory
    profiler = get_memory_profiler()
    if profiler.enabled:
        memory_stats = profiler.take_snapshot()
        checks["memory"] = {
            "current_mb": memory_stats["current_mb"],
            "peak_mb": memory_stats["peak_mb"]
        }

    # Status geral
    overall_status = "healthy"
    for component, status in checks.items():
        if status.get("status") in ["unhealthy", "critical"]:
            overall_status = "unhealthy"
            break
        elif status.get("status") == "warning":
            overall_status = "degraded"

    return {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "checks": checks
    }
```

---

## 8. Troubleshooting de Performance

### 8.1 Problemas Comuns e Solucoes

#### 8.1.1 Startup Lento (> 30s)

**Sintomas:**
- Aplicacao demora para responder apos deploy
- Health check falha por timeout
- Logs mostram inicializacao sequencial

**Diagnostico:**
```bash
# Verificar tempo de cada servico
grep "initialized\|completed\|failed" logs/startup.log | sort -t'(' -k2 -n
```

**Solucoes:**
1. Verificar se inicializacao paralela esta ativa
2. Reduzir timeouts de conexao
3. Mover servicos nao-criticos para background
4. Verificar conectividade de rede (Firebase, Redis)

#### 8.1.2 Queries Lentas (> 500ms)

**Sintomas:**
- Endpoints especificos com alta latencia
- CPU do database alto
- Timeout em requests

**Diagnostico:**
```sql
-- Queries mais lentas
SELECT query, mean_time, calls
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Verificar se indices estao sendo usados
EXPLAIN ANALYZE SELECT * FROM patients WHERE clinic_id = 'xxx';
```

**Solucoes:**
1. Adicionar indices faltantes
2. Corrigir queries N+1 com eager loading
3. Implementar cache para queries frequentes
4. Otimizar queries com JOINs desnecessarios

#### 8.1.3 Memory Leak

**Sintomas:**
- Memoria cresce continuamente
- OOM killer mata processo
- Performance degrada com o tempo

**Diagnostico:**
```python
# Habilitar profiler
profiler = get_memory_profiler()
profiler.start()

# Apos algumas horas
leaks = profiler.detect_leaks(threshold_mb=10.0)
print(leaks)
```

**Solucoes:**
1. Identificar arquivos com maior crescimento
2. Verificar closures que capturam referencias
3. Limpar caches periodicamente
4. Verificar listeners de eventos nao removidos

#### 8.1.4 Connection Pool Exhaustion

**Sintomas:**
- Requests falham com "connection pool exhausted"
- Timeout ao obter conexao
- Latencia crescente

**Diagnostico:**
```python
health = await check_pool_health()
print(f"Utilization: {health['utilization_percent']}%")
print(f"Checked out: {health['checked_out']}")
```

**Solucoes:**
1. Aumentar pool_size se recursos permitirem
2. Verificar conexoes nao fechadas (missing `async with`)
3. Reduzir tempo de transacoes
4. Implementar connection timeout menor

### 8.2 Scripts de Diagnostico

```python
# scripts/diagnose_performance.py

import asyncio
from datetime import datetime

async def full_diagnostic():
    """Executa diagnostico completo de performance."""

    results = {
        "timestamp": datetime.now().isoformat(),
        "issues": [],
        "recommendations": []
    }

    # 1. Database
    pool_health = await check_pool_health()
    if pool_health["utilization_percent"] > 80:
        results["issues"].append({
            "component": "database",
            "severity": "warning",
            "message": f"High pool utilization: {pool_health['utilization_percent']}%"
        })
        results["recommendations"].append(
            "Consider increasing pool_size or optimizing queries"
        )

    # 2. Redis
    try:
        redis_info = await redis_client.info("memory")
        used_memory_mb = redis_info["used_memory"] / 1024 / 1024

        if used_memory_mb > 500:
            results["issues"].append({
                "component": "redis",
                "severity": "warning",
                "message": f"High Redis memory: {used_memory_mb:.0f}MB"
            })
    except Exception as e:
        results["issues"].append({
            "component": "redis",
            "severity": "critical",
            "message": f"Redis unreachable: {e}"
        })

    # 3. Memory
    profiler = get_memory_profiler()
    if profiler.enabled:
        snapshot = profiler.take_snapshot()

        if snapshot["current_mb"] > 1024:  # > 1GB
            results["issues"].append({
                "component": "memory",
                "severity": "warning",
                "message": f"High memory usage: {snapshot['current_mb']:.0f}MB"
            })

        leaks = profiler.detect_leaks()
        if leaks:
            results["issues"].append({
                "component": "memory",
                "severity": "critical",
                "message": f"Potential memory leaks detected: {len(leaks)}"
            })

    # 4. Slow queries
    slow_queries = await get_slow_queries(threshold_ms=500)
    if slow_queries:
        results["issues"].append({
            "component": "database",
            "severity": "warning",
            "message": f"Found {len(slow_queries)} slow queries"
        })
        results["recommendations"].append(
            "Review slow queries and add missing indexes"
        )

    return results


if __name__ == "__main__":
    results = asyncio.run(full_diagnostic())

    print("\n=== Performance Diagnostic Report ===\n")
    print(f"Timestamp: {results['timestamp']}\n")

    if results["issues"]:
        print("Issues Found:")
        for issue in results["issues"]:
            print(f"  [{issue['severity'].upper()}] {issue['component']}: {issue['message']}")
    else:
        print("No issues found!")

    if results["recommendations"]:
        print("\nRecommendations:")
        for rec in results["recommendations"]:
            print(f"  - {rec}")
```

### 8.3 Checklist de Performance

```
Pre-Deploy Checklist:
---------------------
[ ] Todas as queries criticas tem indices
[ ] N+1 queries corrigidas
[ ] Cache configurado para endpoints frequentes
[ ] Connection pool dimensionado corretamente
[ ] Rate limiting configurado
[ ] Memory profiler habilitado
[ ] Health checks funcionando
[ ] Logs de performance configurados

Post-Deploy Monitoring:
-----------------------
[ ] Startup time < 20s
[ ] P95 latency < 500ms
[ ] Error rate < 1%
[ ] Memory usage estavel
[ ] Connection pool < 80%
[ ] Cache hit rate > 80%
[ ] No memory leaks detectados
```

### 8.4 Comandos Uteis

```bash
# Verificar logs de startup
grep -E "completed in|failed|timeout" /var/log/hormonia/app.log

# Monitorar memoria em tempo real
watch -n 5 'curl -s localhost:8000/health/detailed | jq .checks.memory'

# Verificar conexoes do database
psql -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

# Verificar cache Redis
redis-cli INFO memory | grep used_memory_human

# Verificar slow queries
psql -c "SELECT query, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 5;"

# Teste de carga rapido
hey -n 1000 -c 50 http://localhost:8000/api/v2/patients
```

---

## Apendice: Referencias Rapidas

### Configuracoes Recomendadas

| Parametro | Valor | Descricao |
|-----------|-------|-----------|
| DB Pool Size | 10 | Conexoes por worker |
| DB Max Overflow | 10 | Conexoes extras |
| Redis Max Connections | 50 | Pool de conexoes Redis |
| Cache TTL (default) | 120s | Time-to-live padrao |
| Rate Limit (read) | 100/min | Limite para leitura |
| Rate Limit (write) | 30/min | Limite para escrita |
| Startup Timeout | 30s | Timeout de inicializacao |
| Query Timeout | 30s | Timeout de queries |

### Metricas Target

| Metrica | Target | Critico |
|---------|--------|---------|
| Startup Time | < 20s | > 45s |
| API P95 Latency | < 300ms | > 1000ms |
| Error Rate | < 0.1% | > 1% |
| Memory Usage | < 70% | > 90% |
| Pool Utilization | < 70% | > 95% |
| Cache Hit Rate | > 80% | < 50% |

---

**Documento consolidado em**: Dezembro 2025
**Proxima revisao**: Janeiro 2026
