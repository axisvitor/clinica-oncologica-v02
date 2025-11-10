# Railway Deploy Guide - Clínica Oncológica v2

## Estrutura de Serviços Railway

O projeto está organizado em **5 serviços** independentes no Railway:

### 1. Backend API (FastAPI)
- **Pasta**: `backend-hormonia/`
- **Dockerfile**: `Dockerfile`
- **Config**: `railway.json`
- **Healthcheck**: `/health`
- **Porta**: 8000 (Railway injeta via `$PORT`)
- **Comando**: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`

### 2. Celery Worker
- **Pasta**: `backend-hormonia/worker/`
- **Dockerfile**: `../Dockerfile.worker`
- **Config**: `railway.json`
- **Filas**: `celery,flows,quiz,maintenance,monitoring`
- **Concorrência**: 4 workers (configurável via `CELERY_WORKER_CONCURRENCY`)

### 3. Celery Beat (Scheduler)
- **Pasta**: `backend-hormonia/beat/`
- **Dockerfile**: `../Dockerfile.beat`
- **Config**: `railway.json`
- **Função**: Agendamento de tarefas periódicas

### 4. Frontend (React + Vite)
- **Pasta**: `frontend-hormonia/`
- **Builder**: NIXPACKS (não usa Dockerfile em produção)
- **Config**: `railway.json`
- **Build**: `npm run build:railway`
- **Start**: `npm run preview`
- **Healthcheck**: `/`
- **Porta**: Dinâmica (Railway injeta via `$PORT`)

### 5. Quiz Interface (Next.js 14)
- **Pasta**: `quiz-mensal-interface/`
- **Dockerfile**: `Dockerfile`
- **Config**: `railway.json`
- **Healthcheck**: `/api/health`
- **Porta**: 3000 (Railway injeta via `$PORT`)
- **Comando**: `pnpm exec next start -p ${PORT:-3000} -H 0.0.0.0`

---

## Variáveis de Ambiente Necessárias

### Backend API, Worker e Beat (compartilham as mesmas variáveis)

```bash
# Core
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<gerar-com-secrets.token_urlsafe(64)>
JWT_SECRET_KEY=<gerar-com-secrets.token_urlsafe(64)>
CSRF_SECRET_KEY=<gerar-com-secrets.token_urlsafe(32)>

# Database (AWS RDS PostgreSQL)
DATABASE_URL=postgresql+psycopg://USER:PASS@HOST:5432/DB?sslmode=require
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=40

# Redis
REDIS_URL=redis://default:PASSWORD@HOST:PORT
REDIS_SSL=false
REDIS_MAX_CONNECTIONS=25

# Celery
CELERY_BROKER_URL=redis://default:PASSWORD@HOST:PORT/0
CELERY_RESULT_BACKEND=redis://default:PASSWORD@HOST:PORT/0
CELERY_QUEUES=celery,flows,quiz,maintenance,monitoring

# CORS
FRONTEND_URL=https://frontend-production.up.railway.app
QUIZ_URL=https://quiz-production.up.railway.app
ALLOWED_ORIGINS=["https://frontend-production.up.railway.app","https://quiz-production.up.railway.app"]

# Evolution API (WhatsApp)
ENABLE_EVOLUTION=true
EVOLUTION_API_URL=https://evolution.domain.com
EVOLUTION_INSTANCE_NAME=clinica_oncologica
EVOLUTION_API_KEY=<sua-api-key>
EVOLUTION_WEBHOOK_SECRET=<gerar-segredo>
EVOLUTION_WEBHOOK_URL=https://backend-production.up.railway.app/api/v2/webhooks/whatsapp

# WhatsApp
WHATSAPP_MAX_RETRIES=3
WHATSAPP_RETRY_DELAY_SECONDS=60
CLINIC_NAME=Neoplasias Litoral
CLINIC_SUPPORT_PHONE=+55 XX XXXXX-XXXX

# AI (Google Gemini)
GEMINI_API_KEY=<sua-gemini-key>
GEMINI_MODEL=gemini-2.0-flash-exp
AI_HUMANIZATION_ENABLED=true
AI_HUMANIZATION_SAFETY_MODE=true

# Firebase Admin SDK
FIREBASE_ADMIN_PROJECT_ID=<project-id>
FIREBASE_ADMIN_CLIENT_EMAIL=<service-account-email>
FIREBASE_ADMIN_PRIVATE_KEY=<private-key-com-\n>

# Monthly Quiz
MONTHLY_QUIZ_VIA_LINK=true
MONTHLY_QUIZ_BASE_URL=https://quiz-production.up.railway.app/quiz/monthly
MONTHLY_QUIZ_TOKEN_SECRET=<gerar-segredo>
MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS=72

# Logging
LOG_LEVEL=INFO
ENABLE_REQUEST_LOGGING=true

# API
API_VERSION=v2
```

### Frontend (React + Vite)

```bash
# Environment
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false

# Backend API
VITE_API_BASE_URL=https://backend-production.up.railway.app
VITE_API_URL=https://backend-production.up.railway.app/api/v2
VITE_WS_BASE_URL=wss://backend-production.up.railway.app/ws
VITE_WS_URL=wss://backend-production.up.railway.app/ws

