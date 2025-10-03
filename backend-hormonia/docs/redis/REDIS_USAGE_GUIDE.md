# Redis Cloud Usage Guide - Sistema Hormonia

## 📋 Visão Geral

O Redis Cloud é usado como **camada de cache e coordenação** para aliviar pressão do Postgres (Supabase), **nunca como fonte de verdade**. Todos os dados críticos (pacientes, sessões/respostas de quiz, PHI) permanecem no Supabase com RLS.

---

## 🎯 Casos de Uso Atuais

### 1. **JWT Cache e Blacklist** ✅
**Arquivo:** `app/services/jwt_cache_service.py`

**Propósito:**
- Cacheia validações de tokens do Supabase Auth
- Mantém blacklist de logout com TTL derivado do `exp`
- Evita round-trips ao Supabase para cada validação

**Padrões de chave:**
```
jwt:{token_hash}         # Token validation cache
jwt:blacklist:{token_id} # Logout blacklist
```

**TTLs:**
- Cache de validação: Baseado no exp do token
- Blacklist: Até expiração do token

---

### 2. **Humanização de Perguntas** ✅
**Arquivo:** `app/services/question_humanizer.py`

**Propósito:**
- Anti-repetição: histórico recente de perguntas por paciente
- Telemetria diária de humanizações

**Padrões de chave:**
```
question_history:{patient_id}  # Últimas perguntas (7 dias)
question_humanizer:telemetry:daily:{date}  # Métricas diárias (30 dias)
```

**TTLs:**
- Histórico: 7 dias (`setex`)
- Telemetria: 30 dias (`expire`)

---

### 3. **Cache de Templates** ✅
**Arquivo:** `app/services/template_cache.py`

**Classe:** `TemplateRedisCache`

**Propósito:**
- Cacheia templates de fluxo e mensagens
- Hot-reload via Pub/Sub
- Evita consultas repetitivas no Postgres

**Padrões de chave:**
```
versioned_template:{version}:{template_name}  # Template cache
template:update  # Pub/Sub channel para invalidação
```

**TTLs:**
- ~15 minutos (padrão)
- Invalidação via Pub/Sub

---

### 4. **Cache Unificado de Dados** ✅
**Arquivo:** `app/utils/unified_cache.py`

**Propósito:**
- Camada de cache genérica (pacientes, templates, analytics)
- Fallback local quando Redis indisponível
- Métricas de hit/miss

**Padrões de chave:**
```
cache:{namespace}:{key}  # Generic cache
patient:{patient_id}     # Patient data cache
```

**TTLs:** Variáveis conforme namespace

---

### 5. **Rate Limiting Distribuído** ✅
**Arquivo:** `app/utils/rate_limiting.py`

**Propósito:**
- Janela deslizante para controle de taxa
- Fallback in-memory quando Redis indisponível
- Coordenação entre múltiplas instâncias

**Padrões de chave:**
```
rate_limit:{user_id}:{endpoint}  # Rate limit tracking
```

**TTLs:** Baseado na janela configurada (ex: 60s, 3600s)

---

### 6. **Métricas e Séries Temporais** ✅
**Arquivo:** `app/services/metrics_redis_storage.py`

**Propósito:**
- Armazena métricas raw/hourly/daily
- Políticas de retenção automáticas
- Mantém telemetria fora do Postgres

**Padrões de chave:**
```
hormonia:metrics:{metric_name}:raw:{timestamp}    # Raw metrics
hormonia:metrics:{metric_name}:hourly:{hour}      # Aggregated hourly
hormonia:metrics:{metric_name}:daily:{date}       # Aggregated daily
```

**TTLs:**
- Raw: 24 horas
- Hourly: 7 dias
- Daily: 30 dias

---

### 7. **Caches de IA** ✅
**Arquivos:**
- `app/services/ai_cache_service.py`
- `app/services/ai_redis_cache.py`

**Propósito:**
- Cacheia respostas de IA para reduzir chamadas externas
- Economia de custos de API

