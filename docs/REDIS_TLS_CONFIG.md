# Configuração Redis com TLS/SSL

## Resumo das Correções (Python 3.13 + redis-py 5.x)

### Problema Resolvido
**Erro**: `AbstractConnection.__init__() got an unexpected keyword argument 'ssl_cert_reqs'`

**Causa**: redis-py 5.x com Python 3.13 não aceita mais `ssl_cert_reqs` e `ssl_check_hostname` como kwargs diretos. A API correta usa `ssl.SSLContext`.

### Solução Implementada

#### 1. Atualização de Dependências
```txt
redis>=5.1.1,<6.0.0  # Updated for Python 3.13 compatibility
```

#### 2. RedisManager com SSLContext ([app/core/redis_manager.py](cci:7://file:///c:/Meu%20Projetos/clinica-oncologica-v02/backend-hormonia/app/core/redis_manager.py:0:0-0:0))

**Padrão Correto**:
```python
import ssl

# Create SSL context
ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

# Configure based on REDIS_SSL_CERT_REQS
if ssl_cert_reqs == 'none':
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
elif ssl_cert_reqs == 'optional':
    ssl_context.verify_mode = ssl.CERT_OPTIONAL
else:  # 'required' (default)
    ssl_context.check_hostname = True
    ssl_context.verify_mode = ssl.CERT_REQUIRED

# Pass SSLContext to connection pool
connection_kwargs['ssl'] = ssl_context
pool = redis.ConnectionPool.from_url(url, **connection_kwargs)
```

**Padrão Incorreto (removido)**:
```python
# ❌ NÃO FAZER - incompatível com redis-py 5.x
connection_kwargs['ssl_cert_reqs'] = ssl.CERT_NONE
connection_kwargs['ssl_check_hostname'] = False
```

#### 3. Arquivos Corrigidos

