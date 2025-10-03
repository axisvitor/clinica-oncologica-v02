# 🚀 Railway Deploy - Quick Start

## TL;DR - Copy/Paste Guide

### 1. Backend API

```yaml
Root Directory: backend-hormonia
Builder: DOCKERFILE
Health Path: /health
Health Timeout: 120
```

**Vars essenciais**:
```bash
DATABASE_URL=postgresql+psycopg://...
REDIS_URL=rediss://...
SECRET_KEY=<32+ chars>
JWT_SECRET_KEY=<32+ chars>
ALLOWED_ORIGINS=["https://<frontend>.railway.app","https://<quiz>.railway.app"]
FRONTEND_URL=https://<frontend>.railway.app
QUIZ_URL=https://<quiz>.railway.app
```

---

### 2. Celery Worker

```yaml
Root Directory: backend-hormonia  # ⚠️ NÃO use /worker/
Builder: DOCKERFILE
Dockerfile Path: Dockerfile.worker
```

**Vars**: Mesmas do Backend

---

### 3. Celery Beat

```yaml
Root Directory: backend-hormonia  # ⚠️ NÃO use /beat/
Builder: DOCKERFILE
Dockerfile Path: Dockerfile.beat
```

**Vars**: Mesmas do Backend

---

### 4. Frontend

```yaml
Root Directory: frontend-hormonia
Builder: DOCKERFILE
Health Path: /health
Health Timeout: 120
```

**Var OBRIGATÓRIA** (senão nginx crashea):
```bash
BACKEND_URL=https://<backend>.railway.app  # SEM /api no final!
```

---

### 5. Quiz

```yaml
Root Directory: quiz-mensal-interface
Builder: DOCKERFILE
Health Path: /api/health
Health Timeout: 300
```

**Vars**:
```bash
NODE_ENV=production
NEXT_PUBLIC_API_URL=https://<backend>.railway.app
```

---

## ✅ Checklist 30 segundos

- [ ] **Backend**: Root=`backend-hormonia`, Health=`/health`, Vars=DB+REDIS+SECRETS ✓
- [ ] **Worker**: Root=`backend-hormonia`, Dockerfile=`Dockerfile.worker` ✓
- [ ] **Beat**: Root=`backend-hormonia`, Dockerfile=`Dockerfile.beat` ✓
- [ ] **Frontend**: Root=`frontend-hormonia`, **BACKEND_URL definido** ✓
- [ ] **Quiz**: Root=`quiz-mensal-interface`, Var=NEXT_PUBLIC_API_URL ✓
- [ ] Todos no **mesmo branch** com **Auto Deploy ON** ✓

---

## 🔥 Erro mais comum

### ❌ Frontend crashea: "host not found in upstream 'backend'"

**Causa**: Faltou definir `BACKEND_URL`

**Fix** (2 cliques):
1. Frontend → Settings → Variables
2. Add: `BACKEND_URL=https://<seu-backend>.railway.app`
3. Redeploy

---

## 🎯 Ordem de Deploy

1. **Backend** → espere health ✓
2. **Worker** + **Beat** (paralelo)
3. **Frontend** (com BACKEND_URL!)
4. **Quiz**

---

## 📋 Template de Variáveis (copie e ajuste)

### Backend/Worker/Beat
```bash
# Database
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db

# Cache (Redis Cloud - já configurado)
REDIS_URL=redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149
REDIS_PASSWORD=6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR
REDIS_HOST=redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com
REDIS_PORT=14149
REDIS_SSL=false

# Celery (usa mesmo Redis com DB 0)
CELERY_BROKER_URL=redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0
CELERY_RESULT_BACKEND=redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0

# Security
SECRET_KEY=YOUR_SECRET_KEY_MIN_32_CHARS_HERE
JWT_SECRET_KEY=YOUR_JWT_SECRET_KEY_MIN_32_CHARS_HERE

# CORS (ajuste domínios)
ALLOWED_ORIGINS=["https://frontend-xxx.up.railway.app","https://quiz-xxx.up.railway.app","http://localhost:3000"]
FRONTEND_URL=https://frontend-xxx.up.railway.app
QUIZ_URL=https://quiz-xxx.up.railway.app

# Environment
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=info
```

### Frontend
```bash
# ⚠️ OBRIGATÓRIO
BACKEND_URL=https://backend-xxx.up.railway.app
```

### Quiz
```bash
NODE_ENV=production
NEXT_PUBLIC_API_URL=https://backend-xxx.up.railway.app
```

---

## 🧪 Testes rápidos

```bash
# Backend
curl https://<backend>/health  # → 200

# Frontend
curl https://<frontend>/health  # → 200
curl https://<frontend>/api/v1/health  # → 200 (via proxy)

# Quiz
curl https://<quiz>/api/health  # → 200 com backend status
```

---

**Guia completo**: Ver [RAILWAY_DEPLOYMENT_GUIDE.md](RAILWAY_DEPLOYMENT_GUIDE.md)