**Padrões de chave:**
```
ai:response:{hash}     # AI response cache
ai:embedding:{hash}    # Embedding cache
```

**TTLs:** Variáveis (geralmente 1h - 24h)

---

### 8. **Celery Broker/Backend** ✅
**Arquivo:** `app/config.py`

**Configuração:**
```python
CELERY_BROKER_URL = REDIS_URL + '/0'
CELERY_RESULT_BACKEND = REDIS_URL + '/1'
```

**Propósito:**
- Isolamento do enfileiramento de tarefas
- Persistência de resultados de tasks

---

## 🔧 Cliente Redis Padronizado

### ✅ **USO OFICIAL: `redis_unified.py`**

**Arquivo:** `app/core/redis_unified.py`

**Status:** ✅ Implementado e pronto para uso

**Benefícios:**
- ✅ **Ponto único de entrada**
- ✅ Auto-detecção async/sync
- ✅ **Isolamento de DB** (cache vs broker)
- ✅ **Métricas integradas**
- ✅ Deprecation warnings
- ✅ Connection pooling automático

### **Uso Recomendado**

```python
# 1. Auto-detect (RECOMENDADO - uso geral)
from app.core.redis_unified import get_redis_client

redis = get_redis_client()
redis.set('key', 'value', ex=3600)

# 2. Cache específico (DB 1)
from app.core.redis_unified import get_cache_redis

cache = get_cache_redis()
cache.set('cache:user:123', data, ex=3600)

# 3. Async puro
from app.core.redis_unified import get_async_redis

redis = await get_async_redis()
await redis.set('key', 'value', ex=3600)

# 4. Sync puro
from app.core.redis_unified import get_sync_redis

redis = get_sync_redis()
redis.set('key', 'value', ex=3600)
```

### **Clientes Legados (REMOVIDOS)**

| Arquivo | Status | Data Remoção |
|---------|--------|--------------|
| `redis_client_factory.py` | ✅ REMOVIDO | 2025-10-02 |
| `redis_simple.py` | ✅ REMOVIDO | 2025-10-02 |
| `redis_client.py` | ✅ REMOVIDO | 2025-10-02 |
| `async_redis_client.py` | ✅ REMOVIDO | 2025-10-02 |
| `redis_cloud_client.py` | ✅ REMOVIDO | 2025-10-02 |

**Nota:** Todos os clientes legados foram removidos. Use exclusivamente `redis_unified` para novas implementações.

---

## 📏 Boas Práticas Atuais

### ✅ **O que está sendo feito corretamente**

1. **Dados efêmeros apenas**
   - Cache, coordenação, histórico auxiliar
   - Nunca PHI/PII em texto puro

2. **TTLs conservadores**
   - JWT: baseado em exp
   - Histórico perguntas: 7 dias
   - Templates: 15 min
   - Métricas: 24h (raw), 7d (hourly), 30d (daily)

3. **Namespaces de chave**
   - `jwt:*`, `cache:*`, `hormonia:metrics:*`
   - Facilita gestão e limpeza

4. **Fallbacks graciosos**
   - Template cache → DB direto
   - Unified cache → local storage
   - Rate limiting → in-memory

5. **Não cachear dados clínicos sensíveis**
   - quiz_sessions/quiz_responses ficam no Postgres
   - Apenas metadados/telemetria no Redis

---

## ⚠️ O que EVITAR

### ❌ **Não fazer**

1. **Não armazenar sessões/respostas de quiz**
   - ✅ Correto: Postgres com RLS
   - ❌ Errado: Redis sem persistência garantida

2. **Não criar caches desnecessários**
   - Os caches atuais cobrem hot paths
   - Medir antes de adicionar novos

3. **Não cachear PII/PHI em texto puro**
   - Se absolutamente necessário: criptografar + TTL curto
   - Preferir evitar completamente

4. **Não usar múltiplas fábricas sem motivo**
   - Padronizar em `redis_manager.py`
   - Remover código duplicado

---

## 🔐 Configuração de Produção

