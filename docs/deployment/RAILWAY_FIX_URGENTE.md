# 🚨 CORREÇÕES URGENTES APLICADAS - Railway Deploy

**Data**: 2025-10-04
**Commit**: `3749978`
**Status**: ✅ **PUSHED - Deploy iniciando**

---

## ✅ PROBLEMAS CORRIGIDOS

### 1. **Frontend TOML Parse Error**

**Erro Original:**
```
Failed to parse TOML file frontend-hormonia/railway.toml: (21, 21): no value can start with p
```

**Causa:**
```toml
# ❌ INVÁLIDO - TOML não suporta JavaScript
VITE_SUPABASE_URL = process.env['VITE_SUPABASE_URL'] || ""
VITE_SUPABASE_ANON_KEY = process.env['VITE_SUPABASE_ANON_KEY'] || ""
```

**Correção:**
```toml
# ✅ VÁLIDO - Comentários documentando onde configurar
# NOTE: All environment variables must be set in Railway Dashboard
# Required variables to set in Railway Dashboard:
# - VITE_SUPABASE_URL
# - VITE_SUPABASE_ANON_KEY
# - VITE_API_URL
```

**Por que TOML não aceita JavaScript:**
- TOML é um formato de configuração estático
- Não suporta expressões, funções ou operadores (`||`, `process.env`, etc)
- Apenas valores literais: strings, números, booleans, arrays

---

### 2. **Backend Dockerfile Not Found**

**Erro Original:**
```
[Region: us-east4]
Dockerfile `Dockerfile` does not exist.
```

**Causa:**
```toml
builder = "DOCKERFILE"  # ❌ Maiúsculas incorretas
```

**Correção:**
```toml
builder = "dockerfile"  # ✅ Minúsculas corretas
```

**Arquivos Corrigidos:**
- ✅ `backend-hormonia/railway.toml`
- ✅ `railway.toml` (root - 4 ocorrências corrigidas)

---

## 🔧 AÇÃO NECESSÁRIA: Configurar Variáveis no Railway Dashboard

**Agora você DEVE configurar as variáveis de ambiente manualmente no Railway Dashboard**, pois o TOML não pode mais conter valores dinâmicos.

### **PASSO 1: Frontend Service**

Acesse: **Railway Dashboard → Frontend Service → Variables**

Adicione estas variáveis:

```bash
# API URLs (CRÍTICO - substitua <backend-service> pelo nome real)
VITE_API_URL=https://<backend-service>.up.railway.app/api/v1
VITE_API_BASE_URL=https://<backend-service>.up.railway.app
VITE_WS_BASE_URL=wss://<backend-service>.up.railway.app/ws

# Supabase (chaves públicas)
VITE_SUPABASE_URL=https://rszpypytdciggybbpnrp.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJzenB5cHl0ZGNpZ2d5YmJwbnJwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDkzMDQ0NzksImV4cCI6MjA2NDg4MDQ3OX0.qF_byaebH1q78a6SYhGfCuGSotF523o1ZqTrwOBkPYg

# Firebase (chaves públicas - serão carregadas via runtime config)
VITE_FIREBASE_API_KEY=AIzaSyDbZHMNV2eZQty03TgA4yNo_3L6UDSpHdI
VITE_FIREBASE_PROJECT_ID=sistema-oncologico-auth
VITE_FIREBASE_APP_ID=1:608742835827:web:fa12840b0bd4949b7c8c06
VITE_FIREBASE_AUTH_DOMAIN=sistema-oncologico-auth.firebaseapp.com
VITE_FIREBASE_STORAGE_BUCKET=sistema-oncologico-auth.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=608742835827
VITE_FIREBASE_MEASUREMENT_ID=G-J3QD21JF3F

# Environment
NODE_ENV=production
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false

# PORT é configurado automaticamente pelo Railway
```

---

### **PASSO 2: Backend Service**

Acesse: **Railway Dashboard → Backend API Service → Variables**

**Chaves de Segurança (GERAR NOVAS!):**

```bash
# NUNCA use as chaves do .env local em produção!
# Gere novas chaves com estes comandos:

# No terminal local:
python -c "import secrets; print(secrets.token_urlsafe(64))"  # SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(64))"  # JWT_SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # ENCRYPTION_KEY
python -c "import secrets; print(secrets.token_urlsafe(64))"  # MONTHLY_QUIZ_TOKEN_SECRET
```

**Adicione no Railway:**

