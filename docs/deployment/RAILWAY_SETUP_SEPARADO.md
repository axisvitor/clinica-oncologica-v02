# 🚀 Railway Setup - Serviços Separados

**Data**: 2025-10-04
**Commit**: `8be74d8`

---

## ✅ ESTRUTURA CORRETA IMPLEMENTADA

Cada serviço tem seu próprio `railway.toml` dentro de sua pasta:

```
clinica-oncologica-v02/
├── backend-hormonia/
│   ├── railway.toml ✅ Configuração do backend
│   ├── Dockerfile
│   └── app/
├── frontend-hormonia/
│   ├── railway.toml ✅ Configuração do frontend
│   ├── Dockerfile
│   └── src/
└── interface-quiz-mensal/
    └── (futuro serviço)
```

**❌ NÃO existe `railway.toml` na raiz** - removido!

---

## 📋 SETUP NO RAILWAY DASHBOARD

Você precisa criar **2 serviços separados** no Railway.

### **PASSO 1: Criar Serviço Backend**

1. **Acesse Railway Dashboard**: https://railway.app/dashboard
2. **New Project** → **Deploy from GitHub repo**
3. **Selecione**: `axisvitor/clinica-oncologica-v02`
4. **Configure o serviço**:
   - **Service Name**: `backend-hormonia`
   - **Root Directory**: `backend-hormonia` ← IMPORTANTE!
   - **Branch**: `docs-refactor-py313`

5. **Railway vai automaticamente**:
   - Detectar `railway.toml` em `backend-hormonia/`
   - Usar `builder = "dockerfile"`
   - Executar `Dockerfile`
   - Health check em `/health`

6. **Adicionar Variáveis de Ambiente**:

```bash
# SECURITY KEYS (GERAR NOVAS!)
SECRET_KEY=<gerar-novo>
JWT_SECRET_KEY=<gerar-novo>
ENCRYPTION_KEY=<gerar-novo>

# DATABASE (adicionar PostgreSQL plugin)
DATABASE_URL=<railway-auto-gera>

# REDIS (adicionar Redis plugin)
REDIS_URL=<railway-auto-gera>
REDIS_SSL=true

# SUPABASE
SUPABASE_URL=https://rszpypytdciggybbpnrp.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJzenB5cHl0ZGNpZ2d5YmJwbnJwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDkzMDQ0NzksImV4cCI6MjA2NDg4MDQ3OX0.qF_byaebH1q78a6SYhGfCuGSotF523o1ZqTrwOBkPYg
SUPABASE_SERVICE_ROLE_KEY=<pegar-do-supabase-dashboard>

# FIREBASE (criar nova service account)
FIREBASE_ADMIN_PROJECT_ID=sistema-oncologico-auth
FIREBASE_ADMIN_CLIENT_EMAIL=<email-da-service-account>
FIREBASE_ADMIN_PRIVATE_KEY=<private-key-completa>

# AI
GEMINI_API_KEY=<sua-key>

# WHATSAPP
EVOLUTION_API_KEY=<sua-key>
EVOLUTION_WEBHOOK_SECRET=<seu-secret>
EVOLUTION_API_URL=https://evolution.axisvanguard.site

# APP CONFIG
ENVIRONMENT=production
DEBUG=false
ALLOWED_ORIGINS=["https://frontend-production-18bb.up.railway.app"]
```

7. **Deploy** → Aguardar build completar

---

### **PASSO 2: Criar Serviço Frontend**

1. **No mesmo projeto Railway**: **New Service** → **Deploy from GitHub repo**
2. **Selecione**: `axisvitor/clinica-oncologica-v02`
3. **Configure o serviço**:
   - **Service Name**: `frontend-hormonia`
   - **Root Directory**: `frontend-hormonia` ← IMPORTANTE!
   - **Branch**: `docs-refactor-py313`

4. **Railway vai automaticamente**:
   - Detectar `railway.toml` em `frontend-hormonia/`
   - Usar `builder = "dockerfile"`
   - Executar multi-stage Dockerfile
   - Health check em `/health`

5. **Adicionar Variáveis de Ambiente**:

