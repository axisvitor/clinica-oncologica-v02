# Environment Variables Guide

Guia completo das variáveis de ambiente para as 3 pastas principais do sistema.

## 📁 Estrutura de Arquivos .env

```
clinica-oncologica-v02/
├── frontend-hormonia/
│   ├── .env                 # Production/Development config
│   └── .env.example         # Template with placeholders
├── backend-hormonia/
│   ├── .env                 # Production/Development config
│   └── .env.example         # Template with placeholders
└── quiz-mensal-interface/
    ├── .env                 # Production/Development config
    └── .env.example         # Template with placeholders
```

---

## 🎨 Frontend Hormonia - Variáveis Críticas

### ⚠️ Variáveis OBRIGATÓRIAS Atualizadas

#### API Configuration (CRITICAL FIXES)
```bash
# ✅ NOVO: Base URL sem /api/v1 (usado para construir URLs completas)
VITE_API_BASE_URL="http://localhost:8000"

# ✅ ATUALIZADO: Full API URL com /api/v1 (suporte legado)
VITE_API_URL="http://localhost:8000/api/v1"
```

**Por que 2 variáveis?**
- `VITE_API_BASE_URL`: URL base limpa, sem sufixo `/api/v1`
  - Usado em: `config-initializer.tsx`, `WhatsAppService.ts`
  - Previne duplicação: evita `/api/v1/api/v1/...`

- `VITE_API_URL`: URL completa com `/api/v1` (legado)
  - Compatibilidade com código antigo
  - Será deprecado futuramente

#### WebSocket Configuration (CRITICAL FIXES)
```bash
# ✅ NOVO: Base URL padrão (alias para VITE_WS_URL)
VITE_WS_BASE_URL="ws://localhost:8000/ws"

# ✅ ATUALIZADO: URL WebSocket (porta 8000, não 8080!)
VITE_WS_URL="ws://localhost:8000/ws"
```

**Por que 2 variáveis?**
- Ambas apontam para o mesmo endereço
- `VITE_WS_BASE_URL`: Nova convenção padronizada
- `VITE_WS_URL`: Compatibilidade com código legado
- **Porta correta**: 8000 (mesma do backend, NÃO 8080)

### Exemplo de .env Completo (Frontend)

```bash
# API Configuration
VITE_API_BASE_URL="http://localhost:8000"
VITE_API_URL="http://localhost:8000/api/v1"
VITE_API_TIMEOUT="30000"

# WebSocket Configuration
VITE_WS_BASE_URL="ws://localhost:8000/ws"
VITE_WS_URL="ws://localhost:8000/ws"

# Supabase
VITE_SUPABASE_URL="https://xxx.supabase.co"
VITE_SUPABASE_ANON_KEY="eyJhbGci..."
VITE_SUPABASE_REALTIME_ENABLED="true"

# Firebase
VITE_FIREBASE_API_KEY="AIza..."
VITE_FIREBASE_AUTH_DOMAIN="xxx.firebaseapp.com"
VITE_FIREBASE_PROJECT_ID="xxx"

# Application
VITE_ENVIRONMENT="production"
VITE_APP_NAME="Hormonia - Sistema de Gestão Oncológica"
VITE_APP_VERSION="2.0.0"

# WhatsApp
VITE_WHATSAPP_INSTANCE_NAME="hormonia-instance"
```

---

## 🔧 Backend Hormonia - Variáveis Críticas

### ⚠️ Variáveis OBRIGATÓRIAS

```bash
# Environment
ENVIRONMENT=production
DEBUG=False

# Security Keys
SECRET_KEY=<gerado com python -c "import secrets; print(secrets.token_urlsafe(64))">
JWT_SECRET_KEY=<gerado com python -c "import secrets; print(secrets.token_urlsafe(64))">

# Database
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname

# Redis
REDIS_URL=redis://default:password@host:port
REDIS_SSL=false  # CRITICAL: Set to false for non-SSL Redis

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGci...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...

# Firebase Admin
FIREBASE_ADMIN_PROJECT_ID=xxx
FIREBASE_ADMIN_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\nMII...\n-----END PRIVATE KEY-----
FIREBASE_ADMIN_CLIENT_EMAIL=xxx@xxx.iam.gserviceaccount.com

# Gemini AI
GEMINI_API_KEY=AIza...

# Evolution API (WhatsApp)
EVOLUTION_API_KEY=xxx
EVOLUTION_INSTANCE_NAME=clinica_oncologica
EVOLUTION_API_URL=https://evolution.axisvanguard.site

# File Upload (NEW)
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE=10485760
```

