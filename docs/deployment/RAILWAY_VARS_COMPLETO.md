# 🚨 RAILWAY - CORREÇÃO COMPLETA DE TODAS AS VARIÁVEIS

## ❌ PROBLEMA CONFIRMADO PELOS LOGS

### **Frontend** (Loading Infinito)
```
API URL: https:clinica-oncologica-v02-production.up.railway.appapiv1
WS  URL: wss:clinica-oncologica-v02-production.up.railway.appwsconnect
         ^^ falta //                                   ^^ falta /
```

### **Backend** (401 - SSL Connection Closed)
```
DATABASE_URL: postgresql+psycopg:postgres.rszp...@aws-0-sa-east-1.pooler.supabase.com:5432postgressslmode=require
                           ^^ falta //                                           ^^ falta /  ^^ falta ?
```

**Resultado**:
- WebSocket: `new URL()` falha → loop infinito
- Database: TLS falha → Supabase fecha conexão → 401

---

## ✅ CORREÇÃO COMPLETA - COPIAR E COLAR

### **FRONTEND SERVICE** (`frontend-production-18bb`)

Railway Dashboard → `frontend-production-18bb` → Variables → **Editar cada uma**:

#### **URLs Principais** (5 variáveis)

**1. VITE_API_BASE_URL**
```
❌ ERRADO: https:clinica-oncologica-v02-production.up.railway.app
✅ CORRETO: https://clinica-oncologica-v02-production.up.railway.app
```

**2. VITE_API_URL**
```
❌ ERRADO: https:clinica-oncologica-v02-production.up.railway.appapiv1
✅ CORRETO: https://clinica-oncologica-v02-production.up.railway.app/api/v1
```

**3. VITE_API_BASE_PATH**
```
❌ ERRADO: /apiv1
✅ CORRETO: /api/v1
```

**4. VITE_WS_BASE_URL**
```
❌ ERRADO: wss:clinica-oncologica-v02-production.up.railway.appwsconnect
✅ CORRETO: wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
```

**5. VITE_WS_URL**
```
❌ ERRADO: wss:clinica-oncologica-v02-production.up.railway.appwsconnect
✅ CORRETO: wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
```

---

### **BACKEND SERVICE** (Serviço Principal)

Railway Dashboard → Backend → Variables → **Editar cada uma**:

#### **Database** (CRÍTICO - SSL)

**DATABASE_URL**
```
❌ ERRADO:
postgresql+psycopg:postgres.rszpypytdciggybbpnrp:NvbKfi1xMY7wzNof@aws-0-sa-east-1.pooler.supabase.com:5432postgressslmode=require

✅ CORRETO:
postgresql+psycopg://postgres.rszpypytdciggybbpnrp:NvbKfi1xMY7wzNof@aws-0-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require
                  ^^                                                                                          ^        ^
              adicionar                                                                                   adicionar adicionar
```

**Diferenças**:
1. `postgresql+psycopg:` → `postgresql+psycopg://` (adicionar `//`)
2. `:5432postgres` → `:5432/postgres` (adicionar `/`)
3. `postgressslmode=require` → `postgres?sslmode=require` (adicionar `?`)

#### **Supabase URLs**

**SUPABASE_URL**
```
❌ ERRADO: https:rszpypytdciggybbpnrp.supabase.co
✅ CORRETO: https://rszpypytdciggybbpnrp.supabase.co
```

#### **Evolution API URLs**

**EVOLUTION_API_URL**
```
❌ ERRADO: https:clinica-oncologica-v02-production.up.railway.app
✅ CORRETO: https://clinica-oncologica-v02-production.up.railway.app
```

**EVOLUTION_WEBHOOK_URL**
```
❌ ERRADO: https:clinica-oncologica-v02-production.up.railway.appwebhookevolution
✅ CORRETO: https://clinica-oncologica-v02-production.up.railway.app/webhook/evolution
```

#### **CORS & Frontend URL**

