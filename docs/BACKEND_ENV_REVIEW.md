# 🔍 Revisão das Variáveis do Backend - Produção Railway

## 🚨 Problemas Críticos Identificados

### 1️⃣ **CORS - URLs de Localhost (CRÍTICO)**

```bash
❌ ALLOWED_ORIGINS="["http://localhost:5173","http://localhost:3000","http://127.0.0.1:5173"]"
❌ ALLOWED_HOSTS="["localhost","127.0.0.1","0.0.0.0"]"
```

**Problema**: O frontend em produção (`*.up.railway.app`) será bloqueado por CORS!

**Solução**:
```bash
✅ ALLOWED_ORIGINS=["https://SEU-FRONTEND.up.railway.app","https://clinica-oncologica-v02-production.up.railway.app"]
✅ ALLOWED_HOSTS=["clinica-oncologica-v02-production.up.railway.app","*.up.railway.app"]
```

### 2️⃣ **URLs do Frontend - Localhost (CRÍTICO)**

```bash
❌ FRONTEND_API_URL="http://localhost:8000"
❌ FRONTEND_URL="http://localhost:5173"
❌ QUIZ_URL="http://localhost:3001"
```

**Problema**: Backend não sabe onde está o frontend em produção!

**Solução**:
```bash
✅ FRONTEND_API_URL="https://clinica-oncologica-v02-production.up.railway.app"
✅ FRONTEND_URL="https://SEU-FRONTEND.up.railway.app"
✅ QUIZ_URL="https://SEU-QUIZ.up.railway.app"  # Se tiver quiz separado
```

### 3️⃣ **Webhook Evolution - Localhost (CRÍTICO)**

```bash
❌ EVOLUTION_WEBHOOK_URL="http://localhost:8000/webhooks/whatsapp/evolution/clinica_oncologica"
```

**Problema**: Evolution API não consegue enviar webhooks para localhost!

**Solução**:
```bash
✅ EVOLUTION_WEBHOOK_URL="https://clinica-oncologica-v02-production.up.railway.app/api/v1/webhooks/whatsapp/evolution/clinica_oncologica"
```

### 4️⃣ **Quiz URL Base - Localhost**

```bash
❌ MONTHLY_QUIZ_BASE_URL="http://localhost:3001/quiz/monthly"
```

**Solução**:
```bash
✅ MONTHLY_QUIZ_BASE_URL="https://SEU-FRONTEND.up.railway.app/quiz/monthly"
# Ou se tiver quiz separado:
✅ MONTHLY_QUIZ_BASE_URL="https://SEU-QUIZ.up.railway.app/quiz/monthly"
```

### 5️⃣ **LOG_LEVEL - Debug em Produção**

```bash
⚠️ LOG_LEVEL="DEBUG"
```

**Problema**: Logs muito verbosos em produção, afeta performance.

**Solução**:
```bash
✅ LOG_LEVEL="INFO"  # Ou "WARNING" para produção
```

### 6️⃣ **FIREBASE_ALLOWED_DOMAINS - Formato JSON Incorreto**

```bash
❌ FIREBASE_ALLOWED_DOMAINS="["neoplasiaslitoral.com.br","clinicahormonia.com.br"]"
```

**Problema**: String JSON com aspas duplas dentro de aspas duplas.

**Solução**:
```bash
✅ FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com.br","clinicahormonia.com.br","up.railway.app"]
# Ou se o código espera string:
✅ FIREBASE_ALLOWED_DOMAINS='["neoplasiaslitoral.com.br","clinicahormonia.com.br","up.railway.app"]'
```

## ✅ Variáveis Corretas (Manter)

```bash
# Firebase - OK
✅ FIREBASE_ADMIN_PROJECT_ID="sistema-oncologico-auth"
✅ FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----..."
✅ FIREBASE_ADMIN_CLIENT_EMAIL="firebase-adminsdk-fbsvc@sistema-oncologico-auth.iam.gserviceaccount.com"

# Database - OK
✅ DATABASE_URL="postgresql+psycopg://postgres:..."

# Redis - OK
✅ REDIS_URL="redis://default:..."

# Security - OK
✅ SECRET_KEY="TVj0AS9r..."
✅ JWT_SECRET_KEY="mYEeH00A..."
✅ ENCRYPTION_KEY="OUo9cgiZ..."

# Environment - OK
✅ ENVIRONMENT="production"
✅ DEBUG="False"
✅ HOST="0.0.0.0"
✅ PORT="8000"
```

