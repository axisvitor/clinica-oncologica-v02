# 🚂 Guia Completo de Deploy no Railway

> **Causa raiz dos erros**: Root Directory incorreto e variáveis de ambiente ausentes no Railway.

Este guia cobre o deploy completo dos 5 serviços do projeto no Railway.

---

## 📋 Arquitetura de Serviços

```
┌─────────────────────────────────────────────────────┐
│                  Railway Project                     │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │   Backend    │  │  Celery      │  │  Celery   │ │
│  │   (FastAPI)  │  │  Worker      │  │  Beat     │ │
│  │              │  │              │  │           │ │
│  └──────────────┘  └──────────────┘  └───────────┘ │
│         │                  │                │       │
│         └──────────────────┴────────────────┘       │
│                      │                              │
│         ┌────────────┴────────────┐                 │
│         │                         │                 │
│  ┌──────▼──────┐          ┌───────▼──────┐          │
│  │  Frontend   │          │     Quiz     │          │
│  │  (Vite+Nginx)│         │  (Next.js)   │          │
│  └─────────────┘          └──────────────┘          │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## 🎯 1) Backend API – `backend-hormonia/`

### Configuração Railway

| Campo | Valor |
|-------|-------|
| **Root Directory** | `backend-hormonia` |
| **Builder** | `DOCKERFILE` |
| **Dockerfile Path** | _(deixe em branco)_ |
| **Branch** | `main` ou `docs-refactor-py313` |
| **Healthcheck Path** | `/health` |
| **Healthcheck Timeout** | `120` |
| **Start Command** | _(deixe em branco - usa CMD do Dockerfile)_ |

### Variáveis de Ambiente

#### Básicas
```bash
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=info
PASSLIB_BUILTIN_BCRYPT=enabled
```

#### Banco de Dados & Cache
```bash
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db

# Redis Cloud (já configurado - copie exatamente como está)
REDIS_URL=redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149
REDIS_PASSWORD=6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR
REDIS_HOST=redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com
REDIS_PORT=14149
REDIS_SSL=false
REDIS_SSL_CERT_REQS=none
REDIS_MAX_CONNECTIONS=25
REDIS_SOCKET_TIMEOUT=10.0
REDIS_ENABLE_DB_ISOLATION=true
REDIS_CACHE_DB=1
REDIS_BROKER_DB=0

# Celery (usa mesmo Redis, DB 0 para broker)
CELERY_BROKER_URL=redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0
CELERY_RESULT_BACKEND=redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0
```

#### Segurança
```bash
SECRET_KEY=<generate-secure-key-min-32-chars>
JWT_SECRET_KEY=<generate-secure-key-min-32-chars>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

#### CORS & URLs dos outros serviços
```bash
ALLOWED_ORIGINS=["https://<frontend-domain>.up.railway.app","https://<quiz-domain>.up.railway.app","http://localhost:3000","http://localhost:5173"]
FRONTEND_URL=https://<frontend-domain>.up.railway.app
QUIZ_URL=https://<quiz-domain>.up.railway.app
```

#### WhatsApp (Evolution API)
```bash
ENABLE_EVOLUTION=true
EVOLUTION_API_URL=https://<evolution-api-domain>
EVOLUTION_API_KEY=<your-api-key>
EVOLUTION_INSTANCE_NAME=<instance-name>
EVOLUTION_WEBHOOK_SECRET=<webhook-secret>
EVOLUTION_WEBHOOK_URL=https://<backend-domain>.up.railway.app/webhooks/whatsapp/evolution/<instance-name>
```

### Validação

```bash
# Health check básico
curl https://<backend-domain>.up.railway.app/health
# Resposta: 200 OK

# API health check
curl https://<backend-domain>.up.railway.app/api/v1/health
# Resposta: 200 OK com JSON
```

---

## 🔄 2) Celery Worker – `backend-hormonia/`

### Configuração Railway

| Campo | Valor |
|-------|-------|
| **Root Directory** | `backend-hormonia` ⚠️ |
| **Builder** | `DOCKERFILE` |
| **Dockerfile Path** | `Dockerfile.worker` |
| **Start Command** | _(deixe em branco)_ |

> ⚠️ **IMPORTANTE**: Use `backend-hormonia` como Root Directory, NÃO `backend-hormonia/worker/`. O Dockerfile.worker precisa do contexto completo para os `COPY` funcionarem.

### Variáveis de Ambiente

**Todas as variáveis do Backend** + as seguintes opcionais:

```bash
# Worker Configuration
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000
CELERY_WORKER_TIME_LIMIT=300
CELERY_WORKER_SOFT_TIME_LIMIT=240
CELERY_QUEUES=celery,flows,quiz,maintenance,monitoring
```

