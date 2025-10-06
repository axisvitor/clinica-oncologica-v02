# Railway Deployment Checklist

## 🎯 Objetivo
Garantir que todas as variáveis de ambiente estejam corretas antes de fazer deploy no Railway, evitando:
- Loading infinito por URLs malformadas
- Erros SSL de conexão com banco de dados
- Problemas de CORS e autenticação

---

## ✅ PRÉ-DEPLOY CHECKLIST

### 1. Validação Automática
```bash
# Rodar script de validação
./scripts/validate-env.sh both

# Deve retornar:
# ✅ All validations passed!
# Safe to deploy to Railway
```

### 2. Frontend Variables (Railway Dashboard)

**Service**: `frontend-production-18bb`

#### URLs Principais ✅
```bash
VITE_API_BASE_URL=https://clinica-oncologica-v02-production.up.railway.app
VITE_API_URL=https://clinica-oncologica-v02-production.up.railway.app/api/v1
VITE_API_BASE_PATH=/api/v1
```

**Validação**:
- [ ] URLs começam com `https://`
- [ ] Incluem path completo `/api/v1`
- [ ] Não têm espaços ou caracteres especiais

#### WebSocket URLs ✅
```bash
VITE_WS_BASE_URL=wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
VITE_WS_URL=wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
```

**Validação**:
- [ ] URLs começam com `wss://`
- [ ] Incluem path completo `/ws/connect`
- [ ] Ambas apontam para mesmo endpoint

#### Firebase ✅
```bash
VITE_FIREBASE_ENABLED=true
VITE_FIREBASE_API_KEY=AIzaSyDbZHMNV2eZQty03TgA4yNo_3L6UDSpHdI
VITE_FIREBASE_AUTH_DOMAIN=sistema-oncologico-auth.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=sistema-oncologico-auth
```

**Validação**:
- [ ] `VITE_FIREBASE_ENABLED=true`
- [ ] Todas as keys Firebase preenchidas

#### Supabase (Desabilitado) ✅
```bash
VITE_SUPABASE_AUTH_ENABLED=false
VITE_SUPABASE_REALTIME_ENABLED=false
```

**Validação**:
- [ ] Auth desabilitado
- [ ] Realtime desabilitado

---

### 3. Backend Variables (Railway Dashboard)

**Service**: Backend principal

#### Database (CRÍTICO) ✅
```bash
DATABASE_URL=postgresql+psycopg://postgres.rszpypytdciggybbpnrp:[PASSWORD]@aws-0-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require
```

**Validação OBRIGATÓRIA**:
- [ ] Inclui `?sslmode=require` no final
- [ ] Protocolo é `postgresql+psycopg://`
- [ ] Password está correto
- [ ] Porta é `5432` (connection pooler) ou `6543` (direct)

**⚠️ ATENÇÃO**: Sem `?sslmode=require` você terá:
```
psycopg.OperationalError: SSL connection has been closed unexpectedly
GET /api/v1/auth/me | Status: 401 | Total: 42.515s
```

#### CORS ✅
```bash
ALLOWED_ORIGINS=https://frontend-production-18bb.up.railway.app,https://clinica-oncologica-v02-production.up.railway.app
```

**Validação**:
- [ ] Inclui domínio Railway frontend
- [ ] Inclui domínio Railway backend (se aplicável)
- [ ] Sem espaços entre domínios
- [ ] Separados por vírgula

#### Firebase Admin ✅
```bash
FIREBASE_BLOCK_PUBLIC_DOMAINS=false
```

**Validação**:
- [ ] Deve ser `false` no Railway
- [ ] `true` causaria erro de autenticação

---

### 4. Firebase Console

**URL**: https://console.firebase.google.com/

#### Authorized Domains ✅
```
Authentication → Settings → Authorized domains
```

**Adicionar**:
- [ ] `frontend-production-18bb.up.railway.app`
- [ ] `clinica-oncologica-v02-production.up.railway.app`
- [ ] `localhost` (desenvolvimento)

---

### 5. Git & Deploy

#### Pre-Deploy ✅
```bash
# Verificar branch
git branch --show-current
# Esperado: docs-refactor-py313 ou main

# Verificar status
git status
# Esperado: working tree clean

# Verificar último commit
git log -1 --oneline
# Deve ter fix mais recente
```

#### Railway Deploy ✅
- [ ] Aguardar build completar (status "Success")
- [ ] Verificar logs sem erros SSL
- [ ] Confirmar que serviço está "Active"

---

## 🧪 PÓS-DEPLOY VALIDATION

### 1. Backend Health Check
```bash
curl https://clinica-oncologica-v02-production.up.railway.app/api/v1/health
```

**Esperado**:
```json
{
  "status": "healthy",
  "configured": true,
  "connected": true
}
```

### 2. Frontend Access
```
https://frontend-production-18bb.up.railway.app
```

**Validação**:
- [ ] Página carrega (não fica em branco)
- [ ] DevTools Console: sem erros "Invalid URL"
- [ ] DevTools Network: HTML tem `Cache-Control: no-cache`

### 3. WebSocket Connection
**DevTools → Console**:
```
WebSocket connection established
wss://clinica-oncologica-v02-production.up.railway.app/ws/connect?token=...
```

**Validação**:
- [ ] WebSocket abre com `wss://` (não `wss:`)
- [ ] Inclui `?token=...`
- [ ] Sem erro "Invalid URL"

### 4. Login Flow
**Teste completo**:
- [ ] Tela de login carrega
- [ ] Credenciais válidas autenticam
- [ ] Não trava em "loading infinito"
- [ ] Dashboard carrega em ~2-3s
- [ ] Sem loop de reconexão

---

## 🚨 TROUBLESHOOTING

### Problema: Loading Infinito
**Sintomas**:
- Login trava em spinner
- DevTools: `wss:clinica...` (sem `//`)
- Console: "Invalid URL"

**Fix**:
1. Verificar Railway vars: `VITE_WS_URL` tem `wss://`
2. Hard refresh: Ctrl + Shift + R
3. Verificar bundle hash mudou

---

### Problema: SSL Connection Closed
**Sintomas**:
- Backend logs: `psycopg.OperationalError: SSL connection closed`
- `/auth/me` retorna 401
- Timeout de 40+ segundos

**Fix**:
1. Adicionar `?sslmode=require` ao `DATABASE_URL`
2. Redeploy backend
3. Verificar Supabase está operacional

---

### Problema: CORS Error
**Sintomas**:
- DevTools: "CORS policy: No 'Access-Control-Allow-Origin'"
- Requests bloqueados

**Fix**:
1. Backend `ALLOWED_ORIGINS` inclui Railway frontend domain
2. Formato correto: `https://frontend-production-18bb.up.railway.app`
3. Sem trailing slash

---

## 📚 Documentação Relacionada

- [Railway Env Vars Corretas](./RAILWAY_ENV_VARS_CORRECT.md)
- [MAINTENANCE_PLAN.md](../MAINTENANCE_PLAN.md)
- Script de validação: `scripts/validate-env.sh`

---

## 🎯 Quick Reference

```bash
# Validar .env localmente
./scripts/validate-env.sh both

# Verificar backend health
curl https://clinica-oncologica-v02-production.up.railway.app/api/v1/health

# Hard refresh frontend
Ctrl + Shift + R (Windows)
Cmd + Shift + R (Mac)

# Verificar WebSocket
DevTools → Console → Filtrar "WebSocket"
```

---

**Última atualização**: 2025-10-06
**Versão**: 2.0 (pós-diagnóstico loading infinito)