## 📝 Configuração Corrigida Completa

### Variáveis para Atualizar no Railway (Backend):

```bash
# ========== CORS E HOSTS (ATUALIZAR) ==========
ALLOWED_ORIGINS=["https://SEU-FRONTEND.up.railway.app","https://clinica-oncologica-v02-production.up.railway.app"]
ALLOWED_HOSTS=["clinica-oncologica-v02-production.up.railway.app","*.up.railway.app"]

# ========== URLS DO FRONTEND (ATUALIZAR) ==========
FRONTEND_API_URL=https://clinica-oncologica-v02-production.up.railway.app
FRONTEND_URL=https://SEU-FRONTEND.up.railway.app
QUIZ_URL=https://SEU-FRONTEND.up.railway.app

# ========== WEBHOOKS (ATUALIZAR) ==========
EVOLUTION_WEBHOOK_URL=https://clinica-oncologica-v02-production.up.railway.app/api/v1/webhooks/whatsapp/evolution/clinica_oncologica

# ========== QUIZ (ATUALIZAR) ==========
MONTHLY_QUIZ_BASE_URL=https://SEU-FRONTEND.up.railway.app/quiz/monthly

# ========== LOGGING (ATUALIZAR) ==========
LOG_LEVEL=INFO

# ========== FIREBASE DOMAINS (CORRIGIR) ==========
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com.br","clinicahormonia.com.br","up.railway.app"]
```

## 🎯 Substituir Placeholders

**Você precisa descobrir a URL do frontend Railway:**

1. Railway Dashboard → Projeto → Serviço **frontend-hormonia**
2. Copie a URL pública (ex: `frontend-hormonia-production-abc123.up.railway.app`)
3. Substitua `SEU-FRONTEND` em TODAS as variáveis acima

## ⚠️ Variáveis Opcionais (Se Aplicável)

### Se você NÃO tem Quiz separado:
```bash
QUIZ_URL=https://SEU-FRONTEND.up.railway.app
MONTHLY_QUIZ_BASE_URL=https://SEU-FRONTEND.up.railway.app/quiz/monthly
```

### Se você tem domínio customizado:
```bash
ALLOWED_ORIGINS=["https://app.neoplasiaslitoral.com.br","https://clinica-oncologica-v02-production.up.railway.app"]
FRONTEND_URL=https://app.neoplasiaslitoral.com.br
```

## 🔐 Segurança - Observações

### ✅ Correto:
- `SECURE_SSL_REDIRECT="true"` - OK para Railway (tem HTTPS automático)
- `SESSION_COOKIE_SECURE="true"` - OK (força HTTPS)
- `SESSION_COOKIE_HTTPONLY="true"` - OK (previne XSS)

### ⚠️ Verificar:
- **Sentry DSN**: Vazio - configure se quiser monitoramento de erros
- **Firebase Block Public Domains**: `"true"` pode bloquear Railway - teste e mude para `"false"` se necessário

## 📋 Checklist de Atualização

- [ ] Obter URL pública do frontend Railway
- [ ] Atualizar `ALLOWED_ORIGINS` com URLs de produção
- [ ] Atualizar `ALLOWED_HOSTS` com domínios Railway
- [ ] Atualizar `FRONTEND_URL` com URL do frontend
- [ ] Atualizar `FRONTEND_API_URL` com URL do backend
- [ ] Atualizar `EVOLUTION_WEBHOOK_URL` com URL pública
- [ ] Atualizar `MONTHLY_QUIZ_BASE_URL` com URL do frontend
- [ ] Mudar `LOG_LEVEL` para `INFO`
- [ ] Corrigir `FIREBASE_ALLOWED_DOMAINS` (adicionar `up.railway.app`)
- [ ] Salvar e redeploy no Railway

## 🚀 Após Corrigir

1. **Redeploy do backend** no Railway
2. **Teste CORS**:
   ```bash
   # No navegador, console (F12):
   fetch('https://clinica-oncologica-v02-production.up.railway.app/api/v1/health')
     .then(r => r.json())
     .then(console.log)

   # Não deve dar erro CORS
   ```

3. **Teste webhooks** (se usar Evolution):
   - Evolution deve conseguir enviar para a URL pública
   - Verifique logs no Railway para confirmar recebimento

---

**Status**: Identificados 6 problemas críticos que impedem funcionamento em produção.