### **Variáveis de Ambiente**

```bash
# Redis Cloud URL
REDIS_URL=redis://default:password@host:port

# SSL (Redis Cloud)
REDIS_SSL=true  # Força SSL mesmo com redis://

# Connection Pool
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=30.0

# Decode
REDIS_DECODE_RESPONSES=true
```

### **✅ Isolamento DB Implementado**

**Status:** ✅ Configurado e ativo

O sistema agora usa **DBs Redis separados** para evitar contenção:

```bash
# Configuração (app/config.py)
REDIS_CACHE_DB=1                    # Cache usa DB 1
REDIS_BROKER_DB=0                   # Celery broker usa DB 0
REDIS_ENABLE_DB_ISOLATION=true      # Ativa isolamento

# URLs automáticas
CELERY_BROKER_URL=redis://host:port/0      # Broker
CELERY_RESULT_BACKEND=redis://host:port/1  # Results
```

**Benefícios:**
- ✅ Separação lógica broker vs cache
- ✅ Evita contenção de memória
- ✅ Flush seletivo (FLUSHDB em DB específico)
- ✅ Monitoramento independente

---

## 📊 Observabilidade

### **✅ Métricas Globais Implementadas**

**Arquivo:** `app/services/redis_metrics.py`

**Status:** ✅ Pronto para uso

### **Uso - Tracking Automático**

```python
from app.services.redis_metrics import track_cache_metrics, async_track_cache_metrics

# Sync decorator
@track_cache_metrics('jwt')
def get_from_jwt_cache(token):
    # Retorna valor ou None
    return redis.get(f'jwt:{token}')

# Async decorator
@async_track_cache_metrics('template')
async def get_from_template_cache(name):
    # Retorna valor ou None
    return await redis.get(f'template:{name}')
```

### **Uso - Manual**

```python
from app.services.redis_metrics import (
    record_cache_hit,
    record_cache_miss,
    record_cache_error,
    get_cache_summary
)

# Registrar hit/miss
if value := redis.get('key'):
    record_cache_hit('my_cache')
else:
    record_cache_miss('my_cache')

# Ver métricas
summary = get_cache_summary()
# {
#   "summary": {
#     "total_hits": 1250,
#     "total_misses": 150,
#     "overall_hit_rate": 89.29,
#     "uptime_seconds": 3600
#   },
#   "caches": {
#     "jwt": {"hits": 800, "misses": 50, "hit_rate": 94.12},
#     "template": {"hits": 450, "misses": 100, "hit_rate": 81.82}
#   }
# }
```

### **Exportação Prometheus**

```python
from app.services.redis_metrics import get_metrics_collector

collector = get_metrics_collector()
metrics_text = collector.export_prometheus()

# Output:
# redis_cache_hits_total{cache="jwt"} 800
# redis_cache_misses_total{cache="jwt"} 50
# redis_cache_hit_rate_percent{cache="jwt"} 94.12
```

### **Outras Métricas Importantes**

1. **Memória Redis**
   - `redis-cli INFO memory`
   - Alertar em >80% uso

2. **TTL Médio**
   - `redis-cli --scan --pattern '*' | xargs redis-cli TTL`

3. **Comandos Lentos**
   - `SLOWLOG GET 10`

---

## ✅ Padronização Completa (IMPLEMENTADO)

**Status:** ✅ Concluído

### **Implementações**

1. **✅ Cliente Unificado**
   - `app/core/redis_unified.py` criado
   - Ponto único de entrada
   - Deprecation warnings automáticos

2. **✅ Isolamento de DB**
   - Broker (DB 0) vs Cache (DB 1)
   - Configurável via `REDIS_ENABLE_DB_ISOLATION`
   - Suporte em `redis_manager.py`

3. **✅ Métricas Globais**
   - `app/services/redis_metrics.py` criado
   - Decorators para tracking automático
   - Exportação Prometheus

### **Guia de Migração**

**Status:** ✅ Migração principal concluída (6 arquivos)

