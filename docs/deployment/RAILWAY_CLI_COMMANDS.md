# Railway CLI - Comandos para Corrigir Variáveis

**Data**: 2025-10-06
**Status**: 🚨 **AÇÃO MANUAL NECESSÁRIA**

---

## 🎯 Problema Identificado

O Railway CLI requer linking interativo que está dando timeout em ambiente automatizado. Você precisa executar os comandos manualmente.

---

## 📋 Etapas - Executar Manualmente

### **Etapa 1: Link ao Projeto**

```bash
# Abrir terminal e navegar para o projeto
cd "c:\Meu Projetos\clinica-oncologica-v02"

# Linkar ao projeto Railway (selecionar "sistema-oncologico")
railway link
# → Selecionar: "sistema-oncologico"
# → Workspace: "My Workspace"
# → Environment: "production"
```

---

### **Etapa 2: Listar Variáveis Atuais do Frontend**

```bash
# Listar todas as variáveis do frontend service
railway variables --service frontend-production-18bb
```

**Ou se o nome do service for diferente:**
```bash
# Listar todos os services
railway service

# Depois listar variáveis do service correto
railway variables --service <FRONTEND_SERVICE_NAME>
```

---

### **Etapa 3: Corrigir Variáveis do Frontend**

**Copie e cole EXATAMENTE esses valores no Railway Dashboard:**

#### **VITE_API_BASE_URL**
```
https://clinica-oncologica-v02-production.up.railway.app
```
✅ Tem `https://` (não `https:`)

#### **VITE_API_URL**
```
https://clinica-oncologica-v02-production.up.railway.app/api/v1
```
✅ Tem `https://` e `/api/v1`

#### **VITE_API_BASE_PATH**
```
/api/v1
```
✅ Tem `/` no início

#### **VITE_WS_BASE_URL**
```
wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
```
✅ Tem `wss://` e `/ws/connect`

#### **VITE_WS_URL**
```
wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
```
✅ Tem `wss://` e `/ws/connect`

---

### **Comandos Railway CLI para Atualizar Frontend:**

```bash
# Atualizar cada variável (copiar/colar uma por vez)
railway variables --set VITE_API_BASE_URL="https://clinica-oncologica-v02-production.up.railway.app"

railway variables --set VITE_API_URL="https://clinica-oncologica-v02-production.up.railway.app/api/v1"

railway variables --set VITE_API_BASE_PATH="/api/v1"

railway variables --set VITE_WS_BASE_URL="wss://clinica-oncologica-v02-production.up.railway.app/ws/connect"

railway variables --set VITE_WS_URL="wss://clinica-oncologica-v02-production.up.railway.app/ws/connect"
```

---

### **Etapa 4: Listar Variáveis Atuais do Backend**

```bash
# Listar todos os services para encontrar o backend
railway service

# Listar variáveis do backend (ajustar nome do service se necessário)
railway variables --service <BACKEND_SERVICE_NAME>
```

---

### **Etapa 5: Corrigir Variáveis do Backend**

**Copie e cole EXATAMENTE esses valores:**

#### **DATABASE_URL**
```
postgresql+psycopg://postgres.rszpypytdciggybbpnrp:NvbKfi1xMY7wzNof@aws-0-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require
```
✅ Tem `://` após `psycopg`
✅ Tem `/postgres` antes de `?`
✅ Tem `?sslmode=require` no final

#### **SUPABASE_URL**
```
https://rszpypytdciggybbpnrp.supabase.co
```
✅ Tem `https://`

#### **EVOLUTION_API_URL**
```
https://evolution-api-production.up.railway.app
```
✅ Tem `https://`

#### **EVOLUTION_WEBHOOK_URL**
```
https://clinica-oncologica-v02-production.up.railway.app/webhook/evolution
```
✅ Tem `https://` e `/webhook/evolution`

#### **ALLOWED_ORIGINS** (JSON array)
```json
["https://frontend-production-18bb.up.railway.app","https://clinica-oncologica-v02-production.up.railway.app"]
```
✅ Cada URL tem `https://`

#### **FRONTEND_URL**
```
https://frontend-production-18bb.up.railway.app
```
✅ Tem `https://`

#### **FRONTEND_API_URL** (se existir)
```
https://clinica-oncologica-v02-production.up.railway.app/api/v1
```
✅ Tem `https://` e `/api/v1`

---

### **Comandos Railway CLI para Atualizar Backend:**

```bash
# Atualizar DATABASE_URL
railway variables --set DATABASE_URL="postgresql+psycopg://postgres.rszpypytdciggybbpnrp:NvbKfi1xMY7wzNof@aws-0-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require"

# Atualizar SUPABASE_URL
railway variables --set SUPABASE_URL="https://rszpypytdciggybbpnrp.supabase.co"

# Atualizar EVOLUTION_API_URL
railway variables --set EVOLUTION_API_URL="https://evolution-api-production.up.railway.app"

# Atualizar EVOLUTION_WEBHOOK_URL
railway variables --set EVOLUTION_WEBHOOK_URL="https://clinica-oncologica-v02-production.up.railway.app/webhook/evolution"

# Atualizar ALLOWED_ORIGINS (atenção às aspas)
railway variables --set ALLOWED_ORIGINS='["https://frontend-production-18bb.up.railway.app","https://clinica-oncologica-v02-production.up.railway.app"]'

# Atualizar FRONTEND_URL
railway variables --set FRONTEND_URL="https://frontend-production-18bb.up.railway.app"

# Atualizar FRONTEND_API_URL (se existir)
railway variables --set FRONTEND_API_URL="https://clinica-oncologica-v02-production.up.railway.app/api/v1"
```

