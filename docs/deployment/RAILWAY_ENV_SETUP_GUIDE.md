# Railway Environment Variables Setup Guide

## 📋 Quick Reference

Este guia lista **TODAS** as variáveis de ambiente necessárias para cada serviço no Railway. Use os arquivos `.env` criados em cada pasta como referência completa.

---

## 🔧 Backend Services (backend-web, backend-worker, backend-beat)

### Plugins Necessários
1. **PostgreSQL** → Gera `DATABASE_URL` automaticamente
2. **Redis** → Gera `REDIS_URL` automaticamente

### Variáveis CRÍTICAS (obrigatórias)

```bash
# SECURITY
SECRET_KEY=<generate-with-python-secrets>
ALGORITHM=HS256

# FIREBASE (get from Firebase Console → Service Accounts)
FIREBASE_ADMIN_PROJECT_ID=<your-firebase-project-id>
FIREBASE_ADMIN_PRIVATE_KEY=<your-private-key-with-newlines>
FIREBASE_ADMIN_CLIENT_EMAIL=<firebase-adminsdk-xxxxx@project.iam.gserviceaccount.com>

# SUPABASE (get from Supabase Dashboard → API)
SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_ANON_KEY=<your-anon-key>
SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>

# DATABASE (Railway auto-generates, but change driver)
# IMPORTANT: Change from postgresql:// to postgresql+psycopg://
DATABASE_URL=postgresql+psycopg://postgres:<pass>@<host>:<port>/<db>

# REDIS (Railway auto-generates)
REDIS_URL=<railway-redis-url>
REDIS_HOST=<railway-redis-host>
REDIS_PORT=<railway-redis-port>
REDIS_PASSWORD=<railway-redis-password>

# CELERY (use same Redis, change DB number)
CELERY_BROKER_URL=<same-as-redis-url-but-db0>
CELERY_RESULT_BACKEND=<same-as-redis-url-but-db0>
```

### Variáveis RECOMENDADAS (opcionais)

```bash
# AI SERVICE (get from Google AI Studio)
GEMINI_API_KEY=<your-gemini-api-key>

# WHATSAPP (get from your Evolution API instance)
ENABLE_EVOLUTION=true
EVOLUTION_API_KEY=<your-evolution-api-key>
EVOLUTION_API_URL=<your-evolution-api-url>
EVOLUTION_WEBHOOK_SECRET=<your-webhook-secret>

# CORS (add after frontend/quiz are deployed)
ALLOWED_ORIGINS=["<frontend-url>","<quiz-url>"]

# MONITORING (optional)
SENTRY_DSN=<your-sentry-dsn>
```

### Variáveis AUTO-CONFIGURADAS (já definidas em railway.json)

```bash
PORT=${{RAILWAY_PORT}}
PYTHONUNBUFFERED=1
PYTHONDONTWRITEBYTECODE=1
PASSLIB_BUILTIN_BCRYPT=enabled
LOG_LEVEL=INFO
ENVIRONMENT=production
```

---

## 🎨 Frontend Service

### Variáveis CRÍTICAS (obrigatórias)

```bash
# BACKEND CONNECTION (set after backend-web is deployed)
VITE_API_URL=<backend-web-public-url>
VITE_API_BASE_URL=<backend-web-public-url>
VITE_WS_URL=wss://<backend-domain>/ws
VITE_WS_BASE_URL=wss://<backend-domain>/ws

# SUPABASE (same as backend - PUBLIC keys only)
VITE_SUPABASE_URL=https://<your-project>.supabase.co
VITE_SUPABASE_ANON_KEY=<your-supabase-anon-key>
```

### Variáveis RECOMENDADAS (opcionais)

```bash
# MONITORING
VITE_SENTRY_DSN=<your-sentry-dsn>
VITE_ANALYTICS_TRACKING_ID=<your-analytics-id>

# CLINIC BRANDING
VITE_CLINIC_NAME=Clínica Hormonia
VITE_CLINIC_PHONE=+55 11 99999-9999
VITE_CLINIC_EMAIL=contato@clinicahormonia.com.br
```

### Variáveis AUTO-CONFIGURADAS (já definidas em .env)

```bash
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false
VITE_ENABLE_WHATSAPP_INTEGRATION=true
VITE_ENABLE_AI_CHAT=true
# ... (130+ variables já configuradas no .env)
```

---

## 📝 Quiz Service

### Variáveis CRÍTICAS (obrigatórias)