Para atualizar código legado:

```python
# ANTES (deprecated)
from app.core.redis_client_factory import get_redis_factory
factory = get_redis_factory()
redis = factory.get_sync_client()

# DEPOIS (recomendado)
from app.core.redis_unified import get_redis_client
redis = get_redis_client()
```

**Arquivos já migrados:**
- ✅ `app/dependencies.py`
- ✅ `app/core/startup.py`
- ✅ `app/services/metrics_redis_storage.py`
- ✅ `app/utils/unified_cache.py`
- ✅ `app/utils/cache.py`

**Detalhes:** Veja [REDIS_MIGRATION_SUMMARY.md](REDIS_MIGRATION_SUMMARY.md)

**Exemplos:** Execute `python -m app.core.redis_unified`

---

## 🔍 Checklist de Verificação

Ao adicionar novo uso de Redis:

- [ ] Dados são **efêmeros** (não fonte de verdade)?
- [ ] TTL configurado adequadamente?
- [ ] Namespace de chave definido?
- [ ] Fallback implementado?
- [ ] Não contém PII/PHI sensível?
- [ ] Métricas/logs adicionados?
- [ ] Documentado neste guia?

---

## 📚 Referências Rápidas

### **Comandos Úteis**

```bash
# Health check
redis-cli PING

# Verificar chaves por pattern
redis-cli --scan --pattern 'jwt:*' | head -10

# Verificar memória
redis-cli INFO memory

# Limpar namespace
redis-cli --scan --pattern 'cache:*' | xargs redis-cli DEL

# Monitorar em tempo real
redis-cli MONITOR
```

### **Conexão Manual**

```bash
redis-cli -h <host> -p <port> --tls --insecure
AUTH default <password>
```

---

## ✅ Status Atual

| Componente | Status | Observação |
|------------|--------|------------|
| JWT Cache | ✅ Produção | Funcionando corretamente |
| Question Humanizer | ✅ Produção | TTLs apropriados |
| Template Cache | ✅ Produção | Pub/Sub implementado |
| Unified Cache | ✅ Produção | Fallback local OK |
| Rate Limiting | ✅ Produção | Distribuído + fallback |
| Métricas | ✅ Produção | Políticas de retenção OK |
| AI Caches | ✅ Produção | Reduzindo custos de API |
| Celery | ✅ Produção | Isolado em DB separado |
| **Cliente Unificado** | ✅ **Implementado** | `redis_unified.py` |
| **DB Isolation** | ✅ **Implementado** | Cache (DB1) vs Broker (DB0) |
| **Métricas Globais** | ✅ **Implementado** | `redis_metrics.py` + Prometheus |

**Conclusão:** O uso do Redis está **otimizado e pronto para produção**. Todas as melhorias recomendadas foram implementadas.

---

## 🎉 Implementações Recentes

### **✅ Concluído (2025-10-02)**

1. **Cliente Redis Unificado**
   - ✅ `app/core/redis_unified.py` criado
   - ✅ Ponto único de entrada
   - ✅ Deprecation warnings automáticos
   - ✅ Auto-detecção async/sync

2. **Isolamento de DB**
   - ✅ Broker (DB 0) vs Cache (DB 1)
   - ✅ Configurável via variáveis de ambiente
   - ✅ Evita contenção de recursos

3. **Métricas Globais de Hit Rate**
   - ✅ `app/services/redis_metrics.py` criado
   - ✅ Decorators para tracking automático
   - ✅ Exportação Prometheus
   - ✅ API para coleta de métricas

---

## 🔄 Próximos Passos (Opcional)

1. **[BAIXA PRIORIDADE]** Migrar código legado para `redis_unified`
2. **[BAIXA PRIORIDADE]** Dashboard Grafana com métricas Redis
3. **[BAIXA PRIORIDADE]** Alertas automáticos (memória >80%, hit rate <70%)

---

**Última atualização:** 2025-10-02 (Padronização completa)
**Responsável:** Sistema Hormonia - Oncologia