```bash
# Security (GERAR NOVAS!)
SECRET_KEY=<cole-resultado-do-comando-1>
JWT_SECRET_KEY=<cole-resultado-do-comando-2>
ENCRYPTION_KEY=<cole-resultado-do-comando-3>
MONTHLY_QUIZ_TOKEN_SECRET=<cole-resultado-do-comando-4>

# Database (Railway vai fornecer automaticamente se você adicionar PostgreSQL)
DATABASE_URL=<railway-fornece-automaticamente>

# Redis (Railway vai fornecer automaticamente se você adicionar Redis)
REDIS_URL=<railway-fornece-automaticamente>
REDIS_PASSWORD=<extrair-da-redis-url>
REDIS_HOST=<extrair-da-redis-url>
REDIS_PORT=<extrair-da-redis-url>
REDIS_SSL=true

# Supabase
SUPABASE_URL=https://rszpypytdciggybbpnrp.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJzenB5cHl0ZGNpZ2d5YmJwbnJwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDkzMDQ0NzksImV4cCI6MjA2NDg4MDQ3OX0.qF_byaebH1q78a6SYhGfCuGSotF523o1ZqTrwOBkPYg
SUPABASE_SERVICE_ROLE_KEY=<sua-service-role-key-do-supabase-dashboard>

# Firebase Admin SDK (Criar nova service account!)
FIREBASE_ADMIN_PROJECT_ID=sistema-oncologico-auth
FIREBASE_ADMIN_CLIENT_EMAIL=<firebase-adminsdk-email>
FIREBASE_ADMIN_PRIVATE_KEY=<private-key-da-service-account>

# AI Services
GEMINI_API_KEY=<sua-gemini-api-key>

# WhatsApp Evolution API
EVOLUTION_API_KEY=<sua-evolution-key>
EVOLUTION_WEBHOOK_SECRET=<seu-webhook-secret>
EVOLUTION_API_URL=https://evolution.axisvanguard.site

# CORS (CRÍTICO - adicionar URL real do frontend)
ALLOWED_ORIGINS=["https://frontend-production-18bb.up.railway.app"]

# Environment
ENVIRONMENT=production
DEBUG=false
APP_NAME=NeoplasiaLitoral-Backend
ENABLE_REDIS=true
ENABLE_EVOLUTION=true
```

---

## 📊 STATUS DO DEPLOY

### Railway Agora Vai:

1. **Detectar o novo push** (commit `3749978`)
2. **Ler os arquivos TOML corrigidos:**
   - ✅ `builder = "dockerfile"` (minúsculas)
   - ✅ Sem expressões JavaScript inválidas
3. **Backend:**
   - Encontrar `Dockerfile` em `backend-hormonia/`
   - Build com Python 3.13
   - Iniciar com Gunicorn + Uvicorn
4. **Frontend:**
   - Build com `npm run build:runtime`
   - Gerar configs em runtime (docker-entrypoint.sh)
   - Servir com nginx

---

## ⏱️ Timeline Esperado

- ✅ **Agora**: Push detectado pelo Railway
- 🔄 **+1 min**: Build iniciado
- 🔄 **+3 min**: Backend buildando
- 🔄 **+5 min**: Frontend buildando
- ✅ **+7 min**: Deploy completo (se variáveis configuradas)

---

## 🚨 IMPORTANTE: Sem Variáveis = Falha

**Se você não configurar as variáveis no Railway Dashboard:**
- ❌ Backend não inicia (falta SECRET_KEY, DATABASE_URL, etc)
- ❌ Frontend não conecta (falta VITE_API_URL)
- ❌ Autenticação não funciona (falta Firebase/Supabase keys)

**Ordem recomendada:**
1. Configure variáveis do **Backend** primeiro
2. Aguarde backend deploy completar
3. Copie a URL do backend
4. Configure variáveis do **Frontend** com a URL do backend
5. Aguarde frontend deploy completar

---

## 🔍 Verificação Pós-Deploy

### Backend:
```bash
curl https://<seu-backend>.up.railway.app/health

# Esperado:
# {"status":"healthy","service":"hormonia-backend"}
```

### Frontend:
```bash
curl https://frontend-production-18bb.up.railway.app/api/config

# Esperado:
# { "VITE_API_URL": "https://...", "VITE_SUPABASE_URL": "https://..." }
```

### Navegador:
```
https://frontend-production-18bb.up.railway.app
```

**Deve:**
- ✅ Carregar sem "Loading" infinito
- ✅ Conectar ao backend
- ✅ Autenticação funcionar

---

## 📚 Referências

**Documentação TOML:**
- Não suporta variáveis ou expressões
- Apenas valores estáticos
- Veja: https://toml.io/en/

**Railway Config:**
- https://docs.railway.app/reference/config-as-code
- Environment Variables: https://docs.railway.app/guides/variables

**Guias de Deploy:**
- [docs/deployment/RAILWAY_COMPLETE_GUIDE.md](./RAILWAY_COMPLETE_GUIDE.md)
- [docs/deployment/RAILWAY_ENV_VARS_COMPLETE.md](./RAILWAY_ENV_VARS_COMPLETE.md)

---

**Status**: ✅ **CORREÇÕES APLICADAS - AGUARDANDO CONFIGURAÇÃO DE VARIÁVEIS**