# Firebase Client SDK
VITE_FIREBASE_API_KEY=<firebase-web-api-key>
VITE_FIREBASE_AUTH_DOMAIN=<project-id>.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=<project-id>
VITE_FIREBASE_STORAGE_BUCKET=<project-id>.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=<sender-id>
VITE_FIREBASE_APP_ID=<app-id>

# Features
VITE_ENABLE_WHATSAPP_INTEGRATION=true
VITE_ENABLE_AI_CHAT=true
VITE_AI_CHAT_ENABLED=true
```

### Quiz Interface (Next.js)

```bash
# Environment
NODE_ENV=production
NEXT_PUBLIC_ENVIRONMENT=production
NEXT_PUBLIC_DEBUG_MODE=false
NEXT_TELEMETRY_DISABLED=1

# Backend API
NEXT_PUBLIC_API_URL=https://backend-production.up.railway.app/api/v2
NEXT_PUBLIC_QUIZ_PUBLIC_API_URL=https://backend-production.up.railway.app/api/v2/monthly-quiz-public

# Quiz Session
QUIZ_SESSION_SECRET=<gerar-segredo>

# API Settings
NEXT_PUBLIC_API_TIMEOUT=30000
NEXT_PUBLIC_REQUEST_RETRY_ATTEMPTS=3
```

---

## Ordem de Deploy

1. **Backend API** (primeiro, pois outros dependem dele)
2. **Celery Worker** (processa tarefas assíncronas)
3. **Celery Beat** (agenda tarefas periódicas)
4. **Frontend** (consome API do backend)
5. **Quiz Interface** (consome API do backend)

---

## Dependências Externas

### Obrigatórias
- **PostgreSQL**: AWS RDS (configurado com SSL)
- **Redis**: Redis Cloud ou Railway Redis addon
- **Firebase**: Autenticação e Admin SDK
- **Google Gemini**: API para IA

### Opcionais
- **Sentry**: Monitoramento de erros
- **Evolution API**: Integração WhatsApp

---

## Healthchecks

| Serviço | Path | Timeout |
|---------|------|---------|
| Backend API | `/health` | 10s |
| Frontend | `/` | 10s |
| Quiz | `/api/health` | 300s |
| Worker | Celery inspect | 10s |
| Beat | File check | 10s |

---

## Troubleshooting

### Backend não inicia
- Verificar `DATABASE_URL` com `?sslmode=require`
- Verificar `REDIS_URL` acessível
- Verificar `FIREBASE_ADMIN_PRIVATE_KEY` com `\n` corretos

### Frontend não conecta ao backend
- Verificar `VITE_API_URL` aponta para backend Railway
- Verificar CORS no backend (`ALLOWED_ORIGINS`)
- Verificar `VITE_WS_URL` usa `wss://` (não `ws://`)

### Quiz não funciona
- Verificar `NEXT_PUBLIC_QUIZ_PUBLIC_API_URL` correto
- Verificar `QUIZ_SESSION_SECRET` configurado
- Verificar endpoint `/api/v2/monthly-quiz-public` no backend

### Celery Worker não processa tarefas
- Verificar `CELERY_BROKER_URL` e `CELERY_RESULT_BACKEND`
- Verificar `CELERY_QUEUES` configuradas
- Verificar logs do worker para erros de conexão

---

## Arquivos Removidos (Obsoletos)

- ❌ `backend-hormonia/railway-debug.dockerfile`
- ❌ `backend-hormonia/docker-compose.yml`
- ❌ `backend-hormonia/docker-compose.monitoring.yml`
- ❌ `frontend-hormonia/railway-dns-diagnostic.sh`
- ❌ `frontend-hormonia/railway.toml`

---

## Estrutura Final de Arquivos de Deploy

```
backend-hormonia/
├── Dockerfile                 # Backend API
├── Dockerfile.worker          # Celery Worker
├── Dockerfile.beat            # Celery Beat
├── railway.json               # Config Backend API
├── worker/
│   └── railway.json           # Config Worker
└── beat/
    └── railway.json           # Config Beat

frontend-hormonia/
├── Dockerfile                 # (Não usado, Railway usa NIXPACKS)
└── railway.json               # Config Frontend

quiz-mensal-interface/
├── Dockerfile                 # Quiz Next.js
└── railway.json               # Config Quiz
```

---

## Comandos Úteis

### Gerar segredos
```python
import secrets
print(secrets.token_urlsafe(64))  # SECRET_KEY, JWT_SECRET_KEY
print(secrets.token_urlsafe(32))  # CSRF_SECRET_KEY, outros
```

### Testar healthcheck local
```bash
# Backend
curl http://localhost:8000/health

# Frontend (após build)
curl http://localhost:4173/

# Quiz
curl http://localhost:3000/api/health
```

### Logs Railway
```bash
railway logs --service backend-api
railway logs --service celery-worker
railway logs --service celery-beat
railway logs --service frontend
railway logs --service quiz
```

---

**Última atualização**: 2025-11-10