---

## ⏰ 3) Celery Beat – `backend-hormonia/`

### Configuração Railway

| Campo | Valor |
|-------|-------|
| **Root Directory** | `backend-hormonia` ⚠️ |
| **Builder** | `DOCKERFILE` |
| **Dockerfile Path** | `Dockerfile.beat` |
| **Start Command** | _(deixe em branco)_ |

> ⚠️ **IMPORTANTE**: Use `backend-hormonia` como Root Directory, NÃO `backend-hormonia/beat/`.

### Variáveis de Ambiente

**Todas as variáveis do Backend** + as seguintes opcionais:

```bash
# Beat Configuration
CELERY_BEAT_SCHEDULER=celery.beat.PersistentScheduler
CELERY_BEAT_MAX_INTERVAL=300
```

---

## 🎨 4) Frontend – `frontend-hormonia/`

### Configuração Railway

| Campo | Valor |
|-------|-------|
| **Root Directory** | `frontend-hormonia` |
| **Builder** | `DOCKERFILE` |
| **Dockerfile Path** | _(deixe em branco)_ |
| **Healthcheck Path** | `/health` |
| **Healthcheck Timeout** | `120` |
| **Start Command** | _(deixe em branco - usa ENTRYPOINT do Dockerfile)_ |

### Variáveis de Ambiente OBRIGATÓRIAS

```bash
# ⚠️ OBRIGATÓRIO - Nginx precisa disso para funcionar
BACKEND_URL=https://<backend-domain>.up.railway.app
```

> **IMPORTANTE**:
> - NÃO inclua `/api` no final
> - O nginx.conf já roteia `/api/*` e `/ws` para o backend
> - Se não definir `BACKEND_URL`, o nginx tentará usar `http://backend:8000` que não existe em deploys separados

### Variáveis de Ambiente Opcionais

```bash
# Build-time variables (opcional - BACKEND_URL é suficiente)
VITE_API_URL=https://<backend-domain>.up.railway.app
VITE_API_BASE_URL=https://<backend-domain>.up.railway.app
VITE_WS_URL=wss://<backend-domain>.up.railway.app/ws
VITE_WS_BASE_URL=wss://<backend-domain>.up.railway.app/ws

# Supabase (públicas - seguro expor)
VITE_SUPABASE_URL=https://<seu-projeto>.supabase.co
VITE_SUPABASE_ANON_KEY=<anon-key-publico>
```

### Validação

```bash
# Health check
curl https://<frontend-domain>.up.railway.app/health
# Resposta: 200 OK

# Proxy para backend (do navegador)
https://<frontend-domain>.up.railway.app/api/v1/health
# Deve responder via proxy para o backend
```

### ❌ Erro Comum

**Erro**: `nginx: [emerg] host not found in upstream "backend"`

**Causa**: `BACKEND_URL` não está definido no Railway

**Solução**:
1. Vá em **Settings → Variables**
2. Adicione: `BACKEND_URL=https://<seu-backend>.up.railway.app`
3. Redeploy o serviço

---

## 📝 5) Quiz – `quiz-mensal-interface/`

### Configuração Railway

| Campo | Valor |
|-------|-------|
| **Root Directory** | `quiz-mensal-interface` |
| **Builder** | `DOCKERFILE` |
| **Dockerfile Path** | `Dockerfile` |
| **Healthcheck Path** | `/api/health` |
| **Healthcheck Timeout** | `300` |
| **Start Command** | _(deixe em branco - usa CMD do Dockerfile)_ |

### Variáveis de Ambiente

```bash
NODE_ENV=production
NEXT_PUBLIC_API_URL=https://<backend-domain>.up.railway.app
```

### Validação

```bash
# Health check
curl https://<quiz-domain>.up.railway.app/api/health
# Resposta: 200 OK

# Verificar campo 'dependencies.backend_api.status' deve ser 'healthy'
```

---

## 🚀 Auto Deploy (Recomendado)

### Setup no Railway

1. **Crie UM ÚNICO projeto** Railway
2. **Adicione os 5 serviços** no mesmo projeto:
   - Backend (FastAPI)
   - Worker (Celery)
   - Beat (Celery Beat)
   - Frontend (Vite + Nginx)
   - Quiz (Next.js)

3. **Configure TODOS para o mesmo branch** (ex: `main`)
4. **Ative "Auto Deploy on Git Push"** em todos os serviços

**Resultado**: Um único `git push` dispara build e deploy de todos os serviços automaticamente.

---

## ✅ Checklist Final

### Backend
- [ ] Root Directory: `backend-hormonia`
- [ ] Builder: DOCKERFILE
- [ ] Health: `/health`
- [ ] Vars: DATABASE_URL, REDIS_URL, EVOLUTION_*, CORS, SECRET_KEY
- [ ] `GET /health` → 200 ✓

