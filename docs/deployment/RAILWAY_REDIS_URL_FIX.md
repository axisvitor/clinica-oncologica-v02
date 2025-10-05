# 🔧 Railway Redis URL Configuration Fix

## ❌ Problema Atual

As variáveis de ambiente do Railway contêm o parâmetro `?ssl_cert_reqs=none` que é **incompatível com redis-py 6.0.0**:

```bash
# ❌ ERRADO - Causa erro
REDIS_URL="redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149?ssl_cert_reqs=none"
CELERY_BROKER_URL="redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0?ssl_cert_reqs=none"
CELERY_RESULT_BACKEND="redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0?ssl_cert_reqs=none"
```

**Erro resultante:**
```
ERROR - Failed to create async Redis client:
AbstractConnection.__init__() got an unexpected keyword argument 'ssl_cert_reqs'
```

## ✅ Solução: Variáveis Corretas para Railway

### 1. REDIS_URL (SEM parâmetros)
```bash
REDIS_URL=redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149
```

### 2. CELERY_BROKER_URL (SEM parâmetros)
```bash
CELERY_BROKER_URL=redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0
```

### 3. CELERY_RESULT_BACKEND (SEM parâmetros)
```bash
CELERY_RESULT_BACKEND=redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0
```

## 📋 Como Atualizar no Railway

### Método 1: Via Dashboard (Recomendado)
1. Acesse: https://railway.app/project/[seu-project-id]/service/[seu-service-id]
2. Vá em **Variables** tab
3. Edite cada variável removendo `?ssl_cert_reqs=none`:
   - `REDIS_URL`
   - `CELERY_BROKER_URL`
   - `CELERY_RESULT_BACKEND`
4. Clique em **Deploy** para aplicar as mudanças

### Método 2: Via Railway CLI
```bash
# Atualizar REDIS_URL
railway variables set REDIS_URL="redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149"

# Atualizar CELERY_BROKER_URL
railway variables set CELERY_BROKER_URL="redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0"

# Atualizar CELERY_RESULT_BACKEND
railway variables set CELERY_RESULT_BACKEND="redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0"

# Fazer redeploy
railway up
```

## 🔑 Regras Importantes - redis-py 6.0.0

### ✅ O QUE FUNCIONA:
1. **Controle de SSL via scheme da URL:**
   - `redis://` → Conexão SEM SSL
   - `rediss://` → Conexão COM SSL

2. **Especificar database via path:**
   - `redis://host:port/0` → Database 0
   - `redis://host:port/1` → Database 1

3. **Autenticação na URL:**
   - `redis://default:password@host:port`
   - `redis://:password@host:port`

### ❌ O QUE NÃO FUNCIONA:
1. **Parâmetros SSL como query string:**
   - ❌ `?ssl_cert_reqs=none`
   - ❌ `?ssl_check_hostname=false`
   - ❌ `?ssl=true`

2. **Passar ssl_context como kwarg:**
   - ❌ `ConnectionPool.from_url(url, ssl_context=ctx)`

## 🎯 Formato Correto das URLs

### Para Redis Cloud (porta 14149 - SEM SSL):
```bash
# URL base (sem database específico)
redis://default:PASSWORD@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149

# Com database específico (Celery usa DB 0)
redis://default:PASSWORD@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0
```

### Se fosse COM SSL (porta 6379 típica):
```bash
# Usar rediss:// (com dois 's')
rediss://default:PASSWORD@host:6379
```

## ✅ Variáveis Completas Corrigidas

```bash
# Redis Configuration
ENABLE_REDIS=true
REDIS_URL=redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149
REDIS_PASSWORD=6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR
REDIS_HOST=redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com
REDIS_PORT=14149
REDIS_SSL=false
REDIS_SSL_CERT_REQS=none
REDIS_MAX_CONNECTIONS=25
REDIS_SOCKET_TIMEOUT=10.0
REDIS_SOCKET_CONNECT_TIMEOUT=5.0
REDIS_RETRY_ON_TIMEOUT=true
REDIS_HEALTH_CHECK_INTERVAL=30
REDIS_ENABLE_DB_ISOLATION=true
REDIS_CACHE_DB=1
REDIS_BROKER_DB=0
REDIS_SESSION_DB=2
REDIS_RATE_LIMIT_DB=3

# Celery Configuration
CELERY_BROKER_URL=redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0
CELERY_RESULT_BACKEND=redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000
CELERY_WORKER_TIME_LIMIT=300
CELERY_WORKER_SOFT_TIME_LIMIT=240
CELERY_QUEUES=celery,flows,quiz,maintenance,monitoring
```

## 🧪 Como Verificar

Após atualizar as variáveis, os logs devem mostrar:

```bash
✅ SUCESSO:
2025-10-05 03:08:32 - app.core.redis_manager - INFO - Redis async: Using non-SSL connection
2025-10-05 03:08:32 - app.monitoring.manager - INFO - Monitoring system initialized successfully

❌ ERRO (se ainda tiver problema):
ERROR - Failed to create async Redis client: AbstractConnection.__init__() got an unexpected keyword argument 'ssl_cert_reqs'
```

## 📚 Referências

- [redis-py 6.0.0 Release Notes](https://github.com/redis/redis-py/releases/tag/v6.0.0)
- [Redis URL Scheme Documentation](https://redis-py.readthedocs.io/en/stable/connections.html#redis.Redis.from_url)
- Redis Cloud: Porta 14149 NÃO usa SSL/TLS

---

**⚠️ IMPORTANTE:**
- Não adicione parâmetros de query string nas URLs do Redis
- Controle SSL APENAS pelo scheme (`redis://` vs `rediss://`)
- Redis Cloud porta 14149 = SEM SSL