**ALLOWED_ORIGINS**
```
❌ ERRADO: https:frontend-production-18bb.up.railway.app,https:clinica-oncologica-v02-production.up.railway.app
✅ CORRETO: https://frontend-production-18bb.up.railway.app,https://clinica-oncologica-v02-production.up.railway.app
```

**FRONTEND_URL**
```
❌ ERRADO: https:frontend-production-18bb.up.railway.app
✅ CORRETO: https://frontend-production-18bb.up.railway.app
```

---

## 📋 CHECKLIST DE APLICAÇÃO

### **Etapa 1: Frontend (5 variáveis)**

- [ ] `VITE_API_BASE_URL` tem `https://`
- [ ] `VITE_API_URL` tem `https://` e `/api/v1`
- [ ] `VITE_API_BASE_PATH` é `/api/v1`
- [ ] `VITE_WS_BASE_URL` tem `wss://` e `/ws/connect`
- [ ] `VITE_WS_URL` tem `wss://` e `/ws/connect`
- [ ] Clicou "Save" ou variáveis auto-salvaram

### **Etapa 2: Backend (7 variáveis)**

- [ ] `DATABASE_URL` tem `://`, `/postgres`, `?sslmode=require`
- [ ] `SUPABASE_URL` tem `https://`
- [ ] `EVOLUTION_API_URL` tem `https://`
- [ ] `EVOLUTION_WEBHOOK_URL` tem `https://` e `/webhook/evolution`
- [ ] `ALLOWED_ORIGINS` tem `https://` em ambos
- [ ] `FRONTEND_URL` tem `https://`
- [ ] Clicou "Save" ou variáveis auto-salvaram

### **Etapa 3: Railway Redeploy**

- [ ] Frontend: status "Deploying..." → "Success"
- [ ] Backend: status "Deploying..." → "Success"
- [ ] Aguardou ~2-3 minutos para builds completarem

### **Etapa 4: Firebase Console**

- [ ] Acesso: https://console.firebase.google.com/
- [ ] Projeto: `sistema-oncologico-auth`
- [ ] Authentication → Settings → Authorized domains
- [ ] Adicionado: `frontend-production-18bb.up.railway.app`
- [ ] Adicionado: `clinica-oncologica-v02-production.up.railway.app`
- [ ] Total de domínios: 4 (localhost + firebaseapp + 2 railway)

### **Etapa 5: Teste Frontend**

- [ ] Hard refresh: Ctrl + Shift + R (Windows) ou Cmd + Shift + R (Mac)
- [ ] Ou abriu aba anônima
- [ ] DevTools → Network → HTML tem `Cache-Control: no-cache`
- [ ] DevTools → Network → JS tem hash novo (não `index-B7p7m4he.js`)
- [ ] DevTools → Console → WebSocket: `wss://clinica...?token=...`
- [ ] DevTools → Console → SEM erro "Invalid URL"

### **Etapa 6: Teste Login**

- [ ] Tela de login carregou
- [ ] Inseriu credenciais válidas
- [ ] Login completou em 2-3 segundos (não 40s)
- [ ] Dashboard carregou normalmente
- [ ] SEM loop de reconexão

---

## 🔍 VALIDAÇÃO PÓS-CORREÇÃO

### **Backend Logs (Railway → Backend → Logs)**

**Esperado**:
```
✓ Database connected successfully
✓ Firebase Admin SDK initialized
✓ WebSocket manager initialized
REQUEST | GET /api/v1/auth/me | Status: 200 | Total: 0.234s
```

**NÃO deve aparecer**:
```
❌ psycopg.OperationalError: SSL connection has been closed unexpectedly
❌ GET /api/v1/auth/me | Status: 401 | Total: 42.515s
```

### **Frontend Console (DevTools)**

**Esperado**:
```
[Info] The app is running in production mode
[ApiClient] Request successful: /api/v1/auth/me
[WebSocket] Connection established
wss://clinica-oncologica-v02-production.up.railway.app/ws/connect?token=...
```