| Arquivo | Correção |
|---------|----------|
| [app/core/redis_manager.py](cci:7://file:///c:/Meu%20Projetos/clinica-oncologica-v02/backend-hormonia/app/core/redis_manager.py:0:0-0:0) | SSLContext em `_create_async_client()` e `_create_sync_client()` |
| [app/api/v1/railway_health.py](cci:7://file:///c:/Meu%20Projetos/clinica-oncologica-v02/backend-hormonia/app/api/v1/railway_health.py:0:0-0:0) | Migrado para RedisManager unificado |
| [app/services/token_rotation_service.py](cci:7://file:///c:/Meu%20Projetos/clinica-oncologica-v02/backend-hormonia/app/services/token_rotation_service.py:0:0-0:0) | Corrigido uso de `redis_manager.get_sync_client()` |

## Variáveis de Ambiente

### Configuração Básica
```bash
# URL com esquema rediss:// para TLS
REDIS_URL=rediss://default:password@host:port/db

# Habilitar SSL (redundante se rediss://)
REDIS_SSL=true

# Política de certificados
REDIS_SSL_CERT_REQS=none|optional|required
```

### Railway/Produção
```bash
# Redis Cloud/Railway (TLS sem verificação de certificado)
REDIS_URL=rediss://default:***@redis-xxxxx.cloud.redislabs.com:xxxxx/0
REDIS_SSL=true
REDIS_SSL_CERT_REQS=none
```

### Desenvolvimento Local
```bash
# Redis local sem TLS
REDIS_URL=redis://localhost:6379/0
REDIS_SSL=false
```

## Política de Certificados

| Valor | verify_mode | check_hostname | Uso |
|-------|-------------|----------------|-----|
| `none` | `ssl.CERT_NONE` | `False` | Redis Cloud, Railway (certificados autoassinados) |
| `optional` | `ssl.CERT_OPTIONAL` | `True` | Ambientes intermediários |
| `required` | `ssl.CERT_REQUIRED` | `True` | Produção com CA válida (padrão) |

## Cliente Unificado

### Uso Recomendado
Sempre usar [RedisManager](cci:2://file:///c:/Meu%20Projetos/clinica-oncologica-v02/backend-hormonia/app/core/redis_manager.py:23:0-260:45) ao invés de conexões diretas:

```python
from app.core.redis_manager import get_redis_manager

# Async
redis_manager = get_redis_manager()
client = await redis_manager.get_async_client()
await client.set('key', 'value')

# Sync
redis_manager = get_redis_manager()
client = redis_manager.get_sync_client()
client.set('key', 'value')
```

### Módulos Migrados
- ✅ [app/core/redis_manager.py](cci:7://file:///c:/Meu%20Projetos/clinica-oncologica-v02/backend-hormonia/app/core/redis_manager.py:0:0-0:0) (SSLContext)
- ✅ [app/api/v1/railway_health.py](cci:7://file:///c:/Meu%20Projetos/clinica-oncologica-v02/backend-hormonia/app/api/v1/railway_health.py:0:0-0:0) (RedisManager)
- ✅ [app/services/token_rotation_service.py](cci:7://file:///c:/Meu%20Projetos/clinica-oncologica-v02/backend-hormonia/app/services/token_rotation_service.py:0:0-0:0) (get_sync_client)

### Pendentes de Migração
- ⏳ [app/utils/caching.py](cci:7://file:///c:/Meu%20Projetos/clinica-oncologica-v02/backend-hormonia/app/utils/caching.py:0:0-0:0)
- ⏳ [app/utils/rate_limiting.py](cci:7://file:///c:/Meu%20Projetos/clinica-oncologica-v02/backend-hormonia/app/utils/rate_limiting.py:0:0-0:0)
- ⏳ [app/services/ai_redis_cache.py](cci:7://file:///c:/Meu%20Projetos/clinica-oncologica-v02/backend-hormonia/app/services/ai_redis_cache.py:0:0-0:0)
- ⏳ [app/services/conversation_memory.py](cci:7://file:///c:/Meu%20Projetos/clinica-oncologica-v02/backend-hormonia/app/services/conversation_memory.py:0:0-0:0)

## Celery (broker/result backend)

### Configuração
```python
# app/config.py
CELERY_BROKER_URL = REDIS_URL  # rediss:// automaticamente
CELERY_RESULT_BACKEND = REDIS_URL
```

**Nota**: Com `rediss://`, não é necessário `broker_use_ssl` explícito. O Celery detecta automaticamente.

## Monitoramento

O [MonitoringManager](cci:2://file:///c:/Meu%20Projetos/clinica-oncologica-v02/backend-hormonia/app/monitoring/manager.py:28:0-403:49) usa `redis.asyncio.from_url()` com URL de `settings.REDIS_URL`. Se o URL tiver `rediss://`, o TLS é habilitado automaticamente.

**Fallback gracioso**: Se Redis falhar, o monitoramento continua sem Redis (features limitadas).

## Testes de Validação

### Conectividade
```bash
# Async
client = await redis_manager.get_async_client()
await client.ping()

# Sync
client = redis_manager.get_sync_client()
client.ping()
```

### Operações Básicas
```python
# SET/GET
await client.set('test', 'value', ex=60)
value = await client.get('test')

# Pipeline
async with redis_transaction() as pipe:
    pipe.set('k1', 'v1')
    pipe.incr('counter')
    results = await pipe.execute()
```

### Health Check
```bash
curl http://localhost:8000/api/v1/railway/health
```

## Troubleshooting

### Erro: `ssl_cert_reqs` não reconhecido
**Solução**: Atualizar para redis-py >=5.1.1 e usar SSLContext

### Erro: Timeout de conexão
**Solução**:
- Verificar `REDIS_URL` (esquema `rediss://`)
- Aumentar `socket_timeout` em [RedisManager](cci:2://file:///c:/Meu%20Projetos/clinica-oncologica-v02/backend-hormonia/app/core/redis_manager.py:23:0-260:45)
- Verificar firewall/network

### Erro: Certificado inválido
**Solução**: Setar `REDIS_SSL_CERT_REQS=none` (Railway/Redis Cloud)

## Referências

- [redis-py 5.x documentation](https://redis-py.readthedocs.io/)
- [Python ssl module](https://docs.python.org/3/library/ssl.html)
- [Railway Redis Setup](https://docs.railway.app/databases/redis)
