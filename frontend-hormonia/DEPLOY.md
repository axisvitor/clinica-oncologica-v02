# Frontend Hormonia - Railway Deployment Guide

## 🚀 Deploy Standalone (Pasta Única)

Este guia é para fazer deploy **APENAS** do frontend como serviço independente.

---

## 📋 Pré-requisitos

1. Conta no Railway
2. Backend já deployed (para obter URL)
3. Credenciais do Supabase (apenas chaves públicas)

---

## 🔧 Passo 1: Criar Serviço no Railway

1. Acesse [Railway](https://railway.app)
2. Click "New Project" (ou use projeto existente)
3. Selecione "Deploy from GitHub repo"
4. Conecte seu repositório
5. **IMPORTANTE**: Defina **Root Directory** = `frontend-hormonia`

---

## 🔑 Passo 2: Configurar Variáveis de Ambiente

Copie o conteúdo do arquivo `.env` desta pasta e cole em:
**Settings → Variables → RAW Editor**

### Variáveis CRÍTICAS (substitua os placeholders)

```bash
# BACKEND CONNECTION (obter após deploy do backend)
VITE_API_URL=https://<backend-domain>.up.railway.app
VITE_API_BASE_URL=https://<backend-domain>.up.railway.app
VITE_WS_URL=wss://<backend-domain>.up.railway.app/ws
VITE_WS_BASE_URL=wss://<backend-domain>.up.railway.app/ws

# SUPABASE (mesmas chaves do backend - PÚBLICAS)
VITE_SUPABASE_URL=https://<seu-projeto>.supabase.co
VITE_SUPABASE_ANON_KEY=<anon-key-publico>
```

### Variáveis JÁ CONFIGURADAS no .env
```bash
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false
VITE_APP_NAME=Hormonia - Sistema de Gestão Oncológica
VITE_ENABLE_WHATSAPP_INTEGRATION=true
VITE_ENABLE_AI_CHAT=true
# ... (130+ variáveis pré-configuradas)
```

---

## 📦 Passo 3: Deploy

1. Railway detectará `railway.json` automaticamente
2. Build usará `Dockerfile` (Multi-stage: Node 20 build + Nginx runtime)
3. Nginx servirá arquivos estáticos e fará proxy para backend
4. Healthcheck: `GET /health` (timeout 120s)

### Build Process
```
Stage 1: Build (Node 20-alpine)
  → npm install
  → npm build (Vite)

Stage 2: Runtime (nginx:alpine)
  → Copia build/
  → Configura Nginx
  → Injeta BACKEND_URL em runtime
```

---

## ✅ Passo 4: Verificar Health

Após deploy bem-sucedido:

```bash
curl https://<seu-dominio>.up.railway.app/health
```

Resposta esperada:
```
200 OK
```

---

## 🔄 Passo 5: Atualizar Backend CORS

Volte ao **backend** e adicione a URL do frontend:

```bash
ALLOWED_ORIGINS=["https://<frontend-domain>.up.railway.app","..."]
FRONTEND_URL=https://<frontend-domain>.up.railway.app
```

Redeploy o backend.

---

## 🌐 Arquitetura

```
┌─────────────────────────────────────┐
│     Railway Project                  │
├─────────────────────────────────────┤
│                                      │
│  ┌──────────────┐                   │
│  │   frontend   │  Port: 3000       │
│  │   (Nginx)    │  /health          │
│  └──────────────┘                   │
│         │                            │
│         │ Proxy /api → Backend      │
│         │ Proxy /ws  → Backend WS   │
│         │                            │
│         ├─ Vite Build (React)       │
│         ├─ Nginx (Static + Proxy)   │
│         └─ Supabase Client (Auth)   │
└─────────────────────────────────────┘
```

---

## 🔧 Nginx Configuration

O `nginx.conf` está configurado para:

1. **Servir arquivos estáticos** do build Vite
2. **Proxy `/api/`** para backend (VITE_API_URL)
3. **Proxy `/ws`** para backend WebSocket
4. **Health endpoint** em `/health` (200 OK)
5. **Injeção de variáveis** via entrypoint script

### Configuração Dinâmica

O `docker-entrypoint.sh` injeta `BACKEND_URL` em tempo de execução:
- Lê variável de ambiente `BACKEND_URL`
- Substitui `${BACKEND_URL}` no nginx.conf
- Ajusta `PORT` se Railway definir diferente de 3000

---

## 🐛 Troubleshooting

### "API calls failing (CORS)"
→ Adicione frontend URL no backend `ALLOWED_ORIGINS`

### "502 Bad Gateway on /api requests"
→ Verifique se `VITE_API_URL` está correto e backend está online

### "Build fails"
→ Verifique `package.json` scripts: `build` deve existir

### "Nginx permission denied on entrypoint"
→ Dockerfile já inclui `chmod +x /docker-entrypoint.sh`

---

## 📁 Arquivos Importantes

- `Dockerfile` - Multi-stage build (Node → Nginx)
- `nginx.conf` - Configuração Nginx (proxy + static)
- `railway.json` - Configuração Railway
- `.env` - Variáveis de ambiente (NÃO commitar)
- `package.json` - Dependências e scripts
- `vite.config.ts` - Configuração Vite

---

## 🔒 Segurança

- [ ] `.env` está no `.gitignore`
- [ ] Apenas variáveis `VITE_*` são públicas (seguro)
- [ ] CORS configurado no backend
- [ ] HTTPS forçado (Nginx + Railway SSL)
- [ ] Headers de segurança configurados

---

## 🎨 Customização

### Branding
Edite no `.env`:
```bash
VITE_CLINIC_NAME=Sua Clínica
VITE_CLINIC_PHONE=+55 11 99999-9999
VITE_CLINIC_EMAIL=contato@suaclinica.com.br
```

### Features
Toggle features no `.env`:
```bash
VITE_ENABLE_AI_CHAT=true/false
VITE_ENABLE_WHATSAPP_INTEGRATION=true/false
VITE_ENABLE_TELEMEDICINE=true/false
```

---

**Deployment Type**: Standalone Service
**Builder**: Docker (Multi-stage: Node 20 + Nginx)
**Runtime**: Nginx Alpine
**Health Check**: GET /health (120s timeout)