**NÃO deve aparecer**:
```
❌ Invalid URL
❌ wss:clinica-oncologica-v02-production.up.railway.appwsconnect
❌ Failed to construct 'URL': Invalid URL
```

---

## 🎯 RESUMO VISUAL DAS CORREÇÕES

### **Frontend - Padrão de Correção**

```
PADRÃO:
https:DOMAIN/PATH  →  https://DOMAIN/PATH
wss:DOMAIN/PATH    →  wss://DOMAIN/PATH
      ^^                     ^^
   adicionar              adicionar
```

**Exemplos**:
```
https:clinica...appapiv1           →  https://clinica.../api/v1
wss:clinica...appwsconnect         →  wss://clinica.../ws/connect
```

### **Backend - Padrão de Correção**

```
PADRÃO DATABASE_URL:
postgresql+psycopg:USER:PASS@HOST:PORTDATABASEsslmode=require
                  ^                    ^       ^
              adicionar://         adicionar/  adicionar?

postgresql+psycopg://USER:PASS@HOST:PORT/DATABASE?sslmode=require
```

**Exemplo**:
```
postgresql+psycopg:postgres...@aws...com:5432postgressslmode=require
                  ^^                        ^        ^
              adicionar                 adicionar adicionar

postgresql+psycopg://postgres...@aws...com:5432/postgres?sslmode=require
```

---

## 🚨 TROUBLESHOOTING

### **Problema: Variáveis não salvam**
**Sintomas**: Edita, clica fora, recarrega página e valor antigo volta
**Fix**:
1. Railway Dashboard → Service → Variables
2. Edite variável
3. **Pressione Enter** antes de clicar fora
4. Veja se aparece checkmark ✓ verde
5. Se não salvar: use "Raw Editor" mode (botão no canto)

### **Problema: Deploy não trigga automaticamente**
**Sintomas**: Editou variáveis mas build não inicia
**Fix**:
1. Railway Dashboard → Service → Settings
2. Clique "Redeploy" manualmente
3. Ou altere qualquer outra variável (adicione espaço no final e remova)

### **Problema: Login ainda trava após correções**
**Sintomas**: Todas variáveis corretas, builds Success, mas login trava
**Fix**:
1. Feche **TODAS** as abas do site
2. Limpe cache: Ctrl + Shift + Delete → "Cached images and files"
3. Reinicie browser
4. Abra **aba anônima**
5. Teste novamente

### **Problema: 401 persiste mesmo com DATABASE_URL correto**
**Sintomas**: Backend logs: "Connection refused" ou "max connections"
**Fix**:
1. Verifique Supabase Dashboard: https://supabase.com/dashboard
2. Projeto: `rszpypytdciggybbpnrp`
3. Settings → Database → Connection pooling: deve estar **habilitado**
4. Connection string deve usar porta **6543** (pooler) ou **5432** (direct)

---

## 📚 REFERÊNCIAS

- **Guia urgente**: [RAILWAY_FIX_URGENTE.md](./RAILWAY_FIX_URGENTE.md)
- **Checklist deploy**: [RAILWAY_DEPLOY_CHECKLIST.md](./RAILWAY_DEPLOY_CHECKLIST.md)
- **Env vars corretas**: [RAILWAY_ENV_VARS_CORRECT.md](./RAILWAY_ENV_VARS_CORRECT.md)
- **Script validação**: `scripts/validate-env.sh`

---

## 🎯 AÇÃO IMEDIATA

1. ✅ Abra Railway Dashboard
2. ✅ Frontend: corrija 5 variáveis
3. ✅ Backend: corrija 7 variáveis
4. ✅ Aguarde deploys (2-3 min)
5. ✅ Configure Firebase domains
6. ✅ Hard refresh e teste login

---

**Última atualização**: 2025-10-06
**Status**: 🚨 **TODAS AS CORREÇÕES IDENTIFICADAS - APLICAR AGORA**