```bash
# API URLS (copiar do backend depois que deployar!)
VITE_API_URL=https://backend-hormonia-production.up.railway.app/api/v1
VITE_API_BASE_URL=https://backend-hormonia-production.up.railway.app
VITE_WS_BASE_URL=wss://backend-hormonia-production.up.railway.app/ws

# SUPABASE (mesmas do backend)
VITE_SUPABASE_URL=https://rszpypytdciggybbpnrp.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJzenB5cHl0ZGNpZ2d5YmJwbnJwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDkzMDQ0NzksImV4cCI6MjA2NDg4MDQ3OX0.qF_byaebH1q78a6SYhGfCuGSotF523o1ZqTrwOBkPYg

# FIREBASE (públicas)
VITE_FIREBASE_API_KEY=AIzaSyDbZHMNV2eZQty03TgA4yNo_3L6UDSpHdI
VITE_FIREBASE_PROJECT_ID=sistema-oncologico-auth
VITE_FIREBASE_APP_ID=1:608742835827:web:fa12840b0bd4949b7c8c06
VITE_FIREBASE_AUTH_DOMAIN=sistema-oncologico-auth.firebaseapp.com
VITE_FIREBASE_STORAGE_BUCKET=sistema-oncologico-auth.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=608742835827
VITE_FIREBASE_MEASUREMENT_ID=G-J3QD21JF3F

# ENVIRONMENT
NODE_ENV=production
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false
```

6. **Deploy** → Aguardar build completar

---

## 🔗 IMPORTANTE: Conectar Frontend ao Backend

**Depois que o backend deployar**, você precisa:

1. **Copiar a URL do backend** no Railway Dashboard
   - Exemplo: `https://backend-hormonia-production-xyz.up.railway.app`

2. **Atualizar variáveis do frontend**:
   ```bash
   VITE_API_URL=https://backend-hormonia-production-xyz.up.railway.app/api/v1
   VITE_API_BASE_URL=https://backend-hormonia-production-xyz.up.railway.app
   VITE_WS_BASE_URL=wss://backend-hormonia-production-xyz.up.railway.app/ws
   ```

3. **Atualizar CORS do backend**:
   ```bash
   ALLOWED_ORIGINS=["https://frontend-hormonia-production-abc.up.railway.app"]
   ```

4. **Redeploy ambos os serviços**

---

## ✅ Verificação

### Backend:
```bash
curl https://<seu-backend>.up.railway.app/health

# Esperado:
# {"status":"healthy","service":"hormonia-backend"}
```

### Frontend:
```bash
curl https://<seu-frontend>.up.railway.app/api/config

# Esperado:
# {"VITE_API_URL":"https://...","VITE_SUPABASE_URL":"https://..."}
```

### Browser:
```
https://<seu-frontend>.up.railway.app
```

Deve:
- ✅ Carregar sem loading infinito
- ✅ Conectar ao backend
- ✅ Firebase auth funcionar

---

## 📊 Ordem de Deploy Recomendada

1. ✅ **Backend** (criar primeiro)
   - Adicionar PostgreSQL plugin
   - Adicionar Redis plugin
   - Configurar todas as variáveis
   - Deploy e aguardar sucesso

2. ✅ **Frontend** (criar depois)
   - Usar URL do backend deployado
   - Configurar variáveis
   - Deploy e aguardar sucesso

3. ✅ **Conectar** (final)
   - Atualizar CORS do backend com URL do frontend
   - Redeploy backend
   - Testar integração completa

---

## 🎯 Por Que Serviços Separados?

**Vantagens**:
- ✅ Deploy independente (frontend e backend podem deployar separadamente)
- ✅ Escalonamento independente (scale up apenas o que precisa)
- ✅ Logs separados (mais fácil debugar)
- ✅ Domínios separados (melhor organização)
- ✅ Custo otimizado (paga apenas pelo que usa)

**Como funciona**:
- Cada serviço lê **apenas** seu `railway.toml` local
- Railway detecta automaticamente a pasta correta via "Root Directory"
- Build e deploy são completamente independentes

---

## 📚 Referências

- **Railway Multi-Service**: https://docs.railway.app/guides/monorepo
- **Root Directory**: https://docs.railway.app/guides/root-directory
- **Config as Code**: https://docs.railway.app/reference/config-as-code

---

**Status**: ✅ **ESTRUTURA CORRETA - PRONTO PARA DEPLOY**