### Celery Worker
- [ ] Root Directory: `backend-hormonia` (não `/worker/`)
- [ ] Dockerfile Path: `Dockerfile.worker`
- [ ] Vars: mesmas do Backend + opcionais Celery
- [ ] Logs mostram worker iniciado ✓

### Celery Beat
- [ ] Root Directory: `backend-hormonia` (não `/beat/`)
- [ ] Dockerfile Path: `Dockerfile.beat`
- [ ] Vars: mesmas do Backend + opcionais Beat
- [ ] Logs mostram scheduler iniciado ✓

### Frontend
- [ ] Root Directory: `frontend-hormonia`
- [ ] Builder: DOCKERFILE
- [ ] Health: `/health`
- [ ] **Var OBRIGATÓRIA**: `BACKEND_URL=https://<backend>`
- [ ] `GET /health` → 200 ✓
- [ ] Proxy `GET /api/v1/health` funciona ✓

### Quiz
- [ ] Root Directory: `quiz-mensal-interface`
- [ ] Builder: DOCKERFILE
- [ ] Health: `/api/health`
- [ ] Var: `NEXT_PUBLIC_API_URL=https://<backend>`
- [ ] `GET /api/health` → 200 ✓
- [ ] Campo `dependencies.backend_api.status: "healthy"` ✓

### Auto Deploy
- [ ] Todos os 5 serviços no MESMO projeto Railway
- [ ] Todos apontando para o MESMO branch
- [ ] Auto Deploy ativado em todos
- [ ] `git push` → builds disparados automaticamente ✓

---

## 🔧 Troubleshooting

### Backend não inicia

**Erro**: `ModuleNotFoundError` ou import errors

**Solução**:
- Verifique se Root Directory está em `backend-hormonia`
- Confirme que `requirements.txt` está completo
- Check logs: `alembic upgrade head` deve rodar sem erros

### Worker/Beat não conecta ao Redis

**Erro**: `redis.exceptions.ConnectionError`

**Solução**:
- Verifique `REDIS_URL` está correto (formato: `rediss://` para SSL)
- Teste conexão: `redis-cli -u $REDIS_URL ping`

### Frontend: Nginx "host not found"

**Erro**: `nginx: [emerg] host not found in upstream "backend"`

**Solução**:
- Defina `BACKEND_URL=https://<backend-domain>.up.railway.app`
- Redeploy o frontend
- Verifique logs: deve mostrar "Configured BACKEND_URL to https://..."

### Quiz não conecta ao backend

**Erro**: Health check mostra `backend_api.status: "unhealthy"`

**Solução**:
- Verifique `NEXT_PUBLIC_API_URL` está correto
- Teste: `curl $NEXT_PUBLIC_API_URL/health` deve retornar 200
- Verifique CORS no backend inclui domínio do quiz

### CORS errors no navegador

**Erro**: `Access-Control-Allow-Origin` bloqueado

**Solução**:
- No backend, adicione URLs do frontend e quiz em `ALLOWED_ORIGINS`
- Formato: `["https://frontend.railway.app","https://quiz.railway.app"]`
- Redeploy o backend

---

## 📊 Ordem de Deploy Recomendada

1. **Backend** → Aguarde health check OK
2. **Worker** → Verifique logs (deve conectar ao Redis e DB)
3. **Beat** → Verifique logs (scheduler deve iniciar)
4. **Frontend** → Configure `BACKEND_URL` → Deploy
5. **Quiz** → Configure `NEXT_PUBLIC_API_URL` → Deploy

---

## 🔒 Segurança

- [ ] Todas as secrets em variáveis de ambiente (não no código)
- [ ] `SECRET_KEY` e `JWT_SECRET_KEY` são únicos e >= 32 chars
- [ ] CORS configurado apenas com domínios necessários
- [ ] HTTPS ativo em todos os serviços (Railway SSL automático)
- [ ] `.env` no `.gitignore`
- [ ] Logs não expõem dados sensíveis

---

## 📝 Notas Importantes

1. **Root Directory é crítico**: Deve apontar para a pasta onde está o Dockerfile
2. **Celery Worker/Beat**: Usar `backend-hormonia` como root, não subpastas
3. **Frontend BACKEND_URL**: Obrigatório, sem `/api` no final
4. **Auto Deploy**: Todos no mesmo branch para deploy sincronizado
5. **Health checks**: Validar ANTES de marcar serviço como pronto

---

**Última atualização**: 2025-10-03
**Branch testado**: `docs-refactor-py313`
**Railway Region**: Recomendado `us-east` (latência BR ~100ms)