---

### **Etapa 6: Verificar Correções**

```bash
# Verificar frontend novamente
railway variables --service frontend-production-18bb

# Verificar backend novamente
railway variables --service <BACKEND_SERVICE_NAME>
```

**Procurar por:**
- ✅ Todas URLs com `https://` ou `wss://` (não `https:` ou `wss:`)
- ✅ DATABASE_URL com `://`, `/postgres`, `?sslmode=require`
- ✅ Todas variáveis de path com `/` no início

---

### **Etapa 7: Triggerar Redeploy**

```bash
# Redeploy do frontend
railway up --service frontend-production-18bb --detach

# Redeploy do backend
railway up --service <BACKEND_SERVICE_NAME> --detach
```

**Ou via Railway Dashboard:**
1. Ir em "Deployments"
2. Clicar em "Redeploy" no último deploy
3. Aguardar build completar (~2-3 minutos)

---

## 🔍 Validação Pós-Correção

### **1. Logs do Frontend (Railway Dashboard)**
```
✅ Deve exibir:
API URL: https://clinica-oncologica-v02-production.up.railway.app/api/v1
WS URL: wss://clinica-oncologica-v02-production.up.railway.app/ws/connect

❌ NÃO deve exibir:
API URL: https:clinica...apiv1
WS URL: wss:clinica...wsconnect
```

### **2. Logs do Backend (Railway Dashboard)**
```
✅ Deve exibir:
Database connected to postgres at aws-0-sa-east-1.pooler.supabase.com:5432

❌ NÃO deve exibir:
psycopg.OperationalError: connection failed
SSL connection required
```

### **3. Teste no Browser**
1. Abrir https://frontend-production-18bb.up.railway.app
2. Hard refresh: `Ctrl+Shift+R` (Windows) ou `Cmd+Shift+R` (Mac)
3. Abrir DevTools → Console
4. Fazer login com credenciais de teste
5. ✅ **Login deve completar em 2-3 segundos**
6. ✅ **Não deve ficar em "loading infinito"**

### **4. DevTools Network Tab**
Procurar por:
- ✅ Request para `https://clinica.../api/v1/auth/me` → status 200
- ✅ WebSocket para `wss://clinica.../ws/connect?token=...` → status 101 (Switching Protocols)
- ❌ **NÃO** deve ter status 404, 401, ou "Invalid URL"

---

## 🚨 Troubleshooting

### **Problema 1: Railway CLI não encontra service**
```bash
# Listar todos os services disponíveis
railway service

# Copiar nome EXATO do service
# Usar nome exato no comando --service
```

### **Problema 2: Variável não aceita valor**
```bash
# Tentar via Railway Dashboard Web:
# 1. Ir em Settings → Variables
# 2. Editar variável manualmente
# 3. Colar valor exato
# 4. Salvar
```

### **Problema 3: Redeploy não funciona via CLI**
```bash
# Usar Railway Dashboard Web:
# 1. Ir em "Deployments"
# 2. Último deploy → "..." → "Redeploy"
```

---

## 📊 Checklist Final

**Frontend Variables** (5 de 5):
- [ ] `VITE_API_BASE_URL` com `https://`
- [ ] `VITE_API_URL` com `https://` e `/api/v1`
- [ ] `VITE_API_BASE_PATH` com `/api/v1`
- [ ] `VITE_WS_BASE_URL` com `wss://` e `/ws/connect`
- [ ] `VITE_WS_URL` com `wss://` e `/ws/connect`

**Backend Variables** (7 de 7):
- [ ] `DATABASE_URL` com `://`, `/postgres`, `?sslmode=require`
- [ ] `SUPABASE_URL` com `https://`
- [ ] `EVOLUTION_API_URL` com `https://`
- [ ] `EVOLUTION_WEBHOOK_URL` com `https://` e `/webhook/evolution`
- [ ] `ALLOWED_ORIGINS` JSON com `https://` em cada URL
- [ ] `FRONTEND_URL` com `https://`
- [ ] `FRONTEND_API_URL` com `https://` e `/api/v1` (se existir)

**Redeploy Triggered**:
- [ ] Frontend redeployado
- [ ] Backend redeployado

**Validation**:
- [ ] Logs do frontend mostram URLs corretas
- [ ] Logs do backend mostram database conectado
- [ ] Login completa em 2-3 segundos
- [ ] WebSocket conecta (status 101)

---

## 🎯 Resumo Executivo

**O que fazer:**
1. Executar `railway link` e selecionar projeto
2. Copiar/colar os 12 comandos `railway variables --set` listados acima
3. Triggerar redeploy de ambos os services
4. Testar login no browser

**Tempo estimado:** 10-15 minutos

**Resultado esperado:** Login funciona em 2-3 segundos, sem "loading infinito"

---

**Última Atualização**: 2025-10-06
**Autor**: Claude Code - Wave 3 Deployment Fix
**Status**: ⏳ Aguardando execução manual dos comandos Railway CLI