### ✅ NOVA Configuração de Upload

```bash
# File Upload Settings
UPLOAD_DIR=uploads                # Diretório para arquivos (relativo ou absoluto)
MAX_UPLOAD_SIZE=10485760          # 10MB em bytes (10 * 1024 * 1024)
```

**Endpoint criado:**
- `POST /api/v1/upload/media` - Upload de arquivos
- `DELETE /api/v1/upload/media?url=...` - Deletar arquivo
- `GET /api/v1/upload/media/info?url=...` - Info do arquivo

---

## 📝 Quiz Mensal Interface - Variáveis Críticas

### ⚠️ Variáveis OBRIGATÓRIAS

```bash
# Backend API (CRITICAL)
NEXT_PUBLIC_API_URL=https://clinica-oncologica-v02-production.up.railway.app

# Runtime
NODE_ENV=production
NEXT_TELEMETRY_DISABLED=1

# Monitoring (Optional)
NEXT_PUBLIC_SENTRY_DSN={{YOUR_SENTRY_DSN}}
NEXT_PUBLIC_GOOGLE_ANALYTICS_ID={{YOUR_ANALYTICS_ID}}
```

---

## 🚀 Railway Deployment - Variáveis Específicas

### Frontend Hormonia (Railway)
```bash
VITE_API_BASE_URL="https://clinica-oncologica-v02-production.up.railway.app"
VITE_API_URL="https://clinica-oncologica-v02-production.up.railway.app/api/v1"
VITE_WS_BASE_URL="wss://clinica-oncologica-v02-production.up.railway.app/ws"
VITE_WS_URL="wss://clinica-oncologica-v02-production.up.railway.app/ws"
```

### Backend Hormonia (Railway)
```bash
ENVIRONMENT=production
DEBUG=False
DATABASE_URL=${{Postgres.DATABASE_URL}}  # Railway internal variable
REDIS_URL=${{Redis.REDIS_URL}}           # Railway internal variable
FRONTEND_URL=https://hormonia.neoplasiaslitoral.com.br
ALLOWED_ORIGINS=["https://hormonia.neoplasiaslitoral.com.br"]
```

---

## 📋 Checklist de Deploy

### Antes do Deploy

- [ ] Todas as variáveis OBRIGATÓRIAS preenchidas
- [ ] `VITE_API_BASE_URL` e `VITE_WS_BASE_URL` corretas (frontend)
- [ ] Porta WebSocket é 8000 (não 8080)
- [ ] Keys de produção (não development)
- [ ] `REDIS_SSL=false` para Redis sem SSL
- [ ] URLs do Railway atualizadas
- [ ] Secrets não estão hardcoded no código

### Validar Configuração

```bash
# Frontend
cd frontend-hormonia
grep -E "VITE_API_BASE_URL|VITE_WS_BASE_URL" .env

# Backend
cd backend-hormonia
grep -E "UPLOAD_DIR|MAX_UPLOAD_SIZE|REDIS_SSL" .env

# Quiz
cd quiz-mensal-interface
grep "NEXT_PUBLIC_API_URL" .env
```

---

## 🔍 Troubleshooting

### Erro: "Cannot connect to API"
**Causa**: `VITE_API_BASE_URL` incorreta ou contém `/api/v1` duplicado
**Solução**: Usar `VITE_API_BASE_URL` sem `/api/v1` no final

### Erro: "WebSocket connection failed"
**Causa**: Porta 8080 em vez de 8000, ou protocolo errado (ws/wss)
**Solução**: `VITE_WS_BASE_URL="ws://localhost:8000/ws"` (desenvolvimento)

### Erro: "SSL: WRONG_VERSION_NUMBER" (Redis)
**Causa**: `REDIS_SSL=true` mas Redis não usa SSL
**Solução**: `REDIS_SSL=false`

### Erro: "Upload failed"
**Causa**: `UPLOAD_DIR` ou `MAX_UPLOAD_SIZE` não configurados
**Solução**: Adicionar variáveis no backend `.env`

---

## 📖 Referências

- [FRONTEND_BACKEND_FIXES.md](./FRONTEND_BACKEND_FIXES.md) - Correções de conexão
- [TYPESCRIPT_FIXES.md](./TYPESCRIPT_FIXES.md) - Configuração TypeScript
- [Railway Docs](https://docs.railway.app/) - Deploy Railway
- [Vite Env Docs](https://vitejs.dev/guide/env-and-mode.html) - Variáveis Vite

---

**Última atualização:** 2025-10-05
**Status:** ✅ Documentação completa e atualizada
