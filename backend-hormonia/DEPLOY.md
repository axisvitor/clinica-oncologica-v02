# Backend Hormonia - Railway Deployment Guide

## 🚀 Deploy Standalone (Pasta Única)

Este guia é para fazer deploy **APENAS** do backend como serviço independente.

---

## 📋 Pré-requisitos

1. Conta no Railway
2. Credenciais do Supabase (PostgreSQL + Storage)
3. Credenciais do Firebase (Authentication)
4. Redis instance (Railway fornecerá)

---

## 🔧 Passo 1: Criar Projeto no Railway

1. Acesse [Railway](https://railway.app)
2. Click "New Project"
3. Selecione "Deploy from GitHub repo"
4. Conecte seu repositório
5. **IMPORTANTE**: Defina **Root Directory** = `backend-hormonia`

---

## 🔌 Passo 2: Adicionar Plugins

### PostgreSQL (Opcional - se não usar Supabase externo)
```
+ New → Database → PostgreSQL
```
- Railway gerará `DATABASE_URL` automaticamente
- **ATENÇÃO**: Mude de `postgresql://` para `postgresql+psycopg://`

### Redis (Obrigatório)
```
+ New → Database → Redis
```
- Railway gerará `REDIS_URL`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`

---

## 🔑 Passo 3: Configurar Variáveis de Ambiente

Copie o conteúdo do arquivo `.env` desta pasta e cole em:
**Settings → Variables → RAW Editor**

### Variáveis CRÍTICAS (substitua os placeholders)

```bash
# SECURITY
SECRET_KEY=<gere com: python -c "import secrets; print(secrets.token_urlsafe(64))">
ALGORITHM=HS256

# FIREBASE
FIREBASE_ADMIN_PROJECT_ID=<seu-projeto-firebase>
FIREBASE_ADMIN_PRIVATE_KEY=<chave-privada-firebase>
FIREBASE_ADMIN_CLIENT_EMAIL=<email-service-account>

# SUPABASE
SUPABASE_URL=https://<seu-projeto>.supabase.co
SUPABASE_ANON_KEY=<anon-key>
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>

# DATABASE (Supabase ou Railway PostgreSQL)
DATABASE_URL=postgresql+psycopg://user:pass@host:port/db

# REDIS (auto-gerado pelo Railway)
REDIS_URL=${{REDIS_URL}}
REDIS_HOST=${{REDIS_HOST}}
REDIS_PORT=${{REDIS_PORT}}
REDIS_PASSWORD=${{REDIS_PASSWORD}}

# CELERY (mesmo Redis)
CELERY_BROKER_URL=${{REDIS_URL}}
CELERY_RESULT_BACKEND=${{REDIS_URL}}
```

### Variáveis AUTO-CONFIGURADAS (Railway)
```bash
PORT=${{RAILWAY_PORT}}
PYTHONUNBUFFERED=1
PYTHONDONTWRITEBYTECODE=1
PASSLIB_BUILTIN_BCRYPT=enabled
LOG_LEVEL=INFO
```

---

## 📦 Passo 4: Deploy

1. Railway detectará `railway.json` automaticamente
2. Build usará `Dockerfile` (Python 3.13 + Node.js para bcrypt/supabase-js)
3. Comando: `gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker`
4. Healthcheck: `GET /health` (timeout 120s)

### Aguarde o Deploy
```
Building... → Deploying... → Running
```

---

## ✅ Passo 5: Verificar Health

Após deploy bem-sucedido:

```bash
curl https://<seu-dominio>.up.railway.app/health
```

Resposta esperada:
```json
{
  "status": "healthy",
  "version": "2.0.0"
}
```

---

## 🔄 Serviços Adicionais (Worker/Beat)

Se precisar de Celery worker ou beat:

### Worker
1. Crie **novo serviço** no mesmo projeto
2. Root Directory: `backend-hormonia`
3. Settings → Build → Dockerfile Path: `Dockerfile.worker`
4. Copie as **mesmas variáveis** de ambiente do backend-web

### Beat
1. Crie **novo serviço** no mesmo projeto
2. Root Directory: `backend-hormonia`
3. Settings → Build → Dockerfile Path: `Dockerfile.beat`
4. Copie as **mesmas variáveis** de ambiente do backend-web

---

## 🌐 Passo 6: Configurar CORS (após deploy frontend/quiz)

Volte ao backend e atualize:

```bash
ALLOWED_ORIGINS=["https://<frontend-domain>","https://<quiz-domain>"]
FRONTEND_URL=https://<frontend-domain>
QUIZ_URL=https://<quiz-domain>
```

Redeploy backend.

---

## 📊 Arquitetura

```
┌─────────────────────────────────────┐
│     Railway Project                  │
├─────────────────────────────────────┤
│                                      │
│  ┌──────────────┐                   │
│  │ backend-web  │  Port: 8000       │
│  │ (FastAPI)    │  /health          │
│  └──────────────┘                   │
│         │                            │
│         ├─ PostgreSQL (Supabase)    │
│         ├─ Redis (Railway)          │
│         └─ Firebase Auth            │
│                                      │
│  ┌──────────────┐  ┌─────────────┐ │
│  │   worker     │  │    beat     │ │
│  │  (Celery)    │  │  (Celery)   │ │
│  └──────────────┘  └─────────────┘ │
└─────────────────────────────────────┘
```

---

## 🐛 Troubleshooting

### "DATABASE_URL connection error"
→ Certifique-se de usar `postgresql+psycopg://` (não `postgresql://`)

### "Redis connection refused"
→ Verifique se variáveis `REDIS_*` estão definidas

### "Firebase authentication failed"
→ Verifique se private key tem `\n` (newlines) corretos

### "Build fails on bcrypt"
→ O Dockerfile já instala Node.js necessário para bcrypt nativo

---

## 📁 Arquivos Importantes

- `Dockerfile` - Build principal (web server)
- `Dockerfile.worker` - Celery worker
- `Dockerfile.beat` - Celery beat scheduler
- `railway.json` - Configuração Railway
- `.env` - Variáveis de ambiente (NÃO commitar)
- `requirements.txt` - Dependências Python

---

## 🔒 Segurança

- [ ] `.env` está no `.gitignore`
- [ ] SECRET_KEY gerado com 64+ caracteres
- [ ] ENCRYPTION_KEY gerado com 32 bytes
- [ ] Firebase private key protegido
- [ ] CORS configurado com domínios específicos
- [ ] SSL/TLS habilitado (HTTPS only)

---

**Deployment Type**: Standalone Service
**Builder**: Docker (Python 3.13-slim + Node 20)
**Runtime**: Gunicorn + Uvicorn Workers
**Health Check**: GET /health (120s timeout)