```bash
# BACKEND CONNECTION (set after backend-web is deployed)
NEXT_PUBLIC_API_URL=<backend-web-public-url>
```

### Variáveis AUTO-CONFIGURADAS

```bash
NODE_ENV=production
NEXT_TELEMETRY_DISABLED=1
```

### Variáveis OPCIONAIS

```bash
# MONITORING
NEXT_PUBLIC_SENTRY_DSN=<your-sentry-dsn>
NEXT_PUBLIC_GOOGLE_ANALYTICS_ID=<your-analytics-id>
```

---

## 🚀 Deployment Workflow

### Phase 1: Setup Plugins

1. **Add PostgreSQL plugin** to your Railway project
   - Note the `DATABASE_URL` generated
   - **Change driver**: Replace `postgresql://` with `postgresql+psycopg://`

2. **Add Redis plugin** to your Railway project
   - Note the `REDIS_URL`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`

### Phase 2: Deploy Backend Services

1. **Create backend-web service**
   - Root Directory: `backend-hormonia`
   - Add all CRITICAL variables from above
   - Railway will use `railway.json` → `Dockerfile`
   - Deploy and wait for public URL

2. **Create backend-worker service**
   - Root Directory: `backend-hormonia`
   - Set Dockerfile Path: `Dockerfile.worker`
   - Copy same env variables from backend-web
   - Add `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`

3. **Create backend-beat service**
   - Root Directory: `backend-hormonia`
   - Set Dockerfile Path: `Dockerfile.beat`
   - Copy same env variables from backend-web
   - Add `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`

### Phase 3: Deploy Frontend

1. **Create frontend service**
   - Root Directory: `frontend-hormonia`
   - Railway will use `railway.json` → `Dockerfile`
   - Add `VITE_API_URL` = backend-web public URL
   - Add `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`
   - Redeploy after adding variables

### Phase 4: Deploy Quiz

1. **Create quiz service**
   - Root Directory: `quiz-mensal-interface`
   - Railway will use `railway.json` (Nixpacks)
   - Add `NEXT_PUBLIC_API_URL` = backend-web public URL
   - Redeploy after adding variables

### Phase 5: Update Backend CORS

1. Go back to **backend-web** service
2. Update `ALLOWED_ORIGINS`:
   ```bash
   ALLOWED_ORIGINS=["<frontend-url>","<quiz-url>"]
   ```
3. Redeploy backend-web

---

## 🔒 Security Checklist

- [ ] Changed all `{{PLACEHOLDER}}` values in `.env` files
- [ ] Generated secure random keys using `python -c "import secrets; print(secrets.token_urlsafe(64))"`
- [ ] DATABASE_URL uses `postgresql+psycopg://` driver
- [ ] Redis URL includes SSL (`rediss://`) for production
- [ ] CORS `ALLOWED_ORIGINS` set to specific domains (not `*`)
- [ ] Firebase private key properly formatted (with `\n` for newlines)
- [ ] All secrets stored in Railway environment variables (not committed to git)

---

## 📊 Environment Variables Count Summary

| Service | Critical Vars | Recommended Vars | Auto-Configured | Total |
|---------|--------------|------------------|-----------------|-------|
| backend-web | 15 | 8 | 10 | 33 |
| backend-worker | 17 | 5 | 8 | 30 |
| backend-beat | 17 | 5 | 8 | 30 |
| frontend | 6 | 5 | 130+ | 140+ |
| quiz | 1 | 2 | 2 | 5 |

---

## 🆘 Quick Troubleshooting

### "DATABASE_URL connection error"
→ Ensure you changed `postgresql://` to `postgresql+psycopg://`

### "Redis connection refused"
→ Check `REDIS_SSL=true` and `REDIS_URL` starts with `rediss://`

### "CORS policy error"
→ Add frontend/quiz URLs to backend's `ALLOWED_ORIGINS`

### "Firebase authentication failed"
→ Verify private key has `\n` newlines and client email is correct

### "Celery worker not processing tasks"
→ Ensure `CELERY_BROKER_URL` points to Redis DB 0

---

## 📁 Files Reference

- **Backend full config**: `backend-hormonia/.env` (186 lines)
- **Frontend full config**: `frontend-hormonia/.env` (174 lines)
- **Quiz full config**: `quiz-mensal-interface/.env` (19 lines)
- **Deployment guide**: `RAILWAY_DEPLOYMENT.md`

---

**Last Updated**: 2025-10-03
**Configuration Version**: 1.0.0
